from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path

from .contracts import PreparedSequence


@dataclass(frozen=True)
class SequenceConfig:
    frames: int = 4
    height: int = 24
    width: int = 32
    window_seconds: float = 0.6
    stride_seconds: float = 0.2
    sample_tolerance_s: float = 0.08
    scale: float = 1/255
    mean: tuple[float, float, float] = (0.0, 0.0, 0.0)
    std: tuple[float, float, float] = (1.0, 1.0, 1.0)

    def __post_init__(self) -> None:
        if any(type(v) is not int or v < 1 for v in (self.frames, self.height, self.width)) or self.frames < 2:
            raise ValueError("Dimensiuni de secvență invalide")
        if any(not math.isfinite(v) or v <= 0 for v in (self.window_seconds, self.stride_seconds, self.scale, self.sample_tolerance_s)):
            raise ValueError("Parametri temporali/scalare invalizi")
        if len(self.mean) != 3 or len(self.std) != 3 or any(not math.isfinite(v) for v in (*self.mean, *self.std)) or min(self.std) <= 0:
            raise ValueError("Normalizare invalidă")
        object.__setattr__(self, "mean", tuple(self.mean))
        object.__setattr__(self, "std", tuple(self.std))

    @property
    def preprocessing_id(self) -> str:
        digest = hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:16]
        return f"rgb-chw-v1-{digest}"


def validate_sequence(sequence: PreparedSequence, config: SequenceConfig) -> None:
    if sequence.frames.shape != (config.frames, 3, config.height, config.width):
        raise ValueError("Forma secvenței diferă de configurația predictorului")
    if sequence.preprocessing_id != config.preprocessing_id:
        raise ValueError("Configurația preprocesării nu corespunde predictorului")


def load_demo_config(path: str | Path) -> SequenceConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("is_demo") is not True:
        raise ValueError("Configurația trebuie marcată explicit is_demo=true")
    return SequenceConfig(**data["sequence"])
