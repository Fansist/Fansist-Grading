"""Tests for card_detector.py: corner ordering, warp, detection + failures."""

import numpy as np
import pytest

from card_detector import (
    CardDetectionError,
    detect_card,
    four_point_transform,
    order_points,
)
from conftest import CARD_H, CARD_W, make_scene


def test_order_points_orders_tl_tr_br_bl():
    # Deliberately scrambled order.
    pts = np.array([[100, 100], [0, 0], [0, 100], [100, 0]], dtype="float32")
    ordered = order_points(pts)
    assert np.allclose(ordered[0], [0, 0])      # top-left
    assert np.allclose(ordered[1], [100, 0])    # top-right
    assert np.allclose(ordered[2], [100, 100])  # bottom-right
    assert np.allclose(ordered[3], [0, 100])    # bottom-left


def test_four_point_transform_axis_aligned_rect():
    img = np.zeros((200, 200, 3), np.uint8)
    pts = np.array([[10, 20], [110, 20], [110, 220 - 20], [10, 220 - 20]], dtype="float32")
    # Above height (220-20=200) exceeds image; clamp for the test.
    pts = np.array([[10, 20], [110, 20], [110, 180], [10, 180]], dtype="float32")
    warped = four_point_transform(img, pts)
    # width ~100, height ~160.
    assert abs(warped.shape[1] - 100) <= 1
    assert abs(warped.shape[0] - 160) <= 1


def test_detect_card_on_synthetic_scene():
    scene = make_scene()
    det = detect_card(scene)
    # Rectified size should be close to the original card dimensions.
    assert abs(det.rectified.shape[1] - CARD_W) <= 6
    assert abs(det.rectified.shape[0] - CARD_H) <= 6
    assert det.corners.shape == (4, 2)
    # Corners should lie within the (downscaled) source image bounds.
    assert det.corners[:, 0].max() <= det.source.shape[1]
    assert det.corners[:, 1].max() <= det.source.shape[0]


def test_detect_card_rejects_pure_noise():
    rng = np.random.default_rng(0)
    noise = rng.integers(0, 255, (600, 600, 3), dtype=np.uint8)
    with pytest.raises(CardDetectionError):
        detect_card(noise)


def test_detect_card_rejects_empty_image():
    with pytest.raises(CardDetectionError):
        detect_card(np.empty((0, 0, 3), dtype=np.uint8))


def test_detect_card_handles_no_rotation():
    scene = make_scene(rotate_deg=0.0)
    det = detect_card(scene)
    assert abs(det.rectified.shape[1] - CARD_W) <= 6
    assert abs(det.rectified.shape[0] - CARD_H) <= 6
