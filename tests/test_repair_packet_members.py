"""Reject undeclared members instead of certifying a partial packet inventory."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from scripts import repair_source as source
from scripts import repair_panels as panels


class RepairPacketMemberTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.packet = self.root / 'source'
        original = self.root / 'original.png'
        with Image.new('RGB', (16, 16), 'white') as image: image.save(original)
        source.capture(original, self.packet)
        layout = panels.grid(self.packet, rows=1, columns=2)
        layout_path = self.root / 'layout.json'; layout_path.write_bytes(panels._json(layout))
        self.extracted = self.root / 'extracted'
        panels.extract(self.packet, layout_path, self.extracted, source.digest(layout_path.read_bytes()))

    def assert_extras_refused(self, folder, verify):
        for name in ('extra.bin', 'receipt.pending'):
            added = folder / name; added.write_bytes(b'unrecorded bytes')
            with self.subTest(name=name), self.assertRaises(ValueError): verify()
            self.assertEqual(added.read_bytes(), b'unrecorded bytes')
            added.unlink()
        added = folder / 'nested'; added.mkdir()
        with self.assertRaises(ValueError): verify()
        self.assertTrue(added.is_dir())

    def test_source_rejects_extra_files_pending_receipts_and_directories(self):
        self.assert_extras_refused(self.packet, lambda: source.verify(self.packet))

    def test_extraction_rejects_extra_files_pending_receipts_and_directories(self):
        self.assert_extras_refused(self.extracted, lambda: panels.verify_extraction(self.packet, self.extracted))

    def test_unknown_symlinks_are_not_followed_or_ignored(self):
        for folder, verify in ((self.packet, lambda: source.verify(self.packet)),
                               (self.extracted, lambda: panels.verify_extraction(self.packet, self.extracted))):
            added = folder / 'unknown-link'
            try: added.symlink_to(self.root / 'absent')
            except OSError: self.skipTest('symlinks unavailable')
            with self.subTest(folder=folder.name), self.assertRaises(ValueError): verify()
            self.assertTrue(added.is_symlink()); added.unlink()

    def test_source_inventory_refusal_precedes_image_reconstruction(self):
        added = self.packet / 'extra.bin'; added.write_bytes(b'extra')
        with patch.object(source, 'normalize_repair_png', side_effect=AssertionError('decoder reached')):
            with self.assertRaises(ValueError): source.verify(self.packet)


if __name__ == '__main__': unittest.main()
