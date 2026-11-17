# Etapa 5 — analiză temporală a geometriei faciale

Consolidare: o fereastră cu detector EAR configurat, dar fără niciun eșantion EAR valid, returnează `count=None`, nu zero; `observed_ear_samples` documentează disponibilitatea. Frecvența continuă să necesite durată validă suficientă. `geometric_api.temporal_payload` oferă un mesaj serializabil cu ID-uri, fără un scheduler nou; detalii în `docs/contracts.md`. Contoarele de evenimente automate nu sunt referințe manuale și nu demonstrează atenția.

## Arhitectură

`temporal_analysis.py` nu importă MediaPipe, OpenCV sau interfața video. `TemporalAnalyzer.update(record)` acceptă un `VideoMeasurement` existent sau un `TemporalSample(timestamp_ms, head, left_ear, right_ear, left_iris, right_iris)`. Pentru obiectul video, lipsa feței, o eroare sau flagurile de disponibilitate invalide produc măsurători lipsă; singularitatea Euler invalidează analiza temporală a unghiurilor. Nu se execută inferențe suplimentare.

Fiecare apel întoarce `TemporalUpdate`: statisticile ferestrelor, evenimentele noi, contoare cumulative pe ochi, geometria filtrată și indicatorul de trunchiere. `VideoProcessor` creează un analizor nou per sesiune; `on_temporal(update)` livrează rezultatul curent, iar `VideoSessionReport.temporal` păstrează numai ultima actualizare. `on_result(record)` și CSV-ul pe cadru păstrează valorile brute.

Ferestrele implicite sunt 5, 10 și 30 secunde. Istoricul conține doar măsurătorile din cea mai mare fereastră, cu o limită suplimentară de 10000 de eșantioane. Evenimentele au o coadă separată limitată la 1000. Filtrele au și ele cozi limitate. Callback-urile utilizatorului pot reține date; acestea nu sunt controlate de analizor.

## Timp și disponibilitate

Timestampurile trebuie să fie întregi nenegative strict crescătoare. Duratele se calculează prin diferențe de timestamp, niciodată prin numărarea cadrelor/FPS. Se păstrează proveniența timestampurilor în CSV-ul video: estimările fallback din etapa 4 rămân estimări, nu timestampuri fizice validate.

Într-o fereastră la t se includ eșantioanele din `[t-window_ms, t]`. `observed_span_ms` este diferența dintre primul și ultimul eșantion reținut, nu durata observațiilor valide. Durata validă pentru o caracteristică este suma intervalelor dintre două eșantioane consecutive valide, doar când distanța lor temporală nu depășește `max_gap_ms` (implicit 500 ms). Nu se traversează eșantioane lipsă și nu se interpolează. Nu se atribuie durată înaintea primului/după ultimul eșantion și nu se decupează artificial un interval ce traversează marginea ferestrei.

Limita de capacitate poate reduce fereastra efectivă. `history_truncated=True` indică eșantioane eliminate prematur; `events_truncated` indică evenimente eliminate prematur. Frecvența clipirilor rămâne indisponibilă în aceste cazuri. Ratele nu sunt calculate pe durata nominală a ferestrei.

## Mișcarea capului

Se păstrează ordinea `(yaw,pitch,roll)` și convențiile din `head-pose.md`. Pentru fiecare componentă:

- media circulară: `atan2(mean(sin(angle)), mean(cos(angle)))`;
- variația circulară: `1 - hypot(mean(sin(angle)), mean(cos(angle)))`, adimensională, în [0,1];
- când direcția medie nu este definită (rezultantă aproape zero), componenta mediei este `None`;
- diferențele consecutive sunt reduse în [-180°,180°), evitând salturi false la ±180°.

Mărimea pasului este norma euclidiană a celor trei diferențe Euler. Este un indicator geometric în grade, nu distanța geodezică exactă pe SO(3) sau o viteză. Stabilitatea și schimbările sunt definite prin praguri **pe pas consecutiv**: implicit ≤2° stabil, ≥10° schimbare semnificativă. Intervalele consecutive din aceeași categorie sunt unite și raportează început, sfârșit, durată și număr. Deriva lentă poate fi stabilă pe fiecare pas; nu se pretinde stabilitate față de o orientare absolută fixă. Rezultatele depind de rata de eșantionare; calibrarea pragurilor trebuie să țină cont de aceasta.

Mediile și variațiile folosesc eșantioanele valide cu ponderi egale, nu ponderi proporționale cu timpul. Numai duratele folosesc diferențe temporale. Unghiurile în gimbal lock sunt excluse de adaptorul video pentru a evita interpretarea unei reprezentări Euler ambigue ca mișcare fizică.

## Clipiri prin EAR și histerezis

Pragurile sunt **dezactivate implicit**. Pentru fiecare ochi se configurează separat `close` și `reopen`, cu `0 < close < reopen`. Sunt valori EAR brute, măsurate și alese individual; fotografia neutră singură nu definește pragurile. `--neutral-image` calibrează geometria din etapele anterioare, dar nu inventează praguri pentru clipiri.

Mașina de stări, per ochi:

1. Este necesară mai întâi o observație deschisă (`EAR >= reopen`). Un ochi deja închis la început nu produce automat eveniment.
2. `EAR <= close` începe un candidat la timestampul primei observații sub prag.
3. Valorile dintre praguri mențin starea; fluctuațiile mici nu deschid/închid repetat evenimentul.
4. Prima observație `EAR >= reopen` încheie candidatul. Este acceptat algoritmic numai dacă durata este între `min_blink_ms` și `max_blink_ms` (implicit 40…800 ms, parametri operaționali nevalidați).
5. EAR lipsă, pierderea feței sau un interval >`max_gap_ms` întrerupe candidatul. Evenimentele neîncheiate la oprire nu sunt numărate/exportate ca clipiri complete.

Durata este `end_ms - start_ms`. Nu se estimează retrospectiv momentul fizic dintre cadre. Frecvența pe minut este `număr_evenimente_complete * 60000 / durată_EAR_validă_ms`, numai după cel puțin `min_rate_duration_ms` de date valide (implicit 10000 ms) și fără trunchiere. Un eveniment trebuie să înceapă și să se termine în fereastră. Contoarele sunt independente pentru ochiul stâng/drept; nu sunt unite automat într-un număr binocular.

Acestea sunt evenimente automate complete după regulile algoritmului, nu confirmări experimentale. Fiecare rând exportat păstrează `validation_status=automatic_unvalidated`. Închiderea prelungită sau variațiile patologice/artefactele pot necesita alte praguri și validare; nu se deduce atenția.

## Geometria irisului și calibrare

Pentru fiecare ochi: media și variația populației pentru `(iris_x, iris_y)` în reperul local al ochiului; norma deplasării dintre eșantioane consecutive valide; intervale stabile sau cu schimbare semnificativă. Implicit, pragurile sunt 0.02 și 0.15 în coordonate normalizate ale ochiului, configurabile. Nu sunt fixații sau saccade validate.

Calibrarea neutră din `EyeFeaturesEstimator` rămâne disponibilă în măsurătorile brute (`*_gaze_dx/dy`, `*_ear_relative`). Statistica de mișcare folosește pozițiile brute normalizate; scăderea unei referințe constante nu schimbă deplasările sau variația. Pragurile temporale se pot calibra individual din secvențe autorizate, prin distribuția fluctuațiilor în poziție neutră și marcaje de mișcare. La schimbarea subiectului, camerei sau calibrării începe o sesiune/instanță temporală nouă.

## Filtrare opțională

- `none`: valorile geometrice brute, comportamentul implicit;
- `moving_average`: media eșantioanelor din ultimele `smoothing_ms`, circulară pentru cap;
- `ema`: `alpha = 1 - exp(-dt/smoothing_ms)`, folosind distanța circulară pentru cap;
- deadband opțional separat pentru unghiuri și iris: păstrează ultima valoare filtrată când diferența este sub prag.

Filtrele se resetează pe canal la date lipsă sau gap prea mare. Nu produc valori în intervalele absente. EAR și detecția clipirilor utilizează întotdeauna date brute, indiferent de filtrul geometric. CSV-ul temporal include separat `filtered_*_json`; CSV-ul pe cadru rămâne brut. Filtrarea poate întârzia/atenua mișcările geometrice rapide și trebuie aleasă explicit.

## Configurare și execuție

`configs/temporal.example.json` conține toate opțiunile, cu clipirile dezactivate (`left_blink/right_blink=null`). Pentru activare, în copia individuală a configurației completează fiecare ochi cu `{"close": valoare_măsurată, "reopen": valoare_măsurată}`. Nu copia praguri EAR ale altei persoane ca valori universale.

```powershell
# webcam cu overlay temporal opțional
.\.venv\Scripts\python.exe run_video_analysis.py --source 0 --show-temporal --temporal-config configs/temporal.example.json

# video, trei exporturi explicite, fișiere noi
.\.venv\Scripts\python.exe run_video_analysis.py --source "data/test/video.mp4" --no-display --temporal-config "configs/temporal.example.json" --output-csv "results/frames.csv" --output-temporal-csv "results/temporal.csv" --output-blinks-csv "results/blinks.csv"
```

Prin API se configurează `TemporalConfig` în constructorul `VideoProcessor`. Nu există clasificator de atenție, scor de concentrare sau informații de identitate în această componentă.

## Exporturi și referință manuală

Exporturile sunt independente și activate numai prin argumentele explicite:

- `--output-csv`: măsurători brute, formatul etapei 4;
- `--output-temporal-csv`: un rând per cadru și fereastră, timestamp, durată nominală/observată, număr de eșantioane și trunchiere. Coloanele `head_json`, `left/right_gaze_json`, `left/right_blink_json` păstrează statisticile și intervalele structurate. Valorile indisponibile din JSON sunt `null`; cele filtrate indisponibile sunt celule goale;
- `--output-blinks-csv`: `eye,start_ms,end_ms,duration_ms,validation_status`, numai evenimente automate complete. Lipsa pragurilor produce doar antetul, nu evenimente simulate.

Fișierele trebuie să fie distincte și să nu existe deja. Se scriu incremental și sunt închise inclusiv la Ctrl+C. Nu sunt salvate imagini/video în această etapă.

Pentru validare, adnotează manual o secvență autorizată într-un CSV cu antetul `eye,start_ms,end_ms`, folosind aceleași timestampuri și left/right ale subiectului. Păstrează fișierul de referință separat de detecții:

```powershell
.\.venv\Scripts\python.exe compare_blinks.py --detected "results/blinks.csv" --reference "results/manual_blinks.csv" --tolerance-ms 100
```

`compare_blinks` asociază unu-la-unu evenimentele aceluiași ochi cu începutul și sfârșitul în toleranța aleasă. Potrivirea maximizează numărul perechilor și preferă local erori mici, fără garanția minimului erorii totale. Afișează potriviri cu referința, detecții/referințe neasociate, erori de timp, precizie și recall. Fără referințe, recall este indisponibil. Comparația nu rescrie statusul evenimentelor automate și nu reprezintă validare clinică; marcajele sunt necesare pentru evaluare experimentală, cu verificare manuală a asocierilor.

## Limite

Configurația numerică este operațională, nu validată pe participanți. Decuparea ferestrei, rata variabilă, erorile MediaPipe, ocluziile și estimările timestampurilor influențează rezultatele. Într-un gol sub `max_gap_ms`, durata dintre două observații valide este folosită ca interval observabil; o clipire completă între două cadre poate fi ratată. Nu se pot reconstrui evenimente care nu sunt eșantionate.

La saturarea cozii, numărul de evenimente din fereastră poate deveni o limită inferioară; flagurile avertizează acest lucru și rata rămâne indisponibilă. Numai contoarele cumulative păstrează numărul automat total cu memorie constantă. Overlay-ul este opțional și prezintă prima fereastră configurată; niciun indicator nu este interpretat ca atenție.

## Verificări executate în etapa 5

- `.\.venv\Scripts\python.exe -m pytest -q --basetemp artifacts\pytest-stage5-verified`: **143 passed** în selecția implicită completă, inclusiv 28 cazuri noi față de etapa 4. Testele istorice `tests/test_*.py` nu au fost reexecutate.
- Scenarii sintetice: ferestre și expirare, timestampuri neregulate, durate valide cu goluri, medie/variație circulară la ±180°, intervale de mișcare/stabilitate, variația irisului, clipiri individuale/consecutive, histerezis, lipsa feței, evenimente incomplete, limite de durată/capacitate, EMA/moving average/deadband, date invalide și potrivire unu-la-unu cu referințe sintetice.
- Extragerea video simulată verifică faptul că aceeași instanță MediaPipe este apelată tot de trei ori pentru trei cadre, deși se calculează și ferestrele temporale. Exportul unui eveniment sintetic are `start_ms=40,end_ms=80,duration_ms=40,validation_status=automatic_unvalidated`.
- Exemplu numeric executat separat: EAR sintetic `[.3,.1,.18,.21,.25,.3]` la `[0,100,150,200,250,600]` ms, cu praguri **artificiale de test** close=.15/reopen=.22 numai pentru ochiul stâng, produce exact un eveniment stâng de la 100 la 250 ms, durata 150 ms. Aceste valori nu sunt o calibrare recomandată pentru persoane.
- Rulare reală cu modelul local:

```powershell
.\.venv\Scripts\python.exe run_video_analysis.py --source artifacts\mvp_blank.avi --no-display --temporal-config configs\temporal.example.json --output-temporal-csv artifacts\temporal-stage5-verified.csv --output-blinks-csv artifacts\blinks-stage5-verified.csv
```

Au fost procesate 20 cadre fără față, cu 0 erori; fiecare fereastră conține 20 eșantioane și o durată observată de 3800 ms. CSV-ul temporal a fost verificat: **60 rânduri** (20×3 ferestre), medii ale capului `null`. CSV-ul clipirilor conține doar antetul. Contoarele de clipire sunt indisponibile în acest caz deoarece pragurile nu sunt configurate. Aceasta este verificare tehnică pe un clip gol, nu evaluarea evenimentelor pe persoane.

Nu a fost disponibilă o secvență video autorizată cu marcaje manuale reale. Precizia și recall raportate de comparația unitară sunt exclusiv pentru referințe sintetice. Următorul pas este colectarea unor secvențe autorizate, adnotarea independentă, calibrarea pe o parte a materialului și evaluarea pe secvențe separate.
