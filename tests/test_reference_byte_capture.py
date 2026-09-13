"""Reference provenance must describe one bounded capture, not two path reads."""
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from test_references import ref


LIMIT = 20 * 1024 * 1024


def encoded(size=(40, 60), *, orientation=None):
    with Image.new('RGB', size, 'teal') as image, io.BytesIO() as output:
        if orientation is None:
            image.save(output, 'PNG')
        else:
            exif = Image.Exif(); exif[274] = orientation
            image.save(output, 'JPEG', exif=exif)
        return output.getvalue()


class ReferenceByteCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        # Match production's canonical spelling (Windows temp paths can be aliases).
        self.root = Path(self.temporary.name).resolve()
        self.path = self.root / 'source.png'
        self.original = encoded()
        self.path.write_bytes(self.original)

    def test_replacement_before_decode_cannot_mix_hash_and_dimensions(self):
        replacement = encoded((11, 7))
        original_open = Image.open
        calls = []

        def replace_then_open(source, *args, **kwargs):
            calls.append(True)
            self.path.write_bytes(replacement)
            return original_open(source, *args, **kwargs)

        with patch.object(Image, 'open', side_effect=replace_then_open):
            record = ref.image_record(self.root, self.path.name)
        self.assertEqual(calls, [True])
        self.assertEqual(record['sha256'], hashlib.sha256(self.original).hexdigest())
        self.assertEqual(record['bytes'], len(self.original))
        self.assertEqual((record['width'], record['height']), (40, 60))
        self.assertEqual(self.path.read_bytes(), replacement)

    def test_growth_after_stat_is_rejected_before_image_decode(self):
        original_open = Path.open
        reads = []

        def grow_then_open(path, mode='r', *args, **kwargs):
            if path == self.path and mode == 'rb':
                reads.append(True)
                with original_open(path, 'r+b') as stream:
                    stream.seek(LIMIT)
                    stream.write(b'x')
            return original_open(path, mode, *args, **kwargs)

        with patch.object(Path, 'open', grow_then_open), patch.object(Image, 'open', wraps=Image.open) as decoder:
            with self.assertRaisesRegex(ValueError, '20 MiB'):
                ref.image_record(self.root, self.path.name)
            decoder.assert_not_called()
        self.assertEqual(reads, [True])
        self.assertEqual(self.path.stat().st_size, LIMIT + 1)

    def test_read_has_a_hard_byte_bound_and_closes_its_handle(self):
        original_open = Path.open
        handles = []
        class CheckedStream:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): return self
            def __exit__(self, *args): self.stream.close()
            def read(self, count=-1):
                self_test.assertGreater(count, 0, 'Reference read must not be unbounded')
                self_test.assertLessEqual(count, LIMIT + 1)
                return self.stream.read(count)
        self_test = self
        def opened(path, mode='r', *args, **kwargs):
            stream = original_open(path, mode, *args, **kwargs)
            if path == self.path and mode == 'rb':
                handles.append(stream)
                return CheckedStream(stream)
            return stream
        with patch.object(Path, 'open', opened):
            self.assertEqual(ref.image_record(self.root, self.path.name)['bytes'], len(self.original))
        self.assertEqual(len(handles), 1)
        self.assertTrue(handles[0].closed)

    def test_exif_orientation_dimensions_and_encoded_hash_are_preserved(self):
        raw = encoded((40, 60), orientation=6)
        self.path.write_bytes(raw)
        record = ref.image_record(self.root, self.path.name)
        self.assertEqual(record, {'file': self.path.name, 'sha256': hashlib.sha256(raw).hexdigest(),
                                 'bytes': len(raw), 'width': 60, 'height': 40})
        self.assertEqual(self.path.read_bytes(), raw)

    def test_exact_byte_limit_stays_accepted(self):
        with self.path.open('r+b') as stream:
            stream.seek(LIMIT - 1); stream.write(b'\0')
        record = ref.image_record(self.root, self.path.name)
        self.assertEqual(record['bytes'], LIMIT)
        self.assertEqual((record['width'], record['height']), (40, 60))

    def test_preexisting_oversize_missing_and_escape_are_still_refused(self):
        with self.path.open('r+b') as stream:
            stream.seek(LIMIT); stream.write(b'\0')
        with patch.object(Path, 'open', side_effect=AssertionError('No read needed')):
            with self.assertRaisesRegex(ValueError, '20 MiB'):
                ref.image_record(self.root, self.path.name)
        for name in ('missing.png', '../escape.png'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                ref.image_record(self.root, name)


if __name__ == '__main__': unittest.main()
