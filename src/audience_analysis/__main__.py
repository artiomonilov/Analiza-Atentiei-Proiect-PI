import argparse
from pathlib import Path
import sys


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Mini-template: SIMULARE, fără AI real")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--demo", action="store_true", help="UI + motor P2 + FakePredictor")
    modes.add_argument("--ui-demo", action="store_true", help="UI P3 + scenariu DemoEngine")
    parser.add_argument("--config", type=Path, help="Configurație demo JSON; implicit SequenceConfig")
    args = parser.parse_args()
    if not args.demo and not args.ui_demo:
        parser.print_help()
        print("\nModelul real nu este configurat. Alege explicit un mod de SIMULARE.")
        return 0
    from PySide6.QtWidgets import QApplication
    from .ui.main_window import MainWindow
    app = QApplication(sys.argv[:1])
    if args.ui_demo:
        from .ui.demo_engine import DemoEngine
        engine = DemoEngine()
    else:
        from .ai.fake_predictor import FakePredictor
        from .config import SequenceConfig, load_demo_config
        from .engine.controller import EngineController
        config = load_demo_config(args.config) if args.config else SequenceConfig()
        engine = EngineController(config, lambda: FakePredictor(config), demo=True)
    window = MainWindow(engine)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
