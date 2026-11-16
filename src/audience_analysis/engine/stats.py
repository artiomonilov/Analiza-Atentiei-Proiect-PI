
from collections import deque
from dataclasses import dataclass, field
from threading import Lock
import time

from ..contracts import PredictionResult, Status

SAMPLES = 2000  # câte valori recente se păstrează pentru p95 (memoria rămâne limitată)


@dataclass
class _Timing:
    count: int = 0
    total: float = 0.0
    maximum: float = 0.0
    recent: deque = field(default_factory=lambda: deque(maxlen=SAMPLES))

    def add(self, value: float) -> None:
        self.count += 1
        self.total += value
        self.maximum = max(self.maximum, value)
        self.recent.append(value)

    def summary(self) -> dict:
        if not self.count:
            return {"mean": None, "p95": None, "max": None}
        ordered = sorted(self.recent)
        return {"mean": self.total / self.count, "p95": ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))],
                "max": self.maximum}


@dataclass
class _SourceStats:
    run_id: str
    started: float = field(default_factory=time.monotonic)
    frames: int = 0
    frames_no_face: int = 0
    frames_low_quality: int = 0
    submitted: int = 0
    replaced_baseline: int = 0
    ok: int = 0
    errors: int = 0
    rejected: int = 0
    reconnects: int = 0
    wait: _Timing = field(default_factory=_Timing)
    inference: _Timing = field(default_factory=_Timing)


class EngineStats:
    """Contoare per sursă pentru rularea curentă; o rulare nouă (start_source) le pornește de la zero."""

    def __init__(self):
        self._lock = Lock()
        self._sources: dict[str, _SourceStats] = {}

    def start_run(self, source_id: str, run_id: str, replaced_so_far: int) -> None:
        with self._lock:
            self._sources[source_id] = _SourceStats(run_id, replaced_baseline=replaced_so_far)

    def _current(self, source_id: str, run_id: str) -> _SourceStats | None:
        stats = self._sources.get(source_id)
        return stats if stats is not None and stats.run_id == run_id else None  # ignoră rulările vechi

    def frame(self, source_id: str, run_id: str, status: Status) -> None:
        """Chemat de SourceWorker pentru fiecare cadru real analizat."""
        with self._lock:
            if stats := self._current(source_id, run_id):
                stats.frames += 1
                stats.frames_no_face += status == Status.NO_FACE
                stats.frames_low_quality += status == Status.LOW_QUALITY

    def submitted(self, source_id: str, run_id: str) -> None:
        with self._lock:
            if stats := self._current(source_id, run_id):
                stats.submitted += 1

    def reconnect(self, source_id: str, run_id: str) -> None:
        with self._lock:
            if stats := self._current(source_id, run_id):
                stats.reconnects += 1

    def result(self, result: PredictionResult, accepted: bool) -> None:
        """Chemat de controller pentru fiecare rezultat sosit, acceptat sau respins de ResultGate."""
        with self._lock:
            stats = self._sources.get(result.source_id)
            if stats is None:
                return
            if not accepted:
                stats.rejected += 1
                return
            if result.status == Status.OK:
                stats.ok += 1
            else:
                stats.errors += 1
            stats.wait.add(result.queue_wait_ms)
            stats.inference.add(result.inference_ms)

    def snapshot(self, replaced: dict[str, int]) -> list[dict]:
        """Un rând per sursă (dicționar simplu, ușor de exportat în CSV/JSON)."""
        now = time.monotonic()
        with self._lock:
            rows = []
            for source_id, s in sorted(self._sources.items()):
                wait, inference = s.wait.summary(), s.inference.summary()
                rows.append({
                    "source_id": source_id, "run_id": s.run_id, "duration_s": now - s.started,
                    "frames": s.frames, "frames_no_face": s.frames_no_face, "frames_low_quality": s.frames_low_quality,
                    "requests_submitted": s.submitted,
                    "requests_replaced": max(0, replaced.get(source_id, 0) - s.replaced_baseline),
                    "results_ok": s.ok, "results_error": s.errors, "results_rejected": s.rejected,
                    "reconnects": s.reconnects,
                    "queue_wait_ms_mean": wait["mean"], "queue_wait_ms_p95": wait["p95"], "queue_wait_ms_max": wait["max"],
                    "inference_ms_mean": inference["mean"], "inference_ms_p95": inference["p95"],
                    "inference_ms_max": inference["max"],
                })
            return rows


def format_report(rows: list[dict]) -> str:
    """Tabel text cu statisticile, câte un bloc per sursă."""
    if not rows:
        return "Nicio sursă pornită încă."
    def ms(value):
        return "—" if value is None else f"{value:.1f} ms"
    lines = []
    for r in rows:
        frames = r["frames"] or 0
        no_face = f" ({100 * r['frames_no_face'] / frames:.0f}%)" if frames else ""
        lines += [
            f"Sursa {r['source_id']} — {r['duration_s']:.1f} s",
            f"  Cadre analizate: {frames}; fără față: {r['frames_no_face']}{no_face}; fețe prea mici: {r['frames_low_quality']}",
            f"  Cereri către model: {r['requests_submitted']}; înlocuite înainte de model: {r['requests_replaced']}",
            f"  Rezultate: {r['results_ok']} OK, {r['results_error']} cu eroare, {r['results_rejected']} respinse (întârziate)",
            f"  Așteptare în coadă: medie {ms(r['queue_wait_ms_mean'])}, p95 {ms(r['queue_wait_ms_p95'])}, max {ms(r['queue_wait_ms_max'])}",
            f"  Calcul model: medie {ms(r['inference_ms_mean'])}, p95 {ms(r['inference_ms_p95'])}, max {ms(r['inference_ms_max'])}",
            f"  Reconectări: {r['reconnects']}",
        ]
    return "\n".join(lines)
