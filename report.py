"""report.py

Build a detailed, TAG-style grading report for a card, mint a unique cert ID,
generate the QR code that goes on the slab, and persist everything so a web page
can serve it.

A TAG (Technical Authentication & Grading) digital report shows, for one card:
an overall grade (on a 1-10 scale and a 1000-point scale), the four sub-grades
(centering / corners / edges / surface), and a *breakdown* within each factor --
a score for every individual corner and edge, the centering measurements, and a
surface defect read-out -- alongside the imagery. This module produces the same
shape of data from our pipeline so the QR-linked page can present it.

Flow:
    run_pipeline(image) -> PipelineResult
    build_report(result, cert_id, base_url) -> GradeReport (rich stats)
    save_report(report, images, store_dir)  -> writes JSON + PNGs + qr.png
    the web app (web_report.py) reads that store and renders /card/<cert_id>.

No Flask dependency here -- only the optional ``qrcode`` package for the QR PNG.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from grading import grade_corners, grade_edges
from pipeline import (
    PipelineResult,
    annotate_condition,
    annotate_original,
    annotate_rectified,
)

# Default public base for the QR link; override per deployment / per call.
DEFAULT_BASE_URL = "https://grade.fansist.app"

# Image file names written into each cert folder.
IMG_ORIGINAL = "original.png"
IMG_CENTERING = "centering.png"
IMG_CONDITION = "condition.png"
IMG_QR = "qr.png"


@dataclass
class GradeReport:
    """The full stats record behind a slab's QR code."""

    cert_id: str
    graded_at: str            # ISO-8601 UTC
    report_url: str

    overall_grade: float | None       # 1-10 (half steps)
    overall_score_1000: int | None    # 1-1000 scale (TAG-style)

    # Sub-grades (value + label), None if a factor wasn't assessed.
    centering_grade: float | None
    centering_label: str
    corners_grade: float | None
    corners_label: str
    edges_grade: float | None
    edges_label: str
    surface_grade: float | None
    surface_label: str

    # Per-factor breakdowns ------------------------------------------------
    centering_detail: dict           # ratios + margins (px)
    corners_detail: dict             # per-corner 1-10 grade
    edges_detail: dict               # per-edge 1-10 grade
    surface_detail: dict             # defect density

    images: dict = field(default_factory=dict)   # role -> filename
    meta: dict = field(default_factory=dict)      # optional card/population info

    def to_dict(self) -> dict:
        return asdict(self)


def mint_cert_id() -> str:
    """A short, human-readable certificate id, e.g. ``FAN-3F9A2C7B1D``."""
    return "FAN-" + uuid.uuid4().hex[:10].upper()


def _score_1000(overall: float | None) -> int | None:
    """Map a 1-10 overall grade onto a 1-1000 scale (TAG-style headline number)."""
    if overall is None:
        return None
    return int(round(overall * 100))


def build_report(
    result: PipelineResult,
    cert_id: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    graded_at: str | None = None,
    meta: dict | None = None,
) -> GradeReport:
    """Assemble a :class:`GradeReport` from a pipeline result.

    Per-corner / per-edge 1-10 scores are derived by running the same condition
    grade scales over each region's individual wear score, so the breakdown is
    internally consistent with the aggregate sub-grades.
    """
    cert_id = cert_id or mint_cert_id()
    graded_at = graded_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    grade = result.grade

    # Centering breakdown.
    c = result.centering
    centering_detail = {
        "horizontal_pct": {"left": c.horizontal_ratio[0], "right": c.horizontal_ratio[1]},
        "vertical_pct": {"top": c.vertical_ratio[0], "bottom": c.vertical_ratio[1]},
        "margins_px": {"left": c.left, "right": c.right, "top": c.top, "bottom": c.bottom},
        "method": c.method,
    }

    # Per-corner / per-edge 1-10 grades from their individual wear.
    corners_detail = {}
    if result.corners is not None:
        corners_detail = {
            name: grade_corners(w)[0] for name, w in result.corners.per_corner.items()
        }
    edges_detail = {}
    if result.edges is not None:
        edges_detail = {
            name: grade_edges(w)[0] for name, w in result.edges.per_edge.items()
        }
    surface_detail = {}
    if result.surface is not None:
        surface_detail = {
            "defect_density_pct": round(result.surface.defect_fraction * 100.0, 3)
        }

    return GradeReport(
        cert_id=cert_id,
        graded_at=graded_at,
        report_url=f"{base_url.rstrip('/')}/card/{cert_id}",
        overall_grade=grade.overall,
        overall_score_1000=_score_1000(grade.overall),
        centering_grade=grade.centering_grade,
        centering_label=grade.centering_label,
        corners_grade=grade.corners,
        corners_label=grade.corners_label,
        edges_grade=grade.edges,
        edges_label=grade.edges_label,
        surface_grade=grade.surface,
        surface_label=grade.surface_label,
        centering_detail=centering_detail,
        corners_detail=corners_detail,
        edges_detail=edges_detail,
        surface_detail=surface_detail,
        images={"original": IMG_ORIGINAL, "centering": IMG_CENTERING,
                "condition": IMG_CONDITION, "qr": IMG_QR},
        meta=meta or {},
    )


def make_qr_image(url: str):
    """Return a PIL image of the QR code for ``url`` (requires ``qrcode``)."""
    import qrcode

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")


def make_qr_png_bytes(url: str) -> bytes:
    """Return the QR code for ``url`` as PNG bytes."""
    import io

    buf = io.BytesIO()
    make_qr_image(url).save(buf, format="PNG")
    return buf.getvalue()


def save_report(report: GradeReport, result: PipelineResult, store_dir: str) -> str:
    """Persist the report JSON, annotated images and QR PNG under the cert folder.

    Returns the path to the written cert folder.
    """
    import cv2

    cert_dir = os.path.join(store_dir, report.cert_id)
    os.makedirs(cert_dir, exist_ok=True)

    det = result.detection
    cv2.imwrite(os.path.join(cert_dir, IMG_ORIGINAL), annotate_original(det))
    cv2.imwrite(os.path.join(cert_dir, IMG_CENTERING),
                annotate_rectified(det.rectified, result.centering))
    cv2.imwrite(os.path.join(cert_dir, IMG_CONDITION),
                annotate_condition(det.rectified, result.corners, result.edges, result.surface))

    with open(os.path.join(cert_dir, IMG_QR), "wb") as fh:
        fh.write(make_qr_png_bytes(report.report_url))

    with open(os.path.join(cert_dir, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(report.to_dict(), fh, indent=2)

    return cert_dir


def load_report(store_dir: str, cert_id: str) -> GradeReport | None:
    """Load a persisted report by cert id, or ``None`` if it doesn't exist."""
    path = os.path.join(store_dir, cert_id, "report.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return GradeReport(**json.load(fh))


def grade_image_to_report(
    image_bgr,
    store_dir: str,
    base_url: str = DEFAULT_BASE_URL,
    cert_id: str | None = None,
    meta: dict | None = None,
    calibration=None,
) -> GradeReport:
    """Run the pipeline on an image, mint a cert, persist the report + QR.

    ``calibration`` (a ``calibration.Calibration``) applies a learned grade
    mapping if supplied.
    """
    from pipeline import run_pipeline

    result = run_pipeline(image_bgr, calibration=calibration)
    report = build_report(result, cert_id=cert_id, base_url=base_url, meta=meta)
    save_report(report, result, store_dir)
    return report


def _cli(argv: list[str] | None = None) -> int:
    import argparse

    import cv2

    parser = argparse.ArgumentParser(
        description="Grade a card image, mint a cert, and write its QR report."
    )
    parser.add_argument("image", help="Path to a card photo.")
    parser.add_argument("--store", default="./cards", help="Report store directory.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help="Public base URL the QR points at.")
    parser.add_argument("--calibration", default=os.environ.get("FANSIST_CALIBRATION"),
                        help="Path to a trained calibration.json (or set "
                             "FANSIST_CALIBRATION).")
    args = parser.parse_args(argv)

    from calibration import load_optional
    calibration = load_optional(args.calibration)

    image = cv2.imread(args.image, cv2.IMREAD_COLOR)
    if image is None:
        print(f"error: could not read image {args.image!r}")
        return 2
    try:
        report = grade_image_to_report(image, args.store, base_url=args.base_url,
                                       calibration=calibration)
    except Exception as exc:  # detection or processing failure
        print(json.dumps({"error": str(exc)}))
        return 1

    print(json.dumps({
        "cert_id": report.cert_id,
        "report_url": report.report_url,
        "overall_grade": report.overall_grade,
        "overall_score_1000": report.overall_score_1000,
        "calibrated": calibration is not None,
        "stored": os.path.join(os.path.abspath(args.store), report.cert_id),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
