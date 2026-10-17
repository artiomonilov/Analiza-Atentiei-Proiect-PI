from ..config import SequenceConfig, validate_sequence
from ..contracts import ModelOutput, PreparedSequence


class FakePredictor:
    """Scenariu fix, independent de pixeli; niciun rezultat AI real."""

    def __init__(self, config: SequenceConfig):
        self.config = config

    def predict(self, sequence: PreparedSequence) -> ModelOutput:
        validate_sequence(sequence, self.config)
        return ModelOutput({"engagement": 2}, "SIMULARE-fixed-v1", True)
