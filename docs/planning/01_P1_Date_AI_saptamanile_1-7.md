# P1 — Date și model AI

**Proiect:** Analiza atenției și angajamentului audienței.
**Responsabilitate:** F4–F5 / T1–T3: date, antrenare, comparații și predictor local.
**Tehnologii:** Python, Google Colab, NumPy, PyTorch, Torchvision și scikit-learn.
**Unde lucrezi în șablonul propus:** `src/audience_analysis/ai/`, `notebooks/`, `tests/ai/`.
**Nu preiei:** citirea camerelor, cozile, controlul surselor sau desenarea interfeței.

> Numerotarea 1–7 urmează „Desfășurare proiect”, pp. 4–5 din prezentare. Sarcinile de mai jos sunt detalierea propusă pentru echipă, nu cerințe tehnice citate din prezentare.

Bifează un task după verificare. Pentru fiecare săptămână păstrează în Git codul și o notă scurtă cu ce ai testat și ce nu funcționează.

## Săptămâna 1 — Organizare și documentare

**Scop:** Înțelegi datele și stabilești ce va prezice modelul.

- [ ] **P1-S1.1** — Verifică accesul și condițiile de utilizare pentru DAiSEE. Notează ce fișiere ai primit; nu încărca datasetul în GitHub.
- [ ] **P1-S1.2** — Citește descrierea DAiSEE și 2–3 lucrări relevante. Notează pe scurt datele folosite, metoda și limitele; păstrează sursele pentru raport.
- [ ] **P1-S1.3** — Identifică cele patru dimensiuni și nivelurile lor din fișierele efective. Prima versiune va prezice numai angajamentul; nu adăuga o etichetă de oboseală.
- [ ] **P1-S1.4** — Pornește mediul Colab și exemplul pentru P1 din șablon. Verifică schimbul de date cu predictorul simulat, fără să îl prezinți drept model antrenat.

**Livrezi:** Notițe despre date și metode, accesul la dataset verificat și mediul de lucru pregătit.
**Este gata când:** Poți explica ce primește modelul, ce estimează și ce nu poate demonstra.

## Săptămâna 2 — Pregătirea datelor și definirea modelului

**Scop:** Pregătești antrenarea și stabilești intrarea pe care o va trimite P2.

- [ ] **P1-S2.1** — Construiește lista clipurilor cu identificatorul participantului, etichetele și setul din care fac parte: antrenare, validare sau test. Verifică fișierele lipsă și etichetele nevalide.
- [ ] **P1-S2.2** — Verifică suprapunerile de participanți și clipuri între seturi. Nu distribui cadrele aceluiași clip în seturi diferite; documentează orice limitare a împărțirii primite.
- [ ] **P1-S2.3** — Stabilește cu P2 numărul de cadre, dimensiunea, ordinea culorilor și normalizarea. Folosește aceeași funcție de pregătire a imaginilor, nu o copie separată în notebook.
- [ ] **P1-S2.4** — Pregătește încărcarea secvențelor și arhitectura inițială: MobileNetV3 Small → media caracteristicilor cadrelor → clasificator. Definește și reperul care prezice clasa majoritară din antrenare.

**Livrezi:** Încărcarea datelor, configurația comună și notebookul pregătit pentru primul experiment.
**Este gata când:** Un lot de secvențe are forma și etichetele corecte și poate fi trecut prin model.

## Săptămâna 3 — Primul model real și evaluarea MVP-ului

**Scop:** Livrezi modelul care înlocuiește simularea din aplicație.

- [ ] **P1-S3.1** — Antrenează modelul inițial pentru angajament. Pornește cu extractorul vizual înghețat și salvează configurația, versiunea codului și ponderile.
- [ ] **P1-S3.2** — Evaluează pe validare modelul și reperul majoritar. Calculează macro-F1, balanced accuracy și matricea de confuzie; notează câteva erori reprezentative.
- [ ] **P1-S3.3** — Implementează predictorul local: încarcă modelul o dată, verifică intrarea și oferă `predict(sequence)`. La model absent sau intrare greșită, returnează o eroare explicită, nu rezultate simulate.
- [ ] **P1-S3.4** — Testează cu P2 aceeași secvență în Colab și local. Predă pachetul modelului și verifică împreună traseul până la interfața P3.

**Livrezi:** Predictor real, pachet de model și primele rezultate de validare.
**Este gata când:** Aplicația analizează un videoclip și afișează rezultatul modelului antrenat, nu al unui mock.

## Săptămâna 4 — Prezentare intermediară

**Scop:** Explici ce funcționează și ce mai trebuie îmbunătățit.

- [ ] **P1-S4.1** — Pregătește contribuția ta la prezentarea comună de 6–7 slide-uri: datele, modelul, rezultatele și limitele.
- [ ] **P1-S4.2** — Alege exemple autorizate cu predicții corecte și greșite. Nu raporta acuratețe pentru videoclipuri fără etichete de referință.
- [ ] **P1-S4.3** — Verifică modelul și configurația folosite în demonstrație. Evită schimbarea arhitecturii imediat înainte de prezentare.
- [ ] **P1-S4.4** — Notează feedbackul primit despre AI și transformă-l în sarcini pentru săptămânile 5–6.

**Livrezi:** Rezultatele intermediare, partea ta din slide-uri și lista de îmbunătățiri.
**Este gata când:** Poți reproduce experimentul prezentat și explica principalele greșeli ale modelului.

## Săptămâna 5 — Model temporal și stări suplimentare

**Scop:** Compari metodele și extinzi ieșirile modelului.

- [ ] **P1-S5.1** — Implementează și antrenează varianta MobileNetV3 Small + GRU, care procesează ordinea cadrelor.
- [ ] **P1-S5.2** — Compară modelele pe aceeași împărțire de date și cu aceeași pregătire a imaginilor. Alege configurația pe validare, nu pe setul de test.
- [ ] **P1-S5.3** — Adaugă ieșiri separate pentru plictiseală, confuzie și frustrare. Antrenează și evaluează fiecare dimensiune; nu înlocui etichetele lipsă cu zero.
- [ ] **P1-S5.4** — Predă modelul actualizat, lista ieșirilor disponibile și configurația. Confirmă cu P2 și P3 că dimensiunile încă neimplementate nu apar ca rezultate reale.

**Livrezi:** Comparație între modele și predictor extins, pentru dimensiunile efectiv antrenate.
**Este gata când:** Poți justifica alegerea modelului; fiecare stare afișată are o ieșire antrenată și o evaluare.

## Săptămâna 6 — Evaluare finală și documentație

**Scop:** Fixezi versiunea finală și măsori rezultatele fără schimbarea protocolului.

- [ ] **P1-S6.1** — Fixează configurația folosind validarea, apoi efectuează evaluarea finală pe test. Raportează rezultatele pe fiecare dimensiune și numărul de exemple evaluabile.
- [ ] **P1-S6.2** — Analizează cu P2 experimentul de preprocesare: rezoluție redusă sau decupaj diferit. Alege variantele pe validare; nu ajusta modelul după rezultatele finale de test.
- [ ] **P1-S6.3** — Verifică exportul, etichetele, normalizarea și rularea locală pe laptopul de prezentare. Documentează cum se reproduce inferența și ce fișiere sunt necesare.
- [ ] **P1-S6.4** — Scrie secțiunile despre date, metodă, experimente și limite pentru articol și poster. Nu inventa metrici pentru componente netestate.

**Livrezi:** Model final, rezultate comparative și secțiunile tale din raport și poster.
**Este gata când:** Un coleg poate încărca pachetul modelului și reproduce predicția pe intrarea de referință.

## Săptămâna 7 — Predare și prezentare finală

**Scop:** Predai modelul și explici contribuția ta.

- [ ] **P1-S7.1** — Verifică pachetul de predare: notebookuri, configurații, ponderi disponibile prin metoda autorizată și rezultate, fără publicarea datasetului.
- [ ] **P1-S7.2** — Repetă demonstrația cu echipa și confirmă versiunea modelului folosită în demo-ul de rezervă.
- [ ] **P1-S7.3** — Prezintă modelul ales, comparațiile și limitele. Arată clar ce ai implementat, ce ai reutilizat și ce a rămas nefinalizat.

**Livrezi:** Pachetul AI final și prezentarea contribuției personale.
**Este gata când:** Rezultatele din raport corespund exact modelului și experimentelor predate.

## Regula de colaborare

La sfârșitul săptămânii faci o integrare cu ceilalți doi membri. O schimbare a mesajelor sau a pregătirii imaginilor se discută înainte de modificare. Fiecare membru scrie și verifică partea sa din documentație.

**Bază:** `Plan_proiect_AI_responsabilitati_taskuri.md`, secțiunile 4–7; `PI-P_săptămâna1.pdf`, pp. 4–5; `CTI.DD.317_PI_P_FD_2024_2025.pdf`, p. 2, „Termene limită și livrabile”.

**Notă de calendar:** pagina 3 a prezentării are reperele 7–8/14. Acest checklist urmează exclusiv desfășurătorul 1–7 cerut; nu stabilește o echivalență între numerotări.
