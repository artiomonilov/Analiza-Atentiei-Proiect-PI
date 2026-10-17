# P3 — Interfață, istoric și raportare

**Proiect:** Analiza atenției și angajamentului audienței.
**Responsabilitate:** F6–F7 / T8–T10: comenzi UI, afișare, istoric, export și instalare.
**Tehnologii:** Python, PySide6 QtWidgets / QtGui / Signal / Slot / QTimer, `csv`, Git și GitHub.
**Unde lucrezi în șablonul propus:** `src/audience_analysis/ui/`, `tests/ui/`, README și integrarea punctului de pornire.
**Nu preiei:** citirea surselor, construirea secvențelor, gestionarea cozii sau apelarea directă a modelului.

> Numerotarea 1–7 urmează „Desfășurare proiect”, pp. 4–5 din prezentare. Sarcinile de mai jos sunt detalierea propusă pentru echipă, nu cerințe tehnice citate din prezentare.

Bifează un task după verificare. Pentru fiecare săptămână păstrează în Git codul și o notă scurtă cu ce ai testat și ce nu funcționează.

## Săptămâna 1 — Organizare și schița aplicației

**Scop:** Pregătești proiectul comun și modul de utilizare.

- [ ] **P3-S1.1** — Pregătește cu echipa repository-ul GitHub, accesul membrilor și regulile pentru taskuri și modificări. Echipa stabilește tema și completează formularul cerut.
- [ ] **P3-S1.2** — Configurează mediul Python și pornește o fereastră PySide6. Notează comenzile necesare, fără instalarea obligatorie a pachetelor AI pentru dezvoltarea interfeței.
- [ ] **P3-S1.3** — Schițează ecranul: configurarea surselor, pornire/oprire, card participant, predicție, stare tehnică și istoric.
- [ ] **P3-S1.4** — Stabilește cu P2 comenzile de care ai nevoie. Nu vei deschide camerele și nu vei chema predictorul din butoanele interfeței.

**Livrezi:** Repository comun, mediu funcțional și schița interfeței.
**Este gata când:** Fiecare coleg știe unde lucrează; fereastra poate fi pornită pe laptopul de dezvoltare.

## Săptămâna 2 — Interfață independentă cu date simulate

**Scop:** Construiești ecranul fără să aștepți modelul real.

- [ ] **P3-S2.1** — Implementează formularul sursei și cardul participantului. Verifică identificatorii și câmpurile introduse, fără să citești tu efectiv sursa video.
- [ ] **P3-S2.2** — Folosește motorul simulat din exemplul pentru UI: trimite comenzi și primește aceleași tipuri de mesaje ca de la motorul P2.
- [ ] **P3-S2.3** — Afișează previzualizarea, intervalul analizat și stările tehnice. Marchează vizibil modul «SIMULARE — fără analiză AI reală».
- [ ] **P3-S2.4** — Conectează semnalele la actualizarea widgeturilor în firul principal. Stabilește cu P2 ce mesaje primești la pornire, oprire și eroare.

**Livrezi:** Interfață utilizabilă cu un motor simulat și contract stabil cu P2.
**Este gata când:** Poți testa aspectul și comenzile fără dataset, model, cameră sau GPU.

## Săptămâna 3 — Integrarea MVP-ului real

**Scop:** Înlocuiești motorul simulat cu cel al P2.

- [ ] **P3-S3.1** — Conectează selectorul de videoclip și comenzile de pornire/oprire la motorul real. Nu muta în UI logica de captură sau de inferență.
- [ ] **P3-S3.2** — Afișează cadrele și caseta feței pentru cadrul primit. Afișează separat ultima predicție cu intervalul ei; nu pretinde că rezultatul descrie exact cadrul curent.
- [ ] **P3-S3.3** — Tratează mesajele «date insuficiente», «față nedetectată», «model indisponibil» și sfârșitul fișierului. Lipsa predicției nu trebuie afișată ca nivel zero.
- [ ] **P3-S3.4** — Testează împreună pornirea, oprirea, restartarea și redimensionarea ferestrei. Pregătește cu echipa raportarea intermediară a MVP-ului.

**Livrezi:** Aplicația MVP conectată la motor și predictor real.
**Este gata când:** Un utilizator poate încărca un clip, vedea rezultate reale și opri analiza fără blocarea ferestrei.

## Săptămâna 4 — Prezentare intermediară și demo

**Scop:** Pregătești demonstrația fără să ascunzi limitările.

- [ ] **P3-S4.1** — Asamblează cu colegii prezentarea comună de 6–7 slide-uri. Fiecare furnizează conținutul propriei componente.
- [ ] **P3-S4.2** — Verifică scenariul de demo: încărcare, pornire, rezultat, caz fără date și oprire. Confirmă că demo-ul de evaluare folosește modelul real.
- [ ] **P3-S4.3** — Testează rularea locală pe laptopul de prezentare și pregătește instrucțiuni scurte de pornire.
- [ ] **P3-S4.4** — Consemnează feedbackul și repartizează cu echipa corecțiile. Nu prezenta funcțiile simulate sau nefinalizate drept implementate.

**Livrezi:** Prezentarea comună, demo-ul MVP și feedback transformat în sarcini.
**Este gata când:** Demo-ul este repetabil, iar fiecare membru își poate prezenta partea.

## Săptămâna 5 — Grilă multi-sursă, istoric și export

**Scop:** Completezi experiența pentru 3–4 participanți.

- [ ] **P3-S5.1** — Extinde grila și controalele pentru 3–4 surse. Permite adăugare, oprire și eliminare individuală prin motorul P2.
- [ ] **P3-S5.2** — Afișează noile dimensiuni numai dacă predictorul le oferă. Distinge între estimare, rezultat vechi și lipsa rezultatului; nu inventa procente ale atenției.
- [ ] **P3-S5.3** — Implementează istoricul din mesajele acceptate, nu din redesenarea video. Folosește identificatorii cererii/rulării pentru a evita rândurile duplicate.
- [ ] **P3-S5.4** — Implementează exportul CSV: sursă, rulare, cerere, interval, niveluri, stare, versiune model și marcaj de simulare. La erori, nivelurile rămân goale; nu exporta adrese cu parole.

**Livrezi:** Interfață multi-sursă, istoric și export CSV verificabil.
**Este gata când:** Un rezultat apare o singură dată în istoric și în CSV, la participantul corect.

## Săptămâna 6 — Testarea aplicației și materialele finale

**Scop:** Finalizezi utilizarea, instalarea și raportarea.

- [ ] **P3-S6.1** — Testează butoanele, redimensionarea, mesajele de eroare și închiderea în timpul procesării. Verifică împreună cu P2 că UI rămâne utilizabilă și nu afișează rezultate din rulări eliminate.
- [ ] **P3-S6.2** — Verifică exportul pe cazuri normale, fără predicții, cu erori și cu date simulate. Compară rândurile exportate cu istoricul și evită amestecarea simulării cu rezultatele reale.
- [ ] **P3-S6.3** — Testează instalarea într-un mediu curat și finalizează README-ul: dependențe, model, rulare, demo și probleme cunoscute.
- [ ] **P3-S6.4** — Asamblează cu echipa articolul și posterul, verifică drepturile imaginilor folosite și înregistrează demo-ul de rezervă.

**Livrezi:** Aplicație testată, ghid de instalare și materialele finale complete.
**Este gata când:** Un coleg poate porni aplicația folosind README-ul și poate repeta scenariul de demo.

## Săptămâna 7 — Predare și prezentare finală

**Scop:** Demonstrezi aplicația și predai o versiune verificată.

- [ ] **P3-S7.1** — Verifică împreună cu echipa codul, modelul, articolul, posterul, README-ul și materialul video de rezervă.
- [ ] **P3-S7.2** — Rulează demonstrația și prezintă interfața, istoricul și exportul. Explică diferența dintre predicție, stare tehnică și simulare.
- [ ] **P3-S7.3** — Arată contribuția ta în cod și teste, precum și ce funcționalități sunt finalizate sau rămân extensii.

**Livrezi:** Pachetul final și prezentarea contribuției personale.
**Este gata când:** Codul predat, demonstrația și documentația descriu aceeași versiune.

## Regula de colaborare

La sfârșitul săptămânii faci o integrare cu ceilalți doi membri. O schimbare a mesajelor sau a pregătirii imaginilor se discută înainte de modificare. Fiecare membru scrie și verifică partea sa din documentație.

**Bază:** `Plan_proiect_AI_responsabilitati_taskuri.md`, secțiunile 4–7; `PI-P_săptămâna1.pdf`, pp. 4–5; `CTI.DD.317_PI_P_FD_2024_2025.pdf`, p. 2, „Termene limită și livrabile”.

**Notă de calendar:** pagina 3 a prezentării are reperele 7–8/14. Acest checklist urmează exclusiv desfășurătorul 1–7 cerut; nu stabilește o echivalență între numerotări.
