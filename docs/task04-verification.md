# Verificarea taskului 04 — 15 octombrie 2026

## Medii și instalare

Instalarea editable a fost executată în `.venv`, apoi într-un mediu nou `.venv-template` fără system-site-packages. Nu s-au instalat pachete global. Nu s-au descărcat dataseturi sau ponderi și nu s-a efectuat antrenare. Instalarea pachetelor NumPy/Qt/testare a fost singura operație de descărcare.

| Element | Mediu existent | Mediu curat verificat |
|---|---|---|
| Python | 3.13.2 | 3.13.2 |
| NumPy | 2.4.2 | 2.5.4 |
| PySide6 / Qt | 6.12.0 | 6.12.0 |
| pytest | 9.1.1 | 9.1.1 |
| pytest-qt | 4.5.0 | 4.5.0 |
| torch / cv2 / sklearn / PyQt5 | Disponibile unele pachete istorice | Niciunul instalat |

Python 3.11/3.12 rămâne ținta de compatibilitate a sursei, însă acești interpreteri nu erau disponibili pentru verificare. Nu este furnizat un lockfile nou pretins testat. `requirements-lock.txt` rămâne snapshotul anterior.

Prima instalare editable în sandbox a întâlnit permisiuni insuficiente în folderul temporar implicit. TEMP/TMP au fost mutate pentru comanda de instalare într-un folder local `artifacts/tmp`, după care instalarea a reușit. Mediul curat a fost creat fără ensurepip, iar instalarea a folosit pip-ul existent cu `--python .venv-template`; niciun pachet nou nu a fost instalat în Python-ul global.

## Rezultate executate

- `python -m pytest -q --basetemp artifacts/pytest-task04-clean`, folosind `.venv-template/Scripts/python.exe`: **27 passed in 15.91s**.
- Exemplul P1: rezultat determinist, is_demo=True, fără Qt/cv2/torch la import.
- Exemplul P2: două surse, patru rezultate simulate, oprire controlată și proces încheiat.
- Intrările `--ui-demo` și `--demo`: pornire, rezultat și închidere în subprocess, cu importurile opționale explicit blocate în test.
- Fără flag demo: ajutor, mesajul modelului real neconfigurat și niciun import Qt.
- Sintaxă verificată pentru surse și scripturi prin compileall.
- Cele trei notebookuri-schelet: JSON valid, celule Python compilabile, execution_count=None, outputs goale. Nu au fost rulate în Colab.
- Cele cinci fișiere din `docs/planning` sunt identice octet cu octet cu documentele furnizate. Checklisturile nu au fost bifate.
- `git diff --check`: fără erori.

Acoperire: validarea mesajelor și configurației, copii stabile ale imaginilor, FakePredictor, lipsa fallback-ului real→fake, selectarea temporală, înlocuirea cererii în așteptare, alternarea surselor, invalidare după stop/restart/remove, erori fără niveluri, istoric fără duplicate, CSV, fabrica predictorului apelată o dată în firul AI și închiderea în timpul unui calcul.

Testele anterioare `tests/test_*.py` au fost păstrate cu importuri de compatibilitate, dar **nu au fost rerulate** în taskul 04. Nicio afirmație anterioară despre 19 teste nu descrie această execuție nouă.

## Interfață și limite

Testele Qt sunt **offscreen**. Captura `artifacts/task04-demo.png` a fost generată și inspectată: banner permanent de simulare, dreptunghi sintetic fără oameni, interval separat și rând de istoric marcat. Aceasta nu echivalează cu verificare vizuală manuală pe desktopul Windows; testarea manuală a redimensionării, fonturilor, focusului și butoanelor rămâne de făcut pe laptopul de prezentare.

Nu s-au activat camere sau fluxuri reale. Noile puncte de integrare reale ridică NotImplementedError. Nu există evaluare AI sau metrici de clasificare în această livrare. Interfața este intenționat mică: un participant sintetic, fără formular complet/grilă/dialog CSV.

Oprirea este cooperativă. Un predictor extern care se blochează definitiv nu poate fi întrerupt forțat prin acest schelet; integrarea reală trebuie să garanteze durate finite. Exemplele și testele folosesc predictor determinist și timeouturi, fără terminate().
