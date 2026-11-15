"""Ferestre temporale pe geometrie facială; fără inferență sau clasificare."""
from collections import deque
from dataclasses import dataclass
import json
import math
from typing import Any

import numpy as np


@dataclass(frozen=True)
class BlinkThresholds:
    close: float
    reopen: float

    def __post_init__(self):
        if not (math.isfinite(self.close) and math.isfinite(self.reopen) and 0 < self.close < self.reopen):
            raise ValueError("Pragurile EAR individuale cer 0 < close < reopen, valori finite.")


@dataclass(frozen=True)
class TemporalConfig:
    windows_s: tuple[float, ...] = (5, 10, 30)
    max_samples: int = 10000
    max_events: int = 1000
    max_gap_ms: int = 500
    min_blink_ms: int = 40
    max_blink_ms: int = 800
    min_rate_duration_ms: int = 10000
    left_blink: BlinkThresholds | None = None
    right_blink: BlinkThresholds | None = None
    head_stable_deg: float = 2.0
    head_change_deg: float = 10.0
    gaze_stable_distance: float = .02
    gaze_change_distance: float = .15
    smoothing: str = "none"
    smoothing_ms: float = 200
    head_deadband_deg: float = 0
    gaze_deadband: float = 0

    def __post_init__(self):
        if not self.windows_s or any(not math.isfinite(w) or w <= 0 for w in self.windows_s):
            raise ValueError("Ferestrele temporale trebuie să fie pozitive și finite.")
        for name in ("max_samples", "max_events", "max_gap_ms", "min_blink_ms", "max_blink_ms", "min_rate_duration_ms"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} trebuie să fie un întreg pozitiv.")
        if self.max_samples < 2 or self.max_blink_ms < self.min_blink_ms:
            raise ValueError("Capacitate minimă 2; max_blink_ms >= min_blink_ms.")
        if self.smoothing not in {"none", "moving_average", "ema"}:
            raise ValueError("smoothing: none, moving_average sau ema.")
        for name in ("head_stable_deg", "head_change_deg", "gaze_stable_distance", "gaze_change_distance",
                     "head_deadband_deg", "gaze_deadband", "smoothing_ms"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0 or (name == "smoothing_ms" and value == 0):
                raise ValueError(f"Parametru numeric invalid: {name}")
        if self.head_change_deg <= self.head_stable_deg or self.gaze_change_distance <= self.gaze_stable_distance:
            raise ValueError("Pragul de schimbare trebuie să depășească pragul de stabilitate.")

    @classmethod
    def from_dict(cls, data: dict) -> "TemporalConfig":
        try:
            data = dict(data)
            for side in ("left_blink", "right_blink"):
                if data.get(side) is not None:
                    data[side] = BlinkThresholds(**data[side])
            if "windows_s" in data:
                data["windows_s"] = tuple(data["windows_s"])
            return cls(**data)
        except TypeError as error:
            raise ValueError(f"Configurație temporală invalidă: {error}") from error


def _finite(value):
    try:
        return value is not None and math.isfinite(value)
    except (TypeError, ValueError):
        return False


@dataclass(frozen=True)
class TemporalSample:
    timestamp_ms: int
    head: tuple[float, float, float] | None = None  # yaw, pitch, roll
    left_ear: float | None = None
    right_ear: float | None = None
    left_iris: tuple[float, float] | None = None
    right_iris: tuple[float, float] | None = None

    @classmethod
    def from_measurement(cls, record) -> "TemporalSample":
        if not record.face_detected or record.error:
            return cls(record.timestamp_ms)
        def iris(side):
            return (getattr(record, side + "_iris_x"), getattr(record, side + "_iris_y")) if getattr(record, side + "_iris_available") else None
        return cls(record.timestamp_ms,
                   (record.yaw, record.pitch, record.roll) if record.head_pose_available and not record.head_pose_gimbal_lock else None,
                   record.left_ear if record.left_ear_available else None,
                   record.right_ear if record.right_ear_available else None, iris("left"), iris("right"))


@dataclass(frozen=True)
class BlinkEvent:
    eye: str
    start_ms: int
    end_ms: int
    duration_ms: int
    validation_status: str = "automatic_unvalidated"


@dataclass(frozen=True)
class TemporalUpdate:
    timestamp_ms: int
    windows: tuple[dict[str, Any], ...]
    new_blinks: tuple[BlinkEvent, ...]
    blink_totals: dict[str, int]
    filtered_head: tuple | None
    filtered_left_iris: tuple | None
    filtered_right_iris: tuple | None
    history_truncated: bool


def angular_delta(new, old):
    return (np.asarray(new) - np.asarray(old) + 180) % 360 - 180


def circular_mean(values):
    values = np.deg2rad(values)
    s, c = np.mean(np.sin(values), axis=0), np.mean(np.cos(values), axis=0)
    means = np.rad2deg(np.arctan2(s, c))
    resultant = np.hypot(s, c)
    return means, resultant


def _motion(rows, key, max_gap, stable, significant, angular=False):
    valid = [(t, values[key]) for t, values in rows if values[key] is not None]
    result = {"valid_samples": len(valid), "valid_duration_ms": 0, "mean": None, "variance": None,
              "mean_step": None, "max_step": None, "stable_intervals": [], "change_intervals": []}
    if valid:
        values = np.array([v for _, v in valid])
        if angular:
            mean, resultant = circular_mean(values)
            result["mean"] = [float(v) if r > 1e-8 else None for v, r in zip(mean, resultant)]
            result["variance"] = (1 - np.clip(resultant, 0, 1)).tolist()  # circulară, adimensională
        else:
            result["mean"] = values.mean(axis=0).tolist()
            result["variance"] = values.var(axis=0).tolist()
    steps = []
    for (t0, v0), (t1, v1) in zip(rows, rows[1:]):
        if v0[key] is None or v1[key] is None or t1 - t0 > max_gap:
            continue
        delta = angular_delta(v1[key], v0[key]) if angular else np.asarray(v1[key]) - v0[key]
        distance = float(np.linalg.norm(delta))
        steps.append(distance)
        result["valid_duration_ms"] += t1 - t0
        for name, active in (("stable_intervals", distance <= stable), ("change_intervals", distance >= significant)):
            if active:
                intervals = result[name]
                if intervals and intervals[-1]["end_ms"] == t0:
                    intervals[-1]["end_ms"] = t1
                    intervals[-1]["duration_ms"] += t1 - t0
                else:
                    intervals.append({"start_ms": t0, "end_ms": t1, "duration_ms": t1 - t0})
    if steps:
        result["mean_step"], result["max_step"] = float(np.mean(steps)), max(steps)
    for name in ("stable", "change"):
        result[name + "_count"] = len(result[name + "_intervals"])
        result[name + "_duration_ms"] = sum(item["duration_ms"] for item in result[name + "_intervals"])
    return result


class TemporalAnalyzer:
    def __init__(self, config: TemporalConfig | None = None):
        self.config = config or TemporalConfig()
        self._history = deque(maxlen=self.config.max_samples)
        self._events = deque(maxlen=self.config.max_events)
        self._blink_state = {side: {"open": False, "start": None, "last": None} for side in ("left", "right")}
        self._channels = {}
        self._last_timestamp = None
        self._last_evicted = None
        self._last_evicted_event = None
        self._totals = {"left": 0, "right": 0}

    def _filter(self, key, value, timestamp, angular, deadband):
        if value is None:
            self._channels.pop(key, None)
            return None
        config = self.config
        if config.smoothing == "none" and deadband == 0:
            return tuple(value)
        previous = self._channels.get(key)
        if previous is None or timestamp - previous[0] > config.max_gap_ms:
            previous = (timestamp, np.array(value), deque(maxlen=config.max_samples))
        last_t, last_value, history = previous
        history.append((timestamp, value))
        while history and history[0][0] < timestamp - config.smoothing_ms:
            history.popleft()
        current = np.array(value)
        if config.smoothing == "moving_average":
            values = [item[1] for item in history]
            if angular:
                current, resultant = circular_mean(values)
                if (resultant < 1e-8).any():
                    self._channels.pop(key, None)
                    return None
            else:
                current = np.mean(values, axis=0)
        elif config.smoothing == "ema":
            alpha = 1 - math.exp(-(timestamp - last_t) / config.smoothing_ms)
            delta = angular_delta(current, last_value) if angular else current - last_value
            current = last_value + alpha * delta
        delta = angular_delta(current, last_value) if angular else current - last_value
        if np.linalg.norm(delta) <= deadband:
            current = last_value
        if angular:
            current = (current + 180) % 360 - 180
        self._channels[key] = (timestamp, current, history)
        return tuple(map(float, current))

    def _blink(self, side, ear, timestamp):
        thresholds = getattr(self.config, side + "_blink")
        state = self._blink_state[side]
        if thresholds is None or ear is None:
            state.update(open=False, start=None, last=None)
            return None
        if state["last"] is not None and timestamp - state["last"] > self.config.max_gap_ms:
            state.update(open=False, start=None)
        state["last"] = timestamp
        if state["start"] is not None:
            if ear >= thresholds.reopen:
                start = state["start"]
                state.update(open=True, start=None)
                if self.config.min_blink_ms <= timestamp - start <= self.config.max_blink_ms:
                    return BlinkEvent(side, start, timestamp, timestamp - start)
        elif state["open"] and ear <= thresholds.close:
            state["start"] = timestamp
            state["open"] = False
        elif ear >= thresholds.reopen:
            state["open"] = True
        return None

    def update(self, measurement) -> TemporalUpdate:
        sample = measurement if isinstance(measurement, TemporalSample) else TemporalSample.from_measurement(measurement)
        t = sample.timestamp_ms
        if type(t) is not int or t < 0 or (self._last_timestamp is not None and t <= self._last_timestamp):
            raise ValueError("Temporal Analyzer necesită timestampuri întregi strict crescătoare, nenegative.")
        raw = {}
        for key, length in (("head", 3), ("left_iris", 2), ("right_iris", 2)):
            value = getattr(sample, key)
            try:
                raw[key] = tuple(value) if value is not None and len(value) == length and all(_finite(v) for v in value) else None
            except TypeError:
                raw[key] = None
        for side in ("left", "right"):
            ear = getattr(sample, side + "_ear")
            raw[side + "_ear"] = ear if _finite(ear) and ear >= 0 else None
        filtered = dict(raw)
        filtered["head"] = self._filter("head", raw["head"], t, True, self.config.head_deadband_deg)
        for side in ("left", "right"):
            key = side + "_iris"
            filtered[key] = self._filter(key, raw[key], t, False, self.config.gaze_deadband)
        new_events = []
        for side in ("left", "right"):
            event = self._blink(side, raw[side + "_ear"], t)
            if event:
                if len(self._events) == self._events.maxlen:
                    self._last_evicted_event = self._events[0].end_ms
                self._events.append(event)
                self._totals[side] += 1
                new_events.append(event)
        if len(self._history) == self._history.maxlen:
            self._last_evicted = self._history[0][0]
        self._history.append((t, filtered))
        cutoff = t - max(self.config.windows_s) * 1000
        while self._history and self._history[0][0] < cutoff:
            self._history.popleft()
        while self._events and self._events[0].end_ms < cutoff:
            self._events.popleft()
        self._last_timestamp = t
        windows = tuple(self._window(t, duration) for duration in self.config.windows_s)
        return TemporalUpdate(t, windows, tuple(new_events), dict(self._totals), filtered["head"],
                              filtered["left_iris"], filtered["right_iris"], any(w["history_truncated"] for w in windows))

    def _window(self, end, duration):
        start = end - duration * 1000
        rows = [(t, row) for t, row in self._history if t >= start]
        truncated = self._last_evicted is not None and self._last_evicted >= start
        config = self.config
        result = {"timestamp_ms": end, "window_s": duration, "sample_count": len(rows),
                  "observed_span_ms": rows[-1][0] - rows[0][0] if rows else 0,
                  "history_truncated": truncated,
                  "head": _motion(rows, "head", config.max_gap_ms, config.head_stable_deg, config.head_change_deg, True)}
        for side in ("left", "right"):
            result[side + "_gaze"] = _motion(rows, side + "_iris", config.max_gap_ms, config.gaze_stable_distance, config.gaze_change_distance)
            valid_duration = sum(t1 - t0 for (t0, a), (t1, b) in zip(rows, rows[1:])
                                 if a[side + "_ear"] is not None and b[side + "_ear"] is not None and t1 - t0 <= config.max_gap_ms)
            events = [event for event in self._events if event.eye == side and event.start_ms >= start and event.end_ms <= end]
            enabled = getattr(config, side + "_blink") is not None
            thresholds = getattr(config, side + "_blink")
            events_truncated = self._last_evicted_event is not None and self._last_evicted_event >= start
            result[side + "_blink"] = {"enabled": enabled, "count": len(events) if enabled else None,
                "close_threshold": thresholds.close if thresholds else None,
                "reopen_threshold": thresholds.reopen if thresholds else None,
                "valid_duration_ms": valid_duration,
                "rate_per_min": len(events) * 60000 / valid_duration if enabled and not truncated and not events_truncated and valid_duration >= config.min_rate_duration_ms else None,
                "last_duration_ms": events[-1].duration_ms if events else None,
                "events_truncated": events_truncated}
        return result


def temporal_csv_row(update: TemporalUpdate, window: dict) -> dict:
    row = {key: window[key] for key in ("timestamp_ms", "window_s", "sample_count", "observed_span_ms", "history_truncated")}
    for key in ("head", "left_gaze", "right_gaze", "left_blink", "right_blink"):
        row[key + "_json"] = json.dumps(window[key], ensure_ascii=False, allow_nan=False)
    for key in ("filtered_head", "filtered_left_iris", "filtered_right_iris"):
        value = getattr(update, key)
        row[key + "_json"] = json.dumps(value, allow_nan=False) if value is not None else None
    return row


def compare_blinks(detected: list[BlinkEvent], reference: list[BlinkEvent], *, tolerance_ms: int = 100) -> dict:
    """Potrivire unu-la-unu cu referință manuală explicită, pe ochi/start/end.

    Maximum de potriviri prin augmentare bipartită, cu preferință locală pentru
    eroarea temporală mică. Nu modifică statusul evenimentelor exportate.
    """
    if type(tolerance_ms) is not int or tolerance_ms < 0:
        raise ValueError("Toleranța trebuie să fie un întreg nenegativ.")
    for event in (*detected, *reference):
        if event.eye not in {"left", "right"} or not 0 <= event.start_ms < event.end_ms:
            raise ValueError("Eveniment invalid în comparația cu referința.")
    candidates = []
    for event in detected:
        matches = [i for i, ref in enumerate(reference) if event.eye == ref.eye
                   and abs(event.start_ms - ref.start_ms) <= tolerance_ms
                   and abs(event.end_ms - ref.end_ms) <= tolerance_ms]
        candidates.append(sorted(matches, key=lambda i: abs(event.start_ms - reference[i].start_ms) + abs(event.end_ms - reference[i].end_ms)))
    owners = {}
    def assign(index, seen):
        for target in candidates[index]:
            if target not in seen:
                seen.add(target)
                if target not in owners or assign(owners[target], seen):
                    owners[target] = index
                    return True
        return False
    for i in range(len(detected)):
        assign(i, set())
    matched = len(owners)
    return {"matched_reference": matched, "unmatched_detections": len(detected) - matched,
            "unmatched_reference": len(reference) - matched,
            "precision": matched / len(detected) if detected else None,
            "recall": matched / len(reference) if reference else None,
            "matches": [{"detected_index": index, "reference_index": target,
                         "start_error_ms": detected[index].start_ms - reference[target].start_ms,
                         "end_error_ms": detected[index].end_ms - reference[target].end_ms}
                        for target, index in sorted(owners.items())], "tolerance_ms": tolerance_ms}
