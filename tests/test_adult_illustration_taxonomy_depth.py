from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from studio_prompt.adult_illustration_taxonomy import build_taxonomy_index
from tests.test_adult_illustration_taxonomy import csv_bytes, review_entry, write_contracts


class TaxonomyDepthTests(unittest.TestCase):
    def test_relationship_depth_counts_memoized_descendants(self) -> None:
        rows = [(1, "a", 0, 10), (2, "b", 0, 9), (3, "c", 0, 8)]
        source = csv_bytes(rows)
        entries = [
            review_entry("a"),
            review_entry("b", implications=["a"]),
            review_entry("c", implications=["b"]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_contracts(root, source, rows, entries)
            contract_path = (
                root
                / "research"
                / "adult-illustration"
                / "taxonomy-source.json"
            )
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["bounds"]["max_relationship_depth"] = 2
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exceeds depth 2"):
                build_taxonomy_index(source, root)


if __name__ == "__main__":
    unittest.main()
