"""Free drawing: finger combinations pick colours, hold a gesture to clear or undo."""

from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np

from spectra.core.canvas import DEFAULT_BRUSH_SIZE, ERASER_SIZE, DrawingCanvas
from spectra.core.trail import Trail
from spectra.detection.hand_detector import DetectionResult
from spectra.i18n import t
from spectra.modes.base import BaseMode, ModeContext
from spectra.modes.palette import COMMAND_CLEAR, COMMAND_ERASER, COMMAND_UNDO, resolve
from spectra.ui.text import draw_text, draw_text_centered
from spectra.ui.widgets import draw_finger_hud, draw_progress_bar

ACTION_CLEAR = "clear"
ACTION_SAVE = "save"
ACTION_UNDO = "undo"

FEEDBACK_SECONDS = 2.5


class FreeDrawMode(BaseMode):
    def __init__(self, context: ModeContext) -> None:
        super().__init__(context)
        config = context.config
        self.canvas = DrawingCanvas(self.width, self.height, config.undo_history)
        self.trail = Trail(config.trail_length)
        self.brush_size = DEFAULT_BRUSH_SIZE
        self.color_label = t("common.none")
        self.color_bgr: tuple[int, int, int] | None = None
        self.previous_point: tuple[int, int] | None = None
        self.drawing = False
        self._feedback_text = ""
        self._feedback_at = 0.0
        self._command: str | None = None
        self._command_start: float | None = None
        self._command_progress = 0.0

        button_width, button_height = 112, 42
        y = self.height - button_height - 10
        self.buttons = [
            self.make_button(
                10,
                y,
                button_width,
                button_height,
                t("paint.clear"),
                (80, 20, 20),
                value=ACTION_CLEAR,
            ),
            self.make_button(
                130,
                y,
                button_width,
                button_height,
                t("paint.save"),
                (20, 70, 20),
                value=ACTION_SAVE,
            ),
            self.make_button(
                250,
                y,
                button_width,
                button_height,
                t("paint.undo"),
                (80, 60, 10),
                value=ACTION_UNDO,
            ),
        ]
        self.buttons += self.navigation_buttons()

    # ------------------------------------------------------------- feedback
    def _feedback(self, message: str) -> None:
        self._feedback_text = message
        self._feedback_at = time.time()

    def _reset_command(self) -> None:
        self._command = None
        self._command_start = None
        self._command_progress = 0.0

    def _advance_command(self, command: str) -> None:
        """Hold-to-confirm for destructive gestures (clear, undo)."""
        now = time.time()
        if self._command != command or self._command_start is None:
            self._command = command
            self._command_start = now
            self._command_progress = 0.0
            return
        elapsed = now - self._command_start
        hold = self.context.config.gesture_hold_secs
        self._command_progress = min(1.0, elapsed / hold)
        if elapsed >= hold:
            self._reset_command()
            self._run_command(command)

    def _run_command(self, command: str) -> None:
        if command == COMMAND_CLEAR:
            self.canvas.clear()
            self.trail.clear()
            self._feedback(t("paint.canvas_cleared"))
        elif command == COMMAND_UNDO:
            undone = self.canvas.undo()
            self._feedback(t("paint.undone") if undone else t("paint.nothing_to_undo"))

    # ------------------------------------------------------------- painting
    def _paint(self, point: tuple[int, int] | None, color: tuple[int, int, int] | None) -> None:
        if point is None:
            self.previous_point = None
            self.drawing = False
            return
        if not self.drawing:
            self.canvas.begin_stroke()
            self.drawing = True
        if self.previous_point is not None:
            size = ERASER_SIZE if color is None else self.brush_size
            self.canvas.draw(self.previous_point, point, color, size)
        self.trail.add(point, color)
        self.previous_point = point

    def _stop_painting(self) -> None:
        self.previous_point = None
        self.drawing = False

    def _save(self) -> None:
        directory = self.context.config.drawings_dir
        path = directory / f"pintura_{int(time.time())}.png"
        try:
            self.canvas.save(path)
        except OSError:
            self._feedback(t("paint.save_failed"))
            self.context.sound.error()
            return
        self._feedback(t("paint.saved", filename=path.name))
        self.context.sound.success()

    # -------------------------------------------------------------- process
    def process(self, frame: np.ndarray, detection: DetectionResult) -> tuple[np.ndarray, Any]:
        height, width = frame.shape[:2]
        composite = cv2.addWeighted(self.canvas.image, 0.65, frame, 0.35, 0)

        pointer = self.pointer(detection, frame.shape)
        states = self.read_states(detection)
        gesture_label = t("common.none")

        entry = resolve(states)
        if states is None or entry is None:
            self._stop_painting()
            self._reset_command()
        elif entry.command in (COMMAND_CLEAR, COMMAND_UNDO):
            gesture_label = entry.label
            self._stop_painting()
            self._advance_command(entry.command)
        elif entry.command == COMMAND_ERASER:
            gesture_label = entry.label
            self._reset_command()
            self.color_label, self.color_bgr = entry.label, None
            self._paint(pointer, None)
        else:
            gesture_label = entry.label
            self._reset_command()
            self.color_label, self.color_bgr = entry.label, entry.color
            if states.index:
                self._paint(pointer, entry.color)
            else:
                self._stop_painting()

        self.trail.draw(composite)
        action = self.draw_buttons(composite, pointer)

        self._draw_hud(composite)
        draw_text(
            composite,
            t("paint.gesture", gesture=gesture_label),
            (14, height - 84),
            0.62,
            (220, 220, 220),
        )

        if pointer is not None:
            cursor = self.color_bgr or (200, 200, 200)
            cv2.circle(composite, pointer, self.brush_size, cursor, -1)
            cv2.circle(composite, pointer, self.brush_size + 2, (20, 20, 20), 2)

        if self._feedback_text and (time.time() - self._feedback_at) < FEEDBACK_SECONDS:
            draw_text_centered(
                composite, self._feedback_text, width // 2, height // 2, 1.0, (0, 220, 255), 3
            )

        if self._command is not None and self._command_progress > 0:
            label = t("paint.clearing") if self._command == COMMAND_CLEAR else t("paint.undoing")
            draw_text(
                composite,
                f"{label} {self._command_progress * 100:.0f}%",
                (10, height - 60),
                0.7,
                (0, 220, 255),
                2,
            )
            draw_progress_bar(composite, (10, height - 52), (300, 12), self._command_progress)

        if states is not None:
            draw_finger_hud(composite, states, width - 155, height - 68)

        if action == ACTION_CLEAR:
            self.canvas.clear()
            self.trail.clear()
            self._feedback(t("paint.canvas_cleared"))
            action = None
        elif action == ACTION_SAVE:
            self._save()
            action = None
        elif action == ACTION_UNDO:
            undone = self.canvas.undo()
            self._feedback(t("paint.undone") if undone else t("paint.nothing_to_undo"))
            action = None

        return composite, action

    def _draw_hud(self, frame: np.ndarray) -> None:
        width = frame.shape[1]
        cv2.rectangle(frame, (0, 0), (width, 50), (15, 15, 15), -1)
        draw_text(frame, t("paint.title"), (10, 22), 0.62)
        swatch = self.color_bgr or (200, 200, 200)
        cv2.circle(frame, (230, 14), 11, swatch, -1)
        cv2.circle(frame, (230, 14), 12, (255, 255, 255), 1)
        draw_text(frame, self.color_label, (248, 20), 0.58)
        draw_text(frame, t("paint.brush", size=self.brush_size), (420, 20), 0.48, (180, 180, 180))
        for i, key in enumerate(("paint.legend_1", "paint.legend_2")):
            draw_text(frame, t(key), (width - 490, 18 + i * 16), 0.35, (170, 170, 170))
