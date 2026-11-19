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
    parser.add_argument("--calibration", type=Path, help="profil JSON salvat de calibrate_session.py")
    parser.add_argument("--frozen-plan", type=Path, help="configurația experimentală înghețată după D01")
    parser.add_argument("--session-id", help="ID anonim, obligatoriu pentru pachetul înghețat")
    parser.add_argument("--role", choices=("calibration", "development", "validation"), default="validation")
    args = parser.parse_args(argv)
    from audience_analysis.video_processor import VideoProcessor
    source = int(args.source) if args.source.isdecimal() else Path(args.source)
    try:
        from audience_analysis.temporal_analysis import TemporalConfig
        config = TemporalConfig.from_dict(json.loads(args.temporal_config.read_text(encoding="utf-8"))) if args.temporal_config else TemporalConfig()
        estimators = {}
        plan = None
        if args.session_id:
            from audience_analysis.experimental import validate_role_id
            validate_role_id(args.session_id, args.role)
            if not args.output_csv: raise ValueError("O sesiune identificată necesită --output-csv pentru proveniență.")
            if args.role == "validation" and not args.frozen_plan: raise ValueError("V01 necesită --frozen-plan; ajustează parametrii numai pe D01.")
            receipt_path = Path(str(args.output_csv) + ".experiment.json")
            if receipt_path.exists(): raise ValueError("Fișierul de proveniență există deja.")
        if args.frozen_plan:
            from audience_analysis.experimental import FrozenExperiment
            if not args.session_id or not args.output_csv:
                raise ValueError("Rularea fixată necesită --session-id și --output-csv.")
            if args.calibration or args.neutral_image or args.temporal_config:
                raise ValueError("Pachetul înghețat nu permite suprascrierea calibrării sau pragurilor.")
            plan = FrozenExperiment.load(args.frozen_plan)
            if plan.payload.get("pipeline_parameters") is not None:
                raise ValueError("Planul P2 necesită audience-p2-video, nu procesorul video separat")
            plan.validate_target(args.session_id, args.role); plan.validate_runtime(args.model)
            plan.validate_source(source, args.role)
            manager, config = plan.estimators()
            estimators = {"pose_estimator": manager.pose, "eye_estimator": manager.eyes}
            receipt_path = Path(str(args.output_csv) + ".experiment.json")
            if receipt_path.exists(): raise ValueError("Fișierul de proveniență există deja.")
        if args.calibration:
            if args.neutral_image:
                raise ValueError("Alege profilul --calibration sau --neutral-image, nu ambele.")
            from audience_analysis.calibration import CalibrationManager
            manager = CalibrationManager.load(args.calibration)
            config = manager.temporal_config(config)
            estimators = {"pose_estimator": manager.pose, "eye_estimator": manager.eyes}
        report = VideoProcessor(args.model, temporal_config=config, **estimators).run(
            source, neutral_image=args.neutral_image, output_csv=args.output_csv,
            display=not args.no_display, show_landmarks=args.show_landmarks, show_temporal=args.show_temporal,
            output_temporal_csv=args.output_temporal_csv, output_blinks_csv=args.output_blinks_csv)
        if plan:
            from audience_analysis.experimental import make_receipt
            receipt = make_receipt(plan, args.session_id, args.role, args.output_csv, events=args.output_blinks_csv, source=source)
            with receipt_path.open("x", encoding="utf-8") as handle: json.dump(receipt, handle, ensure_ascii=False, indent=2)
        elif args.session_id:
            from dataclasses import asdict
            from audience_analysis.experimental import code_version, file_digest, measurement_digest, event_digest, environment_versions
            from audience_analysis.dashboard_data import load_rows
            from audience_analysis.validation import read_blinks
            receipt = {"session_id": args.session_id, "role": args.role, "config_version": "unfrozen",
                       "code": code_version(), "environment": environment_versions(), "temporal": asdict(config),
                       "model_sha256": file_digest(args.model), "measurement_content_sha256": measurement_digest(load_rows(args.output_csv)),
                       "source_sha256": file_digest(source) if not isinstance(source, int) else None,
                       "calibration": manager.to_dict() if args.calibration else None,
                       "event_content_sha256": event_digest(read_blinks(args.output_blinks_csv)) if args.output_blinks_csv else None}
            with receipt_path.open("x", encoding="utf-8") as handle: json.dump(receipt, handle, ensure_ascii=False, indent=2)
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
