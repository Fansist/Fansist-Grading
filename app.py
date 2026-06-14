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

from card_detector import CardDetectionError
from pipeline import (
    annotate_original,
    annotate_rectified,
    decode_image,
    run_pipeline,
)


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

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Original (detected outline)")
        st.image(_bgr_to_rgb(annotate_original(detection)), use_container_width=True)
    with col_b:
        st.subheader("Rectified card + measurements")
        st.image(
            _bgr_to_rgb(annotate_rectified(detection.rectified, centering)),
            use_container_width=True,
        )

    st.subheader("Centering results")
    h_left, h_right = centering.horizontal_ratio
    v_top, v_bottom = centering.vertical_ratio

    m1, m2, m3 = st.columns(3)
    m1.metric("Horizontal (L : R)", f"{h_left:.0f} / {h_right:.0f}")
    m2.metric("Vertical (T : B)", f"{v_top:.0f} / {v_bottom:.0f}")
    m3.metric("Centering grade", f"{grade.centering_grade:g}", grade.centering_label)

    st.caption(
        f"Margins (px) -- left {centering.left}, right {centering.right}, "
        f"top {centering.top}, bottom {centering.bottom}. "
        f"Inner-border method: {centering.method}."
    )

    with st.expander("Full grade object (centering only in v1)"):
        st.json(grade.to_dict())


def main() -> None:
    st.set_page_config(page_title="Card Centering Grader", page_icon="🃏", layout="wide")
    st.title("🃏 Trading Card Centering Grader (v1)")
    st.write(
        "Upload a single photo of a trading card on a **plain, high-contrast "
        "background** with even, glare-free lighting and the camera held "
        "parallel to the card. v1 grades **centering only**."
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
