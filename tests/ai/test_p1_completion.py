"""Fixture-uri de date și backends mock explicite; nu generează ponderi."""
from dataclasses import asdict
import json
from types import SimpleNamespace

import numpy as np
import pytest

from audience_analysis.ai.data import load_training_manifest, prepare_sequence, load_prepared_sequence, iter_samples
from audience_analysis.ai.evaluation import majority_class, compare_models, choose_on_validation
from audience_analysis.ai.package import validate_manifest, load_package, export_package
from audience_analysis.ai.predictor import RealPredictor, ModelUnavailableError
from audience_analysis.contracts import PreparedSequence, Status


def metadata(config):
    return {"schema_version": 1, "architecture": "mean", "hidden_size": 128, "dimensions": ["engagement"],
        "labels": {"engagement": [0, 1, 2, 3]}, "sequence": asdict(config), "weights_sha256": "0" * 64,
        "model_version": "TEST_BACKEND_ONLY_NOT_A_MODEL", "training": {"trained": True, "purpose": "mock metadata only", "manifest_sha256": "2" * 64},
        "evaluation": {"validated": True, "split": "validation", "samples": 2, "report_sha256": "1" * 64, "dataset_sha256": "2" * 64}}


def manifest(tmp_path, records):
    path = tmp_path / "manifest.csv"
    path.write_text("clip_id,participant_id,path,split,engagement,boredom\n" + "\n".join(records), encoding="utf-8")
    return path


def test_manifest_optional_labels_and_disjoint_participants(tmp_path):
    (tmp_path / "a.npz").write_bytes(b"synthetic cache A")
    (tmp_path / "b.npz").write_bytes(b"synthetic cache B")
    path = manifest(tmp_path, ["A,P1,a.npz,train,2,", "B,P2,b.npz,validation,1,0"])
    rows = load_training_manifest(path)
    assert rows[0]["labels"] == {"engagement": 2}
    assert rows[1]["labels"] == {"engagement": 1, "boredom": 0}


@pytest.mark.parametrize("rows", [
    ["A,P1,a,train,2,", "B,P1,b,test,1,"],
    ["A,P1,a,train,2,", "A,P2,b,test,1,"],
    ["A,P1,a,train,2,", "B,P2,a,test,1,"],
    ["A,P1,a,train,4,"], ["A,P1,a,train,,"], ["A,P1,a,train,1,-1"],
    ["A,P1,a,unknown,1,"], [",P1,a,train,1,"], ["A,,a,train,1,"]])
def test_manifest_invalid_labels_duplicates_and_leakage(tmp_path, rows):
    with pytest.raises(ValueError): load_training_manifest(manifest(tmp_path, rows), verify_files=False)


def test_manifest_missing_and_duplicate_content(tmp_path):
    path = manifest(tmp_path, ["A,P1,a,train,1,"])
    with pytest.raises(FileNotFoundError): load_training_manifest(path)
    (tmp_path / "a").write_bytes(b"same content")
    (tmp_path / "b").write_bytes(b"same content")
    path = manifest(tmp_path, ["A,P1,a,train,1,", "B,P2,b,test,0,"])
    with pytest.raises(ValueError, match="Conținut"): load_training_manifest(path)


def test_preparation_cache_and_inference_do_not_normalize_twice(config, tmp_path):
    frames = np.zeros((config.frames, 12, 15, 3), np.uint8); frames[..., 2] = 255
    sequence = prepare_sequence(frames, np.linspace(0, .6, config.frames), config)
    assert sequence.frames[:, 0].min() == 1 and sequence.frames[:, 2].max() == 0
    path = tmp_path / "cache.npz"
    np.savez(path, frames=sequence.frames, sample_times_s=sequence.sample_times_s, preprocessing_id=config.preprocessing_id)
    restored = load_prepared_sequence(path, config)
    np.testing.assert_array_equal(restored.frames, sequence.frames)
    records = [{"clip_id": "A", "split": "train", "labels": {"engagement": 2}, "path": path}]
    assert next(iter_samples(records, config, split="train"))[2] == 2
    assert list(iter_samples(records, config, split="train", dimension="boredom")) == []
    seen = []
    backend = SimpleNamespace(manifest=metadata(config), predict_logits=lambda x: (seen.append(x.copy()) or {"engagement": np.array([0, 1, 2, 3])}))
    loads = []
    predictor = RealPredictor("mock-only", config, loader=lambda p: (loads.append(p) or backend))
    assert predictor.predict(restored).levels == {"engagement": 3}
    assert predictor.predict(restored).is_demo is False and len(loads) == 1
    np.testing.assert_array_equal(seen[0], sequence.frames)


@pytest.mark.parametrize("change", ["order", "untrained", "unvalidated", "split", "shape", "version", "hash"])
def test_invalid_package_metadata_is_unavailable(config, change):
    data = metadata(config)
    if change == "order": data["labels"]["engagement"] = [3, 2, 1, 0]
    elif change == "untrained": data["training"]["trained"] = False
    elif change == "unvalidated": data["evaluation"]["validated"] = False
    elif change == "split": data["evaluation"]["split"] = "test"
    elif change == "shape": data["sequence"]["frames"] += 1
    elif change == "version": data["schema_version"] = 77
    else: data["weights_sha256"] = "bad"
    with pytest.raises(ModelUnavailableError) as exc:
        RealPredictor("mock-only", config, loader=lambda _: SimpleNamespace(manifest=data))
    assert exc.value.status == Status.MODEL_UNAVAILABLE


@pytest.mark.parametrize("logits", [{"engagement": [0, 1, 2]}, {"engagement": [0, 1, 2, float('nan')]}, {"unknown": [0, 1, 2, 3]}])
def test_predictor_rejects_incompatible_outputs(config, sequence, logits):
    backend = SimpleNamespace(manifest=metadata(config), predict_logits=lambda _: logits)
    with pytest.raises(ValueError): RealPredictor("mock-only", config, loader=lambda _: backend).predict(sequence)


def test_safe_package_load_uses_hash_and_tensor_only_deserialization(config, tmp_path, monkeypatch):
    import sys
    import audience_analysis.ai.package as module
    import audience_analysis.ai.models as factories
    (tmp_path / "manifest.json").write_text(json.dumps(metadata(config)))
    with pytest.raises(FileNotFoundError): load_package(tmp_path)  # no weights manufactured
    calls = []
    model = SimpleNamespace(load_state_dict=lambda state, strict: calls.append((state, strict)))
    model.cpu = lambda: model; model.eval = lambda: model
    monkeypatch.setattr(module, "sha256", lambda _: "0" * 64)
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(load=lambda *a, **k: (calls.append(k) or {})))
    monkeypatch.setattr(factories, "build_model", lambda *a, **k: model)
    assert load_package(tmp_path).model is model
    assert calls[0] == {"map_location": "cpu", "weights_only": True} and calls[1] == ({}, True)
    monkeypatch.setattr(module, "sha256", lambda _: "3" * 64)
    with pytest.raises(ValueError, match="Weights"): load_package(tmp_path)


def test_export_requires_evidence_before_creating_any_weights(config, tmp_path):
    model = SimpleNamespace(architecture="mean", hidden_size=128)
    with pytest.raises(ValueError): export_package(tmp_path / "not-created", model, config, training={"trained": False}, evaluation={})
    assert not (tmp_path / "not-created").exists()


def test_majority_and_mean_gru_compare_use_same_observable_subset():
    report = compare_models([0, 2, 2, 3], [0, 1, 2, 3], {"mean": [0, 1, None, 3], "gru": [0, 0, 2, 3]}, data_kind="synthetic")
    assert report["majority_class_from_train"] == 2 and majority_class([1, 0]) == 0
    assert report["common_indices"] == [0, 1, 3]
    assert report["models"]["mean"]["n"] == report["models"]["gru"]["n"] == report["R0"]["n"] == 3
    assert report["coverage"]["mean"] == .75 and choose_on_validation(report) == "mean"
    report["split"] = "test"
    with pytest.raises(ValueError): choose_on_validation(report)


def test_comparison_no_data_is_na_and_invalid_classes_are_rejected():
    report = compare_models([1], [0], {"mean": [None], "gru": [None]})
    assert report["models"]["mean"] is None and report["R0"] is None
    with pytest.raises(ValueError): compare_models([1], [0], {"mean": [True]})
    with pytest.raises(ValueError): majority_class([])


def test_optional_model_factories_reuse_legacy_without_downloads():
    pytest.importorskip("torchvision", reason="Backend real opțional; necesită mediul izolat [ai].")
    import torch
    from audience_analysis.ai.models import build_model
    torch.set_num_threads(1)
    with torch.inference_mode():
        for architecture in ("mean", "gru"):
            model = build_model(architecture, dimensions=("engagement", "boredom", "confusion", "frustration")).eval()
            output = model(torch.zeros(1, 2, 3, 32, 32))
            assert set(output) == {"engagement", "boredom", "confusion", "frustration"}
            assert all(value.shape == (1, 4) for value in output.values())


def test_imagenet_training_inference_preprocessing_parity():
    pytest.importorskip("cv2")
    from audience_analysis.config import SequenceConfig
    from audience_analysis.preprocessing import normalize
    config = SequenceConfig(frames=2, height=32, width=32, mean=(.485, .456, .406), std=(.229, .224, .225))
    raw = np.random.default_rng(37).integers(0, 256, (2, 32, 32, 3), dtype=np.uint8)
    actual = prepare_sequence(raw, (0., .6), config)
    expected = normalize(raw[..., ::-1])  # legacy train: crop-ul este RGB uint8
    np.testing.assert_allclose(actual.frames, expected, rtol=1e-6, atol=1e-6)


def test_p1_cli_reports_missing_model_and_comparison_without_loading_torch(config, tmp_path, capsys):
    from audience_analysis.ai.cli import main
    assert main(["inspect-model", str(tmp_path / "missing")]) == 4
    assert json.loads(capsys.readouterr().out)["levels"] is None
    inputs = tmp_path / "comparison.json"
    inputs.write_text(json.dumps({"training_labels": [0, 1, 1], "targets": [0, 1], "predictions": {"mean": [0, 1], "gru": [1, 1]}, "data_kind": "synthetic"}))
    output = tmp_path / "report.json"
    assert main(["compare", str(inputs), "--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["data_kind"] == "synthetic"


def test_predictor_rejects_wrong_temporal_span_before_inference(config, sequence):
    backend = SimpleNamespace(manifest=metadata(config), predict_logits=lambda _: pytest.fail("nu se apelează modelul"))
    invalid = PreparedSequence(sequence.frames, tuple(np.linspace(0, .03, config.frames)), config.preprocessing_id)
    with pytest.raises(ValueError, match="Durata"):
        RealPredictor("mock-only", config, loader=lambda _: backend).predict(invalid)
