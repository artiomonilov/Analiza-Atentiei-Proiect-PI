# Integrarea Artiom / Ilie — procesare facială în motorul P2

## Starea inițială și arhitectura înainte de modificări

19 noiembrie 2026. Lucrările se desfășoară exclusiv în worktree-ul
`C:/Users/artio/Desktop/AnalizaAtentiei/AnalizaAtentiei-integration`, pe
`integration/artiom-ilie-video`. Worktree-ul fusese mutat din directorul vecin;
înregistrarea sa Git a fost reparată fără mutarea sau ștergerea fișierelor.

Baza Artiom: `c69808ed7fb71a9972ff1a104f1b6a250301c4cb` (include
`51597bc5d45eb52085eeb25e6f8f9c0af442e426`). Merge-ul Ilie era deja în curs,
cu `MERGE_HEAD=58d8a91a518c06e2585847b3cf2828fde53def5b`, 13 căi staged și
zero conflicte nerezolvate. Branchurile originale nu sunt modificate.

Fluxul inițial P2: `FileSource/LiveSource -> SourceWorker(QThread) -> YuNet ->
FaceTracker -> SequenceBuilder per track -> LatestScheduler -> un singur
InferenceWorker -> ResultGate -> UI`. PreviewStore păstrează ultimul cadru.
Fișierele folosesc index/FPS; live folosește monotonic și retry. Calculele
MediaPipe/head/eye/temporal există separat în VideoProcessor și nu sunt încă
apelate din SourceWorker. UI moștenită din Ilie include Ema la `86e5a90`, nu
ultimele schimbări `3072d65`; nu se adaugă din nou branchul Ema.

Probleme reverificate înainte de modificări: complete fără run_id, mailboxuri
fără limită totală, matching înainte de expirarea trackurilor, istoric insuficient
pentru ferestre lungi și cleanup live incomplet. Prima încercare pytest a folosit
un basetemp al cărui părinte nu exista: 107 erori de fixture, 6 failures și 179
passed. Aceasta nu oferă un baseline valid; rularea corectă, cu TEMP/TMP și
părintele artifacts pregătite, a dat 291 passed, 1 failed, 3 deselected.
Eșecul precis era așteptarea de stub rămasă în test_real_adapters_are_explicit.

## Implementare și verificare

**Integrarea software este implementată și verificată în working tree: 316
teste trecute, 3 deselectate explicit, 0 failures, 0 skips. Finalizarea
istoricului Git este blocată de revizuirea automată a permisiunilor, explicată
în secțiunea Git. Nu se declară merge-ul comis.**

Nicio predicție de angajament nu este fabricată. Nu s-au antrenat sau descărcat
modele/date. Modelul MediaPipe local și dependențele existente sunt reutilizate.
Nu s-a făcut push, merge în main sau modificare a branchurilor originale.

## Arhitectura după integrare

```text
P2 FileSource / LiveSource + FrameClock
  -> SourceWorker, o captură per sursă/run
  -> YuNet, FaceTracker, FramePacket imuabil cu timp și epoch
     -> PreviewStore: ultimul cadru către UI
     -> FacialAnalysisSession: un MediaPipe VIDEO per sursă/run
        -> asociere geometrică unică cu trackul YuNet
        -> HeadPose + EyeFeatures din același rezultat, pe cadrul întreg
        -> TemporalAnalyzer + profil individual
        -> FacialCSVExport comun -> CSV, summary JSON și receipt
        -> FeatureStore -> geometry_ready / take_latest_features
     -> separat: crop -> SequenceBuilder -> LatestScheduler
        -> un InferenceWorker P1 -> ResultGate -> result_ready
Export geometric -> DashboardSession / dashboard existent -> validation
```

FacialAnalysisSession nu construiește VideoCapture și nu cheamă
VideoProcessor.run. Sunt reutilizate FaceLandmarker, HeadPoseEstimator,
EyeFeaturesEstimator, TemporalAnalyzer, CalibrationManager, FrameClock,
VideoMeasurement, measurement, temporal_csv_row, FrozenExperiment și motorul
de validare existente. Exportorul comun este folosit și de procesorul original.
Inferența și exportul rulează în SourceWorker, fără calcule AI în widgeturi.

## Fișiere create și modificate

Fișiere noi ale integrării:

| Fișier | Rol |
|---|---|
| src/audience_analysis/engine/facial.py | Configurație și sesiune per run, MediaPipe reutilizat, asociere, calibrare, temporal și proveniență |
| src/audience_analysis/facial_features.py | DTO geometric separat de predicțiile P1 |
| src/audience_analysis/facial_export.py | Writer CSV incremental comun cu VideoProcessor |
| src/audience_analysis/engine/cli.py | Comanda efectivă P2 + geometrie, fără Fake implicit |
| tests/engine/test_facial_integration.py | 24 de cazuri noi, inclusiv parametrizări și fixture-uri sintetice explicite |
| docs/artiom-ilie-integration.md | Raportul și comenzile acestei livrări |

Modificări proprii față de indexul merge-ului pregătit:

- contracts.py: timestamp_source/capture_epoch opționale la sfârșitul FramePacket;
  API-urile PreparedSequence/ModelOutput/PredictionResult rămân compatibile.
- engine/controller.py: injecție geometry_factory și reader_factory, notificări
  bounded, restart amânat până la închiderea workerului anterior, run_finished.
- engine/workers.py: analiză pe cadrul P2, închiderea sesiunii/exportului înainte
  de EOF, reseturi, stări comasate, oprire inclusiv în inițializarea modelului.
- engine/scheduler.py: chei source/run/request, bugete și confirmarea livrării;
  engine/stats.py: ignorarea rezultatelor altui run și eliminarea contoarelor.
- video/sources.py: FrameClock, metadata/fallback, owner/release live și rezervări;
  video/tracking.py: expirare înainte de matching și limită de trackuri;
  video/sequences.py: istoric temporal dimensionat și subeșantionare bounded.
- video_processor.py: reutilizarea FacialCSVExport, fără a schimba algoritmii
  matematici; experimental.py: pipeline_parameters opțional și verificări comune;
  run_video_analysis.py: refuză executarea unui plan P2 prin procesorul separat.
- dashboard_data.py: curbele/variația se întrerup la schimbarea source/run/epoch/
  track; datele live nu sunt asociate arbitrar unui fișier de adnotare.
- pyproject.toml: entry point audience-p2-video. README, docs/contracts.md și
  README-urile engine/video documentează noul flux.
- tests/engine/test_scheduler.py: confirmări explicite în testele consumatorului
  unic; tests/video/test_preparation.py: testul de stub înlocuit prin verificarea
  erorii reale, detector injectat și constructorul de secvențe implementat.

Cele 13 fișiere incoming Ilie sunt păstrate în indexul merge-ului. Fișierele
ui/history.py și ui/main_window.py provin din Ilie; suplimentar au fost eliminate
numai trei spații finale din MainWindow. `git diff --ignore-space-at-eol
origin/ilie-p2 -- src/audience_analysis/ui/main_window.py
src/audience_analysis/ui/history.py` nu arată schimbări funcționale proprii P3.
Lista exactă completă este și în inventarul snapshotului local de conservare.

## Contracte, timestampuri și selecția feței

FacialFeatureResult conține source_id/run_id/frame_index/timestamp_ms/track_id
opțional/capture_epoch, VideoMeasurement, TemporalUpdate, calibration_status și
association_status. `to_dict()` adaugă schema_version=1, availability și unități.
Nu include ModelOutput.levels. None este null în JSON și celulă goală în CSV.
Trackul este un număr temporar, nu identitate biometrică.

Unghiurile sunt grade în convenția existentă Rz(roll)Ry(yaw)Rx(pitch); EAR este
adimensional, iar irisul este normalizat în regiunea ochiului. Head pose/ochii
folosesc rezultatul aceleiași inferențe MediaPipe pe cadrul întreg, astfel încât
profilul neutru nu este reinterpretat în coordonatele unui crop.

Fără --track-id se acceptă numai o singură față YuNet și o asociere unică cu
reperele MediaPipe: centrul bounding box-ului landmarkurilor în caseta YuNet și
minimum 50% din aria acelui box suprapusă. Cu --track-id se verifică același
criteriu pentru ținta cerută. Mai mulți candidați, lipsa corespondenței sau
geometria degenerată produc indisponibilitate, nu combinarea unor persoane.
Asocierea 2D nu este recunoaștere și poate eșua în ocluzii sau fețe suprapuse.

La track nou/reconnect se resetează temporalul. Dacă profilul sau pragurile
individuale erau deja legate de o țintă, schimbarea trackului/epochului produce
calibration_target_lost și valori indisponibile până la un nou run confirmat de
operator. Profilul nu se transferă automat. Fără calibrare, revenirea unei fețe
permite măsurători brute pe noul track, cu istoric temporal nou.

Fișierele folosesc POS_MSEC valid, apoi FPS declarat, apoi estimare 30 FPS,
cu etichetarea fallbackului și strict_order când trebuie corectată ordinea.
Nu se presupune FPS constant dacă decoderul furnizează timpi variați. Webcam/
network folosesc monotonic relativ la run, cu epoch nou la reconnect. Timpul
de inferență și processing_fps sunt măsurători de procesare separate. processing_fps
din adaptor include inițializarea sesiunii; nu este așteptat să fie identic cu
cel din procesorul vechi, care pornea cronometrul după inițializare.

Pentru live, frame_index este indexul cadrelor livrate de reader, nu al unei
înregistrări independente. Dashboardul cere o mapare independentă pentru acel
caz și refuză navigarea automată nesigură; graficele rămân utilizabile.

## Corecții P2 separate pentru review-ul lui Ilie

| Problemă | Corecție implementată / dovadă |
|---|---|
| R03, completion cross-run | complete cere run_id și confirmă numai cererea efectiv preluată; un old-run nu șterge outstanding-ul nou |
| R04, mailboxuri nelimitate | Implicit 1 pending/sursă, 16 global, 16 surse; un singur rezultat AI neconfirmat către controller; fairness pe surse |
| Cereri/Qt backlog | Latest pentru preview/geometrie/stări, maximum o notificare per sursă; CSV complet scris în worker; rezultatele AI așteaptă ack înainte de următoarea preluare |
| R05, tracking | Expirare înainte de matching, maximum 32 trackuri reținute, 8 fețe vizibile; anularea cererilor trackurilor încheiate |
| Ferestre de model lungi | Subeșantionare după toleranță, buget calculat din fereastră și limită 4096; 10 s/30 FPS produce secvențe, în loc de zero cu limita veche 128 |
| R06, timp | FrameClock reutilizat pentru fișiere și strict ms pentru MP; live monotonic și reseturi explicite |
| Cleanup/restart | Workerul nou al aceleiași surse așteaptă închiderea celui vechi; Stop în inițializarea MP nu mai deschide captura ulterior |
| Cleanup live | Release în finally al ownerului, fără release concurent peste read; timeout explicit și rezervare până la eliberare; fără fallback network fără parametrii FFmpeg |
| R07, asociere | Un rezultat MP pe cadrul întreg, verificare unică cu YuNet/track, N/A la ambiguitate; fără atribuirea head/eye altui track |
| Stats/date vechi | Rezultatele din alt run nu incrementează statisticile noi; DTO/preview/stări vechi invalidate; contextul graficelor nu traversează trackuri |
| EOF/export | Închiderea modelului și exportului precede EOF; run_finished raportează și erorile de cleanup/export după Stop |

Un read nativ OpenCV sau un predictor extern care nu revine nu poate fi ucis
în siguranță prin QThread. UI nu execută wait nelimitat, însă shutdown de fișier
poate aștepta acel backend. Live raportează timeout și împiedică redeschiderea
concurentă; nu se pretinde eliberare hardware garantată pentru orice driver.

## Export, dashboard și C/D/V

Fiecare rulare scrie separat în output/source_id/run_id, fără suprascriere:
measurements.csv, temporal.csv, blinks.csv și summary.json. CSV-ul geometric
extinde VideoMeasurement cu source_id/run_id/track_id/capture_epoch/
association_status. Nu salvează imagini, nume afișate sau căi absolute ale
sursei. Callbackurile GUI pot omite cadre intermediare; exportul nu le omite.

Receiptul measurements.csv.experiment.json leagă rezultatele de model, cod,
mediu, profil, praguri, sursă și pipeline_parameters: P2, politica de asociere,
track selectat, hash YuNet și clock. Sursa/modelul/codul/mediul sunt reverificate
la close; o modificare împiedică scrierea provenienței. Pipeline-ul final și
receiptul trebuie să corespundă la evaluare, inclusiv prin API direct.

C01 poate alimenta CalibrationManager. D01 folosește profilul și se salvează
prin experimental_session create. freeze reutilizează FrozenExperiment și
include parametrii P2; V01 necesită acel plan și nu permite suprascrierea
profilului/pragurilor. Un V oprit înainte de EOF nu primește receipt final.
run_video_analysis refuză un plan P2, ca procesarea separată să nu pară integrată.
Modelele/planurile vechi nu sunt convertite sau modificate retroactiv.

Dashboardul existent citește exportul, snapshoturile și graficele. read_blinks
citește evenimente automate, separate de referințele manuale. Nu s-a creat
un alt dashboard. MAE/RMSE și P/R/F1 rămân N/A când lipsesc referințele potrivite.

## Teste executate

Pythonul a importat explicit codul din worktree/src, verificat prin
audience_analysis.__file__, nu pachetul instalat al branchului original.
Mediu: Windows/Python 3.13.2, .venv-completion existent, Qt offscreen,
HF/Transformers offline, bytecode/cacheprovider dezactivate și TEMP/TMP locale.
Nu s-au schimbat dependențele acelui mediu și pip check a trecut.

| Selecție | Rezultat executat |
|---|---|
| Baseline corect pregătit, înainte de corecții | 291 passed, 1 failed, 3 deselected in 88.57s; testul stub |
| Regresie inițială engine/video/video_processor/experimental | 67 passed in 40.25s |
| Primele teste noi | Două aserțiuni de test corectate: -0.0 comparat numeric cu 0 și frame_index CSV canonicalizat; apoi 12 passed in 3.25s |
| Suită intermediară | 304 passed, 3 deselected in 86.96s |
| Proveniență/stop și lifecycle noi + controller/scheduler | 24 passed in 13.11s, înaintea ultimelor teste adăugate |
| Acceptare finală | **316 passed, 3 deselected in 78.04s; 0 failed, 0 skipped** |

Rulările se suprapun și nu se însumează. Cele trei deselectate sunt testele
istorice marcate training/checkpoint_fixture; nu au fost eliminate. Selecția
finală include istoricele sigure și testele noi, fără optimizare, checkpoints
sintetice, dataset sau rețea la colectare.

Cele 24 de cazuri noi acoperă: captură reală de fișier sintetic, o captură per
run, o instanță MP mock per run și un apel per cadru, head/eye cu aceeași inferență, calibrare,
temporal și clipiri automate, pierdere/revenire față, no-face/error, asociere,
surse multiple, restart în calcul fără suprapunerea capturilor, Stop în init,
EOF, cozi/ack bounded, expirare, VFR/fallback, export/import/snapshot/dashboard,
MODEL_UNAVAILABLE, schimbarea sursei, freeze/evaluare/guard P2, DTO și refuzul
mapării live nesigure. Mocks/landmarks sintetice nu sunt rezultate reale pe oameni.

Comparația cu VideoProcessor a folosit același fișier sintetic, aceleași
landmarks injectate și aceeași calibrare. Timestampurile, frame_index, unghiurile,
EAR, irisul, gaze_delta și availability au coincis. processing_fps și momentul
notificărilor nu sunt comparate numeric. În producție, asocierea conservatoare,
resetul de track/epoch și blocarea unei calibrări incompatibile pot produce
mai multe valori N/A decât procesorul vechi, care prelua direct prima față MP.

## End-to-end nativ verificat și artifacte

Nu a existat un clip autorizat cu persoane ales pentru verificare. S-au folosit
înregistrările tehnice uniforme preexistente: 20 cadre D și 10 cadre V, fără
fețe, modelul MediaPipe real și detectorul YuNet real. P1 a raportat explicit
MODEL_UNAVAILABLE și geometria a continuat până la EOF. Aceste rulări au folosit
efectiv EngineController și SourceWorker prin engine.cli, nu vechiul script video.

- artifacts/p2-accepted-protocol/: C din semnale EAR sintetice declarate,
  D 20 cadre/20 apeluri MP și V 10 cadre/10 apeluri MP, zero erori și zero fețe.
- frozen.json: SHA256 `81fa3128e1854d2f33c4db5b5d8fed5510473338f9bd53b24a7c4a0b5414bd0d`.
- report-1/report.json și report-2/report.json: identice byte-cu-byte,
  SHA256 `182bc0d88a8256df8ce1784281e69d1506ee1f5e9067d6fd02609236950856ef`.
  Referințe independente 0; MAE/RMSE și evaluarea clipirilor N/A.
- Snapshoturi C/D/V reîncărcate și comparație fără erori. dashboard-comparison.png
  a fost inspectată: trei roluri, grafice lizibile și metrici N/A corecte.
  Aceasta este verificare vizuală offscreen, nu acceptare manuală pe persoane.
- partial/: oprire în inițializare, 0 cadre, model închis, fără receipt.
  partial-after-warmup/: importul bibliotecii MediaPipe a fost preîncălzit,
  modelul rămânând construit o singură dată în SourceWorker; stop-after 1.5 a
  păstrat **6 cadre/6 apeluri MP**, fără EOF, cu export parțial și receipt D.
  Stop/restart cu cadre și capturi fără suprapunere este verificat și prin test Qt.
- artifacts/p2-missing-p1/: și cu --engagement-model către un pachet inexistent,
  CLI-ul a raportat MODEL_UNAVAILABLE și a procesat 10 cadre/10 apeluri MP,
  zero erori, fără Fake sau levels fabricate.
- Artifactele p2-final-protocol și p2-integration-wheel sunt verificări
  intermediare; sursele au fost modificate ulterior. Pentru versiunea curentă
  se folosesc numai p2-accepted-protocol / p2-accepted-wheel.

Nu sunt revendicate erori de orientare, precizie de gaze, acuratețe de clipiri
sau validare experimentală pe oameni. Hashuri diferite pentru două clipuri
sintetice nu demonstrează independența semantică a unor înregistrări reale.

## Pachet și reproducere

SHA256 surse testate în worktree: `7900f30851494327d6cc5de55cd17b92a8198da6bc2c74a6103a6a1792cac2be`.
Acesta identifică sursele efective, inclusiv schimbările încă necomise.
Wheel-ul acceptat: artifacts/p2-accepted-wheel/audience_analysis-0.1.0-py3-none-any.whl,
352518 bytes, SHA256 `55bf5df3a3ce612bdb52265da1f6bf0b09ff7ec74beb029c79c99defabe1bb26`.
A fost instalat fără dependențe/rețea într-un target artifacts separat,
importat din acel target și verificat prin help din alt cwd. Fingerprintul
sursei wheel este identic cu worktree-ul. Mediul original nu a fost reinstalat.

Modelul MediaPipe local: SHA256
`64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`.
YuNet: SHA256 `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`.
Modelele/datele nu fac parte din noile modificări Git sau din snapshotul de cod.

Comanda locală verificată, din PowerShell:

```powershell
$integrationRoot = "C:\Users\artio\Desktop\AnalizaAtentiei\AnalizaAtentiei-integration"
$py = "C:\Users\artio\Desktop\AnalizaAtentiei\.venv-completion\Scripts\python.exe"
$model = "C:\Users\artio\Desktop\AnalizaAtentiei\models\face_landmarker.task"
Set-Location $integrationRoot
$env:PYTHONPATH = "$integrationRoot\src"
$env:PYTHONUTF8 = "1"
& $py -c "import audience_analysis; print(audience_analysis.__file__)"
& $py -m audience_analysis.engine.cli --source "C:\Users\artio\Desktop\AnalizaAtentiei\artifacts\mvp_blank.avi" --model $model --source-id S01 --session-id D01 --role development --output-dir "$integrationRoot\artifacts\my-p2-run" --fast --synthetic-input
```

Această comandă folosește materialul tehnic fără persoane. Pentru un clip
autorizat normal se înlocuiește --source și se omite --synthetic-input;
--track-id permite selectarea explicită. --fast omite numai pacingul, nu cadrele.
--stop-after măsoară timpul inclusiv inițializarea: o valoare mică poate opri
înaintea primului cadru. Ctrl+C cere oprire controlată și returnează 130.
--engagement-model este opțional și cere un pachet P1 local compatibil;
absența/invaliditatea sa nu selectează Fake și nu oprește geometria.

Deschiderea rezultatului în dashboardul existent:

```powershell
$run = Get-ChildItem "$integrationRoot\artifacts\my-p2-run\S01" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
& $py "$integrationRoot\run_dashboard.py" --measurements "$($run.FullName)\measurements.csv" --session-id D01
```

Pentru fereastră vizibilă nu seta QT_QPA_PLATFORM=offscreen; dacă ai rulat teste
în aceeași consolă, elimină acea variabilă de mediu înainte de pornire.
În dashboard importă blinks.csv ca automat, salvează explicit snapshotul și
atașează video numai pentru un CSV de fișier cu mapare confirmată.

Calibrare și C/D/V:

```powershell
# Folosește un profil real autorizat, pregătit prin calibrate_session.py.
& $py -m audience_analysis.engine.cli --source "C:\Date\D01.mp4" --model $model --session-id D01 --role development --calibration "C:\Date\C01_profile.json" --output-dir "$integrationRoot\artifacts\D01-p2"
# Salvează snapshotul D cu experimental_session.py create, apoi freeze.
# V folosește --session-id V01 --role validation --frozen-plan <planul-P2.json>.
& $py "$integrationRoot\experimental_session.py" --help
& $py "$integrationRoot\run_validation.py" --help
```

Comanda acceptării automate:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
# Pregătește artifacts și TEMP/TMP locale; alege un basetemp nou.
& $py -m pytest -q -p no:cacheprovider tests -m "not training and not checkpoint_fixture" --basetemp "$integrationRoot\artifacts\pytest-integration-acceptance-new"
```

## Limitări și lucrări P3 rămase

- UI moștenită din Ilie nu consumă încă geometry_ready, nu afișează câmpurile
  head/eye/temporal sau toate casetele/trackurile și nu oferă modul real complet.
  --demo continuă să folosească FakePredictor explicit; nu este demo-ul geometric.
  Nu s-au reparat widgeturile P3 în locul Ema și nu s-a creat un alt dashboard.
- P3 poate injecta geometry_factory în motor și folosi semnalele bounded/
  take_latest_features, verificând source/run/frame. Bannerul/modelul indisponibil,
  validarea formularului, grila și exportul UI rămân de implementat/testat acolo.
- Trackingul IoU și asocierea geometrică nu verifică identitatea; ocluziile,
  mai multe fețe și schimbarea țintei pot produce N/A. Profilul corect și
  autorizarea materialului sunt responsabilități ale operatorului.
- Cameră fizică, RTSP/MJPEG real, VFR de la echipamente diverse, laptopul final
  și stabilitate/memorie de lungă durată nu au fost validate. Memoria este
  limitată prin bugete de elemente; costul în bytes depinde de rezoluții/config.
- Modelul P1 de angajament nu este furnizat/evaluat. Fabrica, configurația
  manifestului, ModelOutput și workerul unic sunt pregătite; un pachet real,
  datele și paritatea Colab/local sunt necesare înainte de rezultate reale.
- Nu există scor de atenție, Visual Orientation Score, recunoaștere de persoane
  sau determinare exactă a punctului privit pe ecran.

## Starea Git și conservare

Surse fixate: Artiom c69808ed7fb71a9972ff1a104f1b6a250301c4cb;
Ilie 58d8a91a518c06e2585847b3cf2828fde53def5b. Main rămâne
4379f098fd0c5e728436dacd22fa835e22b37c0a. Branchurile și remote nu au fost mutate.

**Commit de merge: necreat. Commituri de integrare: necreate.** Revizuirea
automată a respins operația concretă de commit, invocând instrucțiunea din
AGENTS.md „Nu face commit/push automat” și lipsa unui override suficient de
explicit pentru acel commit. Respingerea nu a fost ocolită. MERGE_HEAD rămâne
Ilie, fără conflicte, iar cele 13 fișiere incoming rămân staged; implementarea,
testele și documentația proprii rămân în working tree.

Rezultatul verificat nu trebuie atribuit numai SHA-ului HEAD c69808e: acesta
este baza Artiom; starea efectivă este identificată de fingerprintul surselor
de mai sus și de snapshotul local. Pentru finalizarea istoricului sunt necesare
aprobarea precisă a commitului de merge și apoi a commitului de integrare,
numai pe integration/artiom-ilie-video, fără push. Nu se face reset/clean și
nu se pierd modificările pregătite. Snapshotul de conservare este în
artifacts/integration-preservation/artiom-ilie-video-2026-11-19.zip, cu inventar
SHA256 și diff față de HEAD; include doar cod/config/docs/teste text, nu date,
modele, medii sau artifacte de analiză.

Inventarul final de conservat cuprinde **28 de fișiere text**: 22 căi tracked
modificate/adăugate față de HEAD și 6 untracked noi. Cele 13 căi din indexul
merge-ului sunt un subset, nu încă 13 fișiere separate. Instrucțiunile Git și
mesajele propuse pentru aprobare sunt: `Merge origin/ilie-p2 into
integration/artiom-ilie-video`, apoi `Integrate P2 facial geometry and lifecycle
safety`, numai pe branchul de integrare și fără push.
