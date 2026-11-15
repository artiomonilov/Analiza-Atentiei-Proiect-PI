"""MediaPipe Tasks IMAGE/VIDEO: landmarks, blendshapes și matrice facială."""
from dataclasses import dataclass
from pathlib import Path

import numpy as np


class FaceLandmarkerError(RuntimeError):
    """Inițializarea sau inferența MediaPipe a eșuat."""


@dataclass(frozen=True)
class Landmark:
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class Blendshape:
    name: str
    score: float


@dataclass(frozen=True)
class FaceLandmarks:
    landmarks: tuple[Landmark, ...]
    blendshapes: tuple[Blendshape, ...]
    transformation_matrix: np.ndarray | None


@dataclass(frozen=True)
class LandmarkerResult:
    faces: tuple[FaceLandmarks, ...]


def validate_bgr(image: np.ndarray) -> None:
    if (not isinstance(image, np.ndarray) or image.dtype != np.uint8
            or image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) == 0):
        raise ValueError("Imaginea trebuie să fie BGR uint8, nevidă, cu trei canale.")


class FaceLandmarker:
    """O singură instanță reutilizabilă; folosește with sau close() la final.

    Coordonatele landmarks sunt normalizate în convenția MediaPipe. Matricea
    este o transformare facială 4x4, nu o măsurare a privirii sau a atenției.
    """

    def __init__(self, model_path: Path, *, mode: str = "IMAGE"):
        if mode not in {"IMAGE", "VIDEO"}:
            raise ValueError("Modul Face Landmarker trebuie să fie IMAGE sau VIDEO.")
        model_path = Path(model_path)
        if not model_path.is_file():
            raise FileNotFoundError(f"Modelul Face Landmarker nu există: {model_path}")
        try:
            import mediapipe as mp
            options = mp.tasks.vision.FaceLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path.resolve())),
                running_mode=getattr(mp.tasks.vision.RunningMode, mode),
                num_faces=1,
                output_face_blendshapes=True,
                output_facial_transformation_matrixes=True,
            )
            self._mp = mp
            self._landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            raise FaceLandmarkerError(f"Inițializarea Face Landmarker a eșuat: {error}") from error
        self._closed = False
        self.mode = mode
        self._last_timestamp_ms = -1

    def process(self, image_bgr: np.ndarray) -> LandmarkerResult:
        if self.mode != "IMAGE":
            raise FaceLandmarkerError("Instanța VIDEO necesită process_video și timestamp_ms.")
        return self._process(image_bgr)

    def process_video(self, image_bgr: np.ndarray, timestamp_ms: int) -> LandmarkerResult:
        if self.mode != "VIDEO":
            raise FaceLandmarkerError("process_video necesită o instanță VIDEO.")
        if type(timestamp_ms) is not int or timestamp_ms < 0 or timestamp_ms <= self._last_timestamp_ms:
            raise ValueError("Timestampurile VIDEO trebuie să fie întregi, nenegative și strict crescătoare.")
        return self._process(image_bgr, timestamp_ms)

    def _process(self, image_bgr: np.ndarray, timestamp_ms: int | None = None) -> LandmarkerResult:
        validate_bgr(image_bgr)
        if self._closed:
            raise FaceLandmarkerError("Face Landmarker este deja închis.")
        # Copie contiguă: inversarea canalelor produce altfel strides negative.
        rgb = np.ascontiguousarray(image_bgr[:, :, ::-1])
        try:
            image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
            if timestamp_ms is None:
                raw = self._landmarker.detect(image)
            else:
                self._last_timestamp_ms = timestamp_ms
                raw = self._landmarker.detect_for_video(image, timestamp_ms)
        except (RuntimeError, ValueError) as error:
            raise FaceLandmarkerError(f"Procesarea Face Landmarker a eșuat: {error}") from error
        faces = []
        for index, points in enumerate(raw.face_landmarks):
            categories = raw.face_blendshapes[index] if index < len(raw.face_blendshapes) else []
            matrix = None
            if index < len(raw.facial_transformation_matrixes):
                matrix = np.array(raw.facial_transformation_matrixes[index], dtype=float, copy=True).reshape(4, 4)
                matrix.setflags(write=False)
            faces.append(FaceLandmarks(
                tuple(Landmark(float(point.x), float(point.y), float(point.z)) for point in points),
                tuple(Blendshape(item.category_name or "", float(item.score)) for item in categories),
                matrix,
            ))
        return LandmarkerResult(tuple(faces))

    def close(self) -> None:
        if not self._closed:
            self._landmarker.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()


def load_image(path: Path) -> np.ndarray:
    """Citire BGR inclusiv din căi Unicode pe Windows."""
    import cv2
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Imaginea nu există: {path}")
    encoded = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR) if encoded.size else None
    if image is None:
        raise ValueError(f"Imaginea nu poate fi decodată: {path}")
    return image


def draw_landmarks(image_bgr: np.ndarray, result: LandmarkerResult) -> np.ndarray:
    import cv2
    validate_bgr(image_bgr)
    annotated = image_bgr.copy()
    height, width = annotated.shape[:2]
    for face in result.faces:
        for point in face.landmarks:
            x, y = int(point.x * width), int(point.y * height)
            if 0 <= x < width and 0 <= y < height:
                cv2.circle(annotated, (x, y), 1, (0, 255, 0), -1)
    return annotated


def save_image(path: Path, image_bgr: np.ndarray) -> None:
    import cv2
    validate_bgr(image_bgr)
    path = Path(path)
    try:
        ok, encoded = cv2.imencode(path.suffix, image_bgr)
    except cv2.error as error:
        raise ValueError(f"Formatul imaginii de ieșire nu este acceptat: {path.suffix}") from error
    if not ok:
        raise RuntimeError("Imaginea adnotată nu a putut fi codificată.")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded.tofile(path)
