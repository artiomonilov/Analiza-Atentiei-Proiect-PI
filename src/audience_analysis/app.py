import argparse
import multiprocessing
import os
from pathlib import Path
import sys


def main():
    multiprocessing.freeze_support()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Laborator desktop de analiză video")
    parser.add_argument("--smoke-test", action="store_true", help="Pornește interfața fără surse și o închide după o secundă")
    parser.add_argument("--screenshot", help="Salvează o captură a interfeței goale în fișierul PNG indicat")
    args = parser.parse_args()
    from .qt import QtCore, QtGui, QtWidgets
    from .legacy_ui import MainWindow
    app = QtWidgets.QApplication(sys.argv[:1])
    # Windows' offscreen Qt platform has no system font discovery.
    if sys.platform == "win32" and not QtGui.QFontDatabase().families():
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "segoeui.ttf"
        if font.is_file():
            QtGui.QFontDatabase.addApplicationFont(str(font))
    window = MainWindow()
    window.show()
    if args.screenshot:
        QtCore.QTimer.singleShot(500, lambda: window.grab().save(args.screenshot))
    if args.smoke_test:
        QtCore.QTimer.singleShot(1000, window.close)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

