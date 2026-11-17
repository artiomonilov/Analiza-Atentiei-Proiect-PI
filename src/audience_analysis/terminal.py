"""Interfață de terminal pentru citirea unui cadru imagine sau a unui videoclip.

Nu încarcă modele și nu deduce informații despre persoane. Rolul ei este să
confirme că sursa poate fi citită, să raporteze progresul și să anunțe finalul.
"""
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import time

from .model_stats import FrameStatistics


IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


@dataclass(frozen=True)
class ProcessingReport:
    source: Path
    kind: str
    frames_read: int
    frames_total: int | None
    elapsed_s: float
    frames_with_statistics: int = 0
    mean_probabilities: dict[str, float] | None = None
    most_frequent_label: str | None = None


def process_source(
    source: Path,
    on_progress: Callable[[int, int, int | None], None],
    predict_frame: Callable[[object], FrameStatistics] | None = None,
) -> ProcessingReport:
    """Citește sursa în flux și cheamă callback-ul cu procentul de progres.

    Pentru imagine există un singur cadru. Pentru videoclip nu se păstrează în
    memorie decât cadrul citit curent.
    """
    if not source.is_file():
        raise ValueError(f"Fișierul nu există: {source}")
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError("Lipsește OpenCV. Instalează extra [terminal].") from error

    started = time.monotonic()
    predictions: list[FrameStatistics] = []

    def build_report(kind: str, frames_read: int, frames_total: int | None) -> ProcessingReport:
        if not predictions:
            return ProcessingReport(source, kind, frames_read, frames_total, time.monotonic() - started)
        labels = sorted(predictions[0].probabilities)
        means = {label: sum(item.probabilities[label] for item in predictions) / len(predictions) for label in labels}
        counts = {label: sum(item.label == label for item in predictions) for label in labels}
        most_frequent = min(counts, key=lambda label: (-counts[label], label))
        return ProcessingReport(source, kind, frames_read, frames_total, time.monotonic() - started, len(predictions), means, most_frequent)

    if source.suffix.lower() in IMAGE_SUFFIXES:
        frame = cv2.imread(str(source), getattr(cv2, "IMREAD_COLOR", 1))
        if frame is None:
            raise ValueError("Imaginea nu poate fi citită sau formatul nu este acceptat.")
        on_progress(0, 0, 1)
        if predict_frame:
            predictions.append(predict_frame(frame))
        on_progress(100, 1, 1)
        return build_report("imagine", 1, 1)

    capture = cv2.VideoCapture(str(source))
    try:
        if not capture.isOpened():
            raise ValueError("Videoclipul nu poate fi deschis. Verifică fișierul și codecul disponibil.")
        total_value = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        total = total_value if total_value > 0 else None
        frames_read = 0
        last_percent = -1
        on_progress(0, 0, total)
        while True:
            ok, _frame = capture.read()
            if not ok:
                break
            frames_read += 1
            if predict_frame:
                predictions.append(predict_frame(_frame))
            percent = min(99, int(frames_read * 100 / total)) if total else 0
            if percent != last_percent:
                on_progress(percent, frames_read, total)
                last_percent = percent
        if frames_read == 0:
            raise ValueError("Videoclipul nu conține cadre care pot fi citite.")
        on_progress(100, frames_read, total)
        return build_report("videoclip", frames_read, total)
    finally:
        capture.release()


def terminal_main(source: Path, *, with_model: bool = True) -> int:
    """Punct de intrare cu mesaje de stare concise, potrivite pentru shell."""
    last_line = None

    def show_progress(percent: int, frames_read: int, frames_total: int | None) -> None:
        nonlocal last_line
        detail = f"{frames_read}/{frames_total} cadre" if frames_total else f"{frames_read} cadre"
        line = f"Progres: {percent:3d}% — {detail}"
        if line != last_line:
            print(line)
            last_line = line

    print(f"Sursă primită: {source}")
    if not source.is_file():
        raise ValueError(f"Fișierul nu există: {source}")
    predict_frame = None
    if with_model:
        from .model_stats import get_statistics_model
        print("Se încarcă modelul de statistică…")
        predict_frame = get_statistics_model().predict_bgr
    report = process_source(source, show_progress, predict_frame)
    total = str(report.frames_total) if report.frames_total is not None else "necunoscut"
    print(
        f"Gata. Tip: {report.kind}; cadre citite: {report.frames_read}; "
        f"cadre declarate: {total}; durată: {report.elapsed_s:.2f} s."
    )
    if report.mean_probabilities:
        print(f"Statistici model pentru {report.frames_with_statistics} cadru/cadre:")
        print(f"  Etichetă cea mai frecventă: {report.most_frequent_label}")
        print("  Probabilități medii: " + "; ".join(f"{label} {score:.1%}" for label, score in report.mean_probabilities.items()))
        print("  Estimările sunt experimentale; nu măsoară atenția sau starea reală a unei persoane.")
    return 0
