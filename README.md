# Analiza atenției și angajamentului — laborator video

Prototip Python pentru **experimente pe materiale autorizate**, cu aplicație desktop, preprocesare comună și comparație R0/R1/R2. Etichetele estimate nu sunt măsurători ale atenției și nu sunt destinate evaluării sau monitorizării operaționale a studenților.

## Interfață de terminal pentru cadre și videoclipuri

Pipeline-ul rulează exclusiv în terminal, primește o imagine sau un videoclip local, citește videoclipul incremental și exportă rapoarte. Nu salvează imagini cu fețe și nu identifică persoane.

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[terminal,model,vision,dev]"

# imagine
.\.venv\Scripts\python.exe -m audience_analysis image --input C:\cale\către\frame.png --output-dir results\image

# video, cu un cadru selectat pe secundă
.\.venv\Scripts\python.exe -m audience_analysis video --input C:\cale\către\video.mp4 --sample-interval 1 --device auto --output-dir results\video
```

Pentru pornire simplă pe Windows există și launcherul `start-analysis.ps1`. Fără argumente, cere calea fișierului; detectează automat dacă este imagine sau videoclip și creează un director de rezultate cu dată/oră.

```powershell
.\start-analysis.ps1
.\start-analysis.ps1 -InputPath "C:\cale\către\video.mp4" -SampleInterval 1
```

Modelul [jihedjabnoun/vit-face-emotion-recognition](https://huggingface.co/jihedjabnoun/vit-face-emotion-recognition) este încărcat local o dată pe proces pentru fața principală (cea mai mare casetă YuNet). Pentru videoclip, consola afișează frecvența expresiilor; `summary.json`, `frames.csv`, `windows.csv` și `errors.log` sunt salvate în directorul indicat. La prima rulare modelul poate necesita internet, apoi folosește cache-ul local.

Modelul are șapte clase (`Anger`, `Disgust`, `Fear`, `Happiness`, `Neutral`, `Sadness`, `Surprise`) și se așteaptă la o față clară, proeminentă în imagine. MediaPipe Face Landmarker este opțional și necesită un fișier local `.task`: `--face-landmarker-model C:\cale\face_landmarker.task`. Adaptorul furnizează unghiurile geometrice ale capului și păstrează `unknown` pentru atenție. Modelul de angajament DAiSEE nu este furnizat, prin urmare rezultatul rămâne explicit „Model de angajament indisponibil”.

## MediaPipe Face Landmarker pe o fotografie

Modulul reutilizabil `audience_analysis.face_landmarker` este folosit atât de scriptul foto, cât și de adaptorul existent `MediaPipeHeadPose` din `vision.py`. Utilizează Tasks API în modul IMAGE, maximum o față, cu blendshapes și matricea facială activate. Modelul local se află în `models/face_landmarker.task`; fișierele `.task` sunt ignorate de Git și nu se descarcă automat. Un alt laptop trebuie să primească separat modelul compatibil, din sursa oficială [MediaPipe](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python).

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[vision,dev]"
.\.venv\Scripts\python.exe test_face_landmarker.py --input "data/test/img1.jpg"

# căi configurabile, relative la directorul curent
.\.venv\Scripts\python.exe test_face_landmarker.py --input "data/test/img1.jpg" --model "models/face_landmarker.task" --output "results/face_landmarker_result.png"
```

La o față detectată, consola afișează numărul de fețe procesate (maximum 1), numărul de landmarks (în mod normal 478), primele 10 blendshapes în ordinea scorurilor și matricea 4×4. Imaginea cu punctele verzi se salvează explicit la executarea scriptului; directorul de ieșire este creat automat. Dacă nu se detectează față, consola spune acest lucru și se salvează o copie fără puncte. O imagine lipsă/invalidă sau un model lipsă produce mesaj de eroare și cod de ieșire nenul. Fotografia originală nu poate fi aleasă ca ieșire.

API: `with FaceLandmarker(model_path) as detector: result = detector.process(frame_bgr)`. `result.faces` conține landmarks `(x,y,z)`, blendshapes `(name,score)` și `transformation_matrix` sau `None`. Randarea este separată prin `draw_landmarks`. Importul modulului nu pornește MediaPipe; modelul se încarcă la construirea detectorului și se eliberează la ieșirea din `with`.

Etapa 2 adaugă `head_pose.py`: rotația este separată prin SVD de scalare și translație, apoi convertită în yaw/pitch/roll în grade. Scriptul afișează unghiurile în consolă și peste fotografie. Pentru calibrare neutră:

```powershell
.\.venv\Scripts\python.exe test_face_landmarker.py --input "data/test/img1.jpg" --neutral-image "data/test/neutral.jpg" --output "results/head_pose.png"
```

Convențiile axelor, ordinea rotațiilor, semnele, calibrarea și limitele sunt în [docs/head-pose.md](docs/head-pose.md). Fără o matrice validă, unghiurile rămân indisponibile. Scriptul foto nu calculează atenția. Modul IMAGE nu urmărește temporal fața; extensia la video va necesita modul VIDEO și timestamp-uri monotone. Verificarea inițială MediaPipe: [docs/face-landmarker-verification.md](docs/face-landmarker-verification.md).

## Task 04 — mini-template comun P1/P2/P3

Livrarea din 15 octombrie 2026 este un **schelet executabil cu simulări explicite**, nu MVP-ul cu model antrenat. Demo-urile nu folosesc oameni, camere, rețea, dataset sau ponderi. Nu se face antrenare. Datele simulate nu sunt rezultate experimentale.

Codul anterior a fost păstrat în același pachet. Contractele lui sunt în `legacy_contracts.py`, fereastra în `legacy_ui.py`, iar vechea intrare `audience_analysis.app` rămâne disponibilă separat și nu este activată de noile demo-uri. Nu există un al doilea proiect instalabil. Modulele reale anterioare sunt material de adaptat, nu o implementare validată a noului contract.

### Instalare locală

Țintă de compatibilitate a sursei: Python 3.11/3.12. Calculatorul disponibil are Python **3.13.2**, pe care au fost executate verificările curente; 3.11/3.12 necesită verificare separată. Nu este necesară instalarea pachetelor AI/video pentru mini-template.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Mediul `.venv` existent este deja instalat editable. Dacă folosești un mediu existent, nu îl recrea. Dependențe de bază: NumPy și PySide6. Grupuri opționale: `[terminal]`/`[video]` = opencv-python; `[model]` = PyTorch, Transformers și Pillow; `[dev]` = pytest, pytest-qt. `[ai]` și `[ml]` sunt păstrate numai pentru codul istoric. **Nu instala simultan opencv-python și opencv-python-headless**, deoarece ambele oferă `cv2`; folosește un mediu separat pentru schimbarea variantei.

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

Selecția implicită acoperă `tests/contracts`, `tests/ai`, `tests/video`, `tests/engine`, `tests/ui` și `tests/terminal`. Testele terminalului nu necesită dataset, cameră, rețea sau model. Testele anterioare `tests/test_*.py` sunt păstrate separat, pot necesita opționale și nu sunt declarate reexecutate în această livrare.

Testele Qt folosesc implicit offscreen; aceasta nu echivalează cu verificarea vizuală manuală pe Windows. Vezi raportul verificării pentru comenzile executate și limite. Dacă folderul temporar al mediului restricționat nu permite scrierea, setează TEMP/TMP într-un subfolder `artifacts/tmp` și rulează pytest cu `--basetemp artifacts/pytest-task04`.
