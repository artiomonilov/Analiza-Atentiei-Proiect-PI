# P1 — documentare și conținut pentru raport/prezentare

Documentare realizată la 16 noiembrie 2026, din surse primare. Nu s-a descărcat DAiSEE, nu s-a antrenat un model și nu s-au atribuit rezultate ale autorilor acestui proiect.

## Surse și relevanță

1. **Gupta et al., DAiSEE: Towards User Engagement Recognition in the Wild**, arXiv v7. Lucrarea descrie 9068 fragmente de la 112 utilizatori, patru dimensiuni (boredom, confusion, engagement, frustration), cu patru niveluri fiecare și adnotare agregată/verificată prin experți. Pentru proiect, etichetele trebuie păstrate separat și spliturile auditate pe materialele primite. Numerele din publicație nu sunt inventarul nostru; nu există încă fișiere DAiSEE verificate aici. Orientarea capului și EAR nu înlocuiesc aceste etichete. [Lucrarea și versiunea](https://arxiv.org/abs/1609.01885v7), [PDF](https://arxiv.org/pdf/1609.01885).
2. **Howard et al., Searching for MobileNetV3**, ICCV 2019. Modelul combină căutare de arhitectură orientată spre hardware și ajustare NetAdapt, cu variante Small/Large. Small este o bază rezonabilă de encoder pentru resurse locale; aceasta este alegerea proiectului, nu o concluzie a lucrării despre angajament. Rezultatele autorilor sunt pe sarcini de viziune, nu o validare DAiSEE a adaptorului nostru. Latența pe laptop trebuie măsurată separat. [Lucrarea](https://arxiv.org/abs/1905.02244v5).
3. **Cho et al., Learning Phrase Representations using RNN Encoder–Decoder**, EMNLP 2014. Articolul descrie reprezentarea secvențelor și unitatea recurentă cu porți, evaluată în traducere automată. Refolosirea unei GRU după encoderul vizual este o ipoteză tehnică a proiectului: păstrează ordinea cadrelor, dar nu garantează îmbunătățirea față de mean pooling. Comparația trebuie făcută pe același split/subset și cu aceleași imagini pregătite. Nu transferăm scorurile de traducere la recunoașterea angajamentului. [Lucrarea](https://aclanthology.org/D14-1179/), [PDF](https://aclanthology.org/D14-1179.pdf).

Pagina [DAiSEE a autorilor](https://people.iith.ac.in/vineethnb/resources/daisee/index.html) nu a răspuns în încercarea de verificare. Condițiile actuale, accesul și permisiunea de utilizare rămân **NOT VERIFIED**; publicarea unui articol nu acordă automat dreptul de redistribuire a datelor. Trebuie obținute documentele și aprobările aplicabile înainte de colectare/antrenare. Nu se inventează un acord sau un responsabil nominal.

## Text reutilizabil — metodă și limite

Implementarea separă două obiective: infrastructura unui predictor de etichete DAiSEE și măsurători geometrice faciale. P1 validează manifestul, participanții disjuncți, etichetele, fișierele și secvențele. Reutilizează preprocesarea comună BGR→RGB→float32 CHW și arhitecturile MobileNetV3 Small cu mediere sau GRU. Fabricile pot defini capete separate pentru dimensiuni, dar nicio ieșire nu este prezentată ca antrenată doar prin existența arhitecturii.

Evaluarea software verifică formele, normalizarea, ordinea claselor, încărcarea sigură și erorile. Comparația modelelor folosește un subset comun observabil și baseline-ul majoritar din train. Selecția se face pe validation, iar testul final rămâne separat. Pentru geometrie, profilul C01 este separat de dezvoltarea D01 și validarea independentă V01. Referințele manuale sunt independente de evenimentele automate. MAE/RMSE unghiulare rămân N/A fără măsurători independente ale orientării.

Nu există rezultate DAiSEE sau un model real de angajament predat. Nu se raportează acuratețe din fixture-uri, din funcționarea dashboardului sau din numărul testelor. Clipirile, geometria irisului și orientarea capului nu demonstrează singure atenție, emoții ori implicare. Validarea pe persoane, generalizarea, performanța pe hardware și paritatea Colab cu modelul real sunt lucrări externe încă necesare.

## Contribuție P1 pentru prezentarea comună de 6–7 slide-uri

Conținutul de mai jos poate fi preluat de echipă; nu este o prezentare susținută sau un poster final:

1. **Scop și limite:** predictor ordinal posibil, laborator geometric existent, fără clasificare a atenției.
2. **Date:** cele patru dimensiuni, auditul manifestului și spliturilor; inventarul local real rămâne de completat după autorizare.
3. **Metodă:** encoder înghețat, mean versus GRU, preprocesare comună și capete numai pentru dimensiuni antrenate/evaluate.
4. **Integrare P1:** PreparedSequence → RealPredictor → ModelOutput; MODEL_UNAVAILABLE fără fallback.
5. **Verificări software:** teste și rezultate exacte din `artiom-branch-completion.md`; fixture-urile sunt sintetice, nu metrici de model.
6. **Evaluare planificată:** R0, macro-F1/BA/confuzie, acoperire și subset comun; pentru laborator C/D/V și referințe independente.
7. **Ce lipsește:** date/weights/permisiuni, evaluare reală, paritate Colab, repetiție cu echipa și contribuții nominale confirmate.

Pentru exemple corecte/greșite, articol/poster cu rezultate sau demo real sunt necesare etichetele și modelul efectiv. Nu există în acest document rezultate sau imagini fictive. Feedbackul trebuie înregistrat după prezentarea reală, cu ID de observație, sursă, decizie, rol responsabil și test/rezultat de acceptare; aici nu este fabricat feedback istoric.
