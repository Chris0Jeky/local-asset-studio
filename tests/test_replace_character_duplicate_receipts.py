"""Duplicate evidence keys must fail closed before any expensive transport call."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "experiments/curated/fantasy-pack-20260916"


def _load_script(filename: str):
    path = SCRIPTS / filename
    spec = importlib.util.spec_from_file_location("duplicate_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DuplicateResearchReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.single = _load_script("pack_replacechar.py")
        cls.chain = _load_script("pack_replacechar_chain.py")

    @staticmethod
    def _forbidden(*_args, **_kwargs):
        raise AssertionError("ambiguous evidence must fail before contacting Studio or ComfyUI")

    def test_duplicate_single_seed_fails_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            results = root / "results.json"
            results.write_text(json.dumps([
                {"variant": "replacechar", "seed": 7, "prompt_id": "a", "status": "success"},
                {"variant": "replacechar", "seed": 7, "prompt_id": "b", "status": "submitted"},
            ]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate.*replacechar.*7"):
                self.single.run(
                    7,
                    results_path=results,
                    graph_dir=root / "graphs",
                    open_url=self._forbidden,
                    sleeper=lambda _seconds: None,
                )

    def test_duplicate_chain_seed_fails_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            results = root / "results.json"
            results.write_text(json.dumps([
                {"group": "chain", "seed": 9, "prompt_id": "a", "status": "success"},
                {"group": "chain", "seed": 9, "prompt_id": "b", "status": "submitted"},
            ]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate.*chain.*9"):
                self.chain.run(
                    "chain",
                    "image-1.png",
                    "image-2.png",
                    9,
                    results_path=results,
                    graph_dir=root / "graphs",
                    open_url=self._forbidden,
                    sleeper=lambda _seconds: None,
                )

    def test_chain_preflight_validates_later_keys_before_reporting_missing_work(self):
        with tempfile.TemporaryDirectory() as raw:
            results = Path(raw) / "results.json"
            results.write_text(json.dumps([
                {"group": "chain", "seed": 9, "prompt_id": "a", "status": "success"},
                {"group": "chain", "seed": 9, "prompt_id": "b", "status": "submitted"},
            ]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate.*chain.*9"):
                self.chain.has_unrecorded("chain", (8, 9), path=results)


if __name__ == "__main__":
    unittest.main()