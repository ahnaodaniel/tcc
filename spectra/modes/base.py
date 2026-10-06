"""Shared scaffolding for the interactive modes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

from spectra.config import AppConfig
from spectra.core.smoothing import ExponentialSmoother
from spectra.detection.hand_detector import DetectionResult
from spectra.gestures.features import FingerStates, finger_states, pointer_position
from spectra.i18n import t
from spectra.ui.button import Button
from spectra.ui.sound import SoundPlayer

ACTION_QUIT = "quit"
ACTION_MENU = "menu"
ACTION_NEXT = "next"

Point = tuple[int, int]


class AppMode(Enum):
    """Top-level screens; values double as i18n keys under ``mode.``."""

    MENU = "menu"
    FREE_DRAW = "free_draw"
    GUIDED_DRAW = "guided_draw"
    EDU_COLORS = "edu_colors"
    EDU_COUNT = "edu_count"
    PHYSIO = "physio"

    @property
    def title(self) -> str:
        return t(f"mode.{self.value}")


@dataclass
class ModeContext:
    """Everything a mode needs from the application shell."""

    config: AppConfig
    width: int
    height: int
    sound: SoundPlayer = field(default_factory=SoundPlayer)
    #: Handedness label of the hand being treated; ``None`` means "first hand seen".
    hand_label: str | None = None


class BaseMode:
    """Base class handling pointer smoothing and dwell-activated buttons."""

    def __init__(self, context: ModeContext) -> None:
        self.context = context
        self.width = context.width
        self.height = context.height
        self.buttons: list[Button] = []
        self._pointer = ExponentialSmoother(context.config.pointer_smooth_alpha)

    # ------------------------------------------------------------------ input
    def active_hand(self, detection: DetectionResult):
        return detection.for_label(self.context.hand_label)

    def pointer(self, detection: DetectionResult, frame_shape: tuple[int, ...]) -> Point | None:
        hand = self.active_hand(detection)
        if hand is None:
            self._pointer.reset()
            return None
        raw = pointer_position(hand.landmarks, frame_shape)
        return self._pointer.update(raw)

    def read_states(self, detection: DetectionResult) -> FingerStates | None:
        hand = self.active_hand(detection)
        if hand is None:
            return None
        return finger_states(hand.landmarks, hand.label)

    # ------------------------------------------------------------------- ui
    def make_button(self, *args: Any, **kwargs: Any) -> Button:
        kwargs.setdefault("hover_seconds", self.context.config.hover_select_secs)
        return Button(*args, **kwargs)

    def draw_buttons(self, frame: np.ndarray, pointer: Point | None) -> Any:
        action: Any = None
        for button in self.buttons:
            if button.update_hover(button.contains(pointer)):
                action = button.value
            button.draw(frame)
        return action

    def navigation_buttons(self, include_next: bool = False) -> list[Button]:
        """Bottom-right ``[Próximo] [Voltar] [Sair]`` cluster shared by every mode."""
        width, height = 138, 44
        y = self.height - height - 10
        buttons: list[Button] = []
        if include_next:
            buttons.append(
                self.make_button(
                    self.width - 3 * width - 30,
                    y,
                    width,
                    height,
                    t("common.next"),
                    (60, 60, 15),
                    value=ACTION_NEXT,
                )
            )
        buttons.append(
            self.make_button(
                self.width - 2 * width - 20,
                y,
                width,
                height,
                t("common.back"),
                (20, 20, 80),
                value=ACTION_MENU,
            )
        )
        buttons.append(
            self.make_button(
                self.width - width - 10,
                y,
                width,
                height,
                t("common.quit"),
                (120, 15, 15),
                value=ACTION_QUIT,
            )
        )
        return buttons

    # --------------------------------------------------------------- contract
    def process(
        self, frame: np.ndarray, detection: DetectionResult
    ) -> tuple[np.ndarray, Any]:  # pragma: no cover - abstract
        raise NotImplementedError

    def on_enter(self) -> None:
        """Called every time the mode becomes active."""
        self._pointer.reset()
        for button in self.buttons:
            button.reset()
