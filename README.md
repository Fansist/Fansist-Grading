# 🃏 Fansist Grading

**The product: grade your cards from home — no shipping.** A customer captures
**pristine images** of a card, those go **straight to a human grader**, and the
customer gets a graded, QR-linked digital report. No mailing the card, no waiting
for a slab in the post.

The capture → human-grader loop:

```
  capture (front/back, quality-checked)        submit.py / capture app
        │  capture_qc.py rejects blurry/glary/low-res shots
        ▼
  SUBMISSION  (images + card info, queued)      submission.py
        │
        ▼
  HUMAN GRADER reviews images, enters grade     grader_portal.py  (internal)
        │
        ▼
  customer report: grade + images + QR          web_report.py     (public /card/<id>)
```

Run it:

```bash
pip install -r requirements.txt
python submit.py front.jpg --back back.jpg --name "Victini" --store ./submissions
FANSIST_STORE=./submissions python grader_portal.py   # grader UI  :8001
FANSIST_STORE=./submissions python web_report.py      # customer reports + registry :8000
```

> **The high-quality, consistent imaging is the whole product** — see the capture
> hardware in [`docs/`](docs/) (lightbox, cross-polarised lighting to kill holo
> glare, fixed geometry). `capture_qc.py` enforces grade-worthy photos before
> anything reaches a grader.

---

## Optional: built-in CV/ML grading engine (experimental, retained)

The repo also contains a complete **automated** four-factor grader (centering /
corners / edges / surface), a learnable **calibration**, and a **CNN** — kept for
future use (e.g. to give graders a draft estimate or pre-screen). It is **not**
the product path above and its grades are estimates, not official. The rest of
this README documents that engine.

---

## Automated grader (optional engine)

A runnable pipeline that analyses a photo and produces a **full grade** from four
factors — **centering, corners, edges, and surface** — combined into an overall.
It locates the card, flattens it with a perspective transform, then measures each
factor on the rectified image.

**Classic computer vision, no heavy ML.** No deep-learning framework, no hardware,
no live camera, no batch processing — just OpenCV + NumPy with tunable constants,
so the whole thing is transparent and runnable anywhere. The four graders are
independent, easy-to-tune modules, and the grade mapping can be **trained on
cards you've already had graded** so it matches a real standard (see
[Training / calibrating](#training--calibrating-on-graded-cards-make-it-accurate)).
See [Accuracy & honesty](#accuracy--honesty) for what each factor can and can't
see from a single flat photo.

---

## How it works (pipeline)

1. **Card detection** (`card_detector.py`)
   grayscale → blur → Canny edges → dilate → contours → largest 4-point
   (quadrilateral) contour via `approxPolyDP` → perspective transform
   (`getPerspectiveTransform` + `warpPerspective`) → a deskewed, top-down crop.
   **All downstream measurements run on this rectified image**, so rotation and
   skew don't corrupt the numbers.

2. **Centering** (`centering.py`)
   Detect the inner border, measure the left/right/top/bottom margins, and
   compute `horizontal = left:right` and `vertical = top:bottom`, each
   normalised to sum to 100 (e.g. `55/45`).

3. **Corners** (`corners.py`)
   Inspect each corner's border region for whitening (exposed light core) and
   chipping (darkening), producing a per-corner wear score.

4. **Edges** (`edges.py`)
   Scan a thin band along each edge for the same whitening/chipping anomalies.

5. **Surface** (`surface.py`)
   High-pass the artwork and flag statistical outliers (scratches/print lines)
   as a surface-defect density.

6. **Grading** (`grading.py`)
   Map each factor to a sub-grade via its own documented threshold table, and
   combine the present sub-grades into an `overall` (`weighted` / `lowest` /
   `average`, selectable) on a `CardGrade` object.

7. **Orchestration + UI** (`pipeline.py`, `app.py`)
   `pipeline.py` runs all of the above headless (also a CLI/library); `app.py`
   is the Streamlit UI showing the annotated images and the grades.

---

## Install & run

Requires **Python 3.11+**.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Streamlit will open a browser tab. Upload a card photo and the app will display:

- the original image with the detected card outline,
- the rectified card with the outer edge + inner border + margin widths,
- a **condition view** (corners/edges coloured green→red by wear; surface
  defects overlaid in red),
- the four sub-grades (centering, corners, edges, surface) and the **overall**.

If detection fails, you'll get a clear message (poor contrast, busy background,
glare, card too small in frame) instead of a crash.

### Headless use (CLI / library)

All the actual work lives in `pipeline.py`, which has **no Streamlit
dependency** — so you can grade without the UI (and the automated machine in
[`docs/HARDWARE_BLUEPRINT.md`](docs/HARDWARE_BLUEPRINT.md) calls it the same way):

```bash
# Print the grade as JSON, and (optionally) save annotated images.
python pipeline.py path/to/card.jpg --out-prefix out/card
```

```python
# Or as a library:
import cv2
from pipeline import run_pipeline

result = run_pipeline(cv2.imread("card.jpg"))
print(result.grade.to_dict())          # all four sub-grades + overall
# run_pipeline(img, assess_condition=False) -> centering-only, faster
```

`run_pipeline` raises `card_detector.CardDetectionError` on a no-detect; the CLI
turns that into an error JSON and a non-zero exit code, and `--out-prefix` saves
`_original`, `_rectified`, and `_condition` annotated PNGs.

### Slab QR code + report web page

Every graded card can mint a **certificate** with a **QR code** (printed on the
slab) that opens a web page showing the full **TAG-style statistics** — overall
grade on 1–10 and 1–1000 scales, the four sub-grades, a per-corner (×4) and
per-edge (×4) breakdown, centering measurements, surface defect density, and the
annotated images.

```bash
# Grade a card (front, optional back, optional metadata) -> cert + QR + report
python report.py front.jpg --back back.jpg --name "Charizard" --set "Base Set" \
    --store ./cards --base-url https://grade.example

# Serve the report page (scanning the slab's QR opens /card/<cert_id>)
FANSIST_STORE=./cards python web_report.py        # http://localhost:8000
```

With a `--back` image each factor takes the **worse of the two sides** (back
centering matters in real grading); the report page shows both sides.

`report.py` builds the stats record + QR; `web_report.py` is a small Flask app
serving `/card/<cert_id>` plus a registry index at `/` with a population count.
The Streamlit app also shows the QR + report link (set `FANSIST_STORE` to persist
and `FANSIST_BASE_URL` to your domain).

**Deploy the report service** (so the QR points at a real domain):

```bash
docker build -t fansist-grading .
docker run -p 8000:8000 -v $PWD/cards:/data/cards \
    -e FANSIST_STORE=/data/cards -e FANSIST_BASE_URL=https://grade.example \
    fansist-grading
# or directly:  FANSIST_STORE=./cards gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app
```

### Training / calibrating on graded cards (make it accurate)

By default the grader uses hand-tuned threshold tables. You can **train it on
cards you've already had graded** (TAG/PSA/BGS) so it matches a real standard —
no ML framework required (pure NumPy: isotonic regression + a learned overall
rule).

1. Put your graded card photos in a folder and list their known grades in a CSV
   (`image` + any of `overall, centering, corners, edges, surface`, 1–10; blanks
   allowed) — see [`data/labels.example.csv`](data/labels.example.csv).
2. Train — it extracts each card's features, fits a monotonic feature→grade curve
   per factor, learns the overall-combination rule (weighted / **lowest** /
   average — e.g. PSA-style "worst sub-grade wins"), and reports the accuracy gain:

   ```bash
   python train.py --manifest data/labels.csv --images-root ./graded --out calibration.json --cv 5
   ```
   `--cv K` adds **K-fold cross-validated (held-out)** accuracy — the honest
   number for how it generalises to unseen cards (vs. the optimistic in-sample fit).
   ```
   factor        n  MAE before  MAE after
   corners      12       0.667      0.333
   edges        12        0.75        0.0
   surface      12       0.583        0.0
   overall      12         2.0      0.333     # learned the "lowest" rule
   ```
3. Apply it everywhere by setting an env var (CLI, report, Streamlit, and the
   automated machine all honour it):

   ```bash
   FANSIST_CALIBRATION=calibration.json python report.py card.jpg --store ./cards
   ```

Calibration only *replaces* the static scales for factors it has enough labels
for, and it's guarded to never do worse than the defaults on your training set.
More labelled cards → better accuracy; validate on a held-out set. The same
feature interface (`pipeline.extract_features`) is where a heavier ML model
(e.g. a CNN over the card crop) would later plug in.

### Deep-learning grader (the AI — TAG-style)

The classical heuristics (corners/edges/surface) are interpretable but limited.
For a **TAG-style ML grader**, there's an optional CNN (`ml_grader.py`,
`train_ml.py`) — a transfer-learning MobileNetV3 that predicts the condition
factors directly from the image and is **trained on labelled cards** (it learns
"what a 10 vs a 9 looks like"). It supports **multi-angle / photometric** input
(`extra_frames=`) — the raking-light captures that let surface/corner defects
actually be seen.

```bash
pip install -r requirements-ml.txt          # torch + torchvision (heavy, optional)
python train_ml.py --manifest data/labels.csv --images-root graded \
    --out model.pth --epochs 40 --freeze --val-split 0.2
FANSIST_ML_MODEL=model.pth python report.py card.jpg --store ./cards
```

When `FANSIST_ML_MODEL` is set, the CNN grades corners/edges/surface (centering
stays the geometric measurement); the app, CLI and report all use it.

> **Reaching TAG-level accuracy is a data + capture problem, not a code one.**
> TAG's accuracy comes from (1) **photometric-stereo capture** (multi-angle
> controlled light — the surface signal does **not** exist in a single flat
> photo) and (2) a **large** labelled set of RAW-card images with grades
> (thousands). This module is the trainable architecture for exactly that; a
> handful of reference cards will overfit (watch the **val** MAE, not train).
> Graded *slabbed* photos are also a different imaging domain than raw cards.

### Testing

```bash
pip install -r requirements-dev.txt
pytest                        # torch tests auto-skip if torch isn't installed
```

The suite uses **synthetic cards with known margins/defects** (`tests/conftest.py`)
to check detection/deskew, margin measurement (both inner-border methods), the
corner/edge/surface assessors (clean → pristine, damage → higher wear), every
grade scale, the overall-combination strategies, and the end-to-end pipeline —
no real photos needed.

---

## 📸 Imaging guidelines (read this — it determines result quality)

The classic computer-vision pipeline used here has **no ML robustness**, so the
quality of your photo *directly* determines the quality of the grade.

> **Inconsistent lighting and a busy/low-contrast background are the two biggest
> causes of unreliable or failed results.** Fix those first.

For best results:

- **Lay the card flat** on a surface — not held in a hand or sleeve.
- **Plain, high-contrast background.** A light-bordered card on a dark mat, or a
  dark card on a white sheet. The card must contrast clearly with what's behind
  it. Avoid patterned tables, wood grain, or anything cluttered.
- **Even, diffuse lighting. No glare, no shadows.** Glossy/foil cards are
  especially glare-prone; use soft, indirect light and avoid direct flash.
  Reflections and cast shadows create false edges that confuse detection.
- **Camera parallel to the card** (shoot straight down). The perspective
  transform corrects moderate skew, but extreme angles still degrade accuracy.
- **Fill the frame and use maximum resolution.** The whole card should be
  visible and occupy most of the frame; more pixels across the border means more
  precise margin measurements. (Very large images are downscaled internally for
  speed — see `MAX_PROCESS_DIM` in `card_detector.py`.)

---

## Tuning

Inner-border appearance varies a lot by card, so the flaky steps expose tunable
**constants at the top of each file**:

- `card_detector.py` — blur kernel, Canny thresholds, min/max card area,
  polygon-approximation epsilon, max processing dimension.
- `centering.py` — detection strategy (`INNER_BORDER_METHOD`), search margins,
  gradient/Sobel parameters, and the expected border colour range
  (`EXPECTED_BORDER_HSV_*`) for the colour-based method.
- `corners.py` / `edges.py` — ROI/band sizes, edge inset, the whitening/chipping
  anomaly thresholds (`BRIGHT_DELTA` / `DARK_DELTA` / `SAT_MAX`), and the
  worst-region weighting.
- `surface.py` — high-pass kernel, `DEFECT_SIGMA` / `DEFECT_MIN_ABS`, minimum
  defect-blob area, and the inner-region margin.
- `grading.py` — every grade scale (`CENTERING_GRADE_SCALE`,
  `CORNER_/EDGE_/SURFACE_GRADE_SCALE`) and the overall combination
  (`OVERALL_STRATEGY` + `OVERALL_WEIGHTS`).

### Two inner-border detection strategies

`centering.py` ships with two methods; pick one with `INNER_BORDER_METHOD`:

- **`"gradient"`** (default, general purpose) — finds the strongest straight
  edge parallel to each side via gradient projection. Works on most cards.
- **`"color"`** — for cards with a solid, uniform border colour (classic white
  or yellow borders). Scans inward until the border colour stops dominating;
  tune `EXPECTED_BORDER_HSV_LOW/HIGH` to your card's frame colour.

---

## Project structure

```
card_detector.py       Locate the card; return a deskewed, top-down crop + corners.
centering.py           Detect the inner border; measure margins + centering ratios.
corners.py             Per-corner whitening/chipping -> corner wear score.
edges.py               Per-edge whitening/chipping -> edge wear score.
surface.py             High-pass defect detection -> surface defect score.
condition_utils.py     Shared border-reference / anomaly helpers for corners+edges.
capture_qc.py          Photo quality gate (sharp/framed/glare-free/hi-res) for capture.
submission.py          Capture -> queue -> human grade lifecycle.
submit.py              CLI: create a submission from captured images.
grader_portal.py       Internal Flask portal: human grader reviews + grades.
grading.py             Map each factor to a sub-grade; combine into overall; CardGrade.
calibration.py         Learn the grade mapping from graded cards (isotonic fit).
train.py               CLI: train a calibration from a CSV of graded cards.
ml_grader.py           Optional CNN condition grader (transfer learning, torch).
train_ml.py            CLI: train the CNN on labelled card images.
pipeline.py            Headless detect -> 4 factors -> grade + decode + annotate + CLI.
report.py              Cert id + QR + TAG-style stats record; persistence + CLI.
web_report.py          Flask page (/card/<cert_id>) + registry index the QR opens.
wsgi.py / Dockerfile   Production entry for the report service (gunicorn/Docker).
app.py                 Streamlit UI (thin layer over pipeline.py) incl. the QR.
data/                  labels.example.csv (training manifest format).
docs/ARCHITECTURE.md   How all the pieces fit together.
tests/                 pytest suite + synthetic-card fixtures.
requirements.txt       Runtime deps (OpenCV, NumPy, Streamlit).
requirements-dev.txt   Test deps (adds pytest).
docs/                  HARDWARE_BLUEPRINT.md — the imaging/slabbing machine design.
README.md              This file.
```

---

## Accuracy & honesty

These are **automated estimates from a single, evenly-lit photo**, not official
grades. What each factor can actually see:

- **Centering** — the most reliable factor: it's a geometric measurement, robust
  once the card is detected and rectified.
- **Corners / edges** — detect **colour anomalies**: whitening (light core
  showing through a worn/chipped border) and darkening (a chip exposing the
  background). Works best on **dark-bordered** cards; on white-bordered cards
  whitening is invisible and only chips register. Glare reads as false wear.
- **Surface** — the **lowest-confidence** factor. Fine scratches and dents are
  revealed by *raking* (low-angle) light and multiple exposures, which a single
  flat photo doesn't have, so this is a coarse "cleanliness" proxy and can be
  fooled by busy artwork. `surface.py` already accepts extra-lighting frames
  (`assess_surface(..., extra_frames=...)`) for when that capture exists.

Tune the per-factor constants (see [Tuning](#tuning)) and the
`OVERALL_STRATEGY` to your card type and standard.

## Next steps / extending

The four-factor grade is implemented; natural extensions:

- **Better surface grading** via the multi-angle/raking-light captures described
  in the hardware blueprint (the `extra_frames` hook is already there), and/or a
  trained ML defect detector dropped in behind the same `assess_surface` API.
- **Back-of-card grading** — run the same pipeline on the reverse and combine.
- **Per-card-type profiles** — bundle constant presets (e.g. modern holo vs.
  vintage white-border) and auto-select.
- **Calibration to a known standard** — fit the thresholds against
  human-graded cards.

Each grader is an independent module returning a `[0,1]` wear score that
`grading.build_full_grade` maps to a sub-grade, and `compute_overall` folds into
the overall — so swapping or improving any one factor never touches the others.

### Hardware: imaging + slabbing machines

Two hardware designs that photograph cards under controlled lighting and
encapsulate them in slabs — the physical front-end/back-end for this software:

- **[SlabStation Mini](docs/SLABSTATION_MINI_MANUFACTURING_SPEC.md)** — a tabletop,
  **manufacturer-ready** device in two SKUs: **Lite** (manual hinged-lever press,
  phone camera, **~$122 BOM**) and **Auto** (onboard camera + computer grade the
  card, then it auto-feeds a shell, **places the card, prints & applies the QR
  label, and closes the slab**, **~$265 BOM**). Package includes the spec/RFQ,
  real **laser-cut DXF panels**, **watertight STL parts**, and parametric
  generators in [`hardware/`](hardware/).
- **[Industrial blueprint](docs/HARDWARE_BLUEPRINT.md)** — a fully-automated
  production line (rotary dial, machine-vision imaging, ultrasonic-welded slabs)
  for high throughput. It supplies the multi-angle captures that make the surface
  (and corner/edge) grading materially better.

Both call this repo's pipeline as a library.

---

## Limitations

- Single, evenly-lit photo: see [Accuracy & honesty](#accuracy--honesty) — surface
  is the weakest factor; corner/edge wear is colour-based.
- Classic CV detection: sensitive to lighting/background as described above.
- One card per grade (front, and optionally back), photographed roughly flat and
  filling the frame.
- The grade is an automated estimate for triage/fun, **not** an official grade.
