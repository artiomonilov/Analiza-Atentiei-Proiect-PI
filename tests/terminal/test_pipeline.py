import json
from pathlib import Path

import pytest

from audience_analysis.engagement import UnavailableEngagementPredictor
from audience_analysis.model_stats import FrameStatistics
from audience_analysis.pipeline import AnalysisResult, FrameResult, export_reports
from audience_analysis.vision import AttentionEstimate


def test_unknown_attention_is_excluded_from_toward_denominator():
    result = AnalysisResult(Path("video.mp4"), "video", 3, 2, 10, 10, frames=[
        FrameResult(0, 1, "detected", AttentionEstimate("toward_screen")),
        FrameResult(1, 1, "detected", AttentionEstimate("away_from_screen")),
        FrameResult(2, 0, "no_face", AttentionEstimate("unknown")),
    ])
    summary = result.summary()
    assert summary["attention_coverage_pct"] == pytest.approx(2 / 3 * 100)
    assert summary["toward_screen_pct_valid"] == 50
    assert not UnavailableEngagementPredictor().predict_clip([]).available


def test_exports_json_and_csv_without_images(tmp_path):
    emotion = FrameStatistics("Neutral", 0.7, {"Neutral": 0.7, "Happiness": 0.3})
    result = AnalysisResult(Path("frame.png"), "image", None, None, 10, 10, frames=[
        FrameResult(0, 1, "detected", AttentionEstimate("unknown"), emotion),
    ])
    export_reports(result, tmp_path)
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))["sampled_frames"] == 1
    assert "Neutral" in (tmp_path / "frames.csv").read_text(encoding="utf-8")
    assert (tmp_path / "windows.csv").is_file()
    assert (tmp_path / "errors.log").is_file()
