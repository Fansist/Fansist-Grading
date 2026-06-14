# 🃏 Trading Card Grader

A small, runnable Python app that analyses a single photo of a trading card and
produces a **full grade** (à la TAG/PSA) from four factors — **centering,
corners, edges, and surface** — combined into an overall grade. It locates the
card, flattens it with a perspective transform, then measures each factor on the
rectified image.

**Classic computer vision, no ML.** No machine learning, no hardware, no live
camera, no batch processing — just OpenCV + NumPy with tunable constants, so the
whole thing is transparent and runnable anywhere. The four graders are
independent, easy-to-tune modules; see [Accuracy & honesty](#accuracy--honesty)
for what each factor can and can't see from a single flat photo.

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

### Testing

```bash
pip install -r requirements-dev.txt
pytest
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
grading.py             Map each factor to a sub-grade; combine into overall; CardGrade.
pipeline.py            Headless detect -> 4 factors -> grade + decode + annotate + CLI.
app.py                 Streamlit UI (thin layer over pipeline.py).
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

### Hardware: automated imaging + slabbing machine

A full engineering blueprint for a machine that photographs cards under
controlled lighting and encapsulates them into sealed slabs — the hardware
front-end/back-end for this software — lives in
[`docs/HARDWARE_BLUEPRINT.md`](docs/HARDWARE_BLUEPRINT.md). It calls this repo's
pipeline as a library and supplies the multi-angle captures that make the
surface (and corner/edge) grading materially better.

---

## Limitations

- Single, evenly-lit photo: see [Accuracy & honesty](#accuracy--honesty) — surface
  is the weakest factor; corner/edge wear is colour-based.
- Classic CV detection: sensitive to lighting/background as described above.
- Assumes one card (front), photographed roughly flat and filling the frame.
- The grade is an automated estimate for triage/fun, **not** an official grade.
