# Lucrul în acest repository

Taskul 04 este păstrat ca mini-template simulat. Utilitarul nou rulează în terminal: `python -m audience_analysis FIȘIER`. La o sursă selectată explicit poate încărca modelul local pentru statistici de expresie.

- `contracts.py`, `config.py`: contractul comun P1/P2/P3; actualizează testele și `docs/contracts.md` la modificări.
- P1: `ai/`, `notebooks/template/`, `tests/ai/`; nu citește surse, nu gestionează cozi/UI.
- P2: `video/`, `engine/`, testele aferente; deține preprocesarea comună și unicul lucrător AI. Nu modifică widgeturi.
- P3: `ui/`, `tests/ui/`; primește motorul în constructor. Nu muta motorul în UI, nu duplica preprocesarea sau schedulerul.
- Nu ascunde simulările. Fără flag demo nu porni automat surse sau FakePredictor.
- Modulele anterioare din rădăcina pachetului și `legacy_*` sunt păstrate; nu le șterge și nu le activa implicit în demo.
- Nu descărca date și nu antrena modele. La cererea explicită a utilizatorului, utilitarul terminal poate descărca modelul Hugging Face de statistică la prima utilizare; nu adăuga ponderi/cache/video în Git. Checklisturile din `docs/planning/` rămân nebifate până la validarea echipei.

Instalare locală: `python -m pip install -e ".[dev]"` într-un venv. Testele mini-template-ului: `python -m pytest`. P1: `python -m audience_analysis.examples.p1_predictor_demo`. P2: `python -m audience_analysis.examples.p2_engine_demo`. UI: `python -m audience_analysis --ui-demo` și `--demo`.

Testele anterioare `tests/test_*.py` sunt păstrate separat de selecția implicită pytest și pot necesita cv2/torch. Testele terminalului folosesc false/mocks, fără modele sau rețea. Nu raporta testele istorice ca reexecutate. Nu face commit/push automat sau instalări globale.
