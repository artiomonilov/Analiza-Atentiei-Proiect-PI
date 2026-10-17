import numpy as np

from ..ai.fake_predictor import FakePredictor
from ..config import SequenceConfig
from ..contracts import PreparedSequence


def main() -> int:
    config = SequenceConfig()
    sequence = PreparedSequence(np.zeros((config.frames, 3, config.height, config.width), np.float32),
                                tuple(np.linspace(0, config.window_seconds, config.frames)), config.preprocessing_id)
    output = FakePredictor(config).predict(sequence)
    print(f"SIMULARE: {output.levels}; is_demo={output.is_demo}; {output.model_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
