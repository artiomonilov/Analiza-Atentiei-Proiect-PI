# Starea implementării — 11 octombrie 2026

Implementarea pornește de la planul furnizat. Nu echivalează cu finalizarea proiectului de cercetare.

Verificare locală: **19 teste automate trecute**, inclusiv sesiune desktop cu patru clipuri sintetice, export fără credențiale, cronologie, excluderea predicțiilor întârziate din sursele evaluabile, manifest, pas de optimizare R1/R2 și fluxul antrenare–export–reîncărcare–evaluare pe fixture sintetic. Interfața a fost pornită și inspectată prin captură. Niciuna dintre aceste verificări nu constituie evaluare pe DAiSEE.

| Componentă | Stare |
|---|---|
| Desktop, 1–4 surse, configurare, istoric filtrabil | Implementat; verificat local cu PyQt5 |
| PySide6 | Cod propus; instalare/verificare blocată de spațiul insuficient |
| YuNet, preprocesare comună, secvențe | Implementat; teste tehnice |
| Fișiere și sfârșit de fișier | Testat cu video sintetic MJPG |
| Cameră și RTSP/HTTP | Implementat; hardware/flux real nevalidate |
| Cozi, continuitate, oprire, export | Implementat; teste automate |
| R1/R2 și reper R0 | Implementate; optimizare și serializare testate |
| Antrenare/evaluare DAiSEE | Necesită date și verificarea condițiilor de utilizare |
| Model real de angajament | Nefurnizat; de antrenat și evaluat |
| Experiment cu/fără margine | Configurații pregătite; rezultate nemăsurate |
| Notebookuri | Execută CLI; nerulate în Colab |
| Paritate Colab–desktop | Verificator implementat; experiment efectiv nerulat |
| Stabilitate 10 minute / capacitate pe hardware-ul final | De executat cu material autorizat |
| Articol, poster, prezentări, contribuții nominale | Necesită rezultatele și informațiile echipei |

Detector: YuNet 2023mar, fixat prin fișier și SHA-256. Captura este izolată în procese pentru a putea opri backenduri blocate. Inferența rulează separat de Qt. Firele native BLAS ale proceselor copil sunt limitate pentru a reduce consumul de memorie.

Interfața folosește un tabel de istoric cu categorii ordonate. Nu produce etichete când fața lipsește și nu identifică persoanele.

## Continuare pe responsabilități

- **P1:** acces DAiSEE, etichete/participanți, manifest, audit, R1/R2, selecție pe validare, evaluare R0/R1/R2.
- **P2:** verificare vizuală, auditul respingerilor, margine 0 versus 0.15, cameră și un flux de rețea documentat.
- **P3:** spațiu pentru PySide6, instalare curată, test 10 minute, latență/memorie/acoperire, integrarea modelului real.

Numele membrilor nu au fost furnizate. Rolurile nu atribuie contribuții umane codului generat.

## Actualizare — task 04, 15 octombrie 2026

Secțiunile de mai sus consemnează implementarea anterioară. Noul mini-template este documentat în README și `docs/contracts.md`. Codul anterior a fost păstrat, cu contractele în `legacy_contracts.py` și fereastra în `legacy_ui.py`. Demo-urile noi nu îl activează.

PySide6 este acum instalat local. Verificarea mini-template-ului a trecut cu **27 de teste într-un mediu curat**, fără pachetele AI/video. Vezi [raportul taskului 04](task04-verification.md) pentru versiuni, exemple, verificarea offscreen și limite. Modelul real și integrarea video reală rămân taskurile echipei; checklisturile originale sunt păstrate nebifate în `docs/planning/`.
