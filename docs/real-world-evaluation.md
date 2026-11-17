# Etapa 8 — evaluare experimentală locală

Acest flux evaluează fiabilitatea geometriei și a evenimentelor. Nu clasifică atenția, emoțiile sau implicarea și nu identifică persoane. Nu există rezultate experimentale pe persoane furnizate pentru această etapă. Testele sintetice și videoclipurile fără fețe verifică funcționarea programului, nu acuratețea pe oameni.

## Separarea sesiunilor

| ID / rol | Utilizare permisă | Rezultate |
|---|---|---|
| C01 / `calibration` | Referințe neutre și praguri EAR individuale | Profil `CalibrationManager`, CSV și condiții |
| D01 / `development` | Alegerea parametrilor, verificarea sincronizării și ajustări | Măsurători, adnotări, rapoarte exploratorii |
| V01 / `validation` | Evaluarea finală a configurației deja fixate | Măsurători independente, adnotări și raport final |

Pentru alte experimente folosește C02/D02/V02 etc. Identificatorii canonici nu pot primi alt rol. ID-urile istorice descriptive rămân compatibile; responsabilul experimentului trebuie să păstreze corespondența corectă a rolurilor. C01 nu poate fi evaluată ca validare, iar V01 nu poate fi sursă pentru calibrare sau înghețarea parametrilor.

`experimental_session.py` reutilizează `DashboardSession` și `SessionStore`. Snapshotul conține `manifest.json`, măsurători, opțional evenimente automate, referințe manuale/geometrice și profilul importat. Manifestul include ID anonim, dată ISO, rol, configurație, durata observată, condiții, proveniență și pachetul înghețat. Durata este diferența dintre primul și ultimul timestamp măsurat, nu durata nominală a videoclipului. Videoclipul rămâne o referință externă, fără copie automată.

## Pregătirea colectării

1. Obține autorizarea și consimțământul adecvat înainte de înregistrare, inclusiv cerințele instituției și ale reprezentantului legal pentru minori. Păstrează documentele de consimțământ separat de datele tehnice.
2. Folosește un cod de sesiune, directoare și etichete fără nume, email, școală sau alte identificatoare. Aplicația nu cere date demografice și nu colectează identificatori ai persoanei.
3. Fixează camera, rezoluția, rata cadrelor, distanța aproximativă, poziția țintelor și iluminarea. Notează condițiile prin etichete anonime (de exemplu `camera_A_720p_30fps`, `light_normal`, `glasses`). Nu inventa valori de lux sau unghiuri fără instrumente de măsurare.
4. Înregistrează separat C, D și V. Recomandarea pentru adnotare reproductibilă este un videoclip local autorizat cu timpi media; păstrează un singur original per sesiune. Scriptul de analiză a webcamului nu salvează automat un videoclip brut.
5. Notează versiunea protocolului, metoda și incertitudinea referințelor, ordinea scenariilor, eventualele abateri și momentul începerii. Condițiile pot avea etichete suplimentare în CSV; observațiile descriptive nu devin unghiuri de referință.

Dashboardul nu pornește camera sau inferența. Captura se pornește numai prin comanda explicită a operatorului; fereastra de webcam trebuie să fie vizibilă. Nu folosi fluxul pentru monitorizare ascunsă.

## Protocol repetabil

Exemplu de secvență de 180 s pentru D/V; repetă de cel puțin două ori și stabilește ordinea înainte de V. Timpii de mai jos sunt planificați: în raport intră limitele observate, aliniate la timestampurile CSV ale fiecărei sesiuni.

| Interval planificat | Scenariu | Condiție și observații |
|---|---|---|
| 0–15 s | Poziție neutră | Cap comod, țintă centrală fixă, clipiri permise |
| 15–35 s | Cap stânga / centru / dreapta / centru | Mișcare lentă, pauze de aproximativ 5 s; stânga/dreapta subiectului |
| 35–55 s | Cap sus / centru / jos / centru | Mișcare comodă, aceleași pauze |
| 55–85 s | Ținte de privire | Centru, stânga, dreapta, sus, jos, centru; cap aproximativ stabil |
| 85–115 s | Clipiri naturale | Fără cerință de număr sau frecvență; ambele pleoape adnotate separat |
| 115–135 s | Pierdere și revenire față | Ieșire voluntară din cadru, revenire neutră; adnotează limitele observabile |
| 135–165 s | Iluminare controlată | Normală / mai redusă / revenire; fără lumină disconfortabilă sau intermitentă |
| 165–180 s | Revenire neutră | Verificarea repetabilității geometriei |

Instrucțiunea „întoarce capul spre stânga” este o categorie, nu o referință de −30°. Țintele de privire indică sarcina cerută, nu confirmă punctul efectiv fixat. MAE/RMSE în grade necesită o măsurare independentă a orientării, sincronizată și în același reper/convenție ca predicția. Nu folosi ieșirea MediaPipe drept propria referință.

C01 include suplimentar fotografii neutre clare și două secvențe scurte: ochi deschiși și ochi închiși confortabil. Extrage doar intervalele verificate în două fișiere de calibrare, cu minimum cinci măsurători valide per ochi. Repetă calibrarea dacă distribuțiile EAR nu sunt separabile. Mai multe fotografii neutre verifică consistența eșantioanelor; profilul nu pretinde automat stabilitate temporală.

## Comenzi C01 → D01 → V01

Rulează în PowerShell din rădăcina repository-ului, cu mediul local existent. Modelul `models/face_landmarker.task` trebuie să fie disponibil local; aceste comenzi nu descarcă și nu antrenează modele. Căile cu spații se pun între ghilimele. Toate ieșirile trebuie să fie noi; pentru reluări schimbă numele, fără să suprascrii experimentul original.

```powershell
$py = ".\.venv-completion\Scripts\python.exe"
$env:PYTHONUTF8 = "1"
New-Item -ItemType Directory -Force data\evaluation | Out-Null
```

### C01 — calibrare individuală

`data/C01_open.mp4`, `data/C01_closed.mp4` și fotografiile neutre sunt materiale autorizate din aceeași sesiune C01. Nu sunt incluse în repository.

```powershell
& $py run_video_analysis.py --source "data/C01_open.mp4" --session-id C01 --role calibration --output-csv data/evaluation/C01_open.csv --no-display
& $py run_video_analysis.py --source "data/C01_closed.mp4" --session-id C01 --role calibration --output-csv data/evaluation/C01_closed.csv --no-display
& $py calibrate_session.py --session-id C01 --neutral-image "data/C01_neutral_1.jpg" "data/C01_neutral_2.jpg" --open-measurements data/evaluation/C01_open.csv --closed-measurements data/evaluation/C01_closed.csv --raw-source "data/C01_open.mp4" --raw-source "data/C01_closed.mp4" --output data/evaluation/C01_profile.json
$cSession = & $py experimental_session.py create --measurements data/evaluation/C01_open.csv --id C01 --role calibration --video "data/C01_open.mp4"
if ($LASTEXITCODE -ne 0) { throw "Crearea C01 a eșuat" }
```

Deschide folderul indicat de `$cSession` în dashboard. Prin „Import calibrare” asociază profilul C01, apoi salvează explicit un snapshot nou. CSV-ul ochilor închiși rămâne în `data/evaluation`, iar profilul păstrează parametrii și rezumatul eșantioanelor. Păstrează toate aceste rezultate în registrul local al experimentului.

### D01 — dezvoltare și fixarea configurației

```powershell
& $py run_video_analysis.py --source "data/D01.mp4" --session-id D01 --role development --calibration data/evaluation/C01_profile.json --output-csv data/evaluation/D01.csv --output-blinks-csv data/evaluation/D01_blinks.csv --no-display
$dSession = & $py experimental_session.py create --measurements data/evaluation/D01.csv --id D01 --role development --automatic data/evaluation/D01_blinks.csv --video "data/D01.mp4"
if ($LASTEXITCODE -ne 0) { throw "Crearea D01 a eșuat" }
```

Pe D01 verifică adnotările, acoperirea, erorile și parametrii temporali. Pentru modificări temporale folosește `--temporal-config` la procesare și același fișier la înghețare. Pragurile EAR din profil suprascriu pragurile corespunzătoare ale configurației de bază. Reprocesează D cu configurația aleasă și salvează un nou snapshot înainte de înghețare. Nu inspecta V pentru alegerea parametrilor.

Pregătește `configs/validation.example.json` sau o copie locală cu toleranțele și convențiile stabilite pe D. Dacă profilul are neutralizare, `prediction_head_frame` trebuie să fie `neutral`; referințele unghiulare independente necesită `reference_head_frame=neutral`, convenția `camera_xyz_rzryrx_deg` și același `prediction_neutral_id`/`reference_neutral_id`. Dacă nu ai asemenea referințe, păstrează verificarea lor falsă; MAE/RMSE vor fi N/A. Pentru unghiuri brute folosește profil fără neutralizarea capului și reper `camera`. Deciziile despre convenții și toleranțe se iau înainte de înghețare.

```powershell
& $py experimental_session.py freeze --calibration data/evaluation/C01_profile.json --development-session $dSession --model models/face_landmarker.task --validation-config configs/validation.example.json --config-version protocol-1 --output data/evaluation/frozen-1.json
```

Pentru mai multe sesiuni D repetă `--development-session`. Pachetul include profilul efectiv, parametrii temporali, parametrii de validare, versiunea configurației, SHA256 al modelului, versiunile bibliotecilor și SHA256 al surselor Python plus commitul Git dacă este disponibil. Nu include imagini sau landmarks. Sunt verificate setările efectiv folosite pe D, conținutul măsurătorilor, codul, modelul și mediul.

### V01 — evaluare independentă

```powershell
& $py run_video_analysis.py --source "data/V01.mp4" --session-id V01 --role validation --frozen-plan data/evaluation/frozen-1.json --output-csv data/evaluation/V01.csv --output-blinks-csv data/evaluation/V01_blinks.csv --no-display
$vSession = & $py experimental_session.py create --measurements data/evaluation/V01.csv --id V01 --role validation --automatic data/evaluation/V01_blinks.csv --video "data/V01.mp4" --frozen-plan data/evaluation/frozen-1.json --config configs/experiment_V01.example.json
if ($LASTEXITCODE -ne 0) { throw "Crearea V01 a eșuat" }
```

V refuză suprascrierea profilului/pragurilor, alt cod/model/mediu și reutilizarea aceluiași fișier video D, inclusiv redenumit. Fiecare rulare identificată produce un fișier `<măsurători.csv>.experiment.json` care leagă rezultatele de sesiune. Păstrează sidecarul lângă CSV la importul în dashboard.

După consolidare, reutilizarea exactă a materialelor C cunoscute este refuzată și ea: `--raw-source` și sidecarurile C verificate leagă sursele prin hash. Modelul din C este verificat când există această proveniență. Validarea finală verifică direct rândurile și evenimentele, inclusiv când se apelează API-ul `validation.evaluate`; dacă detectorul a exportat evenimente, furnizează și CSV-ul automat (chiar gol). Profilele istorice fără raw hash păstrează o limitare explicită. Nici această verificare, nici schimbarea numelui fișierului nu demonstrează independența semantică a unui videoclip re-encodat.

După inspectarea rezultatelor V nu mai modifica algoritmul pentru acel raport final. Dacă este necesară o schimbare, declară rezultatul anterior exploratoriu și planifică o nouă sesiune independentă V02 după un nou ciclu C/D. Codul împiedică confuziile accidentale de rol/proveniență, nu poate verifica declarațiile operatorului sau împiedica editarea deliberată a tuturor metadatelor. Pentru webcam nu există hash de înregistrare brută: separarea trebuie verificată în registrul experimental.

## Ground truth și sincronizare

1. Pornește dashboardul și deschide snapshotul ori CSV-ul V01. Importă profilul înghețat pentru CSV; snapshotul V îl conține deja.
2. În „Adnotare video” deschide originalul autorizat, navighează cadru cu cadru și folosește `blink`, `face_absent` sau `condition`. Selectează ochiul din perspectiva subiectului. Marchează începutul și sfârșitul; timestampurile provin din asocierea `frame_index`–CSV, nu dintr-un timp aproximat la mouse. Fără asociere sigură marcarea este refuzată.
3. Pentru clipiri stabilește înainte de adnotare criteriul vizual al debutului și al redeschiderii. Adnotează ambele pleoape separat, inclusiv diferențele reale. Nu transforma durate observate în constante presupuse. Ideal, primul adnotator nu vede predicțiile automate; importă automatul după adnotarea manuală. Un al doilea adnotator verifică independent o parte sau toate datele; documentează dezacordurile și rezoluția lor.
4. „Clipiri și referințe” permite corectarea, aplicarea și exportul `eye,start_ms,end_ms`. „Protocol și condiții” permite corectarea/aplicarea/exportul `kind,label,start_ms,end_ms`. Intervalele condițiilor trebuie să fie în axa temporală a măsurătorilor; se folosesc ca `[start_ms,end_ms)`. Pentru ultimul interval folosește ultimul timestamp disponibil, fără a inventa un eșantion după final.
5. `face_absent` indică absența vizuală a feței, nu o eroare presupusă a modelului. `condition` poate descrie `neutral`, `head_left`, `gaze_target_left`, `light_dim`, condițiile camerei și abateri. Etichetele nu sunt convertite în grade sau coordonate pe ecran.
6. Apasă „Aplică editările manuale” / „Aplică intervalele” înainte de evaluare. Exportă, de exemplu, `data/evaluation/V01_manual.csv` și `data/evaluation/V01_conditions.csv`. Nu copia detecțiile automate în aceste fișiere. Dacă au fost verificate toate cadrele pentru clipiri, setează explicit `blink_reference_complete=true` în configurația contextuală V; altfel rămâne false. Un CSV manual gol înseamnă zero evenimente numai dacă verificarea completă este declarată, nu lipsă de referințe.

Exemplu de structură, cu timpi care trebuie înlocuiți prin observații reale:

```csv
kind,label,start_ms,end_ms
condition,neutral,0,14000
condition,light_dim,14000,24000
face_absent,out_of_frame,24000,27000
```

Condițiile sunt păstrate separat de evenimentele automate. Pot fi adăugate după înghețare, la fel ca disponibilitatea referințelor verificate; nu pot schimba parametrii algoritmului sau toleranțele de evaluare.

## Evaluare și comparație

```powershell
& $py run_validation.py --measurements data/evaluation/V01.csv --detected-blinks data/evaluation/V01_blinks.csv --reference-blinks data/evaluation/V01_manual.csv --conditions data/evaluation/V01_conditions.csv --frozen-plan data/evaluation/frozen-1.json --config configs/experiment_V01.example.json --output-dir reports/V01-final
& $py experimental_session.py compare --session $cSession --session $dSession --session $vSession --output reports/comparison-1.json
& $py run_dashboard.py
```

Comanda de comparație folosește snapshoturile existente la salvare. După adnotare, salvează noul snapshot din dashboard și înlocuiește `$vSession` cu folderul nou pentru a include marcajele. `--reference` la `run_validation.py` acceptă referințe geometrice independente în formatul descris în [calibration-validation.md](calibration-validation.md). Fără referințe nu furniza acest argument. Dacă nu există adnotări manuale complete, poți omite `--reference-blinks`; metricile respective rămân indisponibile.

Rapoartele sunt `report.json` și `metrics.csv`; `--plots` poate exporta grafice atunci când există date unghiulare suficiente. `None`/`null` și celulele CSV goale înseamnă N/A, nu zero. Repetarea evaluării cu aceleași intrări, cod și mediu produce același raport JSON. Păstrează și fișierele manuale și configurația contextuală, nu doar raportul.

În dashboard:

- Deschide C, D și V prin „Deschide sesiune”. „Aplică metadatele” validează ID, rol și data. Nu redenumi V ca D pentru ajustări.
- „Validare și scenarii” importă configurație, referințe și pachetul înghețat, evaluează sesiunea completă și exportă explicit JSON/CSV.
- „Comparație C/D/V” compară sesiunile încărcate: rol, dată, durata observată, acoperirea capului, yaw MAE și F1 stâng, cu trei grafice. N/A nu devine punct zero în grafice. Zona de detalii include configurațiile, proveniența, metricile ambilor ochi, stabilitatea irisurilor, variația unghiurilor, calitatea datelor, intervalele lipsă per componentă și scenariile cu acoperirea cea mai slabă sau cele mai multe erori disponibile. Graficele folosesc indexul sesiunii din tabel. Derulează pentru restul graficelor.
- „Grafice” și „Calitatea datelor” arată evoluția temporală, discontinuitățile și datele indisponibile. Comparația sesiunilor nu este un test statistic de diferență între persoane.

Metricile au următoarele limite:

| Metrică | Condiții de interpretare |
|---|---|
| Detection coverage / lipsă date | Proporții pe eșantioanele efectiv procesate; lipsa timestampurilor este raportată separat. Nu este recall al detecției feței fără referință independentă de prezență. |
| Absență manuală | Numărul cadrelor adnotate, starea feței cunoscută și detecțiile neașteptate în aceste intervale. Stare necunoscută rămâne N/A. |
| Precision / Recall / F1 clipiri | Referințe complete, evenimente întregi în intervale EAR valide, potrivire cu toleranța fixată. Per ochi; P/R/F1 nedefinite rămân N/A. |
| Erori temporale clipiri | Diferențe de debut, sfârșit și durată pentru perechile potrivite; cuantizarea la cadre limitează precizia. |
| Performanță pe scenariu | Aceleași reguli pe subinterval; evenimentele care traversează limita sunt excluse și numărate separat. Intervalele fără EAR nu devin zero erori. |
| Variație unghiulară / stabilitate iris | Dispersie descriptivă pe date valide, nu eroare față de adevăr și nu dovadă de atenție. |
| MAE / RMSE unghiuri | Numai referințe independente verificate și compatibile, sincronizate; instrucțiunile verbale nu sunt suficiente. |

Ferestrele fără date și întreruperile nu sunt interpolate în valori „bune”. Intervalele EAR conservatoare exclud clipirile neobservabile; raportează și evenimentele excluse și acoperirea, deoarece F1 pe o porțiune observabilă poate ascunde dificultățile de detecție.

## Reproducibilitate, păstrare și eliminare

Păstrează local modelul exact, sursele Python din rulare, mediul virtual sau lista versiunilor, configurația înghețată, profilul C, CSV-urile și sidecarurile, referințele și registrul experimental. SHA256 identifică fișierele, nu constituie o semnătură de autenticitate. Pachetul verifică întregul cod Python din `src/` și scripturile Python din rădăcină: o modificare de UI poate invalida și ea un pachet vechi. Revino la versiunea fixată sau efectuează un nou ciclu D/V, nu edita hashurile pentru a trece verificarea.

Nu se face upload sau recunoaștere facială. Snapshoturile omit implicit căile locale externe ale CSV/video și păstrează checksumul măsurătorilor; reatașarea video se face explicit. Numai opt-in-ul `--include-external-paths` păstrează acele căi. Folosește directoare/etichete anonime și revizuiește manifestele înainte de partajare. Videoclipurile, fotografiile, profilurile și măsurătorile rămân date sensibile chiar dacă ID-ul este anonim. Folderul `data/`, `artifacts/`, `reports/`, rezultatele și modelele sunt excluse din Git conform regulilor existente; verifică și numele căilor personalizate înainte de versionare.

„Elimină sesiune” cere confirmare și șterge numai copiile CSV/JSON gestionate din folderul UUID validat, fără a urmări legături sau a șterge video extern. O sesiune externă poate fi doar scoasă din memorie. Originalele, profilele, pachetele, rapoartele și exporturile separate se elimină explicit de către operator conform termenului stabilit; ștergerea snapshotului nu înseamnă ștergerea tuturor copiilor. Aplicația nu implementează criptare sau ștergere securizată a discului.

## Verificări software și acceptare manuală

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
& $py -m pytest -q --basetemp artifacts/pytest-stage8-final
Remove-Item Env:QT_QPA_PLATFORM
& $py run_dashboard.py
```

Selecția implicită pytest include contractele, P1/P2/P3 și testele terminalului. Testele istorice `tests/test_*.py` rămân excluse conform configurației repository-ului și nu sunt declarate reexecutate. Testele Etapei 8 folosesc date sintetice/mocks și verifică rolurile, integritatea configurației/provenienței, separarea surselor, sincronizarea intervalelor, lipsa datelor, reproducibilitatea raportului și integrarea Qt. Nu necesită camere, persoane, rețea sau descărcări.

Înainte de acceptarea experimentală verifică manual:

- Consimțământul, separarea materialelor C/D/V și îndeplinirea protocolului.
- Sincronizarea câtorva cadre la început/mijloc/final, eventualele cadre pierdute și convențiile stânga/dreapta.
- Limitele clipirilor și ale absenței, independența adnotărilor și dezacordul dintre adnotatori.
- Condițiile reale de iluminare, ocluziile, ochelarii, mișcările rapide și disponibilitatea irisurilor la ochi parțial închiși.
- Lizibilitatea dashboardului pe monitorul Windows, deschiderea videoclipului real, salvarea/reîncărcarea/exportul și eliminarea numai a unei sesiuni de probă.
- Existența măsurătorilor unghiulare independente înainte de interpretarea erorilor în grade.

Etapa următoare recomandată este colectarea autorizată a unui pilot C/D/V, raportarea pe scenarii împreună cu acoperirea și incertitudinea adnotării, apoi repetarea pe sesiuni independente. Stabilește criteriile de acceptare înainte de V. Extinderea la alți participanți necesită un protocol separat și validarea generalizării; aceste rezultate nu justifică încă indicatori de atenție.

## Istoric — verificarea Etapei 8 înaintea consolidării

Rezultatele de mai jos aparțin versiunii anterioare. Planurile înghețate istorice nu sunt reutilizabile după modificarea codului. Verificarea consolidării și limitările actuale sunt în [bilanțul ramurii](artiom-branch-completion.md).

- Comanda executată: `.\.venv\Scripts\python.exe -m pytest -q --basetemp artifacts/pytest-stage8-verified`, cu `QT_QPA_PLATFORM=offscreen` și `PYTHONUTF8=1`: **223 passed in 36.22s**. Cele 200 de teste ale selecției configurate au fost verificate și înaintea extinderii; testele istorice excluse nu au fost reexecutate.
- Testele specifice validării și Etapei 8: **47 passed in 16.51s** înaintea rulării complete, inclusiv limitele scenariilor și datele EAR indisponibile.
- Modelul MediaPipe local a procesat două videoclipuri tehnice fără persoane, distincte ca fișier: D cu 20 cadre și V cu 10 cadre, ambele cu zero fețe și zero erori. Profilul C folosit în acest smoke test conține exclusiv valori EAR sintetice; nu este calibrarea unui participant.
- Pachetul `artifacts/stage8-checked-frozen.json`, sidecarurile și snapshotul V au trecut verificările de proveniență. Două evaluări CLI cu aceleași condiții tehnice au produs rapoarte JSON identice (SHA256 `c34091a0078e5f00d91364a0ac0dad5d78a634ae9d13d76d68b89d5d5eaf4790`). MAE și metricile clipirilor au rămas indisponibile. Absența feței din imaginile uniforme a fost verificată numai ca proprietate a acestui material tehnic.
- Panoul Qt C/D/V a fost randat offscreen și inspectat în `artifacts/stage8-comparison-final.png`; valorile fără referințe apar N/A. Aceasta nu înlocuiește acceptarea manuală cu videoclipuri reale pe calculatorul operatorului.
- `git diff --check` a trecut. Nu s-au descărcat date sau ponderi și nu s-au efectuat commit/push. Artefactele tehnice sunt ignorate de Git și pot fi șterse separat de operator.
