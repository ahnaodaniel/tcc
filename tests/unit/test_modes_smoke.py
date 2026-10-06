from __future__ import annotations

import numpy as np
import pytest

from spectra.modes.base import ACTION_QUIT, AppMode, ModeContext
from spectra.modes.edu_colors import EduColorsMode
from spectra.modes.edu_count import EduCountMode
from spectra.modes.free_draw import FreeDrawMode
from spectra.modes.menu import MenuMode
from spectra.modes.physio import PhysioMode
from spectra.ui.sound import SoundPlayer
from tests.conftest import make_detection

WIDTH, HEIGHT = 640, 480
MODES = [MenuMode, FreeDrawMode, EduColorsMode, EduCountMode, PhysioMode]


@pytest.fixture
def context(config) -> ModeContext:
    return ModeContext(config=config, width=WIDTH, height=HEIGHT, sound=SoundPlayer(enabled=False))


def blank_frame() -> np.ndarray:
    return np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)


@pytest.mark.parametrize("mode_class", MODES)
def test_process_runs_headless_without_a_hand(mode_class, context, empty_detection):
    mode = mode_class(context)
    output, action = mode.process(blank_frame(), empty_detection)
    assert output.shape == (HEIGHT, WIDTH, 3)
    assert action is None


@pytest.mark.parametrize("mode_class", MODES)
def test_process_runs_headless_with_a_hand(mode_class, context):
    mode = mode_class(context)
    detection = make_detection((False, True, False, False, False))
    output, _ = mode.process(blank_frame(), detection)
    assert output.shape == (HEIGHT, WIDTH, 3)


@pytest.mark.parametrize("mode_class", MODES)
def test_every_mode_offers_a_way_out(mode_class, context):
    values = {button.value for button in mode_class(context).buttons}
    assert ACTION_QUIT in values


def test_menu_exposes_every_implemented_mode(context):
    values = {b.value for b in MenuMode(context).buttons if isinstance(b.value, AppMode)}
    assert values == {AppMode.FREE_DRAW, AppMode.EDU_COLORS, AppMode.EDU_COUNT, AppMode.PHYSIO}


def test_free_draw_paints_when_a_colour_gesture_points(context):
    mode = FreeDrawMode(context)
    detection = make_detection((False, True, False, False, False))
    for _ in range(3):
        mode.process(blank_frame(), detection)
    assert (mode.canvas.image != 255).any()


def test_free_draw_save_writes_into_the_data_directory(context):
    mode = FreeDrawMode(context)
    mode._save()
    files = list(context.config.drawings_dir.glob("*.png"))
    assert len(files) == 1


def test_physio_export_writes_into_the_data_directory(context, tmp_path):
    mode = PhysioMode(context)
    mode.progress.add_rep()
    path = mode.export_csv(tmp_path / "exports")
    assert path.is_file()
    assert "reps" in path.read_text(encoding="utf-8")


def test_mode_titles_are_translated():
    assert AppMode.FREE_DRAW.title == "Pintura Livre"
    assert AppMode.PHYSIO.title == "Fisioterapia"
