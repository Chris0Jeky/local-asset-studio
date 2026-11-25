"""Offline cross-check; set P35_SOURCE_ROOT for a separate pinned source tree."""
import json
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

import source_contract_check as check


class SourceContractCheckTests(unittest.TestCase):
    def source_paths(self):
        package = Path(os.environ.get("P35_PACKAGE_ROOT", Path(__file__).resolve().parent))
        source = Path(os.environ.get("P35_SOURCE_ROOT", package.resolve().parents[3]))
        if not (source / "app" / "server.py").is_file():
            self.skipTest("Full pinned source unavailable; run source_contract_check.py --source-root with it")
        return source, package

    def test_production_hash_escapes_unicode(self):
        value = {"prompt": "Picture 1 — Épée"}
        expected = hashlib.sha256(b'{"prompt":"Picture 1 \\u2014 \\u00c9p\\u00e9e"}').hexdigest()
        self.assertEqual(check.studio_hash(value), expected)
        self.assertNotEqual(check.studio_hash(value), hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest())

    def test_native_source_prepares_all_four_materialized_routes(self):
        source, package = self.source_paths()
        report = check.check_contract(source, package)
        self.assertEqual(report["graph_comparisons"], 8)
        self.assertEqual({row["route_id"] for row in report["routes"]}, check.ROUTES)
        self.assertTrue(all(row["matches"] for row in report["routes"]))
        self.assertFalse(report["generation_submitted"])
        self.assertFalse(report["models_loaded"])
        klein4 = next(row for row in report["routes"] if row["route_id"] == "klein4-reference")
        self.assertTrue(all(row["prepared_reference_slots"] == 2 and row["pruned_reference_slots"] == [2] for row in klein4["variants"]))

    def test_whitespace_only_source_change_invalidates_revision_claim(self):
        source, _package = self.source_paths()
        self.assertEqual(check.verify_source_pins(source), check.PINNED_SOURCE_SHA256)
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary)
            for name in check.PINNED_SOURCE_SHA256:
                target = changed / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((source / name).read_bytes())
            server = changed / "app" / "server.py"
            server.write_bytes(server.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'Pinned source bytes differ: app/server.py'):
                check.verify_source_pins(changed)


if __name__ == "__main__":
    unittest.main()
