"""Calibrări reutilizabile și profil JSON explicit, fără fotografii/landmarks."""
from dataclasses import asdict, replace
import json
from pathlib import Path

import numpy as np

from .head_pose import HeadPoseEstimator, extract_rotation
from .eye_features import EyeFeaturesEstimator
from .temporal_analysis import BlinkThresholds, TemporalConfig


class CalibrationManager:
    def __init__(self, session_ids: list[str]):
        if not isinstance(session_ids, (list, tuple)) or not session_ids or any(not isinstance(s, str) or not s.strip() for s in session_ids):
            raise ValueError("Identificatori de sesiune de calibrare obligatorii.")
        self.session_ids = list(session_ids)
        from .experimental import validate_role_id
        for session_id in self.session_ids: validate_role_id(session_id, "calibration")
        self.pose = HeadPoseEstimator()
        self.eyes = EyeFeaturesEstimator()
        self.blink_thresholds = {}
        self.quality = {}
        self.source_materials = []
        self.model_sha256 = None

    def bind_model_hash(self, fingerprint):
        if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
            raise ValueError("Hash de model C invalid.")
        if self.model_sha256 is not None and self.model_sha256 != fingerprint:
            raise ValueError("Materialele C provin din modele diferite.")
        self.model_sha256 = fingerprint

    def register_measurement_source(self, path):
        """Verifică sidecarul C când există; CSV-urile istorice rămân explicit fără proveniență."""
        from .experimental import measurement_digest
        from .dashboard_data import load_rows
        path = Path(path)
        sidecar = Path(str(path) + ".experiment.json")
        if not sidecar.exists(): return False
        receipt = json.loads(sidecar.read_text(encoding="utf-8"))
        if receipt.get("role") != "calibration" or receipt.get("session_id") not in self.session_ids:
            raise ValueError("Datele D/V nu pot fi relabelate ca material C.")
        if receipt.get("measurement_content_sha256") != measurement_digest(load_rows(path)):
            raise ValueError("Măsurătorile C diferă de proveniență.")
        material = None
        if receipt.get("source_sha256"):
            value = receipt["source_sha256"]
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("Hash raw C invalid.")
            material = {"kind": "raw", "sha256": value}
        self.bind_model_hash(receipt.get("model_sha256"))
        if material is not None and material not in self.source_materials: self.source_materials.append(material)
        return True

    def register_materials(self, paths, *, kind="raw"):
        """Leagă sursele C prin hash, fără căi sau nume personale în profil."""
        from .experimental import file_digest
        if kind not in {"raw", "neutral_image", "measurements"}: raise ValueError("Tip de material invalid.")
        additions = [{"kind": kind, "sha256": file_digest(p)} for p in paths]
        self.source_materials = sorted({(m["kind"], m["sha256"]) for m in [*self.source_materials, *additions]})
        self.source_materials = [{"kind": k, "sha256": h} for k, h in self.source_materials]

    def calibrate_neutral(self, observations, *, min_samples=1, max_rotation_spread_deg=5, max_iris_std=.05, max_ear_cv=.2):
        """observations: secvență de perechi (FaceLandmarks, (width,height))."""
        if type(min_samples) is not int or min_samples < 1 or any(not np.isfinite(v) or v <= 0 for v in (max_rotation_spread_deg, max_iris_std, max_ear_cv)):
            raise ValueError("Parametrii de calitate trebuie să fie pozitivi.")
        observations = list(observations)
        if len(observations) < min_samples:
            raise ValueError("Date neutre insuficiente.")
        rotations, results = [], []
        evaluator = EyeFeaturesEstimator()
        for face, size in observations:
            if face is None:
                raise ValueError("Față lipsă în calibrarea neutră.")
            rotations.append(extract_rotation(face.transformation_matrix))
            eyes = evaluator.estimate(face, size)
            if any(eye.ear is None or eye.ear <= 0 or eye.iris_position is None for eye in (eyes.left, eyes.right)):
                raise ValueError("Calibrarea neutră necesită ambii ochi cu geometrie validă.")
            results.append(eyes)
        average = np.eye(4)
        average[:3, :3] = np.mean(rotations, axis=0)
        rotation = extract_rotation(average)
        spread = max(float(np.rad2deg(np.arccos(np.clip((np.trace(rotation.T @ r) - 1) / 2, -1, 1)))) for r in rotations)
        if spread > max_rotation_spread_deg:
            raise ValueError("Orientare neutră instabilă.")
        baseline, quality = {}, {"neutral_samples": len(results), "rotation_spread_deg": spread,
                                 "sample_consistency_checked": len(results) > 1,
                                 "temporal_stability_verified": False}
        for side in ("left", "right"):
            ears = np.array([getattr(row, side).ear for row in results])
            iris = np.array([getattr(row, side).iris_position for row in results])
            cv = float(ears.std() / ears.mean())
            if cv > max_ear_cv or float(iris.std(axis=0).max()) > max_iris_std:
                raise ValueError(f"Geometrie neutră instabilă pentru {side}.")
            baseline[side] = {"ear": float(np.median(ears)), "iris_position": np.median(iris, axis=0).tolist()}
            quality[side] = {"ear_cv": cv, "iris_std": iris.std(axis=0).tolist()}
        pose, eyes = HeadPoseEstimator(), EyeFeaturesEstimator()
        average[:3, :3] = rotation
        pose.calibrate(average)
        eyes.load_calibration_state(baseline)
        self.pose, self.eyes = pose, eyes  # commit numai după validarea completă
        self.quality["neutral"] = quality

    def calibrate_ear(self, side: str, open_values, closed_values, *, min_samples=5):
        if side not in {"left", "right"} or min_samples < 2:
            raise ValueError("Ochi invalid sau număr insuficient de observații cerute.")
        opened, closed = np.asarray(open_values, dtype=float), np.asarray(closed_values, dtype=float)
        if any(v.ndim != 1 or len(v) < min_samples or not np.isfinite(v).all() or (v < 0).any() for v in (opened, closed)):
            raise ValueError("Calibrarea EAR necesită suficiente valori finite nenegative pentru ochi deschiși și închiși.")
        high_closed, low_open = float(np.quantile(closed, .95)), float(np.quantile(opened, .05))
        if low_open <= high_closed:
            raise ValueError("Distribuțiile EAR deschis/închis nu sunt separabile.")
        gap = low_open - high_closed
        thresholds = BlinkThresholds(high_closed + gap * .35, high_closed + gap * .65)
        self.blink_thresholds[side] = thresholds
        self.quality[side + "_ear"] = {"open_samples": len(opened), "closed_samples": len(closed),
                                      "closed_q95": high_closed, "open_q05": low_open}

    def temporal_config(self, base: TemporalConfig | None = None) -> TemporalConfig:
        base = base or TemporalConfig()
        return replace(base, **{side + "_blink": thresholds for side, thresholds in self.blink_thresholds.items()})

    def to_dict(self):
        matrix = self.pose.calibration_matrix()
        result = {"schema_version": 1, "calibration_session_ids": self.session_ids,
                "neutral_head_matrix": matrix.tolist() if matrix is not None else None,
                "eye_baselines": self.eyes.calibration_state(),
                "blink_thresholds": {side: asdict(value) for side, value in self.blink_thresholds.items()}, "quality": self.quality}
        if self.source_materials: result["source_materials"] = self.source_materials
        if self.model_sha256 is not None: result["model_sha256"] = self.model_sha256
        return result

    def save(self, path: Path):
        if self.pose.calibration_matrix() is None and not self.eyes.calibration_state() and not self.blink_thresholds:
            raise ValueError("Profilul nu conține nicio calibrare.")
        payload = json.dumps(self.to_dict(), ensure_ascii=False, indent=2, allow_nan=False)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as handle:
            handle.write(payload)

    @classmethod
    def load(cls, path: Path):
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    @classmethod
    def from_dict(cls, data):
        try:
            if not isinstance(data, dict) or set(data) - {"source_materials", "model_sha256"} != {"schema_version", "calibration_session_ids", "neutral_head_matrix", "eye_baselines", "blink_thresholds", "quality"}:
                raise ValueError("Structură de calibrare invalidă.")
            if type(data["schema_version"]) is not int or data["schema_version"] != 1:
                raise ValueError("Versiune de calibrare incompatibilă.")
            manager = cls(data["calibration_session_ids"])
            if "model_sha256" in data: manager.bind_model_hash(data["model_sha256"])
            materials = data.get("source_materials", [])
            if not isinstance(materials, list) or any(not isinstance(m, dict) or set(m) != {"kind", "sha256"} or m["kind"] not in {"raw", "neutral_image", "measurements"} or not isinstance(m["sha256"], str) or len(m["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in m["sha256"]) for m in materials):
                raise ValueError("Proveniență C invalidă.")
            manager.source_materials = materials
            if data["neutral_head_matrix"] is not None:
                manager.pose.calibrate(data["neutral_head_matrix"])
            manager.eyes.load_calibration_state(data["eye_baselines"])
            for side, value in data["blink_thresholds"].items():
                if side not in {"left", "right"}:
                    raise ValueError("Ochi invalid în profil.")
                manager.blink_thresholds[side] = BlinkThresholds(**value)
            manager.quality = data["quality"]
            if not isinstance(manager.quality, dict) or (manager.pose.calibration_matrix() is None and not manager.eyes.calibration_state() and not manager.blink_thresholds):
                raise ValueError("Profil de calibrare fără referințe sau cu quality invalid.")
            json.dumps(manager.to_dict(), allow_nan=False)
            return manager
        except (KeyError, TypeError) as error:
            raise ValueError("Profil de calibrare incomplet sau invalid.") from error
