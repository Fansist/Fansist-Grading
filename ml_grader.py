"""ml_grader.py

The "AI" grader: a transfer-learning CNN that scores a card's condition factors
(corners / edges / surface, and optionally centering) directly from the image —
the same *kind* of system TAG uses (ML over captured imagery), as opposed to the
hand-tuned classical heuristics in corners.py / edges.py / surface.py.

  * Backbone: MobileNetV3-Small pretrained on ImageNet (transfer learning — the
    right choice when you have limited labeled cards), with a small regression
    head predicting the four factor grades on a 1-10 scale.
  * Multi-angle ("photometric") input: ``grade(image, extra_frames=[...])`` pools
    predictions over the base image plus any raking-light captures — this is the
    signal TAG's photometric-stereo rig provides and what makes surface/corner
    grading actually work (a single flat photo can't see fine scratches/dents).
  * Trained by ``train_ml.py`` on a CSV of images + known grades; used by the
    pipeline when ``FANSIST_ML_MODEL`` points at a checkpoint.

HONEST SCOPE: reaching TAG-level *accuracy* needs (1) controlled multi-angle
capture and (2) a LARGE labeled set of RAW-card images with grades (thousands).
This module is the trainable architecture for that; a handful of reference cards
will overfit, not generalize. torch is an optional dependency (requirements-ml.txt).
"""

from __future__ import annotations

import os
from typing import Optional

import cv2
import numpy as np
import torch
import torch.nn as nn
import torchvision

# Factors the CNN predicts, in output order.
FACTORS = ("centering", "corners", "edges", "surface")
IMG_SIZE = 224
_MEAN = (0.485, 0.456, 0.406)   # ImageNet normalisation
_STD = (0.229, 0.224, 0.225)


def _build_backbone(pretrained: bool) -> nn.Module:
    """MobileNetV3-Small with the classifier replaced by a 4-factor head."""
    weights = None
    if pretrained:
        try:  # weights download needs network the first time; degrade gracefully
            weights = torchvision.models.MobileNet_V3_Small_Weights.DEFAULT
        except Exception:
            weights = None
    try:
        net = torchvision.models.mobilenet_v3_small(weights=weights)
    except Exception:
        net = torchvision.models.mobilenet_v3_small(weights=None)

    in_features = net.classifier[0].in_features
    net.classifier = nn.Sequential(
        nn.Linear(in_features, 256), nn.Hardswish(), nn.Dropout(0.2),
        nn.Linear(256, len(FACTORS)),
    )
    return net


class CardGraderNet(nn.Module):
    """CNN mapping a card image to four raw factor logits."""

    def __init__(self, pretrained: bool = True):
        super().__init__()
        self.backbone = _build_backbone(pretrained)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone(x)  # (B, 4) raw logits

    def freeze_backbone(self) -> None:
        """Train only the head (recommended for small datasets)."""
        for name, param in self.backbone.named_parameters():
            param.requires_grad_(name.startswith("classifier"))


def preprocess(image_bgr: np.ndarray) -> torch.Tensor:
    """BGR uint8 image -> normalised CHW float tensor for the network."""
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_AREA)
    tensor = torch.from_numpy(rgb).float().permute(2, 0, 1) / 255.0
    mean = torch.tensor(_MEAN).view(3, 1, 1)
    std = torch.tensor(_STD).view(3, 1, 1)
    return (tensor - mean) / std


def logits_to_grades(raw: torch.Tensor) -> torch.Tensor:
    """Map raw logits to the 1-10 grade scale (sigmoid -> [1, 10])."""
    return 1.0 + 9.0 * torch.sigmoid(raw)


def grades_to_targets(grades: torch.Tensor) -> torch.Tensor:
    """Inverse of :func:`logits_to_grades`'s range: 1-10 grade -> [0, 1] target."""
    return (grades - 1.0) / 9.0


class MLGrader:
    """Loads a trained checkpoint and grades images."""

    def __init__(self, checkpoint_path: str, device: str = "cpu"):
        self.device = torch.device(device)
        ckpt = torch.load(checkpoint_path, map_location=self.device, weights_only=False)
        self.factors = tuple(ckpt.get("factors", FACTORS))
        self.model = CardGraderNet(pretrained=False).to(self.device)
        self.model.load_state_dict(ckpt["model"])
        self.model.eval()

    @torch.no_grad()
    def grade(self, image_bgr: np.ndarray, extra_frames=None) -> dict:
        """Return {factor: grade 1-10}, pooling over any extra-lighting frames."""
        frames = [image_bgr] + list(extra_frames or [])
        batch = torch.stack([preprocess(f) for f in frames]).to(self.device)
        grades = logits_to_grades(self.model(batch)).mean(dim=0)  # pool frames
        return {f: round(float(g), 1) for f, g in zip(self.factors, grades)}


def load_grader(path: Optional[str], device: str = "cpu") -> Optional["MLGrader"]:
    """Load an :class:`MLGrader` if ``path`` is set and exists, else None."""
    if path and os.path.exists(path):
        return MLGrader(path, device=device)
    return None
