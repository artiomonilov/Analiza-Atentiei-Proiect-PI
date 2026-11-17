"""Comenzi P1 independente de motor, captură și UI."""
import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description="P1: date, pachet local și comparații fără antrenare implicită")
    commands = parser.add_subparsers(dest="command", required=True)
    data = commands.add_parser("check-data"); data.add_argument("manifest", type=Path)
    inspect = commands.add_parser("inspect-model"); inspect.add_argument("model", type=Path)
    predict = commands.add_parser("predict-cache"); predict.add_argument("model", type=Path); predict.add_argument("sequence", type=Path)
    compare = commands.add_parser("compare"); compare.add_argument("input", type=Path); compare.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    from .predictor import ModelUnavailableError, RealPredictor
    try:
        if args.command == "check-data":
            from .data import load_training_manifest
            rows = load_training_manifest(args.manifest)
            result = {"clips": len(rows), "splits": {s: sum(r["split"] == s for r in rows) for s in ("train", "validation", "test")},
                      "real_world_validation": "NOT VERIFIED"}
        elif args.command in {"inspect-model", "predict-cache"}:
            predictor = RealPredictor(args.model)
            result = {"status": "OK", "model_version": predictor.model_version, "dimensions": predictor.dimensions}
            if args.command == "predict-cache":
                from .data import load_prepared_sequence
                result["levels"] = predictor.predict(load_prepared_sequence(args.sequence, predictor.config)).levels
                result["is_demo"] = False
        else:
            from .evaluation import compare_models
            inputs = json.loads(args.input.read_text(encoding="utf-8"))
            result = compare_models(**inputs)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as stream: json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except ModelUnavailableError:
        print(json.dumps({"status": "MODEL_UNAVAILABLE", "levels": None}))
        return 4
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Date/configurație incompatibile: {type(error).__name__}\n")


if __name__ == "__main__":
    raise SystemExit(main())
