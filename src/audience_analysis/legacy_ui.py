import queue
import time

import cv2

from .legacy_contracts import LABELS, STATUS_TEXT, PipelineConfig, PredictionResult, SourceConfig, Status
from .qt import QtCore as C, QtGui as G, QtWidgets as W, BINDING
from .reporting import SessionLog
from .runtime import CaptureHandle, InferenceWorker


STYLE = """
QMainWindow, QDialog { background: #101827; color: #e2e9f4; }
QWidget { font-family: 'Segoe UI'; font-size: 13px; color: #e2e9f4; }
QFrame#panel, QGroupBox { background: #172235; border: 1px solid #29374d; border-radius: 10px; }
QLabel#title { font-size: 27px; font-weight: 600; }
QLabel#muted { color: #96a7bf; }
QLabel#stat { font-size: 23px; font-weight: 600; color: #70dbc7; }
QPushButton { background: #25364e; border: 1px solid #354962; border-radius: 6px; padding: 9px 14px; }
QPushButton:hover { background: #334c69; }
QPushButton:disabled { color: #69768b; background: #1a2637; }
QPushButton#primary { background: #237d70; border: 1px solid #3baa96; font-weight: 600; }
QPushButton#primary:disabled { background: #203a39; color: #718b86; }
QLineEdit, QComboBox, QListWidget, QTableWidget { background: #101a2b; border: 1px solid #314158; border-radius: 5px; padding: 6px; }
QListWidget::item { padding: 9px; }
QListWidget::item:selected { background: #28435e; }
QHeaderView::section { background: #25344a; padding: 7px; border: 0; }
QScrollArea { border: 0; background: transparent; }
QStatusBar { background: #172235; color: #96a7bf; }
QToolTip { background: #25344a; color: white; }
"""


def label(text, name=None):
    widget = W.QLabel(text)
    widget.setWordWrap(True)
    if name:
        widget.setObjectName(name)
    return widget


class SourceDialog(W.QDialog):
    def __init__(self, next_id, parent):
        super().__init__(parent)
        self.setWindowTitle("Adaugă sursă experimentală")
        self.resize(520, 270)
        layout = W.QFormLayout(self)
        self.identifier = W.QLineEdit(next_id)
        self.kind = W.QComboBox()
        self.kind.addItem("Fișier video", "file")
        self.kind.addItem("Cameră locală", "camera")
        self.kind.addItem("Flux RTSP / HTTP direct", "network")
        self.location = W.QLineEdit()
        self.location.setPlaceholderText("Calea fișierului, indexul camerei sau adresa fluxului")
        browse = W.QPushButton("Alege fișier…")
        browse.clicked.connect(self.browse)
        layout.addRow("Identificator", self.identifier)
        layout.addRow("Tip sursă", self.kind)
        layout.addRow("Locație", self.location)
        layout.addRow("", browse)
        layout.addRow(label("Folosește materiale autorizate pentru cercetare. Identificatorul este local; aplicația nu recunoaște identitatea persoanelor.", "muted"))
        buttons = W.QDialogButtonBox(W.QDialogButtonBox.Ok | W.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def browse(self):
        path, _ = W.QFileDialog.getOpenFileName(self, "Alege video", "", "Video (*.mp4 *.avi *.mov *.mkv *.webm);;Toate fișierele (*)")
        if path:
            self.kind.setCurrentIndex(0)
            self.location.setText(path)

    def source(self):
        identifier = self.identifier.text().strip()
        return SourceConfig(identifier, self.kind.currentData(), self.location.text().strip(), identifier)


class VideoCard(W.QFrame):
    def __init__(self, source):
        super().__init__()
        self.setObjectName("panel")
        layout = W.QVBoxLayout(self)
        title = W.QHBoxLayout()
        title.addWidget(label(source.participant_id))
        title.addStretch()
        title.addWidget(label({"file": "FIȘIER", "camera": "CAMERĂ", "network": "REȚEA"}[source.kind], "muted"))
        layout.addLayout(title)
        self.video = label("Previzualizare disponibilă după pornire", "muted")
        self.video.setAlignment(C.Qt.AlignCenter)
        self.video.setMinimumSize(260, 150)
        self.video.setFixedHeight(190)
        self.video.setStyleSheet("background: #0a111e; border-radius: 6px;")
        layout.addWidget(self.video)
        self.result = label("Angajament estimat: —")
        self.state = label("Pregătit", "muted")
        self.interval = label("Niciun interval analizat", "muted")
        layout.addWidget(self.result)
        layout.addWidget(self.state)
        layout.addWidget(self.interval)

    def show_frame(self, bgr):
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        height, width, _ = rgb.shape
        image = G.QImage(rgb.data, width, height, rgb.strides[0], G.QImage.Format_RGB888).copy()
        pixmap = G.QPixmap.fromImage(image).scaled(self.video.size(), C.Qt.KeepAspectRatio, C.Qt.SmoothTransformation)
        self.video.setPixmap(pixmap)


class MainWindow(W.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Analiza audienței · Laborator video")
        self.resize(1280, 850)
        self.setMinimumSize(1000, 700)
        self.setStyleSheet(STYLE)
        self.sources = []
        self.cards = {}
        self.handles = {}
        self.worker = None
        self.session = None
        self.model_path = None
        self.config = PipelineConfig()
        self.stopping = False
        self.closing = False
        self.last_status = {}
        self.last_arrival = {}
        self.latest_prediction = {}
        self.latest_time = {}
        self.build_ui()
        self.timer = C.QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(70)

    def build_ui(self):
        root = W.QWidget()
        self.setCentralWidget(root)
        outer = W.QVBoxLayout(root)
        outer.setContentsMargins(24, 22, 24, 14)
        outer.setSpacing(16)
        heading = W.QHBoxLayout()
        titles = W.QVBoxLayout()
        titles.addWidget(label("Analiza audienței", "title"))
        titles.addWidget(label("Laborator video  /  Prototip experimental", "muted"))
        heading.addLayout(titles, 1)
        heading.addStretch()
        self.badge = label("FĂRĂ MODEL  ·  PREPROCESARE", "muted")
        self.badge.setMinimumWidth(240)
        heading.addWidget(self.badge)
        outer.addLayout(heading)
        self.summary = label("0 surse  ·  0 evaluabile  ·  Nicio sesiune activă", "stat")
        outer.addWidget(self.summary)
        body = W.QHBoxLayout()
        sidebar = W.QFrame()
        sidebar.setObjectName("panel")
        sidebar.setFixedWidth(265)
        settings = W.QVBoxLayout(sidebar)
        settings.setContentsMargins(16, 16, 16, 16)
        settings.addWidget(label("CONFIGURARE SESIUNE", "muted"))
        self.title_input = W.QLineEdit("Experiment local")
        settings.addWidget(self.title_input)
        self.source_list = W.QListWidget()
        settings.addWidget(self.source_list)
        self.add_button = W.QPushButton("+ Adaugă sursă")
        self.add_button.clicked.connect(self.add_source)
        settings.addWidget(self.add_button)
        self.remove_button = W.QPushButton("Elimină sursa selectată")
        self.remove_button.clicked.connect(self.remove_source)
        settings.addWidget(self.remove_button)
        self.model_button = W.QPushButton("Încarcă model .pt…")
        self.model_button.clicked.connect(self.choose_model)
        settings.addWidget(self.model_button)
        self.clear_model = W.QPushButton("Mod preprocesare")
        self.clear_model.clicked.connect(self.unset_model)
        settings.addWidget(self.clear_model)
        settings.addWidget(label("Fereastră inițială: ~10 s / 16 cadre\nActualizare: la ~2 s\nParametrii se preiau din model.", "muted"))
        self.start_button = W.QPushButton("Pornește sesiunea")
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self.start_session)
        settings.addWidget(self.start_button)
        self.stop_button = W.QPushButton("Oprește")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_session)
        settings.addWidget(self.stop_button)
        self.export_button = W.QPushButton("Exportă CSV / JSON…")
        self.export_button.clicked.connect(self.export_session)
        self.export_button.setEnabled(False)
        settings.addWidget(self.export_button)
        body.addWidget(sidebar)
        content = W.QVBoxLayout()
        scroll = W.QScrollArea()
        scroll.setWidgetResizable(True)
        self.grid_widget = W.QWidget()
        self.grid_widget.setStyleSheet("background: #101827;")
        self.grid = W.QGridLayout(self.grid_widget)
        self.empty = label("Adaugă primul videoclip\n\nVerifică detecția și continuitatea secvențelor.\nÎncarcă un model antrenat pentru estimări experimentale.", "muted")
        self.empty.setAlignment(C.Qt.AlignCenter)
        self.grid.addWidget(self.empty, 0, 0)
        scroll.setWidget(self.grid_widget)
        content.addWidget(scroll, 3)
        details = W.QHBoxLayout()
        details.addWidget(label("ISTORICUL SESIUNII", "muted"))
        details.addStretch()
        self.filter = W.QComboBox()
        self.filter.addItem("Toate sursele", None)
        self.filter.currentIndexChanged.connect(self.refresh_history)
        details.addWidget(self.filter)
        content.addLayout(details)
        self.history = W.QTableWidget(0, 5)
        self.history.setHorizontalHeaderLabels(["Sursă", "Interval media", "Angajament estimat", "Stare", "Inferență"])
        self.history.horizontalHeader().setSectionResizeMode(W.QHeaderView.Stretch)
        self.history.verticalHeader().hide()
        self.history.setEditTriggers(W.QAbstractItemView.NoEditTriggers)
        self.history.setMinimumHeight(170)
        content.addWidget(self.history, 1)
        body.addLayout(content, 1)
        outer.addLayout(body, 1)
        outer.addWidget(label("Rezultate experimentale asociate etichetelor din dataset. Nu reprezintă măsurători ale atenției sau evaluări ale studenților. Imaginile nu sunt salvate.", "muted"))
        self.statusBar().showMessage(f"Pregătit · {BINDING}")

    def add_source(self):
        if len(self.sources) >= 4:
            W.QMessageBox.information(self, "Limită prototip", "Versiunea inițială acceptă maximum 4 surse.")
            return
        number = 1
        ids = {s.source_id for s in self.sources}
        while f"P{number:02}" in ids:
            number += 1
        dialog = SourceDialog(f"P{number:02}", self)
        if dialog.exec() != W.QDialog.Accepted:
            return
        try:
            source = dialog.source()
            if source.source_id in ids:
                raise ValueError("Identificatorul există deja")
        except ValueError as error:
            W.QMessageBox.warning(self, "Sursă invalidă", str(error))
            return
        self.sources.append(source)
        self.rebuild_cards()

    def remove_source(self):
        index = self.source_list.currentRow()
        if index >= 0:
            self.sources.pop(index)
            self.rebuild_cards()

    def rebuild_cards(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cards.clear()
        self.source_list.clear()
        self.filter.clear()
        self.filter.addItem("Toate sursele", None)
        for index, source in enumerate(self.sources):
            self.source_list.addItem(f"{source.source_id}  ·  {source.kind}")
            card = VideoCard(source)
            self.cards[source.source_id] = card
            self.grid.addWidget(card, index//2, index % 2)
            self.filter.addItem(source.participant_id, source.source_id)

    def choose_model(self):
        path, _ = W.QFileDialog.getOpenFileName(self, "Pachet model antrenat", "", "Model PyTorch (*.pt)")
        if path:
            self.model_path = path
            self.badge.setText("MODEL SELECTAT · validare la pornire")

    def unset_model(self):
        self.model_path = None
        self.badge.setText("FĂRĂ MODEL · PREPROCESARE")

    def lock_controls(self, active):
        for control in (self.add_button, self.remove_button, self.model_button, self.clear_model, self.title_input, self.start_button):
            control.setEnabled(not active)
        self.stop_button.setEnabled(active)

    def start_session(self):
        if not self.sources:
            W.QMessageBox.information(self, "Nicio sursă", "Adaugă cel puțin o sursă video.")
            return
        # Retain previous session until a new one really starts.
        self.lock_controls(True)
        self.stopping = False
        self.worker = InferenceWorker(self.model_path)
        self.statusBar().showMessage("Se pregătește motorul de procesare…")

    def begin_capture(self):
        self.config = self.worker.predictor.config if self.worker.predictor else PipelineConfig()
        version = self.worker.predictor.version if self.worker.predictor else None
        self.session = SessionLog(self.title_input.text(), self.sources, self.config, version)
        self.last_status.clear()
        self.last_arrival.clear()
        self.latest_prediction.clear()
        self.latest_time.clear()
        self.history.setRowCount(0)
        self.badge.setText(f"MODEL {version}" if version else "FĂRĂ MODEL · PREPROCESARE")
        for source in self.sources:
            self.handles[source.source_id] = CaptureHandle(source, self.config)
            self.cards[source.source_id].result.setText("Angajament estimat: —")
            self.cards[source.source_id].interval.setText("Se formează prima fereastră")
        self.export_button.setEnabled(True)
        self.statusBar().showMessage("Sesiune activă · sursele sunt procesate local")

    def stop_session(self):
        self.stopping = True
        self.stop_button.setEnabled(False)
        if self.worker:
            self.worker.stop()
        for handle in self.handles.values():
            if handle.stop_requested_at is None:
                handle.stop()
        self.statusBar().showMessage("Se eliberează sursele…")

    def poll(self):
        if self.worker and not self.handles and not self.stopping:
            if self.worker.state == "error":
                W.QMessageBox.warning(self, "Model indisponibil", self.worker.error)
                self.worker.stop()
                self.worker = None
                self.lock_controls(False)
            elif self.worker.state == "ready":
                self.begin_capture()
        for source_id, handle in list(self.handles.items()):
            for _ in range(4):
                try:
                    packet = handle.output.get_nowait()
                except queue.Empty:
                    break
                generation = packet["generation"]
                if self.session.generations.get(source_id) != generation:
                    self.session.invalidate(source_id, generation)
                    self.latest_prediction.pop(source_id, None)
                    self.cards[source_id].result.setText("Angajament estimat: —")
                self.latest_time[source_id] = packet["timestamp"]
                self.last_arrival[source_id] = time.monotonic()
                if packet["frame"] is not None:
                    self.cards[source_id].show_frame(packet["frame"])
                status = packet["status"]
                self.cards[source_id].state.setText(STATUS_TEXT[status])
                if status != self.last_status.get(source_id):
                    result = PredictionResult(source_id, handle.source.participant_id, generation, packet["timestamp"], packet["timestamp"], status, model_version=self.session.metadata["model_version"])
                    self.session.append(result)
                    self.last_status[source_id] = status
                    self.refresh_history()
                if packet["batch"] is not None and not self.stopping:
                    self.worker.submit(packet["batch"])
            if (not self.stopping and not handle.process.is_alive()
                    and self.last_status.get(source_id) not in {Status.ENDED, Status.DISCONNECTED, Status.STOPPED, Status.ERROR}):
                # A decoder may exit before sending its final packet.
                generation = self.session.generations.get(source_id, 0) + 1
                self.session.invalidate(source_id, generation)
                self.latest_prediction.pop(source_id, None)
                self.last_status[source_id] = Status.ERROR
                self.cards[source_id].state.setText(STATUS_TEXT[Status.ERROR])
                self.session.append(PredictionResult(source_id, handle.source.participant_id, generation,
                    self.latest_time.get(source_id, 0), self.latest_time.get(source_id, 0), Status.ERROR))
                self.refresh_history()
            if self.stopping and handle.reap():
                if self.last_status.get(source_id) not in {Status.ENDED, Status.DISCONNECTED, Status.STOPPED, Status.ERROR}:
                    generation = self.session.generations.get(source_id, 0) + 1
                    self.session.invalidate(source_id, generation)
                    self.session.append(PredictionResult(source_id, handle.source.participant_id, generation,
                        self.latest_time.get(source_id, 0), self.latest_time.get(source_id, 0), Status.STOPPED))
                    self.last_status[source_id] = Status.STOPPED
                    self.cards[source_id].state.setText(STATUS_TEXT[Status.STOPPED])
                    self.refresh_history()
                handle.close()
                del self.handles[source_id]
        if self.worker:
            for _ in range(32):
                try:
                    result = self.worker.output.get_nowait()
                except queue.Empty:
                    break
                if self.stopping or not self.session or not self.session.append(result):
                    continue
                self.latest_prediction[result.source_id] = (result, time.monotonic())
                self.cards[result.source_id].result.setText("Angajament estimat: " + (LABELS[result.label] if result.label is not None else "—"))
                self.refresh_history()
        evaluable = 0
        counts = [0]*4
        for source_id, (prediction, arrived) in self.latest_prediction.items():
            age = time.monotonic() - arrived
            card = self.cards.get(source_id)
            if card is None:
                continue
            media_lag = self.latest_time.get(source_id, prediction.end) - prediction.end
            fresh = (age <= self.config.stride_seconds*2 + 1
                     and media_lag <= self.config.stride_seconds*2 + 1
                     and time.monotonic() - self.last_arrival.get(source_id, 0) < 2)
            if fresh and prediction.label is not None:
                evaluable += 1
                counts[prediction.label] += 1
            card.interval.setText(f"{prediction.start:.1f}–{prediction.end:.1f} s · actualizat acum {age:.0f} s" + (" · rezultat vechi" if not fresh else ""))
            card.state.setText(STATUS_TEXT[Status(prediction.status)] if fresh else "Rezultat vechi; se așteaptă date noi")
        distribution = "  /  ".join(f"{LABELS[i]}: {count}" for i, count in enumerate(counts) if count)
        self.summary.setText(f"{len(self.sources)} surse  ·  {evaluable} evaluabile" + (f"  ·  {distribution}" if distribution else ""))
        terminal = {Status.ENDED, Status.DISCONNECTED, Status.STOPPED, Status.ERROR}
        if self.handles and not self.stopping and all(self.last_status.get(s) in terminal for s in self.handles):
            self.stop_session()
        if self.stopping and not self.handles:
            if self.session:
                self.session.finish()
            self.worker = None
            self.latest_prediction.clear()
            self.stopping = False
            self.lock_controls(False)
            self.statusBar().showMessage("Sesiune încheiată · istoricul poate fi exportat")
            if self.closing:
                self.close()

    def refresh_history(self):
        if not hasattr(self, "history"):
            return
        records = self.session.records if self.session else []
        selected = self.filter.currentData()
        records = [r for r in records if selected is None or r.source_id == selected][-300:]
        self.history.setRowCount(len(records))
        for row, record in enumerate(reversed(records)):
            values = [record.participant_id, f"{record.start:.1f}–{record.end:.1f} s",
                      LABELS[record.label] if record.label is not None else "—", STATUS_TEXT[Status(record.status)],
                      f"{record.inference_ms:.0f} ms" if record.inference_ms is not None else "—"]
            for column, value in enumerate(values):
                self.history.setItem(row, column, W.QTableWidgetItem(value))

    def export_session(self):
        if not self.session:
            return
        path, _ = W.QFileDialog.getSaveFileName(self, "Exportă sesiunea", "sesiune.json", "JSON (*.json);;CSV (*.csv)")
        if path:
            try:
                self.session.export(path)
                self.statusBar().showMessage("Export salvat · adresele surselor nu sunt incluse")
            except OSError:
                W.QMessageBox.warning(self, "Export nereușit", "Verifică spațiul liber și permisiunile folderului.")

    def closeEvent(self, event):
        if self.handles or self.worker:
            self.closing = True
            self.stop_session()
            event.ignore()
        else:
            event.accept()

