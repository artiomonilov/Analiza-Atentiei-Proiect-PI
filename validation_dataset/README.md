# Structura înregistrărilor autorizate

Fișierele efective se păstrează local în `data/validation/` (ignorat de Git):

```text
data/validation/
  calibration/C01/       videoclipuri și CSV-uri numai pentru calibrare
  development/D01/       materiale separate pentru alegerea parametrilor
  validation/V01/        alte înregistrări pentru evaluare
  references/V01/        repere numerice independente și marcaje manuale
```

Folosește identificatori anonimi. Pentru fiecare sesiune documentează local: permisiunea utilizării, ID-ul înregistrării, grupul calibration/validation, camera, oglindirea, iluminarea, scenariile și proveniența referințelor. Nu adăuga în Git fotografii, video sau date de identificare.

Protocolul actual include și rolul development: C01 → D01 → înghețare → V01, în `docs/real-world-evaluation.md`. Profilul C poate referi materialele prin `--raw-source`, fără căi în profil; verificarea finală a rândurilor/evenimentelor este comună pentru CLI, dashboard și API. Hashurile detectează reutilizarea exactă a materialelor cunoscute, nu re-encodarea sau independența semantică. Snapshoturile omit implicit căile personale și nu copiază video.

Scenarii de colectat: neutru stabil, rotiri stânga/dreapta, sus/jos, clipiri naturale și consecutive, mișcări ale ochilor, schimbări de iluminare, pierderea/revenirea feței. Instrucțiunea „rotește capul” nu este o referință numerică în grade.

Referință geometrică CSV: `timestamp_ms,yaw,pitch,roll,left_iris_x,left_iris_y,right_iris_x,right_iris_y,orientation_category`. Completează numai valorile măsurate/verificate independent; celulele necunoscute rămân goale. Categoria este opțională și nu se convertește automat în grade.

Referință evenimente CSV: `eye,start_ms,end_ms`, cu `eye=left/right` ale subiectului. Folosește aceleași timestampuri ca în măsurători și marchează explicit dacă întreaga secvență a fost adnotată.

Nu sunt incluse înregistrări sau referințe fabricate. Datele locale pot fi șterse manual la sfârșitul perioadei convenite, inclusiv copiile din `results/`; instrumentele nu trimit date în servicii externe și nu șterg automat materialul original.
