from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

from tests.test_adult_illustration_prompt_profiles import sample_projection

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/studio_adult_illustration_prompt.py"


def load_cli():
    spec = importlib.util.spec_from_file_location("adult_prompt_cli", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load CLI from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdultIllustrationPromptCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cli = load_cli()

    def run_cli(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = self.cli.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_profiles_lists_non_executing_pinned_profiles(self):
        code, stdout, stderr = self.run_cli(["profiles", "--repo-root", str(ROOT)])
        self.assertEqual(code, 0, stderr)
        value = json.loads(stdout)
        self.assertEqual(len(value["profiles"]), 3)
        self.assertTrue(all(item["execution_authorized"] is False for item in value["profiles"]))

    def test_compile_and_validate_round_trip_without_submission(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.json"
            compiled = Path(tmp) / "compiled.json"
            source.write_text(json.dumps(sample_projection()), encoding="utf-8")
            code, stdout, stderr = self.run_cli([
                "compile", str(source), "--profile", "qwen-edit-2511-instruction-v1",
                "--repo-root", str(ROOT), "--out", str(compiled),
            ])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(stdout, "")
            value = json.loads(compiled.read_text(encoding="utf-8"))
            self.assertFalse(value["authority"]["generation_submitted"])
            code, stdout, stderr = self.run_cli([
                "validate", str(compiled), "--source", str(source),
                "--repo-root", str(ROOT),
            ])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout), value)

    def test_output_is_exclusive_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.json"
            target = Path(tmp) / "compiled.json"
            source.write_text(json.dumps(sample_projection()), encoding="utf-8")
            args = [
                "compile", str(source), "--profile", "animagine-xl4-ordered-v1",
                "--repo-root", str(ROOT), "--out", str(target),
            ]
            self.assertEqual(self.run_cli(args)[0], 0)
            original = target.read_bytes()
            code, stdout, stderr = self.run_cli(args)
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertEqual(target.read_bytes(), original)
            error = json.loads(stderr)
            self.assertFalse(error["execution_authorized"])
            self.assertFalse(error["generation_submitted"])


if __name__ == "__main__":
    unittest.main()
