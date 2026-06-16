"""capture_qc.py

Quality gate for the capture product: before a card photo is sent to the human
grader, check that it's actually *grade-worthy* — sharp, well-framed, high
resolution, glare-free. This is what makes image-only ("no shipping") grading
credible: the grader must be able to trust the image.

It does NOT grade the card (that's the human's job). It reuses the card detector
purely to confirm a card is present and well-framed, then measures focus, glare
and resolution. All thresholds are tunable constants up top — tune them to your
capture device / lighting.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from card_detector import CardDetectionError, detect_card

# --- Tunable quality thresholds --------------------------------------------

# Minimum long-edge resolution (px) for a submittable photo.
MIN_LONG_EDGE_PX: int = 1200

# Focus: variance of the Laplacian over the card crop. Higher = sharper.
MIN_SHARPNESS: float = 80.0

# Glare: max allowed fraction of near-blown-out (very bright) pixels on the card.
GLARE_VALUE: int = 250
MAX_GLARE_FRAC: float = 0.02

# Framing: the card must fill between these fractions of the frame.
MIN_FILL_FRAC: float = 0.12
MAX_FILL_FRAC: float = 0.98


@dataclass
class QCResult:
    """Outcome of a capture-quality check."""

    ok: bool
    issues: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "issues": self.issues, "metrics": self.metrics}


def check_image(image_bgr: np.ndarray) -> QCResult:
    """Assess one card photo for capture quality.

    Returns a :class:`QCResult` with a pass/fail, a list of human-readable issues,
    and the measured metrics (so a capture app can show live feedback).
    """
    issues: list[str] = []
    metrics: dict = {}

    if image_bgr is None or image_bgr.size == 0:
        return QCResult(ok=False, issues=["no image data"], metrics={})

    h, w = image_bgr.shape[:2]
    long_edge = max(h, w)
    metrics["long_edge_px"] = int(long_edge)
    if long_edge < MIN_LONG_EDGE_PX:
        issues.append(f"resolution too low ({long_edge}px; need >= {MIN_LONG_EDGE_PX}px)")

    try:
        detection = detect_card(image_bgr)
    except CardDetectionError:
        metrics["card_detected"] = False
        issues.append("no card detected — use a plain background and fill the frame")
        return QCResult(ok=False, issues=issues, metrics=metrics)

    metrics["card_detected"] = True
    src_area = detection.source.shape[0] * detection.source.shape[1]
    fill = float(cv2.contourArea(detection.corners.astype("float32")) / src_area)
    metrics["fill_fraction"] = round(fill, 3)
    if fill < MIN_FILL_FRAC:
        issues.append("card too small in the frame — move closer")
    elif fill > MAX_FILL_FRAC:
        issues.append("card fills the whole frame — leave a small margin")

    gray = cv2.cvtColor(detection.rectified, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    metrics["sharpness"] = round(sharpness, 1)
    if sharpness < MIN_SHARPNESS:
        issues.append("image looks blurry / out of focus — hold steady, tap to focus")

    glare = float((gray >= GLARE_VALUE).mean())
    metrics["glare_fraction"] = round(glare, 4)
    if glare > MAX_GLARE_FRAC:
        issues.append("glare / reflections on the card — diffuse the light or change angle")

    return QCResult(ok=len(issues) == 0, issues=issues, metrics=metrics)
