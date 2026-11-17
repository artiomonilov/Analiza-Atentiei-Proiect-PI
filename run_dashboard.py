"""Dashboard experimental desktop, funcționează complet local."""
import argparse
from pathlib import Path
import sys


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"): stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Dashboard local pentru CSV, adnotare și validare")
    parser.add_argument("--measurements", type=Path)
    parser.add_argument("--session-id", default="V01")
    parser.add_argument("--session-root", type=Path, default=Path("data/dashboard_sessions"))
    args = parser.parse_args(argv)
    from PySide6.QtWidgets import QApplication
    from audience_analysis.ui.experimental_dashboard import ExperimentalDashboard
    from audience_analysis.dashboard_data import DashboardSession
    app = QApplication.instance() or QApplication(sys.argv[:1])
    window = ExperimentalDashboard(args.session_root)
    if args.measurements:
        try: window.add_session(DashboardSession.from_csv(args.measurements, args.session_id))
        except (OSError, ValueError) as error: parser.exit(1, f"Eroare: {error}\n")
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
