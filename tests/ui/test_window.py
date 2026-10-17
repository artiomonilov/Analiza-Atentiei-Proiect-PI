import csv
from threading import Event

from PySide6.QtCore import Qt

from audience_analysis.ai.fake_predictor import FakePredictor
from audience_analysis.contracts import PredictionResult, Status
from audience_analysis.engine.controller import EngineController
from audience_analysis.ui.demo_engine import DemoEngine
from audience_analysis.ui.history import ResultHistory
from audience_analysis.ui.main_window import MainWindow


def test_history_dedup_and_csv_errors_are_blank(tmp_path):
    history = ResultHistory()
    ok = PredictionResult("P01", "run1", 0, 0, 1, Status.OK, {"engagement": 2}, "SIMULARE", True, 1, 2)
    error = PredictionResult("P01", "run1", 1, 1, 2, Status.ERROR, None, None, True, 1, 2, "Eroare simulată")
    assert history.add(ok)
    assert not history.add(ok)
    assert history.add(error)
    path = tmp_path/"demo.csv"
    history.export_csv(path)
    with path.open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert rows[1]["engagement"] == ""
    assert all(row["is_demo"] == "True" for row in rows)


def test_ui_demo_commands_history_and_close(qtbot):
    engine = DemoEngine()
    window = MainWindow(engine)
    qtbot.addWidget(window)
    window.show()
    qtbot.mouseClick(window.start_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: len(window.history.records) == 2, timeout=3000)
    assert "SIMULARE" in window.banner.text()
    assert window.history.records[-1].levels is None
    window.on_result(window.history.records[-1])
    assert len(window.history.records) == 2
    qtbot.mouseClick(window.stop_button, Qt.MouseButton.LeftButton)
    assert window.current_run is None
    window.on_result(window.history.records[0])
    assert window.current_run is None
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=2000)
    assert engine.is_shutdown


def test_close_during_prediction_is_cooperative(qtbot, config):
    entered, release = Event(), Event()

    class Slow(FakePredictor):
        def predict(self, sequence):
            entered.set()
            if not release.wait(4):
                raise RuntimeError("timeout")
            return super().predict(sequence)

    engine = EngineController(config, lambda: Slow(config), demo=True)
    window = MainWindow(engine)
    qtbot.addWidget(window)
    window.show()
    try:
        window.start_source()
        qtbot.waitUntil(entered.is_set, timeout=3000)
        window.close()
        assert engine.closing
        assert window.isVisible()  # închiderea nu blochează firul principal
        release.set()
        qtbot.waitUntil(lambda: not window.isVisible(), timeout=3000)
        assert engine.is_shutdown
        assert not window.history.records
    finally:
        release.set()
        engine.shutdown()
        qtbot.waitUntil(lambda: engine.is_shutdown, timeout=3000)
