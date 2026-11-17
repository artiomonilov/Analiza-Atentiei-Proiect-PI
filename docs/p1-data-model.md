# P1 — date, predictor, evaluare și predare

Aceste module nu citesc camere, nu decodează videoclipuri, nu gestionează cozi și nu desenează UI. Sunt utilizabile fără branchurile colegilor. Importul lor nu încarcă torch/Qt/OpenCV și nu descarcă nimic. Nu este furnizat un model de angajament antrenat sau validat pe DAiSEE.

## Date și pregătire

`ai.data.load_training_manifest(path, verify_files=True, check_content=True)` citește CSV cu `clip_id,participant_id,path,split,engagement`; opțional `boredom,confusion,frustration`. ID-urile trebuie să fie anonime. `split` este train/validation/test, nivelurile sunt întregi 0–3; o dimensiune opțională goală este absentă, nu nivelul 0. Rezultatul este o listă de dicționare cu ID-uri, Path local, split și `labels`. Căile sunt necesare încărcării locale, nu sunt exportate automat în rapoartele P1.

Loaderul verifică fișierele, duplicatele de clip/cale/conținut și participantul prezent în două splituri. Hashurile nu detectează re-encodarea sau identitatea semantică; împărțirea reală a DAiSEE trebuie verificată pe fișierele și permisiunile primite. Nu se presupune că splitul oficial satisface automat orice obiectiv de generalizare.

`prepare_sequence(frames_bgr, sample_times_s, config)` reutilizează **exact** `video.preprocessing.prepare_bgr`: nearest-neighbor, BGR→RGB, scalare, normalizare și CHW. Nu construiește un cropper P1 paralel. `load_prepared_sequence` citește NPZ cu `allow_pickle=False`, câmpuri `frames`, `sample_times_s`, `preprocessing_id`. Frames trebuie să fie float32 `[T,3,H,W]`, finite și deja normalizate. Timpii sunt secunde strict crescătoare; durata trebuie să corespundă ferestrei modelului în toleranța a două capete. `iter_samples` livrează `(clip_id, PreparedSequence, label)` pentru splitul și dimensiunea cerute, fără a umple etichetele lipsă.

`SequenceConfig` este contractul existent. Valorile sale implicite sunt pentru demo, nu pentru un model real. Pentru arhitectura legacy cu ImageNet trebuie utilizate mean `(0.485,0.456,0.406)` și std `(0.229,0.224,0.225)`, dimensiunea și T ale modelului. Testul `test_imagenet_training_inference_preprocessing_parity` compară direct pregătirea P1 cu normalizarea legacy pe aceleași pixeli. Compatibilitatea cropului și paritatea Colab pe modelul real necesită ulterior P2 și datele autorizate.

## Modele și pachet

`ai.models.build_baseline`, `build_temporal` și `build_model` reutilizează `models.EngagementModel`: encoder MobileNetV3 Small înghețat, mean sau GRU. Fabricile folosesc întotdeauna `pretrained=False`, deci nu descarcă ImageNet. Pot pregăti capete separate pentru dimensiunile cerute, în ordinea engagement, boredom, confusion, frustration. Construirea arhitecturii nu înseamnă antrenare; modelele nou construite nu trebuie exportate/prezentate ca predictori evaluați.

Pachet local:

```text
model_package/
  manifest.json
  weights.pt        # state_dict din modelul real furnizat, nu obiect Python pickled
```

Manifestul are exact: schema_version=1, architecture mean/gru, hidden_size, dimensions, labels, sequence, weights_sha256, model_version, training, evaluation. `labels` este dicționarul dimensiunilor disponibile cu ordinea `[0,1,2,3]` pentru fiecare. `sequence` este `asdict(SequenceConfig)`. Training declară `trained=true` și `manifest_sha256`; evaluation declară `validated=true`, `split=validation`, `samples>0`, `dataset_sha256` identic cu manifestul training și `report_sha256`. Hashurile sunt SHA256 hex. Aceste declarații nu sunt o dovadă criptografică sau științifică a calității: producătorul și reviewerul trebuie să verifice raportul și drepturile datelor.

`ai.package.export_package(directory, model, config, training=..., evaluation=...)` validează aceste metadate înainte de crearea directorului, apoi salvează **modelul primit** și checksumul. Nu antrenează și nu inventează ponderi. Directorul trebuie să fie nou. Bundle-ul legacy nu este acceptat automat drept pachet validat: se reutilizează arhitectura/state_dict compatibil, dar configurația comună și dovezile evaluării trebuie furnizate explicit de producător. Nu există în repository un exemplu de weights cu etichetă fictivă „trained”.

`RealPredictor(package_path, config=None)` încarcă modelul o singură dată în constructor, verifică manifestul și checksumul, folosește `torch.load(..., weights_only=True)`, `load_state_dict(strict=True)`, CPU/eval și `torch.inference_mode`. `predict(PreparedSequence)` transmite direct float32 RGB CHW, fără normalizare suplimentară. Logits trebuie să fie patru valori reale finite pentru fiecare dimensiune declarată. Rezultatul este `ModelOutput(levels, model_version, is_demo=False)`; level este ordinal 0–3, nu probabilitate, atenție sau stare psihologică demonstrată.

La pachet/ponderi/dependențe lipsă sau incompatibile, constructorul ridică `ModelUnavailableError`, cu `status=Status.MODEL_UNAVAILABLE`. Niciun FakePredictor nu este încărcat automat. Fabrica din engine poate lăsa constructorul să eșueze, iar motorul existent raportează indisponibilitatea; UI-ul real/demo și integrarea surselor rămân responsabilitățile P2/P3.

## Evaluare

`ai.evaluation.majority_class` calculează R0 **numai din etichetele train**, cu departajare deterministă spre clasa mai mică. `compare_models` primește ținte și predicții aliniate, inclusiv None pentru indisponibilitate. Compară R0/mean/GRU pe același subset comun observabil și raportează separat acoperirea fiecărui model. Metricile NumPy reutilizate sunt confusion matrix 4×4, accuracy, macro-F1 pe toate patru clasele cu zero_division=0 și balanced accuracy pe clasele prezente. Fără subset comun, metricile sunt None/N/A. Nu există imputare de nivel 0.

`choose_on_validation` refuză rapoarte de pe test. API-ul nu urmărește ce rapoarte a văzut operatorul; separarea reală și înghețarea selecției trebuie respectate procedural. `data_kind=synthetic` marchează fixture-urile; `authorized` este o declarație a operatorului, nu verificarea automată a permisiunilor. Evaluările DAiSEE și comparațiile de rezoluție/crop rămân blocate de materiale și model real.

## Comenzi

Din repository folosește Pythonul mediului separat sau, după instalarea wheel/editable, entry point-ul `audience-ai`:

```powershell
.\.venv-completion\Scripts\python.exe -m audience_analysis.ai.cli check-data "data/manifest.csv"
.\.venv-completion\Scripts\python.exe -m audience_analysis.ai.cli inspect-model "data/model_package"
.\.venv-completion\Scripts\python.exe -m audience_analysis.ai.cli predict-cache "data/model_package" "data/sequence.npz"
.\.venv-completion\Scripts\python.exe -m audience_analysis.ai.cli compare "data/predictions.json" --output "reports/p1-comparison.json"
```

`inspect-model`/`predict-cache` întorc cod 4 și JSON `{status: MODEL_UNAVAILABLE, levels: null}` dacă modelul lipsește; cod 2 indică date/configurație invalide. `compare` citește un obiect JSON cu `training_labels`, `targets`, `predictions` (nume model → listă), opțional `split` și `data_kind`. Fișierul de ieșire trebuie să fie nou. Nicio comandă nu pornește antrenare, cameră, scheduler sau UI.

Pentru Colab se instalează același pachet și se folosesc aceleași funcții; nu se copiază formula de normalizare în notebook. Execuția Colab și paritatea cu un model real nu au fost declarate verificate.
