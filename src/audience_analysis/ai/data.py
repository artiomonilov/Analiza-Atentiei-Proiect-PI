"""Date P1: metadate și cache-uri; nu capturează sau decodează surse video."""
import csv
import hashlib
from pathlib import Path

import numpy as np

from ..config import SequenceConfig, validate_sequence
from ..contracts import PreparedSequence
from ..video.preprocessing import prepare_bgr

DIMENSIONS = ("engagement", "boredom", "confusion", "frustration")


def validate_model_sequence(sequence, config):
    validate_sequence(sequence, config)
    span = sequence.sample_times_s[-1] - sequence.sample_times_s[0]
    if abs(span - config.window_seconds) > 2 * config.sample_tolerance_s + 1e-8:
        raise ValueError("Durata secvenței diferă de configurația modelului.")


def load_training_manifest(path: str | Path, *, verify_files=True, check_content=True) -> list[dict]:
    path = Path(path).resolve()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"clip_id", "participant_id", "path", "split", "engagement"} <= set(reader.fieldnames or []):
            raise ValueError("Manifest: clip_id, participant_id, path, split, engagement obligatorii.")
        result, clips, paths, participants, contents = [], set(), set(), {}, set()
        for row in reader:
            if None in row or any(row.get(k) is None for k in ("clip_id", "participant_id", "path", "split", "engagement")):
                raise ValueError("Rând CSV incomplet sau cu celule suplimentare.")
            clip, person = row["clip_id"].strip(), row["participant_id"].strip()
            split = row["split"]
            if not clip or not person or not row["path"].strip() or split not in {"train", "validation", "test"}:
                raise ValueError("ID, cale sau split invalid în manifest.")
            media = (path.parent / row["path"]).resolve()
            if clip in clips or media in paths: raise ValueError("Clip/cale duplicată.")
            if person in participants and participants[person] != split: raise ValueError("Participant prezent în splituri diferite.")
            labels = {}
            for dimension in DIMENSIONS:
                value = row.get(dimension, "")
                if value in (None, "") and dimension != "engagement": continue
                if value not in {"0", "1", "2", "3"}: raise ValueError(f"Etichetă invalidă: {dimension}")
                labels[dimension] = int(value)
            if verify_files and not media.is_file(): raise FileNotFoundError(f"Clip lipsă: {clip}")
            if check_content and media.is_file():
                with media.open("rb") as handle: fingerprint = hashlib.file_digest(handle, "sha256").hexdigest()
                if fingerprint in contents: raise ValueError("Conținut duplicat în manifest.")
                contents.add(fingerprint)
            clips.add(clip); paths.add(media); participants[person] = split
            result.append({"clip_id": clip, "participant_id": person, "path": media, "split": split, "labels": labels})
    if not result: raise ValueError("Manifest gol.")
    return result


def prepare_sequence(frames_bgr, sample_times_s, config: SequenceConfig) -> PreparedSequence:
    """Reutilizează exact preprocesarea P2, fără normalizare duplicată în P1."""
    if len(frames_bgr) != config.frames: raise ValueError("Număr de cadre incompatibil.")
    sequence = PreparedSequence(np.stack([prepare_bgr(frame, config) for frame in frames_bgr]),
                                tuple(sample_times_s), config.preprocessing_id)
    validate_model_sequence(sequence, config)
    return sequence


def load_prepared_sequence(path, config: SequenceConfig) -> PreparedSequence:
    with np.load(path, allow_pickle=False) as cache:
        if not {"frames", "sample_times_s", "preprocessing_id"} <= set(cache.files):
            raise ValueError("Cache fără cadre/timp/preprocessing_id.")
        sequence = PreparedSequence(cache["frames"], tuple(cache["sample_times_s"].tolist()), str(cache["preprocessing_id"].item()))
    validate_model_sequence(sequence, config)
    return sequence


def iter_samples(records, config, *, split, dimension="engagement"):
    if split not in {"train", "validation", "test"} or dimension not in DIMENSIONS: raise ValueError("Split/dimensiune invalidă.")
    for record in records:
        if record["split"] == split and dimension in record["labels"]:
            yield record["clip_id"], load_prepared_sequence(record["path"], config), record["labels"][dimension]
