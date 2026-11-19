"""P2 capturează video; geometria Artiom și exportul sunt executate în SourceWorker."""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import signal
import sys


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Motor P2 + MediaPipe/head/eye/temporal + export pentru dashboard")
    parser.add_argument("--source", required=True, help="fișier, index cameră sau flux autorizat")
    parser.add_argument("--model", type=Path, default=Path("models/face_landmarker.task"))
    parser.add_argument("--output-dir", type=Path, required=True, help="rulările sunt în source_id/run_id")
    parser.add_argument("--source-id", default="S01")
    parser.add_argument("--session-id", default="D01")
    parser.add_argument("--role", choices=("calibration", "development", "validation"), default="development")
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--temporal-config", type=Path)
    parser.add_argument("--frozen-plan", type=Path)
    parser.add_argument("--track-id", type=int, help="selectare explicită; altfel necesită o singură față YuNet")
    parser.add_argument("--engagement-model", type=Path, help="pachet P1 separat, opțional; fără Fake implicit")
    parser.add_argument("--fast", action="store_true", help="fișier fără așteptarea ritmului de redare")
    parser.add_argument("--stop-after", type=float, help="oprește controlat după N secunde de procesare")
    parser.add_argument("--synthetic-input", action="store_true", help="etichetează materialul tehnic sintetic")
    args = parser.parse_args(argv)
    try:
        from PySide6.QtCore import QCoreApplication, QTimer
        from ..ai.predictor import ModelUnavailableError, RealPredictor
        from ..ai.package import validate_manifest
        from ..config import SequenceConfig
        from ..contracts import SourceConfig, Status
        from ..experimental import FrozenExperiment
        from ..temporal_analysis import TemporalConfig
        from ..video.sources import resolve_source
        from .controller import EngineController
        from .facial import FacialAnalysisSession, GeometryConfig
        if args.stop_after is not None and (not math.isfinite(args.stop_after) or args.stop_after <= 0):
            raise ValueError("--stop-after trebuie să fie pozitiv și finit")
        if not args.model.is_file():
            raise ValueError("Este necesar modelul MediaPipe local --model")
        source = SourceConfig(source_id=args.source_id, display_name=args.source_id, kind="file", location=args.source)
        if resolve_source(source)[0] == "file" and not Path(args.source).is_file():
            raise ValueError("Fișierul sursă nu există")
        if args.frozen_plan and (args.calibration or args.temporal_config):
            raise ValueError("Nu suprascrie calibrarea/parametrii unui plan înghețat")
        profile = json.loads(args.calibration.read_text(encoding="utf-8")) if args.calibration else None
        temporal = TemporalConfig.from_dict(json.loads(args.temporal_config.read_text(encoding="utf-8"))) if args.temporal_config else TemporalConfig()
        plan = FrozenExperiment.load(args.frozen_plan).document if args.frozen_plan else None
        geometry = GeometryConfig(args.model, args.session_id, args.role, profile, temporal,
                                  args.output_dir, args.track_id, plan, "synthetic" if args.synthetic_input else "unverified")
        config = SequenceConfig()
        engagement_path = args.engagement_model
        if engagement_path is not None:
            try:
                config = validate_manifest(json.loads((engagement_path / "manifest.json").read_text(encoding="utf-8")))
                from ..video.sequences import SequenceBuilder
                SequenceBuilder(config)
            except (OSError, ValueError, TypeError, KeyError):
                engagement_path = None
                config = SequenceConfig()
        def predictor_factory():
            if engagement_path is None:
                raise ModelUnavailableError("Pachet P1 indisponibil")
            return RealPredictor(engagement_path, config)
        app = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])
        engine = EngineController(config, predictor_factory, demo=False, realtime=not args.fast,
                                  geometry_factory=lambda current, run: FacialAnalysisSession(current, run, geometry))
        result_code = [0]
        def status(event):
            print(f"{event.source_id} {event.status}: {event.message}", flush=True)
            if event.status in {Status.END_OF_SOURCE, Status.ERROR}:
                if event.status == Status.ERROR:
                    result_code[0] = 1
                engine.shutdown()
        engine.status_changed.connect(status)
        engine.model_status_changed.connect(lambda value: print("P1: " + value["status"], flush=True))
        if args.engagement_model is not None:
            engine.result_ready.connect(lambda value: print("P1 result: " + json.dumps(asdict(value), ensure_ascii=False), flush=True))
        def completed(outcome):
            if outcome["error"]:
                print(outcome["error"], file=sys.stderr, flush=True)
                if result_code[0] != 130:
                    result_code[0] = 1
        engine.run_finished.connect(completed)
        engine.geometry_ready.connect(lambda result: print(
            f"Cadru {result.frame_index} @ {result.timestamp_ms} ms; track={result.track_id}; "
            f"asociere={result.association_status}; head={result.measurement.head_pose_available}", flush=True))
        engine.shutdown_finished.connect(app.quit)
        heartbeat = QTimer()
        heartbeat.timeout.connect(lambda: None)
        heartbeat.start(100)
        previous_handler = signal.getsignal(signal.SIGINT)
        def interrupted(*_args):
            result_code[0] = 130
            engine.shutdown()
        signal.signal(signal.SIGINT, interrupted)
        try:
            engine.add_source(source)
            run_id = engine.start_source(source.source_id)
            if args.stop_after is not None:
                QTimer.singleShot(max(1, round(args.stop_after * 1000)), engine.shutdown)
            print("P2 geometry: " + str(args.output_dir / source.source_id / run_id), flush=True)
            app.exec()
        finally:
            signal.signal(signal.SIGINT, previous_handler)
            heartbeat.stop()
        return result_code[0]
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
        parser.exit(1, f"Eroare P2: {type(error).__name__}: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
