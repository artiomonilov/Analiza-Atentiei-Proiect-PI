from threading import Event
import subprocess
import sys

from PySide6.QtCore import QThread

from audience_analysis.ai.fake_predictor import FakePredictor
from audience_analysis.contracts import SourceConfig, Status
from audience_analysis.engine.controller import EngineController


def shutdown(engine, qtbot):
    engine.shutdown()
    qtbot.waitUntil(lambda: engine.is_shutdown, timeout=5000)


def test_two_sources_one_factory_and_no_old_results(qtbot, config):
    entered, release = Event(), Event()
    creations, results = [], []

    class SlowFirst(FakePredictor):
        first = True

        def predict(self, sequence):
            if self.first:
                self.first = False
                entered.set()
                if not release.wait(4):
                    raise RuntimeError("test timeout")
            return super().predict(sequence)

    def factory():
        creations.append(QThread.currentThread())
        return SlowFirst(config)

    engine = EngineController(config, factory, demo=True)
    engine.result_ready.connect(results.append)
    try:
        engine.add_source(SourceConfig("P01", "Unu", "demo"))
        engine.add_source(SourceConfig("P02", "Doi", "demo"))
        old_run = engine.start_source("P01")
        qtbot.waitUntil(entered.is_set, timeout=3000)
        engine.stop_source("P01")
        new_run = engine.start_source("P01")
        engine.start_source("P02")
        release.set()
        qtbot.waitUntil(lambda: {r.source_id for r in results} == {"P01", "P02"}, timeout=4000)
        assert all(r.run_id != old_run for r in results)
        assert any(r.run_id == new_run for r in results)
        assert len(creations) == 1
        assert creations[0] != engine.thread()
        assert all(r.queue_wait_ms >= 0 and r.inference_ms >= 0 for r in results)
    finally:
        release.set()
        shutdown(engine, qtbot)


def test_predictor_exception_has_no_levels(qtbot, config):
    class Broken:
        def predict(self, sequence):
            raise ValueError("Deliberate test error")

    engine = EngineController(config, Broken, demo=True)
    results = []
    engine.result_ready.connect(results.append)
    try:
        engine.add_source(SourceConfig("P01", "Test", "demo"))
        engine.start_source("P01")
        qtbot.waitUntil(lambda: bool(results), timeout=3000)
        assert results[0].status == Status.ERROR
        assert results[0].levels is None
        engine.remove_source("P01")
        assert "P01" not in engine.gate.runs
        assert engine.take_latest_preview("P01") is None
    finally:
        shutdown(engine, qtbot)


def test_p2_demo_exits_without_active_workers():
    result = subprocess.run([sys.executable, "-m", "audience_analysis.examples.p2_engine_demo"], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert "P01" in result.stdout and "P02" in result.stdout
    assert "QThread: Destroyed" not in result.stderr
