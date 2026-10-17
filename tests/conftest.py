import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTEST_QT_API", "pyside6")

import numpy as np
import pytest

from audience_analysis.config import SequenceConfig
from audience_analysis.contracts import InferenceRequest, PreparedSequence


@pytest.fixture
def config():
    return SequenceConfig()


@pytest.fixture
def sequence(config):
    return PreparedSequence(np.zeros((config.frames, 3, config.height, config.width), np.float32),
                            tuple(np.linspace(0, config.window_seconds, config.frames)), config.preprocessing_id)


@pytest.fixture
def make_request(sequence):
    def build(source="P01", run="run1", number=0):
        import time
        return InferenceRequest(source, run, number, sequence.sample_times_s[0], sequence.sample_times_s[-1], time.monotonic(), sequence)
    return build
