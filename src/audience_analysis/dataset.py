import csv
import hashlib
from pathlib import Path

import cv2

from .preprocessing import FacePreprocessor, SequenceBuilder
from .legacy_contracts import Status


def read_manifest(path):
    path = Path(path).resolve()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"clip_id", "participant_id", "path", "split", "engagement"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Manifestul necesită: " + ", ".join(sorted(required)))
        records = []
        clips, paths, subjects = set(), set(), {}
        for line, row in enumerate(reader, 2):
            if not row["clip_id"].strip() or not row["participant_id"].strip():
                raise ValueError(f"Identificator lipsă la linia {line}")
            if row["split"] not in {"train", "validation", "test"}:
                raise ValueError(f"Split invalid la linia {line}")
            try:
                value = int(row["engagement"])
            except ValueError as error:
                raise ValueError(f"Etichetă lipsă/invalidă la linia {line}") from error
            if value not in range(4):
                raise ValueError(f"Etichetă în afara intervalului 0–3 la linia {line}")
            media = (path.parent / row["path"]).resolve()
            if row["clip_id"] in clips or media in paths:
                raise ValueError(f"Clip sau cale duplicată la linia {line}")
            if row["participant_id"] in subjects and subjects[row["participant_id"]] != row["split"]:
                raise ValueError(f"Participant prezent în splituri diferite la linia {line}; clarifică protocolul înaintea antrenării")
            clips.add(row["clip_id"])
            paths.add(media)
            subjects[row["participant_id"]] = row["split"]
            records.append({"clip_id": row["clip_id"], "participant_id": row["participant_id"], "path": str(media), "split": row["split"], "engagement": value})
    if not records:
        raise ValueError("Manifest gol")
    return records


def audit_manifest(path):
    rows = read_manifest(path)
    report = {"total": len(rows), "splits": {}, "missing_files": [], "duplicate_content": []}
    hashes = {}
    for row in rows:
        split = report["splits"].setdefault(row["split"], {"clips": 0, "classes": [0]*4, "subjects": set()})
        split["clips"] += 1
        split["classes"][row["engagement"]] += 1
        split["subjects"].add(row["participant_id"])
        path = Path(row["path"])
        if not path.is_file():
            report["missing_files"].append(row["clip_id"])
            continue
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if digest in hashes:
            report["duplicate_content"].append([hashes[digest], row["clip_id"]])
        hashes[digest] = row["clip_id"]
    for split in report["splits"].values():
        split["subjects"] = len(split["subjects"])
    return report


def extract_clip(row, config):
    """First valid nominal window, one example per clip; report all rejections."""
    capture = cv2.VideoCapture(row["path"])
    builder = SequenceBuilder(config, row["clip_id"], row["participant_id"])
    preprocessor = FacePreprocessor(config)
    reasons = {}
    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not capture.isOpened() or not (0 < fps <= 1000):
            return None, {"UNREADABLE": 1}
        index, last_sample, last_media = 0, -1.0, -1.0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            reported = capture.get(cv2.CAP_PROP_POS_MSEC)/1000
            timestamp = reported if reported > last_media else index/fps
            last_media = timestamp
            index += 1
            if timestamp - last_sample < 0.125:
                continue
            last_sample = timestamp
            status, rgb, _ = preprocessor.process(frame)
            if status != Status.READY:
                reasons[str(status)] = reasons.get(str(status), 0) + 1
            batch = builder.add(timestamp, rgb, status)
            if batch is not None:
                return batch, reasons
        reasons["INSUFFICIENT_DATA"] = 1
        return None, reasons
    finally:
        capture.release()

