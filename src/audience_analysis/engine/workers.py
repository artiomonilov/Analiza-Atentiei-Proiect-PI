from collections.abc import Callable
from threading import Event, Lock
import time
from uuid import uuid4

from PySide6.QtCore import QThread, Signal

from ..config import SequenceConfig
from ..contracts import FramePacket, InferenceRequest, ModelOutput, PredictionResult, Predictor, SourceConfig, SourceStatusEvent, Status
from ..video.sequences import SequenceBuilder
from ..video.sources import synthetic_frame
from .scheduler import LatestScheduler


class PreviewStore:
    def __init__(self):
        self.lock = Lock()
        self.runs: dict[str, str] = {}
        self.frames: dict[str, FramePacket] = {}

    def activate(self, source: str, run: str) -> None:
        with self.lock:
            self.runs[source] = run
            self.frames.pop(source, None)

    def put(self, packet: FramePacket) -> None:
        with self.lock:
            if self.runs.get(packet.source_id) == packet.run_id:
                self.frames[packet.source_id] = packet

    def take(self, source: str) -> FramePacket | None:
        with self.lock:
            return self.frames.pop(source, None)

    def invalidate(self, source: str) -> None:
        with self.lock:
            self.runs.pop(source, None)
            self.frames.pop(source, None)


class SourceWorker(QThread):
    status = Signal(object)

    def __init__(self, source: SourceConfig, run_id: str, config: SequenceConfig,
                 scheduler: LatestScheduler, previews: PreviewStore, *, duration_s: float = 30.0):
        super().__init__()
        self.source, self.run_id, self.config = source, run_id, config
        self.scheduler, self.previews = scheduler, previews
        self.duration_s = duration_s
        self.stop_event = Event()

    def stop(self) -> None:
        self.stop_event.set()  # apelabil chiar dacă run() ocupă firul lucrătorului

    def emit_status(self, status: Status, message: str) -> None:
        self.status.emit(SourceStatusEvent(uuid4().hex, self.source.source_id, self.run_id, status, message))

    def run(self) -> None:
        builder = SequenceBuilder(self.config, demo=True)
        frame_id, request_id = 0, 0
        anchor = time.monotonic()
        self.emit_status(Status.INSUFFICIENT_DATA, "SIMULARE: se formează secvența; nu se detectează fețe")
        try:
            while not self.stop_event.is_set():
                media_time = frame_id / 20.0
                if media_time > self.duration_s:
                    self.emit_status(Status.END_OF_SOURCE, "Sfârșitul sursei sintetice")
                    break
                if self.stop_event.wait(max(0, anchor + media_time - time.monotonic())):
                    break
                packet = synthetic_frame(self.source.source_id, self.run_id, frame_id, media_time)
                self.previews.put(packet)
                sequence = builder.add(packet)
                if sequence is not None:
                    request = InferenceRequest(packet.source_id, packet.run_id, request_id,
                        sequence.sample_times_s[0], sequence.sample_times_s[-1], time.monotonic(), sequence)
                    self.scheduler.submit(request)
                    request_id += 1
                frame_id += 1
        except Exception:
            self.emit_status(Status.ERROR, "Eroare în sursa simulată; verifică configurația")
        finally:
            builder.clear()


class InferenceWorker(QThread):
    result = Signal(object)

    def __init__(self, factory: Callable[[], Predictor], scheduler: LatestScheduler, *, demo: bool):
        super().__init__()
        self.factory, self.scheduler, self.demo = factory, scheduler, demo

    def run(self) -> None:
        predictor = None
        try:
            predictor = self.factory()  # o singură instanță, creată în firul AI
        except Exception:
            pass
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
                max(0, started-request.queued_monotonic_s)*1000, (finished-started)*1000, error))
