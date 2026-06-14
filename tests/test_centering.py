"""Tests for centering.py: margin measurement and ratio normalisation."""

import numpy as np
import pytest

from centering import _normalise_ratio, measure_centering
from conftest import make_card

# Margins are measured to within a few pixels of ground truth (edge ops + the
# Sobel/scan land within a small neighbourhood of the true border).
PIXEL_TOL = 3


def test_normalise_ratio_sums_to_100():
    assert _normalise_ratio(40, 60) == (40.0, 60.0)
    assert _normalise_ratio(55, 45) == (55.0, 45.0)


def test_normalise_ratio_zero_total_is_neutral():
    assert _normalise_ratio(0, 0) == (50.0, 50.0)


@pytest.mark.parametrize("method", ["gradient", "color"])
def test_measure_known_margins(method):
    card = make_card(left=40, right=60, top=50, bottom=50)
    res = measure_centering(card, method=method)

    assert abs(res.left - 40) <= PIXEL_TOL
    assert abs(res.right - 60) <= PIXEL_TOL
    assert abs(res.top - 50) <= PIXEL_TOL
    assert abs(res.bottom - 50) <= PIXEL_TOL

    # Horizontal 40:60 -> ~40/60; vertical 50:50 -> ~50/50.
    assert abs(res.horizontal_ratio[0] - 40.0) <= 2.0
    assert abs(res.horizontal_ratio[1] - 60.0) <= 2.0
    assert abs(res.vertical_ratio[0] - 50.0) <= 2.0
    assert res.method == method


@pytest.mark.parametrize("method", ["gradient", "color"])
def test_perfectly_centered_card(method):
    card = make_card(left=50, right=50, top=50, bottom=50)
    res = measure_centering(card, method=method)
    assert abs(res.horizontal_ratio[0] - 50.0) <= 2.0
    assert abs(res.vertical_ratio[0] - 50.0) <= 2.0


def test_inner_rect_is_consistent_with_margins():
    card = make_card(left=40, right=60, top=50, bottom=50)
    h, w = card.shape[:2]
    res = measure_centering(card, method="gradient")
    x_left, y_top, x_right, y_bottom = res.inner_rect
    assert x_left == res.left
    assert y_top == res.top
    assert x_right == (w - 1) - res.right
    assert y_bottom == (h - 1) - res.bottom


def test_empty_image_raises():
    with pytest.raises(ValueError):
        measure_centering(np.empty((0, 0, 3), dtype=np.uint8))


def test_unknown_method_raises():
    card = make_card()
    with pytest.raises(ValueError):
        measure_centering(card, method="nope")
