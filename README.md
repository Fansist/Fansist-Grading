# 🃏 Trading Card Centering Grader (v1)

A small, runnable Python app that analyses a single photo of a trading card and
produces a **centering grade** — the most tractable part of card grading (à la
TAG/PSA). It locates the card, flattens it with a perspective transform, finds
the inner border, measures the four margins, and maps the centering ratios to a
sub-grade.

**v1 is centering only.** No machine learning, no hardware, no live camera, no
batch processing. The code is deliberately architected so that corner, edge, and
surface grading can be added later without rewriting the core (see
[Next steps / extending](#next-steps--extending)).

---

## How it works (pipeline)

1. **Card detection** (`card_detector.py`)
   grayscale → blur → Canny edges → dilate → contours → largest 4-point
   (quadrilateral) contour via `approxPolyDP` → perspective transform
   (`getPerspectiveTransform` + `warpPerspective`) → a deskewed, top-down crop.
   **All downstream measurements run on this rectified image**, so rotation and
   skew don't corrupt the numbers.

2. **Inner border + centering** (`centering.py`)
   On the rectified card, detect the inner border (where the outer margin meets
   the artwork), measure the left/right/top/bottom margin widths in pixels, and
   compute `horizontal = left:right` and `vertical = top:bottom`, each
   normalised to sum to 100 (e.g. `55/45`).

3. **Grading** (`grading.py`)
   Map the centering ratios to a sub-grade using a documented, easy-to-edit
   threshold table, and assemble a `CardGrade` object.

4. **UI** (`app.py`)
   A Streamlit page to upload an image and view the original, the annotated
   rectified card, and the numeric results.

---

## Install & run

Requires **Python 3.11+**.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Streamlit will open a browser tab. Upload a card photo and the app will display:

- the original image with the detected card outline,
- the rectified card with the outer edge + inner border drawn and the four
  margin widths labelled,
- the L/R ratio, T/B ratio, and centering grade.

If detection fails, you'll get a clear message (poor contrast, busy background,
glare, card too small in frame) instead of a crash.

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

- `card_detector.py` — blur kernel, Canny thresholds, minimum card area,
  polygon-approximation epsilon, max processing dimension.
- `centering.py` — detection strategy (`INNER_BORDER_METHOD`), search margins,
  gradient/Sobel parameters, and the expected border colour range
  (`EXPECTED_BORDER_HSV_*`) for the colour-based method.
- `grading.py` — the `CENTERING_GRADE_SCALE` threshold table.

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
card_detector.py   Locate the card; return a deskewed, top-down crop + corners.
centering.py       Detect the inner border; measure margins + centering ratios.
grading.py         Map ratios to a sub-grade; CardGrade dataclass (+ stubs).
app.py             Streamlit UI tying it all together.
requirements.txt   Minimal dependencies (OpenCV, NumPy, Streamlit).
README.md          This file.
```

---

## Next steps / extending

The grade schema is already structured for the full four-factor grade. The
`CardGrade` dataclass (`grading.py`) carries `corners`, `edges`, and `surface`
fields that default to `None`, and `compute_overall()` averages only the
sub-scores that are present — so each new grader plugs in without touching the
core:

- **Corners** — crop each corner from the *rectified* image (already deskewed)
  and score sharpness/whitening. Populate `CardGrade.corners`.
- **Edges** — scan the four edges of the rectified card for chipping/whitening.
  Populate `CardGrade.edges`.
- **Surface** — detect scratches, print lines, and dents (this is where an ML
  model would eventually go). Populate `CardGrade.surface`.

For each: add a module mirroring `centering.py`, call it from `run_pipeline()`
in `app.py`, set the corresponding field on the `CardGrade`, and `compute_overall`
will automatically fold it into the overall grade. Adjust the combination rule
in `compute_overall()` (average vs. lowest-sub-grade-wins vs. weighted) to match
your target grading standard.

---

## Limitations (v1)

- Centering only — corners, edges, and surface are stubbed, not graded.
- Classic CV detection: sensitive to lighting/background as described above.
- Assumes one card, photographed roughly flat and filling the frame.
- The grade is an automated estimate for triage/fun, **not** an official grade.
