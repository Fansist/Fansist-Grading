"""Tests for pipeline.py: end-to-end run, decoding, and annotation."""

import cv2
import numpy as np
import pytest

from card_detector import CardDetectionError
from pipeline import (
    annotate_original,
    annotate_rectified,
    decode_image,
    run_pipeline,
)
from conftest import make_scene


def test_run_pipeline_end_to_end():
    scene = make_scene(left=40, right=60, top=50, bottom=50)
    result = run_pipeline(scene)

    # Measured ratios match the synthetic ground truth (40:60, 50:50).
    assert abs(result.centering.horizontal_ratio[0] - 40.0) <= 3.0
    assert abs(result.centering.vertical_ratio[0] - 50.0) <= 3.0

    # worse ~60 -> Mint (grade 9) and overall mirrors centering in v1.
    assert result.grade.centering_grade == 9.0
    assert result.grade.overall == result.grade.centering_grade
    assert result.grade.corners is None


def test_run_pipeline_raises_on_noise():
    rng = np.random.default_rng(1)
    noise = rng.integers(0, 255, (500, 500, 3), dtype=np.uint8)
    with pytest.raises(CardDetectionError):
        run_pipeline(noise)


def test_annotations_return_same_size_bgr_images():
    scene = make_scene()
    result = run_pipeline(scene)

    orig = annotate_original(result.detection)
    rect = annotate_rectified(result.detection.rectified, result.centering)

    assert orig.shape == result.detection.source.shape
    assert rect.shape == result.detection.rectified.shape
    # Annotations add coloured pixels, so the images differ from the inputs.
    assert not np.array_equal(rect, result.detection.rectified)


def test_decode_image_roundtrip():
    img = np.full((20, 30, 3), 128, np.uint8)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    decoded = decode_image(buf.tobytes())
    assert decoded is not None
    assert decoded.shape == img.shape


def test_decode_image_garbage_returns_none():
    assert decode_image(b"not an image") is None
