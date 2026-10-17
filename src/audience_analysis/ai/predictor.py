from pathlib import Path

from ..config import SequenceConfig, validate_sequence
from ..contracts import ModelOutput, PreparedSequence


class RealPredictor:
    def __init__(self, model_path: str | Path, config: SequenceConfig):
        self.model_path = Path(model_path)
        self.config = config

    def predict(self, sequence: PreparedSequence) -> ModelOutput:
        validate_sequence(sequence, self.config)
        # TODO P1-S3.3: intrare = pachetul antrenat + PreparedSequence;
        # încărcare unică/adaptare a models.py existent, fără a renormaliza;
        # ieșire ModelOutput(is_demo=False); verificare prin paritate P1-S3.4.
        raise NotImplementedError("P1-S3.3: predictorul real nu este configurat; simularea nu se activează automat")
