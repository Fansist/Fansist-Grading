"""Tests for report.py (QR + stats record) and web_report.py (the report page)."""

import numpy as np

from pipeline import run_pipeline
from report import (
    build_report,
    grade_image_to_report,
    load_report,
    make_qr_png_bytes,
    mint_cert_id,
    save_report,
    _score_1000,
)
from web_report import create_app
from conftest import make_scene


def _result():
    return run_pipeline(make_scene(left=40, right=60, top=50, bottom=50))


def test_mint_cert_id_is_unique_and_prefixed():
    a, b = mint_cert_id(), mint_cert_id()
    assert a.startswith("FAN-") and len(a) == 14
    assert a != b


def test_score_1000_mapping():
    assert _score_1000(10.0) == 1000
    assert _score_1000(4.5) == 450
    assert _score_1000(None) is None


def test_build_report_has_tag_style_breakdown():
    report = build_report(_result(), base_url="https://example.test")
    assert report.cert_id.startswith("FAN-")
    assert report.report_url == f"https://example.test/card/{report.cert_id}"
    assert 0 <= report.overall_score_1000 <= 1000

    # Four sub-grades present.
    for g in (report.centering_grade, report.corners_grade,
              report.edges_grade, report.surface_grade):
        assert g is not None

    # Per-corner and per-edge breakdowns: one 1-10 score each.
    assert set(report.corners_detail) == {"top_left", "top_right",
                                          "bottom_right", "bottom_left"}
    assert set(report.edges_detail) == {"top", "right", "bottom", "left"}
    for v in list(report.corners_detail.values()) + list(report.edges_detail.values()):
        assert 1.0 <= v <= 10.0

    # Centering measurements present and consistent.
    h = report.centering_detail["horizontal_pct"]
    assert abs(h["left"] + h["right"] - 100.0) < 0.5
    assert "defect_density_pct" in report.surface_detail


def test_qr_png_bytes_are_a_png():
    data = make_qr_png_bytes("https://example.test/card/FAN-ABCDEF0123")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(data) > 100


def test_save_and_load_roundtrip(tmp_path):
    result = _result()
    report = build_report(result, base_url="https://example.test")
    save_report(report, result, str(tmp_path))

    cert_dir = tmp_path / report.cert_id
    for name in ("report.json", "qr.png", "original.png", "centering.png", "condition.png"):
        assert (cert_dir / name).exists()

    loaded = load_report(str(tmp_path), report.cert_id)
    assert loaded is not None
    assert loaded.to_dict() == report.to_dict()


def test_load_missing_returns_none(tmp_path):
    assert load_report(str(tmp_path), "FAN-NOPE000000") is None


def test_grade_image_to_report_persists(tmp_path):
    scene = make_scene()
    report = grade_image_to_report(scene, str(tmp_path), base_url="https://example.test")
    assert (tmp_path / report.cert_id / "report.json").exists()


# --- Web report page --------------------------------------------------------

def _app_with_one_card(tmp_path):
    result = _result()
    report = build_report(result, base_url="https://example.test")
    save_report(report, result, str(tmp_path))
    return create_app(str(tmp_path)), report.cert_id


def test_web_card_page_renders(tmp_path):
    app, cert_id = _app_with_one_card(tmp_path)
    client = app.test_client()
    resp = client.get(f"/card/{cert_id}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    for needle in (cert_id, "Overall", "Centering", "Corners", "Edges", "Surface"):
        assert needle in body


def test_web_serves_images_and_404s(tmp_path):
    app, cert_id = _app_with_one_card(tmp_path)
    client = app.test_client()
    assert client.get(f"/card/{cert_id}/img/qr.png").status_code == 200
    assert client.get("/card/FAN-MISSING000/img/qr.png").status_code == 404
    assert client.get("/card/FAN-MISSING000").status_code == 404
    assert client.get("/health").status_code == 200
