# Contractele mini-template-ului (task 04)

Contractele sunt în `audience_analysis.contracts`, fără Qt, cv2 sau torch. Configurația este în `config.SequenceConfig`. Importurile de pachete `ai`, `video`, `engine`, `ui` nu pornesc lucrători.

| Mesaj | Semnificație |
|---|---|
| SourceConfig | ID local, nume afișat, tip și locație. `demo` este distinct de `file`, `camera`, `network`. |
| FramePacket | BGR uint8 [H,W,3], source/run/frame ID, timp media și casete ale exact aceluiași cadru. Demo-ul nu conține oameni și trimite casete goale. |
| PreparedSequence | float32 [T,3,H,W], RGB, scalat și normalizat deja; sample_times_s strict crescătoare și preprocessing_id. |
| InferenceRequest | source/run/request ID, interval efectiv, moment monotonic al intrării în coadă și secvență independentă de istoric. |
| ModelOutput | Dimensiuni disponibile → niveluri întregi 0–3; versiune și is_demo obligatoriu. |
| PredictionResult | Identitatea cererii, interval, stare, levels/None, versiune, is_demo, așteptare/inferență în ms și eroare opțională. |
| SourceStatusEvent | event_id unic, source/run, stare și mesaj; nu necesită cerere AI. |

`Predictor.predict(PreparedSequence) -> ModelOutput`. Predictorul nu citește surse. `RealPredictor` ridică o eroare explicită; nu trece automat la simulare.

## Preprocesare și timp

`video.preprocessing.prepare_bgr` redimensionează cu nearest-neighbor NumPy, convertește BGR→RGB, aplică `pixel * scale`, apoi `(pixel - mean) / std`, și transpune HWC→CHW. P1 reutilizează funcția; predictorul nu normalizează a doua oară. Mini-template-ul pregătește întregul cadru exclusiv sintetic. Detecția/decuparea reală sunt puncte explicite de integrare.

Configurația demo implicită: T=4, H=24, W=32, fereastră 0,6 s, pas 0,2 s, scale=1/255, mean=0, std=1. Acestea NU sunt parametri validați pentru un model real. ID-ul preprocesării include un hash al tuturor parametrilor. Pachetul real va furniza propria configurație.

Cadrele sunt selectate după timp, dintr-un deque limitat la 128. Țintele sunt uniform distribuite în fereastră, cu toleranță explicită; cadrele nu sunt duplicate. PreparedSequence copiază și protejează bufferul. Intervalul exportat este primul–ultimul eșantion ales. Timpul media nu măsoară calculele: queue_wait_ms și inference_ms folosesc monotonic.

## Rulări, cozi, oprire

Fiecare pornire/resetare generează un run_id UUID nou. request_id începe de la 0 și crește în rulare; frame_id crește independent. SourceStatusEvent are propriul event_id.

Schedulerul deține Queue(maxsize=1) pentru fiecare sursă. O Condition protejează atât înlocuirea, cât și preluarea; fără empty()/full(), fără busy-wait sau task_done(). O cerere nouă înlocuiește numai cererea în așteptare și mărește contorul replaced. Preluarea alternează sursele disponibile. Calculul început nu este întrerupt.

Stop/reset/remove invalidează run_id înaintea următoarelor livrări, elimină coada și preview-ul, semnalizează Event-ul capturii și respinge răspunsurile vechi. ResultGate respinge rezultatele duplicate/învechite, dar acceptă un răspuns valid în curs chiar dacă există o cerere mai nouă în coadă.

Controllerul trăiește în firul principal, fiecare SourceWorker în propriul QThread, iar predictorul este creat o singură dată în QThread-ul AI. Comunicația către controller/UI folosește Signal/Slot. Previzualizarea păstrează un singur FramePacket per sursă într-un depozit protejat, citit prin take_latest_preview. Nu se emite un semnal cu imagine la fiecare cadru.

`shutdown()` este neblocant; finalizarea este anunțată prin shutdown_finished. Nu se folosește terminate() sau wait() nelimitat în UI. Un predictor extern care nu se mai întoarce nu poate fi oprit forțat; UI rămâne în starea de închidere. Integrarea reală trebuie să definească operații limitate temporal (P2-S6.2).

## Stări și istoric

STARTED/INSUFFICIENT_DATA/NO_FACE/END_OF_SOURCE/STOPPED/REMOVED sunt stări tehnice. OK este o predicție validă; ERROR și MODEL_UNAVAILABLE au obligatoriu levels=None. Niciuna dintre erori nu reprezintă nivelul 0.

Istoricul deduplică (source_id, run_id, request_id). CSV păstrează is_demo și celule goale la eroare; nu conține locații de surse. UI arată separat intervalul predicției și previzualizarea curentă. Bannerul de simulare este permanent.

## Cod anterior

Contractele vechi sunt păstrate în `legacy_contracts.py`, iar fereastra anterioară în `legacy_ui.py`; importurile vechilor module/teste au fost ajustate. `python -m audience_analysis.app` rămâne intrarea anterioară, nefolosită de mini-template. Nu există un al doilea proiect sau un al doilea pachet instalabil. Adaptarea codului real la noile contracte rămâne în taskurile P1/P2, nu este activată în această livrare.
