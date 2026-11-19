"""Captură sincronă locală, MediaPipe VIDEO, geometrie și CSV incremental."""
from contextlib import ExitStack
from dataclasses import asdict, dataclass
import csv
import math
from pathlib import Path
import time

import numpy as np

from .face_landmarker import FaceLandmarker, LandmarkerResult, draw_landmarks, load_image, validate_bgr
from .head_pose import HeadPose, HeadPoseEstimator, draw_head_pose
from .eye_features import EyeFeaturesEstimator, EyesResult, draw_eye_features
from .temporal_analysis import BlinkEvent, TemporalAnalyzer, TemporalConfig, TemporalUpdate, temporal_csv_row


@dataclass(frozen=True)
class VideoMeasurement:
    timestamp_ms: int
    frame_index: int
    face_detected: bool
    yaw: float | None
    pitch: float | None
    roll: float | None
    left_ear: float | None
    right_ear: float | None
    left_iris_x: float | None
    left_iris_y: float | None
    right_iris_x: float | None
    right_iris_y: float | None
    head_pose_available: bool
    head_pose_calibrated: bool
    head_pose_gimbal_lock: bool
    left_ear_available: bool
    right_ear_available: bool
    left_iris_available: bool
    right_iris_available: bool
    left_ear_relative: float | None
    right_ear_relative: float | None
    left_gaze_dx: float | None
    left_gaze_dy: float | None
    right_gaze_dx: float | None
    right_gaze_dy: float | None
    timestamp_source: str
    processing_fps: float
    head_pose_reason: str | None
    left_eye_reason: str | None
    right_eye_reason: str | None
    error: str | None = None


@dataclass(frozen=True)
class VideoSessionReport:
    frames_processed: int
    faces_detected: int
    errors: int
    elapsed_s: float
    processing_fps: float
    source_fps: float | None
    stop_reason: str
    temporal: TemporalUpdate | None = None


class FrameClock:
    """Prezervă POS_MSEC valid; fallback FPS sursă, apoi estimare 30 FPS."""

    def __init__(self, *, webcam: bool, source_fps: float, start: float, last_timestamp_ms: int = -1):
        self.webcam, self.source_fps, self.start = webcam, source_fps, start
        self.last = last_timestamp_ms

    def next(self, frame_index: int, position_ms: float, now: float) -> tuple[int, str]:
        if self.webcam:
            candidate, origin = max(0, round((now - self.start) * 1000)), "webcam_monotonic"
        elif math.isfinite(position_ms) and position_ms >= 0 and position_ms > self.last:
            candidate, origin = round(position_ms), "video_pos_msec"
        else:
            valid_fps = math.isfinite(self.source_fps) and self.source_fps > 0
            fps = self.source_fps if valid_fps else 30.0
            candidate = round(frame_index * 1000 / fps)
            origin = "video_fps" if valid_fps else "estimated_30fps"
        if candidate <= self.last:
            candidate = self.last + 1
            origin += "+strict_order"
        self.last = candidate
        return candidate, origin


def _pair(pair):
    return pair if pair is not None else (None, None)


def measurement(timestamp, index, detected, pose, eyes, origin, fps, error=None) -> VideoMeasurement:
    lx, ly = _pair(eyes.left.iris_position)
    rx, ry = _pair(eyes.right.iris_position)
    ldx, ldy = _pair(eyes.left.gaze_delta)
    rdx, rdy = _pair(eyes.right.gaze_delta)
    return VideoMeasurement(
        timestamp_ms=timestamp, frame_index=index, face_detected=detected,
        yaw=pose.yaw, pitch=pose.pitch, roll=pose.roll,
        left_ear=eyes.left.ear, right_ear=eyes.right.ear,
        left_iris_x=lx, left_iris_y=ly, right_iris_x=rx, right_iris_y=ry,
        head_pose_available=pose.valid, head_pose_calibrated=pose.calibrated,
        head_pose_gimbal_lock=pose.gimbal_lock,
        left_ear_available=eyes.left.ear is not None, right_ear_available=eyes.right.ear is not None,
        left_iris_available=eyes.left.iris_position is not None, right_iris_available=eyes.right.iris_position is not None,
        left_ear_relative=eyes.left.ear_relative, right_ear_relative=eyes.right.ear_relative,
        left_gaze_dx=ldx, left_gaze_dy=ldy, right_gaze_dx=rdx, right_gaze_dy=rdy,
        timestamp_source=origin, processing_fps=fps, head_pose_reason=pose.reason,
        left_eye_reason=eyes.left.reason, right_eye_reason=eyes.right.reason, error=error)


def annotate_frame(frame, landmarks: LandmarkerResult, pose: HeadPose, eyes: EyesResult,
                   record: VideoMeasurement, *, show_landmarks=False, temporal=None):
    import cv2
    image = draw_landmarks(frame, landmarks) if show_landmarks else frame
    image = draw_eye_features(draw_head_pose(image, pose), eyes)
    label = f"FPS processing: {record.processing_fps:.1f} | "
    label += "FACE" if record.face_detected else ("PROCESSING ERROR" if record.error else "NO FACE")
    cv2.putText(image, label, (3, max(12, image.shape[0] // 2 - 30)),
                cv2.FONT_HERSHEY_SIMPLEX, .45, (255, 0, 255), 1, cv2.LINE_AA)
    if temporal is not None:
        window = temporal.windows[0]
        left, right = window["left_blink"], window["right_blink"]
        def available(value):
            return value if value is not None else "n/a"
        lines = [f"Temporal: {window['observed_span_ms'] / 1000:.1f}s / {window['window_s']}s",
                 f"Blinks L/R: {available(left['count'])} / {available(right['count'])}  last ms: {available(left['last_duration_ms'])}/{available(right['last_duration_ms'])}",
                 f"Head circ.var: {window['head']['variance']}",
                 f"Iris stable L/R ms: {window['left_gaze']['stable_duration_ms']}/{window['right_gaze']['stable_duration_ms']}",
                 f"Valid head: {window['head']['valid_samples']}  truncated: {window['history_truncated']}"]
        scale = max(.15, min(.4, image.shape[1] / 1400))
        step = max(8, round(20 * scale / .4))
        start = max(14, image.shape[0] // 2 - 5)
        for i, line in enumerate(lines):
            origin = (3, start + i * step)
            cv2.putText(image, line, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(image, line, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 0, 255), 1, cv2.LINE_AA)
    return image


class VideoProcessor:
    def __init__(self, model_path: Path, *, pose_estimator=None, eye_estimator=None, temporal_config: TemporalConfig | None = None):
        self.model_path = Path(model_path)
        self.pose_estimator = pose_estimator if pose_estimator is not None else HeadPoseEstimator()
        self.eye_estimator = eye_estimator if eye_estimator is not None else EyeFeaturesEstimator()
        self.temporal_config = temporal_config or TemporalConfig()

    def run(self, source: Path | int, *, neutral_image: Path | None = None,
            output_csv: Path | None = None, display: bool = True, show_landmarks: bool = False,
            on_result=None, on_temporal=None, output_temporal_csv: Path | None = None,
            output_blinks_csv: Path | None = None, show_temporal: bool = False) -> VideoSessionReport:
        """Returnează statistici, fără a reține cadrele; callback opțional per măsurătoare.

        Estimatorii pot fi deja calibrați de apelant. Referința foto opțională
        folosește aceeași instanță VIDEO, la timestamp 0, înaintea fluxului.
        """
        import cv2
        webcam = isinstance(source, int)
        if webcam and (source < 0 or not display):
            raise ValueError("Camera necesită index nenegativ și afișare activă (fără --no-display).")
        if not webcam and not Path(source).is_file():
            raise ValueError(f"Fișierul video nu există: {source}")
        if not self.model_path.is_file():
            raise ValueError(f"Modelul Face Landmarker nu există: {self.model_path}")
        exports = [Path(p) for p in (output_csv, output_temporal_csv, output_blinks_csv) if p is not None]
        if len({p.resolve() for p in exports}) != len(exports):
            raise ValueError("Fișierele CSV de export trebuie să fie distincte.")
        for export in exports:
            protected = [self.model_path, *([] if webcam else [Path(source)])]
            if neutral_image is not None:
                protected.append(Path(neutral_image))
            if export.resolve() in {path.resolve() for path in protected}:
                raise ValueError("CSV-ul trebuie să fie diferit de sursă, model și fotografia neutră.")

        capture = cv2.VideoCapture(source if webcam else str(source))
        window_opened = False
        try:
            if not capture.isOpened():
                raise RuntimeError("Camera nu poate fi deschisă." if webcam else "Videoclipul nu poate fi deschis; verifică fișierul și codecul.")
            source_fps = float(capture.get(cv2.CAP_PROP_FPS))
            with ExitStack() as stack:
                landmarker = stack.enter_context(FaceLandmarker(self.model_path, mode="VIDEO"))
                if neutral_image is not None:
                    neutral = load_image(neutral_image)
                    result = landmarker.process_video(neutral, 0)
                    if not result.faces:
                        raise ValueError("Fotografia neutră nu conține o față detectabilă.")
                    face = result.faces[0]
                    self.pose_estimator.calibrate(face.transformation_matrix)
                    self.eye_estimator.calibrate(face, (neutral.shape[1], neutral.shape[0]))
                from .facial_export import FacialCSVExport
                facial_export = stack.enter_context(FacialCSVExport(output_csv, output_temporal_csv, output_blinks_csv))
                analyzer = TemporalAnalyzer(self.temporal_config)
                temporal = None
                start = time.monotonic()
                clock = FrameClock(webcam=webcam, source_fps=source_fps, start=start,
                                   last_timestamp_ms=0 if neutral_image is not None else -1)
                frames, faces, errors, stop_reason = 0, 0, 0, "end_of_file"
                try:
                    while True:
                        ok, frame = capture.read()
                        if not ok:
                            if webcam:
                                raise RuntimeError("Camera a încetat să furnizeze cadre.")
                            if frames == 0:
                                raise RuntimeError("Videoclipul nu conține cadre care pot fi citite.")
                            break
                        now = time.monotonic()
                        timestamp, origin = clock.next(frames, float(capture.get(cv2.CAP_PROP_POS_MSEC)) if not webcam else 0, now)
                        result = LandmarkerResult(())
                        pose = self.pose_estimator.estimate(None)
                        eyes = self.eye_estimator.estimate(None, (1, 1))
                        error, valid_frame = None, True
                        try:
                            validate_bgr(frame)
                            result = landmarker.process_video(frame, timestamp)
                            face = result.faces[0] if result.faces else None
                            pose = self.pose_estimator.estimate(face.transformation_matrix if face else None)
                            eyes = self.eye_estimator.estimate(face, (frame.shape[1], frame.shape[0]))
                        except (ValueError, RuntimeError) as exc:
                            error = f"{type(exc).__name__}: cadru sau geometrie indisponibilă"
                            try:
                                validate_bgr(frame)
                            except ValueError:
                                valid_frame = False
                        elapsed = max(time.monotonic() - start, 1e-9)
                        record = measurement(timestamp, frames, bool(result.faces), pose, eyes, origin, (frames + 1) / elapsed, error)
                        temporal = analyzer.update(record)
                        frames += 1
                        faces += int(record.face_detected)
                        errors += int(error is not None)
                        facial_export.write(record, temporal)
                        if on_result:
                            on_result(record)
                        if on_temporal:
                            on_temporal(temporal)
                        if display:
                            visible = frame if valid_frame else np.zeros((360, 640, 3), np.uint8)
                            image = annotate_frame(visible, result, pose, eyes, record, show_landmarks=show_landmarks,
                                                   temporal=temporal if show_temporal else None)
                            window_opened = True
                            cv2.imshow("AnalizaAtentiei - Q pentru iesire", image)
                            if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                                stop_reason = "q"
                                break
                            if cv2.getWindowProperty("AnalizaAtentiei - Q pentru iesire", cv2.WND_PROP_VISIBLE) < 1:
                                stop_reason = "window_closed"
                                break
                except KeyboardInterrupt:
                    stop_reason = "interrupted"
                elapsed = time.monotonic() - start
                return VideoSessionReport(frames, faces, errors, elapsed, frames / elapsed if elapsed > 0 else 0,
                                          source_fps if math.isfinite(source_fps) and source_fps > 0 else None, stop_reason, temporal)
        except cv2.error as error:
            raise RuntimeError("OpenCV nu a putut captura sau afișa cadrul. Pentru fișiere fără suport GUI folosește --no-display. " + str(error)) from error
        finally:
            try:
                capture.release()
            finally:
                if window_opened:
                    try:
                        cv2.destroyWindow("AnalizaAtentiei - Q pentru iesire")
                    except cv2.error:
                        pass  # Fereastra poate fi deja închisă sau backendul GUI indisponibil.
