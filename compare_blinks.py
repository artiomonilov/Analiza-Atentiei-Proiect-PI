"""Comparație explicită între evenimente automate CSV și marcaje manuale CSV."""
import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compară clipirile automate cu o referință manuală")
    parser.add_argument("--detected", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--tolerance-ms", type=int, default=100)
    args = parser.parse_args(argv)
    from audience_analysis.validation import blink_metrics, read_blinks
    try:
        print(json.dumps(blink_metrics(read_blinks(args.detected), read_blinks(args.reference), tolerance_ms=args.tolerance_ms), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as error:
        parser.exit(1, f"Eroare: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
