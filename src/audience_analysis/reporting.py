import csv
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from .legacy_contracts import LABELS, Status


class SessionLog:
    def __init__(self, title, sources, config, model_version=None):
        self.metadata = {
            "schema_version": 1, "session_id": str(uuid.uuid4()), "title": title,
            "started_at": datetime.now(timezone.utc).isoformat(), "model_version": model_version,
            "pipeline": config.to_dict(), "sources": [s.public_dict() for s in sources],
            "interpretation": "Etichete experimentale; nu măsurători ale atenției sau evaluări ale studenților.",
        }
        self.records = []
        self.latest = {}
        self.generations = {}

    def invalidate(self, source_id, generation):
        self.generations[source_id] = generation
        self.latest.pop(source_id, None)

    def append(self, result):
        expected = self.generations.get(result.source_id, result.generation)
        if result.generation != expected:
            return False
        previous = self.latest.get(result.source_id)
        if previous and result.end < previous.end:
            return False
        result.received_at = datetime.now(timezone.utc).isoformat()
        self.records.append(result)
        self.latest[result.source_id] = result
        return True

    def finish(self):
        self.metadata["ended_at"] = datetime.now(timezone.utc).isoformat()

    def export(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".csv":
            columns = ["session_id", "source_id", "participant_id", "generation", "start", "end", "status", "label", "label_text", "scores", "model_version", "inference_ms", "received_at"]
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns)
                writer.writeheader()
                for record in self.records:
                    row = asdict(record)
                    row["session_id"] = self.metadata["session_id"]
                    row["label_text"] = LABELS[record.label] if record.label is not None else ""
                    row["scores"] = json.dumps(record.scores) if record.scores is not None else ""
                    writer.writerow(row)
            path.with_suffix(".metadata.json").write_text(json.dumps(self.metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            path.write_text(json.dumps({"metadata": self.metadata, "records": [asdict(r) for r in self.records]}, ensure_ascii=False, indent=2), encoding="utf-8")

