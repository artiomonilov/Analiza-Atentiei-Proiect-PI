import csv
from types import SimpleNamespace as NS

import numpy as np
import pytest

from audience_analysis.face_landmarker import FaceLandmarks, Landmark, LandmarkerResult
from audience_analysis.eye_features import LEFT_EAR, LEFT_IRIS, RIGHT_EAR, RIGHT_IRIS
from audience_analysis.video_processor import FrameClock, VideoProcessor


def face_fixture():
    points = [Landmark(.5, .5, 0) for _ in range(478)]
    for cx, six, iris in ((600, LEFT_EAR, LEFT_IRIS), (200, RIGHT_EAR, RIGHT_IRIS)):
        for index, (x, y) in zip(six, [(-50, 0), (-25, -15), (25, -15), (50, 0), (25, 15), (-25, 15)]):
            points[index] = Landmark((cx + x) / 800, (200 + y) / 400, 0)
        for index, (x, y) in zip(iris, [(10, 0), (0, 10), (-10, 0), (0, -10)]):
            points[index] = Landmark((cx + x) / 800, (200 + y) / 400, 0)
    return FaceLandmarks(tuple(points), (), np.eye(4))


@pytest.fixture
def session(monkeypatch, tmp_path):
    import audience_analysis.video_processor as module
    cv2 = pytest.importorskip("cv2")
    state = NS(released=False, closed=0, initialized=0, calls=[], opened=True, index=0,
               frames=[np.zeros((400, 800, 3), np.uint8) for _ in range(3)],
               outcomes=[LandmarkerResult(()), LandmarkerResult((face_fixture(),)), LandmarkerResult(())])
    state.source, state.model = tmp_path / "video.avi", tmp_path / "model.task"
    state.source.touch()
    state.model.touch()

    class Capture:
        def isOpened(self): return state.opened
        def get(self, prop): return 25 if prop == cv2.CAP_PROP_FPS else max(0, state.index - 1) * 40
        def read(self):
            if state.index >= len(state.frames): return False, None
            frame = state.frames[state.index]
            state.index += 1
            if isinstance(frame, BaseException): raise frame
            return True, frame
        def release(self): state.released = True

    class Landmarker:
        def __init__(self, model, *, mode):
            assert model == state.model and mode == "VIDEO"
            state.initialized += 1
        def __enter__(self): return self
        def __exit__(self, *_): state.closed += 1
        def process_video(self, frame, timestamp):
            state.calls.append(timestamp)
            outcome = state.outcomes[len(state.calls) - 1]
            if isinstance(outcome, Exception): raise outcome
            return outcome

    monkeypatch.setattr(cv2, "VideoCapture", lambda _: Capture())
    monkeypatch.setattr(module, "FaceLandmarker", Landmarker)
    return state


def test_video_csv_face_loss_and_one_model(session, tmp_path):
    path = tmp_path / "measurements.csv"
    records = []
    report = VideoProcessor(session.model).run(session.source, display=False, output_csv=path, on_result=records.append)
    assert report.frames_processed == 3 and report.faces_detected == 1
    assert report.processing_fps > 0 and report.source_fps == 25
    assert session.calls == [0, 40, 80]
    assert session.initialized == session.closed == 1 and session.released
    assert records[0].yaw is None and records[0].left_ear is None
    assert records[1].head_pose_available and records[1].left_ear == pytest.approx(.3)
    assert records[1].left_iris_x == pytest.approx(.5)
    assert not records[2].face_detected and records[2].yaw is None
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert len(rows) == 3 and rows[0]["yaw"] == "" and rows[0]["left_iris_y"] == ""


@pytest.mark.parametrize("times,fps,expected", [([0, 40, 80], 25, [0, 40, 80]),
    ([0, 0, -1, float("nan")], 25, [0, 40, 80, 120]),
    ([0, 0, 0], 0, [0, 33, 67]), ([200, 150, 150], 25, [200, 201, 202])])
def test_file_clock_fallbacks(times, fps, expected):
    clock = FrameClock(webcam=False, source_fps=fps, start=0)
    assert [clock.next(i, value, 0)[0] for i, value in enumerate(times)] == expected


def test_webcam_monotonic_clock_and_rounding():
    clock = FrameClock(webcam=True, source_fps=0, start=100)
    assert [clock.next(i, 999999, now)[0] for i, now in enumerate([100, 100, 100.0001, 100.1])] == [0, 1, 2, 100]


@pytest.mark.parametrize("camera", [False, True])
def test_unavailable_capture_is_released(session, camera):
    session.opened = False
    with pytest.raises(RuntimeError, match="Camera|Videoclipul"):
        VideoProcessor(session.model).run(0 if camera else session.source, display=camera)
    assert session.released and session.initialized == 0


def test_empty_video(session):
    session.frames = []
    with pytest.raises(RuntimeError, match="nu conține cadre"):
        VideoProcessor(session.model).run(session.source, display=False)
    assert session.closed == 1 and session.released


def test_inference_error_does_not_reuse_previous_measurements(session):
    session.outcomes = [LandmarkerResult((face_fixture(),)), RuntimeError("inference failed"), LandmarkerResult((face_fixture(),))]
    records = []
    report = VideoProcessor(session.model).run(session.source, display=False, on_result=records.append)
    assert report.errors == 1 and records[1].error == "inference failed"
    assert records[1].yaw is None and records[2].yaw == pytest.approx(0)


def test_invalid_frame_and_recovery(session):
    session.frames[1] = None
    # Invalid frames are rejected before MediaPipe.
    session.outcomes = [LandmarkerResult(()), LandmarkerResult((face_fixture(),))]
    records = []
    report = VideoProcessor(session.model).run(session.source, display=False, on_result=records.append)
    assert report.errors == 1 and records[1].error
    assert session.calls == [0, 80]


def test_interrupt_keeps_partial_csv_and_releases(session, tmp_path):
    session.frames[1] = KeyboardInterrupt()
    path = tmp_path / "partial.csv"
    report = VideoProcessor(session.model).run(session.source, display=False, output_csv=path)
    assert report.stop_reason == "interrupted" and report.frames_processed == 1
    assert len(list(csv.DictReader(path.open(encoding="utf-8")))) == 1
    assert session.closed == 1 and session.released


def test_callback_error_releases_model_and_capture(session):
    def fail(_): raise RuntimeError("callback")
    with pytest.raises(RuntimeError, match="callback"):
        VideoProcessor(session.model).run(session.source, display=False, on_result=fail)
    assert session.closed == 1 and session.released


def test_neutral_reference_reuses_video_model(session, monkeypatch):
    import audience_analysis.video_processor as module
    monkeypatch.setattr(module, "load_image", lambda _: np.zeros((400, 800, 3), np.uint8))
    session.outcomes = [LandmarkerResult((face_fixture(),))] * 4
    records = []
    VideoProcessor(session.model).run(session.source, display=False, neutral_image=session.source, on_result=records.append)
    assert session.initialized == 1 and session.calls == [0, 1, 40, 80]
    assert records[0].left_ear_relative == pytest.approx(1)
    assert records[0].left_gaze_dx == pytest.approx(0)


def test_display_q_and_missing_face(session, monkeypatch):
    import cv2
    destroyed, displayed = [], []
    monkeypatch.setattr(cv2, "imshow", lambda name, image: displayed.append(image))
    monkeypatch.setattr(cv2, "waitKey", lambda _: ord("q"))
    monkeypatch.setattr(cv2, "destroyWindow", destroyed.append)
    report = VideoProcessor(session.model).run(0, display=True, show_landmarks=True)
    assert report.stop_reason == "q" and displayed[0].any()
    assert destroyed and session.released and session.closed == 1


def test_missing_source_model_and_no_display_webcam(session, tmp_path):
    with pytest.raises(ValueError, match="nu există"):
        VideoProcessor(session.model).run(tmp_path / "missing.avi", display=False)
    with pytest.raises(ValueError, match="Modelul"):
        VideoProcessor(tmp_path / "missing.task").run(session.source, display=False)
    with pytest.raises(ValueError, match="afișare"):
        VideoProcessor(session.model).run(0, display=False)


def test_no_default_export_and_no_csv_overwrite(session, tmp_path):
    output = tmp_path / "existing.csv"
    output.write_text("original", encoding="utf-8")
    with pytest.raises(FileExistsError):
        VideoProcessor(session.model).run(session.source, display=False, output_csv=output)
    assert output.read_text(encoding="utf-8") == "original"
    assert session.closed == 1 and session.released


def test_no_export_without_explicit_csv(session, tmp_path):
    before = set(tmp_path.iterdir())
    VideoProcessor(session.model).run(session.source, display=False)
    assert set(tmp_path.iterdir()) == before


def test_model_initialization_error_releases_capture(session, monkeypatch):
    import audience_analysis.video_processor as module
    def fail(*args, **kwargs): raise RuntimeError("model invalid")
    monkeypatch.setattr(module, "FaceLandmarker", fail)
    with pytest.raises(RuntimeError, match="model invalid"):
        VideoProcessor(session.model).run(session.source, display=False)
    assert session.released


def test_camera_read_failure_releases_resources(session):
    session.frames = []
    with pytest.raises(RuntimeError, match="încetat"):
        VideoProcessor(session.model).run(0)
    assert session.closed == 1 and session.released


def test_gui_error_is_reported_and_resources_are_released(session, monkeypatch):
    import cv2
    def fail(*args): raise cv2.error("GUI unavailable")
    monkeypatch.setattr(cv2, "imshow", fail)
    monkeypatch.setattr(cv2, "destroyWindow", fail)
    with pytest.raises(RuntimeError, match="no-display"):
        VideoProcessor(session.model).run(session.source)
    assert session.closed == 1 and session.released


def test_temporal_integration_csv_and_no_additional_inference(session, tmp_path):
    import json
    from audience_analysis.temporal_analysis import BlinkThresholds, TemporalConfig
    stats_path, events_path = tmp_path / "temporal.csv", tmp_path / "blinks.csv"
    updates = []
    report = VideoProcessor(session.model, temporal_config=TemporalConfig(left_blink=BlinkThresholds(.1, .2))).run(
        session.source, display=False, output_temporal_csv=stats_path, output_blinks_csv=events_path,
        on_temporal=updates.append)
    assert session.calls == [0, 40, 80] and session.initialized == 1
    assert len(updates) == 3 and report.temporal is updates[-1]
    rows = list(csv.DictReader(stats_path.open(encoding="utf-8")))
    assert len(rows) == 9 and json.loads(rows[0]["head_json"])["mean"] is None
    assert len(list(csv.DictReader(events_path.open(encoding="utf-8")))) == 0


def test_video_exports_completed_synthetic_blink(session, tmp_path):
    from dataclasses import replace
    from audience_analysis.temporal_analysis import BlinkThresholds, TemporalConfig
    face = face_fixture()
    points = list(face.landmarks)
    for six in (LEFT_EAR, RIGHT_EAR):
        for index in (six[1], six[2], six[4], six[5]):
            point = points[index]
            points[index] = replace(point, y=.5 + (point.y - .5) / 3)
    closed = replace(face, landmarks=tuple(points))
    session.outcomes = [LandmarkerResult((face,)), LandmarkerResult((closed,)), LandmarkerResult((face,))]
    path = tmp_path / "events.csv"
    report = VideoProcessor(session.model, temporal_config=TemporalConfig(left_blink=BlinkThresholds(.15, .22))).run(
        session.source, display=False, output_blinks_csv=path)
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert len(rows) == 1 and rows[0]["start_ms"] == "40" and rows[0]["end_ms"] == "80"
    assert rows[0]["duration_ms"] == "40" and rows[0]["validation_status"] == "automatic_unvalidated"
    assert report.temporal.blink_totals["left"] == 1
