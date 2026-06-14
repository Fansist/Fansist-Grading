"""centering.py

Measure how well a trading card's artwork is centered inside its border.

Input is the *rectified* (deskewed, top-down) card image from
``card_detector.detect_card``. On that image we locate the INNER border -- the
rectangle where the outer margin meets the inner artwork/frame -- and measure
the four margin widths in pixels:

        +----------------------------+   <- outer card edge (the image border)
        |          top               |
        |     +----------------+     |
        | left|   artwork      |right|   <- inner border (what we detect)
        |     +----------------+     |
        |         bottom             |
        +----------------------------+

From those widths we compute the standard centering ratios:

        horizontal centering = left : right   (normalised so the pair sums 100)
        vertical   centering = top  : bottom

A perfectly centered card is 50/50 on both axes.

WHY THIS IS THE FLAKY STEP
--------------------------
Inner-border appearance varies enormously between cards: some have a crisp white
frame, some a coloured frame, some bleed the artwork almost to the edge. There
is no single threshold that works for every card, so the tunable parameters are
exposed as CONSTANTS below and TWO detection strategies are provided:

    * "gradient" (default, general purpose): finds the strongest straight edge
      running parallel to each side. Works on most cards because the inner frame
      is a strong, straight gradient.

    * "color": for cards with a solid, uniform border colour (classic white or
      yellow borders). Scans inward until the border colour stops dominating.
      Often more accurate on those cards; set INNER_BORDER_METHOD = "color" and
      tune EXPECTED_BORDER_HSV_LOW/HIGH.

Both are fully implemented; pick per card type with INNER_BORDER_METHOD.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Detection strategy
# ---------------------------------------------------------------------------

# "gradient" -> edge-projection method (default, works on most cards).
# "color"    -> solid-border-colour method (best for uniform white/yellow borders).
INNER_BORDER_METHOD: str = "gradient"

# ---------------------------------------------------------------------------
# Search geometry (shared by both methods)
# ---------------------------------------------------------------------------

# Ignore this fraction of the card nearest each outer edge when looking for the
# inner border. The perspective warp can leave a sliver of background or the
# card's own outer edge right at the boundary; skipping it avoids false hits.
EDGE_IGNORE_FRAC: float = 0.01

# Only search for each side's inner border within this fraction of the card,
# measured inward from that side. 0.45 means "the inner border is expected
# somewhere in the outer 45% of the card". Keeping it below 0.5 stops the left
# search from wandering past the centre and grabbing the right border.
SEARCH_MARGIN_FRAC: float = 0.45

# ---------------------------------------------------------------------------
# "gradient" method parameters
# ---------------------------------------------------------------------------

# Smoothing applied before computing gradients, to suppress artwork texture so
# the true frame edge stands out in the projection profile.
GRADIENT_BLUR_KERNEL: tuple[int, int] = (5, 5)

# Sobel aperture size used to compute directional gradients.
SOBEL_KSIZE: int = 3

# ---------------------------------------------------------------------------
# "color" method parameters
# ---------------------------------------------------------------------------

# Expected border colour range in HSV (OpenCV ranges: H 0-179, S 0-255,
# V 0-255). The default is a permissive "bright / near-white" range suitable for
# white-bordered cards. For a yellow Pokemon border, try roughly
# H 20-35, S 80-255, V 120-255. Tune these to your card.
EXPECTED_BORDER_HSV_LOW: tuple[int, int, int] = (0, 0, 150)
EXPECTED_BORDER_HSV_HIGH: tuple[int, int, int] = (179, 60, 255)

# A column/row is considered "still in the border" while at least this fraction
# of its pixels (within the frame band) match the border colour. The inner
# border is the position where this drops below the threshold.
BORDER_PRESENCE_THRESHOLD: float = 0.80


@dataclass
class CenteringResult:
    """Border-width measurements and centering ratios for a rectified card.

    Attributes:
        left, right, top, bottom: Margin widths in pixels.
        horizontal_ratio: (left%, right%) normalised to sum 100.
        vertical_ratio:   (top%, bottom%) normalised to sum 100.
        inner_rect: (x_left, y_top, x_right, y_bottom) pixel coordinates of the
            detected inner border on the rectified image -- used for drawing.
        method: Which detection strategy produced the result.
    """

    left: int
    right: int
    top: int
    bottom: int
    horizontal_ratio: tuple[float, float]
    vertical_ratio: tuple[float, float]
    inner_rect: tuple[int, int, int, int]
    method: str


def _normalise_ratio(a: float, b: float) -> tuple[float, float]:
    """Normalise a pair of widths so they sum to 100 (e.g. 55.0, 45.0).

    If both widths are zero (a degenerate detection) we fall back to a neutral
    50/50 rather than dividing by zero.
    """
    total = a + b
    if total <= 0:
        return (50.0, 50.0)
    return (round(100.0 * a / total, 1), round(100.0 * b / total, 1))


def _band_bounds(length: int) -> tuple[int, int]:
    """Pixel bounds of the search band measured inward from one side.

    Returns ``(ignore, limit)`` so the inner border for the "low" side (left or
    top) is searched in ``[ignore, limit)``, and for the "high" side (right or
    bottom) in ``[length - limit, length - ignore)``.
    """
    ignore = max(1, int(round(length * EDGE_IGNORE_FRAC)))
    limit = max(ignore + 1, int(round(length * SEARCH_MARGIN_FRAC)))
    return ignore, limit


# ---------------------------------------------------------------------------
# Gradient (edge-projection) method
# ---------------------------------------------------------------------------

def _gradient_profiles(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return per-column and per-row edge-strength profiles.

    The column profile sums vertical-edge response down each column, so it
    peaks at x-positions where a strong vertical line (the left/right inner
    frame) runs the height of the card. The row profile is the analogous thing
    for horizontal lines (the top/bottom inner frame).
    """
    sobel_x = np.abs(cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=SOBEL_KSIZE))
    sobel_y = np.abs(cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=SOBEL_KSIZE))
    col_profile = sobel_x.sum(axis=0)  # length = width  -> vertical lines
    row_profile = sobel_y.sum(axis=1)  # length = height -> horizontal lines
    return col_profile, row_profile


def _peak_in_band(profile: np.ndarray, length: int, high_side: bool) -> int:
    """Index of the strongest profile peak within the inward search band.

    Args:
        profile: 1-D edge-strength profile along the axis.
        length: Length of the axis (width for columns, height for rows).
        high_side: False for the left/top side (band hugs the start), True for
            the right/bottom side (band hugs the end).
    """
    ignore, limit = _band_bounds(length)
    if high_side:
        start, stop = length - limit, length - ignore
    else:
        start, stop = ignore, limit
    band = profile[start:stop]
    if band.size == 0:
        # Degenerate: collapse the margin to the edge of the band.
        return start
    return start + int(np.argmax(band))


def _measure_gradient(card_bgr: np.ndarray) -> tuple[int, int, int, int]:
    """Measure (left, right, top, bottom) margins via edge projection."""
    gray = cv2.cvtColor(card_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, GRADIENT_BLUR_KERNEL, 0)
    h, w = gray.shape[:2]

    col_profile, row_profile = _gradient_profiles(gray)

    x_left = _peak_in_band(col_profile, w, high_side=False)
    x_right = _peak_in_band(col_profile, w, high_side=True)
    y_top = _peak_in_band(row_profile, h, high_side=False)
    y_bottom = _peak_in_band(row_profile, h, high_side=True)

    left = x_left
    right = (w - 1) - x_right
    top = y_top
    bottom = (h - 1) - y_bottom
    return left, right, top, bottom


# ---------------------------------------------------------------------------
# Colour (solid-border) method
# ---------------------------------------------------------------------------

def _border_color_fractions(card_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-column and per-row fraction of pixels matching the border colour.

    For a column lying entirely within the left margin, the whole column is
    border colour (it passes through the top, left and bottom frame), so the
    fraction is ~1.0. Once the column crosses the inner border, its middle
    section becomes artwork and the fraction drops sharply -- that drop marks
    the inner border. The same logic applies to rows for the top/bottom margins.
    """
    hsv = cv2.cvtColor(card_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, EXPECTED_BORDER_HSV_LOW, EXPECTED_BORDER_HSV_HIGH)
    col_fraction = mask.mean(axis=0) / 255.0  # length = width
    row_fraction = mask.mean(axis=1) / 255.0  # length = height
    return col_fraction, row_fraction


def _scan_for_drop(fraction: np.ndarray, length: int, high_side: bool) -> int:
    """Margin width where the border-colour fraction first drops below threshold.

    Scans inward from the edge through the search band. Returns the margin width
    in pixels (distance from the outer edge to the inner border).
    """
    ignore, limit = _band_bounds(length)
    if not high_side:
        # Scan left/top: x = ignore .. limit, looking inward.
        for x in range(ignore, limit):
            if fraction[x] < BORDER_PRESENCE_THRESHOLD:
                return x
        return limit
    # Scan right/bottom: walk inward from the far edge.
    for offset in range(ignore, limit):
        x = length - 1 - offset
        if fraction[x] < BORDER_PRESENCE_THRESHOLD:
            return offset
    return limit


def _measure_color(card_bgr: np.ndarray) -> tuple[int, int, int, int]:
    """Measure (left, right, top, bottom) margins via the border-colour mask."""
    h, w = card_bgr.shape[:2]
    col_fraction, row_fraction = _border_color_fractions(card_bgr)

    left = _scan_for_drop(col_fraction, w, high_side=False)
    right = _scan_for_drop(col_fraction, w, high_side=True)
    top = _scan_for_drop(row_fraction, h, high_side=False)
    bottom = _scan_for_drop(row_fraction, h, high_side=True)
    return left, right, top, bottom


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def measure_centering(card_bgr: np.ndarray, method: str | None = None) -> CenteringResult:
    """Measure the four margins and centering ratios of a rectified card.

    Args:
        card_bgr: The rectified, top-down BGR card image.
        method: Override the module default (``INNER_BORDER_METHOD``). One of
            ``"gradient"`` or ``"color"``.

    Returns:
        A :class:`CenteringResult`.

    Raises:
        ValueError: If ``method`` is not a known strategy, or the image is empty.
    """
    if card_bgr is None or card_bgr.size == 0:
        raise ValueError("measure_centering received an empty image.")

    chosen = (method or INNER_BORDER_METHOD).lower()
    if chosen == "gradient":
        left, right, top, bottom = _measure_gradient(card_bgr)
    elif chosen == "color":
        left, right, top, bottom = _measure_color(card_bgr)
    else:
        raise ValueError(
            f"Unknown inner-border method {chosen!r}; expected 'gradient' or 'color'."
        )

    h, w = card_bgr.shape[:2]
    inner_rect = (left, top, (w - 1) - right, (h - 1) - bottom)

    return CenteringResult(
        left=int(left),
        right=int(right),
        top=int(top),
        bottom=int(bottom),
        horizontal_ratio=_normalise_ratio(left, right),
        vertical_ratio=_normalise_ratio(top, bottom),
        inner_rect=inner_rect,
        method=chosen,
    )
