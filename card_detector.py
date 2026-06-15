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

# ---------------------------------------------------------------------------
# Segmentation detector (PRIMARY) -- robust for a card on a plain background.
#
# A card on a high-contrast plain background is best found by *segmenting*
# foreground from background (the card differs from the backdrop colour), then
# fitting the best card-shaped rectangle -- far more robust on real photos than
# edge tracing, which fragments on busy/holo artwork and rounded corners.
# ---------------------------------------------------------------------------

# Standard trading-card aspect ratio (long / short side), 3.5 / 2.5 in.
CARD_ASPECT_RATIO: float = 88.9 / 63.5  # ~1.40

# Accept a detected blob as the card only if its rectangle's aspect ratio is
# within this of the ideal -- this is what tells the card apart from clutter
# (shadows, a display stand) and from random-noise blobs.
ASPECT_TOLERANCE: float = 0.35

# ...and only if the blob fills its own minimum-area rectangle at least this
# much (a real card is solidly rectangular; noise/irregular blobs aren't).
MIN_RECT_FILL: float = 0.72

# Drop near-black foreground pixels (max channel <= this) before fitting, so a
# black display stand / dark prop can't merge with the card. Set 0 to disable
# (e.g. if grading genuinely black-bordered cards).
NEAR_BLACK_MAX: int = 55

# Ignore connected components smaller than this fraction of the image.
SEG_MIN_COMPONENT_FRAC: float = 0.05

# Fraction of the image border sampled to estimate the background colour.
BG_SAMPLE_BORDER_FRAC: float = 0.01


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


def _foreground_mask(source: np.ndarray) -> np.ndarray:
    """Binary mask of the card-ish foreground vs the plain background.

    Estimates the background colour from the image border, marks pixels that
    differ from it (Otsu on the colour-distance map), drops near-black clutter,
    and cleans up with morphology.
    """
    h, w = source.shape[:2]
    band = max(8, int(min(h, w) * BG_SAMPLE_BORDER_FRAC))
    border = np.concatenate([
        source[:band].reshape(-1, 3), source[-band:].reshape(-1, 3),
        source[:, :band].reshape(-1, 3), source[:, -band:].reshape(-1, 3),
    ])
    bg = np.median(border, axis=0)

    dist = np.sqrt(((source.astype(np.float32) - bg) ** 2).sum(axis=2))
    dist = cv2.normalize(dist, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    _, mask = cv2.threshold(cv2.GaussianBlur(dist, (5, 5), 0), 0, 255,
                            cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    if NEAR_BLACK_MAX > 0:
        not_black = (source.max(axis=2) > NEAR_BLACK_MAX).astype(np.uint8) * 255
        mask = cv2.bitwise_and(mask, not_black)

    close_k = max(9, int(min(h, w) * 0.012) | 1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                            np.ones((close_k, close_k), np.uint8), iterations=3)
    return mask


def _rect_metrics(box: np.ndarray) -> tuple[float, float]:
    """(short_side, long_side) lengths of a 4-point rotated rectangle."""
    sides = [np.linalg.norm(box[i] - box[(i + 1) % 4]) for i in range(4)]
    short = float(np.mean(sorted(sides)[:2]))
    long = float(np.mean(sorted(sides)[2:]))
    return short, long


def _detect_by_segmentation(source: np.ndarray) -> np.ndarray | None:
    """Find the card by segmentation; return 4 corner points, or None.

    Picks the connected component whose best-fit rectangle is most card-shaped
    (aspect ~1.40, solidly rectangular, sensible size). Returns None if nothing
    qualifies, so the caller can fall back to edge-based detection.
    """
    h, w = source.shape[:2]
    image_area = float(h * w)
    mask = _foreground_mask(source)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)

    best_box, best_score = None, None
    for i in range(1, count):
        if stats[i, cv2.CC_STAT_AREA] < SEG_MIN_COMPONENT_FRAC * image_area:
            continue
        comp = (labels == i).astype(np.uint8) * 255
        contours, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contour = max(contours, key=cv2.contourArea)

        box = cv2.boxPoints(cv2.minAreaRect(contour)).astype("float32")
        short, long = _rect_metrics(box)
        if short < 2:
            continue
        aspect = long / short
        rect_fill = cv2.contourArea(contour) / (short * long + 1e-6)
        frac = cv2.contourArea(contour) / image_area

        if abs(aspect - CARD_ASPECT_RATIO) > ASPECT_TOLERANCE:
            continue
        if rect_fill < MIN_RECT_FILL:
            continue
        if not (MIN_CARD_AREA_FRAC <= frac <= MAX_CARD_AREA_FRAC):
            continue

        score = abs(aspect - CARD_ASPECT_RATIO)
        if best_score is None or score < best_score:
            best_box, best_score = box, score

    return best_box


def detect_card(image: np.ndarray) -> CardDetection:
    """Detect the card in ``image`` and return a rectified top-down crop.

    Tries segmentation first (robust for a card on a plain background), then
    falls back to edge/contour tracing.

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

    corners = _detect_by_segmentation(source)
    if corners is None:
        # Fallback: classic edge tracing (raises CardDetectionError if it fails).
        gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, BLUR_KERNEL, 0)
        edges = cv2.Canny(blurred, CANNY_LOW, CANNY_HIGH)
        if EDGE_DILATE_ITERS > 0:
            edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=EDGE_DILATE_ITERS)
        corners = _find_card_contour(edges, float(source.shape[0] * source.shape[1]))

    rectified = four_point_transform(source, corners)
    ordered_corners = order_points(corners)

    return CardDetection(rectified=rectified, corners=ordered_corners, source=source)
