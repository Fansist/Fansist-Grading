"""Smoke tests for the CNN grader (skipped if torch isn't installed).

These verify the model/training/inference plumbing runs and integrates with the
pipeline -- NOT that it grades accurately (that needs a real dataset).
"""

import numpy as np
import pytest

torch = pytest.importorskip("torch")  # skip whole module if torch absent

from ml_grader import (  # noqa: E402
    FACTORS,
    CardGraderNet,
    MLGrader,
    logits_to_grades,
    preprocess,
)
from pipeline import run_pipeline  # noqa: E402
from conftest import make_card, make_scene  # noqa: E402


def test_model_forward_shape():
    net = CardGraderNet(pretrained=False)
    out = net(torch.randn(2, 3, 224, 224))
    assert out.shape == (2, len(FACTORS))


def test_preprocess_and_grade_range():
    net = CardGraderNet(pretrained=False)
    x = preprocess(make_card())
    assert x.shape == (3, 224, 224)
    grades = logits_to_grades(net(x.unsqueeze(0)))
    assert grades.min() >= 1.0 and grades.max() <= 10.0


def test_one_training_step_runs_and_reduces_loss():
    net = CardGraderNet(pretrained=False)
    net.freeze_backbone()
    opt = torch.optim.Adam([p for p in net.parameters() if p.requires_grad], lr=1e-2)
    x = torch.stack([preprocess(make_card()), preprocess(make_card(40, 40, 40, 40))])
    target = torch.tensor([[1.0, 9.0, 8.0, 10.0], [9.0, 9.0, 9.0, 9.0]])
    mask = torch.ones_like(target)
    tgt_sig = (target - 1.0) / 9.0

    def step():
        opt.zero_grad()
        loss = (((torch.sigmoid(net(x)) - tgt_sig) ** 2) * mask).mean()
        loss.backward()
        opt.step()
        return loss.item()

    first = step()
    for _ in range(8):
        last = step()
    assert last < first  # learning on a fixed batch should reduce loss


def test_save_load_and_grade(tmp_path):
    net = CardGraderNet(pretrained=False)
    path = tmp_path / "model.pth"
    torch.save({"model": net.state_dict(), "factors": FACTORS}, str(path))

    grader = MLGrader(str(path))
    out = grader.grade(make_card())
    assert set(out) == set(FACTORS)
    assert all(1.0 <= v <= 10.0 for v in out.values())
    # Multi-angle pooling path runs too.
    out2 = grader.grade(make_card(), extra_frames=[make_card(), make_card()])
    assert set(out2) == set(FACTORS)


def test_pipeline_uses_ml_model(tmp_path):
    net = CardGraderNet(pretrained=False)
    path = tmp_path / "model.pth"
    torch.save({"model": net.state_dict(), "factors": FACTORS}, str(path))
    grader = MLGrader(str(path))

    scene = make_scene()
    ml_grades = grader.grade(__import__("card_detector").detect_card(scene).rectified)
    result = run_pipeline(scene, ml_model=grader)
    # The pipeline's condition grades come from the model.
    assert result.grade.corners == ml_grades["corners"]
    assert result.grade.surface == ml_grades["surface"]
    # Centering stays measured (not from the model).
    assert result.grade.centering_grade is not None
