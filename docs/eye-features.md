# Etapa 3 — caracteristicile ochilor și poziția aproximativă a irisului

Contractul pentru integrarea viitoare este în `docs/contracts.md`: EAR adimensional, iris normalizat în reperul ochiului, left/right ale subiectului, valori None și flaguri de disponibilitate. `geometric_api` serializează măsurătorile fără inferență/captură suplimentară. Profilele individuale sunt reutilizate din CalibrationManager; geometria rămâne distinctă de punctul privit pe ecran și de atenție.

## Integrare

`src/audience_analysis/eye_features.py` primește `FaceLandmarks` din modulul existent și dimensiunile `(lățime, înălțime)`. Nu încarcă modele. `test_face_landmarker.py` folosește aceeași instanță MediaPipe pentru fotografia neutră și fotografia curentă, apoi calculează separat head pose și geometria ochilor. `vision.MediaPipeHeadPose.geometry(frame_bgr)` oferă `FacialGeometry(head_pose, eyes)` dintr-o singură inferență pe cadru; metoda veche `estimate` rămâne compatibilă.

## Topologia MediaPipe și convențiile laterale

Sursa indicilor este clasa oficială [FaceLandmarksConnections din Tasks API](https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/tasks/python/vision/face_landmarker.py). Contururile sunt păstrate ca cicluri ordonate echivalente conexiunilor oficiale; nu se importă MediaPipe pentru calculele geometrice.

| Grup | Stângul subiectului | Dreptul subiectului |
|---|---|---|
| Colțuri folosite, p1 → p4 | 362 → 263 | 33 → 133 |
| Cele șase puncte EAR, p1…p6 | 362, 385, 387, 263, 373, 380 | 33, 160, 158, 133, 153, 144 |
| Inelul irisului | 474, 475, 476, 477 | 469, 470, 471, 472 |

Toate cele 16 repere ale fiecărui contur sunt în constantele `LEFT_EYE` și `RIGHT_EYE`. Pentru EAR este ales un subset cu două perechi verticale din acele contururi; acesta este algoritmul proiectului, nu o funcție EAR furnizată de MediaPipe. Centrul irisului este media celor patru puncte ale inelului. Nu presupunem existența unui iris atunci când modelul livrează numai reperele faciale fără extensia irisului.

Left/right în API sunt ale **subiectului**. La o față frontală nemirorată, ochiul stâng este în dreapta imaginii. Nu se schimbă automat etichetele pentru fotografii selfie oglindite; acestea necesită verificarea convenției intrării.

## EAR și coordonate

Landmarks normalizate `(x,y)` sunt transformate în `(x*W,y*H)` înainte de orice distanță. Calculul direct al distanțelor normalizate ar deforma EAR într-o imagine nesquare.

`EAR = (norm(p2-p6) + norm(p3-p5)) / (2 * norm(p1-p4))`.

Rezultatul este numeric și adimensional, separat pentru fiecare ochi. Lățimea degenerată produce valoare indisponibilă. EAR=0 este posibil pentru o geometrie complet închisă, dar nu este o clasificare a clipirii. Distanțele sunt 2D și nu compensează perspectiva sau yaw/pitch; sunt invariante la translație, redimensionare uniformă și rotație 2D în plan.

## Poziția irisului și condiții de disponibilitate

1. Axa orizontală locală este vectorul normalizat p1→p4. Axa verticală este perpendiculara orientată către pleoapa inferioară; geometria cu pleoape inversate este respinsă.
2. Proiectăm conturul și centrul irisului în acest reper. Coordonata orizontală a irisului se împarte la lățimea dintre colțuri. Coordonata verticală este fracția dintre minimul și maximul proiecțiilor conturului.
3. `iris_position=(u,v)` are valori [0,1] când geometria este acceptată: u crește spre direcția p1→p4, v spre pleoapa inferioară. Aceste coordonate sunt ale regiunii ochiului, nu ale ecranului. Nu se forțează valori în interval prin clipping.
4. `iris_center` este centrul în coordonate normalizate ale imaginii, iar `iris_position` este poziția în reperul ochiului. Cele două nu sunt interschimbabile.

Reperele lipsă, nefinite sau în afara imaginii invalidează ochiul afectat. Lipsa doar a irisului păstrează EAR, dacă pleoapele sunt valide. Inelul degenerat, centrul în afara regiunii ochiului, pleoapele închise sau o apertură prea mică fac poziția irisului indisponibilă. `min_iris_aperture_px` este o limită numerică configurabilă (implicit 1 pixel), nu un prag de clipire. Un ochi parțial închis poate furniza în continuare geometrie numerică dacă aceasta rămâne suficientă.

Ocluzia cunoscută de apelant se poate transmite prin `occluded_eyes=("left",)`. Landmarks nu conțin aici un scor de vizibilitate pe punct: modelul poate estima puncte și pentru o zonă ocluzionată. Verificările geometrice nu pot detecta toate ocluziile, ochelarii, reflexiile sau estimările greșite. Modulul nu pretinde că un iris numeric este vizibil fizic.

## Structura rezultatelor

`EyesResult` conține `left` și `right`, fiecare `EyeFeatures`:

- `subject_side`: left/right;
- `ear`: EAR brut sau `None`;
- `iris_center`: centrul în imagine, sau `None`;
- `iris_position`: poziția locală normalizată, sau `None`;
- `ear_relative`: EAR/EAR_neutru, numai după calibrarea ochiului;
- `gaze_delta`: poziția locală minus poziția neutră, numai când ambele există;
- `eye_points_px`, `iris_points_px`: puncte pentru vizualizare;
- `reason`: motivul indisponibilității, unde este cazul.

Un rezultat poate avea EAR valid și iris indisponibil. `None` indică lipsa estimării, nu valoarea zero. Fără față, ambii ochi întorc rezultate indisponibile. Ochiul valid nu este invalidat de problema celuilalt ochi.

## Calibrare individuală

```python
from audience_analysis.eye_features import EyeFeaturesEstimator

estimator = EyeFeaturesEstimator(min_open_ratio=0.6)  # exemplu ales de utilizator
estimator.calibrate(neutral_face, (width, height))
eyes = estimator.estimate(current_face, (width, height))
print(eyes.left.ear, eyes.left.ear_relative, eyes.left.gaze_delta)
```

`calibrate(..., sides=("left",))` calibrează doar ochiul ales. Referința necesită EAR pozitiv și iris disponibil. O calibrare invalidă nu modifică referințele existente. `clear_calibration()` le șterge. Referințele rămân în memorie și trebuie refăcute când se schimbă subiectul, camera, orientarea sau convenția de oglindire.

`min_open_ratio` nu este setat implicit. Dacă este configurat și există referință pentru ochiul respectiv, poate suprima poziția irisului când deschiderea relativă scade sub limita aleasă. Păstrează EAR numeric și explică indisponibilitatea irisului; nu produce etichete de clipire sau atenție. `gaze_delta` este o deplasare geometrică 2D, nu un unghi de privire și nici un punct privit pe ecran. Nu este compensat încă cu head pose și nu este combinat binocular.

## Testare foto

```powershell
.\.venv\Scripts\python.exe test_face_landmarker.py --input "data/test/img1.jpg" --model "models/face_landmarker.task" --output "results/eye_features.png"

.\.venv\Scripts\python.exe test_face_landmarker.py --input "data/test/img1.jpg" --neutral-image "data/test/neutral.jpg" --min-open-ratio 0.6 --output "results/eye_features_calibrated.png"
```

Scriptul afișează EAR, poziția irisurilor, rapoartele/deplasările calibrate și head pose dacă este disponibil. În imagine, ochiul stâng al subiectului este galben, cel drept cyan; centrele irisurilor sunt cruci roșii. Head pose este afișat sus, caracteristicile ochilor jos. Fără referință se afișează numai valorile brute. Dacă fotografia neutră are doar un ochi valid, acesta este calibrat, iar scriptul anunță calibrarea incompletă.

Comenzile folosesc modelul local deja configurat. Nu există descărcări, antrenare sau procesare de sesiuni video în această etapă. Testarea unitară utilizează geometrie sintetică; rezultatele sale nu demonstrează precizia MediaPipe pe persoane. Validarea următoare necesită fotografii autorizate cu ochi deschiși, privire neutră, deplasări ale irisului și ocluzii controlate.

## Verificări executate

- `.\.venv\Scripts\python.exe -m pytest -q --basetemp artifacts\pytest-eye-features-final`: **93 passed**, selecția implicită completă, inclusiv 22 de cazuri noi. Testele istorice `tests/test_*.py` nu au fost reexecutate.
- EAR și iris pe geometrie sintetică: imagine nesquare, deplasări cunoscute, scalare uniformă, rotație în plan, calibrare individuală, referință invalidă, lipsa irisului, lipsa feței, coordonate nefinite/în afara imaginii, ochi închiși, apertură redusă, inel degenerat, ocluzie transmisă de apelant.
- Test de integrare foto cu rezultat facial sintetic: o singură inițializare MediaPipe simulată, două procesări (neutru/curent), închidere și imagine adnotată salvată. Testul adaptorului `vision.py` confirmă o singură inferență pentru head pose și ambii ochi.
- Contururile ochilor și irisurilor au fost comparate prin egalitatea conexiunilor cu `FaceLandmarksConnections` din MediaPipe instalat: toate cele patru grupuri coincid.
- `.\.venv\Scripts\python.exe test_face_landmarker.py --input artifacts\mvp-window-smoke.png --output artifacts\eyes-no-face.png`: model real încărcat pe CPU, 0 fețe, EAR și iris indisponibile pentru ambii ochi, imagine salvată. Intrarea este o captură UI fără persoane.
- `artifacts/eye-features-synthetic.png`: randare inspectată vizual pe geometrie sintetică, cu EAR 0.3 și iris deplasat; nu este rezultat pe fotografie umană.

Nu a fost disponibilă o fotografie locală cu față pentru validarea ochilor cu modelul real. Nu sunt declarate acuratețe sau evaluare a privirii pe persoane.
