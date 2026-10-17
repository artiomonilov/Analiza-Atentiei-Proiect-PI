# Prompt Codex — mini-template pentru echipa de trei persoane

**Utilizare:** copiază în Codex blocul de mai jos, din folderul repository-ului. Păstrează cele trei fișe săptămânale în `docs/planning/`, ca agentul să poată lega TODO-urile de taskuri.

**Rezultatul cerut:** un singur proiect cu trei zone de lucru și exemple simulate independente. Acesta este un punct de pornire, nu aplicația cu model antrenat.

```text
Lucrezi în repository-ul unei echipe de trei studenți. Creează un schelet de proiect mic, clar și executabil, NU aplicația finală.

## 1. Context și limite

Proiect: „Analiza atenției și angajamentului audienței”.
Aplicație desktop integral în Python, cu PySide6.
MVP-ul ulterior: un videoclip cu un participant → detectarea feței → secvență de cadre → model AI antrenat → rezultat în interfață.
Versiunea finală urmărește 3–4 surse, cameră locală, un flux de rețea testat, istoric și CSV.

Acum creezi numai mini-template-urile, contractele și un traseu de test SIMULAT.
Nu antrena modele, nu descărca DAiSEE sau ponderi, nu activa camere și nu conecta fluxuri reale.
Nu implementa Meet/Zoom, API HTTP, FastAPI, Redis, bază de date, autentificare sau recunoașterea identității.
Nu pretinde că șablonul este MVP-ul cu AI real și nu inventa rezultate experimentale.

Înainte de modificări:
- Inspectează fișierele existente, README, AGENTS.md și git status.
- Citește fișele 01_P1, 02_P2 și 03_P3 din docs/planning/ dacă sunt prezente.
- Păstrează codul și modificările existente. Nu șterge, nu face reset și nu suprascrie documentația utilizatorului.
- Dacă proiectul are deja o structură compatibilă, adapteaz-o; nu crea un al doilea proiect paralel.
- Nu face commit/push automat și nu instala pachete global.

## 2. Responsabilități

P1 — AI:
date, modele, antrenare, evaluare, export, predict(sequence).
Nu citește surse, nu gestionează cozi și nu importă UI.

P2 — motor central și video:
captură, detectarea feței, preprocesare, secvențe, cozi, lucrători,
apelarea predictorului, validarea răspunsurilor și mesajele către UI.
Nu antrenează modelul și nu modifică widgeturi.

P3 — interfață:
controale, grilă video, afișarea stărilor și predicțiilor, istoric, CSV.
Nu apelează cv2.VideoCapture sau predictorul și nu implementează o a doua coadă AI.

P2 implementează preprocesarea comună, conform configurației convenite cu P1.
P1 o reutilizează la antrenare. Nu normaliza imaginile de două ori.

## 3. Structură propusă

Folosește un singur pachet, de exemplu:

README.md
AGENTS.md
pyproject.toml
.gitignore
configs/demo.json
docs/contracts.md
docs/planning/                       # păstrează fișele existente
notebooks/                          # 3 notebookuri-schelet pentru P1
src/audience_analysis/
    __init__.py
    __main__.py
    contracts.py
    config.py
    ai/
        README.md
        predictor.py
        fake_predictor.py
        data.py
        models.py
    video/
        README.md
        sources.py
        preprocessing.py
        sequences.py
    engine/
        README.md
        controller.py
        scheduler.py
        workers.py
    ui/
        README.md
        main_window.py
        participant_card.py
        history.py
        demo_engine.py
    examples/
        p1_predictor_demo.py
        p2_engine_demo.py
tests/
    contracts/
    ai/
    video/
    engine/
    ui/

Adaugă __init__.py unde este necesar; păstrează-le fără importuri care încarcă automat Qt, OpenCV sau PyTorch.
Comasează fișierele foarte mici; nu crea clase și straturi fără utilitate.
Documentația și mesajele UI sunt în română; identificatorii de cod sunt în engleză.
Folosește type hints, funcții mici și comentarii pentru deciziile neintuitive.

## 4. Contractele comune: înaintea implementării modulelor

Definește în contracts.py dataclasses și Protocol-uri, fără importuri PyTorch sau PySide6.
NumPy este permis pentru imaginile și secvențele schimbate între module.

Stabilește explicit:
- SourceConfig: source_id, nume afișat, tip și locație. Tipul demo este distinct.
- FramePacket: source_id, run_id, frame_id, media_time_s, imagine BGR uint8,
  casete de fețe aferente EXACT acelui cadru.
- PreparedSequence: frames, sample_times_s și preprocessing_id.
  frames este un NumPy float32 cu forma [T, 3, H, W], RGB, deja pregătit.
- InferenceRequest: source_id, run_id, request_id, window_start_s, window_end_s,
  queued_monotonic_s și PreparedSequence.
- ModelOutput: levels, model_version, is_demo.
  levels conține dimensiunile disponibile și niveluri întregi 0–3.
- PredictionResult: identificatorii și intervalul cererii, status, levels sau None,
  model_version, is_demo, queue_wait_ms, inference_ms și eventual un mesaj de eroare.
- SourceStatusEvent: event_id, source_id, run_id, status și mesaj.
  Acesta tratează și evenimente fără cerere AI, precum sfârșitul sursei.
- Predictor: predict(sequence: PreparedSequence) -> ModelOutput.

request_id crește în interiorul unei rulări; run_id este nou la fiecare pornire/resetare.
Nu folosi timpul din videoclip pentru măsurarea duratei calculului.
La eroare, levels este None; nu returna nivelul 0 ca substitut pentru o eroare.

SequenceConfig definește T, H, W, durata ferestrei, pasul și normalizarea.
Pentru demo poți folosi dimensiuni mici și ferestre scurte, marcate ca SIMULARE.
Valorile pentru modelul real vor proveni din configurația exportată de P1, nu din constante duplicate.
Documentează conversia BGR → RGB, scalarea, normalizarea, intervalele și semnificația statusurilor.

## 5. Mini-template pentru P1

Implementează:
- FakePredictor: răspuns determinist pentru verificarea integrării, is_demo=True.
  Datele sunt simulate, nu deduse din imagini. Nu folosi scoruri aleatorii prezentate drept AI.
- Scheletul RealPredictor, cu semnături și erori explicite până la implementare.
  Fără model real, nu face fallback automat la FakePredictor.
- Validarea formei intrării și a configurației, reutilizabilă de predictor.
- Schelete pentru citirea datelor și modelele baseline/GRU; lasă TODO clare.
- Trei notebookuri minimale: auditul datelor, antrenare/comparație, evaluare/export.
  Fără rezultate salvate fictive și fără căi personale hardcodate.
- Exemplu P1 care construiește o secvență sintetică și cheamă FakePredictor,
  fără Qt, cameră, OpenCV sau GPU.

README-ul P1 explică intrarea, ieșirea, comanda exemplului și locul de implementare.
Leagă TODO-urile de P1-S2.1, P1-S3.1, P1-S3.3 și P1-S5.1, când fișele sunt prezente.
Nu implementa antrenarea completă în această etapă.

## 6. Mini-template pentru P2

Creează o sursă sintetică ce produce imagini de test NumPy, fără oameni.
Sursa sintetică și pregătirea ei sunt selectate numai în mod demo.
Nu raporta detectarea unei fețe reale pe aceste imagini.
Lasă citirea video reală și detectorul de fețe ca puncte de extindere explicite;
apelarea unei funcții încă neimplementate trebuie să dea un mesaj clar.

Construiește traseul minim funcțional:
sursă sintetică → secvență → coadă → FakePredictor → PredictionResult.

Include:
- Istoric de cadre limitat pentru fiecare sursă, separat de coada AI.
- Alegerea cadrelor pe baza timpului; o copie stabilă a secvenței trimise.
- Maximum o cerere în așteptare per sursă, folosind Queue(maxsize=1)
  și sincronizare pentru operațiile compuse.
- O cerere mai nouă înlocuiește numai cererea care încă așteaptă.
  Nu întrerupe forțat calculul început.
- Un singur lucrător AI, care creează/încarcă predictorul o dată.
  Predictorul se injectează printr-o fabrică; controllerul nu depinde de clasa modelului.
- Preluare pe rând a cererilor surselor disponibile, cu test pentru două surse.
- Numărarea cererilor înlocuite și măsurarea așteptării și inferenței.
- Fără blocare în așteptarea spațiului din coadă și fără bucle busy-wait.
  Nu te baza pe empty()/full() pentru sincronizarea operațiilor compuse.
  Dacă utilizezi task_done(), contabilizează și cererile eliminate.
- Stop/reset: invalidează rularea, golește cadrele și cererile, ignoră rezultatele
  vechi. Nu emite predicții ca fiind active după stop sau eliminare.
- Respinge răspunsurile din alt run_id ori deja acceptate.
  Nu respinge un răspuns valid doar fiindcă între timp s-a format o cerere mai nouă.
- La o excepție a predictorului, emite un rezultat de eroare cu levels=None.

EngineController expune comenzi scurte:
add_source(config), start_source(source_id), stop_source(source_id),
remove_source(source_id), shutdown().

Comenzile nu execută captură, preprocesare sau inferență în firul UI.
Trimite rezultate/stări prin Signal către Slot-uri ale obiectelor UI.
Pentru previzualizare, păstrează ultimul FramePacket per sursă într-un spațiu limitat;
oferă take_latest_preview(source_id), fără a pune un semnal cu imagine pentru fiecare cadru.

Creează QApplication/QCoreApplication înaintea obiectelor Qt; nu crea QObject-uri globale la import.
Lucrătorii rulează cu QtCore/QThread, fără QtWidgets.
Oprirea trebuie să fie cooperativă și să poată fi cerută și când lucrătorul procesează.
Nu te baza numai pe un slot de oprire pus în event loop-ul ocupat de o buclă lungă.
Folosește Event/întrerupere verificată și eliberează resursele în finalizare.
Nu folosi terminate() și nu aștepta nelimitat în firul interfeței.

Furnizează un exemplu P2 fără fereastră, cu QCoreApplication, sursă sintetică
și predictor fals: afișează câteva rezultate și se oprește controlat.
Nu implementa acum toate adaptoarele video, reconectarea de rețea și optimizările;
lasă TODO pentru P2-S3 și P2-S5. README-ul explică cine deține fiecare fir și resursă.

## 7. Mini-template pentru P3

Construiește o fereastră mică, fără design complex:
- Un participant sintetic, pornire/oprire și previzualizare.
- Ultima predicție, intervalul analizat și starea tehnică.
- Banner permanent „SIMULARE — fără analiză AI reală”.
- O listă simplă de rezultate pentru verificarea fluxului.

UI primește motorul în constructor. Creează un DemoEngine separat, cu aceeași
interfață de comenzi și mesaje, pentru dezvoltarea P3 fără motorul real sau model.
Nu duplica schedulerul în DemoEngine: emite doar date de scenariu pentru UI.

Widgeturile, QPixmap și desenarea sunt gestionate în firul principal.
Folosește QTimer numai pentru citirea ultimului preview deja pregătit și afișare,
nu pentru citire video sau analiză AI.
Protejează durata de viață a bufferului NumPy când creezi QImage; nu lăsa imaginea
să indice către memorie care poate fi rescrisă/eliberată.

Rezultatul AI este separat de imaginea curentă și are propriul interval.
Nu îl redesena drept concluzie exactă pentru fiecare cadru nou.
Istoricul adaugă un rezultat o singură dată, după run_id/source_id/request_id.

Lasă locuri clare pentru formularul real, grila multi-sursă, tabelul complet
și exportul CSV. Un helper CSV minimal este permis; exporturile simulate
trebuie marcate, iar erorile trebuie să aibă celule goale pentru niveluri.

Oferă:
- python -m audience_analysis --ui-demo
  UI cu DemoEngine, fără model și fără video real.
- python -m audience_analysis --demo
  UI cu motorul P2, sursă sintetică și FakePredictor.

Niciuna nu este MVP-ul cu model real. Fără flag de demo, arată ajutor sau
mesajul „Modelul real nu este configurat”; nu porni implicit simularea.

## 8. Dependențe și teste

Țintește Python 3.11 sau 3.12, în funcție de mediul verificat.
Folosește pyproject.toml și instalare editable; fără modificări sys.path în cod.
Dependențe de bază: NumPy și PySide6.
Grupuri opționale: video = OpenCV fără ferestre proprii;
ai = PyTorch, Torchvision, scikit-learn; dev = pytest și pytest-qt.
Nu instala simultan două variante OpenCV cu același modul cv2.
Verifică versiunile disponibile/compatibile; nu inventa un lockfile „testat”.
Importurile de torch/cv2 sunt izolate: demo-ul și testele de bază nu le cer.

Scrie teste deterministe, fără dataset, model descărcat, cameră sau rețea:
1. Validarea formei și a identificatorilor din mesaje.
2. FakePredictor returnează rezultate marcate is_demo=True.
3. Calea predictorului real neimplementat nu întoarce predicții simulate.
4. Coada păstrează cel mult o cerere în așteptare per sursă și o înlocuiește corect.
5. Două surse sunt preluate pe rând, fără amestecarea datelor.
6. Un răspuns din rularea veche este ignorat după reset/stop.
7. O eroare de predictor nu devine o clasă validă.
8. Istoricul nu dublează rezultatele.
9. Test minimal UI: deschidere, comenzi și închidere, când mediul Qt permite.
10. Oprirea lucrătorilor și procesului de demo nu lasă fire active.

Folosește timeouturi și sincronizare explicită în teste, nu așteptări arbitrare lungi.
Nu marca drept trecute teste pe care nu le-ai executat.
Un smoke test offscreen nu echivalează cu verificarea vizuală pe Windows;
raportează separat ce ai verificat și ce necesită verificare manuală.

## 9. Documentare și verificarea livrării

README principal:
- scopul șablonului și diferența față de MVP;
- instalare locală, exemple de comenzi pentru Windows/PowerShell;
- cele două demo-uri UI și exemplele independente P1/P2;
- ce este implementat și ce rămâne de făcut;
- împărțirea P1/P2/P3 și trimitere la checklisturi;
- date autorizate, fără evaluarea reală a studenților.

AGENTS.md: scurt, cu structura, responsabilitățile, comenzile de test și regulile:
nu muta motorul în UI, nu duplica preprocesarea, nu ascunde mockurile,
nu schimba contractele fără actualizarea testelor/documentației.

.gitignore: medii virtuale, cache, date brute, modele mari, exporturi și secrete.
Nu exclude codul sau configurațiile mici necesare reproducerii.

Păstrează checklisturile nebifate. Crearea unui schelet nu finalizează sarcinile echipei.
Fiecare TODO spune ce intră, ce trebuie făcut, ce iese și cum se verifică.
Nu crea zeci de fișiere goale; urmărește cel mai mic exemplu executabil.

La final:
- Creează efectiv fișierele, nu oferi numai un plan.
- Rulează testele și exemplele permise de mediu.
- Rezumă structura, comenzile, rezultatele testelor și limitele.
- Arată pentru fiecare persoană primul fișier de citit și primul TODO de continuat.
- Nu implementa restul proiectului automat.
```

## Proveniență și alegeri tehnice

Rolurile și traseul provin din `Plan_proiect_AI_responsabilitati_taskuri.md`, secțiunile 4–5. Structura de fișiere, formatele exacte și modul de simulare de mai sus sunt propuneri de implementare pentru șablon.

Documentație consultată pentru instrucțiunile tehnice:
- OpenAI, „Custom instructions with AGENTS.md”: `https://developers.openai.com/codex/agent-configuration/agents-md`.
- OpenAI, „Best practices”: `https://developers.openai.com/codex/learn/best-practices`.
- Python, `queue`: `https://docs.python.org/3/library/queue.html`.
- Qt, „Threads and QObjects”: `https://doc.qt.io/qt-6/threads-qobject.html`.
- Qt for Python, `QThread`: `https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html`.

Limitarea cozii este oferită de bibliotecă; înlocuirea cererilor și alternarea surselor sunt reguli ale motorului propus, nu comportamente automate. Separarea lucrătorilor de widgeturi urmează regulile Qt. Alegerea modurilor de demo și a modulelor nu este o cerință a disciplinei.
