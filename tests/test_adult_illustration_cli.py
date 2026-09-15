import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "studio_adult_illustration.py"
EXAMPLE = ROOT / "examples" / "adult-illustration" / "hot-spring-study.json"


def load_cli():
    spec = importlib.util.spec_from_file_location("studio_adult_illustration_cli", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load CLI from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdultIllustrationCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cli = load_cli()

    def run_cli(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = self.cli.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_validate_intent_prints_canonical_record_without_submission(self):
        code, stdout, stderr = self.run_cli(["validate-intent", str(EXAMPLE)])
        self.assertEqual(code, 0, stderr)
        value = json.loads(stdout)
        self.assertEqual(value["format"], "studio.adult-illustration.intent/v1")
        self.assertFalse(value["execution_authorized"])
        self.assertFalse(value["generation_submitted"])
        self.assertEqual(stderr, "")

    def test_project_prints_reviewable_unbound_projection(self):
        code, stdout, stderr = self.run_cli(["project", str(EXAMPLE)])
        self.assertEqual(code, 0, stderr)
        value = json.loads(stdout)
        self.assertEqual(value["state"], "requires_binding")
        self.assertFalse(value["execution_authorized"])
        self.assertFalse(value["generation_submitted"])
        self.assertIn("CONTROL_REQUIRES_BINDING", {item["code"] for item in value["diagnostics"]})

    def test_output_is_exclusive_create_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "projection.json"
            first = self.run_cli(["project", str(EXAMPLE), "--out", str(target)])
            self.assertEqual(first[0], 0, first[2])
            original = target.read_bytes()
            second = self.run_cli(["project", str(EXAMPLE), "--out", str(target)])
            self.assertEqual(second[0], 2)
            self.assertEqual(target.read_bytes(), original)
            error = json.loads(second[2])
            self.assertFalse(error["execution_authorized"])
            self.assertFalse(error["generation_submitted"])

    def test_validate_projection_recomputes_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            projection_path = Path(tmp) / "projection.json"
            self.assertEqual(
                self.run_cli(["project", str(EXAMPLE), "--out", str(projection_path)])[0],
                0,
            )
            code, stdout, stderr = self.run_cli(
                ["validate-projection", str(projection_path)]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["state"], "requires_binding")

            changed = json.loads(projection_path.read_text(encoding="utf-8"))
            changed["state"] = "promoted"
            projection_path.write_text(json.dumps(changed), encoding="utf-8")
            code, stdout, stderr = self.run_cli(
                ["validate-projection", str(projection_path)]
            )
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertIn("Changed or invalid", json.loads(stderr)["error"])

    def test_invalid_intent_fails_closed_and_creates_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "invalid.json"
            target = Path(tmp) / "should-not-exist.json"
            value = json.loads(EXAMPLE.read_text(encoding="utf-8"))
            del value["subjects"][0]["adult_assertion"]
            source.write_text(json.dumps(value), encoding="utf-8")
            code, stdout, stderr = self.run_cli(
                ["validate-intent", str(source), "--out", str(target)]
            )
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertFalse(target.exists())
            error = json.loads(stderr)
            self.assertIn("adult", error["error"].lower())
            self.assertFalse(error["generation_submitted"])

    def test_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "duplicate.json"
            source.write_text('{"format":"a","format":"b"}', encoding="utf-8")
            code, stdout, stderr = self.run_cli(["validate-intent", str(source)])
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertIn("Duplicate JSON key", json.loads(stderr)["error"])

    def test_blocked_projection_is_returned_for_review_not_relabelled_as_cli_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "blocked.json"
            value = json.loads(EXAMPLE.read_text(encoding="utf-8"))
            value["references"][0]["roles"] = ["edit_source"]
            source.write_text(json.dumps(value), encoding="utf-8")
            code, stdout, stderr = self.run_cli(["project", str(source)])
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertEqual(result["state"], "blocked")
            self.assertIsNone(result["creative_intent"])
            self.assertFalse(result["generation_submitted"])


if __name__ == "__main__":
    unittest.main()
