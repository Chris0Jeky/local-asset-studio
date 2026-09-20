"""Native metadata observations for freshly written taxonomy contracts."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock

from studio_prompt import adult_illustration_taxonomy_contracts as contracts


class TaxonomyNativeReadIdentityTests(unittest.TestCase):
    def test_closed_writes_do_not_become_spurious_concurrent_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / contracts.SOURCE_MANIFEST
            path.parent.mkdir(parents=True)
            for number in range(32):
                raw = ('{"record":' + str(number) + '}').encode("ascii")
                path.write_bytes(raw)
                observations = []
                identity = contracts._file_identity

                def observe(info):
                    value = identity(info)
                    observations.append(value)
                    return value

                with mock.patch.object(contracts, "_file_identity", observe):
                    try:
                        value, digest = contracts._load(root, contracts.SOURCE_MANIFEST, "fixture")
                    except ValueError as exc:
                        self.fail(f"Closed write {number} was refused: {exc}; metadata={observations!r}")
                self.assertEqual(value, {"record": number})
                self.assertEqual(digest, contracts.sha256(raw))


if __name__ == "__main__":
    unittest.main()
