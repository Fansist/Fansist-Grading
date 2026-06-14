"""Shared pytest fixtures/helpers: synthetic trading-card images.

We generate cards with KNOWN margins so tests can assert measured values against
ground truth, without needing real photos. Two builders:

  * make_card(...)   -> just the rectified card (white border + coloured inner).
  * make_scene(...)  -> that card placed on a contrasting background and rotated,
                        i.e. what the *detector* must find and deskew.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

# Default known margins (pixels) for the synthetic card.
CARD_W, CARD_H = 400, 560
MARGIN_L, MARGIN_R, MARGIN_T, MARGIN_B = 40, 60, 50, 50

BORDER_BGR = (255, 255, 255)   # white frame
ARTWORK_BGR = (140, 60, 20)    # dark blue artwork
BACKGROUND_BGR = (35, 35, 35)  # dark, contrasting backdrop


def make_card(
    left: int = MARGIN_L,
    right: int = MARGIN_R,
    top: int = MARGIN_T,
    bottom: int = MARGIN_B,
    width: int = CARD_W,
    height: int = CARD_H,
) -> np.ndarray:
    """Return a rectified card BGR image with the given margins."""
    card = np.full((height, width, 3), BORDER_BGR, np.uint8)
    cv2.rectangle(
        card,
        (left, top),
        (width - 1 - right, height - 1 - bottom),
        ARTWORK_BGR,
        thickness=-1,
    )
    return card


def make_scene(
    left: int = MARGIN_L,
    right: int = MARGIN_R,
    top: int = MARGIN_T,
    bottom: int = MARGIN_B,
    rotate_deg: float = 7.0,
) -> np.ndarray:
    """Return a card placed on a contrasting background and rotated."""
    card = make_card(left, right, top, bottom)
    ch, cw = card.shape[:2]
    scene_h, scene_w = 900, 800
    bg = np.full((scene_h, scene_w, 3), BACKGROUND_BGR, np.uint8)
    oy, ox = (scene_h - ch) // 2, (scene_w - cw) // 2
    bg[oy:oy + ch, ox:ox + cw] = card
    if rotate_deg:
        matrix = cv2.getRotationMatrix2D((scene_w / 2, scene_h / 2), rotate_deg, 1.0)
        bg = cv2.warpAffine(bg, matrix, (scene_w, scene_h), borderValue=BACKGROUND_BGR)
    return bg


@pytest.fixture
def card_scene() -> np.ndarray:
    """A default synthetic scene (card on background, rotated)."""
    return make_scene()


@pytest.fixture
def rectified_card() -> np.ndarray:
    """A default rectified synthetic card (no background, axis-aligned)."""
    return make_card()
