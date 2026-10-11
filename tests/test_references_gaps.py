"""Pin app/references.py image_record provenance bytes and dimensions."""
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location('reference_gaps', ROOT / 'app/references.py')
ref = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ref)


class ImageRecordGapsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def write_tiny_png(self, name='tiny.png'):
        path = self.root / name
        with Image.new('RGB', (1, 1), 'white') as image:
            image.save(path, 'PNG')
        return path

    def test_image_record_sha256_pins_bytes(self):
        path = self.write_tiny_png()
        raw = path.read_bytes()
        rec = ref.image_record(self.root, path.name)
        self.assertEqual(rec['file'], path.name)
        self.assertEqual(rec['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(rec['bytes'], len(raw))
        self.assertEqual(rec['width'], 1)
        self.assertEqual(rec['height'], 1)
        # Provenance must describe the exact bytes on disk.
        self.assertEqual(path.read_bytes(), raw)

    def test_image_record_missing_raises(self):
        with self.assertRaises(ValueError):
            ref.image_record(self.root, 'missing.png')

    def test_image_record_oversize_raises(self):
        path = self.write_tiny_png('big.png')
        with path.open('r+b') as stream:
            stream.seek(ref.MAX_REFERENCE_BYTES)
            stream.write(b'\0')
        with self.assertRaisesRegex(ValueError, '20 MiB'):
            ref.image_record(self.root, path.name)

    def test_image_record_animated_raises(self):
        path = self.root / 'animated.png'
        with Image.new('RGB', (1, 1), 'white') as first, Image.new('RGB', (1, 1), 'black') as second:
            first.save(path, save_all=True, append_images=[second])
        with self.assertRaisesRegex(ValueError, 'single still'):
            ref.image_record(self.root, path.name)

    def test_image_record_unreadable_raises(self):
        path = self.root / 'broken.png'
        path.write_bytes(b'not an image')
        with self.assertRaisesRegex(ValueError, 'cannot be read'):
            ref.image_record(self.root, path.name)

    def test_image_record_exif_dimensions_follow_provenance_bytes(self):
        path = self.root / 'oriented.jpg'
        exif = Image.Exif()
        exif[274] = 6
        with Image.new('RGB', (40, 60), 'teal') as image:
            image.save(path, 'JPEG', exif=exif)
        raw = path.read_bytes()
        rec = ref.image_record(self.root, path.name)
        self.assertEqual(rec['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(rec['bytes'], len(raw))
        self.assertEqual((rec['width'], rec['height']), (60, 40))


if __name__ == '__main__':
    unittest.main()
