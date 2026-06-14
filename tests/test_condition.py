"""Tests for the condition assessors: corners.py, edges.py, surface.py.

Strategy: a clean synthetic card (uniform white border, solid inner) should read
as near-pristine (wear ~ 0). Introducing a localised defect should raise the
wear for that region/factor. We assert the *direction* of the response (damage
increases wear) rather than exact magnitudes, since these are heuristics.
"""

import cv2
import numpy as np

from corners import assess_corners
from edges import assess_edges
from surface import assess_surface
from centering import measure_centering
from conftest import make_card


def _inner(card):
    return measure_centering(card).inner_rect


def test_clean_card_corners_are_pristine():
    card = make_card()
    res = assess_corners(card, inner_rect=_inner(card))
    assert res.wear < 0.05
    assert set(res.per_corner) == {"top_left", "top_right", "bottom_right", "bottom_left"}


def test_corner_damage_increases_wear():
    card = make_card()
    inner = _inner(card)
    clean = assess_corners(card, inner_rect=inner)
    damaged_card = make_card()
    # Dark chip at the top-left corner (darkening branch vs a white border).
    cv2.rectangle(damaged_card, (0, 0), (30, 30), (10, 10, 10), thickness=-1)
    damaged = assess_corners(damaged_card, inner_rect=inner)
    assert damaged.per_corner["top_left"] > clean.per_corner["top_left"]
    assert damaged.wear > clean.wear


def test_clean_card_edges_are_pristine():
    card = make_card()
    res = assess_edges(card, inner_rect=_inner(card))
    assert res.wear < 0.05
    assert set(res.per_edge) == {"top", "right", "bottom", "left"}


def test_edge_damage_increases_wear():
    card = make_card()
    inner = _inner(card)
    clean = assess_edges(card, inner_rect=inner)
    damaged_card = make_card()
    # Dark chip along the top edge, away from the corners.
    cv2.rectangle(damaged_card, (150, 0), (250, 12), (10, 10, 10), thickness=-1)
    damaged = assess_edges(damaged_card, inner_rect=inner)
    assert damaged.per_edge["top"] > clean.per_edge["top"]
    assert damaged.wear > clean.wear


def test_clean_surface_has_no_defects():
    card = make_card()
    inner = measure_centering(card).inner_rect
    res = assess_surface(card, inner_rect=inner)
    assert res.defect_fraction < 0.01
    assert res.wear < 0.05
    assert res.defect_mask.shape == card.shape[:2]


def test_surface_scratch_increases_wear():
    card = make_card()
    inner = measure_centering(card).inner_rect
    clean = assess_surface(card, inner_rect=inner)
    # Draw a thin bright scratch across the artwork interior.
    cv2.line(card, (120, 280), (300, 300), (240, 240, 240), thickness=1)
    scratched = assess_surface(card, inner_rect=inner)
    assert scratched.defect_fraction > clean.defect_fraction
    assert scratched.wear >= clean.wear


def test_assessors_reject_empty_image():
    import pytest
    empty = np.empty((0, 0, 3), dtype=np.uint8)
    for fn in (assess_corners, assess_edges, assess_surface):
        with pytest.raises(ValueError):
            fn(empty)
