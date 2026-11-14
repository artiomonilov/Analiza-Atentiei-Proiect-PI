# Etapa 2 — orientarea capului

`head_pose.py` primește matricea facială 4×4 din `FaceLandmarks.transformation_matrix`. Nu inițializează MediaPipe; poate fi reutilizat separat și testat exclusiv cu NumPy. `vision.py` deleagă acum conversia acestui modul. Scriptul foto păstrează afișarea landmarks/blendshapes și adaugă unghiurile în consolă și peste imagine.

## Convenții matematice

Interpretăm transformarea MediaPipe ca o mapare activă, pe vectori coloană, din fața canonică în reperul metric al camerei. Sistemul este drept: +X spre dreapta imaginii nemirorate, +Y în sus, +Z spre observator; camera privește spre -Z. Axa verticală a pixelilor OpenCV este inversă (+Y în jos), dar nu este utilizată pentru conversia Euler. Referință: [MediaPipe Face Geometry](https://chuoling.github.io/mediapipe/solutions/face_mesh.html#face-geometry-module).

Ordinea este fixată prin ecuația `R = Rz(roll) @ Ry(yaw) @ Rx(pitch)`. Aceasta înseamnă rotații extrinseci pe axe fixe X, apoi Y, apoi Z, aplicate de la dreapta la stânga pe vector. Rezultatul API are câmpuri numite `yaw`, `pitch`, `roll`, în grade. Funcția istorică `vision.rotation_to_angles` păstrează numai pentru compatibilitate tuplul `(pitch, yaw, roll)`.

Semnele urmează regula mâinii drepte:

| Unghi pozitiv | Rotație geometrică în reperul camerei |
|---|---|
| pitch, în jurul X | +Z se rotește spre -Y (în jos pentru o față frontală) |
| yaw, în jurul Y | +Z se rotește spre +X (dreapta imaginii) |
| roll, în jurul Z | +X se rotește spre +Y (antiorar în imaginea nemirorată) |

Aceste semne sunt definiții geometrice; „stânga persoanei” nu este „stânga imaginii”. O fotografie oglindită schimbă interpretarea vizuală. Nu se aplică automat schimbări de semn pentru selfie-uri.

## Separarea rotației

Pentru `T = [[A,t],[0,1]]`, translația `t` este ignorată. Descompunerea SVD `A=U S Vt` furnizează factorul polar `R=U Vt`, eliminând scalarea uniformă/neuniformă și stretch-ul simetric pozitiv. Nu extragem Euler direct dintr-o matrice scalată. Pentru shear arbitrar, factorul polar definește rotația cea mai apropiată, nu o recuperare garantată a mișcării fizice originale.

Validăm forma 4×4, numere finite și ultimul rând `[0,0,0,1]` cu toleranță 1e-6. Respinge reflexiile și raportul valorilor singulare sub 1e-8. O matrice lipsă/invalidă produce `HeadPose(valid=False, yaw=None, pitch=None, roll=None, reason=...)`; nu se completează cu unghiuri zero.

Yaw este reprezentat în [-90°,90°], pitch și roll în [-180°,180°]. La yaw ±90° apare gimbal lock: pitch și roll nu mai sunt unice. Modulul setează `gimbal_lock=True`, fixează roll la 0 și păstrează o reprezentare echivalentă a rotației. Unghiurile pot sări la limitele intervalelor; nu există filtrare temporală în această etapă.

## Calibrare neutră

```python
from audience_analysis.head_pose import HeadPoseEstimator

estimator = HeadPoseEstimator()
estimator.calibrate(neutral_face.transformation_matrix)
pose = estimator.estimate(current_face.transformation_matrix)
if pose.valid:
    print(pose.yaw, pose.pitch, pose.roll)
estimator.clear_calibration()
```

Se calculează `R_relative = R_neutral.T @ R_current`: rotația relativă este exprimată în axele poziției neutre. Nu se scad unghiurile Euler individuale. Referința este păstrată în instanță, în memorie. Calibrarea invalidă ridică `ValueError` și nu înlocuiește o referință validă. Schimbarea camerei, a imaginii oglindite sau a persoanei necesită o nouă referință.

## Comenzi

```powershell
# unghiuri în reperul camerei
.\.venv\Scripts\python.exe test_face_landmarker.py --input "data/test/img1.jpg" --output "results/head_pose.png"

# unghiuri față de o fotografie neutră, cu același model și cameră
.\.venv\Scripts\python.exe test_face_landmarker.py --input "data/test/img1.jpg" --neutral-image "data/test/neutral.jpg" --model "models/face_landmarker.task" --output "results/head_pose_calibrated.png"
```

Scriptul încarcă modelul o singură dată, procesează referința și imaginea curentă, apoi închide resursele. Fără față sau matrice, afișează motivul și salvează eticheta „Head pose: unavailable”. O referință neutră fără față oprește rularea cu eroare. Salvarea peste imaginea curentă sau peste referința neutră este respinsă.

Adaptorul `MediaPipeHeadPose` rămâne compatibil cu pipeline-ul prin `AttentionEstimate`, dar întoarce numai unghiuri și `status=unknown`. Parametrul vechi `calibrated=True` nu reprezintă calibrare reală; nu mai activează etichete spre/departe de ecran. Calibrarea geometrică se face prin matricea neutră. Modulul nou și scriptul foto nu rulează clasificatoare de atenție sau expresii.

## Verificări executate și limite

- `python -m pytest -q --basetemp artifacts/pytest-head-pose`: **71 passed**, în selecția implicită. Testele istorice `tests/test_*.py` nu au fost reexecutate.
- Teste sintetice: identitate, rotații pe axe și compuse, semne, translație, scalare uniformă/neuniformă, stretch simetric, neutralizare și rotații relative, matrici invalide/reflexii/singulare, gimbal lock și reconstrucție, adaptor existent și overlay pe copie.
- `python test_face_landmarker.py --input artifacts/mvp-window-smoke.png --output artifacts/head-pose-no-face.png`: inferență reală CPU cu modelul local, 0 fețe, orientare indisponibilă, imagine salvată. Această captură UI nu este o fotografie de persoană.
- Nu există fotografie locală cu față pentru validarea semnelor și a preciziei pe o persoană. Rezultatele sintetice validează algebra, nu acuratețea unghiurilor MediaPipe pe oameni.

Pose-ul depinde de ajustarea modelului facial, perspectivă, repere ocluzionate, expresie, rezoluție și convențiile modelului. Unghiurile sunt estimări geometrice; nu determină singure direcția ochilor, atenția sau angajamentul. Următoarea verificare este o serie autorizată de fotografii: neutru, dreapta/stânga, sus/jos și înclinări, cu verificarea convențiilor înainte de integrarea video.
