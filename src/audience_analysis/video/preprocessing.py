
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..config import SequenceConfig
from ..contracts import Status

# Modelul este în audience_analysis/assets (package-data din pyproject), nu în video/.
DEFAULT_DETECTOR_PATH = Path(__file__).resolve().parent.parent / "assets" / "face_detection_yunet_2023mar.onnx"


def prepare_bgr(image: np.ndarray, config: SequenceConfig) -> np.ndarray:
    """Pregătește un decupaj BGR pentru model, o singură dată; redimensionare nearest în NumPy."""
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) < 1:
        raise ValueError("Decupajul trebuie să fie BGR uint8")
    rows = np.linspace(0, image.shape[0]-1, config.height).astype(int)
    columns = np.linspace(0, image.shape[1]-1, config.width).astype(int)
    rgb = image[rows[:, None], columns[None, :], ::-1].astype(np.float32)
    rgb *= config.scale
    rgb = (rgb - np.asarray(config.mean, np.float32)) / np.asarray(config.std, np.float32)
    return np.ascontiguousarray(rgb.transpose(2, 0, 1))


@dataclass(frozen=True)
class FaceDetection:
    """Rezultatul detecției pentru UN cadru: toate fețele găsite."""
    status: Status
    boxes: tuple[tuple[int, int, int, int], ...]
    crops: tuple[np.ndarray | None, ...] = ()

    @property
    def crop(self) -> np.ndarray | None:
        """Compatibilitate: decupajul primei fețe analizabile, sau None."""
        return next((crop for crop in self.crops if crop is not None), None)


def select_faces(image: np.ndarray, boxes, *, min_face_pixels: int = 40, crop_margin: float = 0.15) -> FaceDetection:
    """Păstrează TOATE fețele dintr-un cadru; NumPy pur, deci testabilă fără OpenCV sau model."""
    height, width = image.shape[:2]
    clean, crops = [], []
    for x, y, w, h in boxes:
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(width, int(x) + int(w)), min(height, int(y) + int(h))
        if x1 - x0 < 1 or y1 - y0 < 1:
            continue
        w, h = x1 - x0, y1 - y0
        clean.append((x0, y0, w, h))
        crop = None
        if min(w, h) >= min_face_pixels:
            margin = int(max(w, h) * crop_margin)
            region = image[max(0, y0-margin):min(height, y1+margin), max(0, x0-margin):min(width, x1+margin)]
            if region.size:
                crop = np.ascontiguousarray(region)
        crops.append(crop)
    if not clean:
        return FaceDetection(Status.NO_FACE, ())
    status = Status.OK if any(crop is not None for crop in crops) else Status.LOW_QUALITY
    return FaceDetection(status, tuple(clean), tuple(crops))


def select_face(image: np.ndarray, boxes, **kwargs) -> FaceDetection:
    """Nume vechi, păstrat pentru compatibilitate; acum întoarce toate fețele (vezi select_faces)."""
    return select_faces(image, boxes, **kwargs)


class FaceDetector:
    """Detector de fețe YuNet (OpenCV). O instanță per lucrător: detectorul nu este sigur între fire."""
    INPUT_SIZE = 320  # identic cu preprocesarea lui P1 (assets/README.md); nu se schimbă fără acordul lui P1

    def __init__(self, model_path: str | Path = DEFAULT_DETECTOR_PATH, *, min_face_pixels: int = 40,
                 crop_margin: float = 0.15, score_threshold: float = 0.8):
        import cv2  # import leneș
        model_path = Path(model_path)
        if not model_path.is_file():
            raise FileNotFoundError(f"Lipsește modelul de detecție: {model_path.name}")
        self._cv2 = cv2
        self.min_face_pixels, self.crop_margin = min_face_pixels, crop_margin
        side = self.INPUT_SIZE
        self._detector = cv2.FaceDetectorYN.create(str(model_path), "", (side, side), score_threshold, 0.3, 5000)

    def detect(self, image: np.ndarray) -> FaceDetection:
        """Detectează toate fețele dintr-un cadru."""
        cv2 = self._cv2
        if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) < 1:
            raise ValueError("Intrarea trebuie să fie BGR uint8")
        side = self.INPUT_SIZE
        height, width = image.shape[:2]
        scale = side / max(height, width)
        resized = cv2.resize(image, (max(1, round(width*scale)), max(1, round(height*scale))))
        padded = np.zeros((side, side, 3), np.uint8)
        padded[:resized.shape[0], :resized.shape[1]] = resized
        _, faces = self._detector.detect(padded)
        boxes = [] if faces is None else np.rint(faces[:, :4] / scale).astype(int).tolist()
        return select_faces(image, boxes, min_face_pixels=self.min_face_pixels, crop_margin=self.crop_margin)


def detect_real_face(image: np.ndarray, detector: FaceDetector) -> FaceDetection:
    """P2-S3.1: scurtătură pentru detector.detect(image); întoarce toate casetele + decupajele analizabile."""
    return detector.detect(image)