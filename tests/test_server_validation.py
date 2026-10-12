import importlib.util
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("asset_server", Path(__file__).parents[1] / "app/server.py")
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)


class ServerValidationTests(unittest.TestCase):
    def test_number_rejects_bool_nan_and_inside_rejects_escape(self):
        with self.assertRaises(server.StudioError):
            server.number(True, "seed", 0, 10)
        with self.assertRaises(server.StudioError):
            server.number(float("nan"), "cfg", 0, 30)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            with self.assertRaises(server.StudioError):
                server.inside(root, root / ".." / "etc" / "x")
        self.assertEqual(server.combo_options(["COMBO", {"options": ["a", 1]}]), ["a"])
        self.assertEqual(server.combo_options([["a", 1, None], {}]), ["a"])


if __name__ == "__main__":
    unittest.main()
