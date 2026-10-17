import subprocess
import sys

import pytest

from audience_analysis.ai.fake_predictor import FakePredictor
from audience_analysis.ai.predictor import RealPredictor


def test_fake_is_deterministic_and_explicit(config, sequence):
    predictor = FakePredictor(config)
    first, second = predictor.predict(sequence), predictor.predict(sequence)
    assert first == second
    assert first.is_demo is True
    assert first.levels == {"engagement": 2}


def test_real_never_falls_back(config, sequence):
    with pytest.raises(NotImplementedError, match="P1-S3.3"):
        RealPredictor("not-configured.pt", config).predict(sequence)


def test_p1_example_needs_no_qt_cv2_or_torch():
    code = """
import sys
from audience_analysis.examples.p1_predictor_demo import main
assert main() == 0
assert not any(name.split('.')[0] in {'PySide6', 'PyQt5', 'cv2', 'torch'} for name in sys.modules)
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert "SIMULARE" in result.stdout


def test_default_cli_does_not_load_qt_or_simulate():
    code = """
import sys
from audience_analysis.__main__ import main
assert main() == 0
assert not any(name.startswith('PySide6') for name in sys.modules)
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, encoding="utf-8", timeout=15)
    assert result.returncode == 0, result.stderr
    assert "Modelul real nu este configurat" in result.stdout
