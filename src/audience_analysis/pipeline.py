"""Pipeline incremental pentru imagine/video, agregare și export reproductibil."""
from collections import Counter
from dataclasses import asdict, dataclass, field
import csv
import json
from pathlib import Path
import time

from .engagement import UnavailableEngagementPredictor
from .model_stats import FrameStatistics, get_statistics_model
from .vision import AttentionEstimate, MediaPipeHeadPose, YuNetFaceDetector


@dataclass
class FrameResult:
    timestamp_s: float
    face_count: int
    face_status: str
    attention: AttentionEstimate
    emotion: FrameStatistics | None = None
    inference_ms: float | None = None
    error: str | None = None


@dataclass
class AnalysisResult:
    source: Path
    kind: str
    duration_s: float | None
    fps: float | None
    width: int | None
    height: int | None
    frames: list[FrameResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    interrupted: bool = False

    def summary(self) -> dict:
        total = len(self.frames)
        face = sum(row.face_status == "detected" for row in self.frames)
        emotions = [row.emotion for row in self.frames if row.emotion]
        attention_valid = [row.attention for row in self.frames if row.attention.status in {"toward_screen", "away_from_screen"}]
        toward = sum(item.status == "toward_screen" for item in attention_valid)
        unknown = sum(row.attention.status == "unknown" for row in self.frames)
        distribution = Counter(item.label for item in emotions)
        inference = [row.inference_ms for row in self.frames if row.inference_ms is not None]
        return {
            "source": str(self.source), "kind": self.kind, "duration_s": self.duration_s, "fps": self.fps,
            "resolution": {"width": self.width, "height": self.height}, "sampled_frames": total,
            "faces_detected": face, "face_coverage_pct": 100 * face / total if total else None,
            "attention_coverage_pct": 100 * len(attention_valid) / total if total else None,
            "toward_screen_pct_valid": 100 * toward / len(attention_valid) if attention_valid else None,
            "unknown_attention_frames": unknown,
            "emotion_frequency": dict(sorted(distribution.items())),
            "emotion_frames": len(emotions), "engagement": asdict(UnavailableEngagementPredictor().predict_clip([])),
            "processing_seconds": self.elapsed_s, "mean_inference_ms": sum(inference) / len(inference) if inference else None,
            "errors": len(self.errors), "interrupted": self.interrupted,
        }


class AnalysisPipeline:
    def __init__(self, *, device: str = "auto", face_landmarker_model: Path | None = None, calibrated: bool = False):
        if device not in {"auto", "cpu", "cuda"}:
            raise ValueError("--device trebuie să fie auto, cpu sau cuda")
        # Modelul existent selectează automat CUDA numai când Torch îl poate utiliza.
        self.device = device
        self.face_detector = YuNetFaceDetector()
        self.head_pose = MediaPipeHeadPose(face_landmarker_model, calibrated=calibrated)
        self.emotion_model = None

    def _emotion(self):
        if self.emotion_model is None:
            if self.device == "cuda":
                import torch
                if not torch.cuda.is_available():
                    raise RuntimeError("CUDA a fost cerut, dar instalarea PyTorch nu oferă CUDA.")
            self.emotion_model = get_statistics_model()
            if self.device == "cpu":
                self.emotion_model.device = self.emotion_model.torch.device("cpu")
                self.emotion_model.model.to(self.emotion_model.device)
        return self.emotion_model

    def analyse_frame(self, bgr, timestamp_s: float) -> FrameResult:
        detected = self.face_detector.detect(bgr)
        if detected.crop_bgr is None:
            return FrameResult(timestamp_s, detected.count, "no_face", AttentionEstimate("unknown", reason="Nu a fost detectată o față."))
        attention = self.head_pose.estimate(bgr)
        started = time.monotonic()
        try:
            emotion = self._emotion().predict_bgr(detected.crop_bgr)
            return FrameResult(timestamp_s, detected.count, "detected", attention, emotion, (time.monotonic() - started) * 1000)
        except (RuntimeError, ValueError) as error:
            return FrameResult(timestamp_s, detected.count, "detected", attention, error=str(error))

    def close(self) -> None:
        self.head_pose.close()


def analyse_image(source: Path, pipeline: AnalysisPipeline) -> AnalysisResult:
    import cv2
    started = time.monotonic()
    frame = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Imaginea nu poate fi citită sau formatul nu este acceptat.")
    result = AnalysisResult(source, "image", None, None, int(frame.shape[1]), int(frame.shape[0]))
    row = pipeline.analyse_frame(frame, 0.0)
    result.frames.append(row)
    if row.error:
        result.errors.append(row.error)
    result.elapsed_s = time.monotonic() - started
    return result


def analyse_video(source: Path, pipeline: AnalysisPipeline, sample_interval_s: float = 1.0, progress=None) -> AnalysisResult:
    import cv2
    if sample_interval_s <= 0:
        raise ValueError("--sample-interval trebuie să fie pozitiv")
    started = time.monotonic()
    capture = cv2.VideoCapture(str(source))
    try:
        if not capture.isOpened():
            raise ValueError("Videoclipul nu poate fi deschis. Verifică fișierul și codecul.")
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = count / fps if fps > 0 and count > 0 else None
        result = AnalysisResult(source, "video", duration, fps if fps > 0 else None, width or None, height or None)
        next_time, index = 0.0, 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            timestamp = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            if timestamp <= 0 and index:
                timestamp = index / fps if fps > 0 else float(index)
            index += 1
            if timestamp + 1e-8 < next_time:
                continue
            next_time = timestamp + sample_interval_s
            row = pipeline.analyse_frame(frame, timestamp)
            result.frames.append(row)
            if row.error:
                result.errors.append(f"{timestamp:.3f}s: {row.error}")
            if progress:
                progress(min(99, int(index * 100 / count)) if count else 0, timestamp)
        if progress:
            progress(100, duration or 0.0)
        result.elapsed_s = time.monotonic() - started
        return result
    finally:
        capture.release()


def export_reports(result: AnalysisResult, output_dir: Path, window_s: float = 5.0) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = result.summary()
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output_dir / "frames.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["timestamp_s", "face_count", "face_status", "attention_status", "yaw", "pitch", "roll", "emotion", "confidence", "emotion_probabilities", "error"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in result.frames:
            writer.writerow({"timestamp_s": row.timestamp_s, "face_count": row.face_count, "face_status": row.face_status,
                             "attention_status": row.attention.status, "yaw": row.attention.yaw, "pitch": row.attention.pitch,
                             "roll": row.attention.roll, "emotion": row.emotion.label if row.emotion else None,
                             "confidence": row.emotion.confidence if row.emotion else None,
                             "emotion_probabilities": json.dumps(row.emotion.probabilities, ensure_ascii=False) if row.emotion else None,
                             "error": row.error})
    buckets = {}
    for row in result.frames:
        buckets.setdefault(int(row.timestamp_s // window_s), []).append(row)
    with (output_dir / "windows.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["start_s", "end_s", "sampled_frames", "faces_detected", "attention_valid", "toward_screen", "unknown_attention", "dominant_emotion"])
        writer.writeheader()
        for bucket, rows in sorted(buckets.items()):
            emotions = Counter(item.emotion.label for item in rows if item.emotion)
            valid_attention = [item.attention for item in rows if item.attention.status in {"toward_screen", "away_from_screen"}]
            writer.writerow({"start_s": bucket * window_s, "end_s": (bucket + 1) * window_s, "sampled_frames": len(rows),
                             "faces_detected": sum(item.face_status == "detected" for item in rows),
                             "attention_valid": len(valid_attention), "toward_screen": sum(item.status == "toward_screen" for item in valid_attention),
                             "unknown_attention": sum(item.attention.status == "unknown" for item in rows),
                             "dominant_emotion": max(emotions, key=emotions.get) if emotions else None})
    (output_dir / "errors.log").write_text("\n".join(result.errors), encoding="utf-8")
