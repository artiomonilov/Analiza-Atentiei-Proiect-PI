"""Organizare C/D/V, înghețare și comparație fără copierea videoclipurilor."""
import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"): stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Gestionare reproductibilă C01 → D01 → V01")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--measurements", type=Path, required=True)
    create.add_argument("--id", required=True)
    create.add_argument("--role", choices=("calibration", "development", "validation"), required=True)
    create.add_argument("--config", type=Path)
    create.add_argument("--video", type=Path)
    create.add_argument("--frozen-plan", type=Path)
    create.add_argument("--processing-metadata", type=Path)
    create.add_argument("--automatic", type=Path)
    create.add_argument("--include-external-paths", action="store_true", help="opt-in: păstrează căile locale CSV/video în manifest")
    create.add_argument("--root", type=Path, default=Path("data/dashboard_sessions"))
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--calibration", type=Path, required=True)
    freeze.add_argument("--development-session", type=Path, action="append", required=True)
    freeze.add_argument("--temporal-config", type=Path)
    freeze.add_argument("--validation-config", type=Path)
    freeze.add_argument("--model", type=Path, default=Path("models/face_landmarker.task"))
    freeze.add_argument("--config-version", default="1")
    freeze.add_argument("--output", type=Path, required=True)
    compare = commands.add_parser("compare")
    compare.add_argument("--session", type=Path, action="append", required=True)
    compare.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    from audience_analysis.dashboard_data import DashboardSession, SessionStore
    from audience_analysis.experimental import FrozenExperiment, code_version, compare_sessions, validate_role_id, check_receipt
    from audience_analysis.validation import read_blinks
    try:
        if args.command == "create":
            validate_role_id(args.id, args.role)
            session = DashboardSession.from_csv(args.measurements, args.id)
            session.role, session.video_path = args.role, args.video.resolve() if args.video else None
            if args.config: session.config = json.loads(args.config.read_text(encoding="utf-8"))
            if args.automatic: session.automatic = read_blinks(args.automatic)
            session.reproducibility = session.reproducibility or {"code": code_version(), "config_version": "unfrozen"}
            if session.reproducibility.get("session_id") and (session.reproducibility["session_id"] != args.id or session.reproducibility.get("role") != args.role):
                raise ValueError("ID/rol diferit de proveniența CSV.")
            if args.frozen_plan:
                plan = FrozenExperiment.load(args.frozen_plan)
                receipt = json.loads((args.processing_metadata or Path(str(args.measurements) + ".experiment.json")).read_text(encoding="utf-8"))
                check_receipt(plan, receipt, args.measurements, session_id=args.id, events=args.automatic)
                if receipt["role"] != args.role: raise ValueError("Rolul diferă de proveniența procesării.")
                session.frozen_plan, session.reproducibility = plan.document, receipt
                session.config = plan.validation_config({**session.config, "session_id": args.id})
            print(SessionStore(args.root).save(session, include_external_paths=args.include_external_paths))
        elif args.command == "freeze":
            from audience_analysis.temporal_analysis import TemporalConfig
            sessions = [SessionStore(path.parent).load(path) for path in args.development_session]
            temporal = TemporalConfig.from_dict(json.loads(args.temporal_config.read_text(encoding="utf-8"))) if args.temporal_config else TemporalConfig()
            validation = json.loads(args.validation_config.read_text(encoding="utf-8")) if args.validation_config else {}
            plan = FrozenExperiment.create(args.calibration, sessions, args.model, temporal=temporal, validation=validation, config_version=args.config_version)
            plan.save(args.output)
            print(f"Configurație înghețată: {args.output} · SHA256 {plan.sha256}")
        else:
            sessions = [SessionStore(path.parent).load(path) for path in args.session]
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as handle: json.dump(compare_sessions(sessions), handle, ensure_ascii=False, indent=2, allow_nan=False)
            print(args.output)
        return 0
    except (OSError, TypeError, KeyError, ValueError) as error:
        parser.exit(1, f"Eroare: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
