# Lucrul în acest repository

Taskul 04 este un mini-template simulat, nu MVP-ul cu AI real.

- `contracts.py`, `config.py`: contractul comun P1/P2/P3; actualizează testele și `docs/contracts.md` la modificări.
- P1: `ai/`, `notebooks/template/`, `tests/ai/`; nu citește surse, nu gestionează cozi/UI.
- P2: `video/`, `engine/`, testele aferente; deține preprocesarea comună și unicul lucrător AI. Nu modifică widgeturi.
- P3: `ui/`, `tests/ui/`; primește motorul în constructor. Nu muta motorul în UI, nu duplica preprocesarea sau schedulerul.
- Nu ascunde simulările. Fără flag demo nu porni automat surse sau FakePredictor.
- Modulele anterioare din rădăcina pachetului și `legacy_*` sunt păstrate; nu le șterge și nu le activa implicit în demo.
- Nu descărca date/ponderi și nu antrena modele în cadrul taskului 04. Checklisturile din `docs/planning/` rămân nebifate până la validarea echipei.

Instalare locală: `python -m pip install -e ".[dev]"` într-un venv. Testele mini-template-ului: `python -m pytest`. P1: `python -m audience_analysis.examples.p1_predictor_demo`. P2: `python -m audience_analysis.examples.p2_engine_demo`. UI: `python -m audience_analysis --ui-demo` și `--demo`.

Testele anterioare `tests/test_*.py` sunt păstrate separat de selecția implicită pytest și pot necesita cv2/torch. Nu raporta testele istorice ca reexecutate. Nu face commit/push automat sau instalări globale.
