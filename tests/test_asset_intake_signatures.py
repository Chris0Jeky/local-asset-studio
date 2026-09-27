"""Receipt-level regressions for recognized image signatures cut during saving."""
import importlib.util
import io
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest.mock import patch


KIT = Path(__file__).resolve().parents[1] / 'docs' / 'adaptive-studio' / 'assets'


class AssetIntakeSignatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('asset_intake_signatures', KIT / 'intake.py')
        cls.intake = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.intake)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ('catalog.csv', 'receipt-template.json'):
            shutil.copyfile(KIT / name, self.root / name)
        (self.root / 'inbox').mkdir()

    def ingest(self, data, candidate):
        path = self.root / 'inbox' / f'state-blank--candidate-{candidate}.png'
        path.write_bytes(data)
        with patch('sys.stdout', io.StringIO()), patch('sys.stderr', io.StringIO()):
            result = self.intake.receipts(self.root, now='2026-09-27T00:00:00+00:00')
        path.unlink()  # Each subtest must observe only its own input, not earlier refusals.
        return result, self.root / 'receipts' / f'{path.stem}.json'

    def test_every_recognized_short_header_keeps_unknown_evidence(self):
        png = b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR' + struct.pack('>II', 4, 4) + b'\x08\x06'
        webp = b'RIFF' + struct.pack('<I', 22) + b'WEBP'
        headers = [png[:n] for n in range(8, 26)]
        for chunk, minimum in ((b'VP8L', 25), (b'VP8X', 30), (b'VP8 ', 30)):
            full = webp + chunk + b'\x00' * 14
            headers.extend(full[:n] for n in range(12, minimum))
        headers.append(b'\xff\xd8')
        for candidate, data in enumerate(headers, 1):
            with self.subTest(prefix=data, size=len(data)):
                result, path = self.ingest(data, candidate)
                self.assertEqual(result, 0, 'Recognized truncation must keep an evidence receipt')
                receipt = json.loads(path.read_text(encoding='utf-8'))
                record = receipt['files'][0]
                self.assertEqual(record['sha256'], self.intake.sha256(data))
                self.assertEqual(record['bytes'], len(data))
                self.assertTrue(all(record[key] is None for key in ('format', 'width', 'height', 'alpha')))
                self.assertEqual(receipt['art_review']['status'], 'not-reviewed')
                self.assertTrue(any('unknown' in item for item in receipt['unknowns']))

    def test_incomplete_or_unsupported_signatures_are_not_images(self):
        cases = (b'', b'hello', b'\x89PNG\r\n\x1a', b'RIFF\x00\x00\x00\x00',
                 b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00JUNK', b'RIFF\x00\x00\x00\x00WEBPJUNK')
        for candidate, data in enumerate(cases, 1):
            with self.subTest(data=data):
                result, path = self.ingest(data, candidate)
                self.assertEqual(result, 2)
                self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
