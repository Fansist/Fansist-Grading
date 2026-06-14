"""app.py

Streamlit UI for the v1 trading-card CENTERING grader.

Run with:

    streamlit run app.py

Flow: upload one photo -> detect & rectify the card -> measure the inner-border
margins -> grade the centering -> show the original, an annotated rectified
card, and the numeric results. Detection failures are reported with a friendly
explanation instead of a crash/stack trace.
"""

from __future__ import annotations

import cv2
import numpy as np
import streamlit as st

from card_detector import CardDetection, CardDetectionError, detect_card
from centering import CenteringResult, measure_centering
from grading import CardGrade, build_grade

# ---------------------------------------------------------------------------
# Annotation drawing helpers (all colours are BGR; converted to RGB for display)
# ---------------------------------------------------------------------------

OUTER_EDGE_COLOR = (0, 165, 255)   # orange  -> outer card edge
INNER_BORDER_COLOR = (0, 0, 255)   # red     -> detected inner border
LABEL_COLOR = (0, 255, 0)          # green   -> margin-width text
CORNER_COLOR = (255, 0, 255)       # magenta -> detected corners on the original


def _bgr_to_rgb(image: np.ndarray) -> np.ndarray:
    """Convert a BGR (OpenCV) image to RGB for display in Streamlit."""
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def _scaled_line_thickness(image: np.ndarray) -> int:
    """Line thickness that stays visible regardless of card resolution."""
    return max(2, int(round(min(image.shape[:2]) / 300)))


def annotate_rectified(card_bgr: np.ndarray, result: CenteringResult) -> np.ndarray:
    """Draw the outer edge, inner border and margin-width labels on the card.

    Returns an RGB image ready for ``st.image``.
    """
    canvas = card_bgr.copy()
    h, w = canvas.shape[:2]
    thickness = _scaled_line_thickness(canvas)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(0.5, min(h, w) / 900.0)

    # Outer card edge = the rectified image's own border.
    cv2.rectangle(canvas, (0, 0), (w - 1, h - 1), OUTER_EDGE_COLOR, thickness)

    # Inner border rectangle.
    x_left, y_top, x_right, y_bottom = result.inner_rect
    cv2.rectangle(canvas, (x_left, y_top), (x_right, y_bottom), INNER_BORDER_COLOR, thickness)

    def put_label(text: str, org: tuple[int, int]) -> None:
        cv2.putText(canvas, text, org, font, font_scale, LABEL_COLOR, thickness, cv2.LINE_AA)

    mid_y = (y_top + y_bottom) // 2
    mid_x = (x_left + x_right) // 2
    pad = int(8 * font_scale) + 4

    # Place each label inside its margin band.
    put_label(f"L:{result.left}px", (pad, mid_y))
    put_label(f"R:{result.right}px", (max(pad, x_right + pad), mid_y))
    put_label(f"T:{result.top}px", (mid_x, max(int(20 * font_scale), y_top - pad)))
    put_label(f"B:{result.bottom}px", (mid_x, min(h - pad, y_bottom + int(22 * font_scale))))

    return _bgr_to_rgb(canvas)


def annotate_original(detection: CardDetection) -> np.ndarray:
    """Draw the detected card outline and corners on the (downscaled) photo."""
    canvas = detection.source.copy()
    thickness = _scaled_line_thickness(canvas)
    corners = detection.corners.astype(int)

    cv2.polylines(canvas, [corners.reshape(-1, 1, 2)], isClosed=True,
                  color=OUTER_EDGE_COLOR, thickness=thickness)
    for (x, y) in corners:
        cv2.circle(canvas, (int(x), int(y)), thickness * 2, CORNER_COLOR, -1)

    return _bgr_to_rgb(canvas)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def decode_upload(uploaded_file) -> np.ndarray | None:
    """Decode an uploaded image file into a BGR OpenCV image, or None on failure."""
    data = np.frombuffer(uploaded_file.getvalue(), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def run_pipeline(image_bgr: np.ndarray) -> tuple[CardDetection, CenteringResult, CardGrade]:
    """Run detect -> measure -> grade on a BGR image."""
    detection = detect_card(image_bgr)
    centering = measure_centering(detection.rectified)
    grade = build_grade(centering.horizontal_ratio, centering.vertical_ratio)
    return detection, centering, grade


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def render_results(image_bgr: np.ndarray) -> None:
    """Run the pipeline on the uploaded image and render all outputs."""
    try:
        detection, centering, grade = run_pipeline(image_bgr)
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

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Original (detected outline)")
        st.image(annotate_original(detection), use_container_width=True)
    with col_b:
        st.subheader("Rectified card + measurements")
        st.image(annotate_rectified(detection.rectified, centering), use_container_width=True)

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
        st.json(
            {
                "centering_ratio_h": list(grade.centering_ratio_h),
                "centering_ratio_v": list(grade.centering_ratio_v),
                "centering_grade": grade.centering_grade,
                "centering_label": grade.centering_label,
                "corners": grade.corners,
                "edges": grade.edges,
                "surface": grade.surface,
                "overall": grade.overall,
            }
        )


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

    image_bgr = decode_upload(uploaded)
    if image_bgr is None:
        st.error("That file could not be read as an image. Try a JPG or PNG.")
        return

    render_results(image_bgr)


if __name__ == "__main__":
    main()
