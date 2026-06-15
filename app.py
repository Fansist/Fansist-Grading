"""app.py

Streamlit UI for the v1 trading-card CENTERING grader.

Run with:

    streamlit run app.py

This module is the *human* front-end only: it handles upload and display. All
the actual work (detect -> measure -> grade, decoding, annotation) lives in the
Streamlit-free ``pipeline`` module so the same logic can run headless (CLI) or
inside the automated imaging/slabbing machine (see docs/HARDWARE_BLUEPRINT.md).

Flow: upload one photo -> run the pipeline -> show the original (with detected
outline), the annotated rectified card, and the numeric results. Detection
failures are reported with a friendly explanation instead of a crash.
"""

from __future__ import annotations

import cv2
import numpy as np
import streamlit as st

import os

from card_detector import CardDetectionError
from pipeline import (
    annotate_condition,
    annotate_original,
    annotate_rectified,
    decode_image,
    grade_card,
)
from report import DEFAULT_BASE_URL, build_report, make_qr_png_bytes, save_report

_TYPES = ["jpg", "jpeg", "png", "bmp", "webp"]


def _bgr_to_rgb(image: np.ndarray) -> np.ndarray:
    """Convert a BGR (OpenCV) image to RGB for display in Streamlit."""
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def _render_side(label: str | None, result) -> None:
    """Show one side's three annotated images."""
    if label:
        st.markdown(f"**{label}**")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.caption("Original (detected outline)")
        st.image(_bgr_to_rgb(annotate_original(result.detection)), use_container_width=True)
    with col_b:
        st.caption("Centering (outer edge, inner border, margins)")
        st.image(_bgr_to_rgb(annotate_rectified(result.detection.rectified, result.centering)),
                 use_container_width=True)
    with col_c:
        st.caption("Condition (corners/edges by wear; surface defects in red)")
        st.image(_bgr_to_rgb(annotate_condition(result.detection.rectified, result.corners,
                                                result.edges, result.surface)),
                 use_container_width=True)


def render_results(front_bgr: np.ndarray, back_bgr: np.ndarray | None = None) -> None:
    """Grade the card (front + optional back) and render all outputs."""
    from calibration import load_optional
    calibration = load_optional(os.environ.get("FANSIST_CALIBRATION"))
    try:
        ts = grade_card(front_bgr, back_bgr, calibration=calibration)
    except CardDetectionError as exc:
        st.error(
            "Could not detect the card.\n\n"
            f"**Reason:** {exc}\n\n"
            "Tips: plain high-contrast background, whole card in frame, no glare, "
            "camera parallel to the card. (If you added a back image, check it too.)"
        )
        return
    except Exception as exc:  # pragma: no cover - defensive guard for the UI
        st.error(f"Unexpected error while processing the image: {exc}")
        return

    front, back, grade = ts.front, ts.back, ts.combined

    # --- Overall grade headline ---------------------------------------------
    if grade.overall is not None:
        st.subheader(f"Overall grade: {grade.overall:g}")
    if back is not None:
        st.caption("Graded from **front + back** (worse side per factor).")
    if calibration is not None:
        st.caption("⚙️ Calibrated to your graded-card dataset (FANSIST_CALIBRATION).")

    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Centering", f"{grade.centering_grade:g}", grade.centering_label)
    g2.metric("Corners", "—" if grade.corners is None else f"{grade.corners:g}",
              grade.corners_label or None)
    g3.metric("Edges", "—" if grade.edges is None else f"{grade.edges:g}",
              grade.edges_label or None)
    g4.metric("Surface", "—" if grade.surface is None else f"{grade.surface:g}",
              grade.surface_label or None)

    # --- Annotated images (per side) ----------------------------------------
    _render_side("Front" if back is not None else None, front)
    if back is not None:
        _render_side("Back", back)

    st.warning(
        "Automated estimates. Corners and edges measure colour whitening/chipping; "
        "**surface** is the lowest-confidence factor from a flat photo (true "
        "scratch/dent detection needs raking light — see the hardware blueprint). "
        "Not an official grade."
    )

    with st.expander("Full grade object (JSON)"):
        st.json(grade.to_dict())

    # --- Slab QR + shareable report -----------------------------------------
    base_url = os.environ.get("FANSIST_BASE_URL", DEFAULT_BASE_URL)
    report = build_report(front, base_url=base_url, back=back,
                          combined=grade if back is not None else None)
    store = os.environ.get("FANSIST_STORE")
    if store:  # persist so the web report page (web_report.py) can serve it
        save_report(report, front, store, back_result=back)

    st.subheader("Slab QR & report")
    qr_col, info_col = st.columns([1, 3])
    with qr_col:
        st.image(make_qr_png_bytes(report.report_url), width=170)
    with info_col:
        st.write(f"**Cert:** `{report.cert_id}`")
        st.write(f"**Overall:** {report.overall_grade:g}/10 "
                 f"({report.overall_score_1000}/1000)")
        st.write(f"**Report:** {report.report_url}")
        st.caption(
            "This QR is printed on the slab; scanning it opens the full report "
            "page (run `web_report.py` to serve it). Set FANSIST_STORE to persist "
            "each card and FANSIST_BASE_URL to your domain."
        )


def main() -> None:
    st.set_page_config(page_title="Card Grader", page_icon="🃏", layout="wide")
    st.title("🃏 Trading Card Grader")
    st.write(
        "Upload a photo of the card **front** (and optionally the **back**) on a "
        "plain, high-contrast background with even, glare-free lighting and the "
        "camera parallel to the card. Grades **centering, corners, edges and "
        "surface** into an overall grade; with a back image, each factor takes the "
        "worse of the two sides."
    )

    col_f, col_b = st.columns(2)
    front_file = col_f.file_uploader("Card FRONT", type=_TYPES, accept_multiple_files=False)
    back_file = col_b.file_uploader("Card BACK (optional)", type=_TYPES,
                                    accept_multiple_files=False)

    if front_file is None:
        st.info("Upload the front image to begin. See the README for imaging guidelines.")
        return

    front_bgr = decode_image(front_file.getvalue())
    if front_bgr is None:
        st.error("The front file could not be read as an image. Try a JPG or PNG.")
        return

    back_bgr = None
    if back_file is not None:
        back_bgr = decode_image(back_file.getvalue())
        if back_bgr is None:
            st.error("The back file could not be read as an image. Try a JPG or PNG.")
            return

    render_results(front_bgr, back_bgr)


if __name__ == "__main__":
    main()
