# Analiza atenției și angajamentului audienței

## 1. Ideea proiectului și MVP-ul

Construim o aplicație desktop, integral în **Python**, care primește surse video și afișează pentru fiecare participant nivelul de angajament estimat de AI.

**MVP:** încărcăm un videoclip cu un participant. Aplicația detectează fața, pregătește secvențe, le pune în coada de analiză și afișează predicțiile unui model antrenat. Putem porni și opri procesarea. Când imaginile nu sunt utilizabile, apare „date insuficiente”, nu „neatent”.

**La final:** țintim 3–4 surse simultane, fișiere video, cameră locală și un tip de flux de rețea testat. Adăugăm istoricul, exportul CSV și estimări separate pentru plictiseală, confuzie și frustrare, după antrenare și evaluare.

Folosim **DAiSEE**, care acoperă aceste patru dimensiuni, fiecare pe patru niveluri; oboseala nu este inclusă.[^date] Antrenăm în Colab, exportăm modelul și rulăm aplicația local. Nu includem Meet/Zoom, conturi sau recunoașterea identității. Mai multe persoane într-o singură cameră și analiza unei imagini rămân extensii opționale.


## 2. Tehnologiile folosite

| Tehnologie | Utilizare în proiect |
|---|---|
| **Python** | Întreaga aplicație. |
| **OpenCV + NumPy** | Citirea surselor, detectarea și decuparea fețelor, pregătirea imaginilor.[^opencv] |
| **PyTorch + Torchvision** | Modelul AI, antrenare și predicție locală. Pornim de la MobileNetV3 Small.[^model] |
| **Google Colab** | Pregătirea datelor, antrenare și evaluare. |
| **`collections.deque` + `queue.Queue`** | Istoricul recent de cadre și cozile limitate de cereri către AI.[^queue] |
| **`dataclasses` + `threading.Lock/Event`** | Formate comune de mesaje, sincronizarea datelor și semnalizarea opririi. |
| **PySide6 — QtCore** | Lucrători în `QThread` și comunicare prin `Signal`/`Slot`, fără blocarea interfeței.[^qt] |
| **PySide6 — QtWidgets/QtGui** | Ferestre, controale, grila video și afișarea rezultatelor. |
| **scikit-learn** | Metrici și matricea de confuzie.[^metrici] |
| **`csv`, Git și GitHub** | Exportul rezultatelor, cod comun și urmărirea contribuțiilor. |

## 3. Funcționalitățile aplicației la final

| Cod | Funcționalitate | Responsabil principal |
|---|---|---|
| **F1** | Citirea fișierelor, camerei și fluxului de rețea verificat. | P2 — OpenCV |
| **F2** | Detectarea feței, verificarea imaginilor și formarea secvențelor. | P2 — OpenCV, NumPy, `deque` |
| **F3** | Motor central: surse simultane, cozi, cereri către AI, răspunsuri și tratarea erorilor. | P2 — Python, `queue`, QtCore |
| **F4** | Estimarea angajamentului prin modelul încărcat local. | P1 — PyTorch, Torchvision |
| **F5** | Estimări separate pentru plictiseală, confuzie și frustrare. | P1 — PyTorch |
| **F6** | Adăugare/eliminare surse, pornire/oprire, grilă video și afișarea predicțiilor/stărilor. | P3 — PySide6 |
| **F7** | Istoric per participant și export CSV. | P3 — Python, PySide6, `csv` |


## 4. Taskurile fiecărei persoane

### P1 — Date și model AI · F4, F5

#### T1. Pregătirea datelor

**Traseu:** DAiSEE → verificarea etichetelor → seturi de antrenare, validare și testare.

Verifică accesul și condițiile de utilizare, citește etichetele, analizează numărul de exemple per clasă și verifică separarea participanților. Stabilește cu P2 formatul imaginilor și al secvențelor. Nu publică datasetul în repository.

**Tehnologii:** Python, Colab, NumPy, PyTorch. **Livrează:** notebookul de pregătire și încărcarea datelor pentru antrenare.

#### T2. Antrenarea și compararea modelelor

**Traseu:** secvențe pregătite → antrenare → validare → alegerea modelului.

Construiește varianta **MobileNetV3 Small + media caracteristicilor cadrelor**. O compară cu **MobileNetV3 Small + GRU**, care procesează succesiunea cadrelor. Începe cu angajamentul, apoi adaugă celelalte trei dimensiuni. Rezultatele fiecărei dimensiuni se evaluează separat; nu presupune că GRU va fi mai bun.

**Tehnologii:** PyTorch, Torchvision, Colab, scikit-learn. **Livrează:** modelele, configurațiile și rezultatele comparative.

#### T3. Modulul de predicție locală

**Traseu:** secvență primită de la P2 → model → nivelurile estimate.

Exportă modelul și scrie o interfață simplă, de exemplu `predict(sequence)`. Documentează numărul cadrelor, dimensiunea, ordinea culorilor, normalizarea și ordinea etichetelor. Verifică aceeași intrare în Colab și local. Modulul nu citește camere, nu gestionează coada și nu desenează interfața.

**Tehnologii:** PyTorch, NumPy, Python. **Livrează:** modelul, configurația și modulul `predictor`, utilizabile de P2.

### P2 — Motorul central, imagini și surse video · F1, F2, F3

#### T4. Citirea și controlul surselor

**Traseu:** comandă din interfață → deschiderea sursei → cadre cu identificator și timp.

Implementează adăugarea, pornirea, oprirea și eliminarea surselor. Începe cu un fișier, apoi adaugă camera și fluxul de rețea. Citește sursele independent, în afara firului interfeței. Pentru fișiere, respectă timpul videoclipului în demonstrație. Raportează sursele indisponibile, deconectările și sfârșitul fișierului; eliberează captura la oprire.

**Tehnologii:** OpenCV, Python, QtCore/QThread. **Livrează:** modulul de captură și controlul surselor.

#### T5. Pregătirea imaginilor și a secvențelor

**Traseu:** cadre → detectarea și decuparea feței → pregătire comună → secvență utilizabilă.

Păstrează într-un `deque` istoricul recent al fiecărei surse, fără să amestece participanții. Alege cadrele după timpul lor și verifică dacă fereastra conține suficiente imagini utilizabile. La lipsa feței, mai multe fețe în modul individual sau întreruperi, transmite o stare tehnică, nu o predicție inventată.

P2 implementează pregătirea imaginilor conform configurației stabilite cu P1; **P1 reutilizează același cod la antrenare**. Testează împreună efectul rezoluției sau al decupajului.

**Tehnologii:** OpenCV, NumPy, `collections.deque`. **Livrează:** preprocesarea comună și constructorul de secvențe.

#### T6. Coada și planificarea procesării

**Traseu:** secvențe gata → coadă limitată → lucrător AI → cererea următoare.

Construiește motorul care decide ce secvență este analizată și când. **Istoricul de cadre și coada AI sunt lucruri diferite:** primul formează secvențele, a doua păstrează cererile gata de procesat. Nu trimitem automat fiecare cadru către model. Secvența trimisă rămâne neschimbată până la terminarea analizei.

Ca variantă inițială, folosim **câte o coadă cu maximum o cerere în așteptare per sursă** și un singur lucrător AI, care preia pe rând cererile disponibile. Modelul este încărcat o singură dată în acest lucrător.

Dacă apare o secvență mai nouă, înlocuim cererea veche care încă așteaptă; nu întrerupem forțat calculul deja început. Această regulă se implementează explicit, nu este comportamentul automat al `Queue`.[^queue] Coordonăm operațiile concurente, nu blocăm captura și raportăm cererile înlocuite. Regula este pentru afișarea live, nu pentru eliminarea exemplelor din evaluarea modelului.

**Tehnologii:** `queue.Queue`, `threading.Lock/Event`, QtCore/QThread. **Livrează:** procesare ordonată, cozi limitate și măsurarea așteptării/calculului.

#### T7. Legătura cerere–răspuns și returnarea către UI

**Traseu:** cerere din coadă → `predictor` de la P1 → rezultat verificat → notificare către P3.

Apelează modelul, leagă predicția de sursă și de intervalul analizat și trimite rezultatul către interfață. Gestionează erorile modelului și împiedică un rezultat vechi să înlocuiască unul mai nou.

La oprire sau resetare, nu mai acceptă cereri pentru rularea veche, golește istoricul/cozile și ignoră răspunsurile întârziate. Folosește un identificator nou de rulare pentru a nu confunda două porniri ale aceleiași surse.

Trimite separat **cadre pentru previzualizare** și **predicții**. Păstrează doar ultimul cadru disponibil pentru afișare, nu un șir nelimitat de imagini neafișate.

**Tehnologii:** Python, `dataclasses`, QtCore/Signal. **Livrează:** motorul central cu comenzile și mesajele pe care P3 le conectează la interfață.

### P3 — Interfață, istoric și raportare · F6, F7

#### T8. Configurarea sesiunii și comenzile

**Traseu:** acțiune utilizator → verificarea formularului → comandă către motorul P2.

Construiește fereastra, selectorul de fișiere/cameră/flux, identificatorii participanților și butoanele de pornire, oprire și eliminare. Conectează aceste controale la interfața motorului. Nu deschide separat camerele și nu apelează modelul din funcția unui buton.

**Tehnologii:** PySide6/QtWidgets, Signal/Slot. **Livrează:** panoul de control conectat la P2.

#### T9. Afișarea video și a rezultatelor

**Traseu:** ultimul cadru și mesajele P2 → actualizarea cardului participantului.

Construiește grila pentru 3–4 surse și afișează predicțiile, intervalul analizat și stările tehnice. Desenează caseta feței folosind coordonatele aferente cadrului primit. Video-ul nu așteaptă terminarea AI; ultima estimare este afișată separat, cu intervalul ei, nu ca rezultat exact al cadrului curent.

Actualizează widgeturile numai în firul principal, prin mecanismele Qt.[^qt] **Modelul returnează etichete, nu un videoclip cu texte desenate; afișarea lor este responsabilitatea P3.**

**Tehnologii:** PySide6/QtWidgets, QtGui, QTimer, Signal/Slot. **Livrează:** grila funcțională și afișarea corectă a mesajelor.

#### T10. Istoricul, exportul și testarea interfeței

**Traseu:** rezultate acceptate de P2 → istoric per participant → tabel și fișier CSV.

Salvează identificatorii, intervalul, predicțiile și starea procesării. Adaugă fiecare rezultat o singură dată, nu la fiecare redesenare video. Implementează exportul, verifică butoanele și mesajele în timpul procesării și pregătește instrucțiunile de instalare. Testează cu P2 întârzierile și oprirea aplicației.

**Tehnologii:** Python, PySide6, `csv`. **Livrează:** istoric, export, teste de interfață și README.

## 5. Cum comunică modulele

Pentru această aplicație propunem obiecte Python locale, cozi și semnale Qt. Nu introducem HTTP, FastAPI, Redis sau un serviciu Colab.

```text
P3: utilizatorul apasă „Pornește”
  → P2: deschide sursa, citește cadrele și pregătește secvența
  → P2: pune cererea în coadă și o preia în lucrătorul AI
  → P1: modulul predictor analizează secvența și întoarce predicțiile
  → P2: verifică rezultatul și îl transmite pentru sursa corectă
  → P3: actualizează cardul și istoricul
```

**Cererea gestionată de P2:** `request_id`, `source_id`, `run_id`, începutul/sfârșitul intervalului și secvența. P2 transmite secvența funcției P1.

**Răspunsul către P3:** aceiași identificatori și interval, plus predicțiile, starea și durata procesării. La eroare, predicțiile lipsesc; nu sunt înlocuite cu nivelul zero.


## 6. Planul pe săptămânile 1–7

Numerotarea urmează secțiunea **„Desfășurare proiect”**, paginile 4–5 ale prezentării. Taskurile tehnice sunt propunerea echipei.[^calendar]

| Săptămâna / etapa | P1 — Date și AI | P2 — Motor central și video | P3 — Interfață și raportare |
|---|---|---|---|
| **1 — Organizare și documentare** | Verifică DAiSEE și studiază modele. | Studiază captura, detectarea feței și organizarea procesării. | Pregătește spațiul GitHub și schița UI. Împreună: echipa, tema și formularul. |
| **2 — Documentare și proiectare** | Pregătește datele și definește intrarea/ieșirea modelului. | Testează un videoclip; proiectează secvențele, cozile și mesajele. | Construiește ecranul; stabilește cu P2 comenzile și afișarea. |
| **3 — Prototip și evaluare** | Livrează și evaluează primul predictor real. | Implementează traseul complet pentru o sursă, inclusiv coada și răspunsul. | Conectează controalele și afișează rezultatele reale. Împreună: evaluarea MVP-ului și raportarea. |
| **4 — Prezentare intermediară** | Prezintă modelul și primele rezultate. | Prezintă preprocesarea, coada și erorile tratate. | Rulează demo-ul și slide-urile pregătite cu echipa; consemnează feedbackul. |
| **5 — Feedback și dezvoltare** | Compară GRU și antrenează ieșirile suplimentare. | Adaugă 3–4 surse, camera, fluxul de rețea și gestionarea întreruperilor. | Extinde grila, afișarea stărilor, istoricul și exportul. Toți aplică feedbackul. |
| **6 — Testare, evaluare și poster** | Fixează modelul și îl evaluează pe test. | Testează preprocesarea, suprasolicitarea, oprirea și rezultatele întârziate. | Testează aplicația completă și finalizează README-ul. Toți finalizează raportul, posterul și demo-ul de rezervă. |
| **7 — Prezentare finală** | Prezintă modelul și comparațiile. | Prezintă motorul, procesarea video și limitele. | Prezintă aplicația. Împreună: poster și demo cu cod funcțional. |


## 7. Ce verificăm 

**AI — P1:** date separate pentru antrenare, validare și test; verificarea suprapunerilor de participanți; fără cadre din același clip împărțite între seturi. Comparăm modelele și clasa majoritară prin macro-F1, balanced accuracy și matricea de confuzie.[^metrici]

**Motor — P2:** sursele nu se amestecă, cozile rămân limitate, erorile sunt raportate, iar oprirea/resetarea nu lasă rezultate vechi să apară într-o rulare nouă. Măsurăm timpul de așteptare, calculul, cererile înlocuite și ferestrele fără rezultat.

**Interfață — P3:** comenzile rămân utilizabile în timpul analizei, imaginile și rezultatele apar la participantul corect, intervalele sunt vizibile și exportul corespunde istoricului.

**Rezultat comun:** aplicație locală funcțională, model exportat, notebookuri, comparații experimentale, README, articol, poster și demo.

---

### Referințe

[^calendar]: `PI-P_săptămâna1.pdf`, pp. 4–5: organizare, documentare, prototip în săptămâna 3, demo intermediar în 4, dezvoltare/testare și poster în 5–6, prezentare finală în 7. Pagina 3 prezintă separat reperele 7–8/14; aici nu stabilim o echivalență între numerotări.
[^fisa]: `CTI.DD.317_PI_P_FD_2024_2025.pdf`, p. 2, „Termene limită și livrabile”: L4 și L7.
[^date]: DAiSEE, pagina autorilor: `https://people.iith.ac.in/vineethnb/resources/daisee/index.html`.
[^opencv]: OpenCV, VideoCapture: `https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html`. Compatibilitatea fluxurilor depinde de sursă și decodare; se testează tipul ales.
[^model]: Torchvision, MobileNetV3 Small: `https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.mobilenet_v3_small.html`. Arhitecturile comparate sunt alegerile proiectului.
[^queue]: Python, `queue`: `https://docs.python.org/3/library/queue.html`. Limita de capacitate este oferită de bibliotecă; înlocuirea cererilor și alternarea surselor sunt reguli pe care le implementăm.
[^qt]: Qt for Python, Signals and Slots: `https://doc.qt.io/qtforpython-6/tutorials/basictutorial/signals_and_slots.html`; Qt, Threads and QObjects: `https://doc.qt.io/qt-6/threads-qobject.html`.
[^metrici]: scikit-learn, Metrics and scoring: `https://scikit-learn.org/stable/modules/model_evaluation.html`.
