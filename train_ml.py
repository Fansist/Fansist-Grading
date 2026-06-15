"""train_ml.py

Train the CNN grader (ml_grader.CardGraderNet) on a CSV of card images + known
grades — this is how the AI "learns what a 10 vs a 9 looks like".

    python train_ml.py --manifest data/labels.csv --images-root graded \
        --out model.pth --epochs 40 --freeze

CSV columns: `image` plus any of `centering, corners, edges, surface` (1-10;
blanks = unknown for that factor on that card). `overall` is ignored here (it's
recomputed from the four factors at grade time). Then grade with it:

    FANSIST_ML_MODEL=model.pth python report.py card.jpg --store ./cards

Reality check: with few cards this WILL overfit (tiny val set, big model). It
needs hundreds-plus labelled RAW cards — ideally with multi-angle captures — to
generalise. Use --val-split and watch the val MAE, not the train MAE.
"""

from __future__ import annotations

import argparse
import csv
import os
import random

import cv2
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

from ml_grader import FACTORS, CardGraderNet, grades_to_targets, logits_to_grades, preprocess


class CardDataset(Dataset):
    """Card images + (masked) factor-grade targets, with light augmentation."""

    def __init__(self, rows: list[dict], images_root: str, train: bool):
        self.rows = rows
        self.root = images_root
        self.train = train

    def __len__(self) -> int:
        return len(self.rows)

    def _augment(self, img: np.ndarray) -> np.ndarray:
        if random.random() < 0.5:
            img = cv2.flip(img, 1)
        # mild brightness/contrast jitter so it doesn't memorise exposure
        alpha = 1.0 + random.uniform(-0.12, 0.12)
        beta = random.uniform(-12, 12)
        return cv2.convertScaleAbs(img, alpha=alpha, beta=beta)

    def __getitem__(self, idx):
        row = self.rows[idx]
        img = cv2.imread(os.path.join(self.root, row["image"]), cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(row["image"])
        if self.train:
            img = self._augment(img)
        x = preprocess(img)

        target = torch.zeros(len(FACTORS))
        mask = torch.zeros(len(FACTORS))
        for i, f in enumerate(FACTORS):
            if row.get(f) is not None:
                target[i] = float(row[f])
                mask[i] = 1.0
        return x, target, mask


def load_rows(manifest: str) -> list[dict]:
    rows = []
    with open(manifest, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            img = (r.get("image") or "").strip()
            if not img:
                continue
            row = {"image": img}
            for f in FACTORS:
                v = (r.get(f) or "").strip()
                row[f] = float(v) if v else None
            rows.append(row)
    return rows


def masked_mse(raw, target, mask):
    pred = torch.sigmoid(raw)
    tgt = grades_to_targets(target)
    se = ((pred - tgt) ** 2) * mask
    return se.sum() / mask.sum().clamp(min=1.0)


def mae_grades(raw, target, mask):
    pred = logits_to_grades(raw)
    ae = (pred - target).abs() * mask
    return ae.sum().item(), mask.sum().item()


def run_epoch(model, loader, optimizer, device):
    train = optimizer is not None
    model.train(train)
    tot_ae = tot_n = 0.0
    for x, target, mask in loader:
        x, target, mask = x.to(device), target.to(device), mask.to(device)
        with torch.set_grad_enabled(train):
            raw = model(x)
            loss = masked_mse(raw, target, mask)
            if train:
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
        ae, n = mae_grades(raw.detach(), target, mask)
        tot_ae += ae
        tot_n += n
    return tot_ae / max(tot_n, 1.0)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Train the CNN card grader.")
    p.add_argument("--manifest", required=True)
    p.add_argument("--images-root", default=".")
    p.add_argument("--out", default="model.pth")
    p.add_argument("--epochs", type=int, default=40)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--val-split", type=float, default=0.2)
    p.add_argument("--freeze", action="store_true", help="Train head only (small data).")
    p.add_argument("--no-pretrained", action="store_true")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args(argv)

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    rows = load_rows(args.manifest)
    if not rows:
        print("No rows in manifest.")
        return 1
    random.shuffle(rows)
    n_val = int(len(rows) * args.val_split)
    val_rows, train_rows = rows[:n_val], rows[n_val:]

    train_loader = DataLoader(CardDataset(train_rows, args.images_root, True),
                              batch_size=args.batch_size, shuffle=True)
    val_loader = (DataLoader(CardDataset(val_rows, args.images_root, False),
                             batch_size=args.batch_size) if val_rows else None)

    model = CardGraderNet(pretrained=not args.no_pretrained).to(device)
    if args.freeze:
        model.freeze_backbone()
    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.Adam(params, lr=args.lr)

    print(f"Training on {len(train_rows)} cards (val {len(val_rows)}) on {device}.")
    for epoch in range(1, args.epochs + 1):
        tr = run_epoch(model, train_loader, optimizer, device)
        msg = f"epoch {epoch:3d}  train MAE {tr:.2f}"
        if val_loader:
            va = run_epoch(model, val_loader, None, device)
            msg += f"  val MAE {va:.2f}"
        if epoch % max(1, args.epochs // 10) == 0 or epoch == args.epochs:
            print(msg)

    torch.save({"model": model.state_dict(), "factors": FACTORS}, args.out)
    print(f"\nSaved -> {args.out}\nApply:  FANSIST_ML_MODEL={args.out} "
          "python report.py card.jpg --store ./cards")
    if len(rows) < 50:
        print("\nNOTE: very few cards — expect overfitting. Add hundreds of "
              "labelled RAW cards (ideally multi-angle) before trusting it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
