# P2 — începe aici

Primul fișier: `controller.py`. Comenzile add/start/stop/remove/shutdown sunt scurte și se apelează din firul principal. Creează mai întâi QCoreApplication/QApplication.

Controllerul deține QThread-urile și conexiunile. SourceWorker deține istoricul temporar; schedulerul deține cozi de capacitate 1; PreviewStore deține un singur cadru per sursă; InferenceWorker creează predictorul o dată prin fabrica injectată. Semnalele către controller sunt queued. Niciun modul engine nu importă QtWidgets.

Exemplu fără fereastră:
`python -m audience_analysis.examples.p2_engine_demo`.

Oprirea invalidează run_id imediat, notifică Event/Condition și eliberează istoricul în finally. Rezultatele din calculul început sunt ignorate dacă rularea s-a închis. Așteaptă semnalul shutdown_finished înainte de terminarea aplicației; fără terminate() și fără wait nelimitat în UI.

Surse acceptate: demo, fișier/poză, cameră locală și flux de rețea (vezi `video/README.md`). Pentru cameră/rețea, `SourceWorker` reîncearcă automat conexiunea pierdută și raportează `ERROR` doar după ultima încercare. [Checklist P2](../../../docs/planning/02_P2_Motor_video_saptamanile_1-7.md).

## Statistici (P2-S4.3)

`engine.stats()` întoarce un dicționar per sursă (rularea curentă): cadre analizate, cadre fără față / cu fețe prea mici, cereri trimise și înlocuite înainte de model, rezultate OK / cu eroare / respinse, reconectări, așteptarea în coadă și calculul modelului (medie, p95, max, în ms). `engine.stats_report()` dă același lucru ca text. Timpii sunt timp de procesare, nu intervalul din videoclip. La `start_source` contoarele sursei pornesc de la zero.
