import importlib.util
from pathlib import Path
import unittest


class RootLauncherImportTest(unittest.TestCase):
    def test_root_entrypoint_imports_flask_app(self):
        root_path = Path(__file__).resolve().parents[1] / "app.py"
        spec = importlib.util.spec_from_file_location("root_entrypoint", root_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertTrue(hasattr(module, "app"))
        self.assertIn("/login", [rule.rule for rule in module.app.url_map.iter_rules()])


if __name__ == "__main__":
    unittest.main()
