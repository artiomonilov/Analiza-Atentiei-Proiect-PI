# P2 — începe aici

Primul fișier: `controller.py`. Comenzile add/start/stop/remove/shutdown sunt scurte și se apelează din firul principal. Creează mai întâi QCoreApplication/QApplication.

Controllerul deține QThread-urile și conexiunile. SourceWorker deține istoricul temporar; schedulerul deține cozi de capacitate 1; PreviewStore deține un singur cadru per sursă; InferenceWorker creează predictorul o dată prin fabrica injectată. Semnalele către controller sunt queued. Niciun modul engine nu importă QtWidgets.

Exemplu fără fereastră:
`python -m audience_analysis.examples.p2_engine_demo`.

Oprirea invalidează run_id imediat, notifică Event/Condition și eliberează istoricul în finally. Rezultatele din calculul început sunt ignorate dacă rularea s-a închis. Așteaptă semnalul shutdown_finished înainte de terminarea aplicației; fără terminate() și fără wait nelimitat în UI.

Primul TODO: **P2-S3.1** din `video/sources.py`, apoi P2-S3.2–3.4 pentru integrarea predictorului real. P2-S5 rămâne pentru adaptoare reale și reconectare, nu pentru această livrare. [Checklist P2](../../../docs/planning/02_P2_Motor_video_saptamanile_1-7.md).
