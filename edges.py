"""edges.py

Assess the four EDGES of a rectified card for wear (whitening / chipping).

For each edge we inspect a thin band running along that side, *within the border
region* (between the outer edge and the inner border, using the centering
``inner_rect``) and *excluding the corners* (graded by ``corners.py``). Within
each band we count pixels that are anomalous relative to the card's border
colour -- the same whitening/darkening test used for corners.

Like ``corners.py``, the band is inset a few pixels from the very edge so the
perspective-warp sliver (a thin background frame) isn't mistaken for damage.

Returns a per-edge breakdown plus one aggregate ``wear`` in [0, 1];
``grading.grade_edges`` maps that to a sub-grade. Tunable CONSTANTS at the top.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from condition_utils import aggregate_wear, anomaly_mask, border_reference, clamp01, to_hsv

# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------

# Edge band thickness as a fraction of the short side (capped to the margin).
EDGE_BAND_FRAC: float = 0.05

# Skip this fraction of each edge's length at both ends so corners aren't
# re-measured here.
CORNER_SKIP_FRAC: float = 0.10

# Skip this fraction of the short side at the very edge (clears the warp sliver).
EDGE_INSET_FRAC: float = 0.015

# Anomaly thresholds (see condition_utils.anomaly_mask).
BRIGHT_DELTA: float = 45.0
DARK_DELTA: float = 60.0
SAT_MAX: float = 70.0

# Anomalous-fraction of an edge band that maps to full wear (1.0).
WORST_ANOMALY_FRAC: float = 0.25

# How strongly the single worst edge dominates the aggregate (0..1).
AGG_MAX_WEIGHT: float = 0.6

EDGE_NAMES = ("top", "right", "bottom", "left")


@dataclass
class EdgeResult:
    """Per-edge wear, band boxes (for drawing), and the aggregate score."""

    wear: float
    per_edge: dict[str, float]
    bands: dict[str, tuple[int, int, int, int]] = field(default_factory=dict)


def _margins(
    h: int, w: int, inner_rect: tuple[int, int, int, int] | None
) -> tuple[int, int, int, int]:
    """(left, right, top, bottom) border widths from the inner rectangle."""
    if inner_rect is None:
        return int(w * 0.08), int(w * 0.08), int(h * 0.08), int(h * 0.08)
    x0, y0, x1, y1 = inner_rect
    return x0, (w - 1) - x1, y0, (h - 1) - y1


def _edge_bands(
    h: int, w: int, margins: tuple[int, int, int, int],
    band_max: int, inset: int, skip_x: int, skip_y: int,
) -> dict[str, tuple[int, int, int, int]]:
    """Edge band boxes sized to fit inside each margin and inset from the edge."""
    left, right, top, bottom = margins

    def depth(margin: int) -> int:
        return max(3, min(band_max, margin - inset - 1))

    d_top, d_bottom = depth(top), depth(bottom)
    d_left, d_right = depth(left), depth(right)
    return {
        "top": (skip_x, inset, w - skip_x, inset + d_top),
        "bottom": (skip_x, h - inset - d_bottom, w - skip_x, h - inset),
        "left": (inset, skip_y, inset + d_left, h - skip_y),
        "right": (w - inset - d_right, skip_y, w - inset, h - skip_y),
    }


def assess_edges(
    card_bgr: np.ndarray,
    inner_rect: tuple[int, int, int, int] | None = None,
) -> EdgeResult:
    """Assess edge wear on a rectified card image.

    Args:
        card_bgr: Rectified card (BGR).
        inner_rect: (x0, y0, x1, y1) inner border from ``centering`` -- keeps the
            bands inside the margin. Falls back to a nominal margin if None.
    """
    if card_bgr is None or card_bgr.size == 0:
        raise ValueError("assess_edges received an empty image.")

    h, w = card_bgr.shape[:2]
    short = min(h, w)
    band_max = max(3, int(round(short * EDGE_BAND_FRAC)))
    inset = max(1, int(round(short * EDGE_INSET_FRAC)))
    skip_x = int(round(w * CORNER_SKIP_FRAC))
    skip_y = int(round(h * CORNER_SKIP_FRAC))

    hsv = to_hsv(card_bgr)
    ref_v, ref_s = border_reference(hsv, band_max, inset=inset)

    bands = _edge_bands(h, w, _margins(h, w, inner_rect), band_max, inset, skip_x, skip_y)
    per_edge: dict[str, float] = {}
    for name, (x0, y0, x1, y1) in bands.items():
        roi = hsv[y0:y1, x0:x1]
        if roi.size == 0:
            per_edge[name] = 0.0
            continue
        mask = anomaly_mask(roi, ref_v, ref_s, BRIGHT_DELTA, DARK_DELTA, SAT_MAX)
        frac = float(np.count_nonzero(mask)) / float(mask.size)
        per_edge[name] = clamp01(frac / WORST_ANOMALY_FRAC)

    wear = aggregate_wear(list(per_edge.values()), AGG_MAX_WEIGHT)
    return EdgeResult(wear=wear, per_edge=per_edge, bands=bands)
