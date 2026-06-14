"""train.py

Train (calibrate) the grader on cards you've already had graded, so it matches a
real standard. Point it at a CSV of images + their known grades; it extracts each
card's features, fits the calibration, saves it, and reports the accuracy gain.

    python train.py --manifest data/labels.csv --images-root ./graded --out calibration.json

CSV columns (header row required): `image` plus any of
`overall, centering, corners, edges, surface` (1-10; blanks = unknown). Example:

    image,overall,centering,corners,edges,surface
    psa10_charizard.jpg,10,10,10,9.5,10
    bgs8_pikachu.jpg,8,7,8,8,9

Then grade with the calibration applied:

    FANSIST_CALIBRATION=calibration.json python report.py card.jpg --store ./cards
"""

from __future__ import annotations

import argparse
import csv
import os

import cv2

from calibration import evaluate, train_calibration
from card_detector import CardDetectionError
from pipeline import extract_features

LABEL_COLS = ("overall", "centering", "corners", "edges", "surface")


def load_records(manifest: str, images_root: str):
    """Read the manifest, extract features per image, attach known labels."""
    records, skipped = [], []
    with open(manifest, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            img = (row.get("image") or row.get("path") or "").strip()
            if not img:
                continue
            full = img if os.path.isabs(img) else os.path.join(images_root, img)
            image = cv2.imread(full, cv2.IMREAD_COLOR)
            if image is None:
                skipped.append((img, "unreadable"))
                continue
            try:
                feats = extract_features(image)
            except CardDetectionError:
                skipped.append((img, "no-detect"))
                continue

            labels = {}
            for col in LABEL_COLS:
                val = (row.get(col) or "").strip()
                if val:
                    try:
                        labels[col] = float(val)
                    except ValueError:
                        pass
            if labels:
                records.append({"features": feats, "labels": labels})
            else:
                skipped.append((img, "no-labels"))
    return records, skipped


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Calibrate the grader on graded cards.")
    p.add_argument("--manifest", required=True, help="CSV of image + known grades.")
    p.add_argument("--images-root", default=".", help="Root for relative image paths.")
    p.add_argument("--out", default="calibration.json", help="Where to save the calibration.")
    args = p.parse_args(argv)

    records, skipped = load_records(args.manifest, args.images_root)
    if not records:
        print(f"No usable labelled cards found (skipped {len(skipped)}). "
              "Check paths, detectability, and that grades are filled in.")
        return 1

    calibration = train_calibration(records)
    calibration.save(args.out)
    metrics = evaluate(records, calibration)

    print(f"Trained on {len(records)} cards (skipped {len(skipped)}). "
          f"Saved -> {args.out}\n")
    print(f"{'factor':10s} {'n':>4s} {'MAE before':>11s} {'MAE after':>10s}")
    for k, v in metrics.items():
        print(f"{k:10s} {v['n']:>4d} {str(v['mae_baseline']):>11s} {str(v['mae_calibrated']):>10s}")
    if calibration.overall_weights:
        w = {k: round(x, 3) for k, x in calibration.overall_weights.items()}
        print(f"\nlearned overall weights: {w}")
    print("\nApply it:  FANSIST_CALIBRATION=%s python report.py card.jpg --store ./cards"
          % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
