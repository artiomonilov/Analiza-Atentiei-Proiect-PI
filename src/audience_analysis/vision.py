"""Detecție locală de față și orientare cap opțională prin MediaPipe."""
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .head_pose import HeadPose, HeadPoseEstimator, extract_rotation, rotation_angles
from .eye_features import EyeFeaturesEstimator, EyesResult


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


@dataclass(frozen=True)
class FacialGeometry:
    head_pose: HeadPose
    eyes: EyesResult


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
        # Argumentele istorice sunt păstrate pentru compatibilitate. Un bool
        # nu definește o poziție neutră și nu permite estimarea privirii.
        self.pose_estimator = HeadPoseEstimator()
        self.eye_estimator = EyeFeaturesEstimator()
        self.landmarker = None
        self.unavailable_reason = "Modelul MediaPipe Face Landmarker nu a fost furnizat."
        if model_path is None:
            return
        if not model_path.is_file():
            self.unavailable_reason = f"Fișierul Face Landmarker nu există: {model_path}"
            return
        try:
            from .face_landmarker import FaceLandmarker
            self.landmarker = FaceLandmarker(model_path)
            self.unavailable_reason = None
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            self.unavailable_reason = f"Face Landmarker indisponibil: {error}"

    def estimate(self, bgr: np.ndarray) -> AttentionEstimate:
        if self.landmarker is None:
            return AttentionEstimate("unknown", reason=self.unavailable_reason)
        result = self.landmarker.process(bgr)
        if not result.faces or result.faces[0].transformation_matrix is None:
            return AttentionEstimate("unknown", reason="MediaPipe nu a returnat repere faciale.")
        matrix = result.faces[0].transformation_matrix
        pose = self.pose_estimator.estimate(matrix)
        return AttentionEstimate("unknown", pose.yaw, pose.pitch, pose.roll,
                                 pose.reason or "Orientarea capului nu clasifică atenția sau privirea.")

    def calibrate(self, neutral_matrix: np.ndarray) -> None:
        self.pose_estimator.calibrate(neutral_matrix)

    def geometry(self, bgr: np.ndarray) -> FacialGeometry:
        """Pose și ochi din aceeași inferență, fără reîncărcarea modelului."""
        from .face_landmarker import validate_bgr
        validate_bgr(bgr)
        result = self.landmarker.process(bgr) if self.landmarker is not None else None
        face = result.faces[0] if result and result.faces else None
        return FacialGeometry(
            self.pose_estimator.estimate(face.transformation_matrix if face else None),
            self.eye_estimator.estimate(face, (bgr.shape[1], bgr.shape[0])),
        )

    def close(self) -> None:
        if self.landmarker is not None:
            self.landmarker.close()


def rotation_to_angles(rotation: np.ndarray) -> tuple[float, float, float]:
    """Compatibilitate: ordinea istorică pitch,yaw,roll; elimină și scalarea."""
    matrix = np.eye(4)
    matrix[:3, :3] = rotation
    yaw, pitch, roll, _ = rotation_angles(extract_rotation(matrix))
    return pitch, yaw, roll
