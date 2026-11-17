from dataclasses import replace
import json
from pathlib import Path
import runpy

import numpy as np
import pytest

from audience_analysis.calibration import CalibrationManager
from audience_analysis.eye_features import EyeFeaturesEstimator


@pytest.fixture
def face():
    return runpy.run_path(str(Path(__file__).with_name("test_eye_features.py")))["face_fixture"]()


def test_neutral_profile_roundtrip_reuses_estimators(face, tmp_path):
    manager = CalibrationManager(["C01"])
    manager.calibrate_neutral([(face, (800, 400))])
    manager.calibrate_ear("left", [.3] * 5, [.1] * 5)
    assert manager.temporal_config().left_blink.close == pytest.approx(.17)
    path = tmp_path / "profile.json"
    manager.save(path)
    restored = CalibrationManager.load(path)
    assert restored.pose.estimate(face.transformation_matrix).yaw == pytest.approx(0)
    assert restored.eyes.estimate(face, (800, 400)).left.gaze_delta == pytest.approx((0, 0))
    assert not restored.quality["neutral"]["temporal_stability_verified"]
    assert "landmarks" not in path.read_text()
    with pytest.raises(FileExistsError): manager.save(path)


def test_failed_recalibration_keeps_previous_state(face):
    manager = CalibrationManager(["C01"])
    manager.calibrate_neutral([(face, (800, 400))])
    before = manager.to_dict()
    with pytest.raises(ValueError): manager.calibrate_neutral([(None, (800, 400))])
    assert manager.to_dict() == before


def test_neutral_quality_rejects_instability(face):
    rotated = np.eye(4)
    rotated[:3, :3] = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
    manager = CalibrationManager(["C01"])
    with pytest.raises(ValueError, match="instabilă"):
        manager.calibrate_neutral([(face, (800, 400)), (replace(face, transformation_matrix=rotated), (800, 400))])


@pytest.mark.parametrize("opened,closed", [([.3] * 2, [.1] * 2), ([.2] * 5, [.3] * 5), ([float("nan")] * 5, [.1] * 5)])
def test_invalid_ear_calibration(opened, closed):
    with pytest.raises(ValueError): CalibrationManager(["C01"]).calibrate_ear("left", opened, closed)


def test_invalid_serialized_calibration(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": 77}))
    with pytest.raises(ValueError): CalibrationManager.load(path)
    with pytest.raises(ValueError): CalibrationManager("C01")
    with pytest.raises(ValueError): CalibrationManager(["C01"]).save(path)


def test_eye_state_validation_is_atomic(face):
    eyes = EyeFeaturesEstimator()
    eyes.calibrate(face, (800, 400))
    previous = eyes.calibration_state()
    with pytest.raises(ValueError): eyes.load_calibration_state({"left": {"ear": .3, "iris_position": [2, 0]}})
    assert eyes.calibration_state() == previous


def test_calibration_cli_from_separate_synthetic_open_closed_csv(tmp_path):
    opened, closed = tmp_path / "open.csv", tmp_path / "closed.csv"
    header = "timestamp_ms,left_ear,right_ear\n"
    opened.write_text(header + "".join(f"{i * 100},0.3,0.31\n" for i in range(5)))
    closed.write_text(header + "".join(f"{i * 100},0.1,0.09\n" for i in range(5)))
    output = tmp_path / "calibration.json"
    main = runpy.run_path(str(Path(__file__).resolve().parents[2] / "calibrate_session.py"))["main"]
    assert main(["--open-measurements", str(opened), "--closed-measurements", str(closed), "--session-id", "C01", "--output", str(output)]) == 0
    assert CalibrationManager.load(output).temporal_config().left_blink.close == pytest.approx(.17)
