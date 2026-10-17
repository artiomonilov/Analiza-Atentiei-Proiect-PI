"""Generează numai cele trei notebookuri-schelet, fără rezultate salvate."""
import json
from pathlib import Path


NOTEBOOKS = [
    ("01_audit_date", "P1-S2.1 — auditul datelor",
     "Intrare: manifest autorizat, fără căi personale. TODO: validează etichete, fișiere și splituri. Ieșire: audit documentat. Verifică fișiere lipsă și suprapuneri. Nu se descarcă date.",
     "from pathlib import Path\nfrom audience_analysis.ai.data import load_training_manifest\nmanifest_path = Path('data/manifest.csv')\n# După implementarea P1-S2.1:\n# records = load_training_manifest(manifest_path)\n"),
    ("02_antrenare_comparatie", "P1-S3.1 / P1-S5.1 — baseline și GRU",
     "Intrare: date autorizate și configurație comună. TODO: adaptează arhitecturile și compară pe validation. Ieșire: configurație, ponderi și metrici reale. Verificare: splituri identice, fără folosirea testului la selecție. Acest notebook nu antrenează nimic.",
     "from audience_analysis.config import SequenceConfig\nfrom audience_analysis.video.preprocessing import prepare_bgr\nfrom audience_analysis.ai.models import build_baseline, build_temporal\n# P1 reutilizează prepare_bgr furnizat de P2; nu dubla normalizarea.\n# Configurația reală trebuie convenită cu P2, nu dedusă din demo.\n"),
    ("03_evaluare_export", "P1-S3.3 / P1-S6.1 — evaluare și export",
     "Intrare: model real fixat pe validation și set test separat. TODO: metrici/acoperire, pachet cu configurație și paritate Colab-local. Ieșire: raport real și predictor is_demo=False. Verifică aceeași secvență în ambele medii; nu salva valori fictive.",
     "from audience_analysis.ai.predictor import RealPredictor\nfrom audience_analysis.config import validate_sequence\n# După implementarea adaptorului, validează PreparedSequence deja normalizată.\n# TODO: salvează model/config/etichete/versiune și verifică paritatea.\n")
]


def main() -> None:
    folder = Path(__file__).resolve().parents[1] / "notebooks" / "template"
    folder.mkdir(parents=True, exist_ok=True)
    for name, title, text, code in NOTEBOOKS:
        path = folder/f"{name}.ipynb"
        if path.exists():
            continue  # păstrează munca ulterioară a colegilor
        notebook = {"nbformat": 4, "nbformat_minor": 4,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "cells": [
                {"cell_type": "markdown", "metadata": {}, "source": [f"# {title}\n", text]},
                {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": code.splitlines(keepends=True)}]}
        path.write_text(json.dumps(notebook, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
