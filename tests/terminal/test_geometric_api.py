import json
from dataclasses import replace

import pytest

from audience_analysis.eye_features import EyeFeaturesEstimator
from audience_analysis.head_pose import HeadPoseEstimator
from audience_analysis.temporal_analysis import TemporalAnalyzer
from audience_analysis.video_processor import measurement
from audience_analysis.geometric_api import observation_payload, temporal_payload


def missing_measurement():
    return measurement(100, 1, False, HeadPoseEstimator().estimate(None), EyeFeaturesEstimator().estimate(None, (640, 480)), "synthetic", 0.)


def test_geometry_handoff_preserves_missing_values_units_and_identifiers():
    row = missing_measurement()
    payload = observation_payload(row, source_id="S1", run_id="RUN1", session_id="D01")
    assert payload["measurement"]["timestamp_ms"] == 100
    assert payload["measurement"]["yaw"] is None and payload["measurement"]["head_pose_available"] is False
    assert payload["run_id"] == "RUN1" and "levels" not in payload
    assert "geometry_only" in json.dumps(payload)
    temporal = temporal_payload(TemporalAnalyzer().update(row), source_id="S1", run_id="RUN1", session_id="D01")
    assert temporal["features"]["new_blinks"] == ()


def test_handoff_rejects_inconsistent_availability_and_missing_ids():
    with pytest.raises(ValueError): observation_payload(replace(missing_measurement(), head_pose_available=True), source_id="S1", run_id="R", session_id="D01")
    with pytest.raises(ValueError): observation_payload(missing_measurement(), source_id="", run_id="R", session_id="D01")
