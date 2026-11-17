# Integrare Face Landmarker — 14 noiembrie 2026

## Arhitectură

Înainte: `vision.py` inițializa MediaPipe pentru adaptorul de orientare a capului, iar `test_face_landmarker.py` inițializa separat același model și implementa desenarea.

După:

```text
test_face_landmarker.py       argumente CLI, afișare și salvare explicită
src/audience_analysis/
  face_landmarker.py         Tasks API, tipuri rezultate, I/O, randare
  vision.py                  adaptorul existent reutilizează modulul comun
models/
  README.md                  instrucțiuni model local
  face_landmarker.task       model existent local, ignorat de Git
tests/terminal/
  test_face_landmarker.py    teste fără inferență reală sau rețea
```

Fișierele schimbate pentru integrare: modulul nou, adaptorul din `vision.py`, scriptul foto existent, testele noi, README, această verificare, `models/README.md`, `.gitignore`. Modificările anterioare ale launcherului și CLI-ului mov sunt păstrate.

## Verificări executate

- Python 3.13.2, MediaPipe 1.2.0, OpenCV 5.0.0, NumPy 2.5.4: importate local cu succes în `.venv`.
- `models/face_landmarker.task` exista înaintea modificărilor (3.758.596 bytes). Nu s-a descărcat model sau fotografie în acest task.
- `python -m pytest -q --basetemp artifacts/pytest-landmarker`: **41 passed**. Selecția implicită include noile teste; testele istorice `tests/test_*.py` nu au fost reexecutate.
- Testele noi verifică opțiunile Tasks IMAGE/num_faces=1, BGR→RGB contiguu, absența feței, extragerea datelor din rezultate simulate (478 puncte, blendshapes, matrice), intrări invalide, fișiere lipsă, închiderea inclusiv la excepție și randarea/salvarea/citirea PNG pe cale Unicode.
- `python test_face_landmarker.py --input artifacts/mvp-window-smoke.png --output artifacts/landmarker-smoke.png`: încărcare reală a modelului, inferență CPU și salvare reușite, **0 fețe**. Intrarea este o captură UI, fără persoane; rezultatul nu validează extragerea pe o fotografie cu față.

## Limite și următorul pas

Nu există fotografie locală cu față identificată ca material de test. Numărul real de landmarks, blendshapes și matricea pe o față nu sunt declarate validate cu modelul real. Pentru această verificare, echipa poate rula:

```powershell
.\.venv\Scripts\python.exe test_face_landmarker.py --input "data/test/img1.jpg" --model "models/face_landmarker.task" --output "results/face_landmarker_result.png"
```

MediaPipe a emis avertismente native despre feedback tensors și a utilizat XNNPACK CPU; execuția s-a încheiat cu succes. Modulul nou nu definește clasificare a atenției și nu interpretează automat blendshapes. Etapa următoare este validarea pe fotografie autorizată, apoi definirea convențiilor pentru geometria ochilor și orientarea capului înainte de calibrare sau utilizarea temporală.
