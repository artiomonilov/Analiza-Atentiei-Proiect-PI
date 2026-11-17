# Audit al proiectului și plan de integrare — 16–22 noiembrie 2026

Data auditului: **16 noiembrie 2026**, Windows / Python 3.13.2. Mod de lucru: **AUDIT & PLANNING ONLY**. Nu au fost modificate funcționalități, instalate dependențe sau executate checkout, merge, rebase, cherry-pick, commit ori push. S-au actualizat numai referințele remote prin `git fetch --no-tags origin`; inspecția ramurilor a folosit `git show`, diffuri și snapshoturi temporare `git archive`. Acest document este singura livrare nouă destinată versionării. Cache-urile și fișierele temporare ale verificărilor sunt în `artifacts/`, ignorat de Git.

## A. Executive Summary

**Proiectul nu este încă un MVP integrat cu predictor real de angajament.** Există componente software substanțiale, însă trei trasee coexistă fără unificare funcțională:

1. **Legacy**, moștenit din `main`: `app.py`, `legacy_ui.py`, `runtime.py`, `legacy_contracts.py`, `models.py`, `dataset.py`, `experiment.py`. Include infrastructură pentru 1–4 surse și arhitecturi mean/GRU, dar nu dovedește antrenare/evaluare DAiSEE.
2. **Mini-template comun P1/P2/P3**, în `contracts.py`, `config.py`, `ai/`, `video/`, `engine/`, `ui/main_window.py`. Simularea funcționează; predictorul P1 real rămâne un stub. `origin/ema` extinde formularul, iar `origin/ilie-p2` adaugă fișiere reale, YuNet și urmărire anonimă.
3. **Analiză geometrică și laborator experimental**, pe `artiom-branch` plus working tree: MediaPipe → head pose/ochi → video/temporal → calibrare/validare → dashboard → C/D/V. Nu produce un clasificator de atenție. Pipeline-ul de expresii din `pipeline.py` este o cale CLI separată, cu model Hugging Face la cerere.

Rezultatele reverificate în audit:

- Working tree curent: **223 passed**, selecția pytest configurată.
- `artiom-branch` publicat la `f4fcfc6`: **143 passed**, snapshot izolat. Diferența de 80 de teste corespunde extensiilor locale de calibrare, dashboard și Etapa 8; codul acestora nu este încă disponibil colegilor prin commitul remote.
- `main`: **27 passed**; `origin/ema`: **27 passed**; `origin/ilie-p2`: **26 passed, 1 failed**. Aceste selecții se suprapun și **nu trebuie însumate** ca teste distincte.
- Istorice suplimentare `test_core.py` și `test_runtime.py`: **15 passed**. Colecția separată care includea `test_models.py` a eșuat din lipsa `torchvision`. Nu au fost executate testele istorice de optimizare/antrenare sau scriptul cu descărcări la import.
- Au fost reproduse riscuri neacoperite de testele existente: coadă P2 de 100 de cereri pentru 100 de track-uri, contabilizare a cererilor noi afectată de finalizarea unei cereri vechi, formular Ema incompatibil cu propriul `SourceConfig`, filtru UI care exclude rezultate reale și verificare incompletă a provenienței în API-ul de validare de nivel jos.

**Nu există o validare experimentală demonstrată pe persoane autorizate.** Verificările sintetice, artifactele tehnice fără fețe și testele offscreen nu măsoară acuratețea pe oameni. Recomandarea principală este integrarea etapizată într-un branch temporar, precedată de stabilirea contractelor și corectarea lifecycle-ului P2/UI, apoi un pilot C/D/V autorizat. Nu este recomandată începerea unui clasificator de atenție în această săptămână.

### Surse și niveluri de încredere

- **VERIFIED**: citit sau executat în acest audit; dovada este indicată prin fișier/ref/commit/test/comandă.
- **REPORTED BUT NOT REVERIFIED**: consemnat anterior, fără repetarea experimentului în audit.
- **INFERRED**: interpretare a codului sau recomandare, explicit separată de un rezultat executat.
- **UNKNOWN**: nu există o dovadă accesibilă; nu înseamnă automat că activitatea nu a avut loc în afara repository-ului.

Statusurile taskurilor sunt `COMPLETED`, `PARTIALLY COMPLETED`, `IN PROGRESS`, `NOT STARTED`, `BLOCKED`, `NOT VERIFIED`. `COMPLETED` într-un task de infrastructură înseamnă satisfacerea acelui task software, nu validarea întregului produs. Nu s-au bifat checklisturile originale.

Sursele cerințelor:

| Cod sursă | Document / domeniu |
|---|---|
| SPEC | `Proiect_Analiza_atentiei_si_angajamentului_AI.md`, F1–F9, T1–T10 și §5–7 |
| PLAN | `docs/planning/00_START_AICI.md`, responsabilități și săptămânile relative 1–7 |
| P1 / P2 / P3 | Cele trei checklisturi `docs/planning/01_P1_Date_AI_saptamanile_1-7.md`, `02_P2_Motor_video_saptamanile_1-7.md`, `03_P3_Interfata_saptamanile_1-7.md`; **27 taskuri fiecare** |
| T04 | `docs/planning/04_Prompt_Codex_mini_template.md`; cere un șablon simulat, nu MVP complet |
| CLI | Cererea istorică din atașamentul `ae5f906b-18a0-49ac-b66c-20ef655d94d4/Pasted text.txt`; pipeline imagine/video, expresii, disponibilitate explicită a angajamentului |
| E1–E3 | Cererile din conversație pentru Face Landmarker, Head Pose și Eye Features; documentate și în README și `docs/face-landmarker-verification.md`, `head-pose.md`, `eye-features.md` |
| E4–E7 | Atașamentele cererilor: `ef762999-…` video, `b5bea94f-…` temporal, `803f2392-…` calibrare, `d5a304f9-…` dashboard; citite în audit |
| E8 | Cererea explicită Etapa 8 din conversație; protocolul implementat în `docs/real-world-evaluation.md` |
| GIT | Istoricul și conținutul branchurilor, nu doar mesajele commiturilor |

Atașamentele vechi din `Downloads` nu mai sunt disponibile la căile menționate; copiile de plan păstrate în repository sunt sursa verificabilă. PDF-urile disciplinei și `Plan_proiect_AI_responsabilitati_taskuri.md` citate de planuri nu sunt în arborii Git analizați: termenele lor originale sunt **UNKNOWN**, nu au fost deduse din referințe. Nu s-a reinterpretat conținutul extern al lucrărilor sau al documentației citate.

## B. Branch Inventory

Repository: `https://github.com/artiomonilov/Analiza-Atentiei-Proiect-PI`. Branch curent: `artiom-branch`. Principal: `main`, confirmat prin `git ls-remote --symref origin HEAD` și metadatele GitHub. La început lipsea simbolicul local `origin/HEAD`; aceasta nu face necunoscut branchul implicit remote.

Sunt **5 branchuri locale și 4 referințe remote**, reprezentând **6 tipuri distincte de arbore la vârf**. Toate sunt incluse mai jos. Referința `origin/ilie-p2` era inițial învechită la `86e5a90`; fetch-ul a adus `dfea4b2`. Celelalte vârfuri remote nu s-au schimbat.

| Branchuri analizate | Vârf / ultimul commit | Față de `main` | Conținut și scop efectiv | Teste executate / grad de finalizare |
|---|---|---|---|---|
| `main`, `origin/main` | `4379f098fd0c5e728436dacd22fa835e22b37c0a`, 17 oct., „Planificarea per saptamani” | Bază | Legacy, template simulat, planuri, 8 notebookuri; fără MediaPipe sau extensiile experimentale recente | **27 passed**; template verificat, MVP real incomplet |
| `artiom-branch`, `origin/artiom-branch` | `f4fcfc6b44a9011102964468d8840f7e241cd4d7`, 15 nov., „statistici pentru cap si irisuri” | 7 commituri înainte, 0 în urmă; 38 fișiere, +3550/−15 | CLI expresii, MediaPipe, pose, ochi, video, temporal; E6–E8 există suplimentar numai local | **143 passed** la commit; **223 passed** în working tree. Geometrie software avansată; integrarea P1/P2/P3 reală și validarea umană lipsesc |
| `ema`, `origin/ema` | `86e5a90138b311580e5df76c1f7d7c0de181fa72`, 2 nov. | 1 commit înainte, 0 în urmă; 1 fișier, +69/−3 | Formular ID/nume/sursă, selector de imagini, text explicit când predicția lipsește | **27 passed**, dar testele nu acoperă o cale reală în formular; incompatibilitatea este reproductibilă. Nu este UI multi-sursă finală |
| `origin/ilie-p2` | `dfea4b258f3bd2c9bef9c9cff606f8d14752406e`, 12 nov., „actualizare motor video” | 2 commituri înainte, 0 în urmă; 10 fișiere, +619/−80 | Include commitul Ema, apoi citire fișiere/imagine, YuNet, decupaje, tracking IoU, cozi per track, EOF după rezultatele restante | **26 passed, 1 failed**; nu sunt adăugate teste sau documente de contract. Cameră/rețea și predictor real lipsesc. Riscuri lifecycle/backpressure verificate |
| `ema-branch` (numai local) | `8142576297d7408d8938ce2677cbdc4d43d7320e`, 20 oct. | 2 commituri înainte; 4 fișiere | Numele nu dovedește lucru Ema: autorul Git este Artiom Onilov. Adaugă F8/F9, un experiment HF și `archive.zip` de **171396591 bytes** | Inspecție statică; experimentul folosește `inputs` nedefinit și descărcări. Nu s-au executat testele acestui snapshot |
| `backup-artiom-before-cleanup` (numai local) | `4c29422045ebc5eabbe3b87bbb29ccb6ddde0e43`, 2 nov. | 4 commituri înainte; 4 fișiere net | Linie istorică cu experiment HF, ștergerea arhivei la vârf; blobul mare rămâne în istoric | Inspecție statică; `tests/test_net.py` este identic cu cel actual. Nu este o sursă nouă de funcționalități de integrat |

Toate cele șase vârfuri au merge-base cu `main` la `4379f09`. `origin/ema` este strămoș al `origin/ilie-p2`; nu trebuie tratat ca încă o implementare independentă de adăugat după Ilie. Merge-base între Artiom și Ilie rămâne `4379f09`.

Istoric relevant Artiom: `6263173` bază fără arhiva mare → `b53e2fd` CLI/model → `6c2e44c` MediaPipe → `ad83d46` landmarker → `878a9f0` pose → `fea8d01` cameră/video → `f4fcfc6` cap/irisuri/temporal. Acestea sunt **etichete de commit și arbori verificați**, nu o certificare a activității experimentale.

### Fișiere diferite față de `main`

`origin/ema`: numai `src/audience_analysis/ui/main_window.py`.

`origin/ilie-p2`: `src/audience_analysis/{contracts.py,engine/controller.py,engine/scheduler.py,engine/workers.py,ui/history.py,ui/main_window.py,video/preprocessing.py,video/sequences.py,video/sources.py,video/tracking.py}`. Față de Ema, primele nouă modificări relevante sunt cele de motor/contract/video; UI este moștenită. Nu există diff în `tests/`, `pyproject.toml` sau `docs/contracts.md`.

`artiom-branch` — inventarul complet de 38 de căi:

```text
.gitignore
AGENTS.md
Proiect_Analiza_atentiei_si_angajamentului_AI.md
README.md
compare_blinks.py
configs/temporal.example.json
docs/STATUS.md
docs/contracts.md
docs/eye-features.md
docs/face-landmarker-verification.md
docs/head-pose.md
docs/temporal-analysis.md
docs/video-processing.md
models/README.md
pyproject.toml
run_video_analysis.py
src/audience_analysis/__main__.py
src/audience_analysis/engagement.py
src/audience_analysis/eye_features.py
src/audience_analysis/face_landmarker.py
src/audience_analysis/head_pose.py
src/audience_analysis/model_stats.py
src/audience_analysis/pipeline.py
src/audience_analysis/temporal_analysis.py
src/audience_analysis/terminal.py
src/audience_analysis/video_processor.py
src/audience_analysis/vision.py
start-analysis.ps1
test_face_landmarker.py
tests/ai/test_predictors.py
tests/terminal/test_eye_features.py
tests/terminal/test_face_landmarker.py
tests/terminal/test_head_pose.py
tests/terminal/test_pipeline.py
tests/terminal/test_temporal_analysis.py
tests/terminal/test_terminal.py
tests/terminal/test_video_processor.py
tests/test_net.py
```

`ema-branch`: SPEC, README, `archive.zip`, `tests/test_net.py`. Backup: `.gitignore`, SPEC, README, `tests/test_net.py`; arhiva nu mai apare în diff la vârf. Nu s-a extras sau executat arhiva. Nu există componente web/backend ascunse demonstrate prin aceste modificări.

### Working tree de păstrat

La început: **6 fișiere tracked modificate, 19 fișiere untracked** (numărate cu `git status --porcelain=v1 -uall`). Nu au fost pierdute sau integrate automat.

Tracked modificate: `README.md`, `compare_blinks.py`, `docs/contracts.md`, `run_video_analysis.py`, `src/audience_analysis/eye_features.py`, `src/audience_analysis/head_pose.py`.

Untracked: `calibrate_session.py`, `experimental_session.py`, `run_dashboard.py`, `run_validation.py`; `configs/{validation.example.json,experiment_V01.example.json}`; `docs/{calibration-validation.md,dashboard-validation.md,real-world-evaluation.md}`; `src/audience_analysis/{calibration.py,dashboard_data.py,experimental.py,validation.py,ui/experimental_dashboard.py}`; `tests/terminal/{test_calibration.py,test_dashboard.py,test_experimental.py,test_validation.py}`; `validation_dataset/README.md`.

Legea de conservare pentru integrare: nu se face checkout/reset/clean peste aceste fișiere. Mai întâi trebuie revizuite și păstrate într-un snapshot/commit aprobat de utilizator. Hashul codului aplicației la audit: `2e51603d2cbf78a469f416789068ddabe2f0cbfe6fb4ed3dd9d0154a8d8151d4`, calculat de `experimental.code_version()`; nu include documentația de audit.

### GitHub și taskuri externe

**VERIFIED** prin GitHub CLI API: repository public, branch implicit `main`, ne-arhivat; listele pentru issues (inclusiv closed), milestones și pull requests (toate stările) sunt `[]`. Nu au fost găsite deadline-uri sau asignări de taskuri în aceste surse. Nu s-a inspectat un GitHub Project separat și nu se presupune existența lui.

## C. Analiza AI — Task Completion Matrix

### Convenții pentru matrice

În P1/P2/P3, titlul scurt rezumă cerința exactă cu același ID din checklist, unde se găsește descrierea completă. Prioritatea **nu este specificată în sursa originală**; P0–P3 din §G este recomandarea auditului. Rolul P1/P2/P3 este documentat, responsabilul nominal nu este confirmat. Testele citate sunt cele din working tree, exceptând mențiunile explicite de branch.

Coduri de dovezi pentru a evita repetarea căilor:

| Cod | Fișiere / teste / rezultat |
|---|---|
| AI0 | `ai/{data.py,models.py,predictor.py}`: stubs explicite; `ai/fake_predictor.py`, `tests/ai/test_predictors.py`: simulare și erori, nu inferență de angajament |
| LEG-D | `dataset.py`, `experiment.py`, `tests/test_core.py`: manifest, split, duplicate, etichete, testele de bază trecute în audit |
| LEG-M | `models.py`, `experiment.py`, `tests/test_models.py`, `tests/test_experiment.py`: cod mean/GRU, export, R0 și evaluare; testele modelelor sunt blocate de `torchvision` în mediul actual, antrenarea nu s-a executat |
| CFG | `config.py`, `video/preprocessing.py`, `preprocessing.py`, `legacy_contracts.py`: două contracte/preprocesări, paritate reală absentă |
| GEO | `face_landmarker.py`, `head_pose.py`, `eye_features.py`, `vision.py`; `tests/terminal/test_{face_landmarker,head_pose,eye_features}.py` trecute |
| VID | `video_processor.py`, `run_video_analysis.py`, `tests/terminal/test_video_processor.py`; fișier/cameră mock, timpi, CSV și resurse testate |
| TEMP | `temporal_analysis.py`, `configs/temporal.example.json`, `compare_blinks.py`, `tests/terminal/test_temporal_analysis.py`: evenimente geometrice sintetice |
| CAL | `calibration.py`, `calibrate_session.py`, `tests/terminal/test_calibration.py`: profile neutre/EAR/iris și validări |
| VAL | `validation.py`, `run_validation.py`, `tests/terminal/test_validation.py`: metrici, periodicitate, scenarii, disponibilitate; vezi și constatarea R08 |
| DASH | `dashboard_data.py`, `ui/experimental_dashboard.py`, `run_dashboard.py`, `tests/terminal/test_dashboard.py`: CSV, grafice, adnotare, salvare/eliminare |
| EXP | `experimental.py`, `experimental_session.py`, `tests/terminal/test_experimental.py`, `docs/real-world-evaluation.md`: pachet fixat și roluri C/D/V |
| DOC | `docs/STATUS.md`, `docs/task04-verification.md`, README și documentația etapelor; afirmațiile istorice nu sunt automat reverificate |
| NB | 5 notebookuri în `notebooks/` și 3 în `notebooks/template/`: toate au `execution_count=null`, fără outputuri salvate; nu dovedesc execuție Colab |

### C1. Toate cele 27 de taskuri P1 — date și predictor

| ID | Cerință / titlu | Stare actuală | Dovadă, test și restanță concretă |
|---|---|---|---|
| P1-S1.1 | Acces și condiții DAiSEE | NOT VERIFIED | PLAN/SPEC conțin sursa; nu există dovadă de acces, licență acceptată sau inventar de date autorizate. Confirmare de către P1. |
| P1-S1.2 | Studiu DAiSEE și 2–3 lucrări | NOT VERIFIED | Există referințe generale în SPEC; nu un rezumat verificabil al studiului cerut. Adăugare bibliografie/metodă/limite. |
| P1-S1.3 | Patru dimensiuni și niveluri, început cu angajament | PARTIALLY COMPLETED | Contractul nou admite dimensiuni, dar LEG-D/LEG-M procesează numai engagement. Verificarea fișierelor DAiSEE și a etichetelor rămâne. |
| P1-S1.4 | Colab și exemplu P1 simulat | PARTIALLY COMPLETED | AI0 și exemplul P1 sunt testate local; NB nu dovedește pornirea Colab. |
| P1-S2.1 | Manifest clip/participant/etichetă/split | PARTIALLY COMPLETED | LEG-D trece teste sintetice; `ai/data.py` încă ridică `NotImplementedError`. Adaptor către contractul comun și manifest real. |
| P1-S2.2 | Separare participanți și clipuri | PARTIALLY COMPLETED | LEG-D respinge leakage/duplicate în fixture; separarea corpusului efectiv nu a fost verificată. |
| P1-S2.3 | Pregătire comună P1/P2 | PARTIALLY COMPLETED | CFG are funcție comună în template, dar legacy/model/Ilie nu au paritate demonstrată; alegerea configurației reale lipsește. |
| P1-S2.4 | Loader, MobileNet mean și reper majoritar | PARTIALLY COMPLETED | LEG-M implementează variantele istorice și R0; AI0 rămâne stub. Sunt necesare adaptorul PreparedSequence și verificarea loturilor. |
| P1-S3.1 | Antrenare baseline și pachet versionat | BLOCKED | Cod LEG-M există; lipsesc dovada datelor autorizate, modelul antrenat și aprobarea unui task de antrenare. Nicio antrenare în audit. |
| P1-S3.2 | Baseline vs R0, macro-F1/BA/confuzie | BLOCKED | Metricile sunt implementate în `metrics.py`/LEG-M; nu există rezultate reale etichetate. |
| P1-S3.3 | Predictor local real, încărcat o dată | PARTIALLY COMPLETED | Predictor legacy există, `ai/RealPredictor` nu este implementat; nu există pachet validat pentru motorul nou. |
| P1-S3.4 | Paritate Colab–local și traseu până la P3 | BLOCKED | NB fără execuție, lipsă pachet real și adaptare CFG/API. Nu este acoperită de succesul FakePredictor. |
| P1-S4.1 | Contribuție la 6–7 slide-uri | NOT VERIFIED | Niciun PPT/PDF de prezentare în arborii analizați. Activitatea externă este UNKNOWN. |
| P1-S4.2 | Exemple autorizate corecte și greșite | BLOCKED | Lipsesc modelul și etichetele independente. Nu înlocui cu fotografii fără ground truth. |
| P1-S4.3 | Model/configurație de demo fixate | BLOCKED | Există fixare EXP pentru geometrie, nu pachet de angajament. Alegerea țintei demo trebuie aprobată. |
| P1-S4.4 | Feedback AI transformat în taskuri | NOT VERIFIED | Nu există jurnal de feedback sau issues. Colectare și trasabilitate. |
| P1-S5.1 | MobileNet + GRU antrenat | PARTIALLY COMPLETED | LEG-M conține GRU, AI0 stub; nu există antrenare reală verificată. |
| P1-S5.2 | Comparație mean/GRU pe același split | BLOCKED | Cod de evaluare prezent; datele și rezultatele experimentale lipsesc. |
| P1-S5.3 | Boredom/confusion/frustration separate | NOT STARTED | LEG-M are un clasificator de 4 niveluri engagement, nu patru capete; `engagement.py` declară indisponibilitatea. |
| P1-S5.4 | Predare model actualizat și ieșiri | BLOCKED | Nu există pachet cu dimensiuni evaluate. Disponibilitatea trebuie exprimată fără niveluri inventate. |
| P1-S6.1 | Fixare pe validare și test final | BLOCKED | Nu există evaluare DAiSEE; protocolul C/D/V geometric nu substituie train/validation/test al modelului. |
| P1-S6.2 | Experiment rezoluție/decupaj | NOT STARTED | `default.json` și `no_margin.json` sunt configurații, fără comparație măsurată. |
| P1-S6.3 | Export, etichete și inferență pe laptop | PARTIALLY COMPLETED | LEG-M are bundle cu verificare numerică; testul curent de bundle blocat de torchvision; paritatea hardware/model real rămâne. |
| P1-S6.4 | Articol și poster: date/metodă/limite | NOT STARTED | Nu au fost găsite artifacte de articol/poster; DOC este documentație tehnică, nu articol. |
| P1-S7.1 | Pachet final notebook/config/weights/rezultate | PARTIALLY COMPLETED | NB și configurații există; lipsesc weights de angajament autorizate, rezultate și predare reproductibilă. |
| P1-S7.2 | Repetiție demo și model de rezervă | NOT VERIFIED | Nicio înregistrare/jurnal de repetiție identificat. |
| P1-S7.3 | Prezentare contribuții și comparații | NOT VERIFIED | Git dovedește commituri, nu prezentarea sau contribuțiile nominale complete. |

### C2. Etapele geometrice și cererile AI suplimentare

| ID audit / sursă | Cerință | Stare software | Teste/dovezi și ce lipsește |
|---|---|---|---|
| T04 | Contracte, FakePredictor, demo P1/P2/P3 explicit | COMPLETED | 27 teste pe `main`, documentație T04. Acest statut privește șablonul, nu MVP-ul real. |
| CLI-01 | Imagine/video, progres, selecție temporală, export JSON/CSV/log | PARTIALLY COMPLETED | `__main__.py`, `terminal.py`, `pipeline.py`, `tests/terminal/test_{terminal,pipeline}.py` trecute. `AnalysisResult.frames` păstrează toate rezultatele eșantionate; nu este memorie constantă pentru sesiuni nelimitate. |
| CLI-02 | Statistică ViT reală de expresii și cache | NOT VERIFIED | `model_stats.py` implementează inferență/cache/etichete; auditul nu a încărcat weights HF. Testele folosesc mocks, dependența torchvision absentă poate afecta calea reală. Fixarea reviziei modelului HF lipsește. |
| CLI-03 | Purple în terminal și launcher Windows | PARTIALLY COMPLETED | `__main__.py` are ANSI 95 numai pe TTY, `start-analysis.ps1` există; terminalul Windows interactiv nu a fost reverificat vizual în audit. |
| CLI-04 | Atenție/privire doar când există estimator valid | COMPLETED | `vision.MediaPipeHeadPose.estimate` returnează `unknown` cu geometrie; nu există clasificare nouă din praguri. Estimarea exactă a punctului privit nu este implementată. |
| CLI-05 | Model de angajament numai dacă disponibil | PARTIALLY COMPLETED | `UnavailableEngagementPredictor` este explicit; integrarea unui predictor real rămâne blocată de AI0/model. |
| E1 | Face Landmarker IMAGE, 478 repere, blendshapes, matrice | COMPLETED | GEO, script foto și teste; model local cerut explicit. Acuratețea pe populația țintă nu este validată. |
| E2 | Rotație din 4×4, yaw/pitch/roll, SVD și neutru | COMPLETED | GEO, matrici sintetice și convenții documentate. Lipsesc măsurători independente pentru erori reale în grade. |
| E3 | EAR, iris normalizat, calibrare și disponibilitate | COMPLETED | GEO, distanțe ajustate la dimensiunile imaginii, teste invalide/închidere. Ocluziile reale și generalizarea rămân NOT VERIFIED. |
| E4 | VIDEO/webcam sincron, timpi, CSV, overlay, resurse | PARTIALLY COMPLETED | VID verificat automat și software; webcamul fizic, latența și decodarea pe material real nu sunt reverificate. Nu este motorul multi-sursă P2. |
| E5 | Ferestre, mișcare, clipiri, histerezis, filtrare | PARTIALLY COMPLETED | TEMP și VID testate; evenimentele sunt nevalidate experimental, nu fixații/saccade/atenție. |
| E6 | Calibrare și metrici cantitative compatibile | PARTIALLY COMPLETED | CAL/VAL și referințe sintetice; colectarea reală lipsește. R08 descrie limita API-ului final. |
| E7 | Dashboard local, adnotări, export, management | PARTIALLY COMPLETED | DASH și Qt offscreen; verificările video reale/manuale pe Windows rămân. Nu înlocuiește UI de operare multi-sursă P3. |
| E8-01 | Manager C/D/V, ID/config/dată/durată/referințe | COMPLETED | EXP/DASH; snapshoturi locale fără copiere automată a video. Datele personale nu sunt cerute. |
| E8-02 | Protocol neutru/mișcare/ținte/clipiri/lumină/absență | COMPLETED | `docs/real-world-evaluation.md` are procedura și comenzile; colectarea este o activitate separată, încă nevalidată. |
| E8-03 | Configurație fixată după D, proveniență V | PARTIALLY COMPLETED | EXP verifică cod/model/mediu/parametri și reutilizarea raw D. Protecția C raw și API-ul de nivel jos sunt incomplete; vezi R08–R09. |
| E8-04 | Ground truth independent, clipiri/absență/condiții | COMPLETED | DASH/EXP, CSV separat, fără generarea manualelor din predicții; necesită adnotatori reali. |
| E8-05 | Metrici justificate și rezultate pe scenarii | COMPLETED | VAL: coverage, P/R/F1, timing, dispersii, lipsuri; MAE/RMSE fără referințe rămân N/A. Validitatea statistică pe oameni rămâne neconfirmată. |
| E8-06 | Panou C/D/V, grafice și N/A | COMPLETED | EXP/DASH și test Qt; screenshot tehnic anterior există. Nu echivalează cu acceptarea ergonomică manuală. |
| E8-07 | Metadata reproducere și ștergere gestionată | PARTIALLY COMPLETED | EXP, `SessionStore.delete`; păstrează căi locale la salvare explicită, nu șterge toate originalele/rapoartele. Nu există criptare/ștergere securizată. |
| E8-08 | Evaluare experimentală real-world | BLOCKED | Nicio serie autorizată C/D/V cu adnotări independente nu a fost demonstrată. Necesită date, consimțământ, protocol și criterii de acceptare. |

### C3. Cele cinci niveluri de finalizare

| Familie | Implementare tehnică | Testare automată actuală | Validare manuală | Date reale | Integrare generală |
|---|---|---|---|---|---|
| Template | COMPLETED pentru simulare | VERIFIED: 27 pe baza main | Istoric raportat, audit offscreen | Nu se aplică demo-ului | Traseu simulat integrat |
| Predictor angajament | Legacy prezent, ai/ stub | Fake și contracte VERIFIED; modele BLOCKED în mediu | UNKNOWN | NOT VERIFIED | NOT STARTED pe contractul nou |
| MediaPipe/pose/ochi | Implementat | VERIFIED în 223 teste | Fotografii/GUI raportate anterior, nerepetate în audit | Acuratețe NOT VERIFIED | CLI geometric, fără engine P2 |
| Video/temporal/calibrare | Implementat local | VERIFIED sintetic/mocks | Hardware/clip real NOT VERIFIED | Metrici reale lipsă | Pipeline sincron separat |
| Dashboard/C/D/V | Implementat necomis | VERIFIED în 223 teste | Randare anterioară raportată | Pilot BLOCKED | Nu este UI multi-sursă P3 |

## D. Global Project Task Matrix

### D1. Cele 27 de taskuri P2 — motor și video

Pentru aceste rânduri, `ENG` înseamnă `engine/{controller,scheduler,workers}.py` și `tests/engine/`; `P2R` înseamnă conținutul `origin/ilie-p2` verificat la `dfea4b2`. `P2R` nu este încă în working tree-ul Artiom.

| ID | Cerință / titlu | Stare | Dovezi / teste / restanță |
|---|---|---|---|
| P2-S1.1 | Citire video, durată, rezoluție, timp | COMPLETED | VID și `tests/test_runtime.py` trecute cu video sintetic; hardware real separat. |
| P2-S1.2 | Detecție facială și limite | COMPLETED | YuNet legacy/vision/P2R și MediaPipe GEO, documentate fără identitate. Politicile de selecție diferă. |
| P2-S1.3 | Traseu sursă–secvență–coadă–predictor | PARTIALLY COMPLETED | ENG funcționează simulat; P2R are fișiere reale; lipsește predictorul compatibil. |
| P2-S1.4 | Proprietate P2 pentru lucrători și comenzi | COMPLETED | PLAN, EngineCommands și ENG; UI nu importă captura. Aprobarea nominală a echipei este UNKNOWN. |
| P2-S2.1 | Mesaje source/run/request/interval | PARTIALLY COMPLETED | `contracts.py` și teste comune; P2R adaugă track_id și toleranță la constructor fără actualizarea documentației/testelor. |
| P2-S2.2 | Citire fundal, istoric limitat, ultim preview | PARTIALLY COMPLETED | ENG/legacy și P2R; realizat software, oprirea unui backend blocat în QThread nu este garantată. |
| P2-S2.3 | Pregătire comună/selectare în timp | PARTIALLY COMPLETED | CFG și `tests/video/test_preparation.py`; la P2R timpi nominali index/FPS, fără paritate reală cu modelul legacy. |
| P2-S2.4 | Cozi și înlocuire fără blocare | COMPLETED | ENG curent simulat și `tests/engine/test_scheduler.py`; schimbarea P2R necesită acceptare separată. |
| P2-S3.1 | Video/detecție/decupaj/secvențe reale | PARTIALLY COMPLETED | P2R implementează; testul adaptorului eșuează pentru așteptare veche, lipsesc teste noi; VID separat nu finalizează integrarea ENG. |
| P2-S3.2 | O cerere în așteptare/sursă și un AI worker | PARTIALLY COMPLETED | ENG curent respectă capacitatea 1; P2R schimbă în 1/track, probează 100/sursă. Alegere de contract obligatorie. |
| P2-S3.3 | Asociere răspuns și erori | PARTIALLY COMPLETED | Gate testează run/request în demo; P2R are defectul de contabilizare cross-run R03 și UI respinge realul. |
| P2-S3.4 | Start/stop/restart, eliberare | PARTIALLY COMPLETED | Teste ENG/VID/legacy trecute; P2R necesită verificare EOF/restart cu request_id reutilizat și backend blocat. |
| P2-S4.1 | Demo valid/no-face/insuficient/EOF | PARTIALLY COMPLETED | Cazuri sintetice verificate; demo cu model real și material autorizat absent. |
| P2-S4.2 | Explicație istoric/coadă/apel AI | COMPLETED | `docs/contracts.md`, `engine/README.md`, exemplul P2; documentația P2R trebuie actualizată la noua coadă. |
| P2-S4.3 | Timpi așteptare/calcul separați de media | PARTIALLY COMPLETED | Câmpuri `queue_wait_ms`/`inference_ms` testate; lipsesc măsurători reprezentative hardware finale. |
| P2-S4.4 | Feedback și corecții critice | NOT VERIFIED | Fără jurnal/issue-uri; constatările auditului sunt taskuri propuse, nu feedback istoric confirmat. |
| P2-S5.1 | Cameră și un flux de rețea verificat | PARTIALLY COMPLETED | VID are webcam; legacy are network cu timeout. P2R refuză camera/network; flux real nevalidat. |
| P2-S5.2 | Surse separate și alternare AI | PARTIALLY COMPLETED | ENG și teste cu două surse; P2R adaugă fețe, necesită fairness și limitare sub încărcare reală. |
| P2-S5.3 | Înlocuire, contoare, preview unic | PARTIALLY COMPLETED | ENG testat; P2R fără limită totală/cleanup de pending-track demonstrată. |
| P2-S5.4 | Deconectare/reconectare/eliminare | PARTIALLY COMPLETED | Stop/remove demo și runtime legacy există; cameră/rețea P2R și reconectarea controlată lipsesc. |
| P2-S6.1 | Suprasolicitare și memorie limitată | PARTIALLY COMPLETED | Teste scheduler/demo prezente; proba R04 arată că limita pe sursă nu mai este garantată în P2R. |
| P2-S6.2 | Oprire în calcul, restart rapid, late results | PARTIALLY COMPLETED | Testele curente trec; proba R03 identifică un caz cross-run neacoperit pe P2R. |
| P2-S6.3 | Experiment preprocesare cu P1 | NOT STARTED | CFG are alternative, fără comparație măsurată comună. |
| P2-S6.4 | Test 10 minute, timpi/memorie, raport | NOT VERIFIED | DOC îl păstrează neexecutat; nu există dovadă verificată de stabilitate pe laptopul final. |
| P2-S7.1 | Surse prezentare și video local de rezervă | NOT VERIFIED | Clipurile tehnice nu sunt demo autorizat cu rezultate reale. Materialele externe sunt UNKNOWN. |
| P2-S7.2 | Documentarea comenzilor, mesajelor și limitelor | PARTIALLY COMPLETED | DOC/ENG/VID există, dar nu descriu fidel toate schimbările P2R și măsurătorile finale. |
| P2-S7.3 | Prezentarea motorului și opririi | NOT VERIFIED | Codul nu dovedește demonstrarea în fața echipei/evaluatorului. |

### D2. Cele 27 de taskuri P3 — interfață și raportare

`UI` = `ui/{main_window,demo_engine,history}.py` și `tests/ui/`; `EMA` = commitul `86e5a90`, moștenit de P2R. Dashboardul experimental este o componentă distinctă de UI-ul de operare.

| ID | Cerință / titlu | Stare | Dovezi / teste / restanță |
|---|---|---|---|
| P3-S1.1 | Repository, acces, reguli, formular disciplină | PARTIALLY COMPLETED | GitHub și AGENTS există; accesul tuturor și formularul extern nu sunt demonstrate. |
| P3-S1.2 | Mediu Python și fereastră fără AI obligatoriu | COMPLETED | UI și PySide6 testate pe main/EMA; instalarea într-un mediu curat este o verificare separată. |
| P3-S1.3 | Schiță ecran configurare/control/istoric | COMPLETED | UI concretă și formular EMA; nu finalizează grila multi-sursă. |
| P3-S1.4 | Comenzi convenite cu P2 | COMPLETED | EngineCommands și injecție constructor; fără VideoCapture sau predictor în widgeturi. |
| P3-S2.1 | Formular SourceConfig/card și validare | PARTIALLY COMPLETED | EMA există, dar constructorul pozițional pentru cale e invalid pe EMA, compensat în P2R prin schimbare de contract. |
| P3-S2.2 | DemoEngine cu aceleași mesaje | COMPLETED | UI, `tests/ui/test_window.py`, 27 teste pe main/EMA. |
| P3-S2.3 | Preview/interval/stări/banner simulare | COMPLETED | UI testat; distinge erori de nivelul 0. |
| P3-S2.4 | Signal/Slot și actualizare pe firul principal | COMPLETED | UI/ENG și teste Qt; nu există widgeturi în worker. |
| P3-S3.1 | Selector videoclip și motor real | PARTIALLY COMPLETED | Selector EMA prioritizează imagini; P2R citește fișiere, dar intrarea principală rămâne demo și RealPredictor lipsește. |
| P3-S3.2 | Cadre/casete aferente și interval separat | PARTIALLY COMPLETED | Pachetele conțin casete, UI separă intervalul; nu desenează efectiv casetele/track_ids noi. |
| P3-S3.3 | Fără date/no-face/model lipsă/EOF | PARTIALLY COMPLETED | Stări demo sunt testate; statuturi noi P2R și rezultatele reale trebuie validate în UI, care filtrează `not is_demo`. |
| P3-S3.4 | Test comun start/stop/restart/resize și raport MVP | PARTIALLY COMPLETED | Teste software existente, fără raport end-to-end cu predictor real și laptop final. |
| P3-S4.1 | Prezentare comună 6–7 slide-uri | NOT VERIFIED | Niciun artifact de prezentare identificat în Git; externe UNKNOWN. |
| P3-S4.2 | Demo de evaluare cu model real | BLOCKED | Fără predictor real și date etichetate autorizate pentru MVP original. |
| P3-S4.3 | Laptop prezentare și instrucțiuni | PARTIALLY COMPLETED | README/launchere există; rularea pe laptopul final nu a fost reverificată. |
| P3-S4.4 | Feedback și repartizarea corecțiilor | NOT VERIFIED | Fără issues sau registru de feedback. |
| P3-S5.1 | Grilă și CRUD pentru 3–4 surse | PARTIALLY COMPLETED | Legacy oferă 4 carduri, test sintetic trecut; UI nouă rămâne o singură sursă, tracking nu este grilă de surse. |
| P3-S5.2 | Dimensiuni disponibile, stale, lipsă rezultate | PARTIALLY COMPLETED | UI iterează dimensiunile primite și separă intervalul; nu are predictor multi-head sau politică stale integrată pe noul motor. |
| P3-S5.3 | Istoric deduplicat din mesaje acceptate | COMPLETED | `ui/history.py` și teste UI/contracts; helperul funcționează, tabelul final lipsește. |
| P3-S5.4 | Export CSV complet fără secrete | PARTIALLY COMPLETED | Helperul CSV și export legacy testate; lipsește dialogul nou și schema track_id comună documentată. |
| P3-S6.1 | UI/resize/închidere în procesare | PARTIALLY COMPLETED | Teste offscreen, nu acceptare manuală; cazurile reale și lifecycle P2R rămân. |
| P3-S6.2 | Export normal/lipsă/eroare/simulat | PARTIALLY COMPLETED | Teste helper și legacy trecute; comparația end-to-end nouă cu un rezultat real rămâne. |
| P3-S6.3 | Instalare curată și README final | PARTIALLY COMPLETED | Test curat T04 doar raportat anterior; mediul actual are două OpenCV și nu are torchvision. README conține și formulări istorice depășite. |
| P3-S6.4 | Articol/poster/drepturi/demo rezervă | NOT STARTED | Nu sunt artifacte în Git; drepturile materialelor și activitatea externă sunt UNKNOWN. |
| P3-S7.1 | Verificarea pachetului final cu echipa | NOT VERIFIED | Nu există checklist validat de echipă; nu a fost bifat automat. |
| P3-S7.2 | Demonstrație UI/istoric/export | NOT VERIFIED | Testele automate nu dovedesc prezentarea efectivă. |
| P3-S7.3 | Prezentarea contribuției proprii | NOT VERIFIED | Autori Git identificați, responsabilități și contribuții complete neconfirmate. |

### D3. Specificația funcțională și taskurile comune

| ID / categorie | Tip în sursă | Stare | Implementare / gap / dependențe |
|---|---|---|---|
| F1 / T4 surse | Obligatoriu în ținta originală | PARTIALLY COMPLETED | VID: fișier/webcam; P2R: fișier; legacy: camera/network, fără verificare reală de rețea |
| F2 / T5 fețe și secvențe | Obligatoriu | PARTIALLY COMPLETED | Legacy respinge ambiguitatea, vision alege cea mai mare față, P2R urmărește toate; trebuie politică unică |
| F3 / T6–T7 cozi și motor | Obligatoriu | PARTIALLY COMPLETED | ENG testat, P2R are R03–R04, lipsește traseul real acceptat de UI |
| F4 / T1–T3 angajament | Obligatoriu în MVP original | BLOCKED | Model real/export/paritate/date autorizate lipsesc; trebuie decizie de scop pentru demo-ul curent |
| F5 ieșiri suplimentare | Țintă finală după evaluare | NOT STARTED | Nu există head-uri antrenate pentru cele trei dimensiuni suplimentare |
| F6 / T8–T9 UI surse/grilă/control | Obligatoriu | PARTIALLY COMPLETED | Legacy și UI nouă nu sunt integrate; formularul EMA incomplet |
| F7 / T10 istoric/export | Obligatoriu | PARTIALLY COMPLETED | Helpers/legacy verificate, experiența finală P3 de completat |
| F8 atent/neatent/oboseală | Cerință adăugată ulterior în SPEC; **în conflict cu direcția E2–E8** | NOT STARTED | E2–E8 interzic clasificarea atenției; DAiSEE din plan nu include oboseală. Clarificare de specificație, nu implementare acum |
| F9 voting „60 frames dintr-o secundă” | Cerință adăugată în SPEC, algoritm neprecizat | PARTIALLY COMPLETED | Selectarea după timp și ferestre există; nu există voting definit/evaluat. Numărul de cadre nu poate presupune 60 FPS pentru orice sursă |
| Mai multe persoane într-o cameră / imagine | Opțional în SPEC inițială | IN PROGRESS | P2R implementează tracking multi-față/imagine, fără teste dedicate sau aprobare de extindere a contractului |
| Contracte/config/preprocesare comune | Obligatoriu în PLAN/T04 | PARTIALLY COMPLETED | Dataclasses sunt comune în template; legacy, geometric și P2R încă diferă |
| Export reproductibil și metadate | Obligatoriu în E6–E8 | PARTIALLY COMPLETED | CSV/JSON, pachete și sidecaruri există local; trebuie o asociere coerentă între exporturile engine și laborator |
| Teste de integrare/build/instalare | Obligatoriu în checklisturi | PARTIALLY COMPLETED | Teste locale disponibile, fără CI identificat și fără instalare curată actuală; distribuția scripturilor root nu este entry-point instalat |
| Articol/poster/slide-uri/demo | Livrabile în PLAN/SPEC | NOT VERIFIED | Lipsesc artifactele în repository; nu există termen calendaristic verificabil pentru această săptămână |
| Backend HTTP, DB, autentificare | **Nu sunt cerințe identificate** | Nu se aplică | SPEC §5 cere obiecte Python locale și Qt, exclude explicit HTTP/FastAPI/Redis/serviciu Colab; nu propunem infrastructură web |
| Meet/Zoom și recunoaștere identitate | Excluse explicit | Nu se aplică | Nu se introduc la integrare; track_id este temporar, nu identitate biometrică |
| Procesare locală, autorizare și eliminare | Obligatoriu procedural în E4–E8 | PARTIALLY COMPLETED | Procesare locală și ștergere copii gestionate; consimțământul, registrul și ștergerea originalelor sunt sarcini ale operatorului |

## E. Completed Work

### E1. Verificări executate în audit

| Verificare | Comandă / izolare | Rezultat observat |
|---|---|---|
| Working tree | `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp artifacts/pytest-audit-current` | **223 passed in 29.97s** |
| Istoric sigur | `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_core.py tests/test_runtime.py --basetemp artifacts/pytest-audit-historical-safe` | **15 passed in 6.61s**; include 4 surse sintetice legacy, EOF, cleanup, manifest, metrici și export fără credențiale |
| Modele istorice — încercare | `... pytest ... tests/test_core.py tests/test_runtime.py tests/test_models.py -k 'not real_optimizer_step' ...` | **Eroare de colecție**, `ModuleNotFoundError: torchvision`; nu există rezultat „passed” pentru acea invocare |
| Snapshot main | `git archive main`, Python cu `PYTHONPATH=<snapshot>/src`, `python -m pytest -q -p no:cacheprovider --basetemp <snapshot>/test-temp` | **27 passed in 14.59s** |
| Snapshot Ema | Aceeași procedură, `origin/ema` | **27 passed in 17.32s** |
| Snapshot Ilie | Aceeași procedură, `origin/ilie-p2` | **26 passed, 1 failed in 14.92s** |
| Snapshot Artiom publicat | Aceeași procedură, `artiom-branch` | **143 passed in 16.76s** |
| Dependențe metadata | `.venv\Scripts\python.exe -m pip check` | `No broken requirements found`; nu verifică paritatea modelelor sau coliziunea fișierelor cv2 |
| Git/surse | status, branch/log, merge-base, diff, ls-tree, ls-remote, API GitHub | Inventarul din §B, fără modificarea branchului curent |

Mediu de test: `QT_QPA_PLATFORM=offscreen`, `PYTHONUTF8=1`, `PYTHONDONTWRITEBYTECODE=1`; pentru istorice/snapshoturi: `TEMP` și `TMP` în `artifacts/audit-temp`, iar Hugging Face în offline. Prima extragere în TEMP implicit a eșuat din permisiunile sandboxului; a fost reluată în directorul temporar al workspace-ului. Această eroare de mediu nu a fost numărată ca regresie a aplicației. Snapshoturile au fost verificate prin `audience_analysis.__file__` pentru a evita importul accidental al working tree-ului. Nu s-au creat branchuri/worktree-uri Git și nu s-au instalat pachete.

Selecția implicită din `pyproject.toml`: `tests/contracts`, `tests/ai`, `tests/video`, `tests/engine`, `tests/ui`, `tests/terminal`. **Nu s-a rulat toată colecția istorică.** `tests/test_net.py` execută operații HF/rețea la import și nu conține teste pytest izolate. `tests/test_experiment.py` și testul `test_real_optimizer_step_both_architectures_and_frozen_encoder` implică antrenare/optimizare; nu au fost lansate în audit, conform limitelor AGENTS. Restul testelor modelelor rămân blocate de dependența lipsă.

Eșecul P2R este precis: `tests/video/test_preparation.py::test_real_adapters_are_explicit` așteaptă `NotImplementedError` pentru un adaptor stub; adaptorul implementat ridică acum `FileNotFoundError` pentru `not-opened.mp4`. Este o **așteptare de test rămasă în urmă**, nu dovada că toate fișierele valide eșuează. Totuși, schimbarea nu este acoperită prin teste noi pentru fișiere reale și detector.

### E2. Rezultate anterioare și atribuirea contribuțiilor

- **REPORTED BUT NOT REVERIFIED**: cele 19 teste și captura desktop din `docs/STATUS.md` (11 oct.), mediul curat cu 27 teste din `docs/task04-verification.md`, fotografiile Landmarker/pose/ochi și testele tehnice MediaPipe ale etapelor anterioare. Auditul a reverificat subseturile și snapshoturile din E1, nu a reluat antrenările sau experimentele de cameră.
- **VERIFIED ca prezență/conținut, nu ca experiment reluat**: `artifacts/stage8-checked-frozen.json`, sidecarurile și raportul tehnic menționate în `docs/real-world-evaluation.md`. Documentația anterioară consemnează 20 cadre D și 10 cadre V fără fețe, profil C sintetic, rapoarte identice și screenshot Qt. Nu sunt date experimentale pe persoane.
- Istoricul Git atribuie commiturile Artiom lui **Artiom Onilov**, `86e5a90` lui **Ema Bruma**, `dfea4b2` lui **ilie**. Numele branchului `ema-branch` nu schimbă autorul Git al celor două commituri locale. Aceste metadate nu dovedesc cine a scris fiecare linie sau ce intervenții au fost asistate.
- Conform conversației, extensiile E6–E8 din working tree au fost realizate în sesiunile anterioare ale acestui asistent; fișierele și testele lor există și sunt acum reverificate. Nu sunt atribuite retroactiv commiturilor colegilor. Autorul uman și revizuirea echipei pentru modificările încă necomise rămân de confirmat.

## F. Missing & Incomplete Work

1. **Scopul produsului:** MVP de angajament DAiSEE din PLAN versus laborator de geometrie și validare din E2–E8. Ambele pot exista ca moduri distincte; succesul laboratorului nu finalizează F4/F5.
2. **Pachetul real P1:** `ai/RealPredictor`, loaderul nou și adaptoarele la model/preprocesare nu sunt implementate. Nu există rezultate reale mean/GRU și capete multiple evaluate.
3. **Motor P2 unificat:** fișierele P2R, timpii VID, estimatorii GEO și C/D/V nu sunt conectate într-un singur traseu de procesare cu proveniență comună.
4. **UI reală:** formularul explicit pentru video/cameră/network, rezultate `is_demo=False`, casete desenate și grila de 3–4 surse rămân incomplete în UI nouă.
5. **Validare umană:** lipsesc materiale C/D/V autorizate cu referințe independente, verificare între adnotatori și criterii de acceptare prestabilite. Fără acestea, acuratețea reală rămâne UNKNOWN.
6. **Livrare reproductibilă:** un mediu curat actual, model `.task` exact/documentat, revizie HF fixată, distribuție coerentă a scripturilor root și CI. Dependențele nu trebuie reparate în timpul unui V deja înghețat.
7. **Artifacte academice:** articol, poster, prezentări, feedback și demo de rezervă nu sunt identificate în Git. Deadline-urile absolute nu sunt documentate aici.
8. **Documentație divergentă:** STATUS menționează vechiul pipeline fără detecție; README spune că video „va necesita” VIDEO deși este deja implementat; documentele engine de pe P2R încă descriu capacitatea 1/sursă și stubs. `validation_dataset/README.md` nu include D01. Acestea necesită actualizări ulterioare aprobate, nu au fost corectate în audit.

## G. Weekly Implementation Plan — 16–22 noiembrie 2026

**Calendar recomandat, nu termene oficiale.** Planurile existente folosesc săptămâni relative 1–7 și trimit la L4/L7, fără o ancoră verificabilă în datele 16–22 noiembrie. Prioritățile și estimările de mai jos sunt propuneri ale auditului. Efortul este orientativ, în ore de lucru efectiv, fără timpul de obținere a acordurilor/datelor. Responsabilii sunt roluri din plan, nu asignări nominale inventate. Branchurile `codex/...` sunt numai propuse și nu au fost create.

| ID / prioritate | Componentă și branch propus | Stare la audit / lucru rămas | Dependențe / disponibilitate | Efort | Responsabil cunoscut | Acceptare | Calendar recomandat |
|---|---|---|---|---|---|---|---|
| W01 — P0 | Livrare E6–E8, `artiom-branch` | IN PROGRESS local; revizuire, inventar și păstrare într-un commit/snapshot aprobat | Imediat tehnic; commit numai la autorizare | 1–2h | Contribuitorul branchului + reviewer; nominal de confirmat | Cele 25 de fișiere existente păstrate, sursă identificabilă, 223 teste, fără date/weights în Git | 16–17 nov. |
| W02 — P0 | Contracte comune, viitor `codex/integration-week-2026-11-16` | PARTIALLY COMPLETED; decide single-face/per-track, DTO geometric, timpi, SourceConfig explicit | Decizie comună P1/P2/P3 înainte de cod | 2–3h | P1/P2/P3 | Contract/document/test agree; unități, availability, IDs și limite definite | 17 nov. |
| W03 — P0 | Lifecycle P2, branch de corecții pornit din `origin/ilie-p2` | PARTIALLY COMPLETED; R03 cross-run și R04 limită totală | W02; lucru imediat după aprobare | 3–5h | P2 | Late completion din old run nu modifică new run; coadă/memorie limitată la churn și predictor lent; EOF sigur | 17–18 nov. |
| W04 — P1 | Formular/UI P3, aceeași bază Ilie care include Ema | PARTIALLY COMPLETED; R01/R02, fișiere video, real vs demo, casete | W02; predictor mock explicit pentru teste | 3–5h | P3 cu P2 | Cale validă/invalidă tratată controlat, real result afișat fără banner simulat fals; fără captură în UI | 18–19 nov. |
| W05 — P1 | Integrare geometrie în engine | NOT STARTED pe noul contract; adaptor GEO/TEMP și CSV/proveniență | W01–W03, model local; fără antrenare | 4–6h | P2 + responsabil geometrie de confirmat | O inferență MediaPipe/cadru procesat, aceleași rezultate ca CLI pentru fixture, cleanup și N/A corecte | 18–20 nov. |
| W06 — P1 | Teste/mediu/pachet, branch integrare | PARTIALLY COMPLETED; actualizează testul P2R, adaugă cazurile R01–R08 și verifică mediu curat | W02–W05; decizie OpenCV/Python | 3–5h | P1/P2/P3 pe module | Selecții relevante verzi, istoric sigur, fără rețea la colectare, launchere documentate; model absent explicit | 19–20 nov. |
| W07 — P1 | Pilot C01/D01, date locale | BLOCKED de autorizare/date/adnotatori | Acces și acorduri, W05/W06; nu se poate finaliza doar prin cod | 2–4h + colectare/adnotare | Operator/adnotator de desemnat | Materiale distincte, referințe manuale independente, registry anonim, acoperire și incertitudine raportate | 20 nov., condiționat |
| W08 — P1 | V01 independent și raport | BLOCKED până la W07 și configurație stabilă | Configurație/model/cod/mediu fixate; V nevăzut la tuning | 2–4h + adnotare | Operator/adnotator + reviewer de desemnat | Fără tuning pe V, P/R/F1 numai unde justificat, MAE angular N/A fără instrument independent, raport reproductibil | 21 nov., condiționat |
| W09 — P2 | Docs și demo integrat | PARTIALLY COMPLETED; harmonizare STATUS/README/contracte, drepturi, contribuții | Rezultatele W01–W08, decizie scop | 2–3h | P1/P2/P3 | Instrucțiuni testate, limite explicite, demo local fără surse pornite implicit, material rezervă autorizat | 22 nov. |
| W10 — P2 | Cameră, un flux rețea, 10 minute | PARTIALLY COMPLETED / NOT VERIFIED | Hardware și flux autorizat; lifecycle stabil | 3–5h | P2 + P3 | Stop/reconnect controlat; memorie/timpi/coverage măsurate 10 minute, fără credențiale în export | După W06; poate fi amânat |
| W11 — P3 | Predictor DAiSEE și dimensiuni noi | BLOCKED / NOT STARTED | Acces/licență/date, definiție scop, task separat de antrenare aprobat | Estimare după auditul datelor | P1 | Pachet, split, metrici și paritate independentă; nu o promisiune pentru 22 nov. | Nu se angajează un termen în această săptămână |
| W12 — P3 | Tracking multi-față/voting avansat | IN PROGRESS opțional / cerință ambiguă | Decizie F8/F9, capacitate și date | 2–4h doar analiză inițială | P2/P1, nominal neconfirmat | Specificație și teste înainte de integrarea ca funcție implicită | Backlog |

W01–W06 însumează aproximativ **16–26 ore**, repartizabile între roluri după stabilirea contractelor; nu sunt 16–26 ore independente de integrare/review. Pilotul și V sunt condiționate și nu trebuie grăbite pentru a produce metrici. Dacă acordurile sau hardware-ul lipsesc, livrabilul din 22 nov. rămâne un build tehnic verificat și protocolul, cu validarea reală explicit amânată.

## H. Cross-Branch Integration Matrix

| Sursă → destinație | Ce se conectează | Contract/API și dependențe | Riscuri Git / semantice | Teste de acceptare necesare |
|---|---|---|---|---|
| Working tree E6–E8 → branch publicat Artiom | Calibrare, validation, dashboard, C/D/V | Metodele `calibration_state`, `from_dict`, profil temporal, sidecaruri; PySide6/QtCharts, model local | Fișiere necomise omitibile; source hash se schimbă dacă se omit metodele auxiliare | Snapshot curat 223 teste; rulare CLI export/salvare/reîncărcare pe fixture |
| `origin/ema` → integrare | Formular și lipsă predicție | SourceConfig cu `kind` și `location` explicite | Nu integra separat dacă se folosește Ilie; formularul singur este incompatibil | Câmpuri goale, cale video/imagine, erori afișate, rezultat real și demo |
| `origin/ilie-p2` → integrare cu Artiom | Captură fișier, YuNet, QThreads/scheduler | `FramePacket.track_ids`, `InferenceRequest.track_id`, `PredictionResult.track_id`, statusuri noi; OpenCV opțional | Nu există overlap al fișierelor schimbate în cele două serii COMISE față de merge-base, dar R01–R07 rămân. Absența overlapului nu certifică merge curat sau compatibilitate | Contracte, timpi, per-source capacity, EOF/drain, restart în calcul, surse multiple, cleanup |
| GEO/TEMP/CAL → lucrător P2 | Caracteristici faciale din aceeași inferență | DTO separat pentru geometrie, `timestamp_ms`, calibrare explicită; nu se convertesc în levels 0–3 | Sincronul VideoProcessor nu trebuie pornit ca a doua captură în UI; YuNet și MP pot selecta fețe diferite | O singură captură și un detector MP/sesiune; same-frame/same-subject; comparație cu CLI și lipsă față |
| P2 → P3 | Preview, geometrie, stare, eventual predicție validată | Signal/Slot, ID/run/request/track, intervale; geometria separată de `ModelOutput.levels` | UI filtrează `not is_demo`, are un singur card și ignoră track_id; schema CSV se schimbă pe Ilie | `is_demo=False` acceptat în mod real, nu după stop; casetele apar pe cadrul potrivit; deduplicare |
| Export engine → DASH/EXP | CSV per cadru, evenimente și provenance | Schema VID și referințe la fișiere, timestamp media și origine; ferestrele AI rămân distincte | `PredictionResult` pe fereastră nu poate fi reinterpretat ca măsurătoare facială per cadru | Import/salvare/reîncărcare fără pierdere, conversie s↔ms, comparare C/D/V și N/A |
| LEG-M → `ai/RealPredictor` | Un viitor model real de angajament | Adaptor `[T,H,W,3] uint8 RGB` legacy → `[T,3,H,W] float32 RGB` nou, fără dublă normalizare; ordine dimensiuni și etichete | Clasele au aceleași nume dar semnături diferite; lipsă torchvision/model real | Paritate numerică pe același lot, model invalid/lipsă, fără fallback Fake, o încărcare |
| Legacy runtime/UI → produs | Reutilizare selectivă a logicii verificate | Procese de captură și contract generation versus QThreads/run_id | Nu se lansează simultan două motoare pentru aceleași surse; Qt shim PyQt5 nu este ținta nouă | Regresie legacy separată, timeout stop, test 4 surse, export fără credențiale |
| `ema-branch` / backup → orice integrare | Nimic nou recomandat automat | Experimente HF divergente, arhivă mare în istoric | Arhivă 171 MB; scriptul vechi cu inputs nedefinit; testul backup deja prezent în Artiom | Nu integra aceste ramuri fără o cerință specifică și selecție/revizuire separată |

### Incompatibilități concrete de contract și timp

| Aspect | Legacy | Template / P2R | Geometrie / EXP | Acțiune recomandată |
|---|---|---|---|---|
| Sursă | `SourceConfig(source_id,kind,location,participant_id)` | `SourceConfig(source_id,display_name,kind,location)`; P2R normalizează arbitrar un kind necunoscut în file | Path/int explicit în CLI | Constructori cu keyword, fără reutilizarea pozițională între clase |
| Continuitate | `generation` numeric | `run_id` nou și request_id pe rulare; P2R introduce track_id | CSV session_id plus frame_index | Mapare explicită și invalidare; identitatea unui subiect nu se deduce din track |
| Secvență | RGB uint8 `[T,H,W,3]`, normalizare în predictor | RGB float32 `[T,3,H,W]`, deja normalizată | Geometrie pe cadru BGR | Un singur contract de preprocesare pentru model, cu paritate testată |
| Timp | Secunde media, fallback FPS | Secunde; P2R folosește numai frame_id/FPS | Milisecunde strict crescătoare, origine POS_MSEC/fallback/monotonic | Conversie într-un adaptor, origine și mapare cadre păstrate; nu presupune VFR constant |
| Rezultat | Etichetă unică + scoruri, Status legacy | Dict de dimensiuni 0–3 + is_demo | Unghiuri/EAR/iris/availability și evenimente | Nu transforma geometria în scor de atenție sau ModelOutput fictiv |
| Configurație | PipelineConfig, 16×224/10 s, ImageNet | SequenceConfig demo, 4×24×32/0.6 s, mean 0/std 1 | TemporalConfig + profil + FrozenExperiment | Valorile demo nu sunt configurația unui model real |
| Pornire | `run.ps1` → `audience_analysis.app` | `python -m audience_analysis --demo/--ui-demo` | Root CLI foto/video/calibrare/validare/dashboard | Moduri documentate; o intrare de produs aleasă, fără activare implicită a surselor |

## I. Recommended Integration Architecture

Se păstrează **un singur pachet Python și contractele locale**, fără backend web sau baze de date. Separarea recomandată este operațională, nu o recreare a proiectului:

```text
P3: comenzi UI explicite / mod real sau demo
    ↓
P2: captură unică per sursă → timestamp + FramePacket
    ├─ ultimul preview limitat → UI
    ├─ etapă geometrică deținută de worker → FaceLandmarker (o instanță/sesiune)
    │      → HeadPose + EyeFeatures → TemporalAnalyzer → măsurători/evenimente
    │      → CSV + sidecar → DashboardSession / CalibrationManager / Validation
    └─ secvență validată → coadă limitată → unicul worker AI
           → Predictor P1 numai dacă este disponibil și compatibil
           → ResultGate (source,run,request[,track]) → UI / istoric / CSV

Experiment: C01 → profil → D01 → FrozenExperiment → V01 independent → raport
```

Diagrama este **INFERRED / propunere de integrare**, nu descrierea unei conexiuni deja implementate. Pasul geometric poate rula serial în workerul sursei în prima integrare; dacă măsurătorile justifică mutarea lui, se definește ulterior un buget explicit și o singură autoritate de scheduler. Nu se pune inferența în QTimer/UI și nu se creează o captură duplicată prin apelarea VideoProcessor peste sursa deja deschisă.

Pentru prima integrare se recomandă **o față selectată explicit per sursă**, conform MVP-ului inițial. Trackingul multi-față din Ilie rămâne opțional până la aprobarea contractului și a limitei totale de memorie. Dacă echipa alege păstrarea lui imediată, sunt obligatorii limita globală/per-sursă, expirarea trackurilor, izolarea calibrării/istoricului și afișarea clară; nu este suficient `track_id` adăugat în dataclass.

Geometria are un mesaj propriu cu availability și proveniență; `ModelOutput.levels` rămâne rezervat dimensiunilor unui model real evaluat sau simulării explicite. Când predictorul real lipsește, aplicația poate afișa geometrie și `MODEL_UNAVAILABLE` pentru angajament. Modurile de expresii existente rămân distincte și nu sunt activate automat în laboratorul E2–E8.

## J. Integration Roadmap

### Strategia principală: integrare etapizată într-un branch temporar

Compararea opțiunilor:

- **Merge clasic direct în main:** simplu textual, dar importă simultan schimbările de scheduler/UI necorectate; nerecomandat acum.
- **Cherry-pick selectiv:** util numai pentru corecții autonome testate; `dfea4b2` schimbă coordonat 9 fișiere și nu este un patch independent de contracte. Nerecomandat ca strategie principală.
- **Extragere amplă de module comune:** contractele există deja; o rescriere ar crește riscul fără să rezolve datele/modelul lipsă. Reutilizarea selectivă și adaptoarele sunt suficiente inițial.
- **Branch temporar cu integrare etapizată și gate-uri:** permite conservarea lucrului, verificarea fiecărei dependențe și un PR final revizuibil. **Aceasta este recomandarea.**

Pașii sunt propuși, **nu au fost executați**:

| Pas | Acțiune după aprobare | Criteriu de acceptare |
|---|---|---|
| 1. Conservare | Revizuiește cele 25 de fișiere locale; creează snapshot/commit aprobat și notează SHA-urile tuturor ramurilor | Nimic pierdut, fără date/cache/weights, sursele și testele locale disponibile reviewerilor |
| 2. Contracte | Aprobă scope geometric vs angajament, față unică/tracking, SourceConfig, DTO-uri și timp | Document și teste de contract actualizate împreună; lipsa datelor distinctă de zero |
| 3. Dependențe | Pregătește mediu izolat verificat, o singură distribuție OpenCV, model `.task` exact | Instalare reproductibilă, `pip check`, smoke Qt/OpenCV/MP fără download implicit; Python țintă confirmat |
| 4. Branch integrare | Creează, după autorizare, `codex/integration-week-2026-11-16` din main identificat, apoi adu baza Artiom revizuită | Branchuri originale intacte, baseline testată înainte de componente noi |
| 5. Pregătire P2/P3 | Corectează pe o ramură de lucru pornită din Ilie R01–R07 și testul stale; nu adăuga încă o copie a commitului Ema | Teste P2 și UI trecute, probe cross-run/backpressure/real-result adăugate |
| 6. Conectare | Integrează file reader/detector și adaptorul GEO/TEMP/CAL, apoi UI și exportul | O captură/sursă, date ale aceluiași cadru/subiect, 1 MP/sesiune, stop cooperativ și erori explicite |
| 7. Conflicte | Rezolvă semantic contractele/README/pyproject/launcherele; nu accepta automat „ours/theirs” | Semnături și scheme coerente, exemple funcționale, fără dublă normalizare sau scheduler duplicat |
| 8. Regresie și E2E | Rulează selecția integrată, istoricele sigure, apoi scenarii de fișier/lipsă model/no-face/EOF/restart/export | Nicio regresie justificată prin „test vechi”; teste înlocuite doar cu comportament acceptat și acoperire echivalentă |
| 9. Pilot și freeze | C/D pe build stabil, fixează codul/modelul/mediul, colectează un V independent | Proveniență validă, referințe independente și consimțământ, fără tuning pe V, metrici N/A unde nu există referințe |
| 10. Pregătire merge final | PR cu scopul final, diferențe, rezultate reale și limite; review de către echipă | Build curat repetabil, demo și rollback documentate; merge numai după aprobare |

**Rollback:** se păstrează branchurile sursă și SHA-urile preintegrare, profilele și artifactele experimentale în locațiile lor originale. Înainte de merge final se poate abandona branchul de integrare, fără reset/clean al lucrului utilizatorului. Dacă integrarea a fost publicată, rollbackul se face printr-un revert revizuit/aprobat, fără force push sau rescriere de istoric. Se revine la codul, mediul și modelul aferente pachetului experimental vechi; un raport V nu se reetichetează ca valid pentru alt cod. Exporturile noi se păstrează separat pentru trasabilitate.

## K. Risks & Blockers

Prioritățile sunt propuse pentru integrare. Fiecare constatare are domeniul verificării delimitat; nu a fost modificat codul pentru a o remedia.

| ID / prioritate | Constatare și dovadă | Impact și acțiune recomandată |
|---|---|---|
| R01 — P1 | **VERIFIED**, EMA `ui/main_window.py:116` apelează `SourceConfig(id,name,uri)`. Contractul din același branch interpretează al treilea argument drept kind. Proba cu o cale reală ridică `ValueError: Numele sau tipul sursei este invalid`. Constructorul este în afara try-ului UI | Formularul EMA independent nu configurează fișierul. Folosește keyword și validare tip/locație; nu ascunde generic toate ValueError ca „sursă duplicată”. Cele 27 teste nu acoperă acest caz |
| R02 — P0 pentru rezultat real | **VERIFIED prin inspecție**, EMA și Ilie `ui/main_window.py:151` resping `not result.is_demo`; `__main__.py` creează FakePredictor în modul demo, iar bannerul este permanent | Un predictor real conectat la motor nu va fi afișat de UI. Mod explicit real/demo și test cu `is_demo=False`; geometria nu se deghizează în predicție |
| R03 — P0 | **VERIFIED prin probă scheduler**, Ilie `engine/controller.py:109` cheamă complete înainte de gate, iar `scheduler.py:85` folosește numai source_id/request_id. Secvență: old run request 0 în calcul → activate new → new request 0 pending → complete old 0. `has_outstanding` devine False deși `pending_counts={'S':1}` | Posibil EOF prematur/invalidează rularea nouă. Complete trebuie legat de run_id și cererea efectivă. Proba verifică starea schedulerului; pierderea UI end-to-end rămâne de testat |
| R04 — P0 | **VERIFIED prin probă**, Ilie `scheduler.py:64`: mailbox per track fără limită totală. 100 cereri cu trackuri distincte pentru aceeași sursă produc `{'S':100}` | Nu mai respectă contractul de capacitate 1/sursă; churn și predictor lent pot acumula secvențe. Decide limita globală/per-sursă și eliminarea trackurilor expirate. Nu este afirmată o măsurătoare de RAM real |
| R05 — P1 | **VERIFIED**, Ilie modifică contractele și motorul fără diff în teste/docs/pyproject; testul adaptorului eșuează. **VERIFIED** proba tracker: box la t=0, lipsă la 0.1, aceeași box la 1.0 păstrează ID 0 cu max_missed_s=0.5; matchingul precedă expirarea (`tracking.py:55,75`) | Teste lipsă pentru funcții reale, policy de gap/expirare ambiguă; expirare înainte de reasociere sau regulă explicită. Nu se afirmă recunoaștere biometrică |
| R06 — P1 | **VERIFIED**, Ilie `video/sources.py:69` folosește frame_id/fps; VID are FrameClock cu POS_MSEC/fallback/monotonic. FileSource face read în QThread fără timeout explicit | VFR/sincronizare referințe și stop pentru un read blocat sunt riscuri de integrare. Nu s-a demonstrat un hang în audit; sunt necesare teste și backenduri documentate |
| R07 — P1 | **VERIFIED prin cod**, UI afișează un singur preview fără desenarea face_boxes/track_ids; Ilie produce mai multe trackuri. Legacy respinge multi-față, vision selectează cea mai mare, MP folosește maximum una | Rezultatele pot fi atribuite unor subiecte diferite dacă se combină fără selecție comună. Politică single-face inițială sau tracking aprobat și testat; nu amesteca profilele/calibrările |
| R08 — P1 | **VERIFIED prin probă API sintetică**, `validation.py:192,215,270` verifică plan/rol/ID pentru final, dar `evaluate` nu leagă direct rows de hashul receiptului. Cu planul tehnic existent și rânduri modificate, `final_evaluation=True` este acceptat de API-ul de jos, deși hashul diferă | CLI și DashboardSession au verificări suplimentare și nu sunt declarate compromise de această probă. Centralizează guard-ul la intrarea finală sau documentează API-ul ca intern și impune wrapperul; adaugă test pe rows/events/model/code |
| R09 — P1 | **VERIFIED prin structură**, EXP păstrează hashurile înregistrărilor D, profilul C păstrează ID-uri, nu hashurile raw C. `validate_source` verifică V contra D; webcam nu are hash raw | Reutilizarea aceluiași material C sub alt ID sau re-encodarea unei înregistrări nu este prevenită automat. Registru procedural și, dacă aprobat, proveniență C; hashurile nu sunt dovadă împotriva editării deliberate |
| R10 — P0 procedural | **VERIFIED**, E6–E8 au 19 fișiere untracked și 6 tracked modificate; colegii nu le primesc prin `origin/artiom-branch` | Pierdere/omisiune la integrare. Conservare și review înainte de orice schimbare de branch. Nu se face commit automat |
| R11 — P1 | **VERIFIED**, Python 3.13.2; NumPy 2.5.4; PySide6 6.12.0; pytest 9.1.1; pytest-qt 4.5.0; MediaPipe 1.2.0; torch 2.15.0; transformers 5.20.2; torchvision absent. `opencv-python` și `opencv-contrib-python` sunt ambele 5.0.0.93 | Mediu diferit de `requirements-lock.txt` și de ținta declarată 3.11/3.12; două distribuții dețin cv2. `pip check` nu certifică această coliziune. Reparare doar într-un mediu separat, fără perturbarea celui fixat pentru V |
| R12 — P1 | **VERIFIED**, istorice excluse implicit; `tests/test_net.py` descarcă model și imagine la import; pe ema-branch există și `inputs` nedefinit | Colecția generală nu este sigură offline și nu este o suită completă validată. Izolare script experimental/test, fără downloaduri în colectare; politica de antrenare rămâne explicită |
| R13 — P1 | **VERIFIED prin cod**, `models.py` este legacy cu normalizare proprie; `ai/RealPredictor` este stub, clase omonime de SourceConfig/PredictionResult au semnături diferite | Adaptoare și paritate obligatorii. Nici existența clasei EngagementModel, nici metadată `trained=True` nu dovedește validarea unui model real |
| R14 — P2 | **VERIFIED prin inspecție**, `pipeline.py:107,141` acumulează FrameResult în listă; YuNet/preprocesarea există în legacy, vision și P2R; două funcții `_end_message` aproape identice în workers Ilie, una în InferenceWorker fără utilizare identificată | Cost/memorie pentru sesiuni lungi și drift de implementări. Nu este demonstrat un bottleneck hardware; măsoară înainte de optimizare, reutilizează treptat |
| R15 — P1 | **VERIFIED prin inventar**, nu există CI/build/deployment definit în arborii analizați; scripturile noi sunt în rădăcină, entry points instalate sunt doar audience-analysis/audience-experiment | Rularea din alt cwd sau dintr-un wheel poate omite scripturile/documentele necesare. Test de instalare și o cale de pornire aleasă; nu presupune nevoie de cloud deployment |
| R16 — P2 | **VERIFIED**, toate cele 8 notebookuri au execution_count null și fără output; documentația conține promisiuni istorice neactualizate | NB nu dovedește Colab sau antrenare. Revizuirea docs și paritatea efectivă rămân; nu genera outputuri fictive |
| R17 — P1 | **VERIFIED prin cod**, salvarea explicită SessionStore păstrează căi absolute la CSV/video; model_stats folosește MODEL_ID fără revizie fixată; source hash EXP include și UI/root scripts | Manifestele pot conține numele utilizatorului din cale; dependențe/model/code noi invalidează V. Anonimizează directoarele, revizuiește exportul și fixează pachetul înainte de V |
| R18 — P0 pentru afirmații de performanță | **NOT VERIFIED**, date reale, consimțământ, referințe unghiulare independente, dezacord adnotatori, hardware/10 minute | Nu raporta acuratețe, robustețe sau validare pe oameni pe baza celor 223 teste. Pilot și protocol înainte de concluzii |
| R19 — P2 | **VERIFIED**, `ema-branch` include archive.zip de 171396591 bytes; backup îl șterge numai la vârf, nu din istorie | Nu integra ramurile istorice doar pentru nume; risc de a reintroduce blobul mare și experimente HF divergente. Nu s-a rescris istoria în audit |

Nu s-au constatat cerințe de autentificare, bază de date sau server web. Nu au fost căutate ori afișate credențiale. Secretele din URI-uri nu trebuie exportate; testele legacy verifică acest lucru pe fixture. Consimțământul și măsurile pentru minori rămân obligații procedurale ale experimentului; auditul nu constituie verificare juridică sau aprobare de colectare.

## L. Decisions Required

Înainte de modificări funcționale sau integrare, echipa/utilizatorul trebuie să decidă:

1. **Ținta livrabilului curent:** laborator geometric verificabil, MVP original cu angajament evaluat sau două moduri distincte. F4/F5 nu pot fi declarate gata prin schimbarea denumirii geometriei.
2. **F8/F9:** păstrare ca extensii viitoare sau revizuirea cerinței; fără clasificator de atenție în scope-ul actual. Definirea votingului numai dacă există un obiectiv și referințe valide.
3. **Politica de față și capacitate:** single-face MVP versus multi-track opțional, limită totală și schema ID-urilor; ownerul calibrării și criteriul de expirare.
4. **Contractele aprobate:** SourceConfig explicit, unitățile/originea timpului, DTO geometric separat, schema CSV și stările reale/demo/model absent.
5. **Baza integrării și conservarea locală:** autorizarea unui snapshot/commit al lucrului local și, ulterior, a branchului temporar. Nicio asemenea acțiune nu este executată de acest raport.
6. **Mediul suportat:** versiune Python, o distribuție OpenCV, versiuni Qt/MP/Torch și revizia/modelul local. Nu se remediază mediul validării prin upgradeuri neconsemnate.
7. **Responsabili nominali:** rolurile P1/P2/P3 sunt documentate; desemnarea adnotatorilor, operatorului, reviewerului și coordonatorului de integrare nu este confirmată.
8. **Accesul la date și acceptarea pilotului:** autorizare, materiale, referințe, număr de sesiuni și criterii de acceptare stabilite înainte de V. Deadline-urile academice reale trebuie confirmate din sursa instituțională.

## M. Next Actions

1. Revizuirea acestui audit și aprobarea scopului săptămânii; confirmați dacă demo-ul urmărește geometrie sau angajament evaluat.
2. Conservarea celor 25 de fișiere locale existente printr-un snapshot/commit explicit autorizat, fără date sau ponderi.
3. Acord P1/P2/P3 asupra SourceConfig, DTO geometric, timestampuri, față unică/tracking și limita cozii.
4. Corectarea R03/R04 pe baza Ilie și adăugarea testelor cu restart în calcul și churn de trackuri.
5. Corectarea formularului și filtrului real/demo din UI; testare cu rezultate reale de fixture, fără simulare ascunsă.
6. Pregătirea unui mediu izolat reproductibil și actualizarea testului stale al adaptorului; păstrarea modelului local exact.
7. După autorizare, crearea branchului temporar și conectarea treptată a GEO/TEMP/CAL la motor, fără a dubla captura sau preprocesarea.
8. Rularea regresiei și E2E, inclusiv lipsa modelului, no-face, EOF, restart, CSV și snapshoturi C/D/V; verificarea API-ului final de validare.
9. Colectarea autorizată C/D și apoi V independent, cu adnotare manuală și fără metrici unghiulare inventate; amânare explicită dacă accesul lipsește.
10. Raport final de integrare cu rezultatele efectiv măsurate, limitele, contribuțiile confirmate și un PR pentru review; merge numai după aprobare.

### Comenzi de evidență Git folosite

```powershell
git status --short --branch
git status --porcelain=v1 -uall
git branch -a -vv
git log --graph --oneline --decorate --all -n 80
git remote -v
git ls-remote --symref origin HEAD refs/heads/*
git fetch --no-tags origin
git merge-base main origin/ilie-p2
git merge-base artiom-branch origin/ilie-p2
git merge-base --is-ancestor origin/ema origin/ilie-p2
git diff --stat main...origin/ilie-p2
git diff --name-status origin/ema...origin/ilie-p2
git show origin/ilie-p2:src/audience_analysis/engine/scheduler.py
git ls-tree -r --name-only origin/ilie-p2
git ls-tree -l ema-branch archive.zip
```

GitHub: `gh api repos/artiomonilov/Analiza-Atentiei-Proiect-PI`, apoi endpointurile `issues?state=all&per_page=100`, `milestones?state=all&per_page=100`, `pulls?state=all&per_page=100`, cu paginare. Au fost numai citiri; nicio postare sau comunicare către colegi. Raportul descrie exclusiv referințele accesibile și starea observată la data auditului.
