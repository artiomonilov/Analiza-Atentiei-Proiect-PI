"""Integrare P2 cu cadre/landmarks sintetice; nu sunt rezultate pe persoane."""
from dataclasses import asdict, replace
import csv
import json
from pathlib import Path
import runpy
from threading import Event, Lock
from types import SimpleNamespace as NS

import numpy as np
import pytest

from audience_analysis.config import SequenceConfig
from audience_analysis.contracts import FramePacket, InferenceRequest, SourceConfig, Status
from audience_analysis.engine.controller import EngineController
from audience_analysis.engine.facial import FacialAnalysisSession, GeometryConfig, associated_track
from audience_analysis.engine.scheduler import LatestScheduler
from audience_analysis.engine.workers import FeatureStore
from audience_analysis.face_landmarker import LandmarkerResult
from audience_analysis.video.sources import FileSource, LiveSource
from audience_analysis.video.tracking import FaceTracker


@pytest.fixture
def fixture_data(tmp_path):
    helper = runpy.run_path(str(Path(__file__).parents[1] / "terminal" / "test_eye_features.py"))
    return NS(face=helper["face_fixture"], size=helper["SIZE"], root=tmp_path)


def video_file(path, frames=12, fps=10, size=(800, 400)):
    import cv2
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, size)
    assert writer.isOpened()
    try:
        for index in range(frames):
            writer.write(np.full((size[1], size[0], 3), index, np.uint8))
    finally:
        writer.release()
    return path


def fake_landmarker(state, outcomes):
    class Landmarker:
        def __init__(self, path, *, mode):
            assert mode == "VIDEO"
            self.index = 0
            self.closed = False
            state.initialized += 1

        def process_video(self, frame, timestamp):
            state.calls.append((id(self), timestamp))
            outcome = outcomes[self.index % len(outcomes)]
            self.index += 1
            if isinstance(outcome, Exception):
                raise outcome
            return LandmarkerResult((outcome,) if outcome is not None else ())

        def close(self):
            if not self.closed:
                state.closed += 1
                self.closed = True

        def __enter__(self): return self
        def __exit__(self, *_error): self.close()
    return Landmarker


class FullFrameDetector:
    def detect(self, image):
        from audience_analysis.video.preprocessing import FaceDetection
        height, width = image.shape[:2]
        return FaceDetection(Status.OK, ((0, 0, width, height),), (image,))


def unavailable():
    raise RuntimeError("No P1 package in synthetic test")


def finish(engine, qtbot):
    engine.shutdown()
    qtbot.waitUntil(lambda: engine.is_shutdown, timeout=7000)


def test_p2_one_capture_one_model_per_frame_export_and_dashboard(qtbot, fixture_data, monkeypatch):
    import cv2
    from audience_analysis.dashboard_data import DashboardSession, SessionStore
    source_path = video_file(fixture_data.root / "synthetic.avi")
    model = fixture_data.root / "mock.task"; model.write_text("mock used only by injected test class")
    state = NS(initialized=0, closed=0, calls=[])
    marker = fake_landmarker(state, [fixture_data.face(), None, RuntimeError("C:/private/error.jpg")])
    capture, opened = cv2.VideoCapture, []
    monkeypatch.setattr(cv2, "VideoCapture", lambda *args, **kwargs: (opened.append(args), capture(*args, **kwargs))[1])
    settings = GeometryConfig(model, "D01", output_dir=fixture_data.root / "exports", data_kind="synthetic")
    engine = EngineController(SequenceConfig(), unavailable, demo=False, realtime=False,
                              detector_factory=FullFrameDetector,
                              geometry_factory=lambda source, run: FacialAnalysisSession(source, run, settings, landmarker_factory=marker))
    statuses, results, features, loaded = [], [], [], []
    engine.status_changed.connect(statuses.append)
    engine.result_ready.connect(results.append)
    engine.geometry_ready.connect(features.append)
    engine.model_status_changed.connect(loaded.append)
    try:
        engine.add_source(SourceConfig("S01", "Synthetic", "file", str(source_path)))
        run = engine.start_source("S01")
        qtbot.waitUntil(lambda: any(e.status == Status.END_OF_SOURCE for e in statuses), timeout=10000)
        directory = settings.output_dir / "S01" / run
        rows = list(csv.DictReader((directory / "measurements.csv").open(encoding="utf-8")))
        assert len(opened) == 1 and state.initialized == state.closed == 1
        assert len(rows) == len(state.calls) == 12
        assert [stamp for _, stamp in state.calls] == [100 * i for i in range(12)]
        assert float(rows[0]["yaw"]) == pytest.approx(0) and float(rows[0]["left_ear"]) == pytest.approx(.3)
        assert rows[1]["yaw"] == rows[1]["left_ear"] == ""
        assert rows[2]["yaw"] == "" and rows[2]["association_status"] == "processing_error"
        assert "private" not in (directory / "measurements.csv").read_text()
        assert all(row["source_id"] == "S01" and row["run_id"] == run for row in rows)
        assert len(list(csv.DictReader((directory / "temporal.csv").open()))) == 36
        assert loaded and loaded[0]["status"] == "MODEL_UNAVAILABLE"
        assert results and all(r.status == Status.MODEL_UNAVAILABLE and r.levels is None for r in results)
        assert features and all(f.source_id == "S01" and f.run_id == run for f in features)
        session = DashboardSession.from_csv(directory / "measurements.csv", "D01")
        session.automatic = []
        report = session.evaluate()
        assert report["reference_pairs"] == 0 and report["head_pose"]["axes"]["yaw"]["mae"] is None
        store = SessionStore(fixture_data.root / "managed")
        assert len(store.load(store.save(session)).rows) == 12
        summary = json.loads((directory / "summary.json").read_text())
        assert summary["stop_reason"] == "end_of_file" and summary["data_kind"] == "synthetic"
    finally:
        finish(engine, qtbot)


def test_geometry_matches_original_video_processor_with_same_calibration(qtbot, fixture_data, monkeypatch):
    from audience_analysis.calibration import CalibrationManager
    from audience_analysis.video_processor import VideoProcessor
    import audience_analysis.video_processor as original
    source = video_file(fixture_data.root / "parity.avi", frames=10)
    model = fixture_data.root / "mock.task"; model.touch()
    manager = CalibrationManager(["C01"])
    manager.pose.calibrate(np.eye(4))
    manager.eyes.calibrate(fixture_data.face(), fixture_data.size)
    outcomes = [fixture_data.face(dx=10), None]
    state = NS(initialized=0, closed=0, calls=[])
    marker = fake_landmarker(state, outcomes)
    settings = GeometryConfig(model, "D01", calibration=manager.to_dict(), output_dir=fixture_data.root / "p2", data_kind="synthetic")
    engine = EngineController(SequenceConfig(), unavailable, demo=False, realtime=False, detector_factory=FullFrameDetector,
                              geometry_factory=lambda source, run: FacialAnalysisSession(source, run, settings, landmarker_factory=marker))
    ended = []
    engine.status_changed.connect(lambda event: ended.append(event.status))
    try:
        engine.add_source(SourceConfig("S01", "Synthetic", "file", str(source)))
        run = engine.start_source("S01")
        qtbot.waitUntil(lambda: Status.END_OF_SOURCE in ended, timeout=10000)
    finally:
        finish(engine, qtbot)
    from audience_analysis.dashboard_data import load_rows
    from audience_analysis.validation import canonical_measurements
    integrated = canonical_measurements(load_rows(settings.output_dir / "S01" / run / "measurements.csv"))
    monkeypatch.setattr(original, "FaceLandmarker", marker)
    second_manager = CalibrationManager.from_dict(manager.to_dict())
    records = []
    VideoProcessor(model, pose_estimator=second_manager.pose, eye_estimator=second_manager.eyes).run(source, display=False, on_result=records.append)
    assert state.initialized == state.closed == 2
    for row, reference in zip(integrated, records):
        for key in ("timestamp_ms", "frame_index", "yaw", "pitch", "roll", "left_ear", "right_ear", "left_iris_x", "left_iris_y",
                    "left_gaze_dx", "right_gaze_dx", "head_pose_calibrated", "head_pose_available"):
            assert row[key] == getattr(reference, key), key


def test_association_and_calibration_do_not_transfer_between_tracks(fixture_data):
    from audience_analysis.calibration import CalibrationManager
    model = fixture_data.root / "mock.task"; model.touch()
    face = fixture_data.face()
    assert associated_track(face, ((0, 0, 400, 400), (400, 0, 400, 400)), (0, 1), np.array(fixture_data.size))[1] == "ambiguous"
    manager = CalibrationManager(["C01"]); manager.pose.calibrate(np.eye(4))
    state = NS(initialized=0, closed=0, calls=[])
    session = FacialAnalysisSession(SourceConfig("S", "Synthetic", "file", "not-read-by-adapter"), "R",
                                   GeometryConfig(model, "D01", calibration=manager.to_dict()),
                                   landmarker_factory=fake_landmarker(state, [face]))
    image = np.zeros((400, 800, 3), np.uint8)
    try:
        packet = FramePacket("S", "R", 0, 0, image, ((0, 0, 800, 400),), (0,), "synthetic")
        first = session.process(packet)
        assert first.measurement.head_pose_available and first.track_id == 0
        second = session.process(replace(packet, frame_id=1, media_time_s=.1, track_ids=(1,)))
        assert second.association_status == "calibration_target_lost" and second.measurement.yaw is None
        assert not second.calibration_status["valid_for_target"]
        with pytest.raises(ValueError): session.process(packet)
    finally:
        session.close()


def test_restart_waits_for_old_capture_and_rejects_old_geometry(qtbot, fixture_data):
    source_path = video_file(fixture_data.root / "restart.avi", frames=8)
    model = fixture_data.root / "mock.task"; model.touch()
    entered, release = Event(), Event()
    state = NS(initialized=0, closed=0, calls=[])
    parent = fake_landmarker(state, [fixture_data.face()])
    class SlowFirst(parent):
        first = True
        def process_video(self, frame, timestamp):
            if SlowFirst.first:
                SlowFirst.first = False
                entered.set()
                assert release.wait(5)
            return super().process_video(frame, timestamp)
    counts = NS(active=0, maximum=0, opened=0)
    lock = Lock()
    def reader_factory(source, **kwargs):
        with lock:
            counts.active += 1; counts.opened += 1; counts.maximum = max(counts.maximum, counts.active)
        reader = FileSource(source.location)
        original_close = reader.close
        def close():
            original_close()
            with lock: counts.active -= 1
        reader.close = close
        return reader
    settings = GeometryConfig(model, "D01", output_dir=fixture_data.root / "restart-output")
    engine = EngineController(SequenceConfig(), unavailable, demo=False, realtime=False, reader_factory=reader_factory,
                              detector_factory=FullFrameDetector,
                              geometry_factory=lambda source, run: FacialAnalysisSession(source, run, settings, landmarker_factory=SlowFirst))
    features, statuses = [], []
    engine.geometry_ready.connect(features.append); engine.status_changed.connect(statuses.append)
    try:
        engine.add_source(SourceConfig("S", "Synthetic", "file", str(source_path)))
        old = engine.start_source("S")
        qtbot.waitUntil(entered.is_set)
        engine.stop_source("S")
        new = engine.start_source("S")
        assert counts.opened == 1
        release.set()
        qtbot.waitUntil(lambda: any(e.run_id == new and e.status == Status.END_OF_SOURCE for e in statuses), timeout=10000)
        assert counts.maximum == 1 and counts.opened == 2 and counts.active == 0
        assert features and all(value.run_id == new for value in features)
        assert json.loads((settings.output_dir / "S" / old / "summary.json").read_text())["stop_reason"] == "stopped"
    finally:
        release.set()
        finish(engine, qtbot)


def test_scheduler_run_expiration_and_bounded_delivery(make_request):
    scheduler = LatestScheduler()
    scheduler.activate("P01", "old")
    old = make_request(run="old")
    scheduler.submit(old); scheduler.take(block=False)
    scheduler.activate("P01", "new")
    scheduler.submit(make_request(run="new"))
    assert not scheduler.complete("P01", 0, run_id="old")
    assert scheduler.has_outstanding("P01") and scheduler.pending_counts()["P01"] == 1
    new = scheduler.take(block=False)
    for number in range(1, 101):
        scheduler.submit(replace(new, request_id=number, track_id=number))
    assert scheduler.pending_counts()["P01"] == 1
    assert len(scheduler.outstanding["P01"]) == 2
    assert scheduler.take(block=False) is None  # maximum un rezultat neconfirmat către controller
    scheduler.expire_tracks("P01", "new", [None])
    assert not scheduler.complete("P01", new.request_id, run_id="new")
    assert scheduler.take(block=False).request_id == 100


def test_tracker_expires_before_matching_and_bounds_churn():
    tracker = FaceTracker(max_missed_s=.5, max_tracks=4)
    assert tracker.update([(0, 0, 10, 10)], 0)[0] == (0,)
    assert tracker.update([(0, 0, 10, 10)], 1) == ((1,), [0])
    for index in range(100):
        tracker.update([(index * 20, 0, 10, 10)], 1 + index / 100)
        assert len(tracker.tracks) <= 4


def test_long_model_window_is_supported_with_a_bounded_history():
    from audience_analysis.video.sequences import SequenceBuilder
    config = SequenceConfig(frames=16, height=2, width=2, window_seconds=10, stride_seconds=1, sample_tolerance_s=.04)
    builder = SequenceBuilder(config)
    count = 0
    for index in range(600):
        count += builder.add(FramePacket("S", "R", index, index / 30, np.zeros((2, 2, 3), np.uint8))) is not None
    assert count >= 9 and len(builder.history) <= builder.history.maxlen <= 503
    with pytest.raises(ValueError): SequenceBuilder(config, max_frames=128)


def test_feature_mailbox_has_one_notification_and_no_old_run(make_request):
    store = FeatureStore(); store.activate("S", "R")
    assert store.put(NS(source_id="S", run_id="R", value=0))
    for i in range(100): assert not store.put(NS(source_id="S", run_id="R", value=i))
    assert store.take("S").value == 99
    store.activate("S", "R2")
    assert not store.put(NS(source_id="S", run_id="R", value=100))


def test_file_source_uses_media_positions_and_fallback(tmp_path, monkeypatch):
    import cv2
    source = tmp_path / "source.avi"; source.touch()
    class Capture:
        def __init__(self): self.index = -1; self.released = False
        def isOpened(self): return True
        def get(self, prop):
            return {cv2.CAP_PROP_FPS: 25, cv2.CAP_PROP_POS_MSEC: [0, 47, 111, float("nan")][max(0, self.index)]}.get(prop, 0)
        def read(self): self.index += 1; return True, np.zeros((2, 2, 3), np.uint8)
        def release(self): self.released = True
    cap = Capture(); monkeypatch.setattr(cv2, "VideoCapture", lambda *_args: cap)
    reader = FileSource(source)
    try:
        assert [round(reader.read()[1] * 1000) for _ in range(4)] == [0, 47, 111, 120]
        assert reader.timestamp_source == "video_fps"
    finally: reader.close()
    assert cap.released


def test_live_capture_releases_from_owner_and_prevents_duplicate_open():
    blocked = Event()
    class Capture:
        released = 0
        def isOpened(self): return True
        def read(self): blocked.wait(5); return False, None
        def release(self): self.released += 1
    cap = Capture()
    reader = LiveSource("integration-test-camera", kind="camera", read_timeout_s=.01, capture_factory=lambda *_args: cap)
    try:
        with pytest.raises(TimeoutError): reader.close()
        with pytest.raises(ConnectionError):
            LiveSource("integration-test-camera", kind="camera", capture_factory=lambda *_args: pytest.fail("duplicate capture"))
    finally:
        blocked.set(); reader._thread.join(2)
    assert not reader._thread.is_alive() and cap.released == 1


def test_two_geometry_sources_have_independent_contexts_and_missing_data(qtbot, fixture_data):
    source_path = video_file(fixture_data.root / "no-face.avi", frames=8)
    model = fixture_data.root / "mock.task"; model.touch()
    state = NS(initialized=0, closed=0, calls=[])
    marker = fake_landmarker(state, [None])
    def factory(source, run):
        settings = GeometryConfig(model, "D01" if source.source_id == "S1" else "D02", output_dir=fixture_data.root / "multi")
        return FacialAnalysisSession(source, run, settings, landmarker_factory=marker)
    engine = EngineController(SequenceConfig(), unavailable, demo=False, realtime=False,
                              detector_factory=FullFrameDetector, geometry_factory=factory)
    ended = []; features = []
    engine.status_changed.connect(lambda event: ended.append(event.source_id) if event.status == Status.END_OF_SOURCE else None)
    engine.geometry_ready.connect(features.append)
    try:
        runs = {}
        for source_id in ("S1", "S2"):
            engine.add_source(SourceConfig(source_id, "Synthetic", "file", str(source_path)))
            runs[source_id] = engine.start_source(source_id)
        qtbot.waitUntil(lambda: set(ended) == {"S1", "S2"}, timeout=10000)
        assert state.initialized == state.closed == 2 and len(state.calls) == 16
        assert len({instance for instance, _ in state.calls}) == 2
        for source_id in runs:
            path = fixture_data.root / "multi" / source_id / runs[source_id] / "measurements.csv"
            rows = list(csv.DictReader(path.open()))
            assert len(rows) == 8 and all(row["face_detected"] == "False" and row["yaw"] == "" for row in rows)
            assert all(row["source_id"] == source_id and row["run_id"] == runs[source_id] for row in rows)
        assert all(not result.measurement.head_pose_available for result in features)
    finally:
        finish(engine, qtbot)


def test_process_refuses_other_source_and_cleans_up(fixture_data):
    model = fixture_data.root / "mock.task"; model.touch()
    state = NS(initialized=0, closed=0, calls=[])
    session = FacialAnalysisSession(SourceConfig("S", "Synthetic", "file", "not-opened"), "R", GeometryConfig(model, "D01"),
                                   landmarker_factory=fake_landmarker(state, [None]))
    try:
        with pytest.raises(ValueError):
            session.process(FramePacket("other", "R", 0, 0, np.zeros((2, 2, 3), np.uint8)))
    finally:
        session.close(); session.close()
    assert state.closed == 1 and state.calls == []


def test_face_loss_and_return_reset_tracks_and_temporal(qtbot, fixture_data):
    from audience_analysis.video.preprocessing import FaceDetection
    source_path = video_file(fixture_data.root / "loss-return.avi", frames=3)
    model = fixture_data.root / "mock.task"; model.touch()
    state = NS(initialized=0, closed=0, calls=[])
    class Detector(FullFrameDetector):
        index = 0
        def detect(self, frame):
            self.index += 1
            return FaceDetection(Status.NO_FACE, ()) if self.index == 2 else super().detect(frame)
    settings = GeometryConfig(model, "D01", output_dir=fixture_data.root / "loss-output")
    marker = fake_landmarker(state, [fixture_data.face(), None, fixture_data.face()])
    engine = EngineController(SequenceConfig(), unavailable, demo=False, realtime=False, detector_factory=Detector,
                              geometry_factory=lambda source, run: FacialAnalysisSession(source, run, settings, landmarker_factory=marker))
    ended = []
    engine.status_changed.connect(lambda event: ended.append(event.status))
    try:
        engine.add_source(SourceConfig("S", "Synthetic", "file", str(source_path)))
        run = engine.start_source("S")
        qtbot.waitUntil(lambda: Status.END_OF_SOURCE in ended, timeout=10000)
        directory = settings.output_dir / "S" / run
        rows = list(csv.DictReader((directory / "measurements.csv").open()))
        assert [row["track_id"] for row in rows] == ["0", "", "1"]
        assert [row["head_pose_available"] for row in rows] == ["True", "False", "True"]
        windows = list(csv.DictReader((directory / "temporal.csv").open()))
        assert windows[-1]["sample_count"] == "1"
        assert len(state.calls) == 3 and state.closed == 1
    finally:
        finish(engine, qtbot)


def test_pending_result_cannot_complete_another_request(make_request):
    scheduler = LatestScheduler(); scheduler.activate("P01", "run1")
    scheduler.submit(make_request(number=0)); scheduler.take(block=False)
    scheduler.submit(make_request(number=1))
    assert not scheduler.complete("P01", 1, run_id="run1")
    assert scheduler.inflight == ("P01", "run1", 0)
    assert scheduler.complete("P01", 0, run_id="run1")


def test_export_receipt_rejects_changed_source(fixture_data):
    source = fixture_data.root / "source.bin"; source.write_bytes(b"synthetic-before")
    model = fixture_data.root / "mock.task"; model.touch()
    state = NS(initialized=0, closed=0, calls=[])
    settings = GeometryConfig(model, "D01", output_dir=fixture_data.root / "changed")
    session = FacialAnalysisSession(SourceConfig("S", "Synthetic", "file", str(source)), "R", settings,
                                   landmarker_factory=fake_landmarker(state, [None]))
    session.process(FramePacket("S", "R", 0, 0, np.zeros((2, 2, 3), np.uint8)))
    source.write_bytes(b"synthetic-after")
    with pytest.raises(ValueError, match="Sursa"):
        session.close("end_of_file")
    assert state.closed == 1 and not (settings.output_dir / "S" / "R" / "measurements.csv.experiment.json").exists()


def test_p2_development_freeze_validation_and_pipeline_guard(fixture_data, monkeypatch):
    from audience_analysis.calibration import CalibrationManager
    from audience_analysis.dashboard_data import DashboardSession
    from audience_analysis.experimental import FrozenExperiment
    from audience_analysis.validation import evaluate, read_measurements, read_blinks
    manager = CalibrationManager(["C01"]); manager.pose.calibrate(np.eye(4))
    profile = fixture_data.root / "C01.json"; manager.save(profile)
    model = fixture_data.root / "mock.task"; model.touch()
    state = NS(initialized=0, closed=0, calls=[])
    marker = fake_landmarker(state, [None])
    source_d = fixture_data.root / "D.bin"; source_d.write_bytes(b"synthetic-D")
    output = fixture_data.root / "protocol"
    development = FacialAnalysisSession(SourceConfig("D", "Synthetic", "file", str(source_d)), "RD",
                        GeometryConfig(model, "D01", calibration=manager.to_dict(), output_dir=output, data_kind="synthetic"),
                        landmarker_factory=marker)
    development.process(FramePacket("D", "RD", 0, 0, np.zeros((2, 2, 3), np.uint8)))
    development.close("end_of_file")
    dsession = DashboardSession.from_csv(output / "D" / "RD" / "measurements.csv", "D01")
    plan = FrozenExperiment.create(profile, [dsession], model)
    assert plan.payload["pipeline_parameters"]["pipeline"] == "p2_geometry_v1"
    source_v = fixture_data.root / "V.bin"; source_v.write_bytes(b"synthetic-V-independent-by-bytes-only")
    validation = FacialAnalysisSession(SourceConfig("V", "Synthetic", "file", str(source_v)), "RV",
                       GeometryConfig(model, "V01", role="validation", output_dir=output, frozen_plan=plan.document, data_kind="synthetic"),
                       landmarker_factory=marker)
    validation.process(FramePacket("V", "RV", 0, 0, np.zeros((2, 2, 3), np.uint8)))
    validation.close("end_of_file")
    csv_path = output / "V" / "RV" / "measurements.csv"
    receipt = json.loads(Path(str(csv_path) + ".experiment.json").read_text())
    config = plan.validation_config({"session_id": "V01", "experiment_id": "synthetic-only"})
    config.update(final_evaluation=True, processing_provenance=receipt)
    rows = read_measurements(csv_path)
    events = read_blinks(output / "V" / "RV" / "blinks.csv")
    report = evaluate(rows, config, detected_blinks=events)
    assert report["reference_pairs"] == 0 and report["head_pose"]["axes"]["yaw"]["mae"] is None
    receipt["pipeline_parameters"]["selected_track_id"] = 123
    with pytest.raises(ValueError, match="Pipeline"):
        evaluate(rows, config, detected_blinks=events)
    dsession.reproducibility["pipeline_parameters"]["selected_track_id"] = 123
    # Un plan P2 nu este executat accidental de VideoProcessor-ul separat.
    path = fixture_data.root / "frozen.json"; plan.save(path)
    import run_video_analysis
    with pytest.raises(SystemExit) as failure:
        run_video_analysis.main(["--source", str(source_v), "--model", str(model), "--session-id", "V01",
                                 "--frozen-plan", str(path), "--output-csv", str(fixture_data.root / "forbidden.csv"), "--no-display"])
    assert failure.value.code == 1
    assert state.initialized == state.closed == 2


def test_stop_during_model_initialization_does_not_open_capture(qtbot, fixture_data):
    model = fixture_data.root / "mock.task"; model.touch()
    entered, release = Event(), Event()
    state = NS(initialized=0, closed=0, calls=[])
    parent = fake_landmarker(state, [None])
    class Initializing(parent):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            entered.set()
            assert release.wait(5)
    settings = GeometryConfig(model, "D01", output_dir=fixture_data.root / "init-stop")
    engine = EngineController(SequenceConfig(), unavailable, demo=False,
                              reader_factory=lambda *_args, **_kwargs: pytest.fail("capture after stop"),
                              geometry_factory=lambda source, run: FacialAnalysisSession(source, run, settings, landmarker_factory=Initializing))
    outcomes = []
    engine.run_finished.connect(outcomes.append)
    try:
        engine.add_source(SourceConfig("S", "Synthetic", "file", "not-opened"))
        run = engine.start_source("S")
        qtbot.waitUntil(entered.is_set)
        engine.stop_source("S")
        release.set()
        qtbot.waitUntil(lambda: bool(outcomes), timeout=7000)
        assert outcomes[0]["stop_reason"] == "stopped" and outcomes[0]["error"] is None
        assert state.closed == 1 and state.calls == []
        summary = json.loads((settings.output_dir / "S" / run / "summary.json").read_text())
        assert summary["frames"] == 0 and summary["provenance_status"] == "not_written"
    finally:
        release.set()
        finish(engine, qtbot)


def test_completed_blinks_are_exported_as_automatic_events(qtbot, fixture_data):
    from audience_analysis.calibration import CalibrationManager
    from audience_analysis.validation import read_blinks
    source_path = video_file(fixture_data.root / "blink-signals.avi", frames=5)
    model = fixture_data.root / "mock.task"; model.touch()
    manager = CalibrationManager(["C01"])
    for side in ("left", "right"):
        manager.calibrate_ear(side, [.3] * 5, [.05] * 5)
    state = NS(initialized=0, closed=0, calls=[])
    opened, closed = fixture_data.face(), fixture_data.face(lid_height=5)
    marker = fake_landmarker(state, [opened, opened, closed, closed, opened])
    settings = GeometryConfig(model, "D01", calibration=manager.to_dict(), output_dir=fixture_data.root / "blinks")
    engine = EngineController(SequenceConfig(), unavailable, demo=False, realtime=False, detector_factory=FullFrameDetector,
                              geometry_factory=lambda source, run: FacialAnalysisSession(source, run, settings, landmarker_factory=marker))
    statuses = []; engine.status_changed.connect(lambda event: statuses.append(event.status))
    try:
        engine.add_source(SourceConfig("S", "Synthetic", "file", str(source_path)))
        run = engine.start_source("S")
        qtbot.waitUntil(lambda: Status.END_OF_SOURCE in statuses, timeout=10000)
        events = read_blinks(settings.output_dir / "S" / run / "blinks.csv")
        assert {(event.eye, event.start_ms, event.end_ms) for event in events} == {("left", 200, 400), ("right", 200, 400)}
        assert all(event.validation_status == "automatic_unvalidated" for event in events)
        assert len(state.calls) == 5 and state.closed == 1
    finally:
        finish(engine, qtbot)


@pytest.mark.parametrize("changes", [{"capture_epoch": -1}, {"capture_epoch": True}, {"timestamp_source": ""}])
def test_packet_timestamp_context_is_validated(changes):
    with pytest.raises(ValueError):
        FramePacket("S", "R", 0, 0, np.zeros((2, 2, 3), np.uint8), **changes)


def test_geometry_dto_rejects_mismatched_frame_and_has_no_model_levels():
    from audience_analysis.facial_features import FacialFeatureResult
    from audience_analysis.head_pose import HeadPoseEstimator
    from audience_analysis.eye_features import EyeFeaturesEstimator
    from audience_analysis.temporal_analysis import TemporalAnalyzer
    from audience_analysis.video_processor import measurement
    record = measurement(0, 0, False, HeadPoseEstimator().estimate(None), EyeFeaturesEstimator().estimate(None, (1, 1)), "synthetic", 1)
    temporal = TemporalAnalyzer().update(record)
    value = FacialFeatureResult("S", "R", 0, 0, None, 0, record, temporal, {}, "no_face")
    assert value.to_dict()["measurement"]["yaw"] is None and "levels" not in value.to_dict()
    assert not value.availability["head_pose_available"]
    with pytest.raises(ValueError): replace(value, frame_index=1)


def test_dashboard_breaks_graphs_and_variation_at_track_change():
    from audience_analysis.dashboard_data import segments, with_head_variation
    base = {"source_id": "S", "run_id": "R", "capture_epoch": "0", "head_pose_available": True,
            "face_detected": True, "pitch": 0, "roll": 0}
    rows = [{**base, "track_id": "0", "timestamp_ms": 0, "yaw": 0},
            {**base, "track_id": "0", "timestamp_ms": 100, "yaw": 1},
            {**base, "track_id": "1", "timestamp_ms": 200, "yaw": 30}]
    assert len(segments(rows, "yaw")) == 2
    assert with_head_variation(rows)[-1]["head_variation"] is None


def test_dashboard_refuses_unmapped_live_recording(monkeypatch):
    import cv2
    from audience_analysis.dashboard_data import VideoNavigator
    monkeypatch.setattr(cv2, "VideoCapture", lambda *_args: pytest.fail("unsafe live mapping opened a recording"))
    with pytest.raises(ValueError, match="live"):
        VideoNavigator("not-opened", [{"timestamp_ms": 0, "frame_index": 0, "timestamp_source": "webcam_monotonic"}])
