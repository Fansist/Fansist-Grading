"""surface.py

Assess the SURFACE of a rectified card for defects (scratches, print lines,
dents, scuffs) from a single top-down image.

Method (classic CV): isolate the inner artwork region, high-pass filter it to
suppress the (legitimate) low-frequency image content, and flag pixels whose
high-frequency response is a strong statistical outlier -- i.e. thin, hard
edges that don't belong (scratches/print lines). The flagged-area fraction is
the surface "defect density", mapped to a sub-grade by ``grading.grade_surface``.

IMPORTANT honesty about limitations
-----------------------------------
Surface grading is the hardest factor to do from ONE evenly-lit photo. Real
defects like fine scratches and dents are revealed by *raking* (low-angle) light
and multiple exposures (photometric stereo) -- exactly the multi-angle capture
the hardware blueprint provides (docs/HARDWARE_BLUEPRINT.md, S3). From a single
flat image this module is a coarse "cleanliness" proxy: busy artwork with many
hard edges will read as noisier than a clean, flat design. Keep the thresholds
conservative and treat the surface sub-grade as the lowest-confidence factor.

The capture hook for the future is already here: pass a list of extra-lighting
gray frames to ``assess_surface(..., extra_frames=...)`` and they are folded in.
Tunable CONSTANTS are at the top.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from condition_utils import clamp01

# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------

# Shrink the inner-artwork region inward by this fraction before inspecting, so
# the inner-border line itself (a legitimate strong edge) isn't flagged.
INNER_MARGIN_FRAC: float = 0.04

# Median-blur kernel (odd) used to build the low-frequency reference that we
# subtract to high-pass the image. Larger = catches broader scuffs/dents.
HIGHPASS_KERNEL: int = 5

# A pixel is a defect if |high-pass| exceeds SIGMA robust standard deviations
# above the median response. Higher = more conservative (fewer false positives
# from normal artwork texture).
DEFECT_SIGMA: float = 7.0

# ...but never flag below this absolute high-pass magnitude (keeps flat,
# uniform regions from flagging sensor noise as defects).
DEFECT_MIN_ABS: float = 12.0

# Drop connected defect blobs smaller than this many pixels -- removes isolated
# single-pixel noise while KEEPING thin scratches/print lines (which are narrow
# but long, so their pixel count is well above this). Set 0 to disable.
MIN_DEFECT_AREA: int = 4

# Defect-area fraction that maps to full wear (1.0).
WORST_DEFECT_FRAC: float = 0.06


@dataclass
class SurfaceResult:
    """Surface defect score and a full-card defect mask (for drawing).

    Attributes:
        wear: Surface defect density mapped to [0, 1] (0 = clean).
        defect_fraction: Raw fraction of inspected pixels flagged as defects.
        defect_mask: uint8 0/255 mask the size of the card; 255 at flagged
            pixels (zero outside the inspected region).
        region: (x0, y0, x1, y1) inspected region on the card.
    """

    wear: float
    defect_fraction: float
    defect_mask: np.ndarray
    region: tuple[int, int, int, int]


def _inspect_region(
    h: int, w: int, inner_rect: tuple[int, int, int, int] | None
) -> tuple[int, int, int, int]:
    """Compute the inspected region, shrunk inward from the inner border."""
    if inner_rect is None:
        # No centering info: inspect a generous central area.
        mx, my = int(w * 0.12), int(h * 0.12)
        return mx, my, w - mx, h - my
    x0, y0, x1, y1 = inner_rect
    dx = int(round((x1 - x0) * INNER_MARGIN_FRAC))
    dy = int(round((y1 - y0) * INNER_MARGIN_FRAC))
    return x0 + dx, y0 + dy, x1 - dx, y1 - dy


def _defect_mask(gray: np.ndarray) -> np.ndarray:
    """High-pass + robust-threshold a gray region into a defect mask (0/255)."""
    g = gray.astype(np.float32)
    k = HIGHPASS_KERNEL if HIGHPASS_KERNEL % 2 == 1 else HIGHPASS_KERNEL + 1
    low = cv2.medianBlur(gray, k).astype(np.float32)
    highpass = np.abs(g - low)

    median = float(np.median(highpass))
    mad = float(np.median(np.abs(highpass - median)))
    # 1.4826 * MAD approximates the standard deviation for robust thresholding.
    robust_std = 1.4826 * mad
    threshold = max(median + DEFECT_SIGMA * robust_std, DEFECT_MIN_ABS)

    mask = (highpass > threshold).astype(np.uint8) * 255
    if MIN_DEFECT_AREA > 0:
        mask = _remove_small_blobs(mask, MIN_DEFECT_AREA)
    return mask


def _remove_small_blobs(mask: np.ndarray, min_area: int) -> np.ndarray:
    """Zero out connected components smaller than ``min_area`` pixels.

    Removes single-pixel noise but keeps thin-yet-long scratches/print lines.
    """
    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    keep = np.zeros_like(mask)
    for label in range(1, num):  # 0 is background
        if stats[label, cv2.CC_STAT_AREA] >= min_area:
            keep[labels == label] = 255
    return keep


def assess_surface(
    card_bgr: np.ndarray,
    inner_rect: tuple[int, int, int, int] | None = None,
    extra_frames: list[np.ndarray] | None = None,
) -> SurfaceResult:
    """Assess surface defects on a rectified card image.

    Args:
        card_bgr: Rectified card (BGR).
        inner_rect: (x0, y0, x1, y1) inner border from ``centering`` -- used to
            inspect only the artwork. If ``None``, a central region is used.
        extra_frames: Optional extra gray captures of the SAME rectified card
            under different lighting (raking-light / photometric set from the
            hardware). Their defect masks are OR-combined with the base frame,
            which is how fine scratches become visible. (No-op if omitted.)
    """
    if card_bgr is None or card_bgr.size == 0:
        raise ValueError("assess_surface received an empty image.")

    h, w = card_bgr.shape[:2]
    x0, y0, x1, y1 = _inspect_region(h, w, inner_rect)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)

    full_mask = np.zeros((h, w), np.uint8)
    if x1 - x0 < 4 or y1 - y0 < 4:
        # Degenerate region (tiny / inverted): nothing to inspect.
        return SurfaceResult(0.0, 0.0, full_mask, (x0, y0, x1, y1))

    gray = cv2.cvtColor(card_bgr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    region_mask = _defect_mask(gray)

    # Fold in any extra-lighting frames (cropped to the same region).
    for frame in extra_frames or []:
        f = frame
        if f.ndim == 3:
            f = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        if f.shape[:2] == (h, w):
            region_mask = cv2.bitwise_or(region_mask, _defect_mask(f[y0:y1, x0:x1]))

    full_mask[y0:y1, x0:x1] = region_mask
    defect_fraction = float(np.count_nonzero(region_mask)) / float(region_mask.size)
    wear = clamp01(defect_fraction / WORST_DEFECT_FRAC)

    return SurfaceResult(
        wear=wear,
        defect_fraction=defect_fraction,
        defect_mask=full_mask,
        region=(x0, y0, x1, y1),
    )
