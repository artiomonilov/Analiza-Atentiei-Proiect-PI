import argparse
from pathlib import Path
import sys


PURPLE = "\033[95m"
RESET = "\033[0m"


def _console(text: str = "") -> None:
    """Afișează mov în terminal interactiv, dar păstrează text curat în loguri."""
    if sys.stdout.isatty():
        print(f"{PURPLE}{text}{RESET}")
    else:
        print(text)


def _print_result(result) -> None:
    summary = result.summary()
    _console(f"\nANALIZA {summary['kind'].upper()}")
    _console(f"- Fișier: {result.source}")
    _console(f"- Durată: {summary['duration_s'] if summary['duration_s'] is not None else 'necunoscută'}")
    _console(f"- FPS original: {summary['fps'] if summary['fps'] is not None else 'necunoscut'}")
    _console(f"- Cadre eșantionate: {summary['sampled_frames']}")
    _console(f"- Fețe detectate: {summary['faces_detected']} ({summary['face_coverage_pct'] or 0:.1f}%)")
    _console("\nATENȚIE VIZUALĂ")
    coverage, toward = summary['attention_coverage_pct'], summary['toward_screen_pct_valid']
    _console(f"- Acoperire estimator: {coverage:.1f}%" if coverage is not None else "- Acoperire estimator: indisponibilă")
    _console(f"- Spre ecran (numai estimări valide): {toward:.1f}%" if toward is not None else "- Spre ecran: unknown (calibrare/estimator indisponibil)")
    _console(f"- Cadre unknown: {summary['unknown_attention_frames']}")
    _console("\nEXPRESII FACIALE")
    if summary['emotion_frequency']:
        for label, count in summary['emotion_frequency'].items():
            _console(f"- {label}: {count / summary['emotion_frames']:.1%} ({count})")
    else:
        _console("- Indisponibile: nu a fost detectată o față validă sau modelul a eșuat.")
    _console("\nANGAJAMENT")
    _console(f"- Model disponibil: {'da' if summary['engagement']['available'] else 'nu'}")
    _console(f"- {summary['engagement']['reason']}")
    _console("\nPERFORMANȚĂ")
    _console(f"- Durata analizei: {summary['processing_seconds']:.2f} s")
    _console(f"- Timp mediu inferență: {summary['mean_inference_ms']:.2f} ms" if summary['mean_inference_ms'] is not None else "- Timp mediu inferență: indisponibil")
    _console(f"- Erori: {summary['errors']}")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Pipeline CLI local pentru analiză video experimentală")
    parser.add_argument("command", nargs="?", choices=("image", "video"), help="tipul sursei analizate")
    parser.add_argument("--input", type=Path, help="imaginea sau videoclipul local")
    parser.add_argument("--output-dir", type=Path, help="director pentru rapoarte")
    parser.add_argument("--sample-interval", type=float, default=1.0, help="video: secunde între cadre (implicit 1)")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--allow-model-download", action="store_true", help="permite explicit descărcarea reviziei fixate a modelului de expresii")
    parser.add_argument("--face-landmarker-model", type=Path, help="cale locală la fișierul MediaPipe .task")
    parser.add_argument("--calibrated", action="store_true", help="opțiune istorică; pentru calibrare neutră folosește scriptul foto --neutral-image")
    parser.add_argument("--config", type=Path, help="configurație pentru demo-ul istoric")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--demo", action="store_true", help="UI + motor P2 + FakePredictor (istoric)")
    modes.add_argument("--ui-demo", action="store_true", help="UI P3 + scenariu DemoEngine (istoric)")
    modes.add_argument("--terminal", type=Path, metavar="FIȘIER", help="compatibilitate: citire/progres simplu")
    parser.add_argument("--no-model", action="store_true", help="compatibilitate --terminal: nu încarcă modelul")
    args = parser.parse_args()
    if args.command:
        if not args.input:
            parser.error("--input este obligatoriu pentru image/video")
        if not args.input.is_file():
            parser.error(f"Fișierul nu există: {args.input}")
        from .pipeline import AnalysisPipeline, analyse_image, analyse_video, export_reports
        pipeline = AnalysisPipeline(device=args.device, face_landmarker_model=args.face_landmarker_model, calibrated=args.calibrated,
                                    allow_model_download=args.allow_model_download)
        try:
            def progress(percent, timestamp): _console(f"Progres: {percent:3d}% — {timestamp:.2f}s")
            result = analyse_image(args.input, pipeline) if args.command == "image" else analyse_video(args.input, pipeline, args.sample_interval, progress,
                report_dir=args.output_dir, retain_frames=False)
            _print_result(result)
            if args.output_dir:
                export_reports(result, args.output_dir)
                _console(f"\nRapoarte salvate în: {args.output_dir}")
            return 130 if result.interrupted else 0
        except KeyboardInterrupt:
            print("\nProcesare întreruptă controlat; resursele video au fost eliberate.", file=sys.stderr)
            return 130
        except (OSError, RuntimeError, ValueError) as error:
            parser.error(str(error))
        finally:
            pipeline.close()
    if args.terminal:
        from .terminal import terminal_main
        try:
            return terminal_main(args.terminal, with_model=not args.no_model)
        except (OSError, RuntimeError, ValueError) as error:
            parser.error(str(error))
    if not args.demo and not args.ui_demo:
        parser.print_help()
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
