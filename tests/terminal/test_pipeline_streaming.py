import csv
import json
import tracemalloc
from types import SimpleNamespace

import numpy as np
import pytest

from audience_analysis.pipeline import FrameResult, analyse_video, export_reports
from audience_analysis.vision import AttentionEstimate


def capture_backend(monkeypatch, n):
    cv2 = pytest.importorskip("cv2")
    state = {"position": 0, "released": False}
    frame = np.zeros((2, 2, 3), np.uint8)
    class Capture:
        def isOpened(self): return True
        def get(self, key):
            return {cv2.CAP_PROP_FPS: 10, cv2.CAP_PROP_FRAME_COUNT: n, cv2.CAP_PROP_FRAME_WIDTH: 2,
                    cv2.CAP_PROP_FRAME_HEIGHT: 2, cv2.CAP_PROP_POS_MSEC: max(0, state["position"] - 1) * 100}.get(key, 0)
        def read(self):
            if state["position"] >= n: return False, None
            state["position"] += 1
            return True, frame
        def release(self): state["released"] = True
    monkeypatch.setattr(cv2, "VideoCapture", lambda _: Capture())
    return state


def test_large_streaming_export_has_bounded_memory_and_complete_counts(monkeypatch, tmp_path):
    def process(_, t):
        if round(t * 10) % 17 == 0: raise OSError("C:/Users/PRIVATE_PERSON/authorized/video.mp4")
        return FrameResult(t, 0, "no_face", AttentionEstimate("unknown"))
    pipeline = SimpleNamespace(analyse_frame=process)
    peaks = []
    for count in (4000, 40000):
        state = capture_backend(monkeypatch, count)
        output = tmp_path / str(count)
        tracemalloc.start()
        result = analyse_video(tmp_path / "authorized.avi", pipeline, .05, report_dir=output, retain_frames=False)
        peaks.append(tracemalloc.get_traced_memory()[1]); tracemalloc.stop()
        assert state["released"] and result.frames == [] and len(result.errors) <= 100
        assert result.summary()["sampled_frames"] == count
        assert result.summary()["errors"] == len(range(0, count, 17))
        with (output / "frames.csv").open(encoding="utf-8", newline="") as handle:
            assert sum(1 for _ in csv.DictReader(handle)) == count
        with (output / "windows.csv").open(encoding="utf-8", newline="") as handle:
            assert sum(int(r["sampled_frames"]) for r in csv.DictReader(handle)) == count
        assert "PRIVATE_PERSON" not in (output / "errors.log").read_text(encoding="utf-8")
        assert json.loads((output / "summary.json").read_text(encoding="utf-8"))["source"] == "local-input"
        export_reports(result, output)
    assert peaks[1] < peaks[0] + 1_000_000  # 10× frames must not retain an O(N) result history


def test_interrupt_keeps_partial_reports_and_releases_capture(monkeypatch, tmp_path):
    state = capture_backend(monkeypatch, 100)
    calls = []
    def process(_, t):
        calls.append(t)
        if len(calls) == 12: raise KeyboardInterrupt
        return FrameResult(t, 0, "no_face", AttentionEstimate("unknown"))
    output = tmp_path / "partial"
    result = analyse_video(tmp_path / "authorized.avi", SimpleNamespace(analyse_frame=process), .05, report_dir=output, retain_frames=False)
    assert result.interrupted and state["released"] and result.summary()["sampled_frames"] == 11
    assert json.loads((output / "summary.json").read_text(encoding="utf-8"))["interrupted"] is True
    assert len((output / "frames.csv").read_text(encoding="utf-8").splitlines()) == 12


def test_streaming_refuses_overwriting_and_requires_export_during_run(monkeypatch, tmp_path):
    state = capture_backend(monkeypatch, 1)
    pipeline = SimpleNamespace(analyse_frame=lambda _, t: FrameResult(t, 0, "no_face", AttentionEstimate("unknown")))
    with pytest.raises(FileExistsError): analyse_video(tmp_path / "a", pipeline, report_dir=tmp_path, retain_frames=False)
    assert state["released"]
    state = capture_backend(monkeypatch, 1)
    result = analyse_video(tmp_path / "a", pipeline, retain_frames=False)
    with pytest.raises(ValueError): export_reports(result, tmp_path / "late")


def test_expression_loader_pins_revision_and_defaults_to_local_cache(monkeypatch):
    import sys
    from audience_analysis import model_stats
    calls = []
    model = SimpleNamespace(config=SimpleNamespace(id2label=dict(enumerate(sorted(model_stats.EXPECTED_LABELS)))))
    model.to = lambda _: model; model.eval = lambda: model
    def processor_load(*args, **kwargs): calls.append(kwargs); return object()
    def model_load(*args, **kwargs): calls.append(kwargs); return model
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(device=lambda x: x, cuda=SimpleNamespace(is_available=lambda: False)))
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(AutoImageProcessor=SimpleNamespace(from_pretrained=processor_load),
        AutoModelForImageClassification=SimpleNamespace(from_pretrained=model_load)))
    instance = model_stats.EmotionStatisticsModel()
    assert instance.revision == model_stats.MODEL_REVISION
    assert all(c == {"revision": model_stats.MODEL_REVISION, "local_files_only": True} for c in calls)
    calls.clear()
    model_stats.EmotionStatisticsModel(allow_download=True)
    assert all(c["local_files_only"] is False for c in calls)
