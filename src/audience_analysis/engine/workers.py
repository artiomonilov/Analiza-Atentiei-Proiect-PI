
from collections.abc import Callable
from dataclasses import replace
from threading import Event, Lock
import time
from uuid import uuid4

from PySide6.QtCore import QThread, Signal

from ..config import SequenceConfig
from ..contracts import FramePacket, InferenceRequest, ModelOutput, PredictionResult, Predictor, SourceConfig, SourceStatusEvent, Status
from ..video.sequences import SequenceBuilder
from ..video.preprocessing import FaceDetector
from ..video.sources import open_real_source, redact, synthetic_frame
from ..video.tracking import FaceTracker
from .scheduler import LatestScheduler


class PreviewStore:
    """Ultimul cadru de previzualizare per sursă; cadrele vechi sunt suprascrise, nu se adună."""
    def __init__(self):
        self.lock = Lock()
        self.runs: dict[str, str] = {}
        self.frames: dict[str, FramePacket] = {}

    def activate(self, source: str, run: str) -> None:
        """Începe o rulare nouă pentru sursă și șterge cadrul vechi."""
        with self.lock:
            self.runs[source] = run
            self.frames.pop(source, None)

    def put(self, packet: FramePacket) -> None:
        """Salvează cadrul dacă aparține rulării active (îl înlocuiește pe cel anterior)."""
        with self.lock:
            if self.runs.get(packet.source_id) == packet.run_id:
                self.frames[packet.source_id] = packet

    def take(self, source: str) -> FramePacket | None:
        """Scoate și întoarce ultimul cadru al sursei, sau None dacă nu a venit unul nou."""
        with self.lock:
            return self.frames.pop(source, None)

    def invalidate(self, source: str) -> None:
        """Oprește previzualizarea sursei și șterge cadrul păstrat."""
        with self.lock:
            self.runs.pop(source, None)
            self.frames.pop(source, None)



class FeatureStore(PreviewStore):
    """Ultimul rezultat per sursă și maximum o notificare Qt în așteptare."""
    def put(self, result):
        with self.lock:
            if self.runs.get(result.source_id) != result.run_id:
                return False
            notify = result.source_id not in self.frames
            self.frames[result.source_id] = result
            return notify


FACE_PROBLEMS = {Status.NO_FACE, Status.LOW_QUALITY}
FACE_MESSAGES = {
    Status.NO_FACE: "Nicio față detectată; secvențele se reiau",
    Status.LOW_QUALITY: "Fețe prea mici pentru analiză",
}


class SourceWorker(QThread):
    """P2 deține captura; analiza geometrică rulează serial în același worker."""
    status = Signal(object)
    features_ready = Signal(str, str)
    status_ready = Signal(str, str)
    RECONNECT_DELAYS_S = (1.0, 2.0, 4.0, 8.0, 8.0)
    MAX_VISIBLE_FACES = 8

    def __init__(self, source, run_id, config, scheduler, previews, *, duration_s=30,
                 detector_factory=None, stats=None, geometry_factory=None, features=None,
                 reader_factory=None, realtime=True, statuses=None):
        super().__init__()
        self.source, self.run_id, self.config = source, run_id, config
        self.scheduler, self.previews, self.stats = scheduler, previews, stats
        self.duration_s, self.detector_factory = duration_s, detector_factory
        self.geometry_factory, self.features = geometry_factory, features
        self.statuses = statuses
        self.reader_factory = reader_factory or open_real_source
        self.realtime = realtime
        self.stop_event = Event()
        self._last_status = None
        self.capture_epoch = 0
        self.outcome = None

    def stop(self):
        self.stop_event.set()

    def emit_status(self, status, message):
        self._last_status = status
        event = SourceStatusEvent(uuid4().hex, self.source.source_id, self.run_id, status, message)
        if self.statuses is None:
            self.status.emit(event)
        elif self.statuses.put(event):
            self.status_ready.emit(self.source.source_id, self.run_id)

    def _face_state(self, status, builders):
        if status in FACE_PROBLEMS:
            if status == Status.NO_FACE:
                builders.clear()
            if self._last_status != status:
                self.emit_status(status, FACE_MESSAGES[status])
        elif self._last_status in FACE_PROBLEMS:
            self.emit_status(Status.INSUFFICIENT_DATA, "Fețe detectate; se formează secvențele")

    def _submit(self, sequence, packet, request_id, track_id):
        if sequence is None:
            return False
        request = InferenceRequest(packet.source_id, packet.run_id, request_id,
                                   sequence.sample_times_s[0], sequence.sample_times_s[-1],
                                   time.monotonic(), sequence, track_id)
        accepted = self.scheduler.submit(request)
        if accepted and self.stats:
            self.stats.submitted(packet.source_id, packet.run_id)
        return accepted

    @staticmethod
    def _end_message(real, reader, frames_read, detection):
        if not real:
            return "Sfârșitul sursei sintetice"
        if getattr(reader, "is_image", False) or frames_read == 1:
            found = len(detection.boxes) if detection is not None else 0
            return f"Imagine statică — {found} fețe detectate; angajamentul necesită video"
        return "Sfârșitul sursei"

    def _reconnect(self, old, builders, tracker, origin):
        old.close()
        builders.clear()
        self.scheduler.expire_tracks(self.source.source_id, self.run_id, tracker.reset())
        self.capture_epoch += 1
        name = getattr(old, "name", redact(self.source.location))
        for attempt, delay in enumerate(self.RECONNECT_DELAYS_S, 1):
            self.emit_status(Status.INSUFFICIENT_DATA,
                             f"Conexiune pierdută cu {name}; reconectare {attempt}/{len(self.RECONNECT_DELAYS_S)}")
            if self.stop_event.wait(delay):
                return None
            try:
                reader = self.reader_factory(self.source, clock_origin=origin)
            except (ConnectionError, OSError, ValueError):
                continue
            self.emit_status(Status.INSUFFICIENT_DATA, f"Reconectat la {name}; se formează secvențele")
            if self.stats:
                self.stats.reconnect(self.source.source_id, self.run_id)
            return reader
        raise ConnectionError(f"{name}: reconectarea a eșuat")

    def run(self):
        real = self.source.kind != "demo"
        builders, tracker = {}, FaceTracker()
        reader = detector = detection = geometry = demo_builder = None
        terminal = None
        reason = "stopped"
        frame_index = request_id = 0
        origin = time.monotonic()
        try:
            demo_builder = SequenceBuilder(self.config)
            if real:
                if self.geometry_factory:
                    geometry = self.geometry_factory(self.source, self.run_id)
                if self.stop_event.is_set():
                    return
                reader = self.reader_factory(self.source, clock_origin=origin)
                if self.stop_event.is_set():
                    return
                detector = (self.detector_factory or FaceDetector)()
            live = bool(getattr(reader, "live", False))
            self.emit_status(Status.INSUFFICIENT_DATA,
                             "Se formează secvențele" if real else "SIMULARE: se formează secvența")
            anchor = time.monotonic()
            while not self.stop_event.is_set():
                if live:
                    try:
                        item = reader.read(self.stop_event)
                    except ConnectionError:
                        old, reader = reader, None
                        reader = self._reconnect(old, builders, tracker, origin)
                        if reader is None:
                            break
                        continue
                elif real:
                    item = reader.read()
                else:
                    media_time = frame_index / 20
                    item = (frame_index, media_time, None) if media_time <= self.duration_s else None
                if item is None:
                    if not self.stop_event.is_set():
                        if real and frame_index == 0:
                            raise ValueError("Sursa nu conține cadre")
                        terminal = (Status.END_OF_SOURCE, self._end_message(real, reader, frame_index, detection))
                        reason = "end_of_file"
                    break
                frame_id, media_time, image = item
                frame_index += 1
                if self.stop_event.wait(0 if live or not self.realtime else max(0, anchor + media_time - time.monotonic())):
                    break
                if not real:
                    packet = synthetic_frame(self.source.source_id, self.run_id, frame_id, media_time)
                    self.previews.put(packet)
                    if self.stats:
                        self.stats.frame(self.source.source_id, self.run_id, Status.OK)
                    if self._submit(demo_builder.add(packet), packet, request_id, None):
                        request_id += 1
                    continue
                detection = detector.detect(image)
                if len(detection.boxes) > self.MAX_VISIBLE_FACES:
                    selected = sorted(range(len(detection.boxes)),
                                      key=lambda i: detection.boxes[i][2] * detection.boxes[i][3],
                                      reverse=True)[:self.MAX_VISIBLE_FACES]
                    detection = replace(detection, boxes=tuple(detection.boxes[i] for i in selected),
                                        crops=tuple(detection.crops[i] for i in selected))
                track_ids, ended = tracker.update(detection.boxes, media_time)
                if detection.status == Status.NO_FACE:
                    ended.extend(tracker.reset())
                self.scheduler.expire_tracks(self.source.source_id, self.run_id, ended)
                for track_id in ended:
                    builders.pop(track_id, None)
                if self.stats:
                    self.stats.frame(self.source.source_id, self.run_id, detection.status)
                packet = FramePacket(self.source.source_id, self.run_id, frame_id, media_time,
                                     image, detection.boxes, track_ids,
                                     getattr(reader, "timestamp_source", "unspecified"), self.capture_epoch)
                self.previews.put(packet)
                if geometry:
                    result = geometry.process(packet)
                    if self.features is not None and self.features.put(result):
                        self.features_ready.emit(self.source.source_id, self.run_id)
                self._face_state(detection.status, builders)
                for track_id, crop in zip(track_ids, detection.crops):
                    if crop is None:
                        continue
                    builder = builders.get(track_id)
                    if builder is None:
                        builder = builders[track_id] = SequenceBuilder(self.config)
                    crop_packet = FramePacket(packet.source_id, packet.run_id, frame_id, media_time, crop,
                                              timestamp_source=packet.timestamp_source, capture_epoch=self.capture_epoch)
                    if self._submit(builder.add(crop_packet), crop_packet, request_id, track_id):
                        request_id += 1
        except ConnectionError as error:
            terminal, reason = (Status.ERROR, str(error)), "error"
        except Exception as error:
            terminal = (Status.ERROR, f"{type(error).__name__}: sursa sau analiza facială a eșuat")
            reason = "error"
        finally:
            if demo_builder:
                demo_builder.clear()
            builders.clear()
            try:
                if reader is not None:
                    reader.close()
            except Exception as error:
                terminal = (Status.ERROR, f"{type(error).__name__}: închiderea capturii a eșuat")
                reason = "error"
            finally:
                try:
                    if geometry is not None:
                        geometry.close(reason)
                except Exception as error:
                    terminal = (Status.ERROR, f"{type(error).__name__}: exportul facial a eșuat")
                    reason = "error"
            self.outcome = {"source_id": self.source.source_id, "run_id": self.run_id, "stop_reason": reason,
                            "error": terminal[1] if terminal is not None and terminal[0] == Status.ERROR else None}
            if terminal is not None and not self.stop_event.is_set():
                self.emit_status(*terminal)


class InferenceWorker(QThread):
    """Singurul fir AI: creează predictorul o dată și procesează cererile din coadă, una câte una."""
    result = Signal(object)
    model_status = Signal(object)

    def __init__(self, factory: Callable[[], Predictor], scheduler: LatestScheduler, *, demo: bool):
        super().__init__()
        self.factory, self.scheduler, self.demo = factory, scheduler, demo

    @staticmethod
    def _end_message(real: bool, reader, frames_read: int, detection) -> str:
        """Textul pentru END_OF_SOURCE."""
        if not real:
            return "Sfârșitul sursei sintetice"
        if not (getattr(reader, "is_image", False) or frames_read == 1):
            return "Sfârșitul sursei"
        found = len(detection.boxes) if detection is not None else 0
        usable = sum(crop is not None for crop in detection.crops) if detection is not None else 0
        if found == 0:
            faces = "nicio față detectată"
        else:
            faces = f"{found} {'față detectată' if found == 1 else 'fețe detectate'}"
            if usable < found:
                faces += f" ({usable} suficient de mari pentru analiză)"
        return f"Imagine statică — {faces}; estimarea angajamentului necesită video"

    def run(self) -> None:
        """Bucla firului AI; se termină când scheduler.take() întoarce None (la shutdown)."""
        predictor = None
        try:
            predictor = self.factory()  # o singură instanță, creată în firul AI
        except Exception:
            pass
        self.model_status.emit({"status": "OK" if predictor is not None else "MODEL_UNAVAILABLE",
                                "is_demo": self.demo})
        while (request := self.scheduler.take()) is not None:
            started = time.monotonic()
            status, levels, version, error = Status.OK, None, None, None
            try:
                if predictor is None:
                    raise RuntimeError("Model indisponibil")
                output = predictor.predict(request.sequence)
                if not isinstance(output, ModelOutput):
                    raise ValueError("Format de răspuns invalid")
                # Revalidare: un predictor extern poate modifica dicționarul după construire.
                output = ModelOutput(dict(output.levels), output.model_version, output.is_demo)
                if output.is_demo != self.demo:
                    raise ValueError("Marcaj de simulare incompatibil")
                levels, version = output.levels, output.model_version
            except Exception:
                status = Status.MODEL_UNAVAILABLE if predictor is None else Status.ERROR
                error = "Predictor indisponibil" if predictor is None else "Predictorul a eșuat sau a întors un răspuns invalid"
            finished = time.monotonic()
            self.result.emit(PredictionResult(request.source_id, request.run_id, request.request_id,
                request.window_start_s, request.window_end_s, status, levels, version, self.demo,
                max(0, started-request.queued_monotonic_s)*1000, (finished-started)*1000, error, request.track_id))
