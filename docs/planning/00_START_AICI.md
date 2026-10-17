# Plan de lucru — echipa de trei persoane

## Ce construim

O aplicație desktop Python care analizează surse video și afișează estimări de angajament.
**MVP-ul din săptămâna 3:** un videoclip cu un participant, detectarea feței, secvențe,
coadă, predictor antrenat și afișarea rezultatului. La date neutilizabile apare o stare
tehnică, nu o etichetă de neatenție.

La final țintim 3–4 surse, cameră locală, un flux de rețea testat, istoric, CSV și
ieșirile suplimentare evaluate. Prototipul folosește date autorizate; nu evaluează
studenții și nu presupune integrare Meet/Zoom sau recunoașterea identității.

## Fișierele din pachet

| Fișier | Ce conține |
|---|---|
| `01_P1_Date_AI_saptamanile_1-7.md` | Checklistul P1: date, modele, evaluare și predictor local. |
| `02_P2_Motor_video_saptamanile_1-7.md` | Checklistul P2: captură, pregătire, cozi, cereri/răspunsuri și control. |
| `03_P3_Interfata_saptamanile_1-7.md` | Checklistul P3: interfață, istoric, export și instalare. |
| `04_Prompt_Codex_mini_template.md` | Promptul care cere crearea scheletului de cod comun. |

Fiecare persoană are **27 de sarcini**, repartizate pe șapte săptămâni.
Fiecare săptămână precizează scopul, sarcinile, ce se predă și cum se verifică.
Identificatorii, de exemplu `P2-S3.2`, pot fi folosiți în taskuri și TODO-uri.

## Cine deține fiecare parte

**P1 construiește predictorul. P2 construiește motorul care îl apelează.
P3 construiește interfața care controlează motorul și afișează rezultatele.**

```text
Utilizator → P3: comandă de pornire
              ↓
P2: sursă → cadre → secvență → coadă
              ↓
P1: predictor → estimări
              ↓
P2: verificare răspuns + asociere sursă/rulare/interval
              ↓
P3: afișare + istoric + export
```

Previzualizarea video circulă separat de predicții. P2 nu desenează widgeturi,
iar P3 nu citește camera și nu apelează direct AI-ul.
Formatul mesajelor și preprocesarea sunt decizii comune; modificarea lor se discută.

## Reperele săptămânale

| Săptămâna | Ce trebuie să existe la final |
|---|---|
| **1 — Organizare** | Echipa, tema, formularul, spațiul GitHub și documentarea inițială. |
| **2 — Proiectare** | Date pregătite pentru antrenare, contracte comune și componente inițiale testabile. |
| **3 — Prototip și evaluare** | MVP cu un videoclip și predicții reale; primele rezultate și raportarea pregătită. |
| **4 — Prezentare intermediară** | Prezentare comună, demo funcțional și feedback consemnat. |
| **5 — Dezvoltare** | Model temporal/stări suplimentare, mai multe surse, istoric și export în dezvoltare integrată. |
| **6 — Testare și documentare** | Evaluare finală, versiune stabilă, articol, README, poster și demo de rezervă. |
| **7 — Prezentare finală** | Poster, cod funcțional și prezentarea contribuției fiecăruia. |

Numerotarea urmează **„Desfășurare proiect”, pp. 4–5** din `PI-P_săptămâna1.pdf`.
Pagina 3 prezintă separat reperele 7–8/14; acest plan nu stabilește o echivalență.
Detalierea tehnică este propunerea de lucru a echipei.
Fișa disciplinei, p. 2, precizează prezentarea intermediară de 6–7 slide-uri și
livrarea finală a articolului, codului și posterului.

## Cum folosiți promptul Codex

Copiați cele trei fișe în `docs/planning/` din repository. O singură persoană
rulează promptul de inițializare din fișierul 04, în proiectul comun.
Promptul cere inspectarea codului existent și evitarea suprascrierilor.

Verificați împreună rezultatul și testele raportate, apoi integrați șablonul.
Fiecare continuă pe propriul branch, de exemplu `p1-ai`, `p2-engine`, `p3-ui`.
Nu rulați trei inițializări independente: modulele trebuie să folosească aceleași
mesaje și aceeași configurație.

**Ce trebuie să genereze Codex:** contracte, scheletele modulelor, exemple
independente, un traseu simulat executabil și teste de bază.

**Ce rămâne echipei:** modelul real, integrarea video reală, validarea
preprocesării, extinderea funcțiilor, evaluarea și prezentarea rezultatelor.

Șablonul nu înseamnă că MVP-ul este terminat. Datele simulate sunt marcate în
interfață și rezultate; nu sunt metrici sau predicții reale.
Dacă un task are deja un început în template, îl citești, îl verifici și îl
completezi, nu îl rescrii automat.

## Regula de lucru săptămânal

Fiecare task are un responsabil și o dovadă: test, rezultat, fișier exportat
sau demonstrație. La finalul săptămânii integrați componentele și verificați
traseul complet. P1 ajută P2 la preprocesare; P3 ajută P2 la testele de integrare,
fără mutarea logicii motorului în interfață.

Nu amânați integrarea până în săptămâna 6. Din săptămâna 3, demonstrația de
evaluare trebuie să folosească predictorul real. Funcțiile nefinalizate se
raportează explicit, nu se înlocuiesc în tăcere cu simulări.

## Baza planului

`Plan_proiect_AI_responsabilitati_taskuri.md`, secțiunile 4–7;
`PI-P_săptămâna1.pdf`, pp. 4–5; `CTI.DD.317_PI_P_FD_2024_2025.pdf`, p. 2.

Pachetul conține **planuri și un prompt**, nu codul aplicației. Structura
repository-ului și detaliile șablonului sunt propuneri de implementare.
