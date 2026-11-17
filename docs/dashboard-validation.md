# Etapa 7 — dashboard experimental și protocol de validare

## Tehnologie și arhitectură

Dashboardul este o aplicație desktop locală **PySide6 + QtCharts**, alternativa echivalentă aleasă în locul Streamlit. PySide6 este deja dependență de bază; nu este necesar un server web, un cont sau un serviciu cloud.

- `run_dashboard.py`: lansare și import opțional CSV.
- `dashboard_data.py`: sesiuni, citirea datelor prin `validation.py`, intervale, segmente de grafic, marcaje, sincronizare video și stocare locală.
- `ui/experimental_dashboard.py`: widgeturi și grafice; delegă evaluarea motorului existent.
- Fluxurile de inferență video și calibrare rămân în scripturile etapelor anterioare. Dashboardul nu pornește camera, nu încarcă modele și nu recalculează predicții.

## Instalare și pornire

Din repository, folosind mediul existent:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe run_dashboard.py

# import inițial opțional
.\.venv\Scripts\python.exe run_dashboard.py --measurements "results/V01_frames.csv" --session-id V01
```

QtCharts este inclus în distribuția completă PySide6. Pentru adnotare video este necesar și OpenCV; folosește distribuția deja instalată în mediul proiectului (`[video]` sau cea adusă de MediaPipe), evitând instalarea a două distribuții care furnizează simultan `cv2`. Fără OpenCV se pot inspecta CSV-uri; deschiderea video raportează dependența lipsă.

Directorul implicit al sesiunilor salvate este `data/dashboard_sessions/`, ignorat de Git. Poate fi schimbat explicit cu `--session-root`. Pornirea nu creează sesiuni pe disc și nu deschide automat video.

## Importul și gestionarea sesiunilor

1. „Import CSV”: selectează un fișier de măsurători din etapa 4/5. Minimul este coloana `timestamp_ms`; măsurătorile incomplete rămân indisponibile. Timpul trebuie să fie strict crescător și valorile numerice finite.
2. Completează ID-ul anonim, data ISO și rolul `calibration` sau `validation`, apoi aplică metadatele. Selectorul de sus schimbă sesiunea activă.
3. În panoul „Validare și scenarii” poți importa profilul de calibrare, referințele geometrice și configurația JSON din etapa 6. Profilul documentează calibrarea utilizată; nu transformă retroactiv măsurătorile brute într-un CSV nou.
4. „Salvează sesiune” copiază **explicit** snapshotul CSV importat, evenimentele încărcate, referințele și profilul într-un director UUID nou, cu manifest JSON și checksum semantic al măsurătorilor. Video nu este copiat; implicit nici căile externe CSV/video nu sunt păstrate, pentru a evita expunerea numelui contului sau directoarelor personale. Reatașează video explicit pentru adnotare. Opt-in-ul CLI `experimental_session.py create --include-external-paths` poate păstra aceste căi dacă operatorul solicită aceasta. Manifestul păstrează data, ID-ul, rolul, configurația și proveniența.
5. „Deschide sesiune”: selectează directorul salvat care conține manifestul. Încărcarea nu pornește automat video.
6. „Elimină sesiune”: pentru o sesiune gestionată din `--session-root`, cere confirmare și șterge definitiv doar copiile CSV/JSON din directorul UUID. Originalele externe și video nu sunt șterse. Ștergerea este refuzată dacă directorul conține fișiere neașteptate, subdirectoare sau legături. Sesiunile importate din afara rădăcinii gestionate pot fi eliminate numai din memorie.

Aplică editările marcajelor înainte de schimbarea sesiunii sau închidere. Închiderea nu salvează automat date pe disc. Pentru o nouă versiune de sesiune, salvarea creează un director nou; versiunile anterioare pot fi deschise/eliminate explicit.

## Grafice și date indisponibile

Intervalul de sus controlează graficele și panoul de calitate, în milisecundele CSV. Sunt disponibile:

- yaw, pitch, roll în grade;
- variația circulară medie a celor trei axe în ultima secundă validă, cu minimum două observații;
- EAR brut separat pe ochi;
- EAR/EAR neutru când coloanele există;
- coordonatele locale ale irisurilor;
- deplasările irisurilor față de referința neutră (`*_gaze_dx/dy`) când există.

Lipsa feței, flagurile de indisponibilitate, gapurile peste `max_gap_ms` și discontinuitățile Euler ±180° rup seriile. Nu se desenează o linie peste aceste goluri. Culoarea unei caracteristici rămâne aceeași după întrerupere. Panoul „Calitatea datelor” enumeră și intervalele eșantioanelor lipsă/gapurile. Un grafic fără date valide este marcat `N/A`; zero numeric rămâne zero.

Fiecare grafic are un buget de 10000 de puncte. La depășire este afișat un mesaj și doar un prefix al seriilor este desenat; restrânge intervalul pentru inspectarea restului. Evaluarea numerică folosește întreaga sesiune, nu acest prefix. Citirea CSV este în memorie și sincronă; fișiere foarte mari pot necesita exportul prealabil al unei sesiuni mai scurte. Nu există interpolare sau resampling ascuns.

## Clipiri automate și referințe manuale

Panoul „Clipiri și referințe” are două tabele separate:

- evenimente automate importate din `--output-blinks-csv`, numai pentru citire și etichetate „automat nevalidat”;
- referințe manuale independente, editabile, cu `eye,start_ms,end_ms`.

Detecțiile nu sunt copiate automat în referințe. Timeline-ul arată intervalele automate și manuale pe rânduri diferite. Numărul afișat este numărul de rânduri din fișier, nu dovada că detectorul a fost configurat corect. Frecvența este `N/A` până când există ≥10000 ms de EAR valid și configurația sesiunii declară `blink_detection_enabled=true`. Evenimentele din afara intervalelor EAR valide sunt excluse din numărătorul ratei. Un fișier automat gol nu dovedește singur că algoritmul a fost activat.

## Adnotarea video și sincronizarea

„Adnotare video” → deschide videoclipul autorizat al **aceleiași sesiuni**. Sliderul și butoanele anterior/următor navighează cadru cu cadru prin OpenCV. Nu rulează MediaPipe și nu înregistrează nimic.

Pentru fiecare cadru, navigatorul:

1. cere indexul de cadru și decodează imaginea;
2. verifică indexul raportat de backend după decodare;
3. asociază indexul cu `frame_index` și `timestamp_ms` din CSV;
4. afișează `N/A` și refuză marcarea dacă asocierea lipsește sau indexul nu este confirmat.

Astfel, referințele folosesc aceeași axă temporală ca procesarea, inclusiv ajustarea primului timestamp la calibrare. Nu se estimează alt timestamp din poziția unui player. Metoda nu poate demonstra că utilizatorul a ales același fișier dacă un alt video are aceiași indici; păstrează asocierea ID înregistrare–CSV–video în registrul experimentului. Backendul și timestampurile fallback din etapa 4 limitează precizia temporală fizică.

Selectează ochiul subiectului (`left/right`), mergi la început și apasă „Marchează început”, apoi la sfârșit și „Marchează sfârșit”. Evenimentul apare numai în tabelul manual. Durata și granițele sunt cuantizate de cadrele disponibile; o eroare sub-cadru nu poate fi eliminată de acest instrument.

Se pot adăuga sau edita direct rânduri când video nu este disponibil. Apasă „Aplică editările manuale”; sunt respinse intervalele negative/inversate, ochii invalizi și suprapunerile pe același ochi. „Export referințe manuale” scrie un CSV nou, compatibil cu `compare_blinks.py` și `run_validation.py`. Datele automate rămân neschimbate. Exportul și salvarea sunt explicite.

## Evaluare, scenarii și rapoarte

În „Validare și scenarii”, importă/editează configurația JSON și apasă „Evaluează sesiunea completă”. Intervalul grafic nu modifică în tăcere setul evaluat; pentru scenarii folosește lista `scenarios` din configurație.

Motorul existent calculează acoperirea și metricile compatibile. Tabelul arată explicit `N/A` pentru metrici nedefinite, inclusiv MAE/RMSE fără referințe numerice independente sau precision/recall/F1 când referința clipirilor nu este completă. Elementele `scenarios`, `conditions` și `repeat_differences` permit compararea condițiilor experimentale. Metricile confirmă cel mult acordul cu referința furnizată; nu certifică automat calitatea ei.

Pentru precizia head pose, păstrează convențiile/reperul din etapa 6 și declară `head_reference_verified=true` numai după verificarea independentă. Categoriile stânga/dreapta/centru nu se transformă în erori în grade. Pentru iris, diferențiază dispersia geometriei de validarea direcției reale a privirii.

O sesiune cu rol calibration nu poate fi evaluată ca validation. Profilul importat contribuie cu sesiunile lui de calibrare la verificarea separării. Metadatele nu pot detecta un clip redenumit sub alt ID; separarea reală trebuie asigurată prin protocol.

„Export explicit raport JSON/CSV” reevaluează configurația curentă și creează un subdirector nou `report-UUID` în directorul ales. Reutilizează `save_report` din `validation.py`; fișierele nu sunt trimise în rețea.

## Protocol practic pentru primele înregistrări reale

1. Obține permisiunile necesare și informează participanții despre date, scop și păstrare. Pentru minori, urmează cerințele aplicabile și protocolul instituției privind acordul părinților/tutorilor. Folosește ID-uri anonime, fără nume în fișierele de analiză.
2. Colectează separat sesiunea de calibrare C01: poziție neutră, ochi deschiși/închiși, condițiile camerei documentate. Creează profilul prin `calibrate_session.py`.
3. Colectează o altă sesiune V01 autorizată, fără ajustarea ulterioară a pragurilor pe ea. Înregistrarea video este un pas explicit extern; dashboardul nu o pornește.
4. Procesează V01 prin scriptul existent cu profilul și exporturile pe cadru/evenimente. Importă CSV-ul în dashboard cu același ID. De exemplu:

```powershell
.\.venv\Scripts\python.exe run_video_analysis.py --source "data/validation/validation/V01/video.mp4" --calibration "results/calibration_C01.json" --no-display --output-csv "results/V01_frames.csv" --output-blinks-csv "results/V01_blinks.csv"
.\.venv\Scripts\python.exe run_dashboard.py --measurements "results/V01_frames.csv" --session-id V01
```

5. Încarcă video corespunzător și marchează manual evenimentele, preferabil înainte de consultarea predicțiilor automate, pentru a reduce influențarea adnotării. Dacă este posibil, verifică acordul între adnotatori. Declară separat dacă referința acoperă complet intervalele evaluabile.
6. Importă detecțiile automate și referințele numerice independente disponibile. Calculează metricile numai în condițiile compatibile; inspectează lipsurile și potrivirile temporale.
7. Inspectează erorile și scenariile: iluminare, orientare, ocluzii și pierderea feței. Nu modifica automat marcajele ca să se potrivească predicțiilor. O nouă optimizare cere un alt set final separat.
8. Exportă raportul, configurația și referințele, notează limitările și păstrează/șterge datele conform perioadei convenite. Generalizarea între persoane necesită participanți separați când aceasta este afirmația studiului.

## Limitări și verificări

Dashboardul este un instrument de inspecție offline, cu navigare video pe cadre, nu un player cu audio sau un nou procesor de sesiuni live. Nu identifică persoane și nu produce clasificări ale emoțiilor, atenției sau concentrării.

Sesiunile salvate conțin măsurători geometrice și trebuie gestionate ca date experimentale. Copiile gestionate se pot șterge explicit; originalele externe și backupurile trebuie eliminate separat de persoana responsabilă. Nu există salvare automată de fotografii, video sau marcaje.

Validarea efectivă pe persoane necesită înregistrări autorizate și referințe independente. Capturile de interfață și testele sintetice verifică funcționarea software-ului, nu precizia măsurătorilor pe oameni.

### Verificări executate

- `.\.venv\Scripts\python.exe -m pytest -q --basetemp artifacts\pytest-dashboard-stage7-acceptance`: **200 passed** în selecția implicită completă; 24 cazuri noi față de etapa 6. Testele istorice `tests/test_*.py` nu au fost reexecutate.
- Testele includ CSV incomplet, coloane calibrate, goluri/wrap Euler, intervale, grafice QtCharts, culori și bugetul de puncte, marcaje independente și export compatibil, salvare/reîncărcare, snapshot stabil după modificarea sursei, refuzul ștergerii în afara domeniului sau cu fișiere neașteptate, navigare video simulată, index neconfirmat, integrarea UI cu `validation.py` și `N/A` fără referințe.
- Referința sintetică cu eroare yaw cunoscută de 1° a fost evaluată prin dashboard cu MAE=1°. Aceasta verifică legătura cu motorul de validare, nu acuratețea pe persoane.
- A fost executată intrarea CLI `run_dashboard.py --measurements artifacts/stage4-smoke-final.csv`, în mod Qt offscreen cu închidere automată. CSV-ul real al clipului sintetic gol conține 20 cadre, 0 fețe; graficele și metricile fără referință sunt marcate N/A.
- Navigatorul OpenCV real a deschis `artifacts/mvp_blank.avi`: cadrele 0 și 10 au fost asociate cu timestampurile CSV 0 și 2000 ms. Un marcaj introdus tehnic de la cadrul 0 la cadrul 2 a exportat 0…400 ms în `artifacts/dashboard-stage7-technical-manual.csv`, citibil cu `read_blinks`. Acest marcaj arbitrar pe un clip fără față nu este referință fiziologică sau clipire observată.
- Capturile `artifacts/dashboard-stage7-charts.png` și `artifacts/dashboard-stage7-final.png` au fost inspectate vizual. Pentru randarea offscreen, testul de inspecție a încărcat explicit fontul Windows Segoe UI disponibil local; produsul folosește fontul sistemului. Nu s-a pornit o cameră și nu s-a încărcat modelul în dashboard.

Nu există încă o sesiune autorizată cu persoane și marcaje independente reale. Următorul pas este aplicarea protocolului de mai sus pe C01/V01, verificarea manuală a sincronizării și adnotarea fără consultarea prealabilă a predicțiilor.
