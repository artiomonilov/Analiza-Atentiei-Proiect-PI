# P1 — începe aici

Primul fișier: `predictor.py`. Citește și `../contracts.py`, `../config.py`.

Intrare: PreparedSequence RGB float32 [T,3,H,W], deja normalizată de P2. Ieșire: ModelOutput(levels, model_version, is_demo). FakePredictor întoarce nivelul fix 2, independent de pixeli, exclusiv pentru integrare. RealPredictor nu face fallback.

Exemplu fără Qt, cv2, GPU sau torch:
`python -m audience_analysis.examples.p1_predictor_demo`.

`data.py` validează manifestele/spliturile și cache-urile și reutilizează pregătirea P2. `models.py` reutilizează encoderul/mean/GRU legacy, opțional cu capete separate, fără download. `package.py` încarcă/exportă state_dict și metadate verificate; `RealPredictor` încarcă o singură dată și transmite intrarea deja normalizată. `evaluation.py` oferă R0 și comparație pe subset comun, cu selecție numai pe validation. Nu există ponderi DAiSEE evaluate în repository și nu se fabrică rezultate din geometrie.

Comenzi independente: `python -m audience_analysis.ai.cli --help` sau entry point `audience-ai`. Model lipsă: cod 4, MODEL_UNAVAILABLE și levels=null; FakePredictor nu este fallback. Formatul pachetului, utilizarea și blocajele sunt în [docs/p1-data-model.md](../../../docs/p1-data-model.md).

Notebookuri: `notebooks/template/`. Checklist: [P1](../../../docs/planning/01_P1_Date_AI_saptamanile_1-7.md).
