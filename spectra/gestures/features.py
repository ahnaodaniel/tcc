"""Finger state and pointer features derived from hand landmarks.

Phase 1 keeps the original tip-versus-joint heuristic so behaviour is unchanged;
the angle-based estimator arrives with the gesture engine.
"""

from __future__ import annotations

from typing import NamedTuple

from spectra.detection.landmarks import (
    INDEX_PIP,
    INDEX_TIP,
    MIDDLE_PIP,
    MIDDLE_TIP,
    PINKY_PIP,
    PINKY_TIP,
    RING_PIP,
    RING_TIP,
    THUMB_IP,
    THUMB_TIP,
    HandLandmarks,
)

FINGER_NAMES: tuple[str, ...] = ("thumb", "index", "middle", "ring", "pinky")

#: Tolerance in normalised coordinates, absorbing detector jitter.
Y_TOLERANCE = 0.02
X_TOLERANCE = 0.02
POINTER_TOLERANCE = 0.02


class FingerStates(NamedTuple):
    """Per-finger extension flags, in thumb-to-pinky order."""

    thumb: bool
    index: bool
    middle: bool
    ring: bool
    pinky: bool

    @property
    def extended_count(self) -> int:
        return sum(self)


def finger_states(landmarks: HandLandmarks, hand_label: str = "Right") -> FingerStates:
    """Return which fingers are extended, using tip-versus-joint comparisons."""
    if hand_label == "Right":
        thumb = landmarks[THUMB_TIP].x < landmarks[THUMB_IP].x - X_TOLERANCE
    else:
        thumb = landmarks[THUMB_TIP].x > landmarks[THUMB_IP].x + X_TOLERANCE
    return FingerStates(
        thumb=bool(thumb),
        index=landmarks[INDEX_TIP].y < landmarks[INDEX_PIP].y - Y_TOLERANCE,
        middle=landmarks[MIDDLE_TIP].y < landmarks[MIDDLE_PIP].y - Y_TOLERANCE,
        ring=landmarks[RING_TIP].y < landmarks[RING_PIP].y - Y_TOLERANCE,
        pinky=landmarks[PINKY_TIP].y < landmarks[PINKY_PIP].y - Y_TOLERANCE,
    )


def pointer_position(
    landmarks: HandLandmarks, frame_shape: tuple[int, ...]
) -> tuple[int, int] | None:
    """Index fingertip position in pixels, or ``None`` when the finger is curled."""
    height, width = frame_shape[:2]
    tip = landmarks[INDEX_TIP]
    pip = landmarks[INDEX_PIP]
    extended = tip.y < pip.y - POINTER_TOLERANCE or tip.z < pip.z - POINTER_TOLERANCE
    if not extended:
        return None
    return (int(tip.x * width), int(tip.y * height))


def extended_count(states: FingerStates) -> int:
    return sum(states)
