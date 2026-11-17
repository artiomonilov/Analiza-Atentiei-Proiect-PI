"""Evaluare offline JSON/CSV, cu referințe opționale declarate explicit."""
import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validare experimentală a măsurătorilor faciale CSV")
    parser.add_argument("--measurements", type=Path, required=True)
    parser.add_argument("--reference", type=Path, help="referințe head pose/iris/categorii CSV")
    parser.add_argument("--detected-blinks", type=Path)
    parser.add_argument("--reference-blinks", type=Path)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, help="profilul folosit; verifică separarea sesiunilor")
    parser.add_argument("--output-dir", type=Path, required=True, help="director nou")
    parser.add_argument("--plots", action="store_true")
    parser.add_argument("--frozen-plan", type=Path)
    parser.add_argument("--processing-metadata", type=Path, help="implicit: măsurători.csv.experiment.json")
    parser.add_argument("--conditions", type=Path, help="marcaje manuale face_absent/condition CSV")
    args = parser.parse_args(argv)
    from audience_analysis.validation import evaluate, read_measurements, read_blinks, save_report
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("Configurația trebuie să fie un obiect JSON.")
        if args.calibration:
            from audience_analysis.calibration import CalibrationManager
            manager = CalibrationManager.load(args.calibration)
            config["calibration_session_ids"] = sorted(set(config.get("calibration_session_ids", [])) | set(manager.session_ids))
        if args.frozen_plan:
            if args.calibration: raise ValueError("Calibrarea este deja inclusă în pachetul înghețat.")
            from audience_analysis.experimental import FrozenExperiment, check_receipt
            plan = FrozenExperiment.load(args.frozen_plan)
            receipt_path = args.processing_metadata or Path(str(args.measurements) + ".experiment.json")
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            check_receipt(plan, receipt, args.measurements, session_id=config.get("session_id"), events=args.detected_blinks)
            config = plan.validation_config(config)
            config["final_evaluation"] = receipt["role"] == "validation"
            config["processing_provenance"] = receipt
        rows = read_measurements(args.measurements)
        annotations = []
        if args.conditions:
            from audience_analysis.experimental import read_conditions
            annotations = read_conditions(args.conditions, rows)
            config["scenarios"] = [*config.get("scenarios", []), *[{"name": a["label"], "start_ms": a["start_ms"], "end_ms": a["end_ms"]} for a in annotations if a["kind"] == "condition"]]
        report = evaluate(rows, config,
                          references=read_measurements(args.reference) if args.reference else None,
                          detected_blinks=read_blinks(args.detected_blinks) if args.detected_blinks else None,
                          reference_blinks=read_blinks(args.reference_blinks) if args.reference_blinks else None)
        from audience_analysis.experimental import manual_absence_report
        report["manual_face_absence"] = manual_absence_report(rows, annotations)
        report["manual_conditions"] = annotations
        save_report(report, args.output_dir, plots=args.plots)
        print(f"Experiment: {report['experiment_id']}; măsurători: {report['evaluated_measurements']}; perechi referință: {report['reference_pairs']}")
        print(f"Raport: {args.output_dir.resolve()}")
        return 0
    except (ImportError, OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"Eroare: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
