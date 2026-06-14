"""condition_utils.py

Small shared helpers for the condition graders (corners / edges), which both
reason about a card's BORDER region and look for two kinds of local defect:

  * "whitening" -- pixels that are noticeably BRIGHTER and LESS saturated than
    the surrounding border (the white cardboard core showing through where the
    coloured border has worn or chipped away). The classic corner/edge wear tell.
  * "darkening" -- pixels noticeably DARKER than the border (a chip exposing the
    dark background, dirt, or a ding shadow). Catches wear on already-white
    borders, where whitening is invisible.

Both graders compare against a single BORDER REFERENCE colour sampled from the
whole card perimeter, so the thresholds mean the same thing on every edge.

These helpers are intentionally tiny and dependency-light (cv2 + numpy). The
*thresholds* live in the calling module so each grader stays independently
tunable per card type.
"""

from __future__ import annotations

import cv2
import numpy as np


def to_hsv(bgr: np.ndarray) -> np.ndarray:
    """Convert a BGR image to HSV (OpenCV ranges: H 0-179, S/V 0-255)."""
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)


def border_reference(hsv: np.ndarray, band_px: int, inset: int = 0) -> tuple[float, float]:
    """Median (value, saturation) of the card's outer border band.

    Samples a frame ``band_px`` thick around the whole perimeter and returns the
    median V and S -- the "normal border" baseline that anomalies are measured
    against. ``inset`` skips that many pixels at the very edge, avoiding the thin
    background sliver a perspective warp can leave at the card boundary.
    """
    h, w = hsv.shape[:2]
    i = max(0, inset)
    t = max(1, min(band_px, h // 2 - i, w // 2 - i))
    strips = [
        hsv[i:i + t, :, :],           # top
        hsv[h - i - t:h - i, :, :],   # bottom
        hsv[:, i:i + t, :],           # left
        hsv[:, w - i - t:w - i, :],   # right
    ]
    samples = np.concatenate([s.reshape(-1, 3) for s in strips], axis=0)
    ref_v = float(np.median(samples[:, 2]))
    ref_s = float(np.median(samples[:, 1]))
    return ref_v, ref_s


def anomaly_mask(
    hsv_region: np.ndarray,
    ref_v: float,
    ref_s: float,
    bright_delta: float,
    dark_delta: float,
    sat_max: float,
) -> np.ndarray:
    """Binary mask (uint8 0/255) of border anomalies in ``hsv_region``.

    A pixel is anomalous if it is either:
      * whitening: V > ref_v + bright_delta AND S < sat_max, or
      * darkening: V < ref_v - dark_delta.
    """
    v = hsv_region[:, :, 2].astype(np.int32)
    s = hsv_region[:, :, 1].astype(np.int32)

    whitening = (v > ref_v + bright_delta) & (s < sat_max)
    darkening = v < ref_v - dark_delta
    return ((whitening | darkening).astype(np.uint8)) * 255


def aggregate_wear(per_region: list[float], max_weight: float) -> float:
    """Blend several regions' wear into one score (0=clean .. 1=worst).

    A single badly-worn corner/edge should pull the grade down, but a lone noisy
    spike shouldn't dominate -- so we blend the mean with the worst region:

        wear = (1 - max_weight) * mean + max_weight * max
    """
    if not per_region:
        return 0.0
    mean = float(np.mean(per_region))
    worst = float(np.max(per_region))
    return clamp01((1.0 - max_weight) * mean + max_weight * worst)


def clamp01(x: float) -> float:
    """Clamp a float to the [0, 1] range."""
    return float(min(1.0, max(0.0, x)))
