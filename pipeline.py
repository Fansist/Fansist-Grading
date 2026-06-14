"""pipeline.py

Headless orchestration of the centering grader: detect -> measure -> grade,
plus image decoding and annotation drawing. This module has **no Streamlit
dependency**, so it can be used:

  * by the Streamlit UI (`app.py`),
  * as a command-line tool (``python pipeline.py CARD.jpg``),
  * and by the automated imaging/slabbing machine as a plain library call
    (see docs/HARDWARE_BLUEPRINT.md).

Annotation helpers draw on (and return) BGR images so the CLI can write them
straight out with ``cv2.imwrite``; the UI converts to RGB only at display time.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass

import cv2
import numpy as np

from card_detector import CardDetection, CardDetectionError, detect_card
from centering import CenteringResult, measure_centering
from grading import CardGrade, build_grade

# ---------------------------------------------------------------------------
# Annotation colours (BGR) and styling
# ---------------------------------------------------------------------------

OUTER_EDGE_COLOR = (0, 165, 255)   # orange  -> outer card edge
INNER_BORDER_COLOR = (0, 0, 255)   # red     -> detected inner border
LABEL_COLOR = (0, 255, 0)          # green   -> margin-width text
CORNER_COLOR = (255, 0, 255)       # magenta -> detected corners on the original


@dataclass
class PipelineResult:
    """Everything the front-ends need from one card image."""

    detection: CardDetection
    centering: CenteringResult
    grade: CardGrade


def decode_image(data: bytes) -> np.ndarray | None:
    """Decode raw image bytes into a BGR OpenCV image, or ``None`` on failure."""
    buffer = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


def run_pipeline(image_bgr: np.ndarray) -> PipelineResult:
    """Run detect -> measure -> grade on a BGR image.

    Raises:
        CardDetectionError: If the card cannot be located (callers should catch
            this and report it gracefully rather than crash).
    """
    detection = detect_card(image_bgr)
    centering = measure_centering(detection.rectified)
    grade = build_grade(centering.horizontal_ratio, centering.vertical_ratio)
    return PipelineResult(detection=detection, centering=centering, grade=grade)


# ---------------------------------------------------------------------------
# Annotation drawing (returns BGR)
# ---------------------------------------------------------------------------

def _scaled_line_thickness(image: np.ndarray) -> int:
    """Line thickness that stays visible regardless of card resolution."""
    return max(2, int(round(min(image.shape[:2]) / 300)))


def annotate_rectified(card_bgr: np.ndarray, result: CenteringResult) -> np.ndarray:
    """Draw outer edge, inner border and margin-width labels on the card (BGR)."""
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

    put_label(f"L:{result.left}px", (pad, mid_y))
    put_label(f"R:{result.right}px", (max(pad, x_right + pad), mid_y))
    put_label(f"T:{result.top}px", (mid_x, max(int(20 * font_scale), y_top - pad)))
    put_label(f"B:{result.bottom}px", (mid_x, min(h - pad, y_bottom + int(22 * font_scale))))

    return canvas


def annotate_original(detection: CardDetection) -> np.ndarray:
    """Draw the detected card outline and corners on the source photo (BGR)."""
    canvas = detection.source.copy()
    thickness = _scaled_line_thickness(canvas)
    corners = detection.corners.astype(int)

    cv2.polylines(canvas, [corners.reshape(-1, 1, 2)], isClosed=True,
                  color=OUTER_EDGE_COLOR, thickness=thickness)
    for (x, y) in corners:
        cv2.circle(canvas, (int(x), int(y)), thickness * 2, CORNER_COLOR, -1)

    return canvas


# ---------------------------------------------------------------------------
# Command-line interface (headless grading of an image file)
# ---------------------------------------------------------------------------

def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Grade the centering of a single card image (headless)."
    )
    parser.add_argument("image", help="Path to a card photo (jpg/png/...).")
    parser.add_argument(
        "--out-prefix",
        help="If set, write annotated images to <prefix>_original.png and "
             "<prefix>_rectified.png.",
    )
    args = parser.parse_args(argv)

    image_bgr = cv2.imread(args.image, cv2.IMREAD_COLOR)
    if image_bgr is None:
        print(f"error: could not read image {args.image!r}", file=sys.stderr)
        return 2

    try:
        result = run_pipeline(image_bgr)
    except CardDetectionError as exc:
        print(json.dumps({"error": "card_detection_failed", "detail": str(exc)}))
        return 1

    print(json.dumps(result.grade.to_dict(), indent=2))

    if args.out_prefix:
        cv2.imwrite(f"{args.out_prefix}_original.png", annotate_original(result.detection))
        cv2.imwrite(
            f"{args.out_prefix}_rectified.png",
            annotate_rectified(result.detection.rectified, result.centering),
        )
        print(f"wrote {args.out_prefix}_original.png and {args.out_prefix}_rectified.png",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
