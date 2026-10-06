from __future__ import annotations

import pytest

from spectra.gestures.features import FingerStates, extended_count, finger_states, pointer_position
from tests.conftest import make_hand

PATTERNS = [
    (False, False, False, False, False),
    (False, True, False, False, False),
    (False, True, True, False, False),
    (False, False, False, True, True),
    (True, False, False, False, False),
    (True, True, True, True, True),
]


@pytest.mark.parametrize("pattern", PATTERNS)
@pytest.mark.parametrize("label", ["Right", "Left"])
def test_finger_states_recover_the_synthetic_pattern(pattern, label):
    landmarks = make_hand(*pattern, label=label)
    assert tuple(finger_states(landmarks, label)) == pattern


def test_extended_count_matches_the_pattern():
    states = finger_states(make_hand(index=True, middle=True, ring=True))
    assert extended_count(states) == 3
    assert states.extended_count == 3


def test_pointer_is_none_when_the_index_is_curled():
    assert pointer_position(make_hand(middle=True), (720, 1280)) is None


def test_pointer_is_scaled_to_pixels():
    landmarks = make_hand(index=True)
    point = pointer_position(landmarks, (720, 1280))
    assert point == (int(landmarks[8].x * 1280), int(landmarks[8].y * 720))


def test_finger_states_is_a_named_tuple():
    states = FingerStates(True, False, False, False, True)
    assert states.thumb is True
    assert states.pinky is True
    assert tuple(states) == (True, False, False, False, True)
