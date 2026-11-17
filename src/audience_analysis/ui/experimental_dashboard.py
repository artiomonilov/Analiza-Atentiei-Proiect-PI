"""Dashboard desktop local; calculele sunt delegate modulelor existente."""
from datetime import date
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtCharts import QChart, QChartView, QLineSeries
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDoubleSpinBox, QFileDialog, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QSlider, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..dashboard_data import (DashboardSession, SessionStore, VideoNavigator, export_annotations,
                              segments, select_interval, validate_annotations, with_head_variation)
from ..temporal_analysis import BlinkEvent
from ..validation import data_quality, read_blinks, save_report
from ..dashboard_data import load_rows


def display_value(value):
    if value is None: return "N/A"
    return f"{value:.4g}" if isinstance(value, float) else str(value)


def make_chart(title, traces):
    chart = QChart()
    chart.setTitle(title)
    chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)
    points = 0
    truncated = False
    colors = ("#4f46e5", "#ea580c", "#0891b2", "#be185d", "#15803d")
    for trace_index, (name, groups) in enumerate(traces):
        for index, group in enumerate(groups):
            if not group: continue
            series = QLineSeries()
            series.setName(name)
            series.setColor(QColor(colors[trace_index % len(colors)]))
            # Buget de randare: se omit segmente întregi după 10000 de puncte,
            # fără a uni artificial capetele unor intervale diferite.
            if points + len(group) > 10000:
                truncated = True
                group = group[:max(0, 10000 - points)]
            if not group: break
            for x, y in group: series.append(float(x), float(y))
            series.setPointsVisible(len(group) == 1)
            chart.addSeries(series)
            points += len(group)
            if index:
                for marker in chart.legend().markers(series): marker.setVisible(False)
    chart.createDefaultAxes()
    if not points: chart.setTitle(title + " · N/A")
    elif truncated: chart.setTitle(title + " · limită 10000 puncte: restrânge intervalul")
    for axis in chart.axes(Qt.Orientation.Horizontal): axis.setTitleText("Timp (s)")
    view = QChartView(chart)
    view.setRenderHint(QPainter.RenderHint.Antialiasing)
    view.setMinimumHeight(250)
    view.setProperty("point_count", points)
    return view


class ExperimentalDashboard(QMainWindow):
    def __init__(self, store_root=Path("data/dashboard_sessions")):
        super().__init__()
        self.store = SessionStore(store_root)
        self.sessions, self.managed, self.navigator = [], {}, None
        self.current_timestamp, self.pending_start = None, None
        self.setWindowTitle("AnalizaAtentiei — validare experimentală locală")
        self.resize(1250, 900)
        root = QWidget(); self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        top = QHBoxLayout(); layout.addLayout(top)
        self.selector = QComboBox(); self.selector.currentIndexChanged.connect(self.activate)
        top.addWidget(self.selector, 1)
        self.button(top, "Import CSV", self.import_csv)
        self.button(top, "Deschide sesiune", self.open_session)
        self.button(top, "Salvează sesiune", self.save_session)
        self.button(top, "Elimină sesiune", self.remove_session)
        meta = QHBoxLayout(); layout.addLayout(meta)
        self.identifier, self.experiment_date = QLineEdit(), QLineEdit(date.today().isoformat())
        self.role = QComboBox(); self.role.addItems(["validation", "development", "calibration"])
        for label, widget in (("ID anonim", self.identifier), ("Data ISO", self.experiment_date), ("Rol", self.role)):
            meta.addWidget(QLabel(label)); meta.addWidget(widget)
        self.button(meta, "Aplică metadatele", self.apply_metadata)
        self.summary = QLabel("Importă un CSV de măsurători. Video este opțional.")
        self.summary.setWordWrap(True); layout.addWidget(self.summary)
        interval = QHBoxLayout(); layout.addLayout(interval)
        self.start_ms, self.end_ms = QDoubleSpinBox(), QDoubleSpinBox()
        for widget in (self.start_ms, self.end_ms): widget.setRange(0, 1e12); widget.setDecimals(0)
        interval.addWidget(QLabel("Interval grafice (ms):")); interval.addWidget(self.start_ms); interval.addWidget(self.end_ms)
        self.button(interval, "Actualizează graficele", self.refresh)
        self.tabs = QTabWidget(); layout.addWidget(self.tabs, 1)
        self.chart_tab = QWidget(); self.chart_layout = QGridLayout(self.chart_tab)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(self.chart_tab)
        self.tabs.addTab(scroll, "Grafice")
        self.quality = QPlainTextEdit(); self.quality.setReadOnly(True); self.tabs.addTab(self.quality, "Calitatea datelor")
        self.build_events()
        self.build_video()
        self.build_validation()
        self.build_protocol()
        self.build_comparison()
        self.statusBar().showMessage("Local · nicio inferență sau înregistrare video activată")

    @property
    def session(self):
        index = self.selector.currentIndex()
        return self.sessions[index] if 0 <= index < len(self.sessions) else None

    def button(self, layout, text, action):
        button = QPushButton(text)
        button.clicked.connect(lambda _checked=False: self.guard(action))
        layout.addWidget(button)
        return button

    def guard(self, action):
        try: return action()
        except (ImportError, OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
            self.statusBar().showMessage(str(error))
            QMessageBox.warning(self, "Operațiune nereușită", str(error))

    def choose(self, title, filters="Toate fișierele (*)"):
        path, _ = QFileDialog.getOpenFileName(self, title, "", filters)
        return Path(path) if path else None

    def add_session(self, session):
        self.sessions.append(session)
        self.selector.addItem(session.session_id)
        self.selector.setCurrentIndex(len(self.sessions) - 1)

    def import_csv(self):
        path = self.choose("CSV de măsurători", "CSV (*.csv)")
        if path: self.add_session(DashboardSession.from_csv(path, path.stem))

    def activate(self, _index):
        self.close_video()
        self.pending_start = None
        session = self.session
        if not session: return
        self.identifier.setText(session.session_id); self.experiment_date.setText(session.experiment_date)
        self.role.setCurrentText(session.role)
        self.config_editor.setPlainText(json.dumps(session.config, indent=2, ensure_ascii=False))
        self.start_ms.setValue(session.rows[0]["timestamp_ms"] if session.rows else 0)
        self.end_ms.setValue(session.rows[-1]["timestamp_ms"] if session.rows else 0)
        self.refresh()
        self.refresh_events(reload_manual=True)
        self.load_protocol_table()

    def apply_metadata(self):
        if not self.session: return
        if not self.identifier.text().strip(): raise ValueError("ID anonim obligatoriu.")
        date.fromisoformat(self.experiment_date.text())
        from ..experimental import validate_role_id
        validate_role_id(self.identifier.text().strip(), self.role.currentText())
        configuration = json.loads(self.config_editor.toPlainText())
        if not isinstance(configuration, dict): raise ValueError("La configurație este necesar un obiect JSON.")
        self.session.config = configuration
        self.session.session_id = self.identifier.text().strip()
        self.session.experiment_date = self.experiment_date.text()
        self.session.role = self.role.currentText()
        self.session.config["session_id"] = self.session.session_id
        self.selector.setItemText(self.selector.currentIndex(), self.session.session_id)
        self.config_editor.setPlainText(json.dumps(self.session.config, indent=2, ensure_ascii=False))

    def clear_charts(self):
        while self.chart_layout.count():
            item = self.chart_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def refresh(self):
        session = self.session
        if not session: return
        rows = select_interval(session.rows, self.start_ms.value(), self.end_ms.value())
        gap = session.config.get("max_gap_ms", 500)
        quality = data_quality(rows, gap)
        self.summary.setText(f"{session.session_id} · {session.role} · {len(rows)} eșantioane în interval · "
                             f"cu față: {display_value(quality['face_frames'])} · durata observată: {quality['observed_span_ms']} ms. "
                             "Curbele întrerupte reprezintă date lipsă; graficele nu interpolează. Maximum 10000 puncte/grafic.")
        self.quality.setPlainText(json.dumps(quality, indent=2, ensure_ascii=False))
        self.clear_charts()
        groups = [("Head pose (grade)", ["yaw", "pitch", "roll"]),
                  ("Variație circulară recentă (1s)", ["head_variation"]),
                  ("EAR brut", ["left_ear", "right_ear"]),
                  ("EAR / EAR neutru (dacă există)", ["left_ear_relative", "right_ear_relative"]),
                  ("Iris — coordonate locale brute", ["left_iris_x", "left_iris_y", "right_iris_x", "right_iris_y"]),
                  ("Iris — deplasare față de neutru", ["left_gaze_dx", "left_gaze_dy", "right_gaze_dx", "right_gaze_dy"])]
        variation = with_head_variation(rows, max_gap_ms=gap)
        for index, (title, fields) in enumerate(groups):
            self.chart_layout.addWidget(make_chart(title, [(key, segments(variation, key, gap)) for key in fields]), index // 2, index % 2)
        self.refresh_events()

    def build_events(self):
        widget = QWidget(); layout = QVBoxLayout(widget)
        tools = QHBoxLayout(); layout.addLayout(tools)
        self.button(tools, "Import evenimente automate", self.import_automatic)
        self.button(tools, "Import referințe manuale", self.import_manual)
        self.button(tools, "Export referințe manuale", self.export_manual)
        self.blink_info = QLabel(); self.blink_info.setWordWrap(True); layout.addWidget(self.blink_info)
        self.auto_table = QTableWidget(0, 5); self.auto_table.setHorizontalHeaderLabels(["Ochi", "Început ms", "Sfârșit ms", "Durată ms", "Statut"])
        self.auto_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(QLabel("Detecții automate — nu sunt transformate în referințe")); layout.addWidget(self.auto_table)
        self.manual_table = QTableWidget(0, 3); self.manual_table.setHorizontalHeaderLabels(["Ochi left/right", "Început ms", "Sfârșit ms"])
        self.manual_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(QLabel("Referințe manuale independente — celule editabile")); layout.addWidget(self.manual_table)
        editing = QHBoxLayout(); layout.addLayout(editing)
        self.button(editing, "Adaugă rând manual", lambda: self.manual_table.insertRow(self.manual_table.rowCount()))
        self.button(editing, "Șterge rând selectat", self.delete_annotation_row)
        self.button(editing, "Aplică editările manuale", self.apply_manual)
        self.event_chart_layout = QVBoxLayout(); layout.addLayout(self.event_chart_layout)
        self.tabs.addTab(widget, "Clipiri și referințe")

    def import_automatic(self):
        if not self.session: return
        path = self.choose("Evenimente automate CSV", "CSV (*.csv)")
        if path: self.session.automatic = read_blinks(path); self.refresh_events()

    def import_manual(self):
        if not self.session: return
        path = self.choose("Referințe manuale CSV", "CSV (*.csv)")
        if path: self.session.manual = validate_annotations(read_blinks(path)); self.refresh_events(reload_manual=True)

    def refresh_events(self, reload_manual=False):
        session = self.session
        if not session: return
        self.auto_table.setRowCount(len(session.automatic or []))
        for i, event in enumerate(session.automatic or []):
            for col, value in enumerate((event.eye, event.start_ms, event.end_ms, event.duration_ms, "automat nevalidat")):
                self.auto_table.setItem(i, col, QTableWidgetItem(str(value)))
        if reload_manual:
            self.manual_table.setRowCount(len(session.manual or []))
            for i, event in enumerate(session.manual or []):
                for col, value in enumerate((event.eye, event.start_ms, event.end_ms)):
                    self.manual_table.setItem(i, col, QTableWidgetItem(str(value)))
        self.blink_info.setText("Evenimente din fișier; frecvența cere ≥10s de EAR valid și blink_detection_enabled=true. " +
                               json.dumps(session.blink_summary(), ensure_ascii=False).replace("null", "N/A"))
        while self.event_chart_layout.count():
            item = self.event_chart_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        traces = []
        for name, events, offset in (("Automat", session.automatic, 0), ("Manual", session.manual, .25)):
            for eye, y in (("left", 0), ("right", 1)):
                groups = [[(e.start_ms / 1000, y + offset), (e.end_ms / 1000, y + offset)] for e in (events or [])
                          if e.eye == eye and e.end_ms >= self.start_ms.value() and e.start_ms <= self.end_ms.value()]
                traces.append((name + " " + eye, groups))
        self.event_chart_layout.addWidget(make_chart("Evenimente: left=0, right=1; manual +0.25", traces))

    def delete_annotation_row(self):
        for row in sorted({index.row() for index in self.manual_table.selectedIndexes()}, reverse=True): self.manual_table.removeRow(row)

    def apply_manual(self):
        if not self.session: return
        events = []
        for row in range(self.manual_table.rowCount()):
            values = [self.manual_table.item(row, col).text().strip() if self.manual_table.item(row, col) else "" for col in range(3)]
            eye, start, end = values[0], int(values[1]), int(values[2])
            events.append(BlinkEvent(eye, start, end, end - start, "manual_reference"))
        self.session.manual = validate_annotations(events)
        self.refresh_events(reload_manual=True)

    def export_manual(self):
        if not self.session: return
        self.apply_manual()
        path, _ = QFileDialog.getSaveFileName(self, "Export referințe — fișier nou", "manual_blinks.csv", "CSV (*.csv)")
        if path: export_annotations(Path(path), self.session.manual or [])

    def build_video(self):
        widget = QWidget(); layout = QVBoxLayout(widget)
        self.button(layout, "Deschide video autorizat pentru adnotare", self.open_video)
        self.video_preview = QLabel("Opțional: dashboardul funcționează și fără video.")
        self.video_preview.setAlignment(Qt.AlignmentFlag.AlignCenter); self.video_preview.setMinimumHeight(280)
        layout.addWidget(self.video_preview, 1)
        self.video_position = QLabel("Timestamp de referință: N/A"); layout.addWidget(self.video_position)
        self.video_slider = QSlider(Qt.Orientation.Horizontal); self.video_slider.valueChanged.connect(lambda value: self.guard(lambda: self.show_frame(value)))
        layout.addWidget(self.video_slider)
        controls = QHBoxLayout(); layout.addLayout(controls)
        self.button(controls, "Cadru anterior", lambda: self.video_slider.setValue(self.video_slider.value() - 1))
        self.button(controls, "Cadru următor", lambda: self.video_slider.setValue(self.video_slider.value() + 1))
        self.annotation_eye = QComboBox(); self.annotation_eye.addItems(["left", "right"]); controls.addWidget(self.annotation_eye)
        self.button(controls, "Marchează început", self.mark_start)
        self.button(controls, "Marchează sfârșit", self.mark_end)
        self.annotation_kind = QComboBox(); self.annotation_kind.addItems(["blink", "face_absent", "condition"])
        controls.addWidget(self.annotation_kind)
        self.condition_label = QLineEdit("neutral"); self.condition_label.setPlaceholderText("Condiție observată, fără grade presupuse")
        controls.addWidget(self.condition_label)
        self.tabs.addTab(widget, "Adnotare video")

    def close_video(self):
        if self.navigator: self.navigator.close()
        self.navigator, self.current_timestamp, self.pending_start = None, None, None
        if hasattr(self, "video_preview"): self.video_preview.setText("Niciun video deschis")
        if hasattr(self, "video_position"): self.video_position.setText("Timestamp de referință: N/A")

    def open_video(self):
        if not self.session: return
        path = self.choose("Video autorizat", "Video (*.mp4 *.avi *.mov *.mkv);;Toate (*)")
        if not path: return
        self.close_video()
        self.navigator = VideoNavigator(path, self.session.rows)
        self.session.video_path = path.resolve()
        self.video_slider.setRange(0, self.navigator.count - 1)
        self.video_slider.setValue(0); self.show_frame(0)

    def show_frame(self, index):
        if not self.navigator: return
        self.current_timestamp = None
        frame, timestamp = self.navigator.read(index)
        self.current_timestamp = timestamp
        image = QImage(frame.data, frame.shape[1], frame.shape[0], frame.strides[0], QImage.Format.Format_BGR888).copy()
        self.video_preview.setPixmap(QPixmap.fromImage(image).scaled(self.video_preview.size(), Qt.AspectRatioMode.KeepAspectRatio))
        self.video_position.setText(f"Cadru {index} · timestamp CSV: {display_value(timestamp)} ms. "
                                    "N/A: adnotarea este dezactivată; necesită frame_index corespunzător.")

    def mark_start(self):
        if self.current_timestamp is None: raise ValueError("Nu există o asociere sigură cadru–timestamp CSV.")
        self.pending_start = (self.annotation_kind.currentText(), self.annotation_eye.currentText(), self.condition_label.text().strip(), self.current_timestamp)
        self.statusBar().showMessage(f"Început manual: {self.pending_start}")

    def mark_end(self):
        if self.pending_start is None or self.current_timestamp is None: raise ValueError("Marchează începutul și alege un cadru sincronizat.")
        kind, eye, label, start = self.pending_start
        if kind == "blink":
            event = BlinkEvent(eye, start, self.current_timestamp, self.current_timestamp - start, "manual_reference")
            self.session.manual = validate_annotations([*(self.session.manual or []), event])
        else:
            from ..experimental import validate_conditions
            item = {"kind": kind, "label": label or kind, "start_ms": start, "end_ms": self.current_timestamp}
            self.session.interval_annotations = validate_conditions([*self.session.interval_annotations, item], self.session.rows)
            self.load_protocol_table()
        self.pending_start = None
        self.refresh_events(reload_manual=True)

    def build_validation(self):
        widget = QWidget(); layout = QVBoxLayout(widget)
        tools = QHBoxLayout(); layout.addLayout(tools)
        self.button(tools, "Import referințe geometrice", self.import_geometry)
        self.button(tools, "Import calibrare", self.import_calibration)
        self.button(tools, "Import config validare", self.import_config)
        self.button(tools, "Import pachet înghețat", self.import_frozen_plan)
        self.config_editor = QPlainTextEdit(); layout.addWidget(self.config_editor)
        self.button(layout, "Evaluează sesiunea completă", self.evaluate_session)
        self.button(layout, "Export explicit raport JSON/CSV", self.export_report)
        self.metrics_table = QTableWidget(0, 2); self.metrics_table.setHorizontalHeaderLabels(["Metrică / scenariu", "Valoare"])
        self.metrics_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.metrics_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.metrics_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); layout.addWidget(self.metrics_table, 1)
        self.tabs.addTab(widget, "Validare și scenarii")

    def import_geometry(self):
        if not self.session: return
        path = self.choose("Referințe geometrice independente", "CSV (*.csv)")
        if path: self.session.references = load_rows(path)

    def import_calibration(self):
        if not self.session: return
        from ..calibration import CalibrationManager
        path = self.choose("Profil calibrare", "JSON (*.json)")
        if path:
            CalibrationManager.load(path)
            self.session.calibration_path = path.resolve()
            self.statusBar().showMessage(f"Calibrare: {path.name}")

    def import_config(self):
        if not self.session: return
        path = self.choose("Configurație validare", "JSON (*.json)")
        if path: self.config_editor.setPlainText(path.read_text(encoding="utf-8"))

    def evaluate_session(self):
        if not self.session: return None
        self.session.config = json.loads(self.config_editor.toPlainText())
        report = self.session.evaluate()
        values = []
        def flatten(value, path=""):
            if isinstance(value, dict):
                for key, item in value.items(): flatten(item, path + "." + key if path else key)
            elif isinstance(value, list):
                for index, item in enumerate(value): flatten(item, f"{path}[{index}]")
            else: values.append((path, display_value(value)))
        flatten(report)
        self.metrics_table.setRowCount(len(values))
        for row, pair in enumerate(values):
            for col, value in enumerate(pair): self.metrics_table.setItem(row, col, QTableWidgetItem(value))
        return report

    def export_report(self):
        report = self.evaluate_session()
        if report is None: return
        parent = QFileDialog.getExistingDirectory(self, "Director părinte pentru raport nou")
        if parent:
            from uuid import uuid4
            output = Path(parent) / ("report-" + str(uuid4()))
            save_report(report, output)
            self.statusBar().showMessage(f"Raport exportat: {output}")

    def save_session(self):
        if not self.session: return
        self.apply_metadata()
        if self.session.manual is not None or self.manual_table.rowCount(): self.apply_manual()
        self.apply_protocol()
        self.session.config = json.loads(self.config_editor.toPlainText())
        folder = self.store.save(self.session)
        self.managed[id(self.session)] = folder
        self.statusBar().showMessage(f"Copii CSV/JSON salvate explicit: {folder}")

    def open_session(self):
        folder = QFileDialog.getExistingDirectory(self, "Directorul unei sesiuni salvate")
        if folder:
            session = self.store.load(Path(folder))
            self.add_session(session)
            self.managed[id(session)] = Path(folder)

    def remove_session(self):
        session = self.session
        if not session: return
        folder = self.managed.get(id(session))
        if folder is not None and folder.resolve().parent != self.store.root:
            folder = None  # O sesiune deschisă extern poate fi eliminată doar din memorie.
        text = f"Ștergi definitiv copiile CSV/JSON ale sesiunii din {folder}? Originalele și video extern nu sunt șterse." if folder else "Elimini sesiunea din memorie?"
        if QMessageBox.question(self, "Eliminare sesiune", text) != QMessageBox.StandardButton.Yes: return
        if folder: self.store.delete(folder)
        self.close_video()
        index = self.selector.currentIndex()
        self.selector.blockSignals(True); self.selector.removeItem(index); self.selector.blockSignals(False)
        self.sessions.pop(index); self.managed.pop(id(session), None)
        if self.session: self.activate(self.selector.currentIndex())
        else:
            self.summary.setText("Nicio sesiune activă"); self.quality.clear(); self.metrics_table.setRowCount(0)
            self.auto_table.setRowCount(0); self.manual_table.setRowCount(0); self.clear_charts()

    def closeEvent(self, event):
        self.close_video(); event.accept()

    def import_frozen_plan(self):
        if not self.session: return
        from ..experimental import FrozenExperiment
        path = self.choose("Pachet experimental înghețat", "JSON (*.json)")
        if path:
            plan = FrozenExperiment.load(path)
            plan.validate_target(self.session.session_id, self.session.role)
            self.session.frozen_plan = plan.document
            self.session.config = plan.validation_config(self.session.config)
            self.config_editor.setPlainText(json.dumps(self.session.config, indent=2, ensure_ascii=False))

    def build_protocol(self):
        widget = QWidget(); layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("Marcaje manuale independente: face_absent / condition. Timestampuri CSV, nu grade presupuse."))
        self.protocol_table = QTableWidget(0, 4)
        self.protocol_table.setHorizontalHeaderLabels(["kind", "label", "start_ms", "end_ms"])
        layout.addWidget(self.protocol_table)
        tools = QHBoxLayout(); layout.addLayout(tools)
        self.button(tools, "Adaugă interval", lambda: self.protocol_table.insertRow(self.protocol_table.rowCount()))
        self.button(tools, "Șterge interval", lambda: self.protocol_table.removeRow(self.protocol_table.currentRow()))
        self.button(tools, "Aplică intervalele", self.apply_protocol)
        self.button(tools, "Import intervale CSV", self.import_protocol)
        self.button(tools, "Export intervale CSV", self.export_protocol)
        self.tabs.addTab(widget, "Protocol și condiții")

    def load_protocol_table(self):
        self.protocol_table.setRowCount(len(self.session.interval_annotations) if self.session else 0)
        if not self.session: return
        for i, item in enumerate(self.session.interval_annotations):
            for col, key in enumerate(("kind", "label", "start_ms", "end_ms")):
                self.protocol_table.setItem(i, col, QTableWidgetItem(str(item[key])))

    def apply_protocol(self):
        if not self.session: return
        from ..experimental import validate_conditions
        items = []
        for row in range(self.protocol_table.rowCount()):
            values = [self.protocol_table.item(row, c).text().strip() if self.protocol_table.item(row, c) else "" for c in range(4)]
            items.append({"kind": values[0], "label": values[1], "start_ms": int(values[2]), "end_ms": int(values[3])})
        self.session.interval_annotations = validate_conditions(items, self.session.rows)
        self.load_protocol_table()

    def import_protocol(self):
        if not self.session: return
        from ..experimental import read_conditions
        path = self.choose("Marcaje de protocol independente", "CSV (*.csv)")
        if path:
            self.session.interval_annotations = read_conditions(path, self.session.rows)
            self.load_protocol_table()

    def export_protocol(self):
        if not self.session: return
        from ..experimental import export_conditions
        self.apply_protocol()
        path, _ = QFileDialog.getSaveFileName(self, "Export protocol — fișier nou", "conditions.csv", "CSV (*.csv)")
        if path: export_conditions(path, self.session.interval_annotations, self.session.rows)

    def build_comparison(self):
        widget = QWidget(); layout = QVBoxLayout(widget)
        self.button(layout, "Compară sesiunile C / D / V încărcate", self.refresh_comparison)
        self.comparison_table = QTableWidget(0, 7)
        self.comparison_table.setMinimumHeight(160)
        self.comparison_table.setHorizontalHeaderLabels(["ID", "Rol", "Data", "Durată ms", "Acoperire cap", "Yaw MAE", "Blink L F1"])
        self.comparison_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.comparison_table)
        self.comparison_details = QPlainTextEdit(); self.comparison_details.setReadOnly(True); self.comparison_details.setMinimumHeight(140); layout.addWidget(self.comparison_details)
        self.comparison_charts = QVBoxLayout(); layout.addLayout(self.comparison_charts)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(widget)
        self.tabs.addTab(scroll, "Comparație C/D/V")

    def refresh_comparison(self):
        from ..experimental import compare_sessions
        result = compare_sessions(self.sessions)
        self.comparison_table.setRowCount(len(result))
        for row, item in enumerate(result):
            for col, key in enumerate(("session_id", "role", "date", "duration_ms", "head_valid_fraction", "yaw_mae", "left_blink_f1")):
                self.comparison_table.setItem(row, col, QTableWidgetItem(display_value(item[key])))
        self.comparison_details.setPlainText(json.dumps(result, indent=2, ensure_ascii=False))
        while self.comparison_charts.count():
            item = self.comparison_charts.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for key in ("head_valid_fraction", "yaw_mae", "left_blink_f1"):
            groups = [[(index, item[key])] for index, item in enumerate(result) if item[key] is not None]
            chart = make_chart(f"{key} — indexul sesiunii în tabel, nu timp", [(key, groups)])
            for axis in chart.chart().axes(Qt.Orientation.Horizontal): axis.setTitleText("Index sesiune (0,1,...)")
            chart.setMinimumHeight(240)
            self.comparison_charts.addWidget(chart)
        return result
