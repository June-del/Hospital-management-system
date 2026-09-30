import importlib.util
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent / "Hospital-Management-System"
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

SPEC = importlib.util.spec_from_file_location("hospital_app", PROJECT_DIR / "app.py")
if SPEC is None or SPEC.loader is None:
    raise ImportError("Unable to load the hospital application entrypoint.")

hospital_app_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = hospital_app_module
SPEC.loader.exec_module(hospital_app_module)
app = hospital_app_module.app


if __name__ == "__main__":
    app.run(debug=True)
