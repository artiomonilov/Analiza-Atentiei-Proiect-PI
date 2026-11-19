
from collections.abc import Callable
from uuid import uuid4

from PySide6.QtCore import QCoreApplication, QObject, Qt, Signal, Slot

from ..config import SequenceConfig
from ..contracts import FramePacket, PredictionResult, Predictor, SourceConfig, SourceStatusEvent, Status
from .scheduler import LatestScheduler, ResultGate
from .stats import EngineStats, format_report
from .workers import FeatureStore, InferenceWorker, PreviewStore, SourceWorker


class EngineController(QObject):
    """Leagă sursele, coada, firul AI și UI-ul."""
    result_ready = Signal(object)
    status_changed = Signal(object)
    shutdown_finished = Signal()
    geometry_ready = Signal(object)
    model_status_changed = Signal(object)
    run_finished = Signal(object)

    def __init__(self, config: SequenceConfig, predictor_factory: Callable[[], Predictor], *, demo: bool, duration_s: float = 30,
                 detector_factory: Callable[[], object] | None = None, geometry_factory=None,
                 reader_factory=None, realtime=True):
        if QCoreApplication.instance() is None:
            raise RuntimeError("Creează QCoreApplication/QApplication înaintea motorului")
        super().__init__()
        # demo = marcajul pe care trebuie să-l poarte răspunsurile predictorului (True: simulat, False: real).
        # detector_factory: None => YuNet implicit; se poate injecta un detector pentru teste.
        self.config, self.duration_s, self.detector_factory = config, duration_s, detector_factory
        from ..video.sequences import SequenceBuilder
        SequenceBuilder(config)  # validează bugetul înainte de pornirea firelor
        self.geometry_factory, self.reader_factory, self.realtime = geometry_factory, reader_factory, realtime
        self.features, self.latest_features, self.waiting_workers = FeatureStore(), {}, {}
        self.worker_statuses = FeatureStore()
        self.sources: dict[str, SourceConfig] = {}
        self.active: dict[str, SourceWorker] = {}
        self.source_threads: list[SourceWorker] = []
        self.scheduler, self.gate, self.previews = LatestScheduler(), ResultGate(), PreviewStore()
        self.engine_stats = EngineStats()  # P2-S4.3: timpi, cereri înlocuite, cadre fără față ...
        self.closing = False
        self._ending: dict[str, SourceStatusEvent] = {}  # END_OF_SOURCE amânat până sosește ultimul rezultat
        self._shutdown_emitted = False
        self.ai_worker = InferenceWorker(predictor_factory, self.scheduler, demo=demo)
        self.ai_worker.result.connect(self._accept_result, Qt.ConnectionType.QueuedConnection)
        self.ai_worker.model_status.connect(self.model_status_changed, Qt.ConnectionType.QueuedConnection)
        self.ai_worker.finished.connect(self._thread_finished)
        self.ai_worker.start()

    def add_source(self, config: SourceConfig) -> None:
        """Înregistrează o sursă (nu o pornește)."""
        if self.closing:
            raise ValueError("Motor închis")
        existing = self.sources.get(config.source_id)
        if existing is None and len(self.sources) >= self.scheduler.max_sources:
            raise ValueError("Limita de surse înregistrate a fost atinsă")
        if existing == config:
            raise ValueError("Identificator duplicat cu aceeași configurație")
        if existing is not None:
            # Același ID, altă sursă (ex. demo -> fișier): oprește rularea veche și înlocuiește configurația.
            self.stop_source(config.source_id)
        self.sources[config.source_id] = config

    def start_source(self, source_id: str) -> str:
        """Pornește (sau repornește) o sursă cu un run_id nou și emite STARTED."""
        if self.closing:
            raise RuntimeError("Motorul este închis")
        source = self.sources[source_id]
        if source_id in self.active:
            self.stop_source(source_id)
        self._ending.pop(source_id, None)
        run_id = uuid4().hex
        self.gate.activate(source_id, run_id)
        self.scheduler.activate(source_id, run_id)
        self.previews.activate(source_id, run_id)
        self.features.activate(source_id, run_id)
        self.worker_statuses.activate(source_id, run_id)
        self.latest_features.pop(source_id, None)
        self.engine_stats.start_run(source_id, run_id, self.scheduler.replaced_counts().get(source_id, 0))
        worker = SourceWorker(source, run_id, self.config, self.scheduler, self.previews, duration_s=self.duration_s,
                              detector_factory=self.detector_factory, stats=self.engine_stats,
                              geometry_factory=self.geometry_factory, features=self.features,
                              reader_factory=self.reader_factory, realtime=self.realtime, statuses=self.worker_statuses)
        self.active[source_id] = worker
        self.waiting_workers[source_id] = worker
        worker.status.connect(self._accept_status, Qt.ConnectionType.QueuedConnection)
        worker.features_ready.connect(self._accept_features, Qt.ConnectionType.QueuedConnection)
        worker.status_ready.connect(self._poll_status, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(self._thread_finished)
        self.status_changed.emit(SourceStatusEvent(uuid4().hex, source_id, run_id, Status.STARTED, "SIMULARE pornită" if source.kind == "demo" else "Sursă pornită"))
        self._launch_waiting_workers()
        return run_id

    def stop_source(self, source_id: str) -> None:
        """Oprește sursa: invalidează rularea, golește coada și previzualizarea, cere oprirea firului și emite STOPPED. Nu blochează UI."""
        worker = self.active.pop(source_id, None)
        self._ending.pop(source_id, None)
        self.gate.invalidate(source_id)
        self.scheduler.deactivate(source_id)
        self.previews.invalidate(source_id)
        self.features.invalidate(source_id)
        self.worker_statuses.invalidate(source_id)
        self.latest_features.pop(source_id, None)
        pending = self.waiting_workers.pop(source_id, None)
        if pending is not None:
            pending.deleteLater()
        if worker:
            worker.stop()
            self.status_changed.emit(SourceStatusEvent(uuid4().hex, source_id, worker.run_id, Status.STOPPED, "Sursă oprită; rezultatele vechi sunt invalidate"))

    def remove_source(self, source_id: str) -> None:
        """Oprește sursa, o uită și emite REMOVED."""
        run_id = self.gate.runs.get(source_id, uuid4().hex)
        self.stop_source(source_id)
        self.sources.pop(source_id, None)
        self.engine_stats.remove_source(source_id)
        self.scheduler.forget_source(source_id)
        self.status_changed.emit(SourceStatusEvent(uuid4().hex, source_id, run_id, Status.REMOVED, "Sursă eliminată"))

    def stats(self) -> list[dict]:
        """P2-S4.3: statisticile rulării curente a fiecărei surse (un dicționar per sursă, ușor de exportat)."""
        return self.engine_stats.snapshot(self.scheduler.replaced_counts())

    def stats_report(self) -> str:
        """Aceleași statistici ca text, gata de afișat în UI sau de copiat în raport."""
        return format_report(self.stats())

    def take_latest_preview(self, source_id: str) -> FramePacket | None:
        """Ultimul cadru al sursei (imagine + face_boxes + track_ids), sau None dacă nu a venit unul nou. Chemat periodic de UI."""
        return self.previews.take(source_id)

    def take_latest_features(self, source_id):
        return self.latest_features.pop(source_id, None)

    @Slot(str, str)
    def _accept_features(self, source_id, run_id):
        if self.closing or self.gate.runs.get(source_id) != run_id:
            return
        features = self.features.take(source_id)
        if features is not None and features.run_id == run_id:
            self.latest_features[source_id] = features
            self.geometry_ready.emit(features)

    def _launch_waiting_workers(self):
        for source_id, worker in list(self.waiting_workers.items()):
            if self.closing or self.gate.runs.get(source_id) != worker.run_id:
                continue
            if any(thread.source.source_id == source_id and thread.isRunning() for thread in self.source_threads):
                continue
            self.waiting_workers.pop(source_id)
            self.source_threads.append(worker)
            worker.start()

    @Slot(str, str)
    def _poll_status(self, source_id, run_id):
        if self.closing or self.gate.runs.get(source_id) != run_id:
            return
        event = self.worker_statuses.take(source_id)
        if event is not None and event.run_id == run_id:
            self._accept_status(event)

    @Slot(object)
    def _accept_result(self, result: PredictionResult) -> None:
        """Primește un rezultat din firul AI și îl trimite în UI dacă trece de ResultGate."""
        if self.closing:
            return
        completed = self.scheduler.complete(result.source_id, result.request_id, run_id=result.run_id)
        accepted = completed and self.gate.accept(result)
        self.engine_stats.result(result, accepted)
        if accepted:
            self.result_ready.emit(result)
        event = self._ending.get(result.source_id)
        if event is not None and not self._results_outstanding(result.source_id):
            self._finish_source(self._ending.pop(result.source_id))

    @Slot(object)
    def _accept_status(self, event: SourceStatusEvent) -> None:
        """Primește stările de la SourceWorker și le trimite în UI."""
        if self.closing or self.gate.runs.get(event.source_id) != event.run_id:
            return
        if event.status == Status.END_OF_SOURCE:
            self.active.pop(event.source_id, None)
            if self._results_outstanding(event.source_id):
                # UI-ul uită rularea la END_OF_SOURCE: anunțăm sfârșitul abia după ultimul rezultat.
                self._ending[event.source_id] = event
            else:
                self._finish_source(event)
            return
        if event.status == Status.ERROR:
            self.active.pop(event.source_id, None)
            self.gate.invalidate(event.source_id)
            self.scheduler.deactivate(event.source_id)
            self.previews.invalidate(event.source_id)
            self.features.invalidate(event.source_id)
            self.worker_statuses.invalidate(event.source_id)
        self.status_changed.emit(event)

    def _results_outstanding(self, source_id: str) -> bool:
        """Adevărat cât timp o cerere trimisă (și neînlocuită) a sursei nu și-a primit încă răspunsul."""
        return self.scheduler.has_outstanding(source_id)

    def _finish_source(self, event: SourceStatusEvent) -> None:
        """Încheie rularea sursei (gate, coadă, previzualizare) și trimite evenimentul final în UI."""
        self.gate.invalidate(event.source_id)
        self.scheduler.deactivate(event.source_id)
        self.previews.invalidate(event.source_id)
        self.features.invalidate(event.source_id)
        self.worker_statuses.invalidate(event.source_id)
        self.status_changed.emit(event)

    def shutdown(self) -> None:
        """Închidere cooperativă: oprește toate sursele și trezește firul AI."""
        if self.closing:
            return
        self.closing = True
        for source_id in list(self.active):
            self.stop_source(source_id)
        self.scheduler.close()  # trezește workerul AI aflat în Condition.wait()
        self._thread_finished()

    @property
    def is_shutdown(self) -> bool:
        """True după shutdown(), când firul AI și toate firele surselor s-au terminat."""
        return self.closing and not self.ai_worker.isRunning() and not any(t.isRunning() for t in self.source_threads)

    @Slot()
    def _thread_finished(self) -> None:
        """Șterge lucrătorii terminați și emite shutdown_finished o singură dată, când totul s-a oprit."""
        for worker in self.source_threads[:]:
            if not worker.isRunning():
                self.source_threads.remove(worker)
                outcome = worker.outcome
                worker.deleteLater()
                if outcome is not None:
                    self.run_finished.emit(outcome)
        self._launch_waiting_workers()
        if self.is_shutdown and not self._shutdown_emitted:
            self._shutdown_emitted = True
            self.shutdown_finished.emit()
