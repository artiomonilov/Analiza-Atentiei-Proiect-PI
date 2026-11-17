# Analiza atenției și angajamentului — laborator video

Prototip Python pentru **experimente pe materiale autorizate**, cu aplicație desktop, preprocesare comună și comparație R0/R1/R2. Etichetele estimate nu sunt măsurători ale atenției și nu sunt destinate evaluării sau monitorizării operaționale a studenților.

Starea curentă a ramurii și toate taskurile P1: [bilanțul de finalizare](docs/artiom-branch-completion.md). Mediul separat verificat și versiunile: [docs/environment.md](docs/environment.md). Predictorul P1, manifestele și comparațiile sunt documentate în [docs/p1-data-model.md](docs/p1-data-model.md). Nu este furnizat un model de angajament evaluat pe DAiSEE.

## Interfață de terminal pentru cadre și videoclipuri

Pipeline-ul rulează exclusiv în terminal, primește o imagine sau un videoclip local, citește videoclipul incremental și exportă rapoarte. Nu salvează imagini cu fețe și nu identifică persoane.

```powershell
py -3.13 -m venv .venv-local
$env:PYTHONUTF8 = "1"
.\.venv-local\Scripts\python.exe -m pip install -c configs/constraints-windows-py313.txt -e ".[terminal,model,vision,dev]"

# imagine
.\.venv-local\Scripts\python.exe -m audience_analysis image --input C:\cale\către\frame.png --output-dir results\image

# video, cu un cadru selectat pe secundă
.\.venv-local\Scripts\python.exe -m audience_analysis video --input C:\cale\către\video.mp4 --sample-interval 1 --device auto --output-dir results\video
```

Pentru pornire simplă pe Windows există și launcherul `start-analysis.ps1`. Fără argumente, cere calea fișierului; detectează automat dacă este imagine sau videoclip și creează un director de rezultate cu dată/oră.

```powershell
.\start-analysis.ps1
.\start-analysis.ps1 -InputPath "C:\cale\către\video.mp4" -SampleInterval 1
.\start-analysis.ps1 -InputPath "C:\cale\către\video.mp4" -PythonPath ".\.venv-completion\Scripts\python.exe"
```

Modelul [jihedjabnoun/vit-face-emotion-recognition](https://huggingface.co/jihedjabnoun/vit-face-emotion-recognition) folosește revizia fixată `ec667156e4f9a2e329911a1da5c13572ae3d75d4`, din cache-ul local implicit. Pentru descărcare este necesar `--allow-model-download`. Este încărcat o dată pe proces pentru fața principală (cea mai mare casetă YuNet). CLI-ul video agregă fără a reține toate rezultatele; CSV-urile se scriu incremental în directorul nou cerut, inclusiv un raport parțial la Ctrl+C. Rapoartele nu includ implicit calea absolută a sursei. API-ul păstrează opțiunea istorică `retain_frames=True`; pentru sesiuni lungi folosește `retain_frames=False` și `report_dir` de la început.

Exemplele directe folosesc un mediu nou `.venv-local`; păstrează `.venv` original și orice mediu asociat unui V înghețat. Mediul verificat în această livrare este `.venv-completion`. Launcherul îl preferă dacă există și permite alegerea explicită prin `-PythonPath`; nu modifică mediile. `-AllowModelDownload` transmite autorizarea explicită de descărcare către CLI. Launcherul pornește Python cu UTF-8; pentru comenzile directe păstrează `$env:PYTHONUTF8="1"` în PowerShell.

Modelul are șapte clase (`Anger`, `Disgust`, `Fear`, `Happiness`, `Neutral`, `Sadness`, `Surprise`) și se așteaptă la o față clară, proeminentă în imagine. MediaPipe Face Landmarker este opțional și necesită un fișier local `.task`: `--face-landmarker-model C:\cale\face_landmarker.task`. Adaptorul furnizează unghiurile geometrice ale capului și păstrează `unknown` pentru atenție. Modelul de angajament DAiSEE nu este furnizat, prin urmare rezultatul rămâne explicit „Model de angajament indisponibil”.

## MediaPipe Face Landmarker pe o fotografie

Modulul reutilizabil `audience_analysis.face_landmarker` este folosit atât de scriptul foto, cât și de adaptorul existent `MediaPipeHeadPose` din `vision.py`. Utilizează Tasks API în modul IMAGE, maximum o față, cu blendshapes și matricea facială activate. Modelul local se află în `models/face_landmarker.task`; fișierele `.task` sunt ignorate de Git și nu se descarcă automat. Un alt laptop trebuie să primească separat modelul compatibil, din sursa oficială [MediaPipe](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python).

```powershell
.\.venv-local\Scripts\python.exe -m pip install -e ".[vision,dev]"
.\.venv-local\Scripts\python.exe test_face_landmarker.py --input "data/test/img1.jpg"

# căi configurabile, relative la directorul curent
.\.venv-local\Scripts\python.exe test_face_landmarker.py --input "data/test/img1.jpg" --model "models/face_landmarker.task" --output "results/face_landmarker_result.png"
```

La o față detectată, consola afișează numărul de fețe procesate (maximum 1), numărul de landmarks (în mod normal 478), primele 10 blendshapes în ordinea scorurilor și matricea 4×4. Imaginea cu punctele verzi se salvează explicit la executarea scriptului; directorul de ieșire este creat automat. Dacă nu se detectează față, consola spune acest lucru și se salvează o copie fără puncte. O imagine lipsă/invalidă sau un model lipsă produce mesaj de eroare și cod de ieșire nenul. Fotografia originală nu poate fi aleasă ca ieșire.

API: `with FaceLandmarker(model_path) as detector: result = detector.process(frame_bgr)`. `result.faces` conține landmarks `(x,y,z)`, blendshapes `(name,score)` și `transformation_matrix` sau `None`. Randarea este separată prin `draw_landmarks`. Importul modulului nu pornește MediaPipe; modelul se încarcă la construirea detectorului și se eliberează la ieșirea din `with`.

Etapa 2 adaugă `head_pose.py`: rotația este separată prin SVD de scalare și translație, apoi convertită în yaw/pitch/roll în grade. Scriptul afișează unghiurile în consolă și peste fotografie. Pentru calibrare neutră:

```powershell
.\.venv-local\Scripts\python.exe test_face_landmarker.py --input "data/test/img1.jpg" --neutral-image "data/test/neutral.jpg" --output "results/head_pose.png"
```

Convențiile axelor, ordinea rotațiilor, semnele, calibrarea și limitele sunt în [docs/head-pose.md](docs/head-pose.md). Fără o matrice validă, unghiurile rămân indisponibile. Scriptul foto nu calculează atenția. IMAGE este pentru fotografie; VIDEO cu timestampuri strict crescătoare este implementat în etapa 4. Verificarea inițială MediaPipe: [docs/face-landmarker-verification.md](docs/face-landmarker-verification.md).

## Etapa 3 — ochi, EAR și poziția aproximativă a irisului

`eye_features.py` reutilizează reperele deja extrase. Returnează separat pentru fiecare ochi EAR, centrul și poziția relativă a irisului, plus abaterile față de o referință neutră. Etichetele left/right sunt ale subiectului. Scriptul foto afișează aceste valori, head pose și contururile ochilor peste imagine:

```powershell
.\.venv-local\Scripts\python.exe test_face_landmarker.py --input "data/test/img1.jpg" --output "results/eyes.png"
.\.venv-local\Scripts\python.exe test_face_landmarker.py --input "data/test/img1.jpg" --neutral-image "data/test/neutral.jpg" --output "results/eyes_calibrated.png"
```

`--min-open-ratio` permite o limită individuală opțională EAR/EAR_neutru pentru disponibilitatea irisului; nu există prag universal de clipire. Geometria insuficientă sau lipsa feței produce valori indisponibile. API-ul `vision.MediaPipeHeadPose.geometry` returnează head pose și ochi dintr-o singură inferență. Formule, indicii oficiali, calibrare și limitări: [docs/eye-features.md](docs/eye-features.md).

## Etapa 4 — fișiere video și webcam, geometrie facială

`run_video_analysis.py` procesează sincron fiecare cadru cu o singură instanță MediaPipe VIDEO. Afișează head pose, ochi/irisuri, EAR, FPS de procesare și starea detecției. Q oprește sesiunea. Exemple:

```powershell
.\.venv-local\Scripts\python.exe run_video_analysis.py --source 0
.\.venv-local\Scripts\python.exe run_video_analysis.py --source "data/test/video.mp4" --show-landmarks
.\.venv-local\Scripts\python.exe run_video_analysis.py --source "data/test/video.mp4" --no-display --output-csv "results/measurements.csv"
```

Modelul implicit este `models/face_landmarker.task`; `--neutral-image` calibrează orientarea și ochii cu aceeași instanță. CSV-ul este opțional și trebuie să fie un fișier nou. Nu se înregistrează automat imagini sau video. Timestampuri, structură CSV, performanța măsurată și limite: [docs/video-processing.md](docs/video-processing.md).

## Etapa 5 — ferestre temporale și evenimente geometrice

`temporal_analysis.py` adaugă ferestre glisante de 5/10/30 secunde, mișcarea capului și irisurilor, clipiri cu histerezis și filtrare geometrică opțională. Istoricul este limitat, duratele folosesc timestampurile și datele lipsă nu sunt interpolate. Clipirile necesită praguri EAR individuale; exemplul de configurare le păstrează dezactivate.

```powershell
.\.venv-local\Scripts\python.exe run_video_analysis.py --source 0 --show-temporal --temporal-config configs/temporal.example.json
.\.venv-local\Scripts\python.exe run_video_analysis.py --source "data/test/video.mp4" --no-display --output-temporal-csv "results/temporal.csv" --output-blinks-csv "results/blinks.csv"
```

Exportul temporal și exportul clipirilor sunt independente de CSV-ul brut `--output-csv`. Evenimentele automate sunt etichetate ca nevalidate experimental. Configurare, formule, calibrare și comparare cu referințe manuale: [docs/temporal-analysis.md](docs/temporal-analysis.md).

## Etapa 6 — calibrare și evaluare cantitativă

`calibrate_session.py` creează profile locale pentru head pose neutru, EAR și iris. `run_video_analysis.py --calibration profil.json` reutilizează profilul. `run_validation.py` evaluează CSV-urile față de referințe compatibile și exportă JSON/CSV, cu grafice opționale:

```powershell
.\.venv-local\Scripts\python.exe calibrate_session.py --neutral-image "data/test/neutral.png" --session-id C01 --output "results/calibration_C01.json"
.\.venv-local\Scripts\python.exe run_validation.py --measurements "results/V01_frames.csv" --config "configs/validation.example.json" --output-dir "results/V01_report"
```

Fără referințe independente nu se raportează precizie în grade. Sesiunile declarate pentru calibrare și evaluarea finală sunt verificate separat. Protocolul, formulele, scenariile și comenzile complete sunt în [docs/calibration-validation.md](docs/calibration-validation.md); structura datelor locale este în [validation_dataset/README.md](validation_dataset/README.md).

## Etapa 7 — dashboard experimental local

Dashboardul folosește PySide6 și QtCharts, deja compatibile cu proiectul. Încarcă CSV-uri, afișează curbe cu goluri pentru măsurători indisponibile, permite adnotarea manuală pe cadre video și reutilizează motorul de validare.

```powershell
.\.venv-local\Scripts\python.exe run_dashboard.py
.\.venv-local\Scripts\python.exe run_dashboard.py --measurements "results/V01_frames.csv" --session-id V01
```

Video este opțional. Sesiunile și rapoartele sunt salvate numai la cerere; marcajele manuale sunt separate de predicții. Instalare, sincronizare, export și protocolul practic: [docs/dashboard-validation.md](docs/dashboard-validation.md).

## Etapa 8 — evaluare experimentală C01 / D01 / V01

Fluxul local separă calibrarea de dezvoltare și validarea independentă. Configurația finală include profilul, parametrii temporali, modelul și versiunea codului; V01 necesită pachetul înghețat și verificarea provenienței CSV. Dashboardul permite adnotarea independentă a condițiilor/absenței feței și compararea sesiunilor, cu N/A pentru metricile fără referințe suficiente. Nu este implementat un clasificator de atenție.

```powershell
.\.venv-local\Scripts\python.exe experimental_session.py --help
.\.venv-local\Scripts\python.exe run_dashboard.py
```

Protocolul complet, comenzile C01 → D01 → V01, exportul rapoartelor, reproducibilitatea și eliminarea datelor: [docs/real-world-evaluation.md](docs/real-world-evaluation.md). Datele tehnice sintetice nu constituie validare experimentală pe persoane.

## Task 04 — mini-template comun P1/P2/P3

Livrarea din 15 octombrie 2026 este un **schelet executabil cu simulări explicite**, nu MVP-ul cu model antrenat. Demo-urile nu folosesc oameni, camere, rețea, dataset sau ponderi. Nu se face antrenare. Datele simulate nu sunt rezultate experimentale.

Codul anterior a fost păstrat în același pachet. Contractele lui sunt în `legacy_contracts.py`, fereastra în `legacy_ui.py`, iar vechea intrare `audience_analysis.app` rămâne disponibilă separat și nu este activată de noile demo-uri. Nu există un al doilea proiect instalabil. Modulele reale anterioare sunt material de adaptat, nu o implementare validată a noului contract.

### Instalare locală

Țintă de compatibilitate a sursei: Python 3.11/3.12. Calculatorul disponibil are Python **3.13.2**, pe care au fost executate verificările curente; 3.11/3.12 necesită verificare separată. Nu este necesară instalarea pachetelor AI/video pentru mini-template.

```powershell
python -m venv .venv
.\.venv-local\Scripts\python.exe -m pip install -e ".[dev]"
```

Mediul `.venv` existent este păstrat. Verificările de consolidare folosesc `.venv-completion`, instalat separat din wheel. Dependențe de bază: NumPy și PySide6. `[terminal]`/`[video]` folosesc opencv-contrib-python, `[model]` include torch/torchvision, Transformers și Pillow, `[dev]` include pytest/pytest-qt. Folosește o singură distribuție OpenCV într-un mediu nou. Rețeta și limitele exacte sunt în [docs/environment.md](docs/environment.md); nu modifica mediul unui V înghețat.

`requirements-lock.txt` este snapshotul istoric al prototipului anterior, nu un lock al mini-template-ului. Versiunile verificate acum sunt consemnate în `docs/task04-verification.md`; nu pretindem verificarea tuturor combinațiilor permise de pyproject.

### Exemple independente și integrare

```powershell
# P1: NumPy + predictor fix, fără Qt/cv2/torch/GPU
.\.venv-local\Scripts\python.exe -m audience_analysis.examples.p1_predictor_demo

# P2: QCoreApplication, două surse sintetice, patru rezultate, oprire controlată
.\.venv-local\Scripts\python.exe -m audience_analysis.examples.p2_engine_demo

# P3: scenariu independent, fără motorul P2
.\.venv-local\Scripts\python.exe -m audience_analysis --ui-demo

# Integrare P1/P2/P3, numai simulare
.\.venv-local\Scripts\python.exe -m audience_analysis --demo --config configs/demo.json

# Fără flag: ajutor și mesaj că modelul real nu este configurat
.\.venv-local\Scripts\python.exe -m audience_analysis
```

În fereastră, apasă **Pornește**. `--ui-demo` emite un scenariu scurt cu rezultat fix, eroare și stop. `--demo` formează secvențe din dreptunghiuri animate și le trece prin scheduler și FakePredictor. Ambele au banner permanent **SIMULARE — fără analiză AI reală**. Butonul Oprește invalidează rularea; închiderea ferestrei așteaptă asincron finalizarea cooperativă a lucrătorilor.

`run.ps1` este păstrat ca launcher al aplicației anterioare; pentru taskul 04 folosește comenzile de mai sus.

### Structură și primii pași

| Responsabil | Primul fișier de citit | Primul TODO |
|---|---|---|
| P1 — date și AI | [ai/README.md](src/audience_analysis/ai/README.md), apoi `ai/predictor.py` | Date autorizate, ponderi reale și evaluare/paritate Colab; infrastructura software este implementată |
| P2 — motor și video | [engine/README.md](src/audience_analysis/engine/README.md), apoi `engine/controller.py` | P2-S3.1 în `video/sources.py`: adaptor real cooperativ și FramePacket corect |
| P3 — interfață | [ui/README.md](src/audience_analysis/ui/README.md), apoi `ui/main_window.py` | P3-S2.1: formular/card prin comenzile motorului, fără captură sau AI în UI |

Contractul comun este descris în [docs/contracts.md](docs/contracts.md). Fișele originale și promptul sunt păstrate în [docs/planning/](docs/planning/00_START_AICI.md), fără bifarea taskurilor. Cele trei notebookuri minimale sunt în `notebooks/template/`; notebookurile anterioare sunt păstrate și nu sunt rulate de taskul 04.

Template-ul implementează contracte validate, FakePredictor determinist, sursă sintetică, pregătire comună, cozi limitate, QThread AI unic, invalidare run_id, UI injectată și helper CSV. RealPredictor P1 este acum funcțional pentru pachete locale validate și raportează MODEL_UNAVAILABLE la lipsa lor. Citirea/detecția reală în motorul template și UI-ul multi-sursă rămân integrare P2/P3; CLI-ul geometric separat nu le activează implicit.

### Testare

```powershell
.\.venv-local\Scripts\python.exe -m pytest
```

Selecția implicită acoperă `tests/contracts`, `tests/ai`, `tests/video`, `tests/engine`, `tests/ui` și `tests/terminal`. Testele terminalului nu necesită dataset, cameră, rețea sau model. Testele anterioare `tests/test_*.py` sunt păstrate separat, pot necesita opționale și nu sunt declarate reexecutate în această livrare.

Testele Qt folosesc implicit offscreen; aceasta nu echivalează cu verificarea vizuală manuală pe Windows. Vezi raportul verificării pentru comenzile executate și limite. Dacă folderul temporar al mediului restricționat nu permite scrierea, setează TEMP/TMP într-un subfolder `artifacts/tmp` și rulează pytest cu `--basetemp artifacts/pytest-task04`.
