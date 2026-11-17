"""Pipeline incremental pentru imagine/video, agregare și export reproductibil."""
from collections import Counter
from dataclasses import asdict, dataclass, field
import csv
import json
import math
from pathlib import Path
import time
from contextlib import ExitStack

from .engagement import UnavailableEngagementPredictor
from .model_stats import FrameStatistics, get_statistics_model, MODEL_ID, MODEL_REVISION
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
    timestamp_origin: str | None = None


@dataclass
class _Totals:
    count: int = 0
    faces: int = 0
    attention_valid: int = 0
    toward: int = 0
    unknown: int = 0
    inference_total: float = 0
    inference_count: int = 0
    errors: int = 0
    emotions: Counter = field(default_factory=Counter)

    def add(self, row):
        self.count += 1
        self.faces += row.face_status == "detected"
        self.attention_valid += row.attention.status in {"toward_screen", "away_from_screen"}
        self.toward += row.attention.status == "toward_screen"
        self.unknown += row.attention.status == "unknown"
        if row.emotion: self.emotions[row.emotion.label] += 1
        if row.inference_ms is not None:
            self.inference_total += row.inference_ms; self.inference_count += 1
        self.errors += bool(row.error)


FRAME_FIELDS = ["timestamp_s", "face_count", "face_status", "attention_status", "yaw", "pitch", "roll", "emotion", "confidence", "emotion_probabilities", "error", "timestamp_origin"]
WINDOW_FIELDS = ["start_s", "end_s", "sampled_frames", "faces_detected", "attention_valid", "toward_screen", "unknown_attention", "dominant_emotion"]


def _frame_row(row):
    return {"timestamp_s": row.timestamp_s, "face_count": row.face_count, "face_status": row.face_status,
        "attention_status": row.attention.status, "yaw": row.attention.yaw, "pitch": row.attention.pitch,
        "roll": row.attention.roll, "emotion": row.emotion.label if row.emotion else None,
        "confidence": row.emotion.confidence if row.emotion else None,
        "emotion_probabilities": json.dumps(row.emotion.probabilities, ensure_ascii=False) if row.emotion else None,
        "error": row.error, "timestamp_origin": row.timestamp_origin}


class _StreamingReports:
    """Scrie cadrele imediat; păstrează doar contoare pentru fereastra curentă."""
    def __init__(self, directory, window_s=5., *, new=True):
        if not math.isfinite(window_s) or window_s <= 0: raise ValueError("Fereastră invalidă.")
        self.directory, self.window_s = Path(directory), window_s
        self.directory.mkdir(parents=True, exist_ok=not new)
        self.stack = ExitStack()
        try:
            self.frames = csv.DictWriter(self.stack.enter_context((self.directory / "frames.csv").open("w", newline="", encoding="utf-8")), fieldnames=FRAME_FIELDS)
            self.windows = csv.DictWriter(self.stack.enter_context((self.directory / "windows.csv").open("w", newline="", encoding="utf-8")), fieldnames=WINDOW_FIELDS)
            self.errors = self.stack.enter_context((self.directory / "errors.log").open("w", encoding="utf-8"))
            self.frames.writeheader(); self.windows.writeheader()
        except BaseException:
            self.stack.close(); raise
        self.bucket, self.totals = None, _Totals()

    def _flush_window(self):
        if self.bucket is None: return
        t = self.totals
        self.windows.writerow({"start_s": self.bucket * self.window_s, "end_s": (self.bucket + 1) * self.window_s,
            "sampled_frames": t.count, "faces_detected": t.faces, "attention_valid": t.attention_valid,
            "toward_screen": t.toward, "unknown_attention": t.unknown,
            "dominant_emotion": max(t.emotions, key=t.emotions.get) if t.emotions else None})

    def add(self, row):
        bucket = int(row.timestamp_s // self.window_s)
        if self.bucket != bucket:
            self._flush_window(); self.bucket, self.totals = bucket, _Totals()
        self.totals.add(row); self.frames.writerow(_frame_row(row))
        if row.error: self.errors.write(f"{row.timestamp_s:.3f}s: {row.error}\n")

    def close(self):
        try: self._flush_window()
        finally: self.stack.close()


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
    _totals: _Totals | None = field(default=None, repr=False)
    reports_path: Path | None = None

    def summary(self) -> dict:
        totals = self._totals
        if totals is None:
            totals = _Totals()
            for row in self.frames: totals.add(row)
        total, face = totals.count, totals.faces
        return {
            "source": "local-input", "kind": self.kind, "duration_s": self.duration_s, "fps": self.fps,
            "resolution": {"width": self.width, "height": self.height}, "sampled_frames": total,
            "faces_detected": face, "face_coverage_pct": 100 * face / total if total else None,
            "attention_coverage_pct": 100 * totals.attention_valid / total if total else None,
            "toward_screen_pct_valid": 100 * totals.toward / totals.attention_valid if totals.attention_valid else None,
            "unknown_attention_frames": totals.unknown,
            "emotion_frequency": dict(sorted(totals.emotions.items())),
            "emotion_frames": sum(totals.emotions.values()), "engagement": asdict(UnavailableEngagementPredictor().predict_clip([])),
            "processing_seconds": self.elapsed_s, "mean_inference_ms": totals.inference_total / totals.inference_count if totals.inference_count else None,
            "errors": totals.errors, "interrupted": self.interrupted,
            "expression_model": {"model_id": MODEL_ID, "revision": MODEL_REVISION, "used": bool(totals.emotions)},
        }


class AnalysisPipeline:
    def __init__(self, *, device: str = "auto", face_landmarker_model: Path | None = None, calibrated: bool = False, allow_model_download=False):
        if device not in {"auto", "cpu", "cuda"}:
            raise ValueError("--device trebuie să fie auto, cpu sau cuda")
        # Modelul existent selectează automat CUDA numai când Torch îl poate utiliza.
        self.device = device
        self.face_detector = YuNetFaceDetector()
        self.head_pose = MediaPipeHeadPose(face_landmarker_model, calibrated=calibrated)
        self.emotion_model = None
        self.allow_model_download, self.emotion_error = allow_model_download, None

    def _emotion(self):
        if self.emotion_error is not None: raise self.emotion_error
        if self.emotion_model is None:
            if self.device == "cuda":
                import torch
                if not torch.cuda.is_available():
                    raise RuntimeError("CUDA a fost cerut, dar instalarea PyTorch nu oferă CUDA.")
            try:
                self.emotion_model = get_statistics_model(allow_download=self.allow_model_download)
            except (RuntimeError, ValueError, ImportError) as error:
                self.emotion_error = error
                raise
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
            return FrameResult(timestamp_s, detected.count, "detected", attention, error=f"{type(error).__name__}: inferență indisponibilă")

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


def analyse_video(source: Path, pipeline: AnalysisPipeline, sample_interval_s: float = 1.0, progress=None,
                  *, report_dir=None, retain_frames=True) -> AnalysisResult:
    import cv2
    from .video_processor import FrameClock
    if not math.isfinite(sample_interval_s) or sample_interval_s <= 0:
        raise ValueError("--sample-interval trebuie să fie pozitiv")
    started = time.monotonic()
    capture = cv2.VideoCapture(str(source))
    writer, result = None, None
    try:
        if not capture.isOpened():
            raise ValueError("Videoclipul nu poate fi deschis. Verifică fișierul și codecul.")
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        if not math.isfinite(fps) or fps <= 0: fps = 0.
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = count / fps if fps > 0 and count > 0 else None
        result = AnalysisResult(source, "video", duration, fps if fps > 0 else None, width or None, height or None)
        if not retain_frames: result._totals = _Totals()
        if report_dir is not None:
            writer = _StreamingReports(report_dir)
            result.reports_path = Path(report_dir).resolve()
        next_time, index = 0.0, 0
        clock = FrameClock(webcam=False, source_fps=fps, start=0)
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            timestamp_ms, origin = clock.next(index, float(capture.get(cv2.CAP_PROP_POS_MSEC)), time.monotonic())
            timestamp = timestamp_ms / 1000.
            index += 1
            if timestamp + 1e-8 < next_time:
                continue
            next_time = timestamp + sample_interval_s
            try:
                row = pipeline.analyse_frame(frame, timestamp)
            except (RuntimeError, ValueError, OSError, ImportError) as error:
                row = FrameResult(timestamp, 0, "error", AttentionEstimate("unknown"), error=f"{type(error).__name__}: cadru indisponibil")
            row.timestamp_origin = origin
            if retain_frames: result.frames.append(row)
            else: result._totals.add(row)
            if writer: writer.add(row)
            if row.error:
                if retain_frames or len(result.errors) < 100: result.errors.append(f"{timestamp:.3f}s: {row.error}")
            if progress:
                progress(min(99, int(index * 100 / count)) if count else 0, timestamp)
        if progress:
            progress(100, duration or 0.0)
        result.elapsed_s = time.monotonic() - started
        return result
    except KeyboardInterrupt:
        if result is None: raise
        result.interrupted = True
        return result
    finally:
        capture.release()
        if writer: writer.close()
        if result is not None:
            result.elapsed_s = time.monotonic() - started
            if writer: (writer.directory / "summary.json").write_text(json.dumps(result.summary(), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def export_reports(result: AnalysisResult, output_dir: Path, window_s: float = 5.0) -> None:
    if result.reports_path is not None:
        if Path(output_dir).resolve() != result.reports_path: raise ValueError("Rezultatul streaming este deja exportat în directorul original.")
        return
    if result._totals is not None: raise ValueError("Fără istoric reținut, exportul trebuie cerut în timpul procesării.")
    writer = _StreamingReports(output_dir, window_s, new=False)
    try:
        for row in result.frames: writer.add(row)
    finally: writer.close()
    (output_dir / "summary.json").write_text(json.dumps(result.summary(), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    (output_dir / "errors.log").write_text("\n".join(result.errors), encoding="utf-8")
