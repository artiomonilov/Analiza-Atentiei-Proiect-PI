from dataclasses import asdict
import json
from pathlib import Path
import runpy

import pytest

from audience_analysis.calibration import CalibrationManager
from audience_analysis.dashboard_data import DashboardSession, SessionStore, load_rows
from audience_analysis.experimental import (FrozenExperiment, check_receipt, code_version, compare_sessions,
    digest, measurement_digest, environment_versions, export_conditions, file_digest, make_receipt, read_conditions, validate_conditions, validate_role_id)


@pytest.fixture
def experiment(tmp_path):
    csv_path = tmp_path / "development.csv"
    csv_path.write_text("timestamp_ms,frame_index,face_detected,yaw,pitch,roll,left_ear,right_ear\n0,0,True,0,0,0,.3,.3\n100,1,False,,,,,\n200,2,True,1,0,0,.3,.3\n")
    model = tmp_path / "model.task"; model.write_bytes(b"synthetic model only, not loaded")
    source = tmp_path / "D-source.bin"; source.write_bytes(b"synthetic recording D")
    manager = CalibrationManager(["C01"])
    manager.calibrate_ear("left", [.3] * 5, [.1] * 5)
    profile = tmp_path / "profile.json"; manager.save(profile)
    development = DashboardSession.from_csv(csv_path, "D01"); development.role = "development"
    development.reproducibility = {"session_id": "D01", "role": "development", "code": code_version(),
        "environment": environment_versions(),
        "model_sha256": file_digest(model), "source_sha256": file_digest(source),
        "measurement_content_sha256": measurement_digest(load_rows(csv_path)), "temporal": asdict(manager.temporal_config()), "calibration": manager.to_dict()}
    plan = FrozenExperiment.create(profile, [development], model, validation={"max_gap_ms": 500})
    return {"path": csv_path, "model": model, "profile": profile, "manager": manager, "d": development, "plan": plan, "source": source}


def test_frozen_plan_roundtrip_and_deterministic_configuration(experiment, tmp_path):
    path = tmp_path / "frozen.json"; experiment["plan"].save(path)
    restored = FrozenExperiment.load(path)
    assert restored.sha256 == experiment["plan"].sha256
    assert restored.payload["calibration"]["calibration_session_ids"] == ["C01"]
    assert restored.estimators()[1].left_blink.close == pytest.approx(.17)
    restored.validate_runtime(experiment["model"])
    with pytest.raises(FileExistsError): restored.save(path)


def test_changed_bundle_is_rejected(experiment):
    document = json.loads(json.dumps(experiment["plan"].document))
    document["payload"]["temporal"]["max_gap_ms"] = 999
    with pytest.raises(ValueError): FrozenExperiment(document)


@pytest.mark.parametrize("identifier,role", [("V01", "development"), ("D01", "calibration"), ("C01", "validation"), ("v01", "calibration"), (" V01 ", "calibration")])
def test_session_roles_cannot_be_swapped(identifier, role):
    with pytest.raises(ValueError): validate_role_id(identifier, role)


def test_v01_is_not_a_calibration_source():
    with pytest.raises(ValueError): CalibrationManager(["V01"])


def test_validation_data_cannot_freeze_thresholds(experiment):
    session = experiment["d"]; session.role = "validation"; session.session_id = "V01"
    with pytest.raises(ValueError): FrozenExperiment.create(experiment["profile"], [session], experiment["model"])


def test_development_must_have_used_chosen_parameters(experiment):
    experiment["d"].reproducibility["temporal"]["max_gap_ms"] = 999
    with pytest.raises(ValueError): FrozenExperiment.create(experiment["profile"], [experiment["d"]], experiment["model"])


def test_final_config_cannot_override_frozen_parameters(experiment):
    with pytest.raises(ValueError): experiment["plan"].validation_config({"max_gap_ms": 999})
    context = experiment["plan"].validation_config({"session_id": "V01", "experiment_id": "EXP", "scenarios": []})
    assert context["max_gap_ms"] == 500 and context["session_id"] == "V01"


def test_runtime_model_change_rejected(experiment):
    experiment["model"].write_bytes(b"different")
    with pytest.raises(ValueError): experiment["plan"].validate_runtime(experiment["model"])


def test_reused_recording_rejected_even_with_new_id(experiment):
    with pytest.raises(ValueError): experiment["plan"].validate_source(experiment["source"], "validation")


def test_processing_provenance_binds_measurements(experiment):
    receipt = make_receipt(experiment["plan"], "V01", "validation", experiment["path"])
    check_receipt(experiment["plan"], receipt, experiment["path"], session_id="V01")
    experiment["path"].write_text("timestamp_ms\n999\n")
    with pytest.raises(ValueError): check_receipt(experiment["plan"], receipt, experiment["path"], session_id="V01")


def test_final_session_snapshot_keeps_semantic_provenance(experiment, tmp_path):
    session = DashboardSession.from_csv(experiment["path"], "V01")
    session.frozen_plan = experiment["plan"].document
    session.reproducibility = make_receipt(experiment["plan"], "V01", "validation", experiment["path"])
    report = session.evaluate()
    assert report["configuration"]["final_evaluation"]
    assert report["head_pose"]["axes"]["yaw"]["mae"] is None
    store = SessionStore(tmp_path / "sessions"); saved = store.save(session)
    restored = store.load(saved)
    assert restored.evaluate() == report


def test_manual_conditions_sync_and_export(experiment, tmp_path):
    items = [{"kind": "face_absent", "label": "out", "start_ms": 0, "end_ms": 100},
             {"kind": "condition", "label": "neutral", "start_ms": 100, "end_ms": 200}]
    path = tmp_path / "conditions.csv"; export_conditions(path, items, experiment["d"].rows)
    assert read_conditions(path, experiment["d"].rows) == items
    with pytest.raises(ValueError): validate_conditions([{**items[0], "end_ms": 999}], experiment["d"].rows)
    assert experiment["d"].manual is None  # condițiile nu creează clipiri


def test_development_evaluation_and_comparison(experiment):
    c = DashboardSession.from_csv(experiment["path"], "C01"); c.role = "calibration"
    d = experiment["d"]
    d.interval_annotations = [{"kind": "face_absent", "label": "out", "start_ms": 0, "end_ms": 100}]
    v = DashboardSession.from_csv(experiment["path"], "V01")
    result = compare_sessions([c, d, v])
    assert [r["role"] for r in result] == ["calibration", "development", "validation"]
    assert result[0]["yaw_mae"] is None and result[1]["duration_ms"] == 200
    assert d.evaluate()["manual_face_absence"]["unexpected_face_detections"] == 1


def test_dashboard_protocol_and_comparison(qtbot, experiment, tmp_path):
    from PySide6.QtWidgets import QTableWidgetItem
    from audience_analysis.ui.experimental_dashboard import ExperimentalDashboard
    window = ExperimentalDashboard(tmp_path / "sessions"); qtbot.addWidget(window)
    window.add_session(experiment["d"])
    window.protocol_table.setRowCount(1)
    for col, value in enumerate(("condition", "neutral", "0", "200")):
        window.protocol_table.setItem(0, col, QTableWidgetItem(value))
    window.apply_protocol()
    assert len(experiment["d"].interval_annotations) == 1
    assert window.refresh_comparison()[0]["role"] == "development"
    assert window.comparison_table.item(0, 5).text() == "N/A"


def test_cli_creates_development_session_without_video_copy(experiment, tmp_path):
    root = tmp_path / "sessions"
    main = runpy.run_path(str(Path(__file__).resolve().parents[2] / "experimental_session.py"))["main"]
    assert main(["create", "--id", "D01", "--role", "development", "--measurements", str(experiment["path"]), "--video", str(experiment["source"]), "--root", str(root)]) == 0
    folder = next(root.iterdir())
    session = SessionStore(root).load(folder)
    assert session.video_path is None  # căile personale sunt păstrate numai prin opt-in
    assert not any(p.suffix == ".bin" for p in folder.iterdir())


def test_final_evaluation_without_frozen_configuration_is_rejected(experiment):
    from audience_analysis.validation import evaluate
    with pytest.raises(ValueError):
        evaluate(experiment["d"].rows, {"experiment_id": "EXP", "session_id": "V01", "calibration_session_ids": ["C01"], "final_evaluation": True})


def test_source_code_change_is_rejected(experiment, monkeypatch):
    import audience_analysis.experimental as module
    monkeypatch.setattr(module, "code_version", lambda: {"source_sha256": "changed", "git_revision": None})
    with pytest.raises(ValueError): experiment["plan"].validate_runtime()


def test_video_cli_rejects_v01_parameter_tuning_without_plan(tmp_path):
    main = runpy.run_path(str(Path(__file__).resolve().parents[2] / "run_video_analysis.py"))["main"]
    with pytest.raises(SystemExit) as exc:
        main(["--source", "not-opened.avi", "--session-id", "V01", "--output-csv", str(tmp_path / "unused.csv"), "--no-display"])
    assert exc.value.code == 1
    assert not (tmp_path / "unused.csv").exists()


def test_manual_absence_does_not_turn_unknown_face_status_into_zero():
    from audience_analysis.experimental import manual_absence_report
    result = manual_absence_report([{"timestamp_ms": 0}], [{"kind": "face_absent", "label": "out", "start_ms": 0, "end_ms": 100}])
    assert result["unexpected_face_detections"] is None


@pytest.mark.parametrize("change", ["measurements", "events", "omit_events", "model", "code", "role", "source"])
def test_final_low_level_api_rejects_changed_provenance(experiment, tmp_path, change):
    from audience_analysis.temporal_analysis import BlinkEvent
    from audience_analysis.validation import evaluate, read_measurements
    events_path = tmp_path / "events.csv"
    events_path.write_text("eye,start_ms,end_ms\nleft,10,50\n")
    receipt = make_receipt(experiment["plan"], "V01", "validation", experiment["path"], events=events_path)
    rows = read_measurements(experiment["path"])
    events = [BlinkEvent("left", 10, 50, 40)]
    config = experiment["plan"].validation_config({"experiment_id": "SYNTHETIC", "session_id": "V01",
        "final_evaluation": True, "processing_provenance": receipt})
    assert evaluate(rows, config, detected_blinks=events)["configuration"]["final_evaluation"]
    if change == "measurements": rows[0]["yaw"] = 75
    elif change == "events": events = [BlinkEvent("right", 10, 50, 40)]
    elif change == "omit_events": events = None
    elif change == "model": receipt["model_sha256"] = "changed"
    elif change == "code": receipt["code"]["source_sha256"] = "changed"
    elif change == "role": receipt["role"] = "development"
    else: receipt["source_sha256"] = file_digest(experiment["source"])
    with pytest.raises(ValueError): evaluate(rows, config, detected_blinks=events)


def test_raw_calibration_material_cannot_be_reused_for_validation(experiment, tmp_path):
    manager = experiment["manager"]
    raw = tmp_path / "C-recording.bin"; raw.write_bytes(b"authorized synthetic C material")
    manager.register_materials([raw])
    manager.register_materials([raw])  # idempotent, no names/paths in profile
    assert len(manager.source_materials) == 1 and str(raw) not in json.dumps(manager.to_dict())
    path = tmp_path / "C-profile.json"; manager.save(path)
    experiment["d"].reproducibility["calibration"] = manager.to_dict()
    plan = FrozenExperiment.create(path, [experiment["d"]], experiment["model"])
    with pytest.raises(ValueError): plan.validate_source(raw, "validation")
    assert CalibrationManager.load(path).to_dict() == manager.to_dict()
    experiment["d"].reproducibility["source_sha256"] = file_digest(raw)
    with pytest.raises(ValueError): FrozenExperiment.create(path, [experiment["d"]], experiment["model"])


def test_managed_snapshot_omits_external_paths_by_default(experiment, tmp_path):
    session = experiment["d"]; session.video_path = experiment["source"]
    store = SessionStore(tmp_path / "private-sessions")
    folder = store.save(session)
    raw = (folder / "manifest.json").read_text(encoding="utf-8")
    assert str(session.measurement_path) not in raw and str(session.video_path) not in raw
    assert SessionStore(store.root).load(folder).video_path is None
    explicit = store.save(session, include_external_paths=True)
    assert store.load(explicit).video_path == session.video_path
    measurements = folder / "measurements.csv"
    measurements.write_text(measurements.read_text(encoding="utf-8").replace("1.0", "75.0"), encoding="utf-8")
    with pytest.raises(ValueError, match="Snapshotul"): store.load(folder)


def test_final_api_cannot_relabel_calibration_sources(experiment):
    from audience_analysis.validation import evaluate
    receipt = make_receipt(experiment["plan"], "V01", "validation", experiment["path"])
    config = experiment["plan"].validation_config({"experiment_id": "TEST", "session_id": "V01", "final_evaluation": True, "processing_provenance": receipt})
    config["calibration_session_ids"] = ["OTHER"]
    with pytest.raises(ValueError): evaluate(experiment["d"].rows, config)


def test_calibration_checks_sidecar_role_data_model_and_raw_material(experiment):
    path = experiment["path"]
    sidecar = Path(str(path) + ".experiment.json")
    receipt = {"role": "validation", "session_id": "V01", "measurement_content_sha256": measurement_digest(load_rows(path)),
               "model_sha256": file_digest(experiment["model"]), "source_sha256": file_digest(experiment["source"])}
    sidecar.write_text(json.dumps(receipt))
    with pytest.raises(ValueError): experiment["manager"].register_measurement_source(path)
    receipt.update(role="calibration", session_id="C01")
    sidecar.write_text(json.dumps(receipt))
    assert experiment["manager"].register_measurement_source(path)
    assert experiment["manager"].model_sha256 == receipt["model_sha256"]
    assert experiment["manager"].source_materials == [{"kind": "raw", "sha256": receipt["source_sha256"]}]
    with pytest.raises(ValueError): experiment["manager"].bind_model_hash("0" * 64)
    receipt["measurement_content_sha256"] = "changed"
    sidecar.write_text(json.dumps(receipt))
    with pytest.raises(ValueError): experiment["manager"].register_measurement_source(path)
