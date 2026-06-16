"""kiosk.py

The finishing/pick-up kiosk's software side: look up a slab code's status, and —
once it's graded — release the grade to be laser-marked onto the slab.

    python kiosk.py --store ./submissions status FAN-XXXXXXXXXX
    python kiosk.py --store ./submissions print  FAN-XXXXXXXXXX

`print` is the action the kiosk runs after the customer inserts a graded slab: it
verifies the backend says GRADED, (the real machine then fires the laser marker),
and records the slab as PRINTED. It refuses if the card isn't graded yet or the
slab was already marked.
"""

from __future__ import annotations

import argparse

from submission import STATUS_GRADED, STATUS_MESSAGE, load_submission, mark_printed


def _grade_text(sub: dict) -> str:
    g = sub.get("grade") or {}
    parts = [f"OVERALL {g['overall']:g}"] if g.get("overall") is not None else []
    for f in ("centering", "corners", "edges", "surface"):
        if g.get(f) is not None:
            parts.append(f"{f[:3].upper()} {g[f]:g}")
    return "  ".join(parts) or "(no grade)"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Finishing kiosk: status / print grade.")
    p.add_argument("action", choices=["status", "print"])
    p.add_argument("code")
    p.add_argument("--store", default="./submissions")
    args = p.parse_args(argv)

    sub = load_submission(args.store, args.code)
    if sub is None:
        print(f"Unknown slab code {args.code!r}.")
        return 2

    if args.action == "status":
        st = sub.get("status")
        print(f"{args.code}: {st.upper()} — {STATUS_MESSAGE.get(st, '')}")
        if st == STATUS_GRADED:
            print(f"  ready to print: {_grade_text(sub)}")
        return 0

    # action == print
    try:
        sub = mark_printed(args.store, args.code)
    except ValueError as exc:
        print(f"Cannot print: {exc}")
        return 1
    # The real kiosk fires the galvo laser here to engrave the grade panel.
    print(f"LASER-MARK -> {_grade_text(sub)}   (cert {args.code})")
    print(f"{args.code}: PRINTED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
