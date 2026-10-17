# Analiza atenției și angajamentului — laborator video

Prototip Python pentru **experimente pe materiale autorizate**, cu aplicație desktop, preprocesare comună și comparație R0/R1/R2. Etichetele estimate nu sunt măsurători ale atenției și nu sunt destinate evaluării sau monitorizării operaționale a studenților.

## Task 04 — mini-template comun P1/P2/P3

Livrarea din 15 octombrie 2026 este un **schelet executabil cu simulări explicite**, nu MVP-ul cu model antrenat. Demo-urile nu folosesc oameni, camere, rețea, dataset sau ponderi. Nu se face antrenare. Datele simulate nu sunt rezultate experimentale.

Codul anterior a fost păstrat în același pachet. Contractele lui sunt în `legacy_contracts.py`, fereastra în `legacy_ui.py`, iar vechea intrare `audience_analysis.app` rămâne disponibilă separat și nu este activată de noile demo-uri. Nu există un al doilea proiect instalabil. Modulele reale anterioare sunt material de adaptat, nu o implementare validată a noului contract.

### Instalare locală

Țintă de compatibilitate a sursei: Python 3.11/3.12. Calculatorul disponibil are Python **3.13.2**, pe care au fost executate verificările curente; 3.11/3.12 necesită verificare separată. Nu este necesară instalarea pachetelor AI/video pentru mini-template.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Mediul `.venv` existent este deja instalat editable. Dacă folosești un mediu existent, nu îl recrea. Dependențe de bază: NumPy și PySide6. Grupuri opționale: `[video]` = opencv-python-headless; `[ai]` = torch, torchvision, scikit-learn; `[dev]` = pytest, pytest-qt. `[ml]` este păstrat pentru codul anterior. **Nu instala simultan opencv-python și opencv-python-headless**, deoarece ambele oferă `cv2`; folosește un mediu separat pentru schimbarea variantei.

`requirements-lock.txt` este snapshotul istoric al prototipului anterior, nu un lock al mini-template-ului. Versiunile verificate acum sunt consemnate în `docs/task04-verification.md`; nu pretindem verificarea tuturor combinațiilor permise de pyproject.

### Exemple independente și integrare

```powershell
# P1: NumPy + predictor fix, fără Qt/cv2/torch/GPU
.\.venv\Scripts\python.exe -m audience_analysis.examples.p1_predictor_demo

# P2: QCoreApplication, două surse sintetice, patru rezultate, oprire controlată
.\.venv\Scripts\python.exe -m audience_analysis.examples.p2_engine_demo

# P3: scenariu independent, fără motorul P2
.\.venv\Scripts\python.exe -m audience_analysis --ui-demo

# Integrare P1/P2/P3, numai simulare
.\.venv\Scripts\python.exe -m audience_analysis --demo --config configs/demo.json

# Fără flag: ajutor și mesaj că modelul real nu este configurat
.\.venv\Scripts\python.exe -m audience_analysis
```

În fereastră, apasă **Pornește**. `--ui-demo` emite un scenariu scurt cu rezultat fix, eroare și stop. `--demo` formează secvențe din dreptunghiuri animate și le trece prin scheduler și FakePredictor. Ambele au banner permanent **SIMULARE — fără analiză AI reală**. Butonul Oprește invalidează rularea; închiderea ferestrei așteaptă asincron finalizarea cooperativă a lucrătorilor.

`run.ps1` este păstrat ca launcher al aplicației anterioare; pentru taskul 04 folosește comenzile de mai sus.

### Structură și primii pași

| Responsabil | Primul fișier de citit | Primul TODO |
|---|---|---|
| P1 — date și AI | [ai/README.md](src/audience_analysis/ai/README.md), apoi `ai/predictor.py` | P1-S2.1 în `ai/data.py`: manifest autorizat, validare, teste negative |
| P2 — motor și video | [engine/README.md](src/audience_analysis/engine/README.md), apoi `engine/controller.py` | P2-S3.1 în `video/sources.py`: adaptor real cooperativ și FramePacket corect |
| P3 — interfață | [ui/README.md](src/audience_analysis/ui/README.md), apoi `ui/main_window.py` | P3-S2.1: formular/card prin comenzile motorului, fără captură sau AI în UI |

Contractul comun este descris în [docs/contracts.md](docs/contracts.md). Fișele originale și promptul sunt păstrate în [docs/planning/](docs/planning/00_START_AICI.md), fără bifarea taskurilor. Cele trei notebookuri minimale sunt în `notebooks/template/`; notebookurile anterioare sunt păstrate și nu sunt rulate de taskul 04.

Implementat aici: contracte validate, FakePredictor determinist, sursă sintetică, pregătire comună, selectare temporală, cozi de capacitate 1/sursă, alternare, QThread AI unic, invalidare run_id, previzualizare limitată, UI injectată și helper CSV cu deduplicare și is_demo. RealPredictor, citirea reală și detecția reală au erori explicite până la integrare. Formularul complet, grila multi-sursă și dialogul CSV sunt TODO-uri.

### Testare

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Selecția implicită acoperă doar `tests/contracts`, `tests/ai`, `tests/video`, `tests/engine`, `tests/ui`. Nu necesită dataset, camere, rețea sau modele. Testele anterioare `tests/test_*.py` sunt păstrate separat, pot necesita opționale și nu sunt declarate reexecutate în această livrare.

Testele Qt folosesc implicit offscreen; aceasta nu echivalează cu verificarea vizuală manuală pe Windows. Vezi raportul verificării pentru comenzile executate și limite. Dacă folderul temporar al mediului restricționat nu permite scrierea, setează TEMP/TMP într-un subfolder `artifacts/tmp` și rulează pytest cu `--basetemp artifacts/pytest-task04`.
