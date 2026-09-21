"""Bound taxonomy contract allocation and bind hashes to one stable read."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from studio_prompt import adult_illustration_taxonomy_contracts as contracts


class TaxonomyContractReadTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.path = self.root / contracts.SOURCE_MANIFEST
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b'{"name":"before"}')

    def load(self):
        return contracts._load(self.root, contracts.SOURCE_MANIFEST, "taxonomy fixture")

    def observe_read(self, change=None):
        original_open = Path.open
        calls, handles = [], []
        target = self.path

        class Reader:
            def __init__(self, handle):
                self.handle = handle
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.handle.close()
            def fileno(self):
                return self.handle.fileno()
            def read(self, size=-1):
                calls.append(size)
                if change is not None:
                    change(original_open)
                return self.handle.read(size)

        def opener(path, mode="r", *args, **kwargs):
            handle = original_open(path, mode, *args, **kwargs)
            if path == target and mode == "rb":
                handles.append(handle)
                return Reader(handle)
            return handle

        return mock.patch.object(Path, "open", opener), calls, handles

    def test_oversized_contract_is_refused_without_opening_body(self):
        self.path.write_bytes(b" " * (contracts.MAX_CONTRACT_BYTES + 1))
        patch, reads, handles = self.observe_read()
        with patch, self.assertRaisesRegex(ValueError, "exceeds"):
            self.load()
        self.assertEqual(reads, [])
        self.assertEqual(handles, [])

    def test_actual_read_is_capped_when_file_grows_after_preflight(self):
        def grow(opener):
            with opener(self.path, "ab") as writer:
                writer.write(b" " * (contracts.MAX_CONTRACT_BYTES + 1))
        patch, reads, handles = self.observe_read(grow)
        with patch, self.assertRaisesRegex(ValueError, "exceeds|changed"):
            self.load()
        self.assertEqual(reads, [contracts.MAX_CONTRACT_BYTES + 1])
        self.assertTrue(handles and all(handle.closed for handle in handles))

    def test_same_size_edit_during_read_is_refused_before_json_decode(self):
        def rewrite(opener):
            before = self.path.stat()
            with opener(self.path, "r+b") as writer:
                writer.write(b'{"name":"after!"}')
            os.utime(self.path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
        patch, _, handles = self.observe_read(rewrite)
        with patch, mock.patch.object(contracts.json, "loads", wraps=json.loads) as decode:
            with self.assertRaisesRegex(ValueError, "changed"):
                self.load()
            decode.assert_not_called()
        self.assertTrue(handles and all(handle.closed for handle in handles))

    def test_exact_limit_and_raw_whitespace_hash_are_preserved(self):
        raw = b'{"name":"before"}'
        raw += b" " * (contracts.MAX_CONTRACT_BYTES - len(raw))
        self.path.write_bytes(raw)
        patch, reads, handles = self.observe_read()
        with patch:
            value, digest = self.load()
        self.assertEqual(value, {"name": "before"})
        self.assertEqual(digest, contracts.sha256(raw))
        self.assertEqual(reads, [contracts.MAX_CONTRACT_BYTES + 1])
        self.assertTrue(handles and all(handle.closed for handle in handles))

    def test_deep_json_uses_the_validation_error_boundary(self):
        self.path.write_bytes(b'{"nested":' + b"[" * 10000 + b"0" + b"]" * 10000 + b"}")
        with self.assertRaisesRegex(ValueError, "Invalid taxonomy fixture"):
            self.load()

    def test_lone_surrogates_cannot_enter_hashable_taxonomy_text(self):
        for value in ("name\ud800", "name\udfff"):
            with self.subTest(value=ascii(value)):
                with self.assertRaisesRegex(ValueError, "Unicode"):
                    contracts.text(value, "source name")
        self.assertEqual(contracts.text("café 🌙", "display"), "café 🌙")


if __name__ == "__main__":
    unittest.main()
