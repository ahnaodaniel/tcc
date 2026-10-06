"""Patient application shell: camera loop, mode routing and rendering."""

from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np

from spectra.config import AppConfig, load_config
from spectra.core.fps import FpsCounter
from spectra.detection.camera import Camera
from spectra.detection.hand_detector import DetectionResult, HandDetector
from spectra.i18n import set_locale, t
from spectra.modes.base import ACTION_MENU, ACTION_QUIT, AppMode, BaseMode, ModeContext
from spectra.modes.edu_colors import EduColorsMode
from spectra.modes.edu_count import EduCountMode
from spectra.modes.free_draw import FreeDrawMode
from spectra.modes.menu import MenuMode
from spectra.modes.physio import PhysioMode
from spectra.ui.sound import SoundPlayer
from spectra.ui.text import draw_text
from spectra.ui.widgets import draw_hand_landmarks, draw_status_bar

logger = logging.getLogger(__name__)

WINDOW_NAME = "SPECTRA"

MODE_FACTORIES: dict[AppMode, type[BaseMode]] = {
    AppMode.MENU: MenuMode,
    AppMode.FREE_DRAW: FreeDrawMode,
    AppMode.EDU_COLORS: EduColorsMode,
    AppMode.EDU_COUNT: EduCountMode,
    AppMode.PHYSIO: PhysioMode,
}


class SpectraApp:
    """Owns the capture loop and dispatches frames to the active mode."""

    def __init__(self, config: AppConfig | None = None, hand_label: str | None = None) -> None:
        self.config = config or load_config()
        self.config.ensure_directories()
        set_locale(self.config.locale)
        self.hand_label = hand_label
        self.mode = AppMode.MENU
        self.modes: dict[AppMode, BaseMode] = {}
        self.fps = FpsCounter()
        self.sound = SoundPlayer(self.config.sound_enabled)

    # ----------------------------------------------------------------- setup
    def build_modes(self, width: int, height: int) -> None:
        context = ModeContext(
            config=self.config,
            width=width,
            height=height,
            sound=self.sound,
            hand_label=self.hand_label,
        )
        self.modes = {mode: factory(context) for mode, factory in MODE_FACTORIES.items()}
        self._context = context

    def switch_to(self, mode: AppMode) -> None:
        self.mode = mode
        self.modes[mode].on_enter()

    def reset_mode(self, mode: AppMode) -> None:
        """Rebuild a mode from scratch, discarding its session state."""
        self.modes[mode] = MODE_FACTORIES[mode](self._context)

    # ------------------------------------------------------------- per frame
    def render_frame(self, frame: np.ndarray, detection: DetectionResult) -> tuple[np.ndarray, Any]:
        handler = self.modes[self.mode]
        output, action = handler.process(frame, detection)
        for hand in detection.hands:
            draw_hand_landmarks(output, hand.landmarks)
        draw_status_bar(output, self.mode.title, t("app.interact_hint"))
        draw_text(
            output,
            t("common.fps", fps=f"{self.fps.tick():.0f}"),
            (output.shape[1] - 78, 18),
            0.46,
            (110, 110, 110),
        )
        return output, action

    def handle_action(self, action: Any) -> bool:
        """Apply a mode action; returns ``False`` when the app should stop."""
        if action == ACTION_QUIT:
            return False
        if action == ACTION_MENU:
            self.reset_mode(AppMode.MENU)
            self.switch_to(AppMode.MENU)
        elif isinstance(action, AppMode):
            self.switch_to(action)
        return True

    # ----------------------------------------------------------------- loop
    def run(self) -> None:
        try:
            camera = Camera(
                self.config.camera_index,
                self.config.capture_width,
                self.config.capture_height,
                self.config.capture_fps,
            )
        except RuntimeError as exc:
            raise RuntimeError(t("app.camera_error")) from exc

        with camera:
            first = camera.read()
            if first is None:
                raise RuntimeError(t("app.frame_error"))
            height, width = first.shape[:2]
            self.build_modes(width, height)

            detector = HandDetector(
                self.config.model_path(),
                detection_size=(self.config.detection_width, self.config.detection_height),
            )
            logger.info("%s", t("app.started"))
            logger.info("%s", t("app.hint"))
            cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(WINDOW_NAME, width, height)
            try:
                while True:
                    frame = camera.read()
                    if frame is None:
                        break
                    output, action = self.render_frame(frame, detector.detect(frame))
                    cv2.imshow(WINDOW_NAME, output)
                    if cv2.waitKey(1) & 0xFF == 27:  # ESC is an emergency exit
                        break
                    if not self.handle_action(action):
                        break
            except KeyboardInterrupt:
                pass
            finally:
                detector.close()
                cv2.destroyAllWindows()
                logger.info("%s", t("app.stopped"))
