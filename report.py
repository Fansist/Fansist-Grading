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
IMG_BACK_ORIGINAL = "back_original.png"
IMG_BACK_CENTERING = "back_centering.png"
IMG_BACK_CONDITION = "back_condition.png"
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

    # Per-factor breakdowns (front) ----------------------------------------
    centering_detail: dict           # ratios + margins (px)
    corners_detail: dict             # per-corner 1-10 grade
    edges_detail: dict               # per-edge 1-10 grade
    surface_detail: dict             # defect density

    # Two-sided ------------------------------------------------------------
    sides: int = 1                   # 1 = front only, 2 = front + back
    back_centering_detail: dict = field(default_factory=dict)
    back_corners_detail: dict = field(default_factory=dict)
    back_edges_detail: dict = field(default_factory=dict)
    back_surface_detail: dict = field(default_factory=dict)

    images: dict = field(default_factory=dict)   # role -> filename
    meta: dict = field(default_factory=dict)      # card info / metadata

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


def _centering_detail(result: PipelineResult) -> dict:
    c = result.centering
    return {
        "horizontal_pct": {"left": c.horizontal_ratio[0], "right": c.horizontal_ratio[1]},
        "vertical_pct": {"top": c.vertical_ratio[0], "bottom": c.vertical_ratio[1]},
        "margins_px": {"left": c.left, "right": c.right, "top": c.top, "bottom": c.bottom},
        "method": c.method,
    }


def _corners_detail(result: PipelineResult) -> dict:
    if result.corners is None:
        return {}
    return {name: grade_corners(w)[0] for name, w in result.corners.per_corner.items()}


def _edges_detail(result: PipelineResult) -> dict:
    if result.edges is None:
        return {}
    return {name: grade_edges(w)[0] for name, w in result.edges.per_edge.items()}


def _surface_detail(result: PipelineResult) -> dict:
    if result.surface is None:
        return {}
    return {"defect_density_pct": round(result.surface.defect_fraction * 100.0, 3)}


def build_report(
    result: PipelineResult,
    cert_id: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    graded_at: str | None = None,
    meta: dict | None = None,
    back: PipelineResult | None = None,
    combined=None,
) -> GradeReport:
    """Assemble a :class:`GradeReport` from a pipeline result.

    Per-corner / per-edge 1-10 scores are derived by running the same condition
    grade scales over each region's individual wear score, so the breakdown is
    internally consistent with the aggregate sub-grades. When ``back`` is given,
    the headline grade is ``combined`` (worse-of-both-sides) and the report also
    carries the back-side breakdown and images.
    """
    cert_id = cert_id or mint_cert_id()
    graded_at = graded_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    grade = combined if (back is not None and combined is not None) else result.grade

    images = {"original": IMG_ORIGINAL, "centering": IMG_CENTERING,
              "condition": IMG_CONDITION, "qr": IMG_QR}
    back_centering = back_corners = back_edges = back_surface = {}
    if back is not None:
        back_centering = _centering_detail(back)
        back_corners = _corners_detail(back)
        back_edges = _edges_detail(back)
        back_surface = _surface_detail(back)
        images.update({"back_original": IMG_BACK_ORIGINAL,
                       "back_centering": IMG_BACK_CENTERING,
                       "back_condition": IMG_BACK_CONDITION})

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
        centering_detail=_centering_detail(result),
        corners_detail=_corners_detail(result),
        edges_detail=_edges_detail(result),
        surface_detail=_surface_detail(result),
        sides=2 if back is not None else 1,
        back_centering_detail=back_centering,
        back_corners_detail=back_corners,
        back_edges_detail=back_edges,
        back_surface_detail=back_surface,
        images=images,
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


def _write_side_images(cert_dir: str, result: PipelineResult, names: tuple[str, str, str]):
    import cv2

    det = result.detection
    cv2.imwrite(os.path.join(cert_dir, names[0]), annotate_original(det))
    cv2.imwrite(os.path.join(cert_dir, names[1]),
                annotate_rectified(det.rectified, result.centering))
    cv2.imwrite(os.path.join(cert_dir, names[2]),
                annotate_condition(det.rectified, result.corners, result.edges, result.surface))


def save_report(
    report: GradeReport,
    result: PipelineResult,
    store_dir: str,
    back_result: PipelineResult | None = None,
) -> str:
    """Persist the report JSON, annotated images and QR PNG under the cert folder.

    Writes back-side images too when ``back_result`` is given. Returns the cert
    folder path.
    """
    cert_dir = os.path.join(store_dir, report.cert_id)
    os.makedirs(cert_dir, exist_ok=True)

    _write_side_images(cert_dir, result, (IMG_ORIGINAL, IMG_CENTERING, IMG_CONDITION))
    if back_result is not None:
        _write_side_images(cert_dir, back_result,
                           (IMG_BACK_ORIGINAL, IMG_BACK_CENTERING, IMG_BACK_CONDITION))

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


def list_reports(store_dir: str) -> list[dict]:
    """Summaries of every stored cert (newest first) for the registry index."""
    out: list[dict] = []
    if not os.path.isdir(store_dir):
        return out
    for name in os.listdir(store_dir):
        path = os.path.join(store_dir, name, "report.json")
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        out.append({
            "cert_id": d.get("cert_id", name),
            "overall_grade": d.get("overall_grade"),
            "overall_score_1000": d.get("overall_score_1000"),
            "graded_at": d.get("graded_at", ""),
        })
    out.sort(key=lambda r: r["graded_at"], reverse=True)
    return out


def population(store_dir: str) -> int:
    """Total number of graded cards in the store (the registry 'population')."""
    return len(list_reports(store_dir))


def grade_card_to_report(
    front_bgr,
    back_bgr=None,
    store_dir: str = "./cards",
    base_url: str = DEFAULT_BASE_URL,
    cert_id: str | None = None,
    meta: dict | None = None,
    calibration=None,
    ml_model=None,
) -> GradeReport:
    """Grade a card (front + optional back), mint a cert, persist report + QR.

    ``calibration`` applies a learned grade mapping; ``ml_model`` (a trained CNN)
    grades the condition factors. With ``back_bgr`` the headline grade is the
    worse-of-both-sides combination.
    """
    from pipeline import grade_card

    ts = grade_card(front_bgr, back_bgr, calibration=calibration, ml_model=ml_model)
    report = build_report(ts.front, cert_id=cert_id, base_url=base_url, meta=meta,
                          back=ts.back, combined=ts.combined)
    save_report(report, ts.front, store_dir, back_result=ts.back)
    return report


def grade_image_to_report(
    image_bgr,
    store_dir: str,
    base_url: str = DEFAULT_BASE_URL,
    cert_id: str | None = None,
    meta: dict | None = None,
    calibration=None,
) -> GradeReport:
    """Front-only convenience wrapper around :func:`grade_card_to_report`."""
    return grade_card_to_report(image_bgr, None, store_dir, base_url, cert_id, meta, calibration)


def _cli(argv: list[str] | None = None) -> int:
    import argparse

    import cv2

    parser = argparse.ArgumentParser(
        description="Grade a card image, mint a cert, and write its QR report."
    )
    parser.add_argument("image", help="Path to the card FRONT photo.")
    parser.add_argument("--back", help="Path to the card BACK photo (optional).")
    parser.add_argument("--store", default="./cards", help="Report store directory.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help="Public base URL the QR points at.")
    parser.add_argument("--calibration", default=os.environ.get("FANSIST_CALIBRATION"),
                        help="Path to a trained calibration.json (or set "
                             "FANSIST_CALIBRATION).")
    parser.add_argument("--name", help="Card name (metadata).")
    parser.add_argument("--set", dest="card_set", help="Card set (metadata).")
    parser.add_argument("--number", help="Card number (metadata).")
    args = parser.parse_args(argv)

    from calibration import load_optional
    from pipeline import load_ml_optional
    calibration = load_optional(args.calibration)
    ml_model = load_ml_optional(os.environ.get("FANSIST_ML_MODEL"))

    front = cv2.imread(args.image, cv2.IMREAD_COLOR)
    if front is None:
        print(f"error: could not read image {args.image!r}")
        return 2
    back = None
    if args.back:
        back = cv2.imread(args.back, cv2.IMREAD_COLOR)
        if back is None:
            print(f"error: could not read back image {args.back!r}")
            return 2

    meta = {k: v for k, v in (("name", args.name), ("set", args.card_set),
                              ("number", args.number)) if v}
    try:
        report = grade_card_to_report(front, back, store_dir=args.store,
                                      base_url=args.base_url, meta=meta,
                                      calibration=calibration, ml_model=ml_model)
    except Exception as exc:  # detection or processing failure
        print(json.dumps({"error": str(exc)}))
        return 1

    print(json.dumps({
        "cert_id": report.cert_id,
        "report_url": report.report_url,
        "sides": report.sides,
        "overall_grade": report.overall_grade,
        "overall_score_1000": report.overall_score_1000,
        "calibrated": calibration is not None,
        "ml_model": ml_model is not None,
        "stored": os.path.join(os.path.abspath(args.store), report.cert_id),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
