"""Detecție locală de față și orientare cap opțională prin MediaPipe."""
from dataclasses import dataclass
from math import atan2, degrees, sqrt
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class FaceDetection:
    count: int
    box: tuple[int, int, int, int] | None
    crop_bgr: np.ndarray | None


@dataclass(frozen=True)
class AttentionEstimate:
    status: str  # toward_screen / away_from_screen / unknown
    yaw: float | None = None
    pitch: float | None = None
    roll: float | None = None
    reason: str | None = None


class YuNetFaceDetector:
    """Detector local; la fețe multiple alege determinist cea mai mare casetă."""

    def __init__(self, min_face_pixels: int = 40):
        import cv2

        asset = Path(__file__).with_name("assets") / "face_detection_yunet_2023mar.onnx"
        if not asset.is_file():
            raise RuntimeError("Fișierul local YuNet lipsește.")
        self.cv2, self.min_face_pixels = cv2, min_face_pixels
        self.detector = cv2.FaceDetectorYN.create(str(asset), "", (320, 320), 0.8, 0.3, 5000)

    def detect(self, bgr: np.ndarray) -> FaceDetection:
        if bgr.dtype != np.uint8 or bgr.ndim != 3 or bgr.shape[2] != 3:
            return FaceDetection(0, None, None)
        height, width = bgr.shape[:2]
        scale = 320 / max(height, width)
        resized = self.cv2.resize(bgr, (max(1, round(width * scale)), max(1, round(height * scale))))
        canvas = np.zeros((320, 320, 3), dtype=np.uint8)
        canvas[:resized.shape[0], :resized.shape[1]] = resized
        try:
            _, faces = self.detector.detect(canvas)
        except self.cv2.error:
            return FaceDetection(0, None, None)
        if faces is None or not len(faces):
            return FaceDetection(0, None, None)
        boxes = np.rint(faces[:, :4] / scale).astype(int).tolist()
        bounded = []
        for x, y, box_width, box_height in boxes:
            x, y = max(0, x), max(0, y)
            box_width, box_height = min(box_width, width - x), min(box_height, height - y)
            if min(box_width, box_height) >= self.min_face_pixels:
                bounded.append((x, y, box_width, box_height))
        if not bounded:
            return FaceDetection(len(boxes), None, None)
        box = max(bounded, key=lambda item: item[2] * item[3])
        x, y, box_width, box_height = box
        return FaceDetection(len(boxes), box, bgr[y:y + box_height, x:x + box_width])


class MediaPipeHeadPose:
    """Folosește Face Landmarker numai cu un model `.task` furnizat explicit."""

    def __init__(self, model_path: Path | None, *, calibrated: bool = False, yaw_limit: float = 25, pitch_limit: float = 20):
        self.calibrated, self.yaw_limit, self.pitch_limit = calibrated, yaw_limit, pitch_limit
        self.landmarker = None
        self.unavailable_reason = "Modelul MediaPipe Face Landmarker nu a fost furnizat."
        if model_path is None:
            return
        if not model_path.is_file():
            self.unavailable_reason = f"Fișierul Face Landmarker nu există: {model_path}"
            return
        try:
            import mediapipe as mp
            options = mp.tasks.vision.FaceLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
                running_mode=mp.tasks.vision.RunningMode.IMAGE,
                num_faces=1,
                output_facial_transformation_matrixes=True,
            )
            self.mp = mp
            self.landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)
            self.unavailable_reason = None
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            self.unavailable_reason = f"Face Landmarker indisponibil: {error}"

    def estimate(self, bgr: np.ndarray) -> AttentionEstimate:
        if self.landmarker is None:
            return AttentionEstimate("unknown", reason=self.unavailable_reason)
        rgb = bgr[:, :, ::-1]
        result = self.landmarker.detect(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb))
        if not result.facial_transformation_matrixes:
            return AttentionEstimate("unknown", reason="MediaPipe nu a returnat repere faciale.")
        matrix = np.asarray(result.facial_transformation_matrixes[0], dtype=float).reshape(4, 4)
        pitch, yaw, roll = rotation_to_angles(matrix[:3, :3])
        if not self.calibrated:
            return AttentionEstimate("unknown", yaw, pitch, roll, "Lipsește calibrarea cameră/ecran.")
        status = "toward_screen" if abs(yaw) <= self.yaw_limit and abs(pitch) <= self.pitch_limit else "away_from_screen"
        return AttentionEstimate(status, yaw, pitch, roll)

    def close(self) -> None:
        if self.landmarker is not None:
            self.landmarker.close()


def rotation_to_angles(rotation: np.ndarray) -> tuple[float, float, float]:
    """Întoarce pitch, yaw, roll în grade; nu echivalează cu direcția privirii."""
    sy = sqrt(rotation[0, 0] ** 2 + rotation[1, 0] ** 2)
    pitch = degrees(atan2(rotation[2, 1], rotation[2, 2]))
    yaw = degrees(atan2(-rotation[2, 0], sy))
    roll = degrees(atan2(rotation[1, 0], rotation[0, 0]))
    return pitch, yaw, roll
