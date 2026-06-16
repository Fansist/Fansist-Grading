# Architecture

How the pieces of Fansist Grading fit together.

## Product: capture → human grader (no shipping)

```
  capture (quality-checked)   submit.py / app  ─ capture_qc.py ─▶  reject bad shots
        ▼
  submission.py   create_submission → store/<id>/ {front,back,...}.png + submission.json
        ▼
  grader_portal.py (internal)   human reviews images, enters grade
        ▼   grade_submission → report.build_human_report → store/<id>/report.json + qr.png
  web_report.py (public)   /card/<id>  grade + images + QR + registry
```

The submission id doubles as the public cert id; one store backs both the
internal portal and the public report app. A pending submission has only
`submission.json` (not public); grading adds `report.json` (servable).
`capture_qc.py` reuses the card detector purely to confirm framing/focus/glare —
it does not grade.

## Optional automated engine (retained, not the product path)

Everything below — detection, the four CV graders, calibration, the CNN — is the
*automated* grader, kept for future use (draft estimates / pre-screening). It is
independent of the human-grading product loop above.

## Data flow

```
  card photo (phone / onboard camera / SlabStation Mini imaging bay)
        │
        ▼
  card_detector.detect_card        grayscale→blur→Canny→contour→perspective warp
        │  rectified, deskewed top-down crop
        ▼
  ┌───────────────── measure on the rectified card ─────────────────┐
  │ centering.measure_centering   L/R, T/B margins + ratios          │
  │ corners.assess_corners        per-corner whitening/chipping wear │
  │ edges.assess_edges            per-edge wear                       │
  │ surface.assess_surface        scratch/defect density              │
  └──────────────────────────────────────────────────────────────────┘
        │  raw features  (pipeline.extract_features)
        ▼
  grading.build_full_grade  ── optional ──▶  calibration.Calibration
        │   maps features→sub-grades→overall   (learned from graded cards;
        │   via static scales OR learned curves  train.py / FANSIST_CALIBRATION)
        ▼
  grading.CardGrade  {centering, corners, edges, surface, overall (+labels)}
        │
        ├─▶ pipeline.annotate_* ─▶ Streamlit app (app.py) / CLI images
        │
        ▼
  report.build_report → GradeReport (TAG-style stats) + cert id + QR
        │  report.save_report → store/<cert_id>/{report.json, images, qr.png}
        ▼
  web_report (Flask) /card/<cert_id>  ←─ QR scan ─  slab in the wild
                     /                 registry index + population
```

## Modules

| Layer | Files | Responsibility |
|---|---|---|
| Detection | `card_detector.py` | Find the card, return a deskewed top-down crop. |
| Measurement | `centering.py`, `corners.py`, `edges.py`, `surface.py`, `condition_utils.py` | Turn the crop into raw, interpretable features. |
| Grading | `grading.py` | Map features → sub-grades → overall (static or calibrated). |
| Learning | `calibration.py`, `train.py` | Fit the mapping to real graded cards (isotonic + learned overall rule); k-fold CV. |
| Orchestration | `pipeline.py` | One call: detect → measure → grade; features; annotation; CLI. |
| Reporting | `report.py` | Cert id, QR, TAG-style record, persistence, registry. |
| Web | `web_report.py`, `wsgi.py` | Public `/card/<cert_id>` page + registry; gunicorn/Docker entry. |
| UI | `app.py` | Streamlit review console. |
| Hardware | `docs/SLABSTATION_MINI_*`, `docs/HARDWARE_BLUEPRINT.md`, `hardware/` | The machines (DXF + STL) that produce the image and the slab. |

## Design principles

- **Interpretable first.** Every grade traces back to a measurable feature; the
  static scales and the learned curves are both monotonic and inspectable.
- **Calibration is additive.** With no calibration the defaults run unchanged;
  a calibration only overrides factors it has enough labels for, and is guarded
  to not do worse than the defaults on the training set.
- **One pipeline, many front-ends.** The Streamlit app, the CLI, the report
  service, and the (Auto) machine all call the same `run_pipeline`.
- **Clean seam for heavier ML.** `pipeline.extract_features` is the boundary a
  CNN over the card crop would plug into, especially to strengthen *surface*.
- **Honest about limits.** Single-image surface grading is weakest; corner/edge
  wear is colour-based; results are automated estimates, not official grades.

## Two-sided grading

`pipeline.grade_card(front, back)` runs the pipeline on each face and
`grading.combine_grades` takes the **worse side per factor** (a defect on either
face counts; centering keeps the worse side's ratios). The `GradeReport` carries
both sides' breakdowns and images, and the web page shows front + back.

## ML grader (the AI)

`ml_grader.py` is a transfer-learning CNN (MobileNetV3) that predicts the
condition factors directly from the image, trained by `train_ml.py` on labelled
cards. When `FANSIST_ML_MODEL` is set, `run_pipeline(..., ml_model=...)` uses it
for corners/edges/surface (centering stays the geometric measurement) via
`grading.build_grade_direct`. It accepts `extra_frames` (multi-angle/photometric
captures) — the signal that makes surface/corner grading real.

The two learnable layers compose: **calibration** (light, framework-free, fits
the feature→grade mapping) and the **CNN** (heavy, learns features from pixels).
Reaching TAG-level accuracy needs controlled multi-angle capture (hardware) and a
large labelled RAW-card dataset — this is the architecture for it, not a
shortcut around the data/capture.

## Extending

- **Card metadata / registry:** `report.py` accepts `--name/--set/--number`;
  `report.list_reports` backs the web index — add per-set population on top.
- **Registry/population:** `report.list_reports` already backs the web index;
  add card metadata + per-set population on top.
