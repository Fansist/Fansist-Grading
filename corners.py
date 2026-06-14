"""corners.py

Assess the four CORNERS of a rectified card for wear.

What this measures (single-image, classic CV): **corner whitening / chipping**.
A worn corner exposes the light cardboard core (whitening) or loses border to a
chip (darkening) near the tip of the card. For each corner we inspect a small
ROI in the BORDER region at that corner and measure the fraction of pixels that
are anomalous relative to the card's border colour (see ``condition_utils``).

To stay reliable we use the centering result's ``inner_rect`` so each corner ROI
sits inside the card's margin (never spilling into the artwork) and is inset a
few pixels from the very edge -- that outermost sliver is dominated by
perspective-warp inaccuracy (a thin background frame), not real damage.

Limitations (be honest):
  * Corner *rounding* is hard to see from a single flat, top-down image (the
    warp fills the corner), so this focuses on the colour-anomaly signal.
  * On white-bordered cards, whitening is invisible; the "darkening" branch
    (chips showing the background) carries the signal instead.
  * Glare reads as false whitening -- even, diffuse light matters.

Returns a per-corner breakdown plus one aggregate ``wear`` in [0, 1]
(0 = pristine, 1 = worst). ``grading.grade_corners`` maps that to a sub-grade.
Tunable CONSTANTS are at the top.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from condition_utils import aggregate_wear, anomaly_mask, border_reference, clamp01, to_hsv

# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------

# Corner ROI size as a fraction of the card's short side (capped to the margin).
CORNER_ROI_FRAC: float = 0.10

# Border-reference sampling band thickness, as a fraction of the short side.
BORDER_BAND_FRAC: float = 0.04

# Skip this fraction of the short side at the very edge -- clears the warp's
# background sliver before inspecting.
EDGE_INSET_FRAC: float = 0.015

# Anomaly thresholds (see condition_utils.anomaly_mask).
BRIGHT_DELTA: float = 45.0   # how much brighter than border counts as whitening
DARK_DELTA: float = 60.0     # how much darker than border counts as a chip
SAT_MAX: float = 70.0        # whitened core is low-saturation

# Anomalous-fraction that maps to full wear (1.0).
WORST_ANOMALY_FRAC: float = 0.35

# How strongly the single worst corner dominates the aggregate (0..1).
AGG_MAX_WEIGHT: float = 0.6

CORNER_NAMES = ("top_left", "top_right", "bottom_right", "bottom_left")


@dataclass
class CornerResult:
    """Per-corner wear, ROI boxes (for drawing), and the aggregate score."""

    wear: float
    per_corner: dict[str, float]
    rois: dict[str, tuple[int, int, int, int]] = field(default_factory=dict)


def _margins(
    h: int, w: int, inner_rect: tuple[int, int, int, int] | None
) -> tuple[int, int, int, int]:
    """(left, right, top, bottom) border widths from the inner rectangle.

    Falls back to a nominal 8% margin when centering info isn't supplied.
    """
    if inner_rect is None:
        return int(w * 0.08), int(w * 0.08), int(h * 0.08), int(h * 0.08)
    x0, y0, x1, y1 = inner_rect
    return x0, (w - 1) - x1, y0, (h - 1) - y1


def _corner_rois(
    h: int, w: int, margins: tuple[int, int, int, int], roi_max: int, inset: int
) -> dict[str, tuple[int, int, int, int]]:
    """Corner ROI boxes, each sized to fit inside its margin and inset from the edge."""
    left, right, top, bottom = margins

    def size(*avail: int) -> int:
        # Largest square that fits the tighter of the two adjacent margins.
        return max(3, min(roi_max, min(avail) - inset - 1))

    s_tl, s_tr = size(left, top), size(right, top)
    s_br, s_bl = size(right, bottom), size(left, bottom)
    return {
        "top_left": (inset, inset, inset + s_tl, inset + s_tl),
        "top_right": (w - inset - s_tr, inset, w - inset, inset + s_tr),
        "bottom_right": (w - inset - s_br, h - inset - s_br, w - inset, h - inset),
        "bottom_left": (inset, h - inset - s_bl, inset + s_bl, h - inset),
    }


def assess_corners(
    card_bgr: np.ndarray,
    inner_rect: tuple[int, int, int, int] | None = None,
) -> CornerResult:
    """Assess corner wear on a rectified card image.

    Args:
        card_bgr: Rectified card (BGR).
        inner_rect: (x0, y0, x1, y1) inner border from ``centering`` -- keeps the
            corner ROIs inside the margin. Falls back to a nominal margin if None.
    """
    if card_bgr is None or card_bgr.size == 0:
        raise ValueError("assess_corners received an empty image.")

    h, w = card_bgr.shape[:2]
    short = min(h, w)
    roi_max = max(4, int(round(short * CORNER_ROI_FRAC)))
    band = max(2, int(round(short * BORDER_BAND_FRAC)))
    inset = max(1, int(round(short * EDGE_INSET_FRAC)))

    hsv = to_hsv(card_bgr)
    ref_v, ref_s = border_reference(hsv, band, inset=inset)

    rois = _corner_rois(h, w, _margins(h, w, inner_rect), roi_max, inset)
    per_corner: dict[str, float] = {}
    for name, (x0, y0, x1, y1) in rois.items():
        roi = hsv[y0:y1, x0:x1]
        if roi.size == 0:
            per_corner[name] = 0.0
            continue
        mask = anomaly_mask(roi, ref_v, ref_s, BRIGHT_DELTA, DARK_DELTA, SAT_MAX)
        frac = float(np.count_nonzero(mask)) / float(mask.size)
        per_corner[name] = clamp01(frac / WORST_ANOMALY_FRAC)

    wear = aggregate_wear(list(per_corner.values()), AGG_MAX_WEIGHT)
    return CornerResult(wear=wear, per_corner=per_corner, rois=rois)
