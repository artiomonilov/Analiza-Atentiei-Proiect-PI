"""Format P1 versionat; state_dict local și metadate, fără model pickled sau download."""
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

from ..config import SequenceConfig
from .data import DIMENSIONS


def sha256(path):
    with Path(path).open("rb") as stream: return hashlib.file_digest(stream, "sha256").hexdigest()


def is_hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def validate_manifest(metadata):
    required = {"schema_version", "architecture", "hidden_size", "dimensions", "labels", "sequence", "weights_sha256", "model_version", "training", "evaluation"}
    if not isinstance(metadata, dict) or set(metadata) != required or type(metadata["schema_version"]) is not int or metadata["schema_version"] != 1:
        raise ValueError("Manifest P1 incompatibil.")
    dimensions = metadata["dimensions"]
    if not isinstance(dimensions, list) or not dimensions or dimensions != [d for d in DIMENSIONS if d in dimensions]:
        raise ValueError("Ordinea dimensiunilor este incompatibilă.")
    if metadata["architecture"] not in {"mean", "gru"} or type(metadata["hidden_size"]) is not int or metadata["hidden_size"] < 1:
        raise ValueError("Arhitectură incompatibilă.")
    if metadata["labels"] != {d: [0, 1, 2, 3] for d in dimensions} or any(type(v) is not int for labels in metadata["labels"].values() for v in labels) or not isinstance(metadata["model_version"], str) or not metadata["model_version"].strip() or not is_hash(metadata["weights_sha256"]):
        raise ValueError("Clase/versiune/weights incompatibile.")
    if not isinstance(metadata["training"], dict) or metadata["training"].get("trained") is not True:
        raise ValueError("Lipsește dovada declarată a antrenării.")
    evidence = metadata["evaluation"]
    if not isinstance(evidence, dict) or evidence.get("split") != "validation" or evidence.get("validated") is not True or type(evidence.get("samples")) is not int or evidence["samples"] < 1:
        raise ValueError("Lipsește evaluarea pe validation.")
    if not all(is_hash(evidence.get(k)) for k in ("report_sha256", "dataset_sha256")):
        raise ValueError("Lipsește proveniența evaluării.")
    if metadata["training"].get("manifest_sha256") != evidence["dataset_sha256"]:
        raise ValueError("Datele declarate pentru model și evaluare nu corespund.")
    return SequenceConfig(**metadata["sequence"])


@dataclass
class LoadedModel:
    manifest: dict
    model: object
    torch: object

    def predict_logits(self, frames):
        with self.torch.inference_mode():
            value = self.model(self.torch.from_numpy(frames.copy())[None])
        if not isinstance(value, dict): value = {"engagement": value}
        return {key: tensor[0].detach().cpu().numpy() for key, tensor in value.items()}


def load_package(directory):
    directory = Path(directory)
    metadata = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    validate_manifest(metadata)
    weights = directory / "weights.pt"
    if sha256(weights) != metadata["weights_sha256"]: raise ValueError("Weights diferite de manifest.")
    import torch
    from .models import build_model
    state = torch.load(weights, map_location="cpu", weights_only=True)
    model = build_model(metadata["architecture"], hidden_size=metadata["hidden_size"], dimensions=metadata["dimensions"])
    model.load_state_dict(state, strict=True)
    model.cpu().eval()
    return LoadedModel(metadata, model, torch)


def export_package(directory, model, config, *, training, evaluation):
    """Exportă doar modelul furnizat de apelant; nu creează/antrenează ponderi."""
    metadata = {"schema_version": 1, "architecture": model.architecture, "hidden_size": model.hidden_size,
        "dimensions": list(getattr(model, "dimensions", ("engagement",))), "sequence": asdict(config),
        "weights_sha256": "0" * 64, "model_version": "pending-export", "training": training, "evaluation": evaluation}
    metadata["labels"] = {d: [0, 1, 2, 3] for d in metadata["dimensions"]}
    validate_manifest(metadata)
    import torch
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=False)
    torch.save({name: tensor.detach().cpu() for name, tensor in model.state_dict().items()}, directory / "weights.pt")
    metadata["weights_sha256"] = sha256(directory / "weights.pt")
    metadata["model_version"] = metadata["weights_sha256"]
    (directory / "manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False), encoding="utf-8")
    return metadata
