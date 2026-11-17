import csv
import json
from pathlib import Path
import runpy

import pytest

from audience_analysis.temporal_analysis import BlinkEvent
from audience_analysis.validation import CONVENTION, blink_metrics, data_quality, evaluate, read_blinks, read_measurements, save_report


def row(t, yaw=0, roll=0, iris=.5):
    return {"timestamp_ms": t, "face_detected": True, "head_pose_available": True,
            "head_pose_calibrated": False, "yaw": yaw, "pitch": 0, "roll": roll,
            "left_ear": .3, "right_ear": .3, "left_iris_x": iris, "left_iris_y": .5,
            "right_iris_x": iris, "right_iris_y": .5}


def config(**kwargs):
    return {"experiment_id": "SYNTHETIC", "session_id": "V01", "calibration_session_ids": ["C01"],
            "prediction_head_convention": CONVENTION, "reference_head_convention": CONVENTION,
            "prediction_head_frame": "camera", "reference_head_frame": "camera", "head_reference_verified": True, **kwargs}


def test_head_mae_rmse_and_periodic_roll():
    report = evaluate([row(0, 10, 179), row(100, 20, -179)], config(), references=[row(0, 8, -179), row(100, 16, 179)])
    assert report["head_pose"]["axes"]["yaw"]["mae"] == 3
    assert report["head_pose"]["axes"]["yaw"]["rmse"] == pytest.approx(10 ** .5)
    assert report["head_pose"]["axes"]["roll"]["mae"] == 2


@pytest.mark.parametrize("changes", [{"head_reference_verified": False}, {"reference_head_convention": "other"},
                                   {"reference_head_frame": "neutral"}])
def test_incompatible_reference_does_not_produce_degree_accuracy(changes):
    report = evaluate([row(0)], config(**changes), references=[row(0)])
    assert report["head_pose"]["axes"]["yaw"]["mae"] is None


def test_absent_or_incomplete_reference():
    assert evaluate([row(0)], config())["head_pose"]["axes"]["yaw"]["mae"] is None
    reference = row(0)
    reference["pitch"] = None
    assert evaluate([row(0)], config(), references=[reference])["head_pose"]["axes"]["yaw"]["count"] == 0


def test_categories_are_separate_from_degrees():
    a, b = row(0), row(0)
    a["orientation_category"] = b["orientation_category"] = "left"
    report = evaluate([a], config(head_reference_verified=False), references=[b])
    assert report["head_pose"]["categorical"]["agreement"] == 1
    assert report["head_pose"]["axes"]["yaw"]["mae"] is None


def test_blink_metrics_and_timing():
    detected = [BlinkEvent("left", 100, 250, 150), BlinkEvent("left", 1000, 1200, 200)]
    reference = [BlinkEvent("left", 110, 260, 150), BlinkEvent("right", 1000, 1200, 200)]
    result = blink_metrics(detected, reference, tolerance_ms=20, valid_duration_ms=60000)
    assert (result["tp"], result["fp"], result["fn"]) == (1, 1, 1)
    assert result["precision"] == result["recall"] == result["f1"] == .5
    assert result["start_error_ms"]["mae"] == 10
    assert result["duration_error_ms"]["mae"] == 0
    assert result["false_positives_per_min"] == 1


def test_undefined_metrics_are_null():
    result = blink_metrics([], [])
    assert result["precision"] is result["recall"] is result["f1"] is None
    assert result["false_positives_per_min"] is None
    assert evaluate([], config())["quality"]["components"]["head"]["valid_fraction"] is None


def test_data_quality_missing_samples_and_gaps():
    missing = row(100)
    missing["face_detected"] = False
    quality = data_quality([row(0), missing, row(200), row(1000)])
    assert quality["face_frames"] == 3
    assert quality["components"]["head"]["valid_fraction"] == .75
    assert quality["components"]["head"]["valid_duration_ms"] == 0
    assert quality["components"]["head"]["missing_sample_intervals"] == [{"first_missing_ms": 100, "last_missing_ms": 100}]
    assert len(quality["timestamp_gaps"]) == 1


def test_scenarios_repeated_iris_and_lighting():
    scenarios = [{"name": "first", "start_ms": 0, "end_ms": 100, "repeat_group": "neutral", "lighting": "normal", "stable_head": True},
                 {"name": "second", "start_ms": 100, "end_ms": 200, "repeat_group": "neutral", "lighting": "dim"}]
    report = evaluate([row(0, iris=.5), row(100, iris=.6)], config(scenarios=scenarios, iris_reference_verified=True, iris_reference_convention="iris_local_normalized"),
                      references=[row(0, iris=.4), row(100, iris=.5)])
    assert report["iris"]["left"]["axes"]["left_iris_x"]["mae"] == pytest.approx(.1)
    assert report["repeat_differences"][0]["delta_mean"] == pytest.approx([.1, 0])
    assert set(report["conditions"]["lighting"]) == {"normal", "dim"}


def test_scenario_blinks_are_scoped_and_boundary_events_are_excluded():
    scenarios = [{"name": "first", "start_ms": 0, "end_ms": 500},
                 {"name": "second", "start_ms": 500, "end_ms": 1000}]
    detected = [BlinkEvent("left", 100, 200, 100), BlinkEvent("left", 450, 550, 100), BlinkEvent("left", 600, 700, 100)]
    reference = [BlinkEvent("left", 100, 200, 100), BlinkEvent("left", 450, 550, 100)]
    report = evaluate([row(t) for t in range(0, 1001, 50)], config(scenarios=scenarios, blink_reference_complete=True),
                      detected_blinks=detected, reference_blinks=reference)
    first, second = [s["blinks"]["left"] for s in report["scenarios"]]
    assert (first["tp"], first["fp"], first["fn"], first["f1"]) == (1, 0, 0, 1)
    assert (second["tp"], second["fp"], second["fn"]) == (0, 1, 0)
    assert first["excluded_scenario_boundary"] == second["excluded_scenario_boundary"] == {"detections": 1, "references": 1}
    assert report["blinks"]["left"]["tp"] == 2


def test_scenario_without_ear_does_not_claim_blink_accuracy():
    missing = [{**row(t), "left_ear": None} for t in (0, 100)]
    report = evaluate(missing, config(scenarios=[{"name": "missing", "start_ms": 0, "end_ms": 200}], blink_reference_complete=True),
                      detected_blinks=[], reference_blinks=[])
    assert report["scenarios"][0]["blinks"]["left"]["f1"] is None


@pytest.mark.parametrize("changes", [{"session_id": "C01"}, {"recording_id": "R01", "calibration_recording_ids": ["R01"]},
    {"cross_person": True, "test_participant": "P01", "training_participants": ["P01"]}])
def test_evaluation_split_leakage_is_rejected(changes):
    with pytest.raises(ValueError): evaluate([row(0)], config(**changes))


def test_csv_missing_and_invalid_fields(tmp_path):
    path = tmp_path / "measurements.csv"
    path.write_text("timestamp_ms,yaw,pitch,roll\n0,0,,0\n100,1,2,3\n")
    rows = read_measurements(path)
    assert rows[0]["yaw"] == 0 and rows[0]["pitch"] is None
    path.write_text("timestamp_ms\n10\n10\n")
    with pytest.raises(ValueError): read_measurements(path)
    path.write_text("timestamp_ms,yaw\n0,nan\n")
    with pytest.raises(ValueError): read_measurements(path)


def test_invalid_annotations_and_duplicate_events(tmp_path):
    path = tmp_path / "blinks.csv"
    path.write_text("eye,start_ms,end_ms\nleft,20,10\n")
    with pytest.raises(ValueError): read_blinks(path)
    path.write_text("eye,start_ms,end_ms\nleft,10,20\nleft,10,20\n")
    with pytest.raises(ValueError): read_blinks(path)


def test_timestamp_validation_for_api():
    with pytest.raises(ValueError): evaluate([row(100), row(0)], config())
    with pytest.raises(ValueError): evaluate([row(0)], config(), references=[row(-1)])


def test_report_json_csv_and_optional_plot(tmp_path):
    report = evaluate([row(0, 2), row(100, 4)], config(), references=[row(0), row(100)])
    output = tmp_path / "report"
    save_report(report, output)
    assert json.loads((output / "report.json").read_text())["evaluated_measurements"] == 2
    assert "head_pose.axes.yaw.mae,3.0" in (output / "metrics.csv").read_text()
    with pytest.raises(FileExistsError): save_report(report, output)


def test_runner_with_real_format_but_synthetic_data(tmp_path):
    measurements = tmp_path / "frames.csv"
    measurements.write_text("timestamp_ms,face_detected,yaw,pitch,roll\n0,True,0,0,0\n100,False,,,\n")
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(config(head_reference_verified=False)))
    main = runpy.run_path(str(Path(__file__).resolve().parents[2] / "run_validation.py"))["main"]
    assert main(["--measurements", str(measurements), "--config", str(cfg), "--output-dir", str(tmp_path / "out")]) == 0


def test_partial_blink_reference_suppresses_precision_and_false_alert_rate():
    events = [BlinkEvent("left", 10, 80, 70)]
    result = evaluate([row(0), row(100)], config(), detected_blinks=events, reference_blinks=events)["blinks"]["left"]
    assert result["tp"] == 1 and result["precision"] is None and result["false_positives_per_min"] is None


def test_complete_reference_uses_only_valid_ear_coverage():
    events = [BlinkEvent("left", 10, 80, 70), BlinkEvent("left", 200, 250, 50)]
    result = evaluate([row(0), row(100)], config(blink_reference_complete=True), detected_blinks=events, reference_blinks=events)["blinks"]["left"]
    assert result["precision"] == result["recall"] == result["f1"] == 1
    assert result["valid_duration_ms"] == 100
    assert result["excluded_detections_outside_valid_ear"] == 1


def test_plot_written_only_with_computable_accuracy(tmp_path, monkeypatch):
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "matplotlib"))
    pytest.importorskip("matplotlib")
    report = evaluate([row(0, 2), row(100, 4)], config(), references=[row(0), row(100)])
    save_report(report, tmp_path / "plots", plots=True)
    assert (tmp_path / "plots" / "head_mae.png").is_file()


@pytest.mark.parametrize("value", [[], config(head_reference_verified="false"), config(scenarios="bad")])
def test_malformed_configuration_is_rejected(value):
    with pytest.raises(ValueError): evaluate([row(0)], value)
