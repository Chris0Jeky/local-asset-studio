"""Cross-platform content checks for bounded resource evidence reads."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'app'), str(ROOT)]
import resource_receipts as receipts


class ReceiptContentIdentityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'evidence.json'
        self.original = b'{"value":1}\n'
        self.replacement = b'{"value":2}\n'
        self.assertEqual(len(self.original), len(self.replacement))
        self.path.write_bytes(self.original)

    @staticmethod
    def drain(stream):
        chunks = []
        while True:
            chunk = stream.read(2)
            if not chunk:
                return b''.join(chunks)
            chunks.append(chunk)

    def test_unchanged_stream_succeeds_when_metadata_signature_is_coarse(self):
        with patch.object(receipts, '_signature', return_value=('stable-metadata',)):
            self.assertEqual(receipts.read_evidence_stream(self.path, 64, self.drain), self.original)

    def test_same_size_rewrite_refuses_when_metadata_signature_is_coarse(self):
        def consume(stream):
            result = self.drain(stream)
            self.path.write_bytes(self.replacement)
            return result

        with patch.object(receipts, '_signature', return_value=('stable-metadata',)):
            with self.assertRaisesRegex(receipts.EvidenceError, '^file_changed$'):
                receipts.read_evidence_stream(self.path, 64, consume)
        self.assertEqual(self.path.read_bytes(), self.replacement)


if __name__ == '__main__':
    unittest.main()
