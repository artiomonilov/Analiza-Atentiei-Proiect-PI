"""Evaluare offline pe CSV: referințele lipsă nu sunt inventate."""
from bisect import bisect_left, bisect_right
import csv
import json
import math
from pathlib import Path

import numpy as np

from .temporal_analysis import BlinkEvent, angular_delta, circular_mean, compare_blinks


CONVENTION = "camera_xyz_rzryrx_deg"
NUMERIC = {"yaw", "pitch", "roll", "processing_fps", "left_ear", "right_ear",
           "left_iris_x", "left_iris_y", "right_iris_x", "right_iris_y",
           "left_ear_relative", "right_ear_relative", "left_gaze_dx", "left_gaze_dy", "right_gaze_dx", "right_gaze_dy"}
BOOLEAN = {"face_detected", "head_pose_available", "head_pose_calibrated", "head_pose_gimbal_lock",
           "left_ear_available", "right_ear_available", "left_iris_available", "right_iris_available"}


def canonical_measurements(rows):
    """Aceeași reprezentare pentru CSV, snapshot și API; păstrează coloanele extra."""
    rows = list(rows)
    fields = set().union(*(r.keys() for r in rows)) if rows else set()
    result = []
    for raw in rows:
        row = {k: None if isinstance(raw.get(k), str) and raw[k] == "" else raw.get(k) for k in fields}
        for key in NUMERIC:
            value = row.get(key)
            if isinstance(value, bool): raise ValueError(f"Număr invalid: {key}")
            row[key] = float(value) if value not in (None, "") else None
            if row[key] is not None and not math.isfinite(row[key]): raise ValueError(f"Număr nefinita: {key}")
        for key in BOOLEAN:
            value = row.get(key)
            if value not in (None, "", True, False, "True", "False", "true", "false", "1", "0"):
                raise ValueError(f"Flag invalid: {key}")
            row[key] = None if value in (None, "") else value in (True, "True", "true", "1")
        for key in ("timestamp_ms", "frame_index"):
            value = row.get(key)
            if key == "frame_index" and value in (None, ""):
                row[key] = None
                continue
            if isinstance(value, bool) or not isinstance(value, (int, str)):
                raise ValueError(f"Întreg invalid: {key}")
            row[key] = int(value)
            if row[key] < 0: raise ValueError(f"Întreg negativ: {key}")
        result.append(row)
    return result


def read_measurements(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "timestamp_ms" not in reader.fieldnames:
            raise ValueError("CSV-ul necesită timestamp_ms.")
        rows, previous = [], -1
        for raw in reader:
            row = dict(raw)
            try:
                t = int(row["timestamp_ms"])
                if t < 0 or t <= previous:
                    raise ValueError("Timestampuri negative, duplicate sau descrescătoare.")
                previous, row["timestamp_ms"] = t, t
                for key in NUMERIC:
                    value = row.get(key)
                    row[key] = float(value) if value not in (None, "") else None
                    if row[key] is not None and not math.isfinite(row[key]):
                        raise ValueError(f"Valoare nefinita în {key}.")
                for key in BOOLEAN:
                    value = row.get(key)
                    if value not in (None, "", "True", "False", "true", "false", "1", "0"):
                        raise ValueError(f"Flag invalid în {key}.")
                    row[key] = None if value in (None, "") else value in ("True", "true", "1")
            except (TypeError, KeyError) as error:
                raise ValueError("Rând CSV incomplet.") from error
            rows.append(row)
    return rows


def read_blinks(path: Path) -> list[BlinkEvent]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"eye", "start_ms", "end_ms"} <= set(reader.fieldnames):
            raise ValueError("Marcajele necesită eye,start_ms,end_ms.")
        result = []
        for row in reader:
            try:
                start, end = int(row["start_ms"]), int(row["end_ms"])
                if row["eye"] not in {"left", "right"} or not 0 <= start < end:
                    raise ValueError("Marcaj de clipire invalid.")
                event = BlinkEvent(row["eye"], start, end, end - start)
                if event in result:
                    raise ValueError("Marcaj de clipire duplicat.")
                result.append(event)
            except (TypeError, KeyError) as error:
                raise ValueError("Marcaj de clipire incomplet.") from error
    return result


def valid(row, component):
    if row.get("face_detected") is False or row.get("error"):
        return False
    if component == "head":
        return row.get("head_pose_available") is not False and not row.get("head_pose_gimbal_lock") and all(is_number(row.get(k)) for k in ("yaw", "pitch", "roll"))
    if component.endswith("_iris"):
        return row.get(component + "_available") is not False and all(is_number(row.get(component + suffix)) and 0 <= row[component + suffix] <= 1 for suffix in ("_x", "_y"))
    return row.get(component + "_available") is not False and is_number(row.get(component)) and row[component] >= 0


def is_number(value):
    try:
        return value is not None and math.isfinite(value)
    except (TypeError, ValueError):
        return False


def data_quality(rows, max_gap_ms=500):
    components = ("head", "left_ear", "right_ear", "left_iris", "right_iris")
    gaps = [{"start_ms": a["timestamp_ms"], "end_ms": b["timestamp_ms"], "duration_ms": b["timestamp_ms"] - a["timestamp_ms"]}
            for a, b in zip(rows, rows[1:]) if b["timestamp_ms"] - a["timestamp_ms"] > max_gap_ms]
    result = {"total_frames": len(rows), "face_frames": sum(r.get("face_detected") is True for r in rows) if any(r.get("face_detected") is not None for r in rows) else None,
              "all_measurements_valid_frames": sum(all(valid(row, component) for component in components) for row in rows),
              "timestamp_gaps": gaps, "components": {},
              "last_processing_fps": next((r["processing_fps"] for r in reversed(rows) if r.get("processing_fps") is not None), None),
              "observed_span_ms": rows[-1]["timestamp_ms"] - rows[0]["timestamp_ms"] if rows else 0}
    for component in components:
        mask = [valid(row, component) for row in rows]
        duration = sum(b["timestamp_ms"] - a["timestamp_ms"] for i, (a, b) in enumerate(zip(rows, rows[1:]))
                       if mask[i] and mask[i + 1] and b["timestamp_ms"] - a["timestamp_ms"] <= max_gap_ms)
        missing = []
        for row, available in zip(rows, mask):
            if not available:
                t = row["timestamp_ms"]
                if missing and missing[-1]["last_missing_ms"] == previous_t:
                    missing[-1]["last_missing_ms"] = t
                else:
                    missing.append({"first_missing_ms": t, "last_missing_ms": t})
            previous_t = row["timestamp_ms"]
        result["components"][component] = {"valid_frames": sum(mask), "valid_fraction": sum(mask) / len(mask) if mask else None,
            "invalid_fraction": 1 - sum(mask) / len(mask) if mask else None, "valid_duration_ms": duration,
            "missing_sample_intervals": missing}
    return result


def pair_timestamps(rows, references, tolerance_ms):
    timestamps = [r["timestamp_ms"] for r in rows]
    used, pairs = set(), []
    for ref in references:
        t = ref["timestamp_ms"]
        available = [i for i in range(bisect_left(timestamps, t - tolerance_ms), bisect_right(timestamps, t + tolerance_ms)) if i not in used]
        if available:
            index = min(available, key=lambda i: (abs(timestamps[i] - t), i))
            used.add(index)
            pairs.append((rows[index], ref))
    return pairs


def errors(values):
    values = np.asarray(values, dtype=float)
    return {"count": int(values.size), "mae": float(np.mean(np.abs(values))) if values.size else None,
            "rmse": float(np.sqrt(np.mean(values ** 2))) if values.size else None,
            "bias": float(np.mean(values)) if values.size else None}


def head_metrics(rows, pairs, compatible=False):
    values = [tuple(r[k] for k in ("yaw", "pitch", "roll")) for r in rows if valid(r, "head")]
    variation = circular_mean(values)[1] if values else None
    result = {"numeric_reference_compatible": compatible,
              "stability_samples_sufficient": len(values) >= 2,
              "circular_variance": (1 - np.clip(variation, 0, 1)).tolist() if variation is not None else None, "axes": {}}
    for axis in ("yaw", "pitch", "roll"):
        deltas = [float(angular_delta(a[axis], b[axis])) for a, b in pairs if valid(a, "head") and valid(b, "head")] if compatible else []
        result["axes"][axis] = errors(deltas)
    categories = [(a.get("orientation_category"), b.get("orientation_category")) for a, b in pairs if a.get("orientation_category") and b.get("orientation_category")]
    result["categorical"] = {"paired_labels": len(categories), "agreement": sum(a == b for a, b in categories) / len(categories) if categories else None,
        "reference_categories": sorted({b.get("orientation_category") for _, b in pairs if b.get("orientation_category")})}
    return result


def iris_metrics(rows, pairs, compatible=False):
    result = {}
    for side in ("left", "right"):
        keys = (side + "_iris_x", side + "_iris_y")
        values = np.array([[r[k] for k in keys] for r in rows if valid(r, side + "_iris")])
        entry = {"valid_frames": len(values), "mean": values.mean(axis=0).tolist() if values.size else None,
                 "stability_samples_sufficient": len(values) >= 2,
                 "variance": values.var(axis=0).tolist() if values.size else None, "numeric_reference_compatible": compatible,
                 "axes": {}}
        for key in keys:
            entry["axes"][key] = errors([a[key] - b[key] for a, b in pairs if valid(a, side + "_iris") and valid(b, side + "_iris")]) if compatible else errors([])
        result[side] = entry
    return result


def blink_metrics(detected, references, *, tolerance_ms=100, valid_duration_ms=None):
    result = compare_blinks(detected, references, tolerance_ms=tolerance_ms)
    tp, fp, fn = result["matched_reference"], result["unmatched_detections"], result["unmatched_reference"]
    result.update(tp=tp, fp=fp, fn=fn, f1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None)
    for name in ("start", "end", "duration"):
        deltas = []
        for match in result["matches"]:
            a, b = detected[match["detected_index"]], references[match["reference_index"]]
            deltas.append((a.end_ms - a.start_ms) - (b.end_ms - b.start_ms) if name == "duration" else getattr(a, name + "_ms") - getattr(b, name + "_ms"))
        result[name + "_error_ms"] = errors(deltas)
    result["valid_duration_ms"] = valid_duration_ms
    result["false_positives_per_min"] = fp * 60000 / valid_duration_ms if valid_duration_ms and valid_duration_ms > 0 else None
    result["false_positives_per_hour"] = fp * 3600000 / valid_duration_ms if valid_duration_ms and valid_duration_ms > 0 else None
    return result


def valid_intervals(rows, component, max_gap_ms):
    intervals = []
    for a, b in zip(rows, rows[1:]):
        start, end = a["timestamp_ms"], b["timestamp_ms"]
        if valid(a, component) and valid(b, component) and end - start <= max_gap_ms:
            if intervals and intervals[-1][1] == start:
                intervals[-1][1] = end
            else:
                intervals.append([start, end])
    return intervals


def validate_config(config):
    if not isinstance(config, dict):
        raise ValueError("Configurația de validare trebuie să fie un obiect JSON.")
    if any(not isinstance(config.get(name), str) or not config[name].strip() for name in ("experiment_id", "session_id")):
        raise ValueError("experiment_id și session_id sunt obligatorii.")
    for name in ("head_reference_verified", "iris_reference_verified", "blink_reference_complete", "final_evaluation", "cross_person"):
        if name in config and type(config[name]) is not bool:
            raise ValueError(f"{name} trebuie să fie boolean JSON, nu text.")
    for name in ("calibration_session_ids", "calibration_recording_ids", "training_participants"):
        if name in config and (not isinstance(config[name], list) or any(not isinstance(item, str) or not item for item in config[name])):
            raise ValueError(f"{name} trebuie să fie o listă de identificatori.")
    if not isinstance(config.get("scenarios", []), list):
        raise ValueError("scenarios trebuie să fie o listă.")
    for name in ("max_gap_ms", "timestamp_tolerance_ms", "blink_tolerance_ms"):
        value = config.get(name, 500 if name == "max_gap_ms" else 100 if name == "blink_tolerance_ms" else 20)
        if type(value) is not int or value < 0 or (name == "max_gap_ms" and value == 0):
            raise ValueError(f"Parametru invalid: {name}")
    if config["session_id"] in config.get("calibration_session_ids", []):
        raise ValueError("Sesiunea de validare se suprapune cu sesiunile de calibrare.")
    if config.get("recording_id") is not None and config["recording_id"] in config.get("calibration_recording_ids", []):
        raise ValueError("Înregistrare reutilizată la calibrare și validare.")
    if config.get("final_evaluation", False) and not config.get("calibration_session_ids"):
        raise ValueError("Evaluarea finală necesită identificarea sesiunilor de calibrare.")
    if config.get("final_evaluation"):
        from .experimental import FrozenExperiment
        plan = FrozenExperiment(config.get("frozen_plan"))
        plan.validate_target(config["session_id"], "validation")
        if config.get("calibration_session_ids") != plan.payload["calibration"]["calibration_session_ids"]:
            raise ValueError("Calibrările diferă de pachetul fixat.")
        plan.validation_config(config)
        receipt = config.get("processing_provenance", {})
        if receipt.get("plan_sha256") != plan.sha256 or receipt.get("role") != "validation" or receipt.get("session_id") != config["session_id"]:
            raise ValueError("Evaluarea finală necesită proveniența procesării cu pachetul înghețat.")
    if config.get("test_participant") in config.get("training_participants", []) and config.get("cross_person", False):
        raise ValueError("Participant de test prezent în calibrarea/antrenarea globală.")
    if config.get("cross_person") and (not config.get("test_participant") or not config.get("training_participants")):
        raise ValueError("Evaluarea între persoane necesită identificatorii anonimi ai grupurilor.")
    for scenario in config.get("scenarios", []):
        if not isinstance(scenario, dict) or not scenario.get("name") or any(type(scenario.get(key)) is not int for key in ("start_ms", "end_ms")) or not 0 <= scenario["start_ms"] < scenario["end_ms"]:
            raise ValueError("Scenariu temporal invalid.")


def covered_blink_metrics(rows, config, detected, references, *, window=None):
    """Evaluează numai evenimente întregi în acoperirea EAR și în scenariu."""
    if detected is None or references is None:
        return None
    quality = data_quality(rows, config.get("max_gap_ms", 500))
    result = {}
    for side in ("left", "right"):
        intervals = valid_intervals(rows, side + "_ear", config.get("max_gap_ms", 500))
        all_detected = [e for e in detected if e.eye == side]
        all_reference = [e for e in references if e.eye == side]
        boundary = {}
        if window is not None:
            start, end = window
            for label, events in (("detections", all_detected), ("references", all_reference)):
                boundary[label] = sum(e.start_ms < end and e.end_ms > start and not (start <= e.start_ms < e.end_ms < end) for e in events)
            all_detected = [e for e in all_detected if start <= e.start_ms < e.end_ms < end]
            all_reference = [e for e in all_reference if start <= e.start_ms < e.end_ms < end]
        def covered(event):
            return any(start <= event.start_ms < event.end_ms <= end for start, end in intervals)
        observed_detected = list(filter(covered, all_detected))
        observed_reference = list(filter(covered, all_reference))
        duration = quality["components"][side + "_ear"]["valid_duration_ms"] if config.get("blink_reference_complete", False) else None
        metrics = blink_metrics(observed_detected, observed_reference,
                                tolerance_ms=config.get("blink_tolerance_ms", 100), valid_duration_ms=duration)
        metrics.update(evaluation_available=bool(intervals), reference_complete=bool(config.get("blink_reference_complete")),
                       excluded_detections_outside_valid_ear=len(all_detected) - len(observed_detected),
                       excluded_references_outside_valid_ear=len(all_reference) - len(observed_reference))
        if window is not None:
            metrics["excluded_scenario_boundary"] = boundary
        if not intervals or not config.get("blink_reference_complete"):
            for key in ("fp", "fn", "precision", "recall", "f1", "false_positives_per_min", "false_positives_per_hour"):
                metrics[key] = None
            if not intervals:
                metrics["tp"] = None
        result[side] = metrics
    return result


def evaluate(rows, config, *, references=None, detected_blinks=None, reference_blinks=None):
    validate_config(config)
    if config.get("final_evaluation"):
        from .experimental import FrozenExperiment, check_evaluation_data
        rows = canonical_measurements(rows)
        check_evaluation_data(FrozenExperiment(config["frozen_plan"]), config["processing_provenance"], rows,
                              session_id=config["session_id"], events=detected_blinks, role="validation")
    # Revalidează ordinea și pentru apelurile API care nu folosesc cititorul CSV.
    timestamps = [r["timestamp_ms"] for r in rows]
    if any(type(t) is not int or t < 0 for t in timestamps) or any(b <= a for a, b in zip(timestamps, timestamps[1:])):
        raise ValueError("Timestampuri de măsurare invalide.")
    references = references if references is not None else []
    ref_times = [r["timestamp_ms"] for r in references]
    if any(type(t) is not int or t < 0 for t in ref_times) or any(b <= a for a, b in zip(ref_times, ref_times[1:])):
        raise ValueError("Timestampuri de referință invalide.")
    head_compatible = bool(config.get("head_reference_verified") and config.get("prediction_head_convention") == config.get("reference_head_convention") == CONVENTION
                           and config.get("prediction_head_frame") == config.get("reference_head_frame") in {"camera", "neutral"})
    if head_compatible and config.get("prediction_head_frame") == "neutral":
        head_compatible = bool(config.get("prediction_neutral_id") and config.get("prediction_neutral_id") == config.get("reference_neutral_id"))
    calibrated = {r.get("head_pose_calibrated") for r in rows if valid(r, "head") and r.get("head_pose_calibrated") is not None}
    if head_compatible and calibrated and calibrated != {config.get("prediction_head_frame") == "neutral"}:
        head_compatible = False
    ref_calibrated = {r.get("head_pose_calibrated") for r in references if valid(r, "head") and r.get("head_pose_calibrated") is not None}
    if head_compatible and ref_calibrated and ref_calibrated != {config.get("reference_head_frame") == "neutral"}:
        head_compatible = False
    iris_compatible = bool(config.get("iris_reference_verified") and config.get("iris_reference_convention") == "iris_local_normalized")
    pairs = pair_timestamps(rows, references, config.get("timestamp_tolerance_ms", 20))
    quality = data_quality(rows, config.get("max_gap_ms", 500))
    report = {"experiment_id": config["experiment_id"], "configuration": config, "evaluated_measurements": len(rows),
              "reference_pairs": len(pairs), "quality": quality, "head_pose": head_metrics(rows, pairs, head_compatible),
              "iris": iris_metrics(rows, pairs, iris_compatible), "blinks": None, "scenarios": [], "repeat_differences": [],
              "limitations": ["Rezultatele descriu măsurători geometrice, nu atenția sau punctul privit pe ecran."]}
    if not config.get("final_evaluation"):
        report["limitations"].append("Rulare exploratorie; nu este raport final de generalizare.")
    elif not any(m["kind"] in {"raw", "neutral_image"} for m in config["frozen_plan"]["payload"]["calibration"].get("source_materials", [])):
        report["limitations"].append("Profil C fără hashurile materialelor; separarea C/V necesită verificarea registrului experimental.")
    if config.get("final_evaluation") and not config["processing_provenance"].get("source_sha256"):
        report["limitations"].append("Sursa brută V nu are hash; independența înregistrării trebuie verificată procedural.")
    if not head_compatible:
        report["limitations"].append("Erorile în grade necesită referințe independente verificate, cu convenții și reper compatibile.")
    report["blinks"] = covered_blink_metrics(rows, config, detected_blinks, reference_blinks)
    if report["blinks"] is None:
        report["limitations"].append("Detecțiile sau referințele clipirilor nu au fost furnizate; metricile lipsesc.")
    for scenario in config.get("scenarios", []):
        selected = [r for r in rows if scenario["start_ms"] <= r["timestamp_ms"] < scenario["end_ms"]]
        scenario_pairs = [(a, b) for a, b in pairs if scenario["start_ms"] <= a["timestamp_ms"] < scenario["end_ms"]]
        report["scenarios"].append({"definition": scenario, "quality": data_quality(selected, config.get("max_gap_ms", 500)),
            "head_pose": head_metrics(selected, scenario_pairs, head_compatible), "iris": iris_metrics(selected, scenario_pairs, iris_compatible),
            "blinks": covered_blink_metrics(selected, config, detected_blinks, reference_blinks,
                                           window=(scenario["start_ms"], scenario["end_ms"]))})
    for i, first in enumerate(report["scenarios"]):
        for second in report["scenarios"][i + 1:]:
            if first["definition"].get("repeat_group") and first["definition"].get("repeat_group") == second["definition"].get("repeat_group"):
                for side in ("left", "right"):
                    a, b = first["iris"][side]["mean"], second["iris"][side]["mean"]
                    report["repeat_differences"].append({"first": first["definition"]["name"], "second": second["definition"]["name"], "eye": side,
                        "delta_mean": (np.asarray(b) - a).tolist() if a is not None and b is not None else None})
    report["conditions"] = {}
    for condition in ("lighting", "head_condition"):
        report["conditions"][condition] = {}
        labels = {s.get(condition) for s in config.get("scenarios", []) if s.get(condition)}
        for label in sorted(labels):
            intervals = [s for s in config["scenarios"] if s.get(condition) == label]
            selected = [row for row in rows if any(s["start_ms"] <= row["timestamp_ms"] < s["end_ms"] for s in intervals)]
            report["conditions"][condition][label] = {"quality": data_quality(selected, config.get("max_gap_ms", 500)), "iris": iris_metrics(selected, [], False)}
    return report


def save_report(report, output_dir: Path, *, plots=False):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    with (output_dir / "metrics.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        def flatten(value, prefix=""):
            if isinstance(value, dict):
                for key, item in value.items(): flatten(item, prefix + "." + key if prefix else key)
            elif isinstance(value, list):
                for i, item in enumerate(value): flatten(item, f"{prefix}[{i}]")
            else:
                writer.writerow([prefix, value])
        flatten(report)
    if plots:
        available = [(key, value["mae"]) for key, value in report["head_pose"]["axes"].items() if value["count"] >= 2 and value["mae"] is not None]
        if available:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            fig = Figure(figsize=(6, 4))
            FigureCanvasAgg(fig)
            axis = fig.subplots()
            axis.bar([k for k, _ in available], [v for _, v in available])
            axis.set_ylabel("MAE (grade)")
            fig.tight_layout()
            fig.savefig(output_dir / "head_mae.png")
