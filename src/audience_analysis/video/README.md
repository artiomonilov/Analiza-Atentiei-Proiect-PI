# P2 — surse video, detecție și secvențe

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

- Fluxul HTTP MJPEG e testat automat (server local); RTSP și camera depind de echipament și trebuie verificate pe laptopul de demo.
- Dacă un backend OpenCV rămâne blocat peste limita de timp, firul lui de captură se termină singur ulterior; sursa e oricum oprită imediat.
