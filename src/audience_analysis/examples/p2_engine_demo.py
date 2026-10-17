import sys

from PySide6.QtCore import QCoreApplication, QTimer

from ..ai.fake_predictor import FakePredictor
from ..config import SequenceConfig
from ..contracts import SourceConfig
from ..engine.controller import EngineController


def main() -> int:
    app = QCoreApplication(sys.argv[:1])
    config = SequenceConfig()
    engine = EngineController(config, lambda: FakePredictor(config), demo=True)
    count = 0
    timed_out = False

    def receive(result):
        nonlocal count
        print(f"SIMULARE {result.source_id} cerere={result.request_id} run={result.run_id[:8]} levels={result.levels} wait={result.queue_wait_ms:.2f}ms infer={result.inference_ms:.2f}ms", flush=True)
        count += 1
        if count >= 4:
            engine.shutdown()

    def timeout():
        nonlocal timed_out
        timed_out = True
        engine.shutdown()

    engine.result_ready.connect(receive)
    engine.shutdown_finished.connect(app.quit)
    watchdog = QTimer()
    watchdog.setSingleShot(True)
    watchdog.timeout.connect(timeout)
    watchdog.start(10000)
    for source_id in ("P01", "P02"):
        engine.add_source(SourceConfig(source_id, source_id, "demo"))
        engine.start_source(source_id)
    app.exec()
    return 0 if engine.is_shutdown and count >= 4 and not timed_out else 1


if __name__ == "__main__":
    raise SystemExit(main())
