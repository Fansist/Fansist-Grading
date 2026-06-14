"""calibration.py

Learn the grade mapping from cards you've *already had graded* (TAG/PSA/BGS),
so the grader becomes accurate to a real standard instead of relying on the
hand-tuned default tables.

How it works (deliberately framework-free — pure NumPy, no PyTorch/TF):

  1. For each labelled card we extract the same raw FEATURES the pipeline
     already computes (centering "worse %", and corner / edge / surface wear).
  2. For each factor we fit a **monotonic curve** feature -> grade by isotonic
     regression (Pool-Adjacent-Violators). Grade must fall as the defect metric
     rises, so the curve is constrained non-increasing — this can't "overfit"
     into something nonsensical, which matters with small datasets.
  3. We fit the **overall-grade weights** (non-negative, sum-to-one) from the
     model's sub-grades to the labelled overall via least squares.

The result is a :class:`Calibration` that ``grading.build_full_grade`` /
``pipeline.run_pipeline`` accept to override the static scales. Train it with
``train.py``. It is a calibration/regression layer; the same feature interface
is where a heavier ML model (e.g. a CNN over the card crop) would later plug in.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Optional

import numpy as np

from grading import (
    CENTERING_GRADE_SCALE,
    CORNER_GRADE_SCALE,
    EDGE_GRADE_SCALE,
    SURFACE_GRADE_SCALE,
    compute_overall,
    grade_from_metric,
)

# Map: factor name -> (feature key, default scale used as the baseline).
FACTOR_FEATURE = {
    "centering": ("centering_worse", CENTERING_GRADE_SCALE),
    "corners": ("corner_wear", CORNER_GRADE_SCALE),
    "edges": ("edge_wear", EDGE_GRADE_SCALE),
    "surface": ("surface_wear", SURFACE_GRADE_SCALE),
}

# Minimum labelled samples before we trust a learned curve for a factor.
MIN_SAMPLES_PER_FACTOR = 3


# ---------------------------------------------------------------------------
# Isotonic (monotonic) curve
# ---------------------------------------------------------------------------

def _pav_nondecreasing(y: np.ndarray) -> np.ndarray:
    """Pool-Adjacent-Violators: least-squares non-decreasing fit of ``y``."""
    vals: list[float] = []
    cnts: list[int] = []
    for yi in y:
        v, c = float(yi), 1
        while vals and vals[-1] > v:
            pv, pc = vals.pop(), cnts.pop()
            v = (pv * pc + v * c) / (pc + c)
            c = pc + c
        vals.append(v)
        cnts.append(c)
    out: list[float] = []
    for v, c in zip(vals, cnts):
        out.extend([v] * c)
    return np.array(out)


@dataclass
class FactorCurve:
    """A learned, monotonic non-increasing mapping feature -> grade (1..10)."""

    xs: list[float]   # feature breakpoints, strictly ascending
    ys: list[float]   # fitted grade at each breakpoint, non-increasing

    def grade(self, x: float) -> float:
        """Grade for a feature value (interpolated, clamped 1..10, half-step)."""
        g = float(np.interp(x, self.xs, self.ys))
        g = min(10.0, max(1.0, g))
        return round(g * 2.0) / 2.0

    @classmethod
    def fit(cls, features, labels) -> Optional["FactorCurve"]:
        """Fit a non-increasing curve to (feature, grade) pairs, or None if too few."""
        x = np.asarray(features, dtype=float)
        y = np.asarray(labels, dtype=float)
        if x.size < MIN_SAMPLES_PER_FACTOR:
            return None
        order = np.argsort(x, kind="mergesort")
        x, y = x[order], y[order]
        fitted = -_pav_nondecreasing(-y)  # non-increasing in x
        # Aggregate duplicate x's so breakpoints are strictly ascending.
        ux, uy = [], []
        i, n = 0, x.size
        while i < n:
            j = i
            while j < n and x[j] == x[i]:
                j += 1
            ux.append(float(x[i]))
            uy.append(float(np.mean(fitted[i:j])))
            i = j
        return cls(xs=ux, ys=uy)

    def to_dict(self) -> dict:
        return {"xs": self.xs, "ys": self.ys}

    @classmethod
    def from_dict(cls, d) -> Optional["FactorCurve"]:
        return None if d is None else cls(xs=list(d["xs"]), ys=list(d["ys"]))


# ---------------------------------------------------------------------------
# Calibration model
# ---------------------------------------------------------------------------

@dataclass
class Calibration:
    """Learned grade mapping. Any field left None falls back to the defaults."""

    centering: Optional[FactorCurve] = None
    corners: Optional[FactorCurve] = None
    edges: Optional[FactorCurve] = None
    surface: Optional[FactorCurve] = None
    overall_strategy: Optional[str] = None   # "weighted" / "lowest" / "average"
    overall_weights: Optional[dict] = None
    meta: dict = field(default_factory=dict)

    def curve(self, factor: str) -> Optional[FactorCurve]:
        return getattr(self, factor)

    def to_dict(self) -> dict:
        d = {f: (getattr(self, f).to_dict() if getattr(self, f) else None)
             for f in ("centering", "corners", "edges", "surface")}
        d["overall_strategy"] = self.overall_strategy
        d["overall_weights"] = self.overall_weights
        d["meta"] = self.meta
        return d

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    @classmethod
    def from_dict(cls, d) -> "Calibration":
        return cls(
            centering=FactorCurve.from_dict(d.get("centering")),
            corners=FactorCurve.from_dict(d.get("corners")),
            edges=FactorCurve.from_dict(d.get("edges")),
            surface=FactorCurve.from_dict(d.get("surface")),
            overall_strategy=d.get("overall_strategy"),
            overall_weights=d.get("overall_weights"),
            meta=d.get("meta", {}),
        )

    @classmethod
    def load(cls, path: str) -> "Calibration":
        with open(path, encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))


def load_optional(path: Optional[str]) -> Optional[Calibration]:
    """Load a calibration if ``path`` is set and exists, else None."""
    import os

    if path and os.path.exists(path):
        return Calibration.load(path)
    return None


# ---------------------------------------------------------------------------
# Prediction & training
# ---------------------------------------------------------------------------

def predict_from_features(features: dict, calibration: Optional[Calibration] = None) -> dict:
    """Predict sub-grades + overall from raw features (calibrated or baseline)."""
    subs: dict[str, Optional[float]] = {}
    for factor, (key, scale) in FACTOR_FEATURE.items():
        if key not in features:
            continue
        curve = calibration.curve(factor) if calibration else None
        if curve is not None:
            subs[factor] = curve.grade(features[key])
        else:
            subs[factor] = grade_from_metric(features[key], scale)[0]
    strategy = calibration.overall_strategy if calibration else None
    weights = calibration.overall_weights if calibration else None
    overall = compute_overall(subs, strategy=strategy, weights=weights)
    return {**subs, "overall": overall}


def _fit_overall(records: list[dict], curves: dict):
    """Choose the overall-combination model that best matches labelled overalls.

    Tries weighted (with fitted non-negative weights), lowest, average, and the
    default weighted -- and picks whichever has the lowest training error. This
    lets calibration learn e.g. a PSA-like "lowest sub-grade dominates" rule, not
    just a weighted average. Returns ``(strategy, weights_or_None)`` or
    ``(None, None)`` if there aren't enough labelled overalls.
    """
    from grading import OVERALL_WEIGHTS

    factors = ("centering", "corners", "edges", "surface")
    cal = Calibration(**{f: curves.get(f) for f in factors})
    rows, targets = [], []
    for rec in records:
        if "overall" not in rec["labels"]:
            continue
        pred = predict_from_features(rec["features"], cal)
        if any(pred.get(f) is None for f in factors):
            continue
        rows.append([pred[f] for f in factors])
        targets.append(rec["labels"]["overall"])
    if len(rows) < MIN_SAMPLES_PER_FACTOR:
        return None, None

    A = np.array(rows, dtype=float)
    b = np.array(targets, dtype=float)
    w, *_ = np.linalg.lstsq(A, b, rcond=None)
    w = np.clip(w, 0.0, None)
    w = w / w.sum() if w.sum() > 0 else np.ones(len(factors)) / len(factors)
    fitted = {f: float(wi) for f, wi in zip(factors, w)}

    candidates = [("weighted", fitted), ("lowest", None), ("average", None),
                  ("weighted", OVERALL_WEIGHTS)]

    def _mae(strategy, weights):
        errs = []
        for row, tgt in zip(rows, targets):
            scores = {f: row[i] for i, f in enumerate(factors)}
            errs.append(abs(compute_overall(scores, strategy=strategy, weights=weights) - tgt))
        return float(np.mean(errs))

    return min(candidates, key=lambda c: _mae(*c))


def train_calibration(records: list[dict]) -> Calibration:
    """Fit a :class:`Calibration` from labelled records.

    Each record is ``{"features": {...}, "labels": {...}}`` where labels may hold
    any subset of ``centering / corners / edges / surface / overall`` (the known
    grades for that card). Factors without enough labels keep the default scale.
    """
    curves: dict = {}
    counts: dict = {}
    for factor, (key, _scale) in FACTOR_FEATURE.items():
        feats, labs = [], []
        for rec in records:
            if key in rec["features"] and factor in rec["labels"]:
                feats.append(rec["features"][key])
                labs.append(rec["labels"][factor])
        counts[factor] = len(feats)
        curves[factor] = FactorCurve.fit(feats, labs)

    strategy, weights = _fit_overall(records, curves)
    return Calibration(
        centering=curves["centering"], corners=curves["corners"],
        edges=curves["edges"], surface=curves["surface"],
        overall_strategy=strategy, overall_weights=weights,
        meta={"n_records": len(records), "label_counts": counts,
              "overall_strategy": strategy},
    )


def evaluate(records: list[dict], calibration: Optional[Calibration]) -> dict:
    """Mean-absolute-error per factor + overall, baseline vs calibrated.

    Lets you see the accuracy gain from training on the same labelled set.
    """
    keys = ("centering", "corners", "edges", "surface", "overall")
    err = {k: {"baseline": [], "calibrated": []} for k in keys}
    for rec in records:
        base = predict_from_features(rec["features"], None)
        cal = predict_from_features(rec["features"], calibration)
        for k in keys:
            if k in rec["labels"] and base.get(k) is not None:
                err[k]["baseline"].append(abs(base[k] - rec["labels"][k]))
                err[k]["calibrated"].append(abs(cal[k] - rec["labels"][k]))

    def _mae(v):
        return round(float(np.mean(v)), 3) if v else None

    return {k: {"n": len(err[k]["baseline"]),
                "mae_baseline": _mae(err[k]["baseline"]),
                "mae_calibrated": _mae(err[k]["calibrated"])} for k in keys}
