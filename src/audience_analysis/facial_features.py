"""Rezultat geometric per cadru, distinct de ModelOutput și de identitatea unei persoane."""
from dataclasses import asdict, dataclass
import json

from .contracts import counter, identifier
from .temporal_analysis import TemporalUpdate
from .video_processor import VideoMeasurement


@dataclass(frozen=True)
class FacialFeatureResult:
    source_id: str
    run_id: str
    frame_index: int
    timestamp_ms: int
    track_id: int | None
    capture_epoch: int
    measurement: VideoMeasurement
    temporal_features: TemporalUpdate
    calibration_status: dict
    association_status: str

    def __post_init__(self):
        object.__setattr__(self, "calibration_status", json.loads(json.dumps(self.calibration_status, allow_nan=False)))
        identifier(self.source_id)
        identifier(self.run_id)
        for value in (self.frame_index, self.timestamp_ms, self.capture_epoch):
            counter(value)
        if self.track_id is not None:
            counter(self.track_id)
        if (self.measurement.timestamp_ms != self.timestamp_ms or self.measurement.frame_index != self.frame_index
                or self.temporal_features.timestamp_ms != self.timestamp_ms):
            raise ValueError("Caracteristicile trebuie să aparțină aceluiași cadru și timestamp")
        if self.association_status not in {"matched", "no_face", "unmatched", "ambiguous", "processing_error", "calibration_target_lost"}:
            raise ValueError("Asociere facială invalidă")
        json.dumps(asdict(self), allow_nan=False)

    @property
    def availability(self):
        return {key: value for key, value in asdict(self.measurement).items() if key.endswith("_available")}

    def to_dict(self):
        return {"schema_version": 1, "kind": "p2_facial_geometry", **asdict(self), "availability": self.availability,
                "units": {"timestamp_ms": "milliseconds", "angles": "degrees_xyz_rzryrx",
                          "ear": "dimensionless", "iris": "eye_local_normalized"},
                "interpretation": "geometry_only_not_attention_or_engagement"}
