"""Contract pentru un model temporal de angajament ce va fi furnizat ulterior."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EngagementResult:
    available: bool
    engagement: float | None = None
    boredom: float | None = None
    confusion: float | None = None
    frustration: float | None = None
    reason: str = "Model de angajament indisponibil"


class EngagementPredictor(Protocol):
    def predict_clip(self, frames: list[object]) -> EngagementResult: ...


class UnavailableEngagementPredictor:
    def predict_clip(self, frames: list[object]) -> EngagementResult:
        return EngagementResult(False)
