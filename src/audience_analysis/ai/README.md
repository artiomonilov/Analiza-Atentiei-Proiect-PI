# P1 — începe aici

Primul fișier: `predictor.py`. Citește și `../contracts.py`, `../config.py`.

Intrare: PreparedSequence RGB float32 [T,3,H,W], deja normalizată de P2. Ieșire: ModelOutput(levels, model_version, is_demo). FakePredictor întoarce nivelul fix 2, independent de pixeli, exclusiv pentru integrare. RealPredictor nu face fallback.

Exemplu fără Qt, cv2, GPU sau torch:
`python -m audience_analysis.examples.p1_predictor_demo`.

Primul TODO: **P1-S2.1**, `data.py`: manifest autorizat → validare fișiere/etichete/splituri → listă validată, verificată cu cazuri negative. `models.py` indică P1-S3.1 și P1-S5.1; `predictor.py` indică P1-S3.3. Refolosește codul anterior numai după verificarea compatibilității cu noul contract; nu normaliza de două ori.

Notebookuri: `notebooks/template/`. Checklist: [P1](../../../docs/planning/01_P1_Date_AI_saptamanile_1-7.md).
