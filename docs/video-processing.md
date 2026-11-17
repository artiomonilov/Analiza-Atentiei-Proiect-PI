# Etapa 4 — procesare video și webcam

## Arhitectură și flux

`run_video_analysis.py` este intrarea pentru geometrie facială sincronă. Reutilizează `FaceLandmarker`, `HeadPoseEstimator`, `EyeFeaturesEstimator` și funcțiile existente de randare; nu apelează clasificatoarele din pipeline-ul CLI anterior. `video_processor.py` se ocupă de captură, timestampuri, măsurători și CSV. Nu există fire de execuție, cozi sau inferențe concurente.

`FaceLandmarker(model_path)` păstrează modul IMAGE pentru fotografii. Noul `FaceLandmarker(model_path, mode="VIDEO")` folosește Tasks VIDEO și `process_video(frame_bgr, timestamp_ms)` → `detect_for_video()`. Verifică ordinea strictă a timestampurilor, convertește o singură dată BGR→RGB contiguu și produce același `LandmarkerResult` ca în etapa foto. Referință API: [MediaPipe Face Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python).

O sesiune:

1. Validează sursa/modelul și deschide captura OpenCV.
2. Creează exact o instanță MediaPipe VIDEO, maximum o față.
3. Aplică opțional calibrarea neutră folosind aceeași instanță.
4. Citește un cadru și stabilește timestampul.
5. Rulează o inferență și transmite aceleași repere către head pose și ochi.
6. Livrează `VideoMeasurement` către callback/CSV și, dacă este activă, afișare.
7. Repetă până la EOF, Q, închiderea ferestrei sau Ctrl+C; închide modelul, captura, CSV-ul și fereastra creată de sesiune.

Nu reține videoclipul sau istoricul rezultatelor în RAM; callback-ul apelantului poate decide separat ce păstrează. O eroare de procesare a unui cadru este raportată în acel rând și sesiunea poate continua. Nu sunt reutilizate măsurătorile cadrului anterior când fața dispare. Cadrele invalide sunt afișate pe un fundal gol cu indicator de eroare.

## Timestampuri

`frame_index` începe de la 0 și reprezintă ordinea capturilor. Timestampurile sunt întregi nenegative în milisecunde, strict crescătoare:

- Fișier: `CAP_PROP_POS_MSEC` după `read()` dacă este finit, nenegativ și depășește timestampul anterior.
- Dacă poziția lipsește, stagnează sau regresează: `frame_index * 1000 / source_fps` când FPS-ul sursei este valid.
- Dacă nici FPS-ul nu este disponibil: estimare explicită la **30 FPS**. Aceasta nu este FPS măsurat și nu reconstruiește exact un fișier cu framerate variabil.
- Webcam: timpul scurs din `time.monotonic()` la citirea cadrului; nu este ceas calendaristic și nici timestamp hardware al expunerii.
- După rotunjire, o valoare care nu depășește precedenta este ajustată la `precedenta + 1 ms`.

CSV-ul păstrează `timestamp_source`: `video_pos_msec`, `video_fps`, `estimated_30fps` sau `webcam_monotonic`, cu sufixul `+strict_order` când s-a impus ordinea. Ajustarea nu adaugă cadre și nu pretinde că repară timingul sursei. La peste 1000 cadre/s, rezoluția întreagă de 1 ms nu poate reprezenta fidel timpul fiecărui cadru.

## Calibrare

Prin API se pot injecta estimatori deja calibrați: `VideoProcessor(model, pose_estimator=pose, eye_estimator=eyes)`. Opțiunea `--neutral-image` procesează fotografia neutră cu instanța VIDEO la timestamp 0, înaintea fluxului, și calibrează orientarea și ambii ochi. Cadrele video încep apoi cu timestampuri strict mai mari; un prim timestamp 0 al fișierului este ajustat la 1 ms. Referința nu apare în CSV, iar indexul primului cadru video rămâne 0.

O referință fără față, fără matrice validă sau fără geometrie validă pentru ambii ochi oprește sesiunea cu mesaj de eroare. Referința trebuie să fie a aceluiași subiect, cu ochii deschiși și aceeași configurație de cameră/oglindire. Sesiunea fără `--neutral-image` furnizează valori brute sau folosește calibrările injectate de apelant.

## Instalare și comenzi

Folosește mediul virtual existent și modelul local `models/face_landmarker.task`. Nu se descarcă modele din acest script. Dependențe: NumPy, OpenCV cu suport GUI pentru afișare și MediaPipe Tasks; versiuni importate local: NumPy 2.5.4, OpenCV 5.0.0, MediaPipe 1.2.0, Python 3.13.2.

```powershell
# dependențele MediaPipe includ furnizorul OpenCV contrib
.\.venv\Scripts\python.exe -m pip install -e ".[vision,dev]"

# webcam: Q oprește, nu înregistrează automat
.\.venv\Scripts\python.exe run_video_analysis.py --source 0

# fișier cu afișare, puncte faciale opționale
.\.venv\Scripts\python.exe run_video_analysis.py --source "data/test/video.mp4" --show-landmarks

# fișier fără fereastră, cu export solicitat explicit
.\.venv\Scripts\python.exe run_video_analysis.py --source "data/test/video.mp4" --no-display --output-csv "results/video_measurements.csv"

# calibrare neutră
.\.venv\Scripts\python.exe run_video_analysis.py --source 0 --model "models/face_landmarker.task" --neutral-image "data/test/neutral.jpg"
```

Un `--source` alcătuit numai din cifre este index de cameră; pentru un fișier numit numeric folosește o cale, de exemplu `./123`. Sunt acceptate numai camere locale și fișiere existente. `--no-display` este disponibil numai pentru fișiere; webcamul folosește afișarea cu Q sau Ctrl+C pentru oprire.

Fără `--show-landmarks` se păstrează contururile ochilor și centrele irisurilor; punctele întregii fețe sunt dezactivate. Overlay-ul arată yaw/pitch/roll, EAR, poziția irisurilor, FPS de procesare și FACE/NO FACE/PROCESSING ERROR. Nu se păstrează imagini sau înregistrări video.

## Structura rezultatelor și CSV

`VideoProcessor.run(...)` returnează `VideoSessionReport`: numărul cadrelor, cadrelor cu față și erorilor, durata, FPS-ul real, FPS-ul sursei (sau `None`) și motivul opririi. `on_result(record)` primește sincron câte un `VideoMeasurement`, independent de export.

| Coloane | Sens |
|---|---|
| timestamp_ms, frame_index, face_detected | Timp, index și existența feței în cadrul curent |
| yaw, pitch, roll | Grade conform convențiilor din `head-pose.md` |
| left_ear, right_ear | EAR separat, numeric dacă este disponibil |
| left_iris_x, left_iris_y, right_iris_x, right_iris_y | Poziții în reperul local al fiecărui ochi, nu coordonate ale ecranului |
| head_pose_available, head_pose_calibrated, head_pose_gimbal_lock | Disponibilitate, calibrare și singularitate Euler |
| left_ear_available, right_ear_available, left_iris_available, right_iris_available | Disponibilitate individuală |
| left_ear_relative, right_ear_relative | EAR / EAR neutru |
| left_gaze_dx, left_gaze_dy, right_gaze_dx, right_gaze_dy | Deplasare geometrică față de irisul neutru |
| timestamp_source, processing_fps | Proveniența timpului și debitul cumulativ măsurat |
| head_pose_reason, left_eye_reason, right_eye_reason, error | Motivele indisponibilității și eroarea de procesare |

CSV-ul se creează doar cu `--output-csv`, în UTF-8, și este scris/flush-uit după fiecare cadru, în ordinea temporală. Valorile `None` sunt celule goale, iar un zero măsurat rămâne numeric. Fișierul trebuie să nu existe deja; nu se suprascrie. Ctrl+C păstrează rândurile deja scrise și returnează cod 130. O eroare de cameră sau de citire păstrează CSV-ul parțial și eliberează resursele.

## Performanță și verificări executate

- `.\.venv\Scripts\python.exe -m pytest -q --basetemp artifacts\pytest-video-stage4-final`: **115 passed** în selecția implicită completă; testele istorice `tests/test_*.py` nu au fost reexecutate.
- Testele noi folosesc capturi și rezultate MediaPipe simulate: VIDEO/timestampuri, fallback-uri, ceas webcam, față prezentă/absentă/recuperată, geometrie, un singur model, referință neutră, cadru invalid, eroare de inferență, fișiere/camere indisponibile, CSV, Ctrl+C, Q, erori GUI și eliberarea resurselor.
- Compatibilitatea IMAGE este păstrată în suita foto. Scriptul foto a rulat separat cu modelul real pe captura UI fără față și a salvat `artifacts/stage4-photo-compat.png`.
- Rulare reală VIDEO cu modelul local:

```powershell
.\.venv\Scripts\python.exe run_video_analysis.py --source artifacts\mvp_blank.avi --no-display --output-csv artifacts\stage4-smoke-final.csv
```

Rezultat verificat: 20 cadre, 0 fețe, 0 erori; sursă 160×120 la 5 FPS, timestampuri 0…3800 ms strict crescătoare. CSV-ul are 20 rânduri și celule goale pentru unghiuri/EAR indisponibile. În acea rulare durata buclei a fost 0.101 s, aproximativ **197.64 FPS**. Această valoare descrie doar clipul gol, mic, fără afișare; nu este performanța pe o persoană sau pe webcam.

FPS-ul procesării este număr de cadre / timpul monotonic al buclei. Exclude încărcarea modelului/calibrarea, include citirea, inferența, exportul și afișarea sesiunii. Overlay-ul este cumulativ până la desenarea cadrului curent, iar valoarea finală include întreaga buclă. FPS-ul sursei este metadată separată; fișierele sunt procesate cât de repede permite sistemul, fără sincronizare la viteza de redare originală. Fără afișare nu se desenează overlay-uri.

## Limite și următorul pas

Webcamul fizic și afișarea nativă în timp real nu au fost verificate manual; în teste sunt simulate. Nu a fost disponibil un video local autorizat cu persoane pentru validarea continuă a head pose/irisului cu modelul real. MediaPipe a emis avertismente native despre feedback tensors și a folosit XNNPACK CPU; rularea s-a încheiat cu succes.

OpenCV poate raporta `read=False` atât la sfârșit, cât și la coruperea fluxului; după cel puțin un cadru de fișier, acest semnal este tratat ca final. Pentru cameră este eroare. Captura sincronă poate întârzia în backendul camerei, iar Q nu poate fi citit în timp ce `read()` sau inferența blochează. Nu există recuperare automată după deconectarea camerei.

Se procesează maximum o față; nu există identificare sau garanție că fața rămâne a aceleiași persoane. Calibrarea nu trebuie reutilizată la schimbarea subiectului. Head pose, EAR și irisul au limitările geometrice descrise în documentele etapelor 2/3 și nu produc scoruri de atenție sau clasificări de emoții în acest flux.

Următoarea verificare recomandată: webcam local autorizat și video cu o persoană, cu pierderea/revenirea feței, Q, calibrare și export; apoi măsurarea vitezei și a stabilității pe rezoluția finală.
