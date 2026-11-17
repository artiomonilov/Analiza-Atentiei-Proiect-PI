# Mediu de referință și reproducere

Configurația efectiv verificată este **Windows, CPython 3.13.2, CPU**. Pachetul declară Python >=3.11, însă combinațiile 3.11/3.12 și alte sisteme nu au fost reverificate în această livrare. Nu se pretinde suport experimental pe toate versiunile permise de dependențele generale.

Mediul `.venv` original este păstrat. Conține încă atât opencv-python, cât și opencv-contrib-python, și nu are torchvision; nu îl „reparăm” peste un experiment V înghețat. `.venv-completion` este un venv separat, fără system-site-packages/PYTHONPATH către cel vechi. Pentru economie de rețea, în el au fost replicate offline 62 de distribuții și dependențele lor din fișierele RECORD ale mediului existent, excluzând opencv-python și cache-urile; apoi s-au instalat wheel-ul proiectului și torchvision 0.29.2. Au fost copiate aproximativ 1.61 GB local; singura bibliotecă descărcată a fost wheel-ul torchvision de aproximativ 1.4 MB, fără dataset sau ponderi. `pip check`, importurile native și testele au fost executate în acest mediu, nu într-un overlay al mediului vechi.

Versiuni principale observate: NumPy 2.5.4, PySide6 6.12.0, MediaPipe 1.2.0, opencv-contrib-python 5.0.0.93, torch 2.15.0+cpu, torchvision 0.29.2+cpu, transformers 5.20.2, pytest 9.1.1, pytest-qt 4.5.0. Versiunile din metadatele pip ale torch/torchvision omit sufixul local `+cpu`. O singură distribuție OpenCV este prezentă în venv-ul separat. `pip check` a trecut; acesta nu este un substitut pentru inferență/teste.

`configs/constraints-windows-py313.txt` fixează versiunile distribuțiilor relevante observate. Nu este un lock cu hashurile tuturor wheel-urilor și nu pretindem că instalarea online a tuturor acelor pachete a fost repetată de la zero. Snapshotul istoric `requirements-lock.txt` este păstrat ca istoric PyQt5, nu ca rețeta versiunii curente. Matricea oficială și instrucțiunile native trebuie consultate dacă se alege altă pereche torch/torchvision sau alt hardware: [Torchvision](https://github.com/pytorch/vision#installation), [PyTorch](https://pytorch.org/get-started/locally/). Wheel-ul folosit aici declară torch>=2.14.0; perechea locală de mai sus a trecut efectiv testele de arhitectură.

## Instalare într-un mediu nou

Comenzi PowerShell propuse pentru reproducere online, folosind Pythonul de referință. Alege un director nou; nu înlocui mediul unui V existent:

```powershell
py -3.13 -m venv .venv-local
$env:PYTHONUTF8 = "1"
.\.venv-local\Scripts\python.exe -m pip install -c configs/constraints-windows-py313.txt -e ".[dev,vision,terminal,model]"
.\.venv-local\Scripts\python.exe -m pip check
```

Extra-urile terminal/video folosesc acum numai opencv-contrib-python; nu instala suplimentar opencv-python, opencv-python-headless sau opencv-contrib-python-headless peste el. Extra-ul model include torchvision. Metricile P1 sunt NumPy și nu cer scikit-learn; extra-ul istoric `[ai]` îl păstrează pentru compatibilitate, dar nu a fost necesar testelor curente.

Pentru a verifica distribuția wheel fără rulare din repository:

```powershell
.\.venv-local\Scripts\python.exe -m pip wheel . --no-deps --wheel-dir artifacts/wheels
# Instalează wheel-ul într-un alt venv cu dependențele corespunzătoare.
# Entry points: audience-ai, audience-video, audience-calibrate,
# audience-validate, audience-dashboard, audience-session.
```

Scripturile root necesare sunt incluse în wheel. `experimental.code_version()` construiește aceleași chei canonice pentru checkout și wheel; nu hashează toate pachetele instalate. Un wheel nou/cod nou necesită un nou ciclu D/V. Git revision poate lipsi în instalarea standalone; hashul surselor rămâne disponibil.

## Modele locale

- MediaPipe local verificat tehnic anterior: `face_landmarker.task`, **3758596 bytes**, SHA256 `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`. Acesta identifică fișierul local, nu garantează autenticitatea unei alte copii. Compară hashul și sursa înainte de folosire. Ponderile nu sunt în Git și nu sunt descărcate de scripturile geometrice.
- Expresii: `jihedjabnoun/vit-face-emotion-recognition`, revizia fixată `ec667156e4f9a2e329911a1da5c13572ae3d75d4`, identificată din cache-ul local existent. Loaderul folosește `local_files_only=True` implicit. Descărcarea acelei revizii este permisă numai când operatorul cere explicit `--allow-model-download`; importul, colecția pytest și geometria nu descarcă modele. Modelul existent a fost încărcat offline și verificat printr-un forward pe o imagine uniformă sintetică: șapte probabilități finite cu sumă 1. Nu s-au descărcat ponderi și nu s-a evaluat acuratețea pe persoane.
- Angajament P1: nu există ponderi reale autorizate/evaluate. `audience-ai inspect-model <pachet>` raportează MODEL_UNAVAILABLE dacă pachetul nu poate fi încărcat. Niciun checkpoint sintetic nu este livrat drept model.

## Testare

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
$env:PYTHONUTF8 = "1"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
.\.venv-completion\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp artifacts/pytest-completion-final
.\.venv-completion\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_core.py tests/test_runtime.py tests/test_models.py tests/test_experiment.py tests/test_net.py -m "not training and not checkpoint_fixture" --basetemp artifacts/pytest-completion-historical
```

Dacă TEMP implicit nu este scriibil în mediul restricționat, setează TEMP/TMP la un subdirector nou din `artifacts/` înainte de execuție. Nu este necesară instalare globală.

Markerii `training` și `checkpoint_fixture` păstrează testele istorice care fac optimizare sau generează checkpointuri sintetice. Au fost separate de selecția sigură, nu eliminate pentru a ascunde eșecuri. Ele necesită o execuție explicită autorizată și rezultatele lor nu ar fi metrici DAiSEE. `tests/test_net.py` este acum un instrument manual cu `main` și un test de import offline, fără model/imagine descărcate la colectare. Succesul offscreen nu înseamnă acceptare manuală a camerelor sau a interfeței pe Windows.
