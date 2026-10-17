"""R1 and R2 share the frozen MobileNetV3 Small image encoder."""
from dataclasses import asdict
import hashlib
import time

import numpy as np
import torch
from torch import nn
from torchvision.models import mobilenet_v3_small, MobileNet_V3_Small_Weights

from .legacy_contracts import LABELS, PipelineConfig, PredictionResult, Status
from .preprocessing import normalize


class EngagementModel(nn.Module):
    def __init__(self, architecture="mean", hidden_size=128, pretrained=False):
        super().__init__()
        if architecture not in {"mean", "gru"}:
            raise ValueError("Arhitectură necunoscută")
        base = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.DEFAULT if pretrained else None)
        self.encoder = nn.Sequential(base.features, base.avgpool, nn.Flatten())
        self.encoder.requires_grad_(False)
        self.architecture = architecture
        self.hidden_size = hidden_size
        self.temporal = nn.GRU(576, hidden_size, batch_first=True) if architecture == "gru" else None
        self.classifier = nn.Linear(hidden_size if self.temporal else 576, 4)

    def train(self, mode=True):
        super().train(mode)
        self.encoder.eval()  # Frozen BatchNorm must not update on training batches.
        return self

    def encode(self, frames):
        b, t, c, h, w = frames.shape
        with torch.no_grad():
            return self.encoder(frames.reshape(b*t, c, h, w)).reshape(b, t, 576)

    def classify(self, features):
        if self.temporal is None:
            pooled = features.mean(dim=1)
        else:
            _, hidden = self.temporal(features)
            pooled = hidden[-1]
        return self.classifier(pooled)

    def forward(self, frames):
        return self.classify(self.encode(frames))


def save_bundle(path, model, config, training, reference_frames=None):
    if not training.get("trained"):
        raise ValueError("Exportul necesită un model antrenat")
    bundle = {
        "format_version": 1, "architecture": model.architecture,
        "hidden_size": model.hidden_size, "labels": list(LABELS),
        "pipeline": asdict(config), "state_dict": model.cpu().state_dict(),
        "training": training,
    }
    if reference_frames is not None:
        reference = torch.from_numpy(normalize(reference_frames))[None]
        with torch.inference_mode():
            bundle["reference_input"] = reference
            bundle["reference_output"] = model.eval()(reference)
    torch.save(bundle, path)


class Predictor:
    def __init__(self, path):
        # Only tensor/primitive deserialization: never unpickle arbitrary model objects.
        bundle = torch.load(path, map_location="cpu", weights_only=True)
        if bundle.get("format_version") != 1 or bundle.get("labels") != list(LABELS):
            raise ValueError("Format sau ordine a etichetelor incompatibilă")
        if not bundle.get("training", {}).get("trained"):
            raise ValueError("Modelul nu este marcat ca antrenat")
        self.config = PipelineConfig(**bundle["pipeline"])
        self.model = EngagementModel(bundle["architecture"], bundle["hidden_size"])
        self.model.load_state_dict(bundle["state_dict"], strict=True)
        self.model.eval()
        with open(path, "rb") as handle:
            self.version = hashlib.file_digest(handle, "sha256").hexdigest()[:16]
        self.reference_verified = False
        if "reference_input" in bundle:
            with torch.inference_mode():
                output = self.model(bundle["reference_input"])
            torch.testing.assert_close(output, bundle["reference_output"], rtol=1e-4, atol=1e-5)
            self.reference_verified = True

    def predict(self, batch):
        started = time.perf_counter()
        expected = (self.config.frames, self.config.image_size, self.config.image_size, 3)
        if batch.frames.shape != expected:
            raise ValueError("Secvență incompatibilă cu modelul")
        with torch.inference_mode():
            logits = self.model(torch.from_numpy(normalize(batch.frames))[None])
            scores = logits.softmax(dim=-1)[0].tolist()
        if not np.isfinite(scores).all():
            raise ValueError("Ieșire numerică invalidă")
        return PredictionResult(batch.source_id, batch.participant_id, batch.generation,
                                batch.start, batch.end, Status.READY, int(np.argmax(scores)), scores,
                                self.version, (time.perf_counter()-started)*1000)

