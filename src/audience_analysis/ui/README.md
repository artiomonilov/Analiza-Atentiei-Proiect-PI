# P3 — începe aici

Primul fișier: `main_window.py`. Motorul este injectat; fereastra trimite comenzi și primește Signal-uri în Slot-uri. QTimer doar preia ultimul preview și îl afișează. QImage.copy() desprinde pixelii de bufferul NumPy.

- `python -m audience_analysis --ui-demo`: scenariu prestabilit DemoEngine (rezultat, eroare, stop), fără scheduler/model/video.
- `python -m audience_analysis --demo`: aceeași fereastră, cu motorul P2 și FakePredictor.

Ambele cer apăsarea Pornire și păstrează bannerul SIMULARE. Închiderea este asincronă; nu așteaptă blocant predictorul. `history.py` deduplică rezultatele și oferă helper CSV cu is_demo și celule goale la erori.

Primul TODO: **P3-S2.1** din `main_window.py`, formular SourceConfig și card participant; folosește numai comenzile motorului și testează validarea. Extensiile grilă/tabel/dialog CSV sunt marcate P3-S5.1/5.3/5.4. [Checklist P3](../../../docs/planning/03_P3_Interfata_saptamanile_1-7.md).
