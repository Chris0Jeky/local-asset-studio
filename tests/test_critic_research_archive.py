"""The historical source handoff is preserved exactly, not silently installed."""
import hashlib
import json
import shutil
import subprocess
import tempfile
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

    def test_windows_style_checkout_preserves_pinned_evidence_bytes(self):
        repo = Path(__file__).resolve().parents[1]
        paths = ('research/agentic-creation/critic-observations/observations.jsonl',
                 'research/agentic-creation/archive/capture-contract-followup/source.patch.zlib')
        with tempfile.TemporaryDirectory() as temporary:
            checkout = Path(temporary)
            def git(*args):
                return subprocess.run(['git', '-c', 'core.autocrlf=true', '-c', 'core.safecrlf=false',
                                       '-C', str(checkout), *args], check=True, capture_output=True,
                                      text=True, timeout=10)
            git('init', '-q')
            # Root rules alone previously allowed JSONL to become CRLF on Windows.
            for name in ('.gitattributes', 'research/agentic-creation/.gitattributes', *paths):
                source = repo / name
                if source.is_file():
                    target = checkout / name; target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
            git('add', '--', '.')
            for name in paths: (checkout / name).unlink()
            git('checkout-index', '-a', '-f')
            for name in paths:
                with self.subTest(path=name):
                    self.assertEqual((checkout / name).read_bytes(), (repo / name).read_bytes())


if __name__ == '__main__': unittest.main()
