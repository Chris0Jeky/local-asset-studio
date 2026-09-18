from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_adult_illustration_benchmark_result.py"
FILES = (
    "benchmark-result-example.json",
    "benchmark-corpus.json",
    "route-candidates.json",
)
AUTHORITY_FIELDS = (
    "download_authorized",
    "install_authorized",
    "execution_authorized",
    "generation_submitted",
    "training_authorized",
    "promotion_authorized",
)


def load_cli():
    spec = importlib.util.spec_from_file_location(
        "validate_adult_illustration_benchmark_result", SCRIPT
    )
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load CLI from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def copy_contract(root: Path) -> Path:
    target = root / "research" / "adult-illustration"
    target.mkdir(parents=True)
    source = ROOT / "research" / "adult-illustration"
    for name in FILES:
        shutil.copy2(source / name, target / name)
    return target


class AdultIllustrationBenchmarkResultCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cli = load_cli()

    def test_checked_in_contract_validates_offline(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = self.cli.main(["--root", str(ROOT)])
        self.assertEqual(status, 0, stderr.getvalue())
        self.assertEqual(stdout.getvalue(), "adult illustration benchmark result: OK\n")
        self.assertEqual(stderr.getvalue(), "")

    def test_tampered_result_returns_structured_zero_authority_error(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            target = copy_contract(root)
            path = target / "benchmark-result-example.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["accounting"]["retained_candidates"] = 1
            path.write_text(json.dumps(value) + "\n", encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                status = self.cli.main(["--root", str(root)])

        self.assertEqual(status, 2)
        self.assertEqual(stdout.getvalue(), "")
        payload = json.loads(stderr.getvalue())
        self.assertEqual(
            payload["schema"],
            "studio.adult-illustration-benchmark-result-error/v1",
        )
        self.assertEqual(payload["authority"], "none")
        self.assertFalse(payload["executable"])
        self.assertIn("retained", payload["error"].casefold())
        for field in AUTHORITY_FIELDS:
            self.assertIs(payload[field], False)

    def test_duplicate_json_key_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            target = copy_contract(root)
            path = target / "benchmark-result-example.json"
            text = path.read_text(encoding="utf-8")
            text = text.replace(
                '"schema":"studio.adult-illustration-benchmark-result/v1"',
                '"schema":"duplicate","schema":"studio.adult-illustration-benchmark-result/v1"',
                1,
            )
            path.write_text(text, encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = self.cli.main(["--root", str(root)])

        self.assertEqual(status, 2)
        self.assertIn("duplicate json key", json.loads(stderr.getvalue())["error"].casefold())

    def test_changed_corpus_bytes_make_result_identity_stale(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            target = copy_contract(root)
            path = target / "benchmark-corpus.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["notes"].append("synthetic mutation")
            path.write_text(json.dumps(value) + "\n", encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = self.cli.main(["--root", str(root)])

        self.assertEqual(status, 2)
        self.assertIn("corpus identity", json.loads(stderr.getvalue())["error"].casefold())


if __name__ == "__main__":
    unittest.main()
