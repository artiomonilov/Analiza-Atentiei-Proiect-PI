"""P2 — Firele de lucru ale motorului.

Conține:
    PreviewStore      păstrează ultimul cadru de previzualizare per sursă (cu chenarele fețelor)
    FACE_PROBLEMS     stările în care nu se poate analiza nimic (NO_FACE, LOW_QUALITY)
    FACE_MESSAGES     textul trimis în UI pentru fiecare dintre aceste stări
    SourceWorker      un fir per sursă: citește, detectează, urmărește fețe, formează secvențe
    InferenceWorker   un singur fir AI: ia cereri din coadă, cheamă predictorul, emite rezultate

Niciun modul engine nu importă QtWidgets; comunicarea cu UI trece prin EngineController.
"""
from collections.abc import Callable
from threading import Event, Lock
import time
from uuid import uuid4

from PySide6.QtCore import QThread, Signal

from ..config import SequenceConfig
from ..contracts import FramePacket, InferenceRequest, ModelOutput, PredictionResult, Predictor, SourceConfig, SourceStatusEvent, Status
from ..video.sequences import SequenceBuilder
from ..video.preprocessing import FaceDetector
from ..video.sources import open_real_source, synthetic_frame
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


FACE_PROBLEMS = {Status.NO_FACE, Status.LOW_QUALITY}
FACE_MESSAGES = {
    Status.NO_FACE: "Nicio față detectată; secvențele se reiau",
    Status.LOW_QUALITY: "Fețe prea mici pentru analiză",
}


class SourceWorker(QThread):
    """Firul unei surse: citește cadre, detectează și urmărește fețele, formează secvențe și le trimite în coadă."""
    status = Signal(object)

    def __init__(self, source: SourceConfig, run_id: str, config: SequenceConfig,
                 scheduler: LatestScheduler, previews: PreviewStore, *, duration_s: float = 30.0,
                 detector_factory: Callable[[], object] | None = None):
        super().__init__()
        self.source, self.run_id, self.config = source, run_id, config
        self.scheduler, self.previews = scheduler, previews
        self.duration_s = duration_s  # se aplică numai sursei demo; un fișier rulează până la EOF
        self.detector_factory = detector_factory
        self.stop_event = Event()
        self._last_status: Status | None = None

    def stop(self) -> None:
        """Cere oprirea; apelabil din orice fir, chiar dacă run() e ocupat. Nu așteaptă terminarea."""
        self.stop_event.set()  # apelabil chiar dacă run() ocupă firul lucrătorului

    def emit_status(self, status: Status, message: str) -> None:
        """Emite un SourceStatusEvent pentru sursa și rularea acestui lucrător și reține starea."""
        self._last_status = status
        self.status.emit(SourceStatusEvent(uuid4().hex, self.source.source_id, self.run_id, status, message))

    def _face_state(self, status: Status, builders: dict[int, SequenceBuilder]) -> None:
        """Emite un eveniment numai la schimbarea stării, nu la fiecare cadru."""
        if status in FACE_PROBLEMS:
            if status == Status.NO_FACE:
                builders.clear()  # fără fețe nu rămân cadre vechi în istoric
            if self._last_status != status:
                self.emit_status(status, FACE_MESSAGES[status])
        elif self._last_status in FACE_PROBLEMS:
            self.emit_status(Status.INSUFFICIENT_DATA, "Fețe detectate; se formează secvențele")

    def _submit(self, sequence, packet: FramePacket, request_id: int, track_id: int | None) -> bool:
        """Transformă o secvență într-o InferenceRequest și o pune în coadă."""
        if sequence is None:
            return False
        request = InferenceRequest(packet.source_id, packet.run_id, request_id, sequence.sample_times_s[0],
                                   sequence.sample_times_s[-1], time.monotonic(), sequence, track_id)
        self.scheduler.submit(request)
        return True

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
        """Bucla firului (pornită de QThread.start())."""
        real = self.source.kind != "demo"
        demo_builder = SequenceBuilder(self.config)
        builders: dict[int, SequenceBuilder] = {}  # un istoric separat pentru fiecare față urmărită
        tracker = FaceTracker()
        reader = detector = detection = None
        frame_index, request_id = 0, 0
        try:
            if real:
                reader = open_real_source(self.source)
                detector = (self.detector_factory or FaceDetector)()
            self.emit_status(Status.INSUFFICIENT_DATA,
                             "Se formează secvențele" if real else "SIMULARE: se formează secvența; nu se detectează fețe")
            anchor = time.monotonic()
            while not self.stop_event.is_set():
                if real:
                    item = reader.read()
                else:
                    media_time = frame_index / 20.0
                    item = (frame_index, media_time, None) if media_time <= self.duration_s else None
                if item is None:
                    self.emit_status(Status.END_OF_SOURCE, self._end_message(real, reader, frame_index, detection))
                    break
                frame_id, media_time, image = item
                frame_index += 1
                if self.stop_event.wait(max(0.0, anchor + media_time - time.monotonic())):
                    break
                if not real:
                    packet = synthetic_frame(self.source.source_id, self.run_id, frame_id, media_time)
                    self.previews.put(packet)
                    if self._submit(demo_builder.add(packet), packet, request_id, None):
                        request_id += 1
                    continue
                detection = detector.detect(image)
                track_ids, ended = tracker.update(detection.boxes, media_time)
                for track_id in ended:
                    builders.pop(track_id, None)
                # Previzualizare = cadrul întreg + TOATE casetele + numerele lor; modelul primește decupajele.
                self.previews.put(FramePacket(self.source.source_id, self.run_id, frame_id, media_time,
                                              image, detection.boxes, track_ids))
                self._face_state(detection.status, builders)
                for track_id, crop in zip(track_ids, detection.crops):
                    if crop is None:
                        continue  # față prea mică în acest cadru; istoricul ei rămâne, golul e tratat de builder
                    builder = builders.setdefault(track_id, SequenceBuilder(self.config))
                    packet = FramePacket(self.source.source_id, self.run_id, frame_id, media_time, crop)
                    if self._submit(builder.add(packet), packet, request_id, track_id):
                        request_id += 1
        except Exception:
            self.emit_status(Status.ERROR, "Eroare în sursa video; verifică fișierul și modelul de detecție")
        finally:
            demo_builder.clear()
            builders.clear()
            if reader is not None:
                reader.close()  # eliberează captura (P2-S3.4)


class InferenceWorker(QThread):
    """Singurul fir AI: creează predictorul o dată și procesează cererile din coadă, una câte una."""
    result = Signal(object)

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