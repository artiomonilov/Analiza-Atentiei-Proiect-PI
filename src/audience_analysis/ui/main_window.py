from PySide6.QtCore import QTimer, Qt, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QMainWindow, QPushButton, QVBoxLayout, QWidget

from ..contracts import PredictionResult, SourceConfig, SourceStatusEvent, Status
from .history import ResultHistory


class MainWindow(QMainWindow):
    """Motor injectat. Widgeturile nu citesc video și nu apelează predictorul."""

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.source = SourceConfig("P01", "Participant sintetic", "demo")
        self.current_run: str | None = None
        self.history = ResultHistory()
        self._closing = False
        self._allow_close = False
        self.setWindowTitle("Mini-template P1 / P2 / P3")
        self.resize(720, 650)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        self.banner = QLabel("SIMULARE — fără analiză AI reală")
        self.banner.setStyleSheet("background:#ffdc86; color:#292318; padding:12px; font-weight:bold;")
        layout.addWidget(self.banner)
        layout.addWidget(QLabel(self.source.display_name))
        self.preview = QLabel("Previzualizare sintetică — fără persoane")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(220)
        layout.addWidget(self.preview)
        controls = QHBoxLayout()
        self.start_button = QPushButton("Pornește")
        self.stop_button = QPushButton("Oprește")
        self.start_button.clicked.connect(self.start_source)
        self.stop_button.clicked.connect(lambda: self.engine.stop_source(self.source.source_id))
        self.stop_button.setEnabled(False)
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        layout.addLayout(controls)
        self.status_label = QLabel("Pregătit pentru simulare")
        self.result_label = QLabel("Rezultat: —")
        self.interval_label = QLabel("Interval analizat: —")
        for widget in (self.status_label, self.result_label, self.interval_label):
            widget.setWordWrap(True)
            layout.addWidget(widget)
        self.history_list = QListWidget()
        layout.addWidget(self.history_list)
        # TODO P3-S2.1/P3-S5.1: intrare formular + SourceConfig; construiește grila
        # folosind comenzile motorului; ieșire carduri independente; teste CRUD/restart.
        # TODO P3-S5.3/P3-S5.4: extinde ResultHistory într-un tabel și dialog CSV;
        # verifică rânduri unice, is_demo și celule goale la eroare.
        self.engine.result_ready.connect(self.on_result)
        self.engine.status_changed.connect(self.on_status)
        self.engine.shutdown_finished.connect(self.finish_close, Qt.ConnectionType.QueuedConnection)
        self.engine.add_source(self.source)
        self.preview_timer = QTimer(self)
        self.preview_timer.setInterval(50)
        self.preview_timer.timeout.connect(self.refresh_preview)
        self.preview_timer.start()

    @Slot()
    def start_source(self) -> None:
        self.engine.start_source(self.source.source_id)

    @Slot(object)
    def on_status(self, event: SourceStatusEvent) -> None:
        if event.source_id != self.source.source_id:
            return
        if event.status == Status.STARTED:
            self.current_run = event.run_id
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.result_label.setText("Rezultat: —")
            self.interval_label.setText("Interval analizat: —")
        elif self.current_run != event.run_id:
            return
        self.status_label.setText(f"{event.status}: {event.message}")
        if event.status in {Status.STOPPED, Status.REMOVED, Status.END_OF_SOURCE, Status.ERROR}:
            self.current_run = None
            self.start_button.setEnabled(not self._closing)
            self.stop_button.setEnabled(False)
            self.result_label.setText("Rezultat activ: — (rezultatele anterioare rămân în istoric)")
            self.preview.clear()

    @Slot(object)
    def on_result(self, result: PredictionResult) -> None:
        if result.source_id != self.source.source_id or result.run_id != self.current_run or not result.is_demo:
            return
        if not self.history.add(result):
            return
        levels = ", ".join(f"{name}: nivel {value}" for name, value in (result.levels or {}).items()) or "—"
        self.result_label.setText(f"SIMULARE · {levels}")
        interval = f"{result.window_start_s:.2f}–{result.window_end_s:.2f} s"
        self.interval_label.setText(f"Interval analizat: {interval} · separat de cadrul curent")
        self.status_label.setText(f"{result.status}: {result.error_message or 'Rezultat simulat'}")
        self.history_list.addItem(f"SIMULARE · cererea {result.request_id} · {interval} · {result.status} · {levels}")

    @Slot()
    def refresh_preview(self) -> None:
        packet = self.engine.take_latest_preview(self.source.source_id)
        if packet is None or packet.run_id != self.current_run:
            return
        frame = packet.image
        image = QImage(frame.data, frame.shape[1], frame.shape[0], frame.strides[0], QImage.Format.Format_BGR888).copy()
        # copy() desprinde QImage de bufferul NumPy înainte ca pachetul să fie eliberat.
        self.preview.setPixmap(QPixmap.fromImage(image).scaled(480, 240, Qt.AspectRatioMode.KeepAspectRatio))

    def closeEvent(self, event) -> None:
        if self._allow_close or self.engine.is_shutdown:
            self.preview_timer.stop()
            event.accept()
            return
        event.ignore()
        self._closing = True
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Se închid cooperativ lucrătorii…")
        self.engine.shutdown()

    @Slot()
    def finish_close(self) -> None:
        if self._closing:
            self._allow_close = True
            self.close()
