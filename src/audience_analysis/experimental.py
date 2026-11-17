"""Roluri C/D/V, configurații înghețate și proveniență reproductibilă locală."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
from importlib.metadata import PackageNotFoundError, version

from .temporal_analysis import TemporalConfig


ROLES = {"calibration", "development", "validation"}
CONTEXT_KEYS = {"session_id", "experiment_id", "scenarios", "final_evaluation", "calibration_session_ids",
                "recording_id", "calibration_recording_ids", "head_reference_verified", "iris_reference_verified",
                "blink_reference_complete", "frozen_plan", "processing_provenance"}


def validate_role_id(session_id, role):
    if role not in ROLES or not isinstance(session_id, str) or not session_id.strip() or session_id != session_id.strip():
        raise ValueError("Rol sau identificator de sesiune invalid.")
    match = re.fullmatch(r"([CDV])\d+", session_id.upper())
    if match and {"C": "calibration", "D": "development", "V": "validation"}[match[1]] != role:
        raise ValueError(f"{session_id} nu poate avea rolul {role}.")


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def measurement_digest(rows):
    from .validation import canonical_measurements
    return digest(canonical_measurements(rows))


def event_digest(events):
    if events is None: return None
    values = [(e.eye, e.start_ms, e.end_ms) for e in events]
    if any(eye not in {"left", "right"} or type(start) is not int or type(end) is not int or not 0 <= start < end for eye, start, end in values):
        raise ValueError("Evenimente invalide în proveniență.")
    return digest(values)


def file_digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): value.update(block)
    return value.hexdigest()


def code_version():
    root = Path(__file__).resolve().parents[2]
    package = Path(__file__).resolve().parent
    if (root / "src" / "audience_analysis").is_dir():
        files = sorted(set((root / "src").rglob("*.py")) | set(root.glob("*.py")))
        source = {p.relative_to(root).as_posix(): file_digest(p) for p in files if "__pycache__" not in p.parts}
    else:
        # Wheel: aceleași nume canonice ca în checkout, fără hash pe întregul site-packages.
        source = {"src/audience_analysis/" + p.relative_to(package).as_posix(): file_digest(p) for p in package.rglob("*.py")}
        for name in ("calibrate_session", "compare_blinks", "experimental_session", "run_dashboard", "run_validation", "run_video_analysis", "test_face_landmarker"):
            path = package.parent / (name + ".py")
            if path.is_file(): source[path.name] = file_digest(path)
    revision = None
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root if (root / ".git").is_dir() else package, capture_output=True, text=True, timeout=5)
        if result.returncode == 0: revision = result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired): pass
    return {"git_revision": revision, "source_sha256": digest(source)}


def environment_versions():
    result = {}
    for name in ("mediapipe", "numpy", "opencv-python", "opencv-contrib-python", "PySide6"):
        try: result[name] = version(name)
        except PackageNotFoundError: pass
    return result


class FrozenExperiment:
    def __init__(self, document):
        if not isinstance(document, dict) or set(document) != {"payload", "sha256"} or digest(document["payload"]) != document["sha256"]:
            raise ValueError("Pachetul înghețat este invalid sau a fost modificat.")
        self.document = json.loads(json.dumps(document))
        self.payload = self.document["payload"]
        self.sha256 = self.document["sha256"]
        required = {"schema_version", "config_version", "calibration", "development_sessions", "temporal", "validation_parameters", "model", "environment", "code"}
        if not isinstance(self.payload, dict) or set(self.payload) != required or self.payload.get("schema_version") != 1:
            raise ValueError("Structură/versiune de pachet incompatibilă.")
        if not isinstance(self.payload["validation_parameters"], dict) or not self.payload["development_sessions"]:
            raise ValueError("Pachet fără parametri sau surse de dezvoltare.")
        from .calibration import CalibrationManager
        CalibrationManager.from_dict(self.payload["calibration"])
        TemporalConfig.from_dict(self.payload["temporal"])

    @classmethod
    def create(cls, calibration, development_sessions, model_path, *, temporal=None, validation=None, config_version="1"):
        from .calibration import CalibrationManager
        manager = CalibrationManager.load(calibration)
        if manager.model_sha256 is not None and manager.model_sha256 != file_digest(model_path):
            raise ValueError("Modelul C diferă de modelul ales pentru experiment.")
        from .dashboard_data import load_rows
        config = manager.temporal_config(temporal or TemporalConfig())
        if not development_sessions: raise ValueError("Este necesară cel puțin o sesiune D de dezvoltare.")
        sources = []
        for session in development_sessions:
            validate_role_id(session.session_id, session.role)
            if session.role != "development": raise ValueError("V01/C01 nu pot fi folosite pentru ajustarea parametrilor.")
            receipt = session.reproducibility
            if receipt.get("role") != "development" or receipt.get("session_id") != session.session_id or receipt.get("measurement_content_sha256") != measurement_digest(load_rows(session.measurement_path)):
                raise ValueError("D01 necesită proveniență verificabilă; procesează cu --session-id D01 --role development.")
            if digest(receipt.get("temporal")) != digest(asdict(config)) or digest(receipt.get("calibration")) != digest(manager.to_dict()):
                raise ValueError("Parametrii aleși nu au fost testați în rularea D01.")
            if receipt.get("model_sha256") != file_digest(model_path) or receipt.get("code", {}).get("source_sha256") != code_version()["source_sha256"]:
                raise ValueError("D01 a folosit alt cod sau model; repetă dezvoltarea cu configurația fixată.")
            if receipt.get("environment") != environment_versions(): raise ValueError("D01 a folosit alte versiuni ale dependențelor.")
            if receipt.get("source_sha256") in {m["sha256"] for m in manager.source_materials}:
                raise ValueError("Înregistrarea D a fost folosită la calibrare.")
            from .validation import data_quality
            sources.append({"session_id": session.session_id, "role": session.role,
                            "measurements_sha256": file_digest(session.measurement_path), "source_sha256": receipt.get("source_sha256"),
                            "quality": data_quality(load_rows(session.measurement_path))})
        if set(manager.session_ids) & {s["session_id"] for s in sources}:
            raise ValueError("C și D trebuie să fie sesiuni distincte.")
        params = {k: v for k, v in (validation or {}).items() if k not in CONTEXT_KEYS}
        payload = {"schema_version": 1, "config_version": str(config_version), "calibration": manager.to_dict(),
                   "development_sessions": sources, "temporal": asdict(config), "validation_parameters": params,
                   "model": {"name": "MediaPipe Face Landmarker", "sha256": file_digest(model_path)},
                   "environment": environment_versions(), "code": code_version()}
        return cls({"payload": payload, "sha256": digest(payload)})

    @classmethod
    def load(cls, path): return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def save(self, path):
        path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream: json.dump(self.document, stream, ensure_ascii=False, indent=2, allow_nan=False)

    def validate_runtime(self, model_path=None):
        if code_version()["source_sha256"] != self.payload["code"]["source_sha256"]:
            raise ValueError("Codul diferă de configurația înghețată; folosește versiunea fixată sau un nou D/V.")
        if model_path is not None and file_digest(model_path) != self.payload["model"]["sha256"]:
            raise ValueError("Modelul diferă de cel înghețat.")
        if self.payload["environment"] != environment_versions(): raise ValueError("Versiunile dependențelor diferă de pachetul înghețat.")

    def estimators(self):
        from .calibration import CalibrationManager
        manager = CalibrationManager.from_dict(self.payload["calibration"])
        return manager, TemporalConfig.from_dict(self.payload["temporal"])

    def validation_config(self, context):
        for key, value in context.items():
            if key not in CONTEXT_KEYS and value != self.payload["validation_parameters"].get(key):
                raise ValueError(f"Parametrul {key} diferă de configurația înghețată.")
        result = {**self.payload["validation_parameters"], **{k: v for k, v in context.items() if k in CONTEXT_KEYS}}
        result["calibration_session_ids"] = self.payload["calibration"]["calibration_session_ids"]
        result["frozen_plan"] = self.document
        return result

    def validate_target(self, session_id, role):
        validate_role_id(session_id, role)
        if role == "calibration": raise ValueError("Pachetul se aplică după calibrare, numai pe D/V.")
        sources = self.payload["calibration"]["calibration_session_ids"] + [s["session_id"] for s in self.payload["development_sessions"]]
        if role == "validation" and session_id in sources:
            raise ValueError("Sesiunea finală a fost folosită la calibrare/dezvoltare.")

    def validate_source(self, source, role):
        if role == "validation" and not isinstance(source, int):
            self.validate_source_hash(file_digest(source))

    def validate_source_hash(self, source_hash):
        used = {s.get("source_sha256") for s in self.payload["development_sessions"]}
        used.update(m["sha256"] for m in self.payload["calibration"].get("source_materials", []))
        if source_hash is not None and source_hash in used:
            raise ValueError("Înregistrarea V a fost folosită la calibrare/dezvoltare.")


def make_receipt(plan, session_id, role, measurements, *, events=None, source=None):
    plan.validate_runtime()
    plan.validate_target(session_id, role)
    if source is not None: plan.validate_source(source, role)
    from .dashboard_data import load_rows
    from .validation import read_blinks
    return {"schema_version": 1, "session_id": session_id, "role": role, "plan_sha256": plan.sha256,
            "model_sha256": plan.payload["model"]["sha256"], "code": code_version(),
            "measurements_sha256": file_digest(measurements), "measurement_content_sha256": measurement_digest(load_rows(measurements)),
            "events_sha256": file_digest(events) if events else None,
            "event_content_sha256": event_digest(read_blinks(events)) if events else None,
            "source_sha256": file_digest(source) if source is not None and not isinstance(source, int) else None}


def check_receipt(plan, receipt, measurements, *, session_id, events=None):
    from .dashboard_data import load_rows
    from .validation import read_blinks
    check_evaluation_data(plan, receipt, load_rows(measurements), session_id=session_id,
                          events=read_blinks(events) if events is not None else None)


def check_evaluation_data(plan, receipt, rows, *, session_id, events=None, role=None):
    """Guard comun pentru CLI, dashboard și API-ul final de nivel inferior."""
    plan.validate_runtime()
    if not isinstance(receipt, dict): raise ValueError("Proveniență absentă/incompatibilă.")
    if role is not None and receipt.get("role") != role: raise ValueError("Rol de proveniență incompatibil.")
    plan.validate_target(session_id, receipt.get("role"))
    if receipt.get("session_id") != session_id or receipt.get("plan_sha256") != plan.sha256:
        raise ValueError("Proveniența nu corespunde sesiunii/pachetului.")
    if receipt.get("measurement_content_sha256") != measurement_digest(rows): raise ValueError("Măsurătorile diferă de rularea fixată.")
    if receipt.get("model_sha256") != plan.payload["model"]["sha256"] or receipt.get("code", {}).get("source_sha256") != plan.payload["code"]["source_sha256"]:
        raise ValueError("Cod/model incompatibil în proveniență.")
    if receipt.get("role") == "validation": plan.validate_source_hash(receipt.get("source_sha256"))
    if receipt.get("event_content_sha256") != event_digest(events): raise ValueError("Evenimentele lipsesc sau diferă de rularea fixată.")


def validate_conditions(items, rows=None):
    result = []
    for item in items:
        if not isinstance(item, dict) or item.get("kind") not in {"face_absent", "condition"}:
            raise ValueError("Tip marcaj: face_absent sau condition.")
        start, end = item.get("start_ms"), item.get("end_ms")
        if type(start) is not int or type(end) is not int or not 0 <= start < end or not str(item.get("label", "")).strip():
            raise ValueError("Marcaj de condiție invalid.")
        if rows is not None and (not rows or start < rows[0]["timestamp_ms"] or end > rows[-1]["timestamp_ms"]):
            raise ValueError("Marcajul nu este în axa temporală a sesiunii.")
        result.append({"kind": item["kind"], "label": item["label"], "start_ms": start, "end_ms": end})
    return sorted(result, key=lambda r: (r["start_ms"], r["kind"], r["label"]))


def read_conditions(path, rows=None):
    import csv
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        records = [{**r, "start_ms": int(r["start_ms"]), "end_ms": int(r["end_ms"])} for r in csv.DictReader(handle)]
    return validate_conditions(records, rows)


def export_conditions(path, items, rows=None):
    import csv
    items = validate_conditions(items, rows)
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["kind", "label", "start_ms", "end_ms"])
        writer.writeheader(); writer.writerows(items)


def manual_absence_report(rows, annotations):
    absent = [r for r in rows if any(a["kind"] == "face_absent" and a["start_ms"] <= r["timestamp_ms"] < a["end_ms"] for a in annotations)]
    known = [r for r in absent if r.get("face_detected") is not None]
    return {"annotated_frames": len(absent), "known_face_status_frames": len(known),
            "unexpected_face_detections": sum(r.get("face_detected") is True for r in known) if known else None}


def compare_sessions(sessions):
    from .validation import data_quality
    result = []
    for session in sessions:
        validate_role_id(session.session_id, session.role)
        quality = data_quality(session.rows, session.config.get("max_gap_ms", 500))
        try:
            report = session.evaluate() if session.role != "calibration" else None
            error = None
        except ValueError as exc:
            report, error = None, str(exc)
        blinks = report.get("blinks") if report else None
        scenarios = report.get("scenarios", []) if report else []
        worst = sorted([s for s in scenarios if s["quality"]["components"]["head"]["valid_fraction"] is not None],
                       key=lambda s: 1 - s["quality"]["components"]["head"]["valid_fraction"], reverse=True)
        worst_errors = sorted([s for s in scenarios if s["head_pose"]["axes"]["yaw"]["mae"] is not None],
                              key=lambda s: s["head_pose"]["axes"]["yaw"]["mae"], reverse=True)
        blink_errors = []
        for scenario in scenarios:
            for eye, metrics in (scenario.get("blinks") or {}).items():
                if metrics["fp"] is not None and metrics["fn"] is not None:
                    blink_errors.append({"scenario": scenario["definition"]["name"], "eye": eye,
                                         "errors": metrics["fp"] + metrics["fn"]})
        result.append({"session_id": session.session_id, "role": session.role, "date": session.experiment_date,
                       "config": session.config, "reproducibility": session.reproducibility,
                       "duration_ms": quality["observed_span_ms"], "head_valid_fraction": quality["components"]["head"]["valid_fraction"],
                       "yaw_mae": report["head_pose"]["axes"]["yaw"]["mae"] if report else None,
                       "left_blink_f1": blinks["left"]["f1"] if blinks else None,
                       "right_blink_f1": blinks["right"]["f1"] if blinks else None,
                       "metrics": {k: report[k] for k in ("head_pose", "iris", "blinks")} if report else None,
                       "missing_intervals": quality["components"]["head"]["missing_sample_intervals"],
                       "missing_intervals_by_component": {k: v["missing_sample_intervals"] for k, v in quality["components"].items()},
                       "quality": quality,
                       "worst_head_coverage_scenarios": [s["definition"]["name"] for s in worst[:3]],
                       "worst_yaw_error_scenarios": [s["definition"]["name"] for s in worst_errors[:3]],
                       "worst_blink_error_scenarios": sorted(blink_errors, key=lambda item: item["errors"], reverse=True)[:3],
                       "evaluation_error": error})
    return result
