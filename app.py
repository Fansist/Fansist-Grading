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
    run_pipeline,
)
from report import DEFAULT_BASE_URL, build_report, make_qr_png_bytes, save_report


def _bgr_to_rgb(image: np.ndarray) -> np.ndarray:
    """Convert a BGR (OpenCV) image to RGB for display in Streamlit."""
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def render_results(image_bgr: np.ndarray) -> None:
    """Run the pipeline on the uploaded image and render all outputs."""
    try:
        result = run_pipeline(image_bgr)
    except CardDetectionError as exc:
        st.error(
            "Could not detect the card.\n\n"
            f"**Reason:** {exc}\n\n"
            "Tips: use a plain, high-contrast background, make sure the whole "
            "card is in frame and fills most of it, avoid glare and shadows, "
            "and hold the camera parallel to the card."
        )
        return
    except Exception as exc:  # pragma: no cover - defensive guard for the UI
        st.error(f"Unexpected error while processing the image: {exc}")
        return

    detection, centering, grade = result.detection, result.centering, result.grade
    rectified = detection.rectified

    # --- Overall grade headline ---------------------------------------------
    if grade.overall is not None:
        st.subheader(f"Overall grade: {grade.overall:g}")

    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Centering", f"{grade.centering_grade:g}", grade.centering_label)
    g2.metric("Corners", "—" if grade.corners is None else f"{grade.corners:g}",
              grade.corners_label or None)
    g3.metric("Edges", "—" if grade.edges is None else f"{grade.edges:g}",
              grade.edges_label or None)
    g4.metric("Surface", "—" if grade.surface is None else f"{grade.surface:g}",
              grade.surface_label or None)

    # --- Annotated images ----------------------------------------------------
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.caption("Original (detected outline)")
        st.image(_bgr_to_rgb(annotate_original(detection)), use_container_width=True)
    with col_b:
        st.caption("Centering (outer edge, inner border, margins)")
        st.image(_bgr_to_rgb(annotate_rectified(rectified, centering)),
                 use_container_width=True)
    with col_c:
        st.caption("Condition (corners/edges by wear; surface defects in red)")
        st.image(
            _bgr_to_rgb(annotate_condition(rectified, result.corners, result.edges,
                                           result.surface)),
            use_container_width=True,
        )

    # --- Numeric detail ------------------------------------------------------
    h_left, h_right = centering.horizontal_ratio
    v_top, v_bottom = centering.vertical_ratio
    st.caption(
        f"Centering ratios — L:R {h_left:.0f}/{h_right:.0f}, "
        f"T:B {v_top:.0f}/{v_bottom:.0f}. "
        f"Margins (px) L {centering.left}, R {centering.right}, "
        f"T {centering.top}, B {centering.bottom}. Method: {centering.method}."
    )

    st.warning(
        "These are automated estimates from a single image. Corners and edges "
        "measure colour whitening/chipping; **surface** is the lowest-confidence "
        "factor from one flat photo (true scratch/dent detection needs raking "
        "light — see the hardware blueprint). Not an official grade."
    )

    with st.expander("Full grade object (JSON)"):
        st.json(grade.to_dict())

    # --- Slab QR + shareable report -----------------------------------------
    base_url = os.environ.get("FANSIST_BASE_URL", DEFAULT_BASE_URL)
    report = build_report(result, base_url=base_url)
    store = os.environ.get("FANSIST_STORE")
    if store:  # persist so the web report page (web_report.py) can serve it
        save_report(report, result, store)

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
        "Upload a single photo of a trading card on a **plain, high-contrast "
        "background** with even, glare-free lighting and the camera held "
        "parallel to the card. Grades **centering, corners, edges and surface**, "
        "then combines them into an overall grade."
    )

    uploaded = st.file_uploader(
        "Card image", type=["jpg", "jpeg", "png", "bmp", "webp"], accept_multiple_files=False
    )

    if uploaded is None:
        st.info("Upload an image to begin. See the README for imaging guidelines.")
        return

    image_bgr = decode_image(uploaded.getvalue())
    if image_bgr is None:
        st.error("That file could not be read as an image. Try a JPG or PNG.")
        return

    render_results(image_bgr)


if __name__ == "__main__":
    main()
