"""Candidate intake refuses oversized files without reading their contents."""
import importlib.util
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


KIT = Path(__file__).resolve().parents[1] / 'docs' / 'adaptive-studio' / 'assets'
PNG = b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR' + struct.pack('>II', 4, 4) + b'\x08\x06'


class AssetIntakeBoundsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('asset_intake_bounds', KIT / 'intake.py')
        cls.intake = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.intake)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ('catalog.csv', 'receipt-template.json'):
            shutil.copyfile(KIT / name, self.root / name)
        (self.root / 'inbox').mkdir()
        self.path = self.root / 'inbox' / 'state-blank--candidate-1.png'

    def sparse_candidate(self, size, header=PNG):
        with self.path.open('wb') as stream:
            stream.write(header)
            stream.seek(size - 1)
            stream.write(b'\x00')

    def receipt(self):
        template = json.loads((self.root / 'receipt-template.json').read_text(encoding='utf-8'))
        return self.intake.receipt_for(self.root, self.path, self.intake.catalogue(self.root), template,
                                       '2026-10-22T00:00:00+00:00')

    def test_oversize_candidate_is_refused(self):
        for extra in (1, 27):
            with self.subTest(extra=extra):
                self.sparse_candidate(self.intake.MAX_DOWNLOAD + extra)
                with self.assertRaisesRegex(ValueError, f'{self.path.name}: candidate exceeds {self.intake.MAX_DOWNLOAD} bytes'):
                    self.receipt()

    def test_oversize_candidate_is_refused_before_open(self):
        self.sparse_candidate(self.intake.MAX_DOWNLOAD + 1)
        with patch.object(Path, 'open', side_effect=AssertionError('oversized candidate was opened')):
            with self.assertRaisesRegex(ValueError, 'candidate exceeds'):
                self.intake.receipt_for(self.root, self.path, {}, {}, 'now')

    def test_oversize_candidate_writes_no_receipt(self):
        self.sparse_candidate(self.intake.MAX_DOWNLOAD + 1)
        with patch('sys.stdout', io.StringIO()), patch('sys.stderr', io.StringIO()) as errors:
            self.assertEqual(self.intake.receipts(self.root, now='now'), 2)
        self.assertIn(f'{self.path.name}: candidate exceeds {self.intake.MAX_DOWNLOAD} bytes', errors.getvalue())
        self.assertFalse((self.root / 'receipts').exists())

    def test_exact_limit_streams_full_hash_and_bounds_header(self):
        self.sparse_candidate(self.intake.MAX_DOWNLOAD)
        with self.path.open('rb') as stream:
            expected_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
        original_open = Path.open
        reads = []

        def bounded_open(path, *args, **kwargs):
            stream = original_open(path, *args, **kwargs)
            if path != self.path:
                return stream
            original_read = stream.read

            def bounded_read(size=-1):
                self.assertGreater(size, 0, 'candidate reads must have a bound')
                self.assertLessEqual(size, self.intake.HEADER_BYTES)
                reads.append(size)
                return original_read(size)

            stream.read = bounded_read
            return stream

        with patch.object(Path, 'open', bounded_open), \
             patch.object(Path, 'read_bytes', side_effect=AssertionError('whole-file read')), \
             patch.object(self.intake, 'image_info', wraps=self.intake.image_info) as info:
            receipt = self.receipt()
        self.assertGreater(len(reads), 1)
        self.assertEqual(len(info.call_args.args[0]), self.intake.HEADER_BYTES)
        record = receipt['files'][0]
        self.assertEqual(record['bytes'], self.intake.MAX_DOWNLOAD)
        self.assertEqual(record['sha256'], expected_hash)
        self.assertEqual((record['format'], record['width'], record['height'], record['alpha']), ('png', 4, 4, True))
        self.assertEqual(receipt['status'], 'candidate-produced')

    def test_candidate_growing_past_stat_size_is_refused(self):
        self.sparse_candidate(self.intake.MAX_DOWNLOAD + 1)
        with patch.object(Path, 'stat', return_value=SimpleNamespace(st_size=self.intake.MAX_DOWNLOAD)):
            with self.assertRaisesRegex(ValueError, 'candidate exceeds'):
                self.receipt()

    def test_frame_beyond_prefix_keeps_unknown_evidence(self):
        self.sparse_candidate(self.intake.HEADER_BYTES + 64, b'\xff\xd8')
        with self.path.open('r+b') as stream:
            stream.seek(self.intake.HEADER_BYTES + 16)
            stream.write(b'\xff\xc0\x00\x0b\x08\x00\x04\x00\x04\x00\x00\x00')
        receipt = self.receipt()
        record = receipt['files'][0]
        self.assertTrue(all(record[key] is None for key in ('format', 'width', 'height', 'alpha')))
        self.assertIn('Format, size and alpha are unknown: JPEG without a frame header.', receipt['unknowns'])
        self.assertEqual(record['bytes'], self.path.stat().st_size)
        with self.path.open('rb') as stream:
            self.assertEqual(record['sha256'], hashlib.file_digest(stream, 'sha256').hexdigest())


if __name__ == '__main__':
    unittest.main()
