"""Shared fixtures: synthetic hands so tests never need a camera or MediaPipe."""

from __future__ import annotations

import pytest

from spectra.config import AppConfig
from spectra.detection.hand_detector import DetectedHand, DetectionResult
from spectra.detection.landmarks import LANDMARK_COUNT, Landmark
from spectra.i18n import set_locale

# Horizontal position of each finger's MCP joint, thumb excluded.
_FINGER_X = {"index": 0.44, "middle": 0.50, "ring": 0.56, "pinky": 0.62}

_EXTENDED_Y = (0.65, 0.55, 0.48, 0.42)
_CURLED_Y = (0.65, 0.57, 0.62, 0.66)

_THUMB_EXTENDED = ((0.42, 0.82), (0.36, 0.76), (0.30, 0.72), (0.26, 0.70))
_THUMB_CURLED = ((0.42, 0.82), (0.40, 0.76), (0.44, 0.72), (0.47, 0.70))


def make_hand(
    thumb: bool = False,
    index: bool = False,
    middle: bool = False,
    ring: bool = False,
    pinky: bool = False,
    label: str = "Right",
) -> list[Landmark]:
    """Build 21 anatomically plausible landmarks for the requested finger pattern."""
    points: list[tuple[float, float]] = [(0.50, 0.90)]  # wrist
    points.extend(_THUMB_EXTENDED if thumb else _THUMB_CURLED)
    for name, extended in (("index", index), ("middle", middle), ("ring", ring), ("pinky", pinky)):
        x = _FINGER_X[name]
        ys = _EXTENDED_Y if extended else _CURLED_Y
        points.extend((x, y) for y in ys)

    if label == "Left":
        points = [(1.0 - x, y) for x, y in points]

    landmarks = [Landmark(x, y, 0.0) for x, y in points]
    assert len(landmarks) == LANDMARK_COUNT
    return landmarks


def make_detection(
    *patterns: tuple[bool, bool, bool, bool, bool], label: str = "Right"
) -> DetectionResult:
    """Wrap one or more finger patterns into a :class:`DetectionResult`."""
    hands = tuple(
        DetectedHand(landmarks=make_hand(*pattern, label=label), label=label, score=0.9)
        for pattern in patterns
    )
    return DetectionResult(hands)


def pinching_hand(distance: float = 0.01, label: str = "Right") -> list[Landmark]:
    """A hand whose thumb tip sits ``distance`` (normalised) from the index tip."""
    landmarks = make_hand(thumb=True, index=True, label=label)
    index_tip = landmarks[8]
    landmarks[4] = Landmark(index_tip.x + distance, index_tip.y, 0.0)
    return landmarks


@pytest.fixture(autouse=True)
def _default_locale():
    set_locale("pt_BR")


@pytest.fixture
def config(tmp_path) -> AppConfig:
    cfg = AppConfig(data_dir=tmp_path / "Spectra")
    cfg.ensure_directories()
    return cfg


@pytest.fixture
def empty_detection() -> DetectionResult:
    return DetectionResult()
