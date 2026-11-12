"""Statistică locală de expresie pentru un cadru BGR, încărcată la cerere."""
from dataclasses import dataclass
from threading import Lock

import numpy as np


MODEL_ID = "jihedjabnoun/vit-face-emotion-recognition"
EXPECTED_LABELS = {"Anger", "Disgust", "Fear", "Happiness", "Neutral", "Sadness", "Surprise"}
_predictor: "EmotionStatisticsModel | None" = None
_predictor_lock = Lock()


class ModelStatisticsError(RuntimeError):
    """Modelul nu poate fi folosit local."""


@dataclass(frozen=True)
class FrameStatistics:
    label: str
    confidence: float
    probabilities: dict[str, float]


class EmotionStatisticsModel:
    """Încarcă modelul o singură dată și produce distribuția softmax completă."""

    def __init__(self, model_id: str = MODEL_ID):
        try:
            import torch
            from PIL import Image
            from transformers import AutoImageProcessor, AutoModelForImageClassification
        except ImportError as error:
            raise ModelStatisticsError("Lipsesc dependențe pentru model. Instalează extra [model].") from error
        self.torch = torch
        self.Image = Image
        self.model_id = model_id
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        try:
            self.processor = AutoImageProcessor.from_pretrained(model_id)
            self.model = AutoModelForImageClassification.from_pretrained(model_id).to(self.device).eval()
        except (OSError, RuntimeError, ValueError) as online_error:
            try:
                self.processor = AutoImageProcessor.from_pretrained(model_id, local_files_only=True)
                self.model = AutoModelForImageClassification.from_pretrained(model_id, local_files_only=True).to(self.device).eval()
            except (OSError, RuntimeError, ValueError) as cache_error:
                raise ModelStatisticsError(
                    "Modelul nu a putut fi încărcat. La prima rulare verifică internetul și spațiul pe disc; "
                    "după descărcare va fi reutilizat din cache local."
                ) from cache_error
        mapping = getattr(self.model.config, "id2label", None)
        if not isinstance(mapping, dict):
            raise ModelStatisticsError("Configurația modelului nu include id2label.")
        try:
            self.labels = tuple(str(mapping[index]) for index in range(len(mapping)))
        except KeyError as error:
            raise ModelStatisticsError("Etichetele modelului nu au indexuri consecutive.") from error
        if set(self.labels) != EXPECTED_LABELS:
            raise ModelStatisticsError(f"Etichete neașteptate: {', '.join(self.labels)}")

    def predict_bgr(self, frame_bgr: np.ndarray) -> FrameStatistics:
        if frame_bgr.dtype != np.uint8 or frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
            raise ValueError("Modelul necesită un cadru BGR uint8 cu trei canale.")
        rgb = frame_bgr[:, :, ::-1]
        image = self.Image.fromarray(rgb, mode="RGB")
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {name: value.to(self.device) for name, value in inputs.items()}
        with self.torch.inference_mode():
            logits = self.model(**inputs).logits
            scores = self.torch.softmax(logits, dim=-1)[0].detach().cpu().tolist()
        if len(scores) != len(self.labels) or not np.isfinite(scores).all():
            raise ModelStatisticsError("Modelul a întors probabilități invalide.")
        probabilities = {label: float(scores[index]) for index, label in enumerate(self.labels)}
        label = max(probabilities, key=probabilities.get)
        return FrameStatistics(label, probabilities[label], probabilities)


def get_statistics_model() -> EmotionStatisticsModel:
    global _predictor
    with _predictor_lock:
        if _predictor is None:
            _predictor = EmotionStatisticsModel()
        return _predictor
