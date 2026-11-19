"""Date locale, sincronizare și sesiuni pentru dashboardul experimental."""
from dataclasses import dataclass, field, replace
from datetime import date
import csv
import json
import math
from pathlib import Path
import shutil
import uuid

from .calibration import CalibrationManager
from .temporal_analysis import BlinkEvent, circular_mean
from .validation import data_quality, evaluate, read_measurements, read_blinks, valid, valid_intervals


EXTRA_NUMERIC = ("left_ear_relative", "right_ear_relative", "left_gaze_dx", "left_gaze_dy", "right_gaze_dx", "right_gaze_dy")


def load_rows(path):
    rows = read_measurements(Path(path))
    for row in rows:
        for key in EXTRA_NUMERIC:
            value = row.get(key)
            row[key] = float(value) if value not in (None, "") else None
            if row[key] is not None and not math.isfinite(row[key]):
                raise ValueError(f"Valoare invalidă: {key}")
    return rows


def select_interval(rows, start_ms, end_ms):
    if start_ms < 0 or end_ms < start_ms:
        raise ValueError("Interval temporal invalid.")
    return [r for r in rows if start_ms <= r["timestamp_ms"] <= end_ms]


def measurement_context(row):
    return tuple(str(row[key]) if row.get(key) not in (None, "") else None
                 for key in ("source_id", "run_id", "capture_epoch", "track_id"))


def segments(rows, field, max_gap_ms=500):
    """Liste de puncte independente: nu unește lipsurile, gapurile sau wrap-ul Euler."""
    component = "head" if field in {"yaw", "pitch", "roll", "head_variation"} else "left_ear" if field.startswith("left_ear") else "right_ear" if field.startswith("right_ear") else "left_iris" if field.startswith("left") else "right_iris"
    groups, current, previous = [], [], None
    for row in rows:
        value = row.get(field)
        available = valid(row, component) and value is not None and math.isfinite(value)
        t = row["timestamp_ms"]
        context = measurement_context(row)
        discontinuity = previous is not None and (context != previous[2] or t - previous[0] > max_gap_ms or (field in {"yaw", "pitch", "roll"} and available and abs(value - previous[1]) > 180))
        if not available or discontinuity:
            if current: groups.append(current)
            current, previous = [], None
        if available:
            current.append((t / 1000, float(value)))
            previous = (t, value, context)
    if current: groups.append(current)
    return groups


def with_head_variation(rows, window_ms=1000, max_gap_ms=500):
    from collections import deque
    history, result, previous = deque(), [], None
    previous_context = None
    for row in rows:
        t = row["timestamp_ms"]
        context = measurement_context(row)
        if not valid(row, "head") or (previous is not None and (t - previous > max_gap_ms or context != previous_context)):
            history.clear()
        if valid(row, "head"):
            history.append((t, [row[k] for k in ("yaw", "pitch", "roll")]))
        while history and history[0][0] < t - window_ms:
            history.popleft()
        value = None
        if len(history) >= 2:
            resultant = circular_mean([v for _, v in history])[1]
            value = float((1 - resultant.clip(0, 1)).mean())
        result.append({**row, "head_variation": value})
        previous = t
        previous_context = context
    return result


def export_annotations(path, events):
    events = validate_annotations(events)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["eye", "start_ms", "end_ms"])
        for event in events: writer.writerow([event.eye, event.start_ms, event.end_ms])


def validate_annotations(events):
    ordered = sorted(events, key=lambda e: (e.start_ms, e.eye, e.end_ms))
    previous = {}
    for event in ordered:
        if event.eye not in {"left", "right"} or type(event.start_ms) is not int or type(event.end_ms) is not int or not 0 <= event.start_ms < event.end_ms:
            raise ValueError("Marcaj invalid: ochi left/right și început < sfârșit, în ms.")
        if previous.get(event.eye, -1) > event.start_ms:
            raise ValueError("Marcaje suprapuse pentru același ochi.")
        previous[event.eye] = event.end_ms
    return [replace(e, duration_ms=e.end_ms-e.start_ms, validation_status="manual_reference") for e in ordered]


@dataclass
class DashboardSession:
    session_id: str
    measurement_path: Path
    experiment_date: str = field(default_factory=lambda: date.today().isoformat())
    role: str = "validation"
    rows: list = field(default_factory=list)
    automatic: list | None = None
    manual: list | None = None
    references: list | None = None
    config: dict = field(default_factory=dict)
    calibration_path: Path | None = None
    video_path: Path | None = None
    interval_annotations: list = field(default_factory=list)
    reproducibility: dict = field(default_factory=dict)
    frozen_plan: dict | None = None

    @classmethod
    def from_csv(cls, path, session_id):
        if not session_id.strip(): raise ValueError("ID anonim obligatoriu.")
        session = cls(session_id.strip(), Path(path).resolve(), rows=load_rows(path),
                   config={"experiment_id": session_id.strip(), "session_id": session_id.strip(), "final_evaluation": False})
        receipt = Path(str(path) + ".experiment.json")
        if receipt.exists():
            session.reproducibility = json.loads(receipt.read_text(encoding="utf-8"))
            session.role = session.reproducibility.get("role", "validation")
        return session

    def evaluate(self):
        from .experimental import FrozenExperiment, validate_conditions, validate_role_id, digest
        validate_role_id(self.session_id, self.role)
        if self.role == "calibration":
            raise ValueError("Sesiunea de calibrare nu poate fi raportată ca validare.")
        if not isinstance(self.config, dict): raise ValueError("Configurația trebuie să fie un obiect JSON.")
        config = {**self.config, "session_id": self.session_id}
        annotations = validate_conditions(self.interval_annotations, self.rows)
        config["scenarios"] = [*config.get("scenarios", []), *[{"name": a["label"], "start_ms": a["start_ms"], "end_ms": a["end_ms"]} for a in annotations if a["kind"] == "condition"]]
        if self.role == "development": config["final_evaluation"] = False
        if self.calibration_path:
            manager = CalibrationManager.load(self.calibration_path)
            config["calibration_session_ids"] = sorted(set(config.get("calibration_session_ids", [])) | set(manager.session_ids))
        if self.frozen_plan:
            plan = FrozenExperiment(self.frozen_plan)
            receipt = self.reproducibility
            from .experimental import check_evaluation_data
            check_evaluation_data(plan, receipt, self.rows, session_id=self.session_id, events=self.automatic, role=self.role)
            config = plan.validation_config(config)
            config["final_evaluation"] = self.role == "validation"
            config["processing_provenance"] = receipt
        report = evaluate(self.rows, config, references=self.references, detected_blinks=self.automatic, reference_blinks=self.manual)
        from .experimental import manual_absence_report
        report["manual_face_absence"] = manual_absence_report(self.rows, annotations)
        report["reproducibility"] = self.reproducibility
        report["session_role"] = self.role
        return report

    def blink_summary(self):
        quality = data_quality(self.rows, self.config.get("max_gap_ms", 500))
        result = {}
        for eye in ("left", "right"):
            duration = quality["components"][eye + "_ear"]["valid_duration_ms"]
            events = None if self.automatic is None else [e for e in self.automatic if e.eye == eye]
            intervals = valid_intervals(self.rows, eye + "_ear", self.config.get("max_gap_ms", 500))
            observed = [e for e in (events or []) if any(start <= e.start_ms < e.end_ms <= end for start, end in intervals)]
            enabled = self.config.get("blink_detection_enabled") is True
            result[eye] = {"count": len(events) if events is not None else None, "valid_duration_ms": duration,
                "rate_per_min": len(observed) * 60000 / duration if events is not None and enabled and duration >= 10000 else None}
        return result


class VideoNavigator:
    """Frame seeking OpenCV, fără inferență; timestampul vine din CSV-ul aceleiași sesiuni."""
    def __init__(self, path, rows):
        if any(str(row.get("timestamp_source") or "").startswith(("webcam_", "network_", "live_")) for row in rows):
            raise ValueError("Datele live necesită o mapare independentă la cadrele înregistrării; nu folosi indexul livrat de cameră")
        import cv2
        self.cv2 = cv2
        self.capture = cv2.VideoCapture(str(path))
        try:
            if not self.capture.isOpened(): raise ValueError("Videoclipul nu poate fi deschis.")
            self.count = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = float(self.capture.get(cv2.CAP_PROP_FPS))
            if self.count <= 0: raise ValueError("Număr de cadre indisponibil; navigarea pe cadre nu este posibilă.")
            self.mapping = {}
            for row in rows:
                if row.get("frame_index") not in (None, ""):
                    index = int(row["frame_index"])
                    if index in self.mapping or index < 0: raise ValueError("frame_index duplicat sau invalid.")
                    self.mapping[index] = row["timestamp_ms"]
        except Exception:
            self.capture.release()
            raise

    def read(self, index):
        if type(index) is not int or not 0 <= index < self.count: raise ValueError("Index de cadru invalid.")
        self.capture.set(self.cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = self.capture.read()
        if not ok or frame is None: raise ValueError("Cadrul nu poate fi decodat.")
        actual = self.capture.get(self.cv2.CAP_PROP_POS_FRAMES) - 1
        if not math.isfinite(actual) or abs(actual - index) > .1:
            raise ValueError("Backendul nu a confirmat indexul cadrului; timestampul nu este asociat.")
        return frame, self.mapping.get(index)

    def close(self): self.capture.release()


class SessionStore:
    """Copii explicite CSV/JSON; videoclipul rămâne o legătură locală externă."""
    FILES = {"manifest.json", "measurements.csv", "automatic.csv", "manual.csv", "references.csv", "calibration.json"}
    OWNER = "AnalizaAtentiei.dashboard.v1"

    def __init__(self, root): self.root = Path(root).resolve()

    def save(self, session, *, include_external_paths=False):
        from .experimental import validate_conditions, validate_role_id, measurement_digest
        validate_role_id(session.session_id, session.role)
        date.fromisoformat(session.experiment_date)
        if not isinstance(session.config, dict): raise ValueError("Configurație de sesiune invalidă.")
        validate_conditions(session.interval_annotations, session.rows)
        folder = self.root / str(uuid.uuid4())
        manifest = {"owner": self.OWNER, "session_id": session.session_id, "experiment_date": session.experiment_date,
                    "role": session.role, "config": session.config,
                    "source_measurements": str(session.measurement_path) if include_external_paths else None,
                    "video_path": str(session.video_path) if include_external_paths and session.video_path else None,
                    "source_measurements_sha256": measurement_digest(session.rows),
                    "duration_ms": session.rows[-1]["timestamp_ms"]-session.rows[0]["timestamp_ms"] if session.rows else 0,
                    "interval_annotations": session.interval_annotations, "reproducibility": session.reproducibility,
                    "frozen_plan": session.frozen_plan}
        # Manifestul este scris primul: și un import incomplet rămâne identificabil.
        serialized = json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False)
        folder.mkdir(parents=True)
        (folder / "manifest.json").write_text(serialized, encoding="utf-8")
        fields = sorted(set().union(*(r.keys() for r in session.rows))) if session.rows else ["timestamp_ms"]
        with (folder / "measurements.csv").open("x", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(session.rows)
        for name, events in (("automatic.csv", session.automatic), ("manual.csv", session.manual)):
            if events is not None:
                if name == "manual.csv": export_annotations(folder / name, events)
                else:
                    with (folder / name).open("x", newline="", encoding="utf-8") as handle:
                        writer = csv.writer(handle); writer.writerow(["eye", "start_ms", "end_ms"])
                        for event in events: writer.writerow([event.eye, event.start_ms, event.end_ms])
        if session.references is not None:
            fields = sorted(set().union(*(row.keys() for row in session.references))) if session.references else ["timestamp_ms"]
            with (folder / "references.csv").open("x", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(session.references)
        if session.calibration_path: shutil.copyfile(session.calibration_path, folder / "calibration.json")
        return folder

    def load(self, folder):
        folder = Path(folder).resolve()
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("owner") != self.OWNER: raise ValueError("Manifest de sesiune incompatibil.")
        if manifest.get("role") not in {"calibration", "development", "validation"} or not isinstance(manifest.get("config"), dict):
            raise ValueError("Metadate de sesiune invalide.")
        date.fromisoformat(manifest["experiment_date"])
        session = DashboardSession.from_csv(folder / "measurements.csv", manifest["session_id"])
        from .experimental import measurement_digest
        if manifest.get("source_measurements_sha256") and manifest["source_measurements_sha256"] != measurement_digest(session.rows):
            raise ValueError("Snapshotul de măsurători a fost modificat.")
        session.experiment_date, session.role, session.config = manifest["experiment_date"], manifest["role"], manifest["config"]
        session.video_path = Path(manifest["video_path"]) if manifest.get("video_path") else None
        from .experimental import validate_conditions, validate_role_id
        validate_role_id(session.session_id, session.role)
        session.interval_annotations = validate_conditions(manifest.get("interval_annotations", []), session.rows)
        session.reproducibility = manifest.get("reproducibility", {})
        session.frozen_plan = manifest.get("frozen_plan")
        if (folder / "automatic.csv").exists(): session.automatic = read_blinks(folder / "automatic.csv")
        if (folder / "manual.csv").exists(): session.manual = validate_annotations(read_blinks(folder / "manual.csv"))
        if (folder / "references.csv").exists(): session.references = load_rows(folder / "references.csv")
        if (folder / "calibration.json").exists(): session.calibration_path = folder / "calibration.json"
        return session

    def delete(self, folder):
        original = Path(folder)
        if original.is_symlink() or getattr(original, "is_junction", lambda: False)(): raise ValueError("Legăturile nu pot fi șterse ca sesiuni.")
        folder = original.resolve()
        if folder.parent != self.root: raise ValueError("Sesiunea nu aparține directorului gestionat.")
        try: uuid.UUID(folder.name)
        except ValueError as exc: raise ValueError("Director de sesiune invalid.") from exc
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("owner") != self.OWNER: raise ValueError("Directorul nu aparține dashboardului.")
        files = list(folder.iterdir())
        if any(p.name not in self.FILES or not p.is_file() or p.is_symlink() or getattr(p, "is_junction", lambda: False)() for p in files):
            raise ValueError("Sesiunea conține fișiere neașteptate; ștergerea automată este refuzată.")
        for path in files: path.unlink()
        folder.rmdir()
