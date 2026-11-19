"""Analiza geometrică a cadrelor deja capturate de P2; nu deschide surse video."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import time

import numpy as np

from ..calibration import CalibrationManager
from ..contracts import identifier
from ..experimental import (FrozenExperiment, code_version, digest, environment_versions, event_digest,
                            file_digest, make_receipt, measurement_digest, validate_role_id)
from ..eye_features import EyeFeaturesEstimator
from ..face_landmarker import FaceLandmarker, validate_bgr
from ..facial_export import FacialCSVExport
from ..facial_features import FacialFeatureResult
from ..head_pose import HeadPoseEstimator
from ..temporal_analysis import TemporalAnalyzer, TemporalConfig
from ..video.preprocessing import DEFAULT_DETECTOR_PATH
from ..video.sources import resolve_source
from ..video_processor import measurement


@dataclass(frozen=True)
class GeometryConfig:
    model_path: Path
    session_id: str
    role: str = "development"
    calibration: dict | None = None
    temporal: TemporalConfig = field(default_factory=TemporalConfig)
    output_dir: Path | None = None
    track_id: int | None = None
    frozen_plan: dict | None = None
    data_kind: str = "unverified"

    def __post_init__(self):
        identifier(self.session_id)
        validate_role_id(self.session_id, self.role)
        if self.track_id is not None and (type(self.track_id) is not int or self.track_id < 0):
            raise ValueError("Track selectat invalid")
        if self.frozen_plan is not None and self.calibration is not None:
            raise ValueError("Calibrarea este inclusă în planul înghețat")
        if self.role == "validation" and self.frozen_plan is None:
            raise ValueError("Validarea independentă necesită un plan înghețat")
        if self.data_kind not in {"unverified", "synthetic", "authorized"}:
            raise ValueError("Proveniență experimentală invalidă")

    def pipeline_parameters(self):
        return {"pipeline": "p2_geometry_v1", "association": "unique_yunet_overlap_0.5",
                "selected_track_id": self.track_id, "max_visible_faces": 8,
                "detector_sha256": file_digest(DEFAULT_DETECTOR_PATH), "clock": "frame_clock_v1"}


def associated_track(face, boxes, track_ids, size, requested=None):
    """Asociere geometrică unică; nu este recunoaștere de identitate."""
    if face is None:
        return None, "no_face"
    points = np.array([(p.x, p.y) for p in face.landmarks], dtype=float)
    if len(points) < 3 or not np.isfinite(points).all() or len(boxes) != len(track_ids):
        return None, "unmatched"
    low, high = points.min(axis=0) * size, points.max(axis=0) * size
    area = float(np.prod(high - low))
    if area <= 0:
        return None, "unmatched"
    center = (low + high) / 2
    matches = []
    for (x, y, width, height), track in zip(boxes, track_ids):
        overlap = np.maximum(0, np.minimum(high, (x + width, y + height)) - np.maximum(low, (x, y)))
        if x <= center[0] <= x + width and y <= center[1] <= y + height and np.prod(overlap) / area >= .5:
            matches.append(track)
    if len(matches) != 1:
        return None, "ambiguous" if len(matches) > 1 else "unmatched"
    if requested is not None and matches[0] != requested:
        return None, "unmatched"
    if requested is None and len(boxes) != 1:
        return None, "ambiguous"
    return matches[0], "matched"


class FacialAnalysisSession:
    """O instanță per source/run, construită și folosită exclusiv în SourceWorker."""
    def __init__(self, source, run_id, config: GeometryConfig, *, landmarker_factory=FaceLandmarker):
        self.source, self.run_id, self.config = source, run_id, config
        identifier(run_id)
        self.stack = ExitStack()
        self.closed = False
        self.frames = self.faces = self.errors = self.available = 0
        self.started = time.monotonic()
        self.target = None
        self.calibration_target_lost = False
        self.last_timestamp = -1
        self.last_epoch = None
        self.plan = FrozenExperiment(config.frozen_plan) if config.frozen_plan else None
        self.pipeline = config.pipeline_parameters()
        self.raw_source = Path(source.location) if resolve_source(source)[0] == "file" else None
        self.source_sha256 = file_digest(self.raw_source) if self.raw_source is not None and self.raw_source.is_file() else None
        self.model_sha256 = file_digest(config.model_path)
        self.code = code_version()
        self.environment = environment_versions()
        self.mediapipe_calls = 0
        try:
            if self.plan:
                self.plan.validate_target(config.session_id, config.role)
                self.plan.validate_runtime(config.model_path)
                self.plan.validate_source_hash(file_digest(self.raw_source) if self.raw_source else None)
                if self.plan.payload.get("pipeline_parameters") != self.pipeline:
                    raise ValueError("Planul nu provine din aceeași configurație P2; repetă D/freeze")
                self.manager, self.temporal_config = self.plan.estimators()
            else:
                self.manager = CalibrationManager.from_dict(deepcopy(config.calibration)) if config.calibration else None
                self.temporal_config = self.manager.temporal_config(config.temporal) if self.manager else config.temporal
            if self.manager and self.manager.model_sha256 is not None and self.manager.model_sha256 != file_digest(config.model_path):
                raise ValueError("Modelul diferă de modelul calibrării")
            self.pose = self.manager.pose if self.manager else HeadPoseEstimator()
            self.eyes = self.manager.eyes if self.manager else EyeFeaturesEstimator()
            self.target_calibrated = self.manager is not None or self.temporal_config.left_blink is not None or self.temporal_config.right_blink is not None
            self.analyzer = TemporalAnalyzer(self.temporal_config)
            self.landmarker = landmarker_factory(config.model_path, mode="VIDEO")
            self.stack.callback(self.landmarker.close)
            self.directory = None
            self.export = None
            if config.output_dir is not None:
                self.directory = Path(config.output_dir) / source.source_id / run_id
                self.directory.mkdir(parents=True, exist_ok=False)
                self.export = self.stack.enter_context(FacialCSVExport(
                    self.directory / "measurements.csv", self.directory / "temporal.csv", self.directory / "blinks.csv",
                    metadata_fields=("source_id", "run_id", "track_id", "capture_epoch", "association_status")))
        except BaseException:
            self.stack.close()
            raise

    def process(self, packet):
        if self.closed or packet.source_id != self.source.source_id or packet.run_id != self.run_id:
            raise ValueError("Cadru din altă sesiune sau sesiune închisă")
        timestamp = round(packet.media_time_s * 1000)
        if timestamp <= self.last_timestamp:
            raise ValueError("Timestampul P2 trebuie să fie strict crescător în milisecunde")
        self.last_timestamp = timestamp
        pose = self.pose.estimate(None)
        eyes = self.eyes.estimate(None, (1, 1))
        face, track, association, error = None, None, "no_face", None
        try:
            validate_bgr(packet.image)
            self.mediapipe_calls += 1
            result = self.landmarker.process_video(packet.image, timestamp)  # exact o inferență
            face = result.faces[0] if result.faces else None
            track, association = associated_track(face, packet.face_boxes, packet.track_ids,
                                                 np.array([packet.image.shape[1], packet.image.shape[0]]), self.config.track_id)
            target = (packet.capture_epoch, track) if track is not None else None
            if target is not None and target != self.target:
                if self.target is not None and self.target_calibrated:
                    self.calibration_target_lost = True
                self.target = target
                self.analyzer = TemporalAnalyzer(self.temporal_config)
            if self.last_epoch is not None and self.last_epoch != packet.capture_epoch:
                self.analyzer = TemporalAnalyzer(self.temporal_config)
                if self.target_calibrated and self.target is not None:
                    self.calibration_target_lost = True
            self.last_epoch = packet.capture_epoch
            if self.calibration_target_lost:
                association = "calibration_target_lost"
                track = None
            if association == "matched":
                pose = self.pose.estimate(face.transformation_matrix)
                eyes = self.eyes.estimate(face, (packet.image.shape[1], packet.image.shape[0]))
        except (RuntimeError, ValueError) as exc:
            association = "processing_error"
            track = None
            pose = self.pose.estimate(None)
            eyes = self.eyes.estimate(None, (1, 1))
            error = f"{type(exc).__name__}: geometrie indisponibilă"
        elapsed = max(time.monotonic() - self.started, 1e-9)
        record = measurement(timestamp, packet.frame_id, face is not None, pose, eyes,
                             packet.timestamp_source, (self.frames + 1) / elapsed, error)
        temporal = self.analyzer.update(record)
        calibration = {"profile_applied": self.manager is not None,
                       "session_ids": self.manager.session_ids if self.manager else [],
                       "valid_for_target": not self.calibration_target_lost,
                       "head_neutral": self.pose.calibration_matrix() is not None,
                       "eye_baselines": sorted(self.eyes.calibration_state())}
        features = FacialFeatureResult(packet.source_id, packet.run_id, packet.frame_id, timestamp, track,
                                       packet.capture_epoch, record, temporal, calibration, association)
        if self.export:
            self.export.write(record, temporal, {"source_id": packet.source_id, "run_id": packet.run_id,
                              "track_id": track, "capture_epoch": packet.capture_epoch, "association_status": association})
        self.frames += 1
        self.faces += face is not None
        self.errors += error is not None
        self.available += association == "matched"
        return features

    def close(self, stop_reason="stopped"):
        if self.closed:
            return
        self.closed = True
        self.stack.close()
        if self.directory is None:
            return
        summary = {"schema_version": 1, "pipeline": "p2_geometry_v1", "source_id": self.source.source_id,
                   "run_id": self.run_id, "session_id": self.config.session_id, "role": self.config.role,
                   "frames": self.frames, "faces": self.faces, "associated_frames": self.available,
                   "mediapipe_calls": self.mediapipe_calls,
                   "errors": self.errors, "stop_reason": stop_reason,
                   "calibration_target_lost": self.calibration_target_lost,
                   "engagement_channel": "separate_P1_results",
                   "pipeline_parameters": self.pipeline, "provenance_status": "not_written"}
        summary["data_kind"] = self.config.data_kind
        (self.directory / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
        if self.frames == 0 or (self.config.role == "validation" and stop_reason != "end_of_file"):
            return
        if file_digest(self.config.model_path) != self.model_sha256:
            raise ValueError("Modelul s-a schimbat în timpul procesării")
        if self.raw_source is not None and file_digest(self.raw_source) != self.source_sha256:
            raise ValueError("Sursa s-a schimbat în timpul procesării")
        if code_version()["source_sha256"] != self.code["source_sha256"] or environment_versions() != self.environment:
            raise ValueError("Codul sau mediul s-a schimbat în timpul procesării")
        measurements, blinks = self.directory / "measurements.csv", self.directory / "blinks.csv"
        if self.plan:
            receipt = make_receipt(self.plan, self.config.session_id, self.config.role, measurements,
                                   events=blinks, source=self.raw_source)
        else:
            from ..dashboard_data import load_rows
            from ..validation import read_blinks
            receipt = {"session_id": self.config.session_id, "role": self.config.role, "config_version": "unfrozen",
                       "code": self.code, "environment": self.environment, "temporal": asdict(self.temporal_config),
                       "model_sha256": self.model_sha256,
                       "measurement_content_sha256": measurement_digest(load_rows(measurements)),
                       "event_content_sha256": event_digest(read_blinks(blinks)),
                       "source_sha256": self.source_sha256,
                       "calibration": self.manager.to_dict() if self.manager else None}
        receipt.update(pipeline_parameters=self.pipeline, source_id=self.source.source_id, run_id=self.run_id,
                       stop_reason=stop_reason, data_kind=self.config.data_kind)
        Path(str(measurements) + ".experiment.json").write_text(json.dumps(receipt, indent=2, allow_nan=False), encoding="utf-8")
        summary["provenance_status"] = "written"
        (self.directory / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
