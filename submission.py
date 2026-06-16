"""submission.py

The capture -> human-grader workflow (no AI). A customer captures high-quality
images; those become a SUBMISSION; a human grader reviews them and enters a
grade, which produces the customer's report (cert + QR + web page) — reusing the
existing report/web stack, only with a human as the grade source.

Storage convention (shared with the report web app): one folder per submission,
named by its id, which is ALSO the cert id. While pending it holds the images +
``submission.json`` (not yet public). On grading it gains ``report.json`` + the
QR, so ``web_report`` serves it at ``/card/<id>`` automatically. Point
``web_report`` (public) and ``grader_portal`` (internal) at the same store.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

import cv2
import numpy as np

from capture_qc import check_image
from report import DEFAULT_BASE_URL, build_human_report, make_qr_png_bytes

# Filename of the slab's tracking QR (encodes the status URL), written at intake.
CODE_QR = "code_qr.png"

STATUS_PENDING = "pending_review"   # IN_REVIEW: model sent to grader
STATUS_GRADED = "graded"            # grader has graded it (ready to print)
STATUS_PRINTED = "printed"          # grade laser-marked onto the slab at a kiosk
STATUS_REJECTED = "rejected"

GRADE_FIELDS = ("overall", "centering", "corners", "edges", "surface")

# Customer-facing status messages keyed by the slab code (for the status site).
STATUS_MESSAGE = {
    STATUS_PENDING: "In review — your card has been scanned and sent to a grader.",
    STATUS_GRADED: "Graded! Return to any Fansist kiosk to print the grade on your slab.",
    STATUS_PRINTED: "Graded and printed on your slab.",
    STATUS_REJECTED: "This submission was not graded.",
}


def mint_submission_id() -> str:
    """Submission id, which doubles as the public cert id (e.g. SUB-3F9A2C7B1D)."""
    return "SUB-" + uuid.uuid4().hex[:10].upper()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write(folder: str, sub: dict) -> None:
    with open(os.path.join(folder, "submission.json"), "w", encoding="utf-8") as fh:
        json.dump(sub, fh, indent=2)


def create_submission(
    front_bgr: np.ndarray,
    back_bgr: np.ndarray | None = None,
    extra_frames: list[np.ndarray] | None = None,
    meta: dict | None = None,
    store_dir: str = "./submissions",
    base_url: str = DEFAULT_BASE_URL,
    run_qc: bool = True,
) -> dict:
    """Create a submission from captured images; returns the submission dict.

    Runs capture-quality checks (``capture_qc``) on each image so the queue/app
    can flag photos that aren't grade-worthy. Does not grade the card.
    """
    sid = mint_submission_id()
    folder = os.path.join(store_dir, sid)
    os.makedirs(folder, exist_ok=True)

    images: dict = {}
    qc: dict = {}

    def _save(role: str, img: np.ndarray) -> None:
        fname = f"{role}.png"
        cv2.imwrite(os.path.join(folder, fname), img)
        images[role] = fname
        if run_qc:
            qc[role] = check_image(img).to_dict()

    _save("front", front_bgr)
    if back_bgr is not None:
        _save("back", back_bgr)
    for i, frame in enumerate(extra_frames or [], start=1):
        _save(f"extra_{i}", frame)

    # The slab's tracking code = the submission id; its QR encodes the status URL
    # so it works from the moment of intake (before the card is graded).
    status_url = f"{base_url.rstrip('/')}/status/{sid}"
    with open(os.path.join(folder, CODE_QR), "wb") as fh:
        fh.write(make_qr_png_bytes(status_url))

    sub = {
        "id": sid,
        "code": sid,
        "created_at": _now(),
        "status": STATUS_PENDING,
        "meta": meta or {},
        "images": images,
        "qc": qc,
        "qc_ok": all(r["ok"] for r in qc.values()) if qc else None,
        "base_url": base_url,
        "status_url": status_url,
        "grade": None,
        "graded_by": None,
        "graded_at": None,
        "notes": "",
        "printed_at": None,
        "cert_id": None,
    }
    _write(folder, sub)
    return sub


def load_submission(store_dir: str, sid: str) -> dict | None:
    path = os.path.join(store_dir, sid, "submission.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def list_submissions(store_dir: str, status: str | None = None) -> list[dict]:
    """Summaries of submissions (newest first), optionally filtered by status."""
    out: list[dict] = []
    if not os.path.isdir(store_dir):
        return out
    for name in os.listdir(store_dir):
        sub = load_submission(store_dir, name)
        if sub is None:
            continue
        if status and sub.get("status") != status:
            continue
        out.append({
            "id": sub["id"],
            "created_at": sub.get("created_at", ""),
            "status": sub.get("status"),
            "qc_ok": sub.get("qc_ok"),
            "name": sub.get("meta", {}).get("name", ""),
            "overall": (sub.get("grade") or {}).get("overall"),
        })
    out.sort(key=lambda r: r["created_at"], reverse=True)
    return out


def grade_submission(
    store_dir: str,
    sid: str,
    grades: dict,
    graded_by: str = "grader",
    notes: str = "",
) -> dict:
    """Record a human grader's grade and produce the customer report.

    ``grades`` maps any of GRADE_FIELDS to a 1-10 value (``overall`` expected).
    Writes ``report.json`` + the QR into the submission folder so the public
    report page serves it, and marks the submission graded. Returns the
    submission dict.
    """
    sub = load_submission(store_dir, sid)
    if sub is None:
        raise KeyError(f"submission {sid!r} not found")

    clean = {k: float(v) for k, v in grades.items()
             if k in GRADE_FIELDS and v is not None and v != ""}
    if "overall" not in clean:
        raise ValueError("an 'overall' grade is required")

    folder = os.path.join(store_dir, sid)
    report = build_human_report(
        cert_id=sid, base_url=sub.get("base_url", DEFAULT_BASE_URL),
        grades=clean, meta=sub.get("meta"), images=sub.get("images"),
        graded_by=f"human:{graded_by}", notes=notes,
    )
    with open(os.path.join(folder, "qr.png"), "wb") as fh:
        fh.write(make_qr_png_bytes(report.report_url))
    with open(os.path.join(folder, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(report.to_dict(), fh, indent=2)

    sub.update(status=STATUS_GRADED, grade=clean, graded_by=graded_by,
               graded_at=_now(), notes=notes, cert_id=sid)
    _write(folder, sub)
    return sub


def mark_printed(store_dir: str, sid: str) -> dict:
    """Pick-up kiosk action: record that the grade was laser-marked on the slab.

    Requires the submission to be GRADED (the laser only fires for a real grade);
    idempotent-safe (re-marking an already-printed slab is rejected). Returns the
    submission dict.
    """
    sub = load_submission(store_dir, sid)
    if sub is None:
        raise KeyError(f"submission {sid!r} not found")
    if sub.get("status") == STATUS_PRINTED:
        raise ValueError("grade already printed on this slab")
    if sub.get("status") != STATUS_GRADED:
        raise ValueError("not graded yet — nothing to print")
    sub.update(status=STATUS_PRINTED, printed_at=_now())
    _write(os.path.join(store_dir, sid), sub)
    return sub

