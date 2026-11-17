"""Geometrie facială sincronă: fișier local sau webcam."""
import argparse
import json
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="MediaPipe VIDEO: head pose, EAR și poziția irisurilor")
    parser.add_argument("--source", required=True, help="cale video sau index webcam (exemplu: 0)")
    parser.add_argument("--model", type=Path, default=Path("models/face_landmarker.task"))
    parser.add_argument("--neutral-image", type=Path)
    parser.add_argument("--output-csv", type=Path, help="export explicit; fișierul nu trebuie să existe deja")
    parser.add_argument("--show-landmarks", action="store_true")
    parser.add_argument("--no-display", action="store_true", help="numai fișiere video")
    parser.add_argument("--temporal-config", type=Path, help="configurație JSON pentru ferestre și praguri individuale EAR")
    parser.add_argument("--output-temporal-csv", type=Path)
    parser.add_argument("--output-blinks-csv", type=Path)
    parser.add_argument("--show-temporal", action="store_true", help="statistici temporale în overlay")
    args = parser.parse_args(argv)
    from audience_analysis.video_processor import VideoProcessor
    source = int(args.source) if args.source.isdecimal() else Path(args.source)
    try:
        from audience_analysis.temporal_analysis import TemporalConfig
        config = TemporalConfig.from_dict(json.loads(args.temporal_config.read_text(encoding="utf-8"))) if args.temporal_config else TemporalConfig()
        report = VideoProcessor(args.model, temporal_config=config).run(
            source, neutral_image=args.neutral_image, output_csv=args.output_csv,
            display=not args.no_display, show_landmarks=args.show_landmarks, show_temporal=args.show_temporal,
            output_temporal_csv=args.output_temporal_csv, output_blinks_csv=args.output_blinks_csv)
        print(f"Cadre: {report.frames_processed}; cu față: {report.faces_detected}; erori: {report.errors}")
        print(f"FPS sursă: {report.source_fps}; FPS procesare: {report.processing_fps:.2f}; durată: {report.elapsed_s:.3f}s")
        print(f"Oprire: {report.stop_reason}")
        if args.output_csv:
            print(f"CSV: {args.output_csv.resolve()}")
        if report.temporal:
            for window in report.temporal.windows:
                left = window['left_blink']['count']
                right = window['right_blink']['count']
                print(f"Fereastră {window['window_s']}s: {window['sample_count']} cadre; durată observată {window['observed_span_ms']}ms; "
                      f"clipiri L/R: {left if left is not None else 'indisponibil'}/{right if right is not None else 'indisponibil'}")
        for path in (args.output_temporal_csv, args.output_blinks_csv):
            if path:
                print(f"CSV temporal: {path.resolve()}")
        return 130 if report.stop_reason == "interrupted" else 0
    except KeyboardInterrupt:
        parser.exit(130, "Procesare întreruptă.\n")
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"Eroare: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
