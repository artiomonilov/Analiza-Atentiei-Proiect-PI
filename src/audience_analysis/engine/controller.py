from collections.abc import Callable
from uuid import uuid4

from PySide6.QtCore import QCoreApplication, QObject, Qt, Signal, Slot

from ..config import SequenceConfig
from ..contracts import FramePacket, PredictionResult, Predictor, SourceConfig, SourceStatusEvent, Status
from .scheduler import LatestScheduler, ResultGate
from .workers import InferenceWorker, PreviewStore, SourceWorker


class EngineController(QObject):
    result_ready = Signal(object)
    status_changed = Signal(object)
    shutdown_finished = Signal()

    def __init__(self, config: SequenceConfig, predictor_factory: Callable[[], Predictor], *, demo: bool, duration_s: float = 30):
        if QCoreApplication.instance() is None:
            raise RuntimeError("Creează QCoreApplication/QApplication înaintea motorului")
        if not demo:
            raise NotImplementedError("P2-S3: motorul real rămâne punct de integrare explicit")
        super().__init__()
        self.config, self.duration_s = config, duration_s
        self.sources: dict[str, SourceConfig] = {}
        self.active: dict[str, SourceWorker] = {}
        self.source_threads: list[SourceWorker] = []
        self.scheduler, self.gate, self.previews = LatestScheduler(), ResultGate(), PreviewStore()
        self.closing = False
        self._shutdown_emitted = False
        self.ai_worker = InferenceWorker(predictor_factory, self.scheduler, demo=demo)
        self.ai_worker.result.connect(self._accept_result, Qt.ConnectionType.QueuedConnection)
        self.ai_worker.finished.connect(self._thread_finished)
        self.ai_worker.start()

    def add_source(self, config: SourceConfig) -> None:
        if self.closing or config.source_id in self.sources:
            raise ValueError("Motor închis sau identificator duplicat")
        if config.kind != "demo":
            raise NotImplementedError("P2-S3/P2-S5: acest motor acceptă exclusiv surse demo")
        self.sources[config.source_id] = config

    def start_source(self, source_id: str) -> str:
        if self.closing:
            raise RuntimeError("Motorul este închis")
        source = self.sources[source_id]
        if source_id in self.active:
            self.stop_source(source_id)
        run_id = uuid4().hex
        self.gate.activate(source_id, run_id)
        self.scheduler.activate(source_id, run_id)
        self.previews.activate(source_id, run_id)
        worker = SourceWorker(source, run_id, self.config, self.scheduler, self.previews, duration_s=self.duration_s)
        self.active[source_id] = worker
        self.source_threads.append(worker)
        worker.status.connect(self._accept_status, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(self._thread_finished)
        self.status_changed.emit(SourceStatusEvent(uuid4().hex, source_id, run_id, Status.STARTED, "SIMULARE pornită"))
        worker.start()
        return run_id

    def stop_source(self, source_id: str) -> None:
        worker = self.active.pop(source_id, None)
        self.gate.invalidate(source_id)
        self.scheduler.deactivate(source_id)
        self.previews.invalidate(source_id)
        if worker:
            worker.stop()
            self.status_changed.emit(SourceStatusEvent(uuid4().hex, source_id, worker.run_id, Status.STOPPED, "Sursă oprită; rezultatele vechi sunt invalidate"))

    def remove_source(self, source_id: str) -> None:
        run_id = self.gate.runs.get(source_id, uuid4().hex)
        self.stop_source(source_id)
        self.sources.pop(source_id, None)
        self.status_changed.emit(SourceStatusEvent(uuid4().hex, source_id, run_id, Status.REMOVED, "Sursă eliminată"))

    def take_latest_preview(self, source_id: str) -> FramePacket | None:
        return self.previews.take(source_id)

    @Slot(object)
    def _accept_result(self, result: PredictionResult) -> None:
        if not self.closing and self.gate.accept(result):
            self.result_ready.emit(result)

    @Slot(object)
    def _accept_status(self, event: SourceStatusEvent) -> None:
        if self.closing or self.gate.runs.get(event.source_id) != event.run_id:
            return
        if event.status in {Status.END_OF_SOURCE, Status.ERROR}:
            self.active.pop(event.source_id, None)
            self.gate.invalidate(event.source_id)
            self.scheduler.deactivate(event.source_id)
            self.previews.invalidate(event.source_id)
        self.status_changed.emit(event)

    def shutdown(self) -> None:
        if self.closing:
            return
        self.closing = True
        for source_id in list(self.active):
            self.stop_source(source_id)
        self.scheduler.close()  # trezește workerul AI aflat în Condition.wait()
        self._thread_finished()

    @property
    def is_shutdown(self) -> bool:
        return self.closing and not self.ai_worker.isRunning() and not any(t.isRunning() for t in self.source_threads)

    @Slot()
    def _thread_finished(self) -> None:
        for worker in self.source_threads[:]:
            if not worker.isRunning():
                self.source_threads.remove(worker)
                worker.deleteLater()
        if self.is_shutdown and not self._shutdown_emitted:
            self._shutdown_emitted = True
            self.shutdown_finished.emit()
