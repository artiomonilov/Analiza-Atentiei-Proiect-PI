import csv
from dataclasses import asdict
from pathlib import Path

from ..contracts import PredictionResult


class ResultHistory:
    def __init__(self):
        self.records: list[PredictionResult] = []
        self.keys: set[tuple[str, str, int]] = set()

    def add(self, result: PredictionResult) -> bool:
        key = (result.source_id, result.run_id, result.request_id)
        if key in self.keys:
            return False
        self.keys.add(key)
        self.records.append(result)
        return True

    def export_csv(self, path: str | Path) -> None:
        dimensions = sorted({name for row in self.records for name in (row.levels or {})})
        columns = ["source_id", "run_id", "request_id", "window_start_s", "window_end_s", "status",
                   "model_version", "is_demo", "queue_wait_ms", "inference_ms", "error_message"]
        with Path(path).open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns+dimensions)
            writer.writeheader()
            for record in self.records:
                row = asdict(record)
                row.pop("levels")
                row.update({name: (record.levels or {}).get(name, "") for name in dimensions})
                writer.writerow(row)
