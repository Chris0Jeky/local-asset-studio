"""Diagnostic fidelity for the second bounded resource-receipt read."""
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
sys.path.insert(0, str(ROOT))

import resource_receipts as receipts


class RecheckDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'evidence.json'
        self.path.write_bytes(b'{"ok":true}\n')

    def second_open(self, error):
        real_open = os.open
        calls = 0

        def controlled(path, flags, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise error
            return real_open(path, flags, *args, **kwargs)

        with patch.object(receipts.os, 'open', side_effect=controlled):
            return receipts.read_evidence_file(self.path, 1024)

    def test_unreadable_second_open_is_not_reported_as_content_change(self):
        with self.assertRaises(receipts.EvidenceError) as caught:
            self.second_open(PermissionError('sharing violation'))
        self.assertEqual(caught.exception.code, 'artifact_unreadable')
        self.assertFalse(caught.exception.incomplete)

    def test_disappearance_before_second_open_remains_file_changed(self):
        with self.assertRaises(receipts.EvidenceError) as caught:
            self.second_open(FileNotFoundError('gone'))
        self.assertEqual(caught.exception.code, 'file_changed')
        self.assertFalse(caught.exception.incomplete)


if __name__ == '__main__':
    unittest.main()
