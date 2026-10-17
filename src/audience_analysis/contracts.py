"""Contractele taskului 04. NumPy este singura dependență externă."""
from dataclasses import dataclass, field
from enum import StrEnum
import math
import re
from typing import Protocol

import numpy as np
from numpy.typing import NDArray


def identifier(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
        raise ValueError("Identificator invalid: folosește litere, cifre, _ sau -")


def nonnegative(value: float) -> None:
    if not math.isfinite(value) or value < 0:
        raise ValueError("Timpul trebuie să fie finit și pozitiv sau zero")


def counter(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("Contorul trebuie să fie un întreg pozitiv sau zero")


def validate_levels(levels: dict[str, int]) -> None:
    if not isinstance(levels, dict) or not levels:
        raise ValueError("Lipsesc dimensiunile modelului")
    for name, level in levels.items():
        identifier(name)
        if type(level) is not int or level not in range(4):
            raise ValueError("Nivelurile trebuie să fie întregi 0–3")


class Status(StrEnum):
    STARTED = "STARTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    OK = "OK"
    NO_FACE = "NO_FACE"
    ERROR = "ERROR"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    END_OF_SOURCE = "END_OF_SOURCE"
    STOPPED = "STOPPED"
    REMOVED = "REMOVED"


@dataclass(frozen=True)
class SourceConfig:
    source_id: str
    display_name: str
    kind: str
    location: str = ""

    def __post_init__(self) -> None:
        identifier(self.source_id)
        if not self.display_name.strip() or self.kind not in {"demo", "file", "camera", "network"}:
            raise ValueError("Numele sau tipul sursei este invalid")
        if self.kind != "demo" and not self.location:
            raise ValueError("Sursa reală necesită o locație")


@dataclass(frozen=True)
class FramePacket:
    source_id: str
    run_id: str
    frame_id: int
    media_time_s: float
    image: NDArray[np.uint8] = field(repr=False)
    face_boxes: tuple[tuple[int, int, int, int], ...] = ()

    def __post_init__(self) -> None:
        identifier(self.source_id)
        identifier(self.run_id)
        counter(self.frame_id)
        nonnegative(self.media_time_s)
        if self.image.dtype != np.uint8 or self.image.ndim != 3 or self.image.shape[2] != 3 or min(self.image.shape[:2]) < 1:
            raise ValueError("Imaginea trebuie să fie BGR uint8 [H,W,3]")
        for x, y, width, height in self.face_boxes:
            if any(type(v) is not int for v in (x, y, width, height)) or min(x, y) < 0 or min(width, height) < 1:
                raise ValueError("Casetă facială invalidă")
            if x+width > self.image.shape[1] or y+height > self.image.shape[0]:
                raise ValueError("Casetă în afara cadrului")
        image = np.array(self.image, copy=True, order="C")
        image.setflags(write=False)
        object.__setattr__(self, "image", image)
        object.__setattr__(self, "face_boxes", tuple(tuple(box) for box in self.face_boxes))


@dataclass(frozen=True)
class PreparedSequence:
    frames: NDArray[np.float32] = field(repr=False)
    sample_times_s: tuple[float, ...]
    preprocessing_id: str

    def __post_init__(self) -> None:
        if (self.frames.dtype != np.float32 or self.frames.ndim != 4
                or self.frames.shape[1] != 3 or min(self.frames.shape) < 1):
            raise ValueError("Secvența trebuie să fie float32 [T,3,H,W]")
        if not np.isfinite(self.frames).all() or len(self.sample_times_s) != len(self.frames):
            raise ValueError("Cadre sau marcaje temporale invalide")
        for value in self.sample_times_s:
            nonnegative(value)
        if any(a >= b for a, b in zip(self.sample_times_s, self.sample_times_s[1:])):
            raise ValueError("Marcajele temporale trebuie să fie strict crescătoare")
        identifier(self.preprocessing_id)
        frames = np.array(self.frames, copy=True, order="C")
        frames.setflags(write=False)
        object.__setattr__(self, "frames", frames)
        object.__setattr__(self, "sample_times_s", tuple(self.sample_times_s))


@dataclass(frozen=True)
class InferenceRequest:
    source_id: str
    run_id: str
    request_id: int
    window_start_s: float
    window_end_s: float
    queued_monotonic_s: float
    sequence: PreparedSequence

    def __post_init__(self) -> None:
        identifier(self.source_id)
        identifier(self.run_id)
        counter(self.request_id)
        for value in (self.window_start_s, self.window_end_s, self.queued_monotonic_s):
            nonnegative(value)
        if self.window_start_s > self.window_end_s:
            raise ValueError("Interval inversat")
        if (self.sequence.sample_times_s[0] < self.window_start_s - 1e-8
                or self.sequence.sample_times_s[-1] > self.window_end_s + 1e-8):
            raise ValueError("Secvența depășește intervalul cererii")


@dataclass(frozen=True)
class ModelOutput:
    levels: dict[str, int]
    model_version: str
    is_demo: bool

    def __post_init__(self) -> None:
        validate_levels(self.levels)
        if not self.model_version or type(self.is_demo) is not bool:
            raise ValueError("Versiune sau marcaj demo invalid")
        object.__setattr__(self, "levels", dict(self.levels))


@dataclass(frozen=True)
class PredictionResult:
    source_id: str
    run_id: str
    request_id: int
    window_start_s: float
    window_end_s: float
    status: Status
    levels: dict[str, int] | None
    model_version: str | None
    is_demo: bool
    queue_wait_ms: float
    inference_ms: float
    error_message: str | None = None

    def __post_init__(self) -> None:
        identifier(self.source_id)
        identifier(self.run_id)
        counter(self.request_id)
        for value in (self.window_start_s, self.window_end_s, self.queue_wait_ms, self.inference_ms):
            nonnegative(value)
        if self.window_end_s < self.window_start_s or type(self.is_demo) is not bool:
            raise ValueError("Interval sau marcaj demo invalid")
        if self.status not in {Status.OK, Status.ERROR, Status.MODEL_UNAVAILABLE}:
            raise ValueError("Stare de predicție invalidă")
        if self.status == Status.OK:
            validate_levels(self.levels)
            if not self.model_version:
                raise ValueError("Lipsește versiunea modelului")
            object.__setattr__(self, "levels", dict(self.levels))
        elif self.levels is not None:
            raise ValueError("La eroare, levels trebuie să fie None")


@dataclass(frozen=True)
class SourceStatusEvent:
    event_id: str
    source_id: str
    run_id: str
    status: Status
    message: str

    def __post_init__(self) -> None:
        for value in (self.event_id, self.source_id, self.run_id):
            identifier(value)
        if not isinstance(self.status, Status):
            raise ValueError("Stare necunoscută")


class Predictor(Protocol):
    def predict(self, sequence: PreparedSequence) -> ModelOutput: ...


class EngineCommands(Protocol):
    def add_source(self, config: SourceConfig) -> None: ...
    def start_source(self, source_id: str) -> str: ...
    def stop_source(self, source_id: str) -> None: ...
    def remove_source(self, source_id: str) -> None: ...
    def shutdown(self) -> None: ...
    def take_latest_preview(self, source_id: str) -> FramePacket | None: ...
