"""Comparație explicită între evenimente automate CSV și marcaje manuale CSV."""
import argparse
import csv
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compară clipirile automate cu o referință manuală")
    parser.add_argument("--detected", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--tolerance-ms", type=int, default=100)
    args = parser.parse_args(argv)
    from audience_analysis.temporal_analysis import BlinkEvent, compare_blinks
    def read(path):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = csv.DictReader(handle)
            if not rows.fieldnames or not {"eye", "start_ms", "end_ms"} <= set(rows.fieldnames):
                raise ValueError("CSV-ul necesită eye,start_ms,end_ms.")
            events = []
            for row in rows:
                start, end = int(row["start_ms"]), int(row["end_ms"])
                events.append(BlinkEvent(row["eye"], start, end, end - start))
            return events
    try:
        print(json.dumps(compare_blinks(read(args.detected), read(args.reference), tolerance_ms=args.tolerance_ms), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as error:
        parser.exit(1, f"Eroare: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
