"""card_detector.py

Locate a trading card in a photograph and return a deskewed, top-down crop.

Pipeline (classic OpenCV, no ML):

    grayscale -> blur -> Canny edges -> dilate -> find contours
    -> pick the largest 4-point (quadrilateral) contour
    -> order its corners -> perspective transform to a flat, top-down image.

ALL downstream measurements (centering, and later corners/edges/surface) run on
the *rectified* image returned here, so camera rotation and perspective skew do
not corrupt the border-width measurements.

IMAGING ASSUMPTION (documented and important):
    The card is photographed roughly flat, filling a good portion of the frame,
    against a PLAIN, HIGH-CONTRAST background (e.g. a dark card on a white desk,
    or a light card on a dark mat). The detector finds the card as the largest
    bright/dark quadrilateral. A busy background, glare, or a card whose colour
    matches the background will make detection unreliable -- see README.

The tunable parameters live as CONSTANTS at the top of the file so they can be
adjusted for different cameras / lighting without hunting through the code.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Tunable constants -- adjust these for your camera / lighting / card type.
# ---------------------------------------------------------------------------

# Gaussian blur kernel applied before edge detection. Larger = more smoothing,
# which suppresses texture/noise but can soften the card's true edge.
BLUR_KERNEL: tuple[int, int] = (5, 5)

# Canny hysteresis thresholds for the OUTER card edge. The card edge against a
# high-contrast background is a strong gradient, so these can be fairly high.
CANNY_LOW: int = 50
CANNY_HIGH: int = 150

# Edges are dilated to close small gaps so findContours sees one closed loop
# instead of a broken outline. Iterations of a 3x3 dilation.
EDGE_DILATE_ITERS: int = 2

# A candidate contour is only accepted as "the card" if it encloses at least
# this fraction of the whole image area. Stops us locking onto small specks.
MIN_CARD_AREA_FRAC: float = 0.10

# ...and no MORE than this fraction. A real card photo always leaves some
# background around the card, so a "card" that spans essentially the entire
# frame is almost always a detection artifact (e.g. a busy/noisy background
# whose dilated edges fill the image). Such candidates are skipped.
MAX_CARD_AREA_FRAC: float = 0.985

# approxPolyDP epsilon as a fraction of the contour perimeter. Controls how
# aggressively the outline is simplified toward a 4-point polygon. ~0.02 is the
# usual sweet spot; raise it if a slightly rounded card refuses to reduce to 4
# corners, lower it if a busy outline collapses too far.
APPROX_EPSILON_FRAC: float = 0.02

# To keep processing fast and consistent, the input is downscaled so its longest
# side is at most this many pixels before detection. The returned rectified card
# is produced from this (possibly downscaled) image. Set high enough to preserve
# border detail; lower it if processing feels slow.
MAX_PROCESS_DIM: int = 2000


class CardDetectionError(Exception):
    """Raised when no card-like quadrilateral can be found in the image.

    The UI catches this and shows a friendly explanation (poor contrast, busy
    background, glare, card too small in frame, ...) instead of crashing.
    """


@dataclass
class CardDetection:
    """Result of :func:`detect_card`.

    Attributes:
        rectified: The deskewed, top-down BGR crop of just the card. All
            downstream measurements run on this image.
        corners: The four outer-edge corner points (in the coordinate space of
            ``source``), ordered top-left, top-right, bottom-right, bottom-left.
        source: The (possibly downscaled) image the corners refer to. Handy for
            drawing the detected outline back onto the photo in the UI.
    """

    rectified: np.ndarray
    corners: np.ndarray
    source: np.ndarray


def _resize_to_max_dim(image: np.ndarray, max_dim: int) -> np.ndarray:
    """Downscale ``image`` so its longest side is at most ``max_dim`` pixels.

    Upscaling is never performed -- small images are returned untouched.
    """
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest <= max_dim:
        return image
    scale = max_dim / float(longest)
    new_size = (int(round(w * scale)), int(round(h * scale)))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)


def order_points(pts: np.ndarray) -> np.ndarray:
    """Order four points as top-left, top-right, bottom-right, bottom-left.

    Uses the classic trick: the top-left point has the smallest (x + y) sum and
    the bottom-right the largest; the top-right has the smallest (y - x)
    difference and the bottom-left the largest. Works for any rotation up to the
    point where "top" and "side" would swap (which a card photo never reaches).
    """
    pts = pts.reshape(4, 2).astype("float32")
    ordered = np.zeros((4, 2), dtype="float32")

    s = pts.sum(axis=1)
    ordered[0] = pts[np.argmin(s)]  # top-left  : min x + y
    ordered[2] = pts[np.argmax(s)]  # bottom-right: max x + y

    diff = np.diff(pts, axis=1).ravel()  # y - x for each point
    ordered[1] = pts[np.argmin(diff)]  # top-right   : min y - x
    ordered[3] = pts[np.argmax(diff)]  # bottom-left : max y - x
    return ordered


def four_point_transform(image: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Perspective-warp the quadrilateral ``pts`` into a top-down rectangle.

    The output size is derived from the measured edge lengths of the detected
    quad, so the rectified card keeps (approximately) the card's true aspect
    ratio instead of being squashed into a fixed shape.
    """
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    # Width = max of the two horizontal edges; height = max of the two vertical
    # edges. Using max (not min/avg) avoids cropping into the artwork.
    width_top = np.linalg.norm(tr - tl)
    width_bottom = np.linalg.norm(br - bl)
    max_width = int(round(max(width_top, width_bottom)))

    height_left = np.linalg.norm(bl - tl)
    height_right = np.linalg.norm(br - tr)
    max_height = int(round(max(height_left, height_right)))

    # Guard against degenerate detections that would crash warpPerspective.
    if max_width < 2 or max_height < 2:
        raise CardDetectionError(
            "Detected card region is too small to rectify -- the card may be "
            "too far away or too low-contrast against the background."
        )

    dst = np.array(
        [
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1],
        ],
        dtype="float32",
    )

    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, matrix, (max_width, max_height))


def _find_card_contour(edges: np.ndarray, image_area: float) -> np.ndarray:
    """Return the four corner points of the largest card-like quadrilateral.

    Scans contours from largest to smallest, simplifies each to a polygon, and
    accepts the first convex 4-point polygon that is large enough to plausibly
    be the card. Raises :class:`CardDetectionError` if none qualify.
    """
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise CardDetectionError(
            "No edges/contours were found at all. The image is likely very "
            "low-contrast or out of focus."
        )

    # Largest contours first -- the card is expected to be the biggest object.
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < MIN_CARD_AREA_FRAC * image_area:
            # Once we drop below the minimum area, every later (smaller) contour
            # is also too small, so we can stop early.
            break
        if area > MAX_CARD_AREA_FRAC * image_area:
            # Spans (almost) the whole frame -> no background visible, treat as
            # an artifact and try the next-largest contour instead.
            continue

        perimeter = cv2.arcLength(contour, closed=True)
        approx = cv2.approxPolyDP(contour, APPROX_EPSILON_FRAC * perimeter, closed=True)

        if len(approx) == 4 and cv2.isContourConvex(approx):
            return approx.reshape(4, 2)

    raise CardDetectionError(
        "Could not find a 4-cornered card shape large enough in the frame. "
        "Make sure the whole card is visible, fills much of the frame, and "
        "sits on a plain, high-contrast background."
    )


def detect_card(image: np.ndarray) -> CardDetection:
    """Detect the card in ``image`` and return a rectified top-down crop.

    Args:
        image: A BGR image (as loaded by OpenCV) of a card on a plain,
            high-contrast background.

    Returns:
        A :class:`CardDetection` with the rectified crop and the outer corners.

    Raises:
        CardDetectionError: If no suitable card quadrilateral can be located.
    """
    if image is None or image.size == 0:
        raise CardDetectionError("No image data was provided.")

    source = _resize_to_max_dim(image, MAX_PROCESS_DIM)

    gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, BLUR_KERNEL, 0)
    edges = cv2.Canny(blurred, CANNY_LOW, CANNY_HIGH)

    # Close small gaps in the outline so the card forms one continuous contour.
    if EDGE_DILATE_ITERS > 0:
        edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=EDGE_DILATE_ITERS)

    image_area = float(source.shape[0] * source.shape[1])
    corners = _find_card_contour(edges, image_area)

    rectified = four_point_transform(source, corners)
    ordered_corners = order_points(corners)

    return CardDetection(rectified=rectified, corners=ordered_corners, source=source)
