"""The historical source handoff is preserved exactly, not silently installed."""
import hashlib
import json
from pathlib import Path
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1] / 'research/agentic-creation/archive/capture-contract-followup'


class ArchivedCaptureContractTests(unittest.TestCase):
    def test_exact_original_patch_and_all_six_paths_are_retained(self):
        meta = json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
        blob = (ROOT/'source.patch.zlib').read_bytes()
        self.assertEqual(len(blob), meta['compressed_bytes'])
        self.assertEqual(hashlib.sha256(blob).hexdigest(), meta['compressed_sha256'])
        decoder = zlib.decompressobj(); raw = decoder.decompress(blob, 200_000)
        self.assertTrue(decoder.eof); self.assertEqual(decoder.unused_data, b'')
        self.assertEqual(len(raw), meta['original_bytes'])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), meta['original_sha256'])
        paths = [line.split(' b/', 1)[1] for line in raw.decode('utf-8').splitlines() if line.startswith('diff --git')]
        self.assertEqual(paths, meta['files']); self.assertEqual(len(paths), 6)
        self.assertEqual(meta['status'], 'preserved_not_integrated')


if __name__ == '__main__': unittest.main()
