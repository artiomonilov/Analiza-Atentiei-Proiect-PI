"""Geometrie 2D a ochilor din rezultate Face Landmarker existente.

LEFT/RIGHT sunt ale subiectului. Topologia provine din conexiunile oficiale
MediaPipe Tasks FaceLandmarksConnections (sursa și indicii în docs/eye-features.md).
Acest modul nu inițializează modele și nu clasifică atenția sau clipirile.
"""
from dataclasses import dataclass, replace

import numpy as np

from .face_landmarker import FaceLandmarks


# Contururi ordonate; închidere implicită ultimul -> primul.
LEFT_EYE = (263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466)
RIGHT_EYE = (33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246)
LEFT_IRIS = (474, 475, 476, 477)
RIGHT_IRIS = (469, 470, 471, 472)
# p1,p2,p3,p4,p5,p6; p1->p4 urmează direcția orizontală locală a imaginii.
LEFT_EAR = (362, 385, 387, 263, 373, 380)
RIGHT_EAR = (33, 160, 158, 133, 153, 144)


@dataclass(frozen=True)
class EyeFeatures:
    subject_side: str
    ear: float | None = None
    iris_center: tuple[float, float] | None = None  # coordonate normalizate ale imaginii
    iris_position: tuple[float, float] | None = None  # fracții în reperul local al ochiului
    ear_relative: float | None = None  # EAR / EAR_neutru
    gaze_delta: tuple[float, float] | None = None  # poziție iris minus referința neutră
    eye_points_px: tuple[tuple[float, float], ...] = ()
    iris_points_px: tuple[tuple[float, float], ...] = ()
    reason: str | None = None


@dataclass(frozen=True)
class EyesResult:
    left: EyeFeatures
    right: EyeFeatures


def _image_size(image_size: tuple[int, int]) -> np.ndarray:
    size = np.asarray(image_size, dtype=float)
    if size.shape != (2,) or not np.isfinite(size).all() or (size <= 0).any():
        raise ValueError("image_size trebuie să fie (lățime, înălțime), valori pozitive finite.")
    return size


def _points(face: FaceLandmarks, indices: tuple[int, ...], size: np.ndarray) -> np.ndarray:
    if len(face.landmarks) <= max(indices):
        raise ValueError("Landmarks lipsă sau model fără reperele irisului.")
    try:
        points = np.array([(face.landmarks[index].x, face.landmarks[index].y) for index in indices], dtype=float)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("Coordonate landmarks invalide.") from error
    if not np.isfinite(points).all() or (points < 0).any() or (points > 1).any():
        raise ValueError("Repere nefinite sau în afara imaginii; ochi parțial vizibil.")
    return points * size


def eye_aspect_ratio(points_px: np.ndarray) -> float:
    """EAR=(|p2-p6|+|p3-p5|)/(2|p1-p4|), șase puncte în pixeli."""
    points = np.asarray(points_px, dtype=float)
    if points.shape != (6, 2) or not np.isfinite(points).all():
        raise ValueError("EAR necesită șase puncte 2D finite, în pixeli.")
    width = np.linalg.norm(points[0] - points[3])
    if width <= 1e-8:
        raise ValueError("Lățimea ochiului este degenerată.")
    return float((np.linalg.norm(points[1] - points[5]) + np.linalg.norm(points[2] - points[4])) / (2 * width))


class EyeFeaturesEstimator:
    def __init__(self, *, min_iris_aperture_px: float = 1.0, min_open_ratio: float | None = None):
        if not np.isfinite(min_iris_aperture_px) or min_iris_aperture_px <= 0:
            raise ValueError("Apertura minimă trebuie să fie pozitivă și finită.")
        if min_open_ratio is not None and (not np.isfinite(min_open_ratio) or not 0 < min_open_ratio < 1):
            raise ValueError("Raportul individual de deschidere trebuie să fie între 0 și 1.")
        self.min_iris_aperture_px = min_iris_aperture_px
        self.min_open_ratio = min_open_ratio
        self._neutral: dict[str, EyeFeatures] = {}

    def _eye(self, face: FaceLandmarks | None, side: str, size: np.ndarray, occluded: bool) -> EyeFeatures:
        if face is None:
            return EyeFeatures(side, reason="Față indisponibilă.")
        if occluded:
            return EyeFeatures(side, reason="Ochi marcat ca ocluzionat de apelant.")
        contour_indices, ear_indices, iris_indices = (
            (LEFT_EYE, LEFT_EAR, LEFT_IRIS) if side == "left" else (RIGHT_EYE, RIGHT_EAR, RIGHT_IRIS))
        try:
            contour = _points(face, contour_indices, size)
            six = _points(face, ear_indices, size)
            ear = eye_aspect_ratio(six)
        except ValueError as error:
            return EyeFeatures(side, reason=str(error))
        features = EyeFeatures(side, ear, eye_points_px=tuple(tuple(map(float, point)) for point in contour))
        reference = self._neutral.get(side)
        if reference is not None:
            features = replace(features, ear_relative=ear / reference.ear)
        # Basis rotates with the canthi; x follows p1->p4 and y points to lower lid.
        horizontal = six[3] - six[0]
        width = np.linalg.norm(horizontal)
        horizontal = horizontal / width
        vertical = np.array([-horizontal[1], horizontal[0]])
        upper = (six[1] + six[2]) / 2
        lower = (six[4] + six[5]) / 2
        if np.dot(lower - upper, vertical) <= 0:
            return replace(features, reason="Pleoape închise sau geometrie inversată.")
        local_contour = (contour - six[0]) @ np.column_stack((horizontal, vertical))
        top, bottom = local_contour[:, 1].min(), local_contour[:, 1].max()
        if bottom - top < self.min_iris_aperture_px:
            return replace(features, reason="Apertură insuficientă pentru poziția irisului.")
        if reference is not None and self.min_open_ratio is not None and features.ear_relative < self.min_open_ratio:
            return replace(features, reason="Deschidere sub limita individuală configurată pentru iris.")
        try:
            iris = _points(face, iris_indices, size)
        except ValueError as error:
            return replace(features, reason=str(error))
        center = iris.mean(axis=0)
        ring = iris - center
        if np.linalg.matrix_rank(ring, tol=1e-8) < 2:
            return replace(features, reason="Geometrie iris degenerată.")
        local_center = center - six[0]
        position = np.array([np.dot(local_center, horizontal) / width,
                             (np.dot(local_center, vertical) - top) / (bottom - top)])
        if (position < 0).any() or (position > 1).any():
            return replace(features, reason="Centrul irisului este în afara regiunii ochiului.")
        delta = tuple(map(float, position - reference.iris_position)) if reference is not None else None
        return replace(features, iris_center=tuple(map(float, center / size)), iris_position=tuple(map(float, position)),
                       gaze_delta=delta, iris_points_px=tuple(tuple(map(float, point)) for point in iris))

    def estimate(self, face: FaceLandmarks | None, image_size: tuple[int, int], *, occluded_eyes=()) -> EyesResult:
        """Folosește aceeași față/imagine ca HeadPose; nu combină rezultatele în scoruri."""
        size = _image_size(image_size)
        occluded_eyes = set(occluded_eyes)
        if occluded_eyes - {"left", "right"}:
            raise ValueError("Ochi ocluzionați acceptați: left/right (subiect).")
        return EyesResult(self._eye(face, "left", size, "left" in occluded_eyes),
                          self._eye(face, "right", size, "right" in occluded_eyes))

    def calibrate(self, face: FaceLandmarks | None, image_size: tuple[int, int], *, sides=("left", "right")) -> None:
        """Memorează deschiderea și poziția neutră separat pentru ochii selectați."""
        sides = tuple(sides)
        if not sides or set(sides) - {"left", "right"}:
            raise ValueError("Selectează left/right pentru calibrare.")
        # Referința se calculează fără filtrele unei calibrări anterioare.
        raw = EyeFeaturesEstimator(min_iris_aperture_px=self.min_iris_aperture_px).estimate(face, image_size)
        selected = {side: getattr(raw, side) for side in sides}
        if any(item.iris_position is None or item.ear is None or item.ear <= 0 for item in selected.values()):
            raise ValueError("Calibrare invalidă: ochi deschiși și iris valid necesari pentru fiecare ochi selectat.")
        self._neutral.update(selected)

    def clear_calibration(self) -> None:
        self._neutral.clear()

    def calibration_state(self) -> dict:
        return {side: {"ear": value.ear, "iris_position": list(value.iris_position)} for side, value in self._neutral.items()}

    def load_calibration_state(self, state: dict) -> None:
        if not isinstance(state, dict) or set(state) - {"left", "right"}:
            raise ValueError("Configurație de calibrare oculară invalidă.")
        validated = {}
        try:
            for side, value in state.items():
                ear = float(value["ear"])
                iris = np.asarray(value["iris_position"], dtype=float)
                if not np.isfinite(ear) or ear <= 0 or iris.shape != (2,) or not np.isfinite(iris).all() or (iris < 0).any() or (iris > 1).any():
                    raise ValueError("Referință EAR/iris invalidă.")
                validated[side] = EyeFeatures(side, ear=ear, iris_position=tuple(map(float, iris)))
        except (KeyError, TypeError) as error:
            raise ValueError("Referință EAR/iris incompletă.") from error
        self._neutral = validated


def draw_eye_features(image_bgr: np.ndarray, result: EyesResult) -> np.ndarray:
    import cv2
    from .face_landmarker import validate_bgr
    validate_bgr(image_bgr)
    image = image_bgr.copy()
    scale = max(.15, min(.55, image.shape[1] / 1050))
    step = max(8, round(24 * scale / .55))
    for index, features in enumerate((result.left, result.right)):
        color = (0, 255, 255) if features.subject_side == "left" else (255, 255, 0)
        for points in (features.eye_points_px, features.iris_points_px):
            if points:
                contour = np.rint(points).astype(np.int32).reshape(-1, 1, 2)
                cv2.polylines(image, [contour], True, color, 1, cv2.LINE_AA)
                for x, y in np.rint(points).astype(int):
                    cv2.circle(image, (int(x), int(y)), 1, color, -1)
        if features.iris_center is not None:
            x, y = np.rint(np.array(features.iris_center) * [image.shape[1], image.shape[0]]).astype(int)
            cv2.drawMarker(image, (int(x), int(y)), (0, 0, 255), cv2.MARKER_CROSS, 8, 1)
        ear = f"{features.ear:.3f}" if features.ear is not None else "n/a"
        iris = f"({features.iris_position[0]:.2f},{features.iris_position[1]:.2f})" if features.iris_position is not None else "n/a"
        text = f"Subject {features.subject_side}: EAR={ear} iris={iris}"
        origin = (3, image.shape[0] - (2 - index) * step)
        cv2.putText(image, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(image, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)
    return image
