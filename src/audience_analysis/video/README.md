# P2 — surse video, detecție și secvențe

Actualizare pe branchul de integrare: FileSource folosește FrameClock și
POS_MSEC când este valid, cu fallback explicit; nu presupune automat FPS
constant. SequenceBuilder subeșantionează temporal și dimensionează istoricul
din fereastră/toleranță (maximum 4096 cadre), respingând un buget insuficient.
Workerul păstrează maximum 8 fețe vizibile, trackerul maximum 32 de trackuri
reținute și expiră trackurile înainte de matching. Geometria folosește cadrul
întreg și o asociere unică verificată, nu primul track dintr-o listă.

- `sources.py` — de unde vin cadrele: sursa sintetică (demo), fișier video sau poză (`FileSource`), cameră locală sau flux de rețea (`LiveSource`).
- `preprocessing.py` — detecția YuNet (toate fețele) și pregătirea comună P1/P2 a imaginilor.
- `tracking.py` — urmărirea anonimă a fețelor (`track_id`); nu recunoaște persoane.
- `sequences.py` — istoric limitat per față, selecție după timp, copie stabilă pentru model.

## Ce se poate scrie în câmpul „Fisier/Sursa”

| Text | Tip | Exemplu |
|---|---|---|
| cale de fișier | video sau poză | `/home/ilie/clip.mp4` |
| număr sau `/dev/videoN` | cameră locală | `0` = prima cameră a laptopului |
| `http://` / `https://` | flux de rețea (testat: MJPEG, ex. aplicația „IP Webcam” de pe telefon) | `http://192.168.1.35:8080/video` |
| `rtsp://` | flux de rețea (cameră IP) | `rtsp://192.168.1.20:554/stream1` |

`resolve_source()` face recunoașterea, deci formularul UI nu trebuie schimbat.

## Camera și rețeaua (P2-S5.1, P2-S5.4)

- Un fir intern citește continuu și păstrează **doar cel mai nou cadru**, ca analiza să nu rămână în urmă.
- Timpul cadrelor vine din ceasul calculatorului, de la pornirea sursei (FPS-ul raportat de cameră/flux nu e de încredere).
- Deschiderea și citirea fluxurilor au limită de 5 s.
- La pierderea conexiunii: secvențele vechi sunt aruncate și se încearcă reconectarea după 1, 2, 4, 8, 8 s (`SourceWorker.RECONNECT_DELAYS_S`); apoi `ERROR`. Celelalte surse nu sunt afectate.
- **Fără parole în Git sau în mesaje:** `redact()` ascunde parola și parametrii adresei (`rtsp://admin:***@...`). Nu scrieți adrese cu parolă în fișiere de configurație comise.

## Limite cunoscute

- Testarea MJPEG cu server local este o afirmație istorică a ramurii Ilie, nereexecutată în această integrare. Testele noi live folosesc capture mocks; camera și fluxurile reale necesită verificare autorizată pe hardware.
- Pentru network se păstrează backendul FFmpeg cu parametri de timeout, fără fallback silențios la un backend fără acei parametri. Suportul efectiv depinde de build/codec.
- Numai firul care citește captura live face release în finally. Dacă read nu revine la timp, close ridică TimeoutError, iar o rezervare împiedică a doua captură pe aceeași adresă până la eliberare. Nu se pretinde că orice backend nativ poate fi întrerupt; maximum 16 capturi live sunt rezervate simultan. Un read de fișier sau un predictor extern blocat poate întârzia shutdown; nu se folosește terminate pe QThread.
