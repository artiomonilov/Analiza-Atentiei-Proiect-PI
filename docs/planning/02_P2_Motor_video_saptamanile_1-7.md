# P2 — Motor central, imagini și surse video

**Proiect:** Analiza atenției și angajamentului audienței.
**Responsabilitate:** F1–F3 / T4–T7: captură, pregătire, cozi, apelarea predictorului și răspunsurile către UI.
**Tehnologii:** Python, OpenCV, NumPy, `deque`, `queue.Queue`, `threading.Lock/Event`, PySide6 QtCore / QThread / Signal.
**Unde lucrezi în șablonul propus:** `src/audience_analysis/video/`, `src/audience_analysis/engine/`, `tests/video/`, `tests/engine/`.
**Nu preiei:** antrenarea modelului sau modificarea directă a widgeturilor. P3 afișează datele pe care le transmiți.

> Numerotarea 1–7 urmează „Desfășurare proiect”, pp. 4–5 din prezentare. Sarcinile de mai jos sunt detalierea propusă pentru echipă, nu cerințe tehnice citate din prezentare.

Bifează un task după verificare. Pentru fiecare săptămână păstrează în Git codul și o notă scurtă cu ce ai testat și ce nu funcționează.

## Săptămâna 1 — Organizare și proiectarea fluxului

**Scop:** Stabilești motorul care leagă sursele, AI-ul și interfața.

- [ ] **P2-S1.1** — Testează citirea unui videoclip local cu OpenCV. Identifică durata, rezoluția și modul în care vei păstra timpul videoclipului.
- [ ] **P2-S1.2** — Studiază o metodă de detectare a feței și notează limitele ei. Nu include recunoașterea identității.
- [ ] **P2-S1.3** — Schițează traseul: sursă → cadre → față → secvență → coadă → predictor → rezultat. Separă istoricul de cadre de coada cererilor AI.
- [ ] **P2-S1.4** — Stabilește cu echipa că tu deții comenzile motorului, lucrătorii și legătura cerere–răspuns. P1 oferă predictorul; P3 doar trimite comenzi și afișează datele.

**Livrezi:** Schița motorului, prima verificare a capturii și limitele responsabilităților.
**Este gata când:** Poți descrie unde este fiecare cadru, cine cheamă modelul și cine primește rezultatul.

## Săptămâna 2 — Contracte și componente de bază

**Scop:** Pregătești module care pot fi conectate fără schimbări improvizate.

- [ ] **P2-S2.1** — Definește cu P1 și P3 mesajele comune: sursă, cadru, secvență, cerere și răspuns. Folosește `source_id`, `run_id`, `request_id` și intervalul analizat.
- [ ] **P2-S2.2** — Construiește citirea în fundal și un istoric limitat de cadre pentru fiecare sursă. Păstrează doar ultimul cadru pentru previzualizare.
- [ ] **P2-S2.3** — Implementează împreună cu P1 pregătirea comună a imaginilor și regulile de selectare a cadrelor după timp. Documentează ce înseamnă o secvență utilizabilă.
- [ ] **P2-S2.4** — Pregătește coada și testele cu sursa/predictorul simulate. Verifică înlocuirea cererii în așteptare fără blocarea citirii sau a interfeței.

**Livrezi:** Contracte comune, captură inițială, pregătire de secvențe și coadă testabilă separat.
**Este gata când:** Un mesaj simulat parcurge motorul și păstrează identificatorii corecți.

## Săptămâna 3 — Motor complet pentru un videoclip

**Scop:** Conectezi întregul traseu al MVP-ului.

- [ ] **P2-S3.1** — Citește videoclipul în afara firului interfeței, detectează și decupează fața, apoi formează secvențe compatibile cu predictorul real.
- [ ] **P2-S3.2** — Folosește maximum o cerere în așteptare pentru sursă și un lucrător AI. Încarcă predictorul o singură dată și trimite secvențe independente de istoricul care continuă să se modifice.
- [ ] **P2-S3.3** — Leagă răspunsul de cerere, sursă, rulare și interval. Trimite separat imaginile pentru previzualizare și rezultatele; respinge datele nevalide și tratează erorile modelului.
- [ ] **P2-S3.4** — Implementează pornirea, oprirea și restartarea. La resetare invalidează rularea veche, golește cadrele/coada și ignoră răspunsurile întârziate; eliberează captura.

**Livrezi:** Motorul MVP cu predictor real, coadă, comenzi și notificări către P3.
**Este gata când:** Un videoclip poate fi analizat, oprit și repornit fără amestecarea rezultatelor.

## Săptămâna 4 — Prezentare intermediară

**Scop:** Demonstrezi traseul și situațiile în care sistemul nu emite o predicție.

- [ ] **P2-S4.1** — Verifică înainte de demo cazurile: videoclip valid, față absentă, secvență insuficientă și fișier terminat.
- [ ] **P2-S4.2** — Pregătește explicația motorului: ce păstrează istoricul, ce păstrează coada și când este apelat modelul.
- [ ] **P2-S4.3** — Înregistrează timpii de așteptare și de calcul fără să îi confunzi cu intervalul din videoclip. Arată limitele observate, fără promisiuni de performanță.
- [ ] **P2-S4.4** — Notează feedbackul pentru motor și fixează problemele critice fără să începi extensii care riscă demo-ul.

**Livrezi:** Motor stabil pentru demo, explicația procesării și lista de îmbunătățiri.
**Este gata când:** Poți urmări o cerere de la formare până la răspuns și explica un caz fără rezultat.

## Săptămâna 5 — Mai multe surse și gestionarea încărcării

**Scop:** Extinzi motorul la 3–4 surse independente.

- [ ] **P2-S5.1** — Adaugă camera locală și un tip de flux de rețea verificat. Deschide fiecare sursă independent; documentează adresa acceptată, fără credențiale în Git sau loguri.
- [ ] **P2-S5.2** — Păstrează istoric, coadă și `run_id` separat pentru fiecare sursă. Lucrătorul AI preia pe rând cererile surselor disponibile, fără să favorizeze permanent una dintre ele.
- [ ] **P2-S5.3** — Implementează înlocuirea cererilor vechi încă neprocesate, numărarea lor și păstrarea unui singur cadru de previzualizare per sursă. Nu întrerupe forțat o predicție deja începută.
- [ ] **P2-S5.4** — Tratează deconectarea, reconectarea și eliminarea sursei în timpul calculului. O sursă cu probleme nu trebuie să blocheze celelalte; la întrerupere invalidează secvențele vechi.

**Livrezi:** Motor multi-sursă și integrare cu tipurile de intrare testate.
**Este gata când:** 3–4 surse produc rezultate separate; oprirea uneia nu oprește întreaga sesiune.

## Săptămâna 6 — Testare, preprocesare și stabilitate

**Scop:** Verifici că motorul se comportă corect și în situații dificile.

- [ ] **P2-S6.1** — Testează suprasolicitarea cu un predictor simulat lent: cozi limitate, înlocuire explicită, alternarea surselor și lipsa acumulării nelimitate de imagini. Acesta este un test software, nu o evaluare AI.
- [ ] **P2-S6.2** — Testează oprirea în timpul predicției, restartarea rapidă, eliminarea sursei și răspunsurile întârziate. Confirmă că lucrătorii se închid controlat, fără blocarea UI.
- [ ] **P2-S6.3** — Rulează cu P1 experimentul de rezoluție sau decupaj. Documentează cadrele/ferestrele respinse și păstrează aceleași reguli de pregătire la antrenare și local.
- [ ] **P2-S6.4** — Testează cu P3 aplicația pe laptopul de demo și măsoară timpii și memoria. Propunere internă: minimum 10 minute de funcționare; scrie rezultatul real și secțiunea ta din raport/poster.

**Livrezi:** Teste pentru motor, măsurători de performanță și descrierea preprocesării.
**Este gata când:** Nu se amestecă sursele/rulările, nu apar cozi nelimitate și erorile au stări explicite.

## Săptămâna 7 — Predare și prezentare finală

**Scop:** Predai motorul și demonstrezi funcționarea lui.

- [ ] **P2-S7.1** — Verifică toate sursele folosite la prezentare și păstrează videoclipuri locale autorizate ca rezervă pentru probleme de cameră sau rețea.
- [ ] **P2-S7.2** — Documentează comenzile motorului, mesajele, limitele măsurate și responsabilitatea fiecărui modul.
- [ ] **P2-S7.3** — Prezintă citirea cadrelor, pregătirea secvențelor, coada și răspunsurile. Arată și oprirea corectă a unei surse.

**Livrezi:** Motorul final, testele și prezentarea contribuției personale.
**Este gata când:** Demo-ul poate fi repetat fără dependență de o conexiune externă sau de Colab.

## Regula de colaborare

La sfârșitul săptămânii faci o integrare cu ceilalți doi membri. O schimbare a mesajelor sau a pregătirii imaginilor se discută înainte de modificare. Fiecare membru scrie și verifică partea sa din documentație.

**Bază:** `Plan_proiect_AI_responsabilitati_taskuri.md`, secțiunile 4–7; `PI-P_săptămâna1.pdf`, pp. 4–5; `CTI.DD.317_PI_P_FD_2024_2025.pdf`, p. 2, „Termene limită și livrabile”.

**Notă de calendar:** pagina 3 a prezentării are reperele 7–8/14. Acest checklist urmează exclusiv desfășurătorul 1–7 cerut; nu stabilește o echivalență între numerotări.
