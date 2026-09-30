import importlib.util
from pathlib import Path
import unittest


class AppointmentModuleTest(unittest.TestCase):
    def test_appointments_blueprint_is_registered(self):
        root_path = Path(__file__).resolve().parents[1] / "app.py"
        spec = importlib.util.spec_from_file_location("root_entrypoint", root_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        rules = {rule.rule for rule in module.app.url_map.iter_rules()}
        self.assertIn("/appointments", rules)
        self.assertIn("/appointments/book", rules)
        self.assertIn("/appointments/calendar", rules)

    def test_appointment_model_is_available(self):
        from routes.appointments import Appointment

        self.assertTrue(hasattr(Appointment, "id"))


if __name__ == "__main__":
    unittest.main()
