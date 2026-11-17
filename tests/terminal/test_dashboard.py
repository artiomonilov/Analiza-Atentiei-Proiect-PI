import csv
from dataclasses import replace
import json

import numpy as np
import pytest

from audience_analysis.dashboard_data import (
    DashboardSession, SessionStore, VideoNavigator, export_annotations, load_rows,
    segments, select_interval, validate_annotations, with_head_variation,
)
from audience_analysis.temporal_analysis import BlinkEvent
from audience_analysis.validation import read_blinks


@pytest.fixture
def measurement_csv(tmp_path):
    path = tmp_path / "measurements.csv"
    fields = ["timestamp_ms", "frame_index", "face_detected", "yaw", "pitch", "roll", "left_ear", "right_ear",
              "left_iris_x", "left_iris_y", "right_iris_x", "right_iris_y", "left_ear_relative", "left_gaze_dx", "left_gaze_dy"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for i in range(3):
            writer.writerow({"timestamp_ms": i * 100, "frame_index": i, "face_detected": i != 1,
                             "yaw": i, "pitch": 0, "roll": 0, "left_ear": .3, "right_ear": .3,
                             "left_iris_x": .5, "left_iris_y": .5, "right_iris_x": .5, "right_iris_y": .5,
                             "left_ear_relative": 1, "left_gaze_dx": 0, "left_gaze_dy": 0})
    return path


def test_load_calibrated_columns_and_missing_values(measurement_csv):
    rows = load_rows(measurement_csv)
    assert rows[0]["left_ear_relative"] == 1
    assert rows[0]["right_ear_relative"] is None
    assert rows[0]["left_gaze_dx"] == 0


def test_no_interpolation_across_missing_face(measurement_csv):
    groups = segments(load_rows(measurement_csv), "yaw")
    assert groups == [[(0, 0)], [(.2, 2)]]


def test_segments_break_wrap_and_large_gaps(measurement_csv):
    rows = load_rows(measurement_csv)
    rows[1]["face_detected"] = True
    rows[0]["roll"], rows[1]["roll"] = 179, -179
    assert len(segments(rows, "roll")) == 2
    rows[2]["timestamp_ms"] = 1000
    assert len(segments(rows, "yaw")) == 2


def test_interval_and_variation_reset(measurement_csv):
    rows = load_rows(measurement_csv)
    assert len(select_interval(rows, 0, 100)) == 2
    assert all(row["head_variation"] is None for row in with_head_variation(rows))
    with pytest.raises(ValueError): select_interval(rows, 20, 10)


def test_annotations_are_independent_and_export_compatible(tmp_path):
    automatic = BlinkEvent("left", 10, 50, 40)
    manual = validate_annotations([replace(automatic, start_ms=12)])
    assert automatic.start_ms == 10 and automatic.validation_status == "automatic_unvalidated"
    path = tmp_path / "manual.csv"
    export_annotations(path, manual)
    assert read_blinks(path)[0].start_ms == 12
    with pytest.raises(FileExistsError): export_annotations(path, manual)


@pytest.mark.parametrize("events", [[BlinkEvent("other", 0, 20, 20)], [BlinkEvent("left", 20, 10, -10)],
                                    [BlinkEvent("left", 10, 80, 70), BlinkEvent("left", 20, 60, 40)]])
def test_invalid_or_overlapping_annotations(events):
    with pytest.raises(ValueError): validate_annotations(events)


def test_session_evaluation_without_reference_is_na(measurement_csv):
    session = DashboardSession.from_csv(measurement_csv, "V01")
    report = session.evaluate()
    assert report["head_pose"]["axes"]["yaw"]["mae"] is None
    assert report["blinks"] is None
    session.role = "calibration"
    with pytest.raises(ValueError): session.evaluate()


def test_session_save_reload_and_safe_delete(measurement_csv, tmp_path):
    store = SessionStore(tmp_path / "sessions")
    session = DashboardSession.from_csv(measurement_csv, "V01")
    session.manual = [BlinkEvent("left", 10, 80, 70)]
    session.automatic = [BlinkEvent("right", 10, 80, 70)]
    session.references = session.rows
    folder = store.save(session)
    restored = store.load(folder)
    assert restored.rows == session.rows
    assert restored.manual[0].validation_status == "manual_reference"
    assert restored.automatic[0].eye == "right"
    assert restored.references[0]["timestamp_ms"] == 0
    store.delete(folder)
    assert not folder.exists() and measurement_csv.exists()


def test_session_delete_refuses_root_and_unexpected_files(measurement_csv, tmp_path):
    store = SessionStore(tmp_path / "sessions")
    folder = store.save(DashboardSession.from_csv(measurement_csv, "V01"))
    (folder / "unexpected.txt").write_text("user file")
    with pytest.raises(ValueError): store.delete(folder)
    assert (folder / "measurements.csv").exists()
    with pytest.raises(ValueError): store.delete(store.root)


def test_saved_snapshot_does_not_re_read_modified_source(measurement_csv, tmp_path):
    store = SessionStore(tmp_path / "sessions")
    session = DashboardSession.from_csv(measurement_csv, "V01")
    measurement_csv.write_text("timestamp_ms\n999\n")
    folder = store.save(session)
    assert store.load(folder).rows[0]["timestamp_ms"] == 0


@pytest.mark.parametrize("change", ["date", "nonfinite_config"])
def test_invalid_metadata_is_rejected_before_snapshot_creation(measurement_csv, tmp_path, change):
    store = SessionStore(tmp_path / "sessions")
    session = DashboardSession.from_csv(measurement_csv, "V01")
    if change == "date": session.experiment_date = "invalid"
    else: session.config["invalid"] = float("nan")
    with pytest.raises(ValueError): store.save(session)
    assert not store.root.exists()


@pytest.fixture
def video_backend(monkeypatch):
    cv2 = pytest.importorskip("cv2")
    state = {"index": 0, "released": False, "wrong_index": False}
    class Capture:
        def isOpened(self): return True
        def get(self, prop):
            if prop == cv2.CAP_PROP_FRAME_COUNT: return 3
            if prop == cv2.CAP_PROP_FPS: return 10
            return 99 if state["wrong_index"] else state["index"]
        def set(self, _prop, index): state["index"] = index
        def read(self): state["index"] += 1; return True, np.zeros((60, 80, 3), np.uint8)
        def release(self): state["released"] = True
    monkeypatch.setattr(cv2, "VideoCapture", lambda _: Capture())
    return state


def test_video_frame_timestamp_uses_csv_not_estimated_player_time(video_backend):
    navigator = VideoNavigator("local.avi", [{"frame_index": "0", "timestamp_ms": 1}, {"frame_index": "1", "timestamp_ms": 45}])
    assert navigator.read(0)[1] == 1
    assert navigator.read(1)[1] == 45
    assert navigator.read(2)[1] is None
    navigator.close()
    assert video_backend["released"]


def test_unconfirmed_decoder_position_refuses_mapping(video_backend):
    navigator = VideoNavigator("local.avi", [{"frame_index": "0", "timestamp_ms": 0}])
    video_backend["wrong_index"] = True
    with pytest.raises(ValueError): navigator.read(0)
    navigator.close()


def test_duplicate_frame_indices_releases_capture(video_backend):
    with pytest.raises(ValueError): VideoNavigator("local.avi", [{"frame_index": 0, "timestamp_ms": 0}, {"frame_index": 0, "timestamp_ms": 100}])
    assert video_backend["released"]


def test_chart_has_separate_series_for_missing_intervals(qtbot, measurement_csv):
    from audience_analysis.ui.experimental_dashboard import make_chart
    view = make_chart("Yaw", [("yaw", segments(load_rows(measurement_csv), "yaw"))])
    qtbot.addWidget(view)
    assert len(view.chart().series()) == 2 and view.property("point_count") == 2


def test_dashboard_load_edit_validate_and_save(qtbot, measurement_csv, tmp_path):
    from PySide6.QtWidgets import QTableWidgetItem
    from audience_analysis.ui.experimental_dashboard import ExperimentalDashboard
    window = ExperimentalDashboard(tmp_path / "managed")
    qtbot.addWidget(window)
    session = DashboardSession.from_csv(measurement_csv, "V01")
    session.automatic = [BlinkEvent("left", 10, 50, 40)]
    window.add_session(session)
    window.manual_table.setRowCount(1)
    for col, value in enumerate(("left", "12", "52")):
        window.manual_table.setItem(0, col, QTableWidgetItem(value))
    window.apply_manual()
    assert session.manual[0].start_ms == 12 and session.automatic[0].start_ms == 10
    report = window.evaluate_session()
    assert report["head_pose"]["axes"]["yaw"]["mae"] is None
    assert any(window.metrics_table.item(row, 1).text() == "N/A" for row in range(window.metrics_table.rowCount()))
    window.config_editor.setPlainText(json.dumps({"experiment_id": "EDITED", "max_gap_ms": 200}))
    window.save_session()
    assert SessionStore(tmp_path / "managed").load(window.managed[id(session)]).config["experiment_id"] == "EDITED"


def test_save_does_not_create_reference_implicitly(qtbot, measurement_csv, tmp_path):
    from audience_analysis.ui.experimental_dashboard import ExperimentalDashboard
    window = ExperimentalDashboard(tmp_path / "managed")
    qtbot.addWidget(window)
    session = DashboardSession.from_csv(measurement_csv, "V01")
    window.add_session(session); window.save_session()
    assert session.manual is None
    assert not (window.managed[id(session)] / "manual.csv").exists()


def test_marking_without_timestamp_is_rejected(qtbot, tmp_path):
    from audience_analysis.ui.experimental_dashboard import ExperimentalDashboard
    window = ExperimentalDashboard(tmp_path / "managed")
    qtbot.addWidget(window)
    with pytest.raises(ValueError): window.mark_start()


def test_independent_synthetic_reference_reuses_validation_engine(measurement_csv):
    from audience_analysis.validation import CONVENTION
    session = DashboardSession.from_csv(measurement_csv, "V01")
    session.references = [{**row, "yaw": row["yaw"] - 1} for row in session.rows]
    session.config.update(head_reference_verified=True, prediction_head_convention=CONVENTION,
                          reference_head_convention=CONVENTION, prediction_head_frame="camera", reference_head_frame="camera")
    assert session.evaluate()["head_pose"]["axes"]["yaw"]["mae"] == 1


def test_refresh_charts_keeps_unapplied_manual_edit(qtbot, measurement_csv, tmp_path):
    from PySide6.QtWidgets import QTableWidgetItem
    from audience_analysis.ui.experimental_dashboard import ExperimentalDashboard
    window = ExperimentalDashboard(tmp_path / "managed"); qtbot.addWidget(window)
    window.add_session(DashboardSession.from_csv(measurement_csv, "V01"))
    window.manual_table.setRowCount(1)
    window.manual_table.setItem(0, 0, QTableWidgetItem("left"))
    window.refresh()
    assert window.manual_table.item(0, 0).text() == "left"


def test_graph_budget_and_segment_color_consistency(qtbot):
    from audience_analysis.ui.experimental_dashboard import make_chart
    view = make_chart("series", [("a", [[(0, 1)], [(1, 2)]])]); qtbot.addWidget(view)
    assert view.chart().series()[0].color() == view.chart().series()[1].color()
    large = make_chart("budget", [("b", [[(i, 1) for i in range(10005)]])]); qtbot.addWidget(large)
    assert large.property("point_count") == 10000
    assert "limită" in large.chart().title()


def test_timestamp_only_csv_dashboard_remains_usable(qtbot, tmp_path):
    from audience_analysis.ui.experimental_dashboard import ExperimentalDashboard
    path = tmp_path / "incomplete.csv"; path.write_text("timestamp_ms\n0\n100\n")
    window = ExperimentalDashboard(tmp_path / "managed"); qtbot.addWidget(window)
    window.add_session(DashboardSession.from_csv(path, "V01"))
    report = window.evaluate_session()
    assert report["quality"]["face_frames"] is None
    assert report["head_pose"]["axes"]["yaw"]["mae"] is None


def test_blink_rate_requires_detector_provenance_and_valid_coverage(measurement_csv):
    session = DashboardSession.from_csv(measurement_csv, "V01")
    base = session.rows[0]
    session.rows = [{**base, "timestamp_ms": i * 500} for i in range(21)]
    session.automatic = [BlinkEvent("left", 100, 200, 100), BlinkEvent("left", 11000, 12000, 1000)]
    assert session.blink_summary()["left"]["rate_per_min"] is None
    session.config["blink_detection_enabled"] = True
    assert session.blink_summary()["left"]["rate_per_min"] == 6
