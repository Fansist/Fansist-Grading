"""submit.py

Create a submission from captured card images (the capture-app / device side):
runs the quality checks and queues the card for the human grader.

    python submit.py front.jpg --back back.jpg --name "Victini" --set "XY Promo" \
        --store ./submissions --base-url https://grade.example
"""

from __future__ import annotations

import argparse
import json
import sys

import cv2

from capture_qc import check_image
from submission import create_submission


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Submit captured card images for human grading.")
    p.add_argument("front", help="Front image path.")
    p.add_argument("--back", help="Back image path (optional).")
    p.add_argument("--extra", nargs="*", default=[], help="Extra (e.g. raking-light) images.")
    p.add_argument("--store", default="./submissions")
    p.add_argument("--base-url", default="https://grade.fansist.app")
    p.add_argument("--name")
    p.add_argument("--set", dest="card_set")
    p.add_argument("--number")
    p.add_argument("--allow-low-quality", action="store_true",
                   help="Submit even if quality checks flag the images.")
    args = p.parse_args(argv)

    front = cv2.imread(args.front, cv2.IMREAD_COLOR)
    if front is None:
        print(f"error: could not read {args.front!r}", file=sys.stderr)
        return 2
    back = cv2.imread(args.back, cv2.IMREAD_COLOR) if args.back else None
    if args.back and back is None:
        print(f"error: could not read back {args.back!r}", file=sys.stderr)
        return 2
    extra = []
    for path in args.extra:
        im = cv2.imread(path, cv2.IMREAD_COLOR)
        if im is not None:
            extra.append(im)

    # Pre-flight quality check so the user gets feedback before queueing.
    qc = check_image(front)
    if not qc.ok and not args.allow_low_quality:
        print(json.dumps({"submitted": False, "reason": "quality_check_failed",
                          "issues": qc.issues, "metrics": qc.metrics}, indent=2))
        print("Re-shoot per the tips above, or pass --allow-low-quality.", file=sys.stderr)
        return 1

    meta = {k: v for k, v in (("name", args.name), ("set", args.card_set),
                              ("number", args.number)) if v}
    sub = create_submission(front, back, extra_frames=extra or None, meta=meta,
                            store_dir=args.store, base_url=args.base_url)
    print(json.dumps({
        "submitted": True,
        "submission_id": sub["id"],
        "status": sub["status"],
        "qc_ok": sub["qc_ok"],
        "report_url_when_graded": f"{args.base_url.rstrip('/')}/card/{sub['id']}",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
