"""Predictor P1 pentru un pachet local validat; FakePredictor rămâne separat."""
from pathlib import Path

import numpy as np

from .data import validate_model_sequence
from ..contracts import ModelOutput, PreparedSequence, Status


class ModelUnavailableError(RuntimeError):
    status = Status.MODEL_UNAVAILABLE


class RealPredictor:
    def __init__(self, model_path, config=None, *, loader=None):
        from .package import load_package, validate_manifest
        self.model_path = Path(model_path)
        try:
            self.backend = (loader or load_package)(self.model_path)
            metadata = self.backend.manifest
            validated_config = validate_manifest(metadata)
            if config is not None and config != validated_config:
                raise ValueError("Configurația solicitată diferă de pachet.")
            self.config, self.dimensions = validated_config, tuple(metadata["dimensions"])
            self.model_version = metadata["model_version"]
        except (OSError, ValueError, KeyError, TypeError, ImportError, RuntimeError) as error:
            raise ModelUnavailableError("MODEL_UNAVAILABLE: pachet local lipsă, nevalidat sau incompatibil.") from error

    def predict(self, sequence: PreparedSequence) -> ModelOutput:
        if not isinstance(sequence, PreparedSequence): raise ValueError("Intrarea trebuie să fie PreparedSequence.")
        validate_model_sequence(sequence, self.config)
        # Datele sunt deja float32 RGB CHW; fără reconversie sau normalizare.
        logits = self.backend.predict_logits(sequence.frames)
        if set(logits) != set(self.dimensions): raise ValueError("Dimensiuni incompatibile în ieșirea modelului.")
        levels = {}
        for dimension in self.dimensions:
            values = np.asarray(logits[dimension])
            if values.shape != (4,) or not np.issubdtype(values.dtype, np.number) or not np.isrealobj(values) or not np.isfinite(values).all():
                raise ValueError("Logits incompatibili: patru clase finite per dimensiune.")
            levels[dimension] = int(values.argmax())
        return ModelOutput(levels, self.model_version, is_demo=False)
