"""Mesaje serializabile de predare către P2/P3; fără captură, scheduler sau UI."""
from dataclasses import asdict
import json

from .contracts import identifier
from .validation import canonical_measurements, valid


def observation_payload(measurement, *, source_id, run_id, session_id, calibration_id=None, model_sha256=None):
    for value in (source_id, run_id, session_id): identifier(value)
    if calibration_id is not None: identifier(calibration_id)
    if model_sha256 is not None and (not isinstance(model_sha256, str) or len(model_sha256) != 64 or any(c not in "0123456789abcdef" for c in model_sha256)):
        raise ValueError("Hash de model invalid.")
    row = canonical_measurements([asdict(measurement)])[0]
    for component, flag in (("head", "head_pose_available"), ("left_ear", "left_ear_available"), ("right_ear", "right_ear_available"),
                             ("left_iris", "left_iris_available"), ("right_iris", "right_iris_available")):
        if row.get(flag) is True and not valid(row, component): raise ValueError("Availability incompatibilă cu geometria.")
    result = {"schema_version": 1, "kind": "facial_geometry", "source_id": source_id, "run_id": run_id, "session_id": session_id,
        "calibration_id": calibration_id, "model_sha256": model_sha256, "measurement": row,
        "head_pose_frame": "neutral" if row.get("head_pose_calibrated") else "camera",
        "units": {"timestamp_ms": "milliseconds_media_or_monotonic", "head_pose": "degrees_xyz_rzryrx", "iris": "eye_local_normalized", "ear": "dimensionless"},
        "interpretation": "geometry_only_not_attention_or_screen_gaze"}
    json.dumps(result, allow_nan=False)
    return result


def temporal_payload(update, *, source_id, run_id, session_id):
    for value in (source_id, run_id, session_id): identifier(value)
    result = {"schema_version": 1, "kind": "temporal_geometry", "source_id": source_id, "run_id": run_id,
              "session_id": session_id, "features": asdict(update), "interpretation": "automatic_events_not_manual_ground_truth"}
    json.dumps(result, allow_nan=False)
    return result
