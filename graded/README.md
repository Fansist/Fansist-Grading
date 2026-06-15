# Reference cards for calibration

Put graded reference card images here (front and/or back), then list their known
grades in [`../data/labels.csv`](../data/labels.csv) and train:

```bash
python train.py --manifest data/labels.csv --images-root graded --out calibration.json --cv 5
FANSIST_CALIBRATION=calibration.json python report.py mycard.jpg --store ./cards
```

`labels.csv` columns: `image` + any of `overall, centering, corners, edges,
surface` (1–10; blanks = unknown). One row per image.

## Honest guidance on what to collect

- **Aim for a spread across grades** (e.g. several 8s, 9s, 10s) and **≥3 per
  factor** — a single example can't fit a curve.
- **Consistency matters more than count.** Calibration learns *feature → grade*;
  if the reference photos are shot very differently from the cards you'll grade,
  the mapping won't transfer. Slabbed eBay photos (card seen through a case, at an
  angle, with glare) are a *different imaging domain* than a flat raw-card photo.
- **What calibrates well from slab/marketplace photos:** **centering** (it's a
  geometric measurement that survives the slab) and the **overall-combination
  rule**.
- **What does *not* calibrate well that way:** **surface / corners / edges** —
  these need controlled, multi-angle capture (see below). No amount of labels
  fixes a single glare-prone holo photo.
