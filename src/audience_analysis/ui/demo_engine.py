from uuid import uuid4

import numpy as np
from PySide6.QtCore import QCoreApplication, QObject, QTimer, Signal

from ..contracts import FramePacket, PredictionResult, SourceConfig, SourceStatusEvent, Status


class DemoEngine(QObject):
    """Scenariu P3 fără captură, preprocesare, predictor, scheduler sau fire de lucru."""
    result_ready = Signal(object)
    status_changed = Signal(object)
    shutdown_finished = Signal()

    def __init__(self):
        if QCoreApplication.instance() is None:
            raise RuntimeError("Creează aplicația Qt înaintea DemoEngine")
        super().__init__()
        self.sources: dict[str, SourceConfig] = {}
        self.runs: dict[str, str] = {}
        self.previews: dict[str, FramePacket] = {}
        self.timers: dict[str, QTimer] = {}
        self.steps: dict[str, int] = {}
        self.is_shutdown = False
        self.image = np.full((48, 64, 3), (40, 90, 130), dtype=np.uint8)
        self.image[12:36, 20:44] = (100, 190, 220)

    def add_source(self, config: SourceConfig) -> None:
        if self.is_shutdown or config.kind != "demo" or config.source_id in self.sources:
            raise ValueError("DemoEngine acceptă numai surse demo unice")
        self.sources[config.source_id] = config

    def emit_status(self, source: str, run: str, status: Status, message: str) -> None:
        self.status_changed.emit(SourceStatusEvent(uuid4().hex, source, run, status, message))

    def start_source(self, source_id: str) -> str:
        if self.is_shutdown or source_id not in self.sources:
            raise ValueError("Sursă indisponibilă")
        self.stop_source(source_id)
        run_id = uuid4().hex
        self.runs[source_id] = run_id
        self.steps[source_id] = 0
        self.previews[source_id] = FramePacket(source_id, run_id, 0, 0, self.image)
        timer = QTimer(self)
        timer.setInterval(300)
        timer.timeout.connect(lambda: self._advance(source_id, run_id))
        self.timers[source_id] = timer
        self.emit_status(source_id, run_id, Status.STARTED, "SIMULARE P3: scenariu prestabilit")
        timer.start()
        return run_id

    def _advance(self, source_id: str, run_id: str) -> None:
        if self.runs.get(source_id) != run_id:
            return
        step = self.steps[source_id]
        self.steps[source_id] += 1
        if step == 0:
            self.emit_status(source_id, run_id, Status.INSUFFICIENT_DATA, "Scenariu: date insuficiente")
        elif step in (1, 2):
            ok = step == 1
            self.result_ready.emit(PredictionResult(source_id, run_id, step-1, 0, 0.6 if ok else 0.8,
                Status.OK if ok else Status.ERROR, {"engagement": 2} if ok else None,
                "SIMULARE-ui-scenario-v1", True, 0, 0, None if ok else "Eroare simulată pentru verificarea UI"))
        else:
            self.stop_source(source_id)

    def stop_source(self, source_id: str) -> None:
        timer = self.timers.pop(source_id, None)
        if timer:
            timer.stop()
            timer.deleteLater()
        run = self.runs.pop(source_id, None)
        self.previews.pop(source_id, None)
        if run:
            self.emit_status(source_id, run, Status.STOPPED, "Scenariu oprit")

    def remove_source(self, source_id: str) -> None:
        run = self.runs.get(source_id, uuid4().hex)
        self.stop_source(source_id)
        self.sources.pop(source_id, None)
        self.steps.pop(source_id, None)
        self.emit_status(source_id, run, Status.REMOVED, "Sursă eliminată")

    def take_latest_preview(self, source_id: str) -> FramePacket | None:
        return self.previews.pop(source_id, None)

    def shutdown(self) -> None:
        if self.is_shutdown:
            return
        for source_id in list(self.runs):
            self.stop_source(source_id)
        self.is_shutdown = True
        self.shutdown_finished.emit()
