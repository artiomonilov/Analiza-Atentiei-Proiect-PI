from dataclasses import replace

import numpy as np
import pytest

from audience_analysis.temporal_analysis import BlinkThresholds, TemporalAnalyzer, TemporalConfig, TemporalSample


def config(**kwargs):
    return TemporalConfig(left_blink=BlinkThresholds(.15, .22), right_blink=BlinkThresholds(.12, .20), **kwargs)


def sample(t, ear=.3, head=(0, 0, 0), iris=(.5, .5)):
    return TemporalSample(t, head, ear, ear, iris, iris)


def test_irregular_timestamps_and_valid_durations():
    analyzer = TemporalAnalyzer(config(windows_s=(.5, 1), max_gap_ms=300))
    for t in (0, 100, 350, 900):
        result = analyzer.update(sample(t))
    short, long = result.windows
    assert short["sample_count"] == 1
    assert long["head"]["valid_duration_ms"] == 350
    assert long["head"]["stable_duration_ms"] == 350
    assert long["head"]["stable_count"] == 1
    assert long["head"]["mean"] == pytest.approx([0, 0, 0])


def test_blink_hysteresis_and_known_duration():
    analyzer = TemporalAnalyzer(config(min_rate_duration_ms=500))
    events = []
    for t, ear in [(0, .3), (100, .1), (150, .18), (200, .21), (250, .25), (600, .3)]:
        result = analyzer.update(sample(t, ear=ear))
        events.extend(result.new_blinks)
    left = [event for event in events if event.eye == "left"]
    assert len(left) == 1
    assert (left[0].start_ms, left[0].end_ms, left[0].duration_ms) == (100, 250, 150)
    assert left[0].validation_status == "automatic_unvalidated"
    stats = result.windows[0]["left_blink"]
    assert stats["count"] == 1
    assert stats["valid_duration_ms"] == 600
    assert stats["rate_per_min"] == pytest.approx(100)


def test_multiple_blinks_and_individual_thresholds():
    analyzer = TemporalAnalyzer(config())
    events = []
    for t, ear in [(0, .3), (100, .14), (200, .3), (300, .14), (450, .3)]:
        events += list(analyzer.update(sample(t, ear=ear)).new_blinks)
    assert [event.duration_ms for event in events if event.eye == "left"] == [100, 150]
    assert not [event for event in events if event.eye == "right"]


@pytest.mark.parametrize("middle", [TemporalSample(150), sample(900, ear=.1)])
def test_missing_landmarks_or_gap_break_blink(middle):
    analyzer = TemporalAnalyzer(config())
    analyzer.update(sample(0))
    analyzer.update(sample(100, ear=.1))
    analyzer.update(middle)
    result = analyzer.update(sample(middle.timestamp_ms + 100))
    assert result.blink_totals == {"left": 0, "right": 0}


def test_initial_closed_and_unfinished_events_not_counted():
    analyzer = TemporalAnalyzer(config())
    analyzer.update(sample(0, ear=.1))
    analyzer.update(sample(100, ear=.3))
    result = analyzer.update(sample(200, ear=.1))
    assert not result.new_blinks and result.windows[0]["left_blink"]["count"] == 0


@pytest.mark.parametrize("duration", [10, 1000])
def test_duration_limits_reject_non_blink_closures(duration):
    analyzer = TemporalAnalyzer(config(max_gap_ms=2000))
    analyzer.update(sample(0))
    analyzer.update(sample(100, ear=.1))
    assert not analyzer.update(sample(100 + duration)).new_blinks


def test_no_universal_threshold_and_rate_requires_long_enough_data():
    analyzer = TemporalAnalyzer()
    analyzer.update(sample(0))
    analyzer.update(sample(100, ear=.1))
    result = analyzer.update(sample(200))
    assert result.windows[0]["left_blink"]["count"] is None
    assert result.windows[0]["left_blink"]["rate_per_min"] is None
    enabled = TemporalAnalyzer(config())
    enabled.update(sample(0))
    assert enabled.update(sample(200)).windows[0]["left_blink"]["rate_per_min"] is None


def test_angular_wrap_and_circular_variance():
    analyzer = TemporalAnalyzer()
    analyzer.update(sample(0, head=(0, 0, 179)))
    result = analyzer.update(sample(100, head=(0, 0, -179)))
    stats = result.windows[0]["head"]
    assert abs(stats["mean"][2]) == pytest.approx(180)
    assert stats["max_step"] == pytest.approx(2)
    assert stats["variance"][2] < .001
    assert stats["stable_duration_ms"] == 100


def test_significant_movements_grouped_into_intervals():
    analyzer = TemporalAnalyzer(config())
    for t, yaw in ((0, 0), (100, 15), (250, 30), (350, 30)):
        result = analyzer.update(sample(t, head=(yaw, 0, 0)))
    stats = result.windows[0]["head"]
    assert stats["change_count"] == 1 and stats["change_duration_ms"] == 250
    assert stats["stable_duration_ms"] == 100


def test_iris_variance_stable_and_change_intervals():
    analyzer = TemporalAnalyzer()
    for t, iris in [(0, (.5, .5)), (100, (.51, .5)), (200, (.8, .5))]:
        result = analyzer.update(sample(t, iris=iris))
    stats = result.windows[0]["left_gaze"]
    assert stats["mean"] == pytest.approx([(.5 + .51 + .8) / 3, .5])
    assert stats["variance"] == pytest.approx(np.var([[.5, .5], [.51, .5], [.8, .5]], axis=0))
    assert stats["stable_duration_ms"] == 100 and stats["change_duration_ms"] == 100


def test_missing_measurements_are_not_interpolated():
    analyzer = TemporalAnalyzer()
    analyzer.update(sample(0))
    analyzer.update(TemporalSample(100))
    result = analyzer.update(sample(200))
    assert result.windows[0]["head"]["valid_duration_ms"] == 0
    assert result.windows[0]["left_gaze"]["stable_duration_ms"] == 0


def test_empty_values_return_null_statistics_not_zeros():
    result = TemporalAnalyzer().update(TemporalSample(0))
    assert result.windows[0]["head"]["mean"] is None
    assert result.windows[0]["left_gaze"]["variance"] is None
    assert result.filtered_head is None


def test_bounded_history_and_events():
    analyzer = TemporalAnalyzer(config(max_samples=3, max_events=1))
    for t, ear in [(0, .3), (100, .1), (200, .3), (300, .1), (400, .3)]:
        result = analyzer.update(sample(t, ear=ear))
    assert len(analyzer._history) == 3 and len(analyzer._events) == 1
    assert result.history_truncated
    assert result.windows[0]["left_blink"]["events_truncated"]
    assert result.windows[0]["left_blink"]["rate_per_min"] is None


@pytest.mark.parametrize("smoothing", ["ema", "moving_average"])
def test_smoothing_is_circular_and_resets_after_missing(smoothing):
    analyzer = TemporalAnalyzer(config(smoothing=smoothing))
    analyzer.update(sample(0, head=(0, 0, 179)))
    result = analyzer.update(sample(100, head=(0, 0, -179)))
    assert abs(result.filtered_head[2]) > 178
    analyzer.update(TemporalSample(200))
    assert analyzer.update(sample(300, head=(10, 0, 0))).filtered_head == pytest.approx((10, 0, 0))


def test_smoothing_does_not_suppress_fast_raw_blink():
    analyzer = TemporalAnalyzer(config(smoothing="ema", smoothing_ms=10000))
    analyzer.update(sample(0))
    analyzer.update(sample(100, ear=.1))
    assert len(analyzer.update(sample(150)).new_blinks) == 2


def test_invalid_timestamp_does_not_mutate_state():
    analyzer = TemporalAnalyzer()
    analyzer.update(sample(10))
    for t in (-1, 10, 9, 10.5):
        with pytest.raises(ValueError): analyzer.update(sample(t))
    assert len(analyzer._history) == 1


def test_configuration_validation_and_json_mapping():
    cfg = TemporalConfig.from_dict({"windows_s": [2, 5], "left_blink": {"close": .1, "reopen": .2}})
    assert cfg.windows_s == (2, 5) and cfg.left_blink.close == .1
    with pytest.raises(ValueError): BlinkThresholds(.3, .1)
    with pytest.raises(ValueError): TemporalConfig(max_samples=1)
    with pytest.raises(ValueError): TemporalConfig(windows_s=(0,))


def test_deadband_keeps_raw_sample_accessible():
    analyzer = TemporalAnalyzer(config(head_deadband_deg=1))
    analyzer.update(sample(0))
    raw = sample(100, head=(.5, 0, 0))
    assert analyzer.update(raw).filtered_head == pytest.approx((0, 0, 0))
    assert raw.head == (.5, 0, 0)


def test_expired_window_samples_and_events_are_removed():
    analyzer = TemporalAnalyzer(config(windows_s=(1,)))
    analyzer.update(sample(0))
    analyzer.update(sample(100, ear=.1))
    analyzer.update(sample(200))
    result = analyzer.update(sample(2000))
    assert result.windows[0]["sample_count"] == 1
    assert result.windows[0]["left_blink"]["count"] == 0
    assert len(analyzer._events) == 0


def test_enabled_blink_counter_without_any_ear_is_unavailable_not_zero():
    analyzer = TemporalAnalyzer(config())
    analyzer.update(TemporalSample(0))
    result = analyzer.update(TemporalSample(200))
    left = result.windows[0]["left_blink"]
    assert left["enabled"] and left["count"] is None and left["observed_ear_samples"] == 0
    assert left["rate_per_min"] is None
    assert analyzer.update(sample(300)).windows[0]["left_blink"]["count"] == 0


def test_reference_matching_distinguishes_automatic_and_manual():
    from audience_analysis.temporal_analysis import BlinkEvent, compare_blinks
    automatic = [BlinkEvent("left", 100, 250, 150), BlinkEvent("left", 110, 260, 150)]
    manual = [BlinkEvent("left", 105, 255, 150), BlinkEvent("right", 100, 250, 150)]
    result = compare_blinks(automatic, manual, tolerance_ms=20)
    assert result["matched_reference"] == 1
    assert result["unmatched_detections"] == 1 and result["unmatched_reference"] == 1
    assert result["precision"] == result["recall"] == .5
    assert automatic[0].validation_status == "automatic_unvalidated"


def test_no_reference_produces_null_recall():
    from audience_analysis.temporal_analysis import compare_blinks
    assert compare_blinks([], [])["recall"] is None


def test_invalid_numeric_values_are_unavailable():
    analyzer = TemporalAnalyzer(config())
    result = analyzer.update(TemporalSample(0, (float("nan"), 0, 0), float("nan"), -1, .5, (float("inf"), .5)))
    assert result.filtered_head is None and result.filtered_left_iris is None
    assert result.filtered_right_iris is None
    assert result.windows[0]["left_blink"]["valid_duration_ms"] == 0


def test_unknown_ear_excluded_from_rate_duration():
    analyzer = TemporalAnalyzer(config(min_rate_duration_ms=100))
    analyzer.update(sample(0))
    analyzer.update(sample(100))
    analyzer.update(TemporalSample(200))
    analyzer.update(sample(300))
    result = analyzer.update(sample(400))
    assert result.windows[0]["left_blink"]["valid_duration_ms"] == 200
    assert result.windows[0]["left_blink"]["rate_per_min"] == 0
