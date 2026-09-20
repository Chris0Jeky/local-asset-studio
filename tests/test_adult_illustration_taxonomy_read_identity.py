"""Native metadata observations for freshly written taxonomy contracts."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
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

    def test_file_id_and_descriptor_change_time_still_detect_drift(self):
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        original = os.fstat
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / contracts.SOURCE_MANIFEST
            path.parent.mkdir(parents=True)
            path.write_bytes(b'{"record":0}')
            for target_call, changed_field in ((1, "st_ino"), (2, "st_ctime_ns")):
                with self.subTest(field=changed_field):
                    calls = []

                    def changed_stat(fd):
                        info = original(fd)
                        values = {field: getattr(info, field) for field in fields}
                        calls.append(fd)
                        if len(calls) == target_call:
                            values[changed_field] += 1
                        return SimpleNamespace(**values)

                    with mock.patch.object(contracts.os, "fstat", changed_stat):
                        with self.assertRaisesRegex(ValueError, "changed"):
                            contracts._load(root, contracts.SOURCE_MANIFEST, "fixture")
                    self.assertEqual(len(calls), target_call)


if __name__ == "__main__":
    unittest.main()
