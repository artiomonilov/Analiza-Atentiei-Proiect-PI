from dataclasses import asdict, dataclass, field
from enum import StrEnum
import math
import re

import numpy as np


class Status(StrEnum):
    COLLECTING = "INSUFFICIENT_DATA"
    READY = "READY"
    NO_FACE = "NO_FACE"
    LOW_QUALITY = "LOW_QUALITY"
    AMBIGUOUS = "AMBIGUOUS_SUBJECT"
    DISCONNECTED = "DISCONNECTED"
    ENDED = "END_OF_FILE"
    STOPPED = "STOPPED"
    NO_MODEL = "NO_MODEL"
    ERROR = "ERROR"


LABELS = ("foarte scăzut", "scăzut", "ridicat", "foarte ridicat")
STATUS_TEXT = {
    Status.COLLECTING: "Se colectează date", Status.READY: "Rezultat disponibil",
    Status.NO_FACE: "Nicio față detectată", Status.LOW_QUALITY: "Față prea mică",
    Status.AMBIGUOUS: "Mai multe fețe — sursă ambiguă",
    Status.DISCONNECTED: "Sursă indisponibilă", Status.ENDED: "Sfârșit fișier",
    Status.STOPPED: "Oprit", Status.NO_MODEL: "Preprocesare activă · fără model",
    Status.ERROR: "Eroare de procesare",
}


@dataclass(frozen=True)
class PipelineConfig:
    window_seconds: float = 10.0
    frames: int = 16
    stride_seconds: float = 2.0
    image_size: int = 224
    crop_margin: float = 0.15
    min_face_pixels: int = 40
    max_gap_seconds: float = 1.0
    version: str = "yunet2023mar-320-rgb-imagenet-v1"

    def __post_init__(self):
        numeric = (self.window_seconds, self.stride_seconds, self.crop_margin, self.max_gap_seconds)
        if not all(math.isfinite(v) for v in numeric):
            raise ValueError("Parametri nefinți în configurație")
        if self.frames < 2 or self.image_size < 16 or self.min_face_pixels < 1:
            raise ValueError("Dimensiuni invalide")
        if self.window_seconds <= 0 or self.stride_seconds <= 0 or self.max_gap_seconds <= 0:
            raise ValueError("Duratele trebuie să fie pozitive")
        if not 0 <= self.crop_margin <= 1 or self.version != "yunet2023mar-320-rgb-imagenet-v1":
            raise ValueError("Configurație de preprocesare incompatibilă")

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class SourceConfig:
    source_id: str
    kind: str
    location: str
    participant_id: str

    def __post_init__(self):
        for value in (self.source_id, self.participant_id):
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", value):
                raise ValueError("Identificatorul acceptă 1–40 litere, cifre, _ sau -")
        if self.kind not in {"file", "camera", "network"} or not self.location.strip():
            raise ValueError("Sursă invalidă")
        if self.kind == "camera" and (not self.location.isdecimal()):
            raise ValueError("Camera necesită un index pozitiv sau zero")
        if self.kind == "network" and not self.location.lower().startswith(("rtsp://", "http://", "https://")):
            raise ValueError("Folosiți o adresă directă RTSP/HTTP(S)")

    def public_dict(self):
        # Do not export addresses, filenames, query tokens or camera credentials.
        return {"source_id": self.source_id, "participant_id": self.participant_id, "kind": self.kind}


@dataclass
class SequenceBatch:
    source_id: str
    participant_id: str
    generation: int
    start: float
    end: float
    frames: np.ndarray = field(repr=False)


@dataclass
class PredictionResult:
    source_id: str
    participant_id: str
    generation: int
    start: float
    end: float
    status: str
    label: int | None = None
    scores: list[float] | None = None
    model_version: str | None = None
    inference_ms: float | None = None
    received_at: str = ""

