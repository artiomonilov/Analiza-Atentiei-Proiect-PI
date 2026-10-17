"""Regenerate the five small Colab entry points; all implementation lives in src/."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETUP = '''from pathlib import Path
import os, subprocess, sys

# În Colab: clonează/încarcă mai întâi repository-ul și ajustează această cale.
REPO = Path('/content/Analiza-Atentiei-Proiect-PI')
if not REPO.exists():
    REPO = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()
assert (REPO / 'src' / 'audience_analysis').is_dir(), 'Configurează REPO'
os.chdir(REPO)
os.environ['PYTHONPATH'] = str(REPO / 'src')

def run(*args):
    subprocess.run([sys.executable, '-m', 'audience_analysis.experiment', *args], check=True)

# Instalează dependențele o singură dată în runtime:
# %pip install -e ".[ml]"
MANIFEST = 'data/manifest.csv'
CACHE = 'artifacts/cache'
'''

NOTEBOOKS = [
    ("00_dataset_audit", "Auditul datasetului", "Verifică etichetele, participanții și spliturile oficiale înainte de antrenare. Nu încărca date în Colab fără permisiunea necesară.",
     "run('audit', MANIFEST, '--output', 'reports/audit.json')\nprint(Path('reports/audit.json').read_text())"),
    ("01_preprocessing", "Preprocesare comună", "Maximum o fereastră per clip. Examinează vizual decupajele autorizate și distribuția respingerilor; un detector funcțional nu validează etichetele de angajament.",
     "run('prepare', MANIFEST, '--output', CACHE)\n# Experiment separat, după fixarea protocolului:\n# run('prepare', MANIFEST, '--config', 'configs/no_margin.json', '--output', 'artifacts/cache-no-margin')"),
    ("02_baseline", "R1 — agregare prin medie", "Extractor MobileNetV3 Small înghețat. Selecția checkpointului folosește validation, niciodată test.",
     "run('train', CACHE, '--architecture', 'mean', '--output', 'artifacts/r1.pt', '--seed', '42')\nrun('evaluate', CACHE, 'artifacts/r1.pt', '--split', 'validation', '--output', 'reports/r1-validation.json')"),
    ("03_temporal_model", "R2 — agregare temporală GRU", "Păstrează același manifest, preprocesare și seed ca la R1. Complexitatea suplimentară nu garantează îmbunătățirea.",
     "run('train', CACHE, '--architecture', 'gru', '--output', 'artifacts/r2.pt', '--seed', '42')\nrun('evaluate', CACHE, 'artifacts/r2.pt', '--split', 'validation', '--output', 'reports/r2-validation.json')"),
    ("04_evaluation_export", "Evaluare finală și export", "Rulează test numai după fixarea alegerilor. Rapoartele conțin acoperire și R0 pe același subset acceptat. Copiază pachetul .pt local pentru testul de paritate; intrarea de referință din pachet este sintetică.",
     "PROTOCOL_FIXED = False  # schimbă după finalizarea selecției pe validation\nassert PROTOCOL_FIXED, 'Fixează protocolul înainte de test'\nfor model in ('r1', 'r2'):\n    run('evaluate', CACHE, f'artifacts/{model}.pt', '--split', 'test', '--output', f'reports/{model}-test.json')")
]


def main():
    folder = ROOT / "notebooks"
    folder.mkdir(exist_ok=True)
    for filename, title, description, code in NOTEBOOKS:
        cells = [
            {"cell_type": "markdown", "metadata": {}, "source": [f"# {title}\n", description]},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": SETUP.splitlines(keepends=True)},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": code.splitlines(keepends=True)},
        ]
        notebook = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}}, "nbformat": 4, "nbformat_minor": 4}
        (folder/f"{filename}.ipynb").write_text(json.dumps(notebook, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
