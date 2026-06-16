"""Tests for the capture -> human-grader product loop (no AI grading)."""

import cv2
import numpy as np
import pytest

from capture_qc import check_image
from submission import (
    CODE_QR,
    STATUS_GRADED,
    STATUS_PENDING,
    STATUS_PRINTED,
    create_submission,
    grade_submission,
    list_submissions,
    load_submission,
    mark_printed,
)
import kiosk
from grader_portal import create_app as grader_app
from web_report import create_app as report_app
from conftest import make_card, make_scene


# --- capture_qc -------------------------------------------------------------

def test_qc_detects_card_and_metrics():
    res = check_image(make_scene())
    assert res.metrics["card_detected"] is True
    assert "sharpness" in res.metrics and "glare_fraction" in res.metrics


def test_qc_flags_blur_and_low_resolution():
    scene = make_scene()
    sharp = check_image(scene).metrics["sharpness"]
    blurred = check_image(cv2.GaussianBlur(scene, (0, 0), 6))
    assert blurred.metrics["sharpness"] < sharp        # blur lowers sharpness
    # 800x900 synthetic is below the high-quality resolution bar.
    assert any("resolution" in i for i in check_image(scene).issues)


def test_qc_empty_image():
    assert check_image(np.empty((0, 0, 3), np.uint8)).ok is False


# --- submission lifecycle ---------------------------------------------------

def test_create_submission_writes_images_and_qc(tmp_path):
    sub = create_submission(make_scene(), make_scene(), meta={"name": "Victini"},
                            store_dir=str(tmp_path))
    folder = tmp_path / sub["id"]
    assert (folder / "front.png").exists() and (folder / "back.png").exists()
    assert (folder / "submission.json").exists()
    assert sub["status"] == STATUS_PENDING
    assert set(sub["qc"]) == {"front", "back"}
    assert sub["cert_id"] is None


def test_pending_then_graded(tmp_path):
    sub = create_submission(make_scene(), meta={"name": "Victini"}, store_dir=str(tmp_path))
    sid = sub["id"]
    assert [r["id"] for r in list_submissions(str(tmp_path), STATUS_PENDING)] == [sid]

    grade_submission(str(tmp_path), sid, {"overall": 9, "centering": 8}, graded_by="alice",
                     notes="sharp corners")
    graded = load_submission(str(tmp_path), sid)
    assert graded["status"] == STATUS_GRADED
    assert graded["grade"]["overall"] == 9.0
    assert graded["cert_id"] == sid
    assert (tmp_path / sid / "report.json").exists()
    assert (tmp_path / sid / "qr.png").exists()
    # No longer pending.
    assert list_submissions(str(tmp_path), STATUS_PENDING) == []


def test_grade_requires_overall(tmp_path):
    sub = create_submission(make_scene(), store_dir=str(tmp_path))
    with pytest.raises(ValueError):
        grade_submission(str(tmp_path), sub["id"], {"centering": 8})


# --- kiosk: slab code QR, status, and grade-print release -------------------

def test_slab_code_qr_written_at_intake(tmp_path):
    sub = create_submission(make_scene(), store_dir=str(tmp_path),
                            base_url="https://example.test")
    assert (tmp_path / sub["id"] / CODE_QR).exists()        # slab tracking QR
    assert sub["status_url"].endswith(f"/status/{sub['id']}")


def test_print_release_lifecycle(tmp_path):
    sub = create_submission(make_scene(), store_dir=str(tmp_path))
    sid = sub["id"]

    # Can't print before it's graded.
    with pytest.raises(ValueError):
        mark_printed(str(tmp_path), sid)

    grade_submission(str(tmp_path), sid, {"overall": 9}, graded_by="alice")
    printed = mark_printed(str(tmp_path), sid)
    assert printed["status"] == STATUS_PRINTED
    assert printed["printed_at"] is not None

    # Idempotent-safe: can't re-print an already-printed slab.
    with pytest.raises(ValueError):
        mark_printed(str(tmp_path), sid)


def test_kiosk_cli_status_and_print(tmp_path, capsys):
    sub = create_submission(make_scene(), meta={"name": "Victini"}, store_dir=str(tmp_path))
    sid = sub["id"]
    assert kiosk.main(["status", sid, "--store", str(tmp_path)]) == 0
    assert "PENDING_REVIEW" in capsys.readouterr().out

    # Not graded -> print refused.
    assert kiosk.main(["print", sid, "--store", str(tmp_path)]) == 1

    grade_submission(str(tmp_path), sid, {"overall": 9, "corners": 9}, graded_by="alice")
    assert kiosk.main(["print", sid, "--store", str(tmp_path)]) == 0
    assert "LASER-MARK" in capsys.readouterr().out
    assert load_submission(str(tmp_path), sid)["status"] == STATUS_PRINTED


def test_status_website(tmp_path):
    sub = create_submission(make_scene(), meta={"name": "Victini"}, store_dir=str(tmp_path),
                            base_url="https://example.test")
    sid = sub["id"]
    client = report_app(str(tmp_path)).test_client()

    # Pending: status works (the slab QR points here) but no grade shown.
    pending = client.get(f"/status/{sid}")
    assert pending.status_code == 200
    assert "REVIEW" in pending.get_data(as_text=True)

    grade_submission(str(tmp_path), sid, {"overall": 9}, graded_by="alice")
    graded = client.get(f"/status/{sid}").get_data(as_text=True)
    assert "GRADED" in graded and "/card/" in graded

    mark_printed(str(tmp_path), sid)
    assert "PRINTED" in client.get(f"/status/{sid}").get_data(as_text=True)
    assert client.get("/status/FAN-NOPE000000").status_code == 404


# --- graded submission is served by the public report app -------------------

def test_public_report_serves_graded_submission(tmp_path):
    sub = create_submission(make_scene(), make_scene(), meta={"name": "Victini"},
                            store_dir=str(tmp_path), base_url="https://example.test")
    sid = sub["id"]
    grade_submission(str(tmp_path), sid, {"overall": 9}, graded_by="alice")

    client = report_app(str(tmp_path)).test_client()
    resp = client.get(f"/card/{sid}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "human grader" in body and "Victini" in body
    assert client.get(f"/card/{sid}/img/front.png").status_code == 200
    # Pending (ungraded) submissions are NOT public.
    pending = create_submission(make_scene(), store_dir=str(tmp_path))
    assert client.get(f"/card/{pending['id']}").status_code == 404


# --- grader portal ----------------------------------------------------------

def test_grader_portal_queue_view_and_grade(tmp_path):
    sub = create_submission(make_scene(), meta={"name": "Victini"}, store_dir=str(tmp_path))
    sid = sub["id"]
    client = grader_app(str(tmp_path)).test_client()

    assert sid in client.get("/").get_data(as_text=True)
    assert client.get(f"/submission/{sid}").status_code == 200
    assert client.get(f"/submission/{sid}/img/front.png").status_code == 200

    resp = client.post(f"/submission/{sid}/grade",
                       data={"overall": "8.5", "graded_by": "alice", "notes": "nice"})
    assert resp.status_code in (302, 303)
    assert load_submission(str(tmp_path), sid)["status"] == STATUS_GRADED
    # Missing overall is rejected.
    sub2 = create_submission(make_scene(), store_dir=str(tmp_path))
    bad = client.post(f"/submission/{sub2['id']}/grade", data={"centering": "8"})
    assert bad.status_code == 400
