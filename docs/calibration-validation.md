# Etapa 6 — calibrare și validare experimentală

## Module și date păstrate

`calibration.py` coordonează `HeadPoseEstimator`, `EyeFeaturesEstimator` și `BlinkThresholds`. Nu dublează detecția sau geometria. Metodele publice noi din estimatori permit exportul și încărcarea referințelor. Profilul JSON versionat păstrează numai rotația neutră, baseline EAR/iris, pragurile individuale, identificatorii sesiunilor și sumarul calității. Nu conține imagini, landmarks, translație facială sau identificare.

`validation.py` citește CSV-urile etapei 4 și marcajele de referință, calculează calitatea și metricile compatibile, apoi exportă JSON/CSV și, opțional, un grafic PNG. Reutilizează `compare_blinks` din etapa 5. `compare_blinks.py` expune acum și F1/TP/FP/FN și erorile temporale. Evaluarea offline nu încarcă modele sau servicii externe.

Fluxul final actual este C01 → D01 → configurație înghețată → V01, descris în [real-world-evaluation.md](real-world-evaluation.md). Exemplele simple de mai jos sunt exploratorii. Pentru proveniența materialelor C adaugă `--raw-source VIDEO_C` (repetabil); imaginile neutre și CSV-urile EAR sunt înregistrate automat prin hash în profil. Câmpul opțional `source_materials` păstrează numai tipul și SHA256, fiind compatibil cu profilele anterioare. Fără materialele C, raportul final menționează limita separării automate.

Sidecarurile CSV C existente sunt verificate: rolul trebuie să fie calibration, ID-ul trebuie să aparțină profilului și măsurătorile să corespundă checksumului. Hashul raw și modelul sunt preluate fără căi. Nu poate fi folosit un CSV V/D relabelat verbal drept C. Fotografiile neutre leagă profilul de modelul `.task` efectiv; amestecarea modelelor sau înghețarea cu alt model este refuzată. CSV-urile istorice fără sidecar rămân utilizabile, dar nu primesc implicit o proveniență verificată.

Guard-ul comun de proveniență este acum apelat și de `validation.evaluate` în modul final: un apel direct cu rânduri/evenimente modificate este refuzat. Dacă rularea a exportat un fișier automat de clipiri, acesta trebuie furnizat și la evaluarea finală, inclusiv când este gol. Nu poate fi omis sau înlocuit neobservat. Referințele manuale rămân independente; nici integritatea datelor, nici un hash nu demonstrează acuratețea estimării ori independența unor clipuri re-encodate.

## Procedura de calibrare

1. Alocă identificatori anonimi pentru sesiuni și înregistrări; separă de la început calibrarea C01 de evaluarea V01. Nu optimiza pragurile pe V01.
2. Înregistrează camera, rezoluția, oglindirea și iluminarea. Colectează fotografii neutre cu ambii ochi deschiși. Multiple observații permit verificarea consistenței; o singură fotografie permite doar o referință geometrică.
3. Pentru EAR, colectează secvențe distinct etichetate de calibrare cu ochi deschiși și închiși, apoi exportă măsurătorile brute prin scriptul video. Fiecare ochi necesită implicit minimum 5 observații valide în fiecare stare. Nu folosi clipiri de test pentru ajustarea pragurilor.
4. Creează explicit profilul:

```powershell
.\.venv\Scripts\python.exe calibrate_session.py --neutral-image "data/validation/calibration/C01/neutral.png" --open-measurements "data/validation/calibration/C01/open.csv" --closed-measurements "data/validation/calibration/C01/closed.csv" --session-id C01 --output "results/calibration_C01.json"
```

Se pot oferi mai multe fotografii după `--neutral-image`, sau se poate omite această opțiune pentru un profil numai cu praguri EAR. Se pot omite ambele CSV-uri EAR pentru un profil numai de geometrie. Repetă `--session-id` pentru toate sesiunile folosite. Profilul trebuie să fie un fișier nou; repetarea calibrării în API înlocuiește referința numai după validare. Pentru altă versiune salvată alege o altă cale.

5. Aplică profilul pe înregistrarea de evaluare:

```powershell
.\.venv\Scripts\python.exe run_video_analysis.py --source "data/validation/validation/V01/video.mp4" --calibration "results/calibration_C01.json" --no-display --output-csv "results/V01_frames.csv" --output-blinks-csv "results/V01_blinks.csv"
```

`--calibration` și `--neutral-image` sunt alternative. Profilul injectează estimatorii existenți și suprascrie pragurile EAR ale ochilor pe care îi calibrează; restul opțiunilor temporale pot proveni din `--temporal-config`.

### Verificările calibrării

Pentru orientarea neutră se extrag rotațiile prin implementarea existentă, se mediază matricile și se proiectează media pe rotații proprii prin SVD. Rotirile relative față de medie trebuie să rămână sub pragul operațional configurabil (implicit 5°). Fiecare ochi necesită EAR pozitiv și iris valid; se verifică variația EAR și dispersia irisului între observații. Praguri operaționale API: `max_ear_cv=.2`, `max_iris_std=.05`, `min_samples=1`. Ele nu reprezintă validare științifică.

Baseline-urile ochilor sunt medianele EAR și pozițiilor irisului. Pentru praguri de clipire, `c=percentila95(EAR_închis)`, `o=percentila5(EAR_deschis)`. Dacă `o<=c`, calibrarea este respinsă; altfel `close=c+.35*(o-c)`, `reopen=c+.65*(o-c)`. Aceste fracții definesc un histerezis în intervalul separat al datelor individuale; nu sunt praguri EAR universale.

Profilul notează numărul observațiilor și consistența lor. Fotografiile nu au timestampuri în această procedură, de aceea `temporal_stability_verified` rămâne fals; consistența dintre fotografii nu demonstrează stabilitate temporală. Referințele invalide, distribuțiile suprapuse, matricile invalide și versiunile de profil incompatibile produc eroare.

## Organizarea setului de validare

Structura este în `validation_dataset/README.md`. Fișierele efective rămân în `data/validation/`, ignorat de Git. Scenarii recomandate: neutru stabil, rotiri stânga/dreapta/sus/jos, clipiri naturale și consecutive, mișcări oculare, iluminare diferită, dispariția/revenirea feței.

Pentru fiecare sesiune păstrează local permisiunea utilizării, identificatorul anonim, ID-ul înregistrării, împărțirea calibration/validation, proveniența și convenția referinței. O instrucțiune verbală „30° la stânga” fără măsurare independentă nu este ground truth în grade.

Referințele geometrice sunt CSV cu `timestamp_ms` și numai coloanele cunoscute dintre `yaw,pitch,roll,left_iris_x,left_iris_y,right_iris_x,right_iris_y,orientation_category`. Necunoscutele sunt celule goale. Marcajele clipirilor folosesc `eye,start_ms,end_ms` și left/right ale subiectului. Timestampurile trebuie să fie în același reper temporal ca măsurătorile; nu estimăm automat offset-ul ceasurilor.

## Configurația validării și separarea datelor

Copiază `configs/validation.example.json` și completează `experiment_id`, `session_id`, `calibration_session_ids` și scenariile reale. Exemplul este exploratoriu (`final_evaluation=false`) și nu declară referințe verificate.

Pentru evaluarea finală folosește `final_evaluation=true` și identifică sesiunile de calibrare. Runnerul poate încărca profilul prin `--calibration` și adaugă automat sesiunile lui la verificări. O sesiune comună calibrare/validare este respinsă. `recording_id`/`calibration_recording_ids` pot preveni reutilizarea explicit declarată a aceleiași înregistrări. Pentru evaluare între persoane setează `cross_person=true`, `training_participants` și `test_participant`; intersecția este respinsă.

Aceste verificări folosesc metadatele declarate. Nu identifică persoanele și nu pot demonstra că același clip nu a fost copiat sau redenumit sub alt ID. Registrul experimentului și separarea materialului original rămân necesare. Nu modifica parametrii după consultarea rezultatelor finale fără să reclasifici sesiunea drept dezvoltare și să alegi alt set final.

## Metrici și formule

### Head pose

Asocierea temporală este unu-la-unu, prin cel mai apropiat timestamp încă neutilizat, în `timestamp_tolerance_ms` (implicit 20 ms). Nu se interpolează și nu se reutilizează un eșantion. Aceasta este o asociere greedy deterministă, nu o sincronizare hardware; rapoartele arată numărul perechilor.

MAE/RMSE necesită:

- referințe numerice și măsurători valide;
- `head_reference_verified=true`, declarat numai pentru o referință independentă;
- `prediction_head_convention=reference_head_convention="camera_xyz_rzryrx_deg"`;
- `prediction_head_frame=reference_head_frame`, camera sau neutral; pentru neutral, aceleași `prediction_neutral_id`/`reference_neutral_id` nenule;
- flagurile de calibrare din CSV, dacă există, să fie compatibile cu aceste declarații.

Eroarea circulară este `e=((pred-ref+180) mod 360)-180`. Pe fiecare axă: `MAE=mean(abs(e))`, `RMSE=sqrt(mean(e²))`, `bias=mean(e)`. Lipsa perechilor sau incompatibilitatea produce `null`, nu zero.

Variația circulară este `1-hypot(mean(sin(a)),mean(cos(a)))`, adimensională. În scenariile declarate `stable_head=true` descrie repetabilitatea orientării stabile; pe un scenariu în mișcare este doar dispersie, nu instabilitate a algoritmului. `stability_samples_sufficient=false` marchează mai puțin de două observații; o variație zero dintr-un singur eșantion nu demonstrează precizie.

Dacă ambele fișiere conțin `orientation_category`, se raportează separat acordul etichetelor furnizate. Nu se transformă etichetele stânga/dreapta/centru în grade și nu se creează un clasificator automat nou.

### Clipiri

Potrivirea reutilizează algoritmul bipartit al etapei 5: maximum de perechi unu-la-unu, același ochi și început/sfârșit în toleranța configurabilă. Preferă local erori mici, fără minimizare globală garantată a erorii totale.

`TP=potriviri`, `FP=detecții neasociate`, `FN=referințe neasociate`. `precision=TP/(TP+FP)`, `recall=TP/(TP+FN)`, `F1=2TP/(2TP+FP+FN)`. Numitorii nuli produc `null`. Pentru perechi se raportează MAE/RMSE/bias ale începutului, sfârșitului și duratei în ms.

În `run_validation.py`, evenimentele sunt evaluate numai dacă sunt integral în intervale cu EAR valid pentru ochiul respectiv, fără gap peste `max_gap_ms`. Evenimentele din afara acoperirii sunt numărate separat ca excluse. Pentru `blink_reference_complete=true`, `FP/min=FP*60000/durata_EAR_validă_ms` și `FP/oră=FP*3600000/durata_EAR_validă_ms`. Această declarație înseamnă că întreaga zonă evaluabilă a fost adnotată, nu că fiecare cadru are o clipire.

Referința incompletă permite inspectarea potrivirilor temporale, dar evaluatorul nu raportează FP/FN, precision/recall/F1 sau alarme false ca metrici finale. Fără acoperire EAR, evaluarea este indisponibilă. Scriptul simplu `compare_blinks.py` păstrează compararea exclusiv a evenimentelor: presupune referința furnizată completă și nu calculează alarme/minut fără durată validă.

### Iris și condiții experimentale

Se raportează media/variația coordonatelor locale pe ochi, fracția validă/invalidă, diferențe ale mediilor scenariilor cu același `repeat_group` și sumar separat pe `lighting` și `head_condition`. Aceste comparații descriptive nu demonstrează o cauză și pot reflecta simultan mișcarea reală și eroarea algoritmului.

Erorile numerice ale irisului necesită `iris_reference_verified=true`, convenția `iris_local_normalized` și perechi valide în același reper local. Se calculează MAE/RMSE/bias pe coordonate; nu sunt erori ale punctului privit pe ecran. Scenariile sunt intervale `[start_ms,end_ms)`, cu `name`, opțional `repeat_group`, `lighting`, `head_condition`, `stable_head`. Valorile acestor câmpuri provin din protocol, nu sunt inferate din imagine.

### Calitatea datelor

Raportul include numărul total, cadre cu față (sau `null` dacă flagul lipsește), cadre cu toate măsurătorile, proporții valide/invalide pe componentă, intervalele eșantioanelor lipsă, gapurile timestampurilor și ultima valoare `processing_fps` exportată de procesor. Validarea offline nu măsoară din nou FPS-ul inferenței și nu confundă FPS-ul sursei cu viteza de procesare.

Durata validă însumează numai segmentele dintre observații consecutive valide, cu gap cel mult configurat. Nu extrapolează înainte/după eșantioane. Intervalele lipsă raportează primul/ultimul eșantion invalid, fără a inventa durata fizică a dispariției dintre cadre. Mediile și variațiile sunt pe eșantioane, nu ponderate cu durata.

## Rulare și rapoarte

```powershell
# calitate și dispersie, fără a inventa metrici de precizie
.\.venv\Scripts\python.exe run_validation.py --measurements "results/V01_frames.csv" --config "configs/validation.example.json" --output-dir "results/V01_quality"

# evaluare cu referințe și profilul folosit
.\.venv\Scripts\python.exe run_validation.py --measurements "results/V01_frames.csv" --reference "data/validation/references/V01/geometry.csv" --detected-blinks "results/V01_blinks.csv" --reference-blinks "data/validation/references/V01/blinks.csv" --config "configs/validation_V01.json" --calibration "results/calibration_C01.json" --output-dir "results/V01_report" --plots
```

Directorul de raport trebuie să fie nou. `report.json` conține experimentul, configurația efectivă, calitatea, metricile disponibile, scenariile și limitările. `metrics.csv` este o versiune aplatizată, cu nume ierarhice și valori lipsă distincte de zero. `--plots` poate produce `head_mae.png` cu Matplotlib dacă fiecare axă reprezentată are cel puțin două perechi și MAE calculabil; altfel nu se fabrică un grafic. Datele originale nu se suprascriu.

## Confidențialitate și limite

Se folosesc numai înregistrări autorizate, local. Nu există încărcare în cloud sau identificare. Păstrează video/fotografii/referințe în `data/`, profilele și rapoartele în `results/` sau `artifacts/`, conform regulilor `.gitignore`. Ștergerea se face explicit asupra sesiunii alese, după verificarea căii și a politicii de păstrare; instrumentele nu șterg automat originalele și nu extind colectarea.

Profilele sunt referințe geometrice experimentale, nu dovezi de identitate sau calibrare fizică validată. O referință manuală poate avea eroare; toleranțele trebuie fixate înaintea testului. Nu există validare clinică, benchmark DAiSEE sau concluzii despre emoții/atenție în această etapă. Pentru generalizare sunt necesare sesiuni, condiții și, când se afirmă generalizare între persoane, participanți separați.

## Verificări efectuate

- `.\.venv\Scripts\python.exe -m pytest -q --basetemp artifacts\pytest-stage6-acceptance`: **176 passed** în selecția implicită completă, cu 33 cazuri noi față de etapa 5. Testele istorice `tests/test_*.py` au rămas în afara selecției și nu sunt declarate reexecutate.
- Calibrare sintetică: geometrie neutră, agregare și respingerea instabilității, referințe EAR separate, date invalide, repetare atomică, profil JSON și încărcare, configurarea estimatorilor existenți și CLI-ul EAR.
- Evaluare sintetică: MAE/RMSE, periodicitate, convenții incompatibile, categorii separate, TP/FP/FN/F1, erori temporale/durată, rate nedefinite, referință parțială, excluderea intervalelor fără EAR, timestampuri invalide și marcaje duplicate, rapoarte JSON/CSV și PNG.
- Scenariul numeric verificat: erori yaw de 2° și 4° produc MAE **3°** și RMSE **sqrt(10)≈3.1623°**. Perechea roll 179°/−179° produce eroare absolută **2°**, nu 358°. Aceste valori provin din matrice/serii sintetice cunoscute, nu dintr-un experiment pe persoane.
- Testul clipirilor cu TP=1, FP=1, FN=1 produce precision=recall=F1=0.5; testul cu referință parțială păstrează potrivirile și suprimă metricile finale incompatibile cu acoperirea.
- `head_mae.png` generat din referințe sintetice a fost inspectat vizual. Nu s-a produs un grafic de precizie pentru datele fără referințe.
- Comandă offline executată pe măsurătorile reale ale clipului sintetic gol din etapa 4:

```powershell
.\.venv\Scripts\python.exe run_validation.py --measurements artifacts\stage4-smoke-final.csv --config configs\validation.example.json --output-dir artifacts\stage6-blank-report
```

Rezultat: 20 măsurători, 0 cadre cu față, 0 perechi de referință; MAE yaw și evaluarea clipirilor sunt indisponibile (`null`). `report.json` și `metrics.csv` au fost generate și inspectate. Nu a fost disponibilă o înregistrare autorizată cu persoane și referințe independente; fiabilitatea experimentală reală rămâne de măsurat, nu este dedusă din testele sintetice.
