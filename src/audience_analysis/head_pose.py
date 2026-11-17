"""Orientare geometrică din T=[A,t;0,1], în grade, fără clasificare.

Vectori coloană, sistem drept: +X dreapta imaginii, +Y sus, +Z spre
observator (camera privește spre -Z). R = Rz(roll) @ Ry(yaw) @ Rx(pitch).
Rotațiile sunt active, pozitive după regula mâinii drepte.
"""
from dataclasses import dataclass
from math import atan2, degrees, hypot

import numpy as np


@dataclass(frozen=True)
class HeadPose:
    yaw: float | None = None
    pitch: float | None = None
    roll: float | None = None
    valid: bool = False
    calibrated: bool = False
    gimbal_lock: bool = False
    reason: str | None = None


def extract_rotation(matrix: np.ndarray) -> np.ndarray:
    """Factorul polar R=U@Vt elimină stretch/scalare; t este ignorată.

    Respinge perspective, reflexii și blocuri singulare sau aproape singulare.
    Stretch-ul simetric pozitiv este separat inclusiv pentru scară neuniformă.
    """
    try:
        transform = np.asarray(matrix, dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError("Matricea facială trebuie să conțină numere reale.") from error
    if transform.shape != (4, 4) or not np.isfinite(transform).all():
        raise ValueError("Matricea facială trebuie să fie 4x4 și finită.")
    if not np.allclose(transform[3], [0, 0, 0, 1], atol=1e-6, rtol=0):
        raise ValueError("Matricea facială nu este o transformare afină omogenă.")
    try:
        u, singular, vt = np.linalg.svd(transform[:3, :3])
    except np.linalg.LinAlgError as error:
        raise ValueError("Descompunerea rotației a eșuat.") from error
    if singular[0] <= np.finfo(float).tiny or singular[-1] / singular[0] < 1e-8:
        raise ValueError("Matricea facială este singulară sau numeric instabilă.")
    rotation = u @ vt
    if np.linalg.det(rotation) < 0:
        raise ValueError("Matricea conține o reflexie, nu o rotație proprie.")
    return rotation


def rotation_angles(rotation: np.ndarray) -> tuple[float, float, float, bool]:
    """Yaw [-90,90], pitch/roll [-180,180]; la singularitate fixăm roll=0."""
    sy = hypot(rotation[0, 0], rotation[1, 0])
    gimbal_lock = sy < 1e-7
    yaw = degrees(atan2(-rotation[2, 0], sy))
    if gimbal_lock:
        pitch = degrees(atan2(-rotation[1, 2], rotation[1, 1]))
        roll = 0.0
    else:
        pitch = degrees(atan2(rotation[2, 1], rotation[2, 2]))
        roll = degrees(atan2(rotation[1, 0], rotation[0, 0]))
    return yaw, pitch, roll, gimbal_lock


class HeadPoseEstimator:
    """Calibrare cu R_neutru.T @ R_curent, în reperul poziției neutre."""

    def __init__(self):
        self._neutral_rotation: np.ndarray | None = None

    def calibrate(self, neutral_matrix: np.ndarray) -> None:
        # O calibrare invalidă nu înlocuiește referința existentă.
        self._neutral_rotation = extract_rotation(neutral_matrix)

    def clear_calibration(self) -> None:
        self._neutral_rotation = None

    def calibration_matrix(self) -> np.ndarray | None:
        """Referință minimă serializabilă, fără translație/scalare sau landmarks."""
        if self._neutral_rotation is None:
            return None
        matrix = np.eye(4)
        matrix[:3, :3] = self._neutral_rotation
        return matrix

    def estimate(self, matrix: np.ndarray | None) -> HeadPose:
        calibrated = self._neutral_rotation is not None
        if matrix is None:
            return HeadPose(calibrated=calibrated, reason="Față sau matrice facială indisponibilă.")
        try:
            rotation = extract_rotation(matrix)
        except ValueError as error:
            return HeadPose(calibrated=calibrated, reason=str(error))
        if calibrated:
            rotation = self._neutral_rotation.T @ rotation
        yaw, pitch, roll, gimbal_lock = rotation_angles(rotation)
        return HeadPose(yaw, pitch, roll, True, calibrated, gimbal_lock)


def draw_head_pose(image_bgr: np.ndarray, pose: HeadPose) -> np.ndarray:
    """Adaugă unghiurile pe o copie a fotografiei (font OpenCV ASCII)."""
    import cv2
    from .face_landmarker import validate_bgr
    validate_bgr(image_bgr)
    image = image_bgr.copy()
    lines = ["Head pose: unavailable"]
    if pose.valid:
        lines = [f"Yaw: {pose.yaw:+.1f} deg", f"Pitch: {pose.pitch:+.1f} deg",
                 f"Roll: {pose.roll:+.1f} deg", "Neutral-relative" if pose.calibrated else "Camera frame"]
        if pose.gimbal_lock:
            lines.append("Gimbal lock: roll fixed to 0")
    scale = max(.15, min(.65, image.shape[1] / 420))
    step = max(7, round(28 * scale / .65))
    for index, line in enumerate(lines):
        origin = (3, (index + 1) * step)
        cv2.putText(image, line, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(image, line, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 0, 255), 1, cv2.LINE_AA)
    return image
