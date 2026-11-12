from pathlib import Path
import sys

import pytest

from audience_analysis.model_stats import FrameStatistics
from audience_analysis.terminal import process_source, terminal_main


class FakeCapture:
    def __init__(self, frames, *, opened=True):
        self.frames = iter(frames)
        self.opened = opened
        self.released = False

    def isOpened(self):
        return self.opened

    def get(self, _property):
        return 3

    def read(self):
        try:
            return True, next(self.frames)
        except StopIteration:
            return False, None

    def release(self):
        self.released = True


def test_video_progress_and_completion(monkeypatch, tmp_path):
    capture = FakeCapture([object(), object(), object()])

    class CV2:
        CAP_PROP_FRAME_COUNT = 7

        @staticmethod
        def VideoCapture(_path):
            return capture

    monkeypatch.setitem(sys.modules, "cv2", CV2)
    source = tmp_path / "clip.mp4"
    source.touch()
    updates = []
    report = process_source(source, lambda *update: updates.append(update))
    assert capture.released
    assert report.kind == "videoclip"
    assert report.frames_read == 3
    assert updates[0] == (0, 0, 3)
    assert updates[-1] == (100, 3, 3)


def test_one_image_is_one_completed_frame(monkeypatch, tmp_path):
    class CV2:
        IMREAD_UNCHANGED = -1

        @staticmethod
        def imread(_path, _mode):
            return object()

    monkeypatch.setitem(sys.modules, "cv2", CV2)
    source = tmp_path / "frame.png"
    source.touch()
    updates = []
    report = process_source(source, lambda *update: updates.append(update))
    assert report.kind == "imagine"
    assert report.frames_read == 1
    assert updates == [(0, 0, 1), (100, 1, 1)]


def test_model_statistics_are_aggregated_for_processed_frames(monkeypatch, tmp_path):
    class CV2:
        IMREAD_UNCHANGED = -1

        @staticmethod
        def imread(_path, _mode):
            return object()

    monkeypatch.setitem(sys.modules, "cv2", CV2)
    source = tmp_path / "frame.png"
    source.touch()
    prediction = FrameStatistics("Neutral", 0.75, {"Happiness": 0.25, "Neutral": 0.75})
    report = process_source(source, lambda *_: None, lambda _frame: prediction)
    assert report.frames_with_statistics == 1
    assert report.most_frequent_label == "Neutral"
    assert report.mean_probabilities == prediction.probabilities


def test_terminal_reports_missing_file(capsys, tmp_path):
    with pytest.raises(ValueError, match="nu există"):
        terminal_main(tmp_path / "absent.png")
    assert "Sursă primită" in capsys.readouterr().out
