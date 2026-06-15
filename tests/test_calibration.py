"""Tests for calibration.py and training integration."""

import numpy as np

from calibration import (
    Calibration,
    FactorCurve,
    cross_validate,
    evaluate,
    load_optional,
    predict_from_features,
    train_calibration,
)
from grading import build_full_grade
from pipeline import extract_features, run_pipeline
from conftest import make_scene


# --- FactorCurve (isotonic) -------------------------------------------------

def test_factor_curve_is_monotonic_non_increasing():
    # Grade should fall as the defect metric rises.
    feats = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    labels = [10, 9, 8, 6, 4, 2]
    curve = FactorCurve.fit(feats, labels)
    assert curve is not None
    grades = [curve.grade(x) for x in feats]
    assert all(grades[i] >= grades[i + 1] for i in range(len(grades) - 1))
    assert all(1.0 <= g <= 10.0 for g in grades)


def test_factor_curve_enforces_monotonicity_on_noisy_labels():
    # A non-monotonic blip is smoothed out by isotonic regression.
    feats = [0.0, 0.1, 0.2, 0.3, 0.4]
    labels = [10, 6, 9, 4, 3]   # 0.1->6 then 0.2->9 violates; gets pooled
    curve = FactorCurve.fit(feats, labels)
    grades = [curve.grade(x) for x in feats]
    assert all(grades[i] >= grades[i + 1] for i in range(len(grades) - 1))


def test_factor_curve_too_few_samples_returns_none():
    assert FactorCurve.fit([0.1, 0.2], [9, 8]) is None


# --- Training recovers a known mapping --------------------------------------

def _synthetic_records(n=40):
    """Features with a known linear feature->grade relationship + small noise."""
    rng = np.random.default_rng(0)
    records = []
    for _ in range(n):
        cw = float(rng.uniform(0, 0.6))
        ew = float(rng.uniform(0, 0.6))
        sw = float(rng.uniform(0, 0.6))
        worse = float(rng.uniform(50, 80))
        # "True" grades the shop assigned (a different curve than our defaults).
        labels = {
            "centering": float(np.clip(10 - (worse - 50) * 0.25, 1, 10)),
            "corners": float(np.clip(10 - cw * 16, 1, 10)),
            "edges": float(np.clip(10 - ew * 16, 1, 10)),
            "surface": float(np.clip(10 - sw * 16, 1, 10)),
        }
        labels["overall"] = float(np.clip(
            0.2 * labels["centering"] + 0.3 * labels["corners"]
            + 0.2 * labels["edges"] + 0.3 * labels["surface"], 1, 10))
        feats = {"centering_worse": worse, "corner_wear": cw,
                 "edge_wear": ew, "surface_wear": sw}
        records.append({"features": feats, "labels": labels})
    return records


def test_training_improves_accuracy():
    records = _synthetic_records()
    cal = train_calibration(records)
    metrics = evaluate(records, cal)
    # Calibration should fit the shop's mapping better than the default scales.
    for factor in ("centering", "corners", "edges", "surface", "overall"):
        m = metrics[factor]
        assert m["mae_calibrated"] <= m["mae_baseline"] + 1e-6
    # The hardest factors should improve clearly.
    assert metrics["corners"]["mae_calibrated"] < metrics["corners"]["mae_baseline"]
    assert cal.overall_weights is not None
    assert abs(sum(cal.overall_weights.values()) - 1.0) < 1e-6


def test_overall_can_learn_a_lowest_dominates_rule():
    # A shop whose overall = the worst sub-grade (PSA-like) should be learned.
    rng = np.random.default_rng(2)
    records = []
    for _ in range(30):
        cw, ew, sw = (float(rng.uniform(0, 0.6)) for _ in range(3))
        worse = float(rng.uniform(50, 80))
        subs = {
            "centering": float(np.clip(10 - (worse - 50) * 0.25, 1, 10)),
            "corners": float(np.clip(10 - cw * 16, 1, 10)),
            "edges": float(np.clip(10 - ew * 16, 1, 10)),
            "surface": float(np.clip(10 - sw * 16, 1, 10)),
        }
        labels = dict(subs)
        labels["overall"] = min(subs.values())
        feats = {"centering_worse": worse, "corner_wear": cw,
                 "edge_wear": ew, "surface_wear": sw}
        records.append({"features": feats, "labels": labels})
    cal = train_calibration(records)
    m = evaluate(records, cal)["overall"]
    # The learned overall matches far better than the default weighted average.
    assert m["mae_calibrated"] <= m["mae_baseline"]
    assert m["mae_calibrated"] < 0.6


def test_cross_validate_reports_held_out_accuracy():
    records = _synthetic_records(60)
    cv = cross_validate(records, k=5)
    for factor in ("centering", "corners", "edges", "surface", "overall"):
        assert cv[factor]["n"] > 0
        assert cv[factor]["mae_calibrated"] is not None
    # On data with a clean signal, held-out corners should still beat the default.
    assert cv["corners"]["mae_calibrated"] <= cv["corners"]["mae_baseline"] + 0.5


def test_save_load_roundtrip(tmp_path):
    cal = train_calibration(_synthetic_records())
    path = tmp_path / "calibration.json"
    cal.save(str(path))
    loaded = Calibration.load(str(path))
    # Predictions match after a round-trip.
    feats = {"centering_worse": 62.0, "corner_wear": 0.3,
             "edge_wear": 0.2, "surface_wear": 0.1}
    assert predict_from_features(feats, cal) == predict_from_features(feats, loaded)


def test_load_optional():
    assert load_optional(None) is None
    assert load_optional("/no/such/calibration.json") is None


# --- Integration with grading / pipeline ------------------------------------

def test_build_full_grade_uses_calibration():
    # A calibration that maps everything to grade 7 must override the defaults.
    flat = FactorCurve(xs=[0.0, 1.0], ys=[7.0, 7.0])
    cal = Calibration(centering=flat, corners=flat, edges=flat, surface=flat)
    grade = build_full_grade((50.0, 50.0), (50.0, 50.0),
                             corner_wear=0.0, edge_wear=0.0, surface_wear=0.0,
                             calibration=cal)
    assert grade.centering_grade == 7.0
    assert grade.corners == 7.0 and grade.edges == 7.0 and grade.surface == 7.0


def test_run_pipeline_applies_calibration():
    scene = make_scene()
    flat = FactorCurve(xs=[0.0, 1.0], ys=[5.0, 5.0])
    cal = Calibration(corners=flat)
    default = run_pipeline(scene)
    calibrated = run_pipeline(scene, calibration=cal)
    assert default.grade.corners == 10.0          # clean card, default scale
    assert calibrated.grade.corners == 5.0        # forced by the calibration


def test_extract_features_keys():
    feats = extract_features(make_scene())
    assert set(feats) == {"centering_worse", "corner_wear", "edge_wear", "surface_wear"}
