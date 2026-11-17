# Finalizarea responsabilităților proprii — artiom-branch

16 noiembrie 2026. Punct de pornire: [auditul proiectului](project-audit-week-2026-11-16.md), citit integral împreună cu planul P1 și specificațiile. Livrarea privește **software-ul P1 și laboratorul E1–E8**. Responsabilitatea P1 este scopul autorizat în taskul curent; atribuirea nominală a tuturor activităților istorice rămâne neconfirmată. Nu sunt atribuite utilizatorului commiturile sau funcționalitățile colegilor.

## A. Summary

Implementat efectiv:

- Manifest P1 cu etichete opționale separate, verificări de fișiere/duplicate/participanți disjuncți, cache NPZ sigur, iterator de secvențe și pregătire comună cu P2.
- `RealPredictor` funcțional pentru pachete locale, încărcare o dată pe instanță, verificarea claselor/dimensiunilor/configurației/checksumului, inferență fără normalizare dublă și `MODEL_UNAVAILABLE` explicit. FakePredictor rămâne separat.
- Reutilizarea MobileNet mean/GRU legacy și infrastructură de capete separate; R0 și comparații pe același subset observabil, cu interdicția selecției pe test. Nu s-a antrenat și nu s-a exportat un model fictiv.
- R08 corectat în API-ul final de nivel inferior, cu guard comun și teste pentru modificarea rândurilor/evenimentelor/codului/modelului/rolului și surselor.
- R09 îmbunătățit prin materialele C hashed, sidecaruri C verificate, model C legat de sursa efectivă când este cunoscut și refuzul reutilizării materialelor cunoscute în D/V. Hashurile nu demonstrează independența semantică a unor re-encodări.
- CLI video cu memorie limitată și export streaming, rapoarte parțiale la întrerupere și erori exportate fără căi personale; snapshoturi fără căi externe implicit și cu integritatea măsurătorilor verificată.
- Model HF fixat la revizie și local implicit; script istoric fără descărcări la import, testele de training/checkpoint marcate separat, wheel și entry points pentru comenzile proprii, mediu virtual separat cu o singură distribuție OpenCV.

Nu s-au modificat schedulerul, capturile sau UI-ul de operare P2/P3 și nu s-au integrat alte branchuri. Dashboardul experimental rămâne componenta distinctă E7/E8.

## B. P1 Task Completion — toate cele 27 de taskuri

Stările inițiale sunt cele din audit. „Software finalizat” în coloana implementării nu înseamnă că este satisfăcut un criteriu care cere date/model/evaluare/prezentare reală. Checklisturile originale rămân nebifate până la validarea echipei.

Dovezi: **P1-T** = `tests/ai/test_p1_completion.py`, `test_predictors.py`; **G-T** = testele din `tests/terminal` pentru geometrie/video/temporal; **V-T** = `test_calibration.py`, `test_validation.py`, `test_experimental.py`, `test_dashboard.py`. Documentație de utilizare: [P1](p1-data-model.md), [surse și contribuția la prezentare](p1-research-and-presentation.md), [mediu](environment.md).

| ID | Task | Stare inițială | Ce s-a implementat/pregătit | Teste/dovezi | Stare finală | Blocaje rămase |
|---|---|---|---|---|---|---|
| P1-S1.1 | Acces și condiții DAiSEE | NOT VERIFIED | Surse primare și pași de audit al materialelor, fără descărcare de dataset | Documentarea P1; pagina autorilor nu a răspuns | BLOCKED | Acces, condiții actuale și permisiuni neconfirmate; nu poate fi rezolvat prin cod |
| P1-S1.2 | DAiSEE și 2–3 lucrări | NOT VERIFIED | Note pe DAiSEE, MobileNetV3 și RNN/GRU, relevanță și limite, surse primare | `p1-research-and-presentation.md`, PDF/articole consultate | COMPLETED | Nu înseamnă acces la date sau validarea propriului model |
| P1-S1.3 | Cele patru dimensiuni și nivelurile reale | PARTIALLY COMPLETED | Contracte labels/dimensions ordonate și etichete lipsă distincte de 0 | P1-T, documentare primară | PARTIALLY COMPLETED | Verificarea coloanelor și mapării din fișierele DAiSEE efectiv primite |
| P1-S1.4 | Colab și exemplul P1 | PARTIALLY COMPLETED | API-uri comune, exemplu simulat separat și instrucțiuni fără importuri grele | P1-T, exemplul P1 | PARTIALLY COMPLETED | Execuție Colab și accesul operatorului; nu se pretinde notebook rulat acolo |
| P1-S2.1 | Manifest și loader | PARTIALLY COMPLETED | Loader funcțional, fișiere, etichete, splituri, duplicate, NPZ și iterator; fără cv2/PyTorch la import | P1-T, cazuri negative | PARTIALLY COMPLETED | Software complet; manifestul real și inventarul clipurilor necesită date autorizate |
| P1-S2.2 | Separare participanți/clipuri | PARTIALLY COMPLETED | Respinge ID/cale/conținut duplicat și participant în splituri diferite | P1-T; istorice manifest | PARTIALLY COMPLETED | Auditarea împărțirii reale și independența semantică a înregistrărilor |
| P1-S2.3 | Preprocesare comună P1/P2 | PARTIALLY COMPLETED | Reutilizează `prepare_bgr`, validează T/CHW/dtype/id/durată, test de paritate ImageNet cu legacy | P1-T, paritate numerică pe pixeli sintetici | PARTIALLY COMPLETED | Configurația pachetului real și confirmarea cropului cu P2/Colab |
| P1-S2.4 | Loader, baseline mean și R0 | PARTIALLY COMPLETED | Loader/caches, fabrici mean și GRU native, R0 train-only | P1-T, forward CPU fără download | COMPLETED | Pregătirea software este încheiată; antrenarea reală aparține S3.1 |
| P1-S3.1 | Antrenare baseline | BLOCKED | Arhitectură și export strict pregătite; nicio antrenare lansată | P1-T verifică refuzul exportului fără dovezi | BLOCKED | Date/permisiuni și task de antrenare autorizat; nu există weights reale |
| P1-S3.2 | Validare baseline vs R0 | BLOCKED | Macro-F1/BA/confuzie, acoperire, subset comun și export JSON | P1-T, metrici cunoscute și comparație sintetică | BLOCKED | Predicții/ținte reale ale modelului validat |
| P1-S3.3 | Predictor local | PARTIALLY COMPLETED | Adaptor complet, load-once, state_dict sigur, clase/config/hash, is_demo=false, indisponibilitate fără fallback | P1-T, mocks explicite, backend mean/GRU nativ | COMPLETED | Modelul real și traseul comun rămân la S3.1/S3.4; adaptorul gestionează explicit absența lor |
| P1-S3.4 | Paritate Colab–local și predare | BLOCKED | Contract/format și paritate de preprocesare pregătite; wheel instalabil | P1-T, verificarea wheel | BLOCKED | Model/date reale, Colab și integrarea colegilor neautorizată în această etapă |
| P1-S4.1 | Conținut pentru 6–7 slide-uri | NOT VERIFIED | Contribuție P1 în 7 puncte cu metodă, software verificat și N/A pentru rezultate reale | Note pentru prezentarea comună | PARTIALLY COMPLETED | Rezultate reale și asamblarea/prezentarea cu echipa |
| P1-S4.2 | Exemple corecte/greșite autorizate | BLOCKED | Procedura și limitele documentate; nu s-au fabricat exemple | P1 docs | BLOCKED | Model evaluat și exemple autorizate etichetate |
| P1-S4.3 | Model/config de demo fixate | BLOCKED | Format versionat/checksum; modelul HF existent fixat, distinct de angajament | P1-T și forward HF offline tehnic | BLOCKED | Pachetul real de angajament și alegerea demo-ului echipei |
| P1-S4.4 | Feedback AI | NOT VERIFIED | Format propus de înregistrare și acceptare a observațiilor | Note P1 | NOT VERIFIED | Feedbackul real al unei prezentări nu există în sursele accesibile |
| P1-S5.1 | GRU implementat și antrenat | PARTIALLY COMPLETED | Reutilizare GRU legacy, encoder înghețat și capete configurabile | P1-T, forward CPU | PARTIALLY COMPLETED | Antrenare și evaluare pe corpus autorizat |
| P1-S5.2 | Mean vs GRU | BLOCKED | Comparator cu același subset, R0 train-only, selectie numai validation | P1-T | BLOCKED | Rezultate reale comparabile; nu se aleg modele din fixture-uri |
| P1-S5.3 | Boredom/confusion/frustration | NOT STARTED | Capete separate și ordine/labels verificate, fără imputarea etichetelor lipsă | P1-T, toate patru capetele pe mean/GRU | PARTIALLY COMPLETED | Fiecare head trebuie antrenat/evaluat independent înainte de utilizare reală |
| P1-S5.4 | Predare model și ieșiri disponibile | BLOCKED | Manifest și ModelOutput cu numai dimensiunile declarate, MODEL_UNAVAILABLE când lipsesc | P1-T; `audience-ai` | BLOCKED | Nu există model real de predat și confirmare cu P2/P3 |
| P1-S6.1 | Test final după fixare pe validation | BLOCKED | Guard de selecție și formatul dovezilor, protocol fără tuning pe test/V | P1-T, V-T | BLOCKED | Date/weights și test independent real; C/D/V geometric nu substituie DAiSEE |
| P1-S6.2 | Rezoluție/decupaj | NOT STARTED | Configurații existente păstrate, comparație comună și preprocesare testabilă | P1-T; default/no_margin | BLOCKED | Experiment real cu P2 și aceleași etichete/splituri, în scope separat |
| P1-S6.3 | Export/normalizare/laptop | PARTIALLY COMPLETED | Export state_dict/manifest, încărcare strictă, paritate numerică și wheel cu comenzi proprii | P1-T, packaging și CLI | PARTIALLY COMPLETED | Pachet real și laptopul de prezentare; nu s-a generat un checkpoint fals pentru a închide taskul |
| P1-S6.4 | Secțiuni articol/poster | NOT STARTED | Text reutilizabil despre date/metodă/validare software/limite, cu surse și fără metrici DAiSEE inventate | Note P1 + acest bilanț | PARTIALLY COMPLETED | Rezultatele reale și materialele finale ale echipei |
| P1-S7.1 | Pachet AI de predare | PARTIALLY COMPLETED | Cod, wheel, notebookurile existente, configurații, CLI, contracte și documentație | Build/wheel/import/teste | PARTIALLY COMPLETED | Weights și rapoarte reale autorizate; revizuire nominală și commit/publicare |
| P1-S7.2 | Repetiție și demo rezervă | NOT VERIFIED | Comenzi și scenariu tehnic pregătite | Smoke local pe materiale fără persoane | NOT VERIFIED | Repetiție comună, model și material autorizat de rezervă |
| P1-S7.3 | Prezentarea contribuției | NOT VERIFIED | Delimitarea contribuțiilor și dovezilor, fără a atribui munca colegilor | Audit + bilanț | NOT VERIFIED | Prezentarea efectivă și confirmarea contribuțiilor nominale |

Restanțele de mai sus nu ascund stubs P1 implementabile: loaderul, predictorul, fabricile, comparația și exportul sunt cod funcțional. Taskurile originale care cer antrenare, corpus, model predat, evaluare sau prezentare rămân deschise pentru că acele dovezi nu există.

## C. E1–E8 Completion

| Componentă | Stare tehnică și schimbare | Testare automată / tehnică | Ce rămâne extern |
|---|---|---|---|
| CLI/pipeline | Streaming, contor global/fereastră, CSV incremental, întrerupere, erori redacționate, model HF local fixat | Test 4000→40000 cadre fără creștere O(N), export complet, Ctrl+C, import offline, launcher și forward HF sintetic | Interpretarea/acuratețea expresiilor pe persoane și hardware real |
| E1 Face Landmarker | Reutilizat fără rescriere; model local identificat prin SHA256 | Teste IMAGE/VIDEO, smoke cu modelul local pe video uniform | Acuratețe/populație/ocluzii reale |
| E2 Head Pose | SVD/grade/convenții/neutru păstrate; frame camera/neutral explicit în payload | Matrici sintetice și teste contractuale | Măsurători independente pentru erori reale în grade |
| E3 Eye Features | EAR/iris/calibrare/availability păstrate și documentate | Teste geometrice, invalide/închise, payload | Ocluzii, ochelari și generalizare; punctul privit nu este determinat exact |
| E4 Video | O instanță MP/sesiune, FrameClock reutilizat; erorile CSV nu expun căi | Mock file/webcam, release, CSV și smoke no-face real MediaPipe | Cameră fizică și latență/stabilitate pe sesiuni autorizate |
| E5 Temporal | Ferestre/histerezis/gapuri păstrate; count=None fără EAR observat | Timestampuri neregulate, lipsă față, limite durată, smoothing, regresie N/A | Clipiri/mișcări confirmate manual pe oameni |
| E6 Calibration/Validation | Guard final central, surse C și model când cunoscute, sidecar verificat, compatibilitate profil vechi | Rânduri/evenimente alterate, roluri, hashuri, profile, metrici și periodicitate | Referințe reale; profilele vechi fără surse rămân explicit cu proveniență incompletă |
| E7 Dashboard | CSV/grafice/navigare/adnotări/export/snapshoturi păstrate; metadate invalide refuzate înainte de scriere | Teste Qt offscreen, import/seek/mark/save/reload/export/delete, N/A | Acceptare vizuală/manuală Windows cu video real și operator |
| E8 C/D/V | Separare, proveniență și reproducibilitate consolidate, fără căi externe implicit | Teste software și rulare tehnică C sintetic/D/V fără persoane | Consimțământ, C/D/V real independent, adnotatori și criterii înainte de V |

Implementarea software nu echivalează cu validarea experimentală. Nu s-a implementat atenție, oboseală, emoții noi, biometrie, scheduler nou sau UI P3 alternativă.

## D. Changes Implemented

Fișierele E6–E8 existente au fost păstrate înainte de lucru în `artifacts/branch-preservation/pre-completion-2026-11-16.zip`, cu inventar SHA256: 26 de fișiere text (cele 25 din audit plus raportul), fără date, binare sau chei private detectate. Acest snapshot, împreună cu baza `f4fcfc6`, permite recuperarea stării inițiale. Nu a fost șters sau activat implicit codul legacy.

Schimbările noi principale:

- `ai/data.py`, `ai/models.py`, `ai/predictor.py`, `ai/package.py`, `ai/evaluation.py`, `ai/cli.py`: infrastructura P1 și CLI independent.
- `experimental.py`, `validation.py`, `calibration.py`, `calibrate_session.py`, `run_video_analysis.py`, `dashboard_data.py`, `experimental_session.py`: guard comun, canonicalizare, surse/model C, verificarea snapshoturilor și opt-in pentru căi.
- `pipeline.py`, `__main__.py`, `model_stats.py`, `video_processor.py`, `start-analysis.ps1`: streaming, erori private redacționate, offline/revision și selectarea explicită a venv-ului.
- `temporal_analysis.py`, `geometric_api.py`, `metrics.py`: N/A la lipsa EAR, mesaje geometrice serializabile și clase numerice strict validate.
- `pyproject.toml`, `.gitignore`, `configs/constraints-windows-py313.txt`: entry points, root modules incluse în wheel, o singură distribuție OpenCV în extra-uri și excluderea artifactelor build.
- Teste P1, payload, streaming/proveniență/dashboard/temporal/video; scriptul istoric `test_net.py` este acum import-safe, iar testele de training/checkpoint sunt marcate, nu eliminate.
- README, STATUS, contracte, documentele etapelor, documentarea P1/mediului/cercetării și acest bilanț. Specificația originală F1–F9 și checklisturile nu au fost modificate ca să pară finalizate.

## E. Bugs Fixed

1. **R08:** un apel direct final cu date/evenimente diferite nu mai trece numai pe baza ID-ului din receipt. CLI, dashboard și API folosesc același guard; omiterea evenimentelor așteptate este refuzată.
2. **R09:** C poate lega materialele efective prin hash și sidecarurile măsurătorilor. D/V cunoscute nu pot fi relabelate ca C; modelul C/D/V este comparat când există proveniență. Profilele vechi nu sunt prezentate ca având raw provenance verificată.
3. **Metadate private:** snapshoturi fără căi externe implicit, checksum semantic verificat la reîncărcare, erori CSV/log fără căile din excepții și source generic în sumarul CLI. Date/config JSON nefinite și date ISO invalide sunt refuzate înainte de creare.
4. **Memorie CLI:** nu mai acumulează toate FrameResult/ferestrele pentru video în CLI. Modul istoric programatic rămâne explicit, cu recomandare pentru streaming la sesiuni lungi.
5. **N/A temporal:** fereastra fără niciun EAR valid nu mai raportează count=0 doar fiindcă pragul a fost configurat.
6. **R12:** `tests/test_net.py` nu descarcă la import; trainingul și checkpointurile sintetice sunt diferențiate prin markeri.
7. **R15 propriu:** wheel-ul conține efectiv toate cele 7 module root și entry point-urile pot rula din alt cwd. Prima verificare a detectat absența lor; maparea setuptools a fost corectată și fingerprintul checkout/wheel este comparat explicit.
8. **R17:** revizia HF este fixată, implicit cache-only; nu există download incidental la import/colecție. Eroarea de încărcare este memorată pe pipeline pentru a evita repetarea încercării la fiecare cadru.

R01–R07 ale P2/P3, camera/network în noul engine, filtrul real/demo și lifecycle-ul colegilor **nu au fost reparate aici**. Sunt dependențe ale integrării ulterioare și rămân documentate în audit.

## F. Tests

Rezultatul de acceptare și hashurile finale sunt consemnate în nota de verificare de la sfârșitul documentului. Verificările executate până la acceptare:

| Selecție | Rezultat observat | Semnificație |
|---|---|---|
| Baseline păstrat, `.venv` | 223 passed in 26.84s | Starea anterioară modificărilor |
| P1 + provenance/dashboard/calibrare/validation | Teste țintite trecute pe parcurs | Fixture-uri și mocks explicite, fără checkpointuri generate |
| Selecția configurată, venv separat | 275 passed in 65.70s | Include backendurile native mean/GRU, geometrie, calibrare, dashboard |
| Istorice sigure, venv separat | 17 passed, 3 deselected in 20.95s | Training/checkpoint nu au fost executate |
| Toate testele sigure combinate — acceptare finală | **292 passed, 3 deselected in 54.60s; 0 failed, 0 skipped** | Rulare după ultima corecție Python, inclusiv redacționarea erorilor |
| `.venv` original, selecție configurată | 274 passed, 1 skipped in 45.96s | torchvision lipsește intenționat din mediul vechi păstrat; nu este baza recomandată |
| Toate patru capetele, mean și GRU CPU | 1 passed in 7.31s | Forward sintetic în memorie, fără antrenare/export de weights |

Numerele rulărilor care se suprapun nu se însumează. Testele nu sunt rezultate DAiSEE. Trei teste istorice rămân deselectate explicit: optimizarea mean/GRU, checkpointul sintetic de paritate și experimentul sintetic cu antrenare/export. Există în continuare și pot fi lansate separat numai cu autorizarea potrivită. În mediul recomandat nu mai sunt blocate de lipsa torchvision.

Comanda acceptării:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
$env:PYTHONUTF8 = "1"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
.\.venv-completion\Scripts\python.exe -m pytest -q -p no:cacheprovider tests -m "not training and not checkpoint_fixture" --basetemp artifacts/pytest-completion-acceptance
```

Verificări suplimentare: build/instalare wheel fără dependențe online, `pip check`, entry points în alt cwd, source fingerprint identic checkout/wheel, CLI model absent → cod 4, launcher pe clip tehnic fără fețe, MediaPipe local pe D/V tehnice și două rapoarte identice. HF din cache a fost încărcat offline și a produs șapte probabilități finite pe o imagine uniformă generată, fără concluzii despre expresii sau persoane.

## G. Environment

[environment.md](environment.md) și `configs/constraints-windows-py313.txt` descriu mediul Windows/Python 3.13.2. `.venv-completion` este separat, cu torch 2.15.0+cpu, torchvision 0.29.2+cpu și numai opencv-contrib-python 5.0.0.93. Mediul original și artifactele V vechi nu au fost rescrise. Codul nou invalidează fingerprintul pachetelor experimentale vechi, conform regulii existente; pentru reproduceri se folosește codul/modelul/mediul fixat, nu se editează hashurile.

Model MP local: SHA256 `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`. HF: `jihedjabnoun/vit-face-emotion-recognition`, revizie `ec667156e4f9a2e329911a1da5c13572ae3d75d4`, cache-only implicit. Nu s-au descărcat date sau ponderi. Biblioteca torchvision de aproximativ 1.4 MB a fost singura descărcare nouă de runtime; restul dependențelor au fost replicate local pentru a păstra mediul original.

## H. Remaining External Blockers

- Date DAiSEE efective, accesul/condițiile și permisiunile lor; model de angajament antrenat/evaluat și rapoarte reale. Nu pot fi înlocuite prin fixture-uri.
- Colectare C/D/V reală autorizată, consimțământ inclusiv pentru minori unde este aplicabil, referințe independente și adnotatori. MAE/RMSE nu sunt calculate din instrucțiuni verbale.
- Cameră fizică, un flux de rețea autorizat, laptop final, stabilitate/performance de durată și acceptare manuală a UI.
- Execuție Colab și paritate cu modelul real, integrarea P2/P3, deciziile comune despre subiect unic/tracking, timpi și limitele motorului.
- Feedback, repetiții, prezentare/articol/poster finale și contribuții nominale confirmate. Notele pregătite sunt material de lucru, nu dovada susținerii unei prezentări.
- Aprobarea precisă pentru commiturile locale dacă sunt dorite: revizuirea automată a refuzat operația de conservare invocând regula AGENTS. Nu s-a ocolit respingerea; codul este păstrat în snapshoturi și working tree.

## I. Integration Readiness

**Software-ul propriu este pregătit pentru review tehnic și integrare ulterioară, cu indisponibilitatea explicită a modelului real și blocajele externe de mai sus.** Nu este declarat produs validat sau MVP original complet.

Contracte pregătite: PreparedSequence/ModelOutput existente, formatul pachetului P1 și erorile lui, VideoMeasurement și payloaduri geometrice/temporale versionate, availability, profil C cu surse/model opționale, metadate C/D/V și formate CSV/JSON cu N/A. Documentația precizează unități, reper, timestampuri, ID-uri, clase, valori lipsă și limitele interpretării.

Nu se importă module din branchurile neintegrate. `src/audience_analysis/engine/`, `src/audience_analysis/video/`, `ui/main_window.py` și `ui/history.py` nu au modificări ale acestei livrări față de branchul curent. Geometria nu a fost conectată la motor printr-o captură/scheduler alternativ. Problemele colegilor sunt gate-uri de integrare, nu stubs proprii ascunse.

## J. Final Git Status

Branchul activ rămâne `artiom-branch`, pornit de la `f4fcfc6b44a9011102964468d8840f7e241cd4d7`. **Zero commituri locale create, zero push, zero merge/rebase/cherry-pick/reset/clean.**

Taskul permitea commituri locale, însă revizuirea automată a respins operația concretă pentru cele 25 de fișiere și audit, invocând regula din AGENTS „Nu face commit/push automat sau instalări globale” și lipsa unei aprobări pe care sistemul să o considere suficient de precisă. Respingerea nu a fost ocolită. Au fost păstrate working tree-ul, snapshotul inițial și un snapshot final versionabil; lista exactă a căilor/hashurilor este în inventarul snapshotului final, împreună cu diff-ul tracked.

Modificările rămân locale pentru review. Înainte de orice commit se revizuiește lista explicită și se exclud `artifacts/`, medii, date și weights. Numai fișiere text de cod/configurație/documentație/teste fac parte din livrare. Auditul istoric este păstrat, nu rescris retroactiv.

Inventarul final cuprinde **63 de fișiere: 31 tracked modificate și 32 untracked**, inclusiv lucrările E6–E8 păstrate și auditul anterior. Indexul Git este gol. Pentru lista completă, vezi `artifacts/branch-preservation/artiom-completion-2026-11-16.inventory.json` și copia sa din ZIP. Bilanțul celor 27 de taskuri P1: **3 COMPLETED, 11 PARTIALLY COMPLETED, 10 BLOCKED, 3 NOT VERIFIED**; etapele software pregătite nu închid criteriile care cer date sau rezultate reale.

## K. Next Steps

1. Revizuirea matricei și codului; dacă se dorește, aprobare explicită pentru commituri locale mici, fără push.
2. Predarea către P2/P3 a contractelor și wheel-ului; corecțiile R01–R07 rămân la componentele lor înainte de conectare.
3. Obținerea datelor/permisiunilor și pregătirea unui task separat de antrenare/evaluare reală. Nu se completează taskurile academice cu scoruri sintetice.
4. Pilot C/D/V autorizat pe cod/model/mediu fixate și verificare manuală a sincronizării/adnotărilor.
5. Integrare între branchuri numai după aprobarea rezultatului și a strategiei comune. Nu a fost începută în această livrare.

## Verificare finală și artifacte tehnice

- Acceptare finală: **292 teste trecute, 3 deselectate explicit, zero eșecuri și zero skip**, 54.60s în `.venv-completion`. Markerii excluși sunt `training` și `checkpoint_fixture`. După aceasta s-au schimbat numai documentația și launcherul PowerShell (`-X utf8`, fallback la mediul nou `.venv-local`); launcherul a fost rerulat cu succes.
- SHA256 al surselor Python: `90000ef54d506625696102613d97673b8048ae25fe271977dea37cc8d1856889`, identic în checkout și în wheel-ul instalat, verificat din alt cwd. Wheel: `artifacts/completion-wheel/audience_analysis-0.1.0-py3-none-any.whl`, SHA256 `dbf76e863afcbef2f0cce72c41106f0734165f418d12524ca47ce3b19de94782`. Wheel-ul conține codul Python și documentele incluse la build, nu launcherul sau ultima versiune a acestui raport; fișierele complete sunt în snapshot.
- Cele șase entry points au trecut `--help` din afara proiectului. `audience-ai inspect-model` fără model a returnat exact `MODEL_UNAVAILABLE`, `levels: null`, cod 4. `pip check`: fără dependențe incompatibile.
- `artifacts/completion-final-verified/` păstrează rularea **TECHNICAL-ONLY-NO-HUMAN-EVALUATION**: C din semnale EAR sintetice declarate, D 20 de cadre fără față și V 10 cadre fără față, zero erori MediaPipe. Nu sunt sesiuni pe persoane și nu există rezultate de acuratețe reală.
- Plan tehnic înghețat SHA256 `75a2cc62fd66f570abafc50c76237b44f4a9c8ca2f989eed06cf32971d468274`. Cele două `report.json` sunt identice byte-cu-byte, SHA256 `24f22602aab066537954899234654f0a8adcb4fce42c7422d8cd69a9c84e5c73`. Referințe independente: 0; MAE/RMSE și evaluarea clipirilor rămân N/A. API-ul direct a refuzat o copie cu yaw modificat.
- Snapshoturile C/D/V s-au reîncărcat, comparația nu a avut erori, manifestele nu conțin căi absolute externe. Captura `artifacts/completion-final-verified/dashboard-comparison.png` a fost inspectată: trei roluri, metrici N/A, grafic de acoperire zero și etichete lizibile. Aceasta este verificare vizuală offscreen, nu acceptare manuală cu operator/video real.
- Launcherul final a procesat 4 cadre eșantionate, zero fețe și zero erori, în `artifacts/completion-launcher-final/`. Pe Windows cu stdout redirecționat și codepage vechi este necesar `$env:PYTHONUTF8="1"` pentru comenzile directe; launcherul setează `-X utf8`. Prima încercare directă fără această setare a procesat datele dar a eșuat la afișarea diacriticelor, deci nu este raportată ca rulare reușită; artifactele parțiale au fost păstrate separat.
- Snapshot final: `artifacts/branch-preservation/artiom-completion-2026-11-16.zip`, cu inventar de căi/dimensiuni/SHA256, fișierele complete modificate/neversionate și diff tracked față de baza Git. Nu include venv, date, clipuri, modele sau artifacte generate. Snapshotul și wheel-ul sunt locale, ignorate de Git; nu s-a făcut commit sau push.
