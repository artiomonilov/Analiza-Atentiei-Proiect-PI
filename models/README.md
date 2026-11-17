# Modele locale

Fișierul MediaPipe local verificat tehnic are 3758596 bytes și SHA256 `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`. Hashul identifică acea copie; nu dovedește autenticitatea unei alte surse sau acuratețea pe persoane. Nu a fost descărcat un model nou în consolidarea ramurii. Revizia fixată HF și pachetul P1 validat sunt documentate în `docs/environment.md` și `docs/p1-data-model.md`; niciun model de angajament DAiSEE nu este furnizat.

Pune modelul MediaPipe Tasks compatibil în `models/face_landmarker.task`, sau indică altă cale prin `--model`. Fișierul `.task` este local și ignorat de Git. Nu se descarcă automat.

Documentație oficială și modele: https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker

Nu adăuga date de test sau fotografii în acest director. Scriptul scrie imaginea adnotată numai la cererea explicită de execuție, implicit în `results/`.
