"""Geometrie facială sincronă: fișier local sau webcam."""
import argparse
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="MediaPipe VIDEO: head pose, EAR și poziția irisurilor")
    parser.add_argument("--source", required=True, help="cale video sau index webcam (exemplu: 0)")
    parser.add_argument("--model", type=Path, default=Path("models/face_landmarker.task"))
    parser.add_argument("--neutral-image", type=Path)
    parser.add_argument("--output-csv", type=Path, help="export explicit; fișierul nu trebuie să existe deja")
    parser.add_argument("--show-landmarks", action="store_true")
    parser.add_argument("--no-display", action="store_true", help="numai fișiere video")
    args = parser.parse_args(argv)
    from audience_analysis.video_processor import VideoProcessor
    source = int(args.source) if args.source.isdecimal() else Path(args.source)
    try:
        report = VideoProcessor(args.model).run(source, neutral_image=args.neutral_image, output_csv=args.output_csv,
                                               display=not args.no_display, show_landmarks=args.show_landmarks)
        print(f"Cadre: {report.frames_processed}; cu față: {report.faces_detected}; erori: {report.errors}")
        print(f"FPS sursă: {report.source_fps}; FPS procesare: {report.processing_fps:.2f}; durată: {report.elapsed_s:.3f}s")
        print(f"Oprire: {report.stop_reason}")
        if args.output_csv:
            print(f"CSV: {args.output_csv.resolve()}")
        return 130 if report.stop_reason == "interrupted" else 0
    except KeyboardInterrupt:
        parser.exit(130, "Procesare întreruptă.\n")
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"Eroare: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
