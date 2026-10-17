"""CLI shared by local runs and Colab notebooks. No data or metrics are invented."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys

import numpy as np

from .legacy_contracts import PipelineConfig
from .dataset import audit_manifest, extract_clip, read_manifest
from .metrics import classification_metrics


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare(args):
    config = PipelineConfig(**json.loads(Path(args.config).read_text(encoding="utf-8")))
    audit = audit_manifest(args.manifest)
    if audit["missing_files"] or audit["duplicate_content"]:
        raise ValueError("Auditul a găsit fișiere lipsă sau conținut duplicat; rulează audit și corectează manifestul")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    rows = read_manifest(args.manifest)
    results = []
    for index, row in enumerate(rows):
        batch, reasons = extract_clip(row, config)
        item = {k: v for k, v in row.items() if k != "path"}
        item["rejections"] = reasons
        item["accepted"] = batch is not None
        if batch is not None:
            name = hashlib.sha256(row["clip_id"].encode()).hexdigest()[:24] + ".npz"
            np.savez_compressed(out/name, frames=batch.frames)
            item.update(file=name, start=batch.start, end=batch.end)
        results.append(item)
        print(f"{index+1}/{len(rows)}: {'acceptat' if batch is not None else 'respins'}", flush=True)
    manifest_hash = hashlib.sha256(Path(args.manifest).read_bytes()).hexdigest()
    write_json(out/"index.json", {"pipeline": asdict(config), "manifest_sha256": manifest_hash, "rows": results,
                                 "unit": "first valid window per clip; maximum one accepted sample per clip"})


def load_cache(directory):
    directory = Path(directory)
    index = json.loads((directory/"index.json").read_text(encoding="utf-8"))
    return directory, index, PipelineConfig(**index["pipeline"])


def train(args):
    import torch
    from .models import EngagementModel, save_bundle
    from .preprocessing import normalize
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(args.threads)
    torch.use_deterministic_algorithms(True)
    directory, index, config = load_cache(args.cache)
    if args.epochs < 1:
        raise ValueError("Sunt necesare cel puțin o epocă și date reale")
    rows = {split: [r for r in index["rows"] if r["split"] == split and r["accepted"]] for split in ("train", "validation")}
    if any(not group for group in rows.values()):
        raise ValueError("Antrenarea necesită exemple acceptate atât în train, cât și în validation")
    model = EngagementModel(args.architecture, pretrained=True).eval()
    features, labels = {}, {}
    # Frozen features are small (~16*576 per clip); raw images are read per clip.
    for split, group in rows.items():
        encoded = []
        for row in group:
            with np.load(directory/row["file"], allow_pickle=False) as data:
                frames = torch.from_numpy(normalize(data["frames"]))[None]
            with torch.inference_mode():
                encoded.append(model.encode(frames)[0].clone())
        features[split] = torch.stack(encoded).clone()
        labels[split] = torch.tensor([r["engagement"] for r in group], dtype=torch.long)
    counts = torch.bincount(labels["train"], minlength=4)
    if (counts == 0).any():
        raise ValueError("Lipsesc clase din train după preprocesare; clarifică protocolul înainte de antrenare")
    weights = len(rows["train"])/(4*counts.float()) if args.class_weights else None
    loss_fn = torch.nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=args.lr)
    history, best_score, best_state = [], -1.0, None
    for epoch in range(args.epochs):
        model.train()
        order = torch.randperm(len(rows["train"]))
        total_loss = 0.0
        for indices in order.split(args.batch_size):
            optimizer.zero_grad()
            loss = loss_fn(model.classify(features["train"][indices]), labels["train"][indices])
            loss.backward()
            optimizer.step()
            total_loss += loss.item()*len(indices)
        model.eval()
        with torch.inference_mode():
            prediction = model.classify(features["validation"]).argmax(-1).tolist()
        metrics = classification_metrics(labels["validation"].tolist(), prediction)
        history.append({"epoch": epoch+1, "train_loss": total_loss/len(rows["train"]), "validation": metrics})
        print(f"Epoca {epoch+1}: validation macro-F1={metrics['macro_f1']:.4f}", flush=True)
        if metrics["macro_f1"] > best_score:
            best_score = metrics["macro_f1"]
            best_state = {name: tensor.detach().clone() for name, tensor in model.state_dict().items()}
            best_epoch = epoch+1
    model.load_state_dict(best_state)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True))
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = "unavailable", True
    training = {"trained": True, "seed": args.seed, "epochs": args.epochs, "best_epoch": best_epoch,
                "selection": "validation macro-F1", "lr": args.lr, "batch_size": args.batch_size,
                "class_weights": args.class_weights, "train_counts": counts.tolist(),
                "manifest_sha256": index["manifest_sha256"], "commit": commit, "dirty_worktree": dirty,
                "torch_version": str(torch.__version__), "encoder": "MobileNet_V3_Small_Weights.DEFAULT",
                "history": history}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # A synthetic parity input contains no person's image and tests serialization only.
    reference = np.random.default_rng(args.seed).integers(0, 256, (config.frames, config.image_size, config.image_size, 3), dtype=np.uint8)
    save_bundle(output, model, config, training, reference)
    write_json(output.with_suffix(".training.json"), training)


def evaluate(args):
    import torch
    from .models import Predictor
    from .legacy_contracts import SequenceBatch
    torch.set_num_threads(args.threads)
    directory, index, config = load_cache(args.cache)
    predictor = Predictor(args.model)
    if predictor.config != config:
        raise ValueError("Preprocesarea cache-ului diferă de cea a modelului")
    bundle = torch.load(args.model, map_location="cpu", weights_only=True)
    if bundle["training"]["manifest_sha256"] != index["manifest_sha256"]:
        raise ValueError("Modelul și cache-ul provin din manifesturi diferite")
    majority = int(np.argmax(bundle["training"]["train_counts"]))
    candidates = [r for r in index["rows"] if r["split"] == args.split]
    accepted = [r for r in candidates if r["accepted"]]
    if not accepted:
        raise ValueError("Nicio secvență evaluabilă în splitul ales")
    targets, predictions, durations, details = [], [], [], []
    for row in accepted:
        with np.load(directory/row["file"], allow_pickle=False) as data:
            batch = SequenceBatch(row["clip_id"], row["participant_id"], 0, row["start"], row["end"], data["frames"])
        result = predictor.predict(batch)
        targets.append(row["engagement"])
        predictions.append(result.label)
        durations.append(result.inference_ms)
        details.append({"clip_id": row["clip_id"], "target": row["engagement"], "prediction": result.label})
    rejected = [{"clip_id": r["clip_id"], "reasons": r["rejections"]} for r in candidates if not r["accepted"]]
    write_json(args.output, {"split": args.split, "model_version": predictor.version,
        "unit": index["unit"], "coverage": len(accepted)/len(candidates), "accepted": len(accepted), "total": len(candidates),
        "metrics_on_accepted_only": classification_metrics(targets, predictions),
        "R0_same_accepted_subset": classification_metrics(targets, [majority]*len(targets)),
        "latency_ms": {"median": float(np.median(durations)), "p95": float(np.percentile(durations, 95))},
        "reference_verified": predictor.reference_verified, "rejected": rejected, "predictions": details})


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Audit, preprocesare, antrenare și evaluare reproductibilă")
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("manifest")
    audit.add_argument("--output", default="reports/audit.json")
    prep = sub.add_parser("prepare")
    prep.add_argument("manifest")
    prep.add_argument("--config", default="configs/default.json")
    prep.add_argument("--output", default="artifacts/cache")
    training = sub.add_parser("train")
    training.add_argument("cache")
    training.add_argument("--architecture", choices=["mean", "gru"], required=True)
    training.add_argument("--output", required=True)
    training.add_argument("--epochs", type=int, default=20)
    training.add_argument("--seed", type=int, default=42)
    training.add_argument("--batch-size", type=int, default=32)
    training.add_argument("--lr", type=float, default=1e-3)
    training.add_argument("--class-weights", action="store_true")
    training.add_argument("--threads", type=int, default=4)
    evaluation = sub.add_parser("evaluate")
    evaluation.add_argument("cache")
    evaluation.add_argument("model")
    evaluation.add_argument("--split", choices=["validation", "test"], default="validation")
    evaluation.add_argument("--threads", type=int, default=4)
    evaluation.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        if args.command == "audit":
            report = audit_manifest(args.manifest)
            write_json(args.output, report)
            if report["missing_files"] or report["duplicate_content"]:
                return 2
        elif args.command == "prepare":
            prepare(args)
        elif args.command == "train":
            if args.batch_size < 1 or args.lr <= 0 or args.threads < 1:
                raise ValueError("Parametri de antrenare invalizi")
            train(args)
        else:
            evaluate(args)
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(2, f"Experiment oprit: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
