"""Derived-feature recorder.

**No video or image of the patient is ever stored.** Each frame is reduced to a handful
of numbers (joint angles, opposition distances, fingertip position) and those are kept at
a reduced rate, 10 Hz by default, which is well above the bandwidth of a voluntary hand
movement but roughly a third of the data a 30 fps stream would produce.

Tracking quality is counted over *every* frame, not only stored ones, so the report can
tell a therapist that a session was too poorly tracked to be trusted.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from spectra.detection.landmarks import INDEX_TIP, HandLandmarks
from spectra.gestures.features import (
    finger_flexion_angles,
    opposition_ratios,
    palm_size,
    thumb_abduction_ratio,
)

DEFAULT_RATE_HZ = 10.0

#: Below this, the report labels the whole session unreliable.
MIN_RELIABLE_PRESENCE = 0.60
MIN_RELIABLE_CONFIDENCE = 0.50


@dataclass(frozen=True)
class FrameSample:
    """One stored frame, already reduced to derived features."""

    at: float
    flexion: tuple[float, float, float, float, float]
    opposition: tuple[float, float, float, float]
    thumb_abduction: float
    index_tip: tuple[float, float]
    palm_size: float
    confidence: float

    def to_dict(self) -> dict:
        return {
            "at": self.at,
            "flexion": list(self.flexion),
            "opposition": list(self.opposition),
            "thumb_abduction": self.thumb_abduction,
            "index_tip": list(self.index_tip),
            "palm_size": self.palm_size,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class TrackingQuality:
    """How well the camera saw the hand; gates the credibility of every other metric."""

    frames_total: int
    frames_with_hand: int
    mean_confidence: float

    @property
    def presence_ratio(self) -> float:
        return self.frames_with_hand / self.frames_total if self.frames_total else 0.0

    @property
    def reliable(self) -> bool:
        return (
            self.frames_total > 0
            and self.presence_ratio >= MIN_RELIABLE_PRESENCE
            and self.mean_confidence >= MIN_RELIABLE_CONFIDENCE
        )

    def to_dict(self) -> dict:
        return {
            "frames_total": self.frames_total,
            "frames_with_hand": self.frames_with_hand,
            "mean_confidence": self.mean_confidence,
            "presence_ratio": self.presence_ratio,
            "reliable": self.reliable,
        }


@dataclass
class SessionRecorder:
    """Collects :class:`FrameSample` at a fixed rate plus tracking statistics."""

    rate_hz: float = DEFAULT_RATE_HZ
    samples: list[FrameSample] = field(default_factory=list)
    frames_total: int = 0
    frames_with_hand: int = 0
    _confidence_sum: float = 0.0
    _last_stored_at: float | None = None

    @property
    def interval(self) -> float:
        return 1.0 / self.rate_hz if self.rate_hz > 0 else 0.0

    def observe(
        self,
        landmarks: HandLandmarks | None,
        confidence: float = 0.0,
        now: float | None = None,
    ) -> FrameSample | None:
        """Account for one frame; returns the stored sample, if this frame was kept."""
        current = time.time() if now is None else now
        self.frames_total += 1
        if landmarks is None:
            return None
        self.frames_with_hand += 1
        self._confidence_sum += confidence
        if self._last_stored_at is not None and current - self._last_stored_at < self.interval:
            return None
        self._last_stored_at = current
        tip = landmarks[INDEX_TIP]
        sample = FrameSample(
            at=current,
            flexion=finger_flexion_angles(landmarks),  # type: ignore[arg-type]
            opposition=opposition_ratios(landmarks),  # type: ignore[arg-type]
            thumb_abduction=thumb_abduction_ratio(landmarks),
            index_tip=(tip.x, tip.y),
            palm_size=palm_size(landmarks),
            confidence=confidence,
        )
        self.samples.append(sample)
        return sample

    def quality(self) -> TrackingQuality:
        mean_confidence = (
            self._confidence_sum / self.frames_with_hand if self.frames_with_hand else 0.0
        )
        return TrackingQuality(
            frames_total=self.frames_total,
            frames_with_hand=self.frames_with_hand,
            mean_confidence=mean_confidence,
        )

    def reset(self) -> None:
        self.samples.clear()
        self.frames_total = 0
        self.frames_with_hand = 0
        self._confidence_sum = 0.0
        self._last_stored_at = None

    def window(self, start: float, end: float) -> list[FrameSample]:
        """Samples recorded within ``[start, end]``, for per-exercise summaries."""
        return [sample for sample in self.samples if start <= sample.at <= end]
