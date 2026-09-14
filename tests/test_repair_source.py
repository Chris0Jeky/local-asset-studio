"""Real PNG/byte/filesystem intake tests. No model or application runtime."""
import hashlib
from io import BytesIO
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

from PIL import Image, PngImagePlugin

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from scripts import repair_source as r


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


def png(mode='RGB', orientation=None, transparency=None, info=None):
    with Image.new(mode, (3, 2)) as im, BytesIO() as out:
        values = [(10 + x * 30, 20 + y * 60, 3 + x + y) for y in range(2) for x in range(3)]
        if mode == 'RGBA': values = [v + (0 if i == 1 else 80 if i == 3 else 255,) for i, v in enumerate(values)]
        if mode in ('RGB', 'RGBA'): im.putdata(values)
        kwargs = {}
        if orientation is not None:
            exif = im.getexif(); exif[274] = orientation; kwargs['exif'] = exif
        if transparency is not None: kwargs['transparency'] = transparency
        if info is not None: kwargs['pnginfo'] = info
        im.save(out, format='PNG', **kwargs)
        return out.getvalue()


def rgba(raw):
    with BytesIO(raw) as data, Image.open(data) as im:
        return im.size, im.convert('RGBA').tobytes()


class RepairSourceTests(unittest.TestCase):
    def call(self, name, *args, **kwargs):
        self.assertTrue(callable(getattr(r, name, None)), name + ' is not implemented')
        return getattr(r, name)(*args, **kwargs)

    def test_plain_source_is_not_changed_and_pixels_match(self):
        original = png(); saved = original[:]
        normalized, report = self.call('normalize_repair_png', original)
        self.assertEqual(original, saved)
        self.assertEqual(rgba(original), rgba(normalized))
        self.assertEqual(report['source']['sha256'], hashlib.sha256(original).hexdigest())
        self.assertEqual(report['normalized']['sha256'], hashlib.sha256(normalized).hexdigest())
        self.assertEqual(report['source']['size'], [3, 2])
        self.assertFalse(report['neural_inference'])
        self.assertEqual(report['review_state'], 'unreviewed')
        self.assertFalse(report['colour']['converted'])

    def test_all_eight_orientations_with_independent_expected_pixels(self):
        order = {1:[0,1,2,3,4,5], 2:[2,1,0,5,4,3], 3:[5,4,3,2,1,0],
                 4:[3,4,5,0,1,2], 5:[0,3,1,4,2,5], 6:[3,0,4,1,5,2],
                 7:[5,2,4,1,3,0], 8:[2,5,1,4,0,3]}
        _, original = rgba(png('RGBA'))
        pixels = [original[i:i+4] for i in range(0, len(original), 4)]
        for orientation in range(1,9):
            with self.subTest(orientation=orientation):
                result, report = self.call('normalize_repair_png', png('RGBA', orientation))
                shape, data = rgba(result)
                self.assertEqual(shape, (2,3) if orientation >= 5 else (3,2))
                self.assertEqual(data, b''.join(pixels[i] for i in order[orientation]))
                self.assertEqual(report['source']['orientation'], orientation)
                with Image.open(BytesIO(result)) as im:
                    self.assertNotIn('exif', im.info)
                    self.assertEqual(im.mode, 'RGBA')

    def test_invalid_orientation_is_not_guessed(self):
        for value in (0,9):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.call('normalize_repair_png', png(orientation=value))

    def test_colour_key_materializes_alpha_without_erasing_hidden_rgb(self):
        original = png(transparency=(40,20,4))
        result, report = self.call('normalize_repair_png', original)
        self.assertEqual(rgba(original), rgba(result))
        self.assertTrue(report['source']['colour_key_transparency'])
        self.assertEqual(rgba(result)[1][4:8], bytes((40,20,4,0)))

    def test_partial_alpha_and_hidden_rgb_survive(self):
        original = png('RGBA')
        result, _ = self.call('normalize_repair_png', original)
        self.assertEqual(rgba(original), rgba(result))

    def test_text_and_exif_removed_only_from_derivative(self):
        info = PngImagePlugin.PngInfo(); info.add_text('prompt', 'private prompt'); info.add_itxt('note', 'hello', zip=True)
        original = png(orientation=1, info=info)
        result, report = self.call('normalize_repair_png', original)
        with Image.open(BytesIO(result)) as im:
            self.assertNotIn('prompt', im.info); self.assertNotIn('exif', im.info)
        self.assertIn('tEXt', report['source']['removed_metadata_chunks'])
        self.assertNotIn('private prompt', json.dumps(report))
        with Image.open(BytesIO(original)) as im: self.assertEqual(im.info['prompt'], 'private prompt')

    def test_colour_chunks_are_retained_not_relabelled_srgb(self):
        info = PngImagePlugin.PngInfo(); info.add(b'gAMA', struct.pack('>I', 50000))
        original = png(info=info)
        result, report = self.call('normalize_repair_png', original)
        with Image.open(BytesIO(result)) as im: self.assertEqual(im.info['gamma'], 0.5)
        self.assertIn('gAMA', report['colour']['retained_chunks'])
        self.assertEqual(report['colour']['interpretation'], 'not_certified')
        self.assertFalse(report['colour']['converted'])

    def test_icc_payload_retained_without_claim_of_validation(self):
        payload = b'opaque-profile-not-certified'
        original = png(); original = original[:33] + chunk(b'iCCP', b'profile\0\0' + zlib.compress(payload)) + original[33:]
        result, report = self.call('normalize_repair_png', original)
        with Image.open(BytesIO(result)) as im: self.assertEqual(im.info['icc_profile'], payload)
        self.assertEqual(report['colour']['icc_sha256'], hashlib.sha256(payload).hexdigest())
        self.assertEqual(report['colour']['interpretation'], 'not_certified')

    def test_non_rgb_and_16_bit_colour_refused_before_decoder(self):
        for mode in ('L','P','I;16'):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.call('normalize_repair_png', png(mode))
        raw = png(); ihdr = bytearray(raw[16:29]); ihdr[8] = 16
        raw = raw[:8] + chunk(b'IHDR', bytes(ihdr)) + raw[33:]
        with patch.object(Image, 'open', side_effect=AssertionError('decoder called')):
            with self.assertRaises(ValueError): self.call('normalize_repair_png', raw)

    def test_animation_and_hdr_are_not_flattened(self):
        for kind, payload in [(b'acTL',struct.pack('>II',1,0)),(b'cICP',b'\1\1\0\1')]:
            raw = png(); raw = raw[:33] + chunk(kind, payload) + raw[33:]
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.call('normalize_repair_png', raw)

    def test_bad_crc_truncation_and_trailing_data_refused(self):
        raw = png()
        for value in (raw[:-2], raw + b'extra', raw[:29] + b'xxxx' + raw[33:], b'not png'):
            with self.subTest(length=len(value)), self.assertRaises(ValueError): self.call('normalize_repair_png', value)

    def test_unknown_critical_and_duplicate_ihdr_refused(self):
        raw = png()
        for extra in (chunk(b'ABCD',b''), raw[8:33]):
            with self.assertRaises(ValueError): self.call('normalize_repair_png', raw[:33] + extra + raw[33:])

    def test_encoded_and_pixel_bounds_precede_decode(self):
        with patch.object(r, 'MAX_SOURCE_BYTES', 10, create=True):
            with self.assertRaises(ValueError): self.call('normalize_repair_png', png())
        raw = png(); data = struct.pack('>IIBBBBB', 100000,100000,8,2,0,0,0)
        raw = raw[:8] + chunk(b'IHDR', data) + raw[33:]
        with patch.object(Image, 'open', side_effect=AssertionError('decoder called')):
            with self.assertRaises(ValueError): self.call('normalize_repair_png', raw)

    def test_compressed_metadata_bomb_refused_before_pillow(self):
        raw = png(); compressed = zlib.compress(b'x' * 4096)
        for kind, payload in [(b'zTXt',b'prompt\0\0' + compressed),
                              (b'iTXt',b'note\0\1\0\0\0' + compressed),
                              (b'iCCP',b'profile\0\0' + compressed)]:
            value = raw[:33] + chunk(kind, payload) + raw[33:]
            with self.subTest(kind=kind), patch.object(r,'MAX_METADATA_BYTES',1024,create=True):
                with patch.object(Image,'open',side_effect=AssertionError('decoder called')):
                    with self.assertRaises(ValueError): self.call('normalize_repair_png', value)

    def test_metadata_budget_is_aggregate(self):
        raw=png(); extra=chunk(b'tEXt',b'a\0'+b'x'*600)+chunk(b'tEXt',b'b\0'+b'y'*600)
        with patch.object(r,'MAX_METADATA_BYTES',1024,create=True):
            with self.assertRaises(ValueError): self.call('normalize_repair_png', raw[:33]+extra+raw[33:])

    def test_untagged_colour_is_not_inferred(self):
        _, report = self.call('normalize_repair_png', png())
        self.assertEqual(report['colour']['retained_chunks'], [])
        self.assertEqual(report['colour']['interpretation'], 'not_certified')

    def test_real_capture_verify_and_original_snapshot_independence(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); src=root/'input.png'; out=root/'packet'; raw=png('RGBA',6); src.write_bytes(raw)
            report=self.call('capture',src,out)
            self.assertEqual((out/'source.png').read_bytes(), raw)
            self.assertEqual(src.read_bytes(),raw)
            src.write_bytes(png())
            verified=self.call('verify',out)
            self.assertEqual(report,verified)
            self.assertEqual((out/'source.png').read_bytes(),raw)

    def test_existing_packet_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); src=root/'input.png'; src.write_bytes(png()); out=root/'packet'; out.mkdir(); (out/'keep').write_text('keep')
            with self.assertRaises(FileExistsError): self.call('capture',src,out)
            self.assertEqual((out/'keep').read_text(),'keep')

    def test_invalid_source_publishes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); src=root/'input.png'; src.write_bytes(b'invalid'); out=root/'packet'
            with self.assertRaises(ValueError): self.call('capture',src,out)
            self.assertFalse(out.exists())

    def test_damaged_packet_and_rehashed_wrong_pixels_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); src=root/'input.png'; src.write_bytes(png()); out=root/'packet'
            self.call('capture',src,out)
            replacement=png('RGBA'); (out/'normalized.png').write_bytes(replacement)
            receipt=json.loads((out/'receipt.json').read_text())
            receipt['normalization']['normalized']['sha256']=hashlib.sha256(replacement).hexdigest()
            receipt['normalization']['normalized']['bytes']=len(replacement)
            (out/'receipt.json').write_text(json.dumps(receipt))
            with self.assertRaises(ValueError): self.call('verify',out)

    def test_missing_marker_and_symlinked_member_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); out=root/'packet'; out.mkdir()
            with self.assertRaises((ValueError,OSError)): self.call('verify',out)
            src=root/'input.png'; src.write_bytes(png()); other=root/'other'
            self.call('capture',src,other)
            (other/'source.png').unlink()
            try: (other/'source.png').symlink_to(src)
            except OSError: self.skipTest('symlinks unavailable')
            with self.assertRaises(ValueError): self.call('verify',other)

    def test_receipt_type_confusion_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); src=root/'input.png'; src.write_bytes(png()); out=root/'packet'
            self.call('capture',src,out)
            receipt=json.loads((out/'receipt.json').read_text()); receipt['neural_inference']=0
            (out/'receipt.json').write_text(json.dumps(receipt))
            with self.assertRaises(ValueError): self.call('verify',out)

    def test_captured_source_does_not_reopen_for_hash_or_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); src=root/'input.png'; before=png('RGBA',6); src.write_bytes(before); out=root/'packet'
            real=r.normalize_repair_png
            def replace_after_capture(raw):
                src.write_bytes(png())
                return real(raw)
            with patch.object(r,'normalize_repair_png',side_effect=replace_after_capture):
                report=self.call('capture',src,out)
            self.assertEqual(report['normalization']['source']['sha256'],hashlib.sha256(before).hexdigest())
            self.assertEqual(report['normalization']['normalized']['size'],[2,3])
            self.assertEqual((out/'source.png').read_bytes(),before)
            self.call('verify',out)

    def test_capture_bounds_actual_read_not_prior_stat(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'file'; path.write_bytes(b'12345')
            self.assertEqual(self.call('read_bounded',path,5),b'12345')
            with self.assertRaises(ValueError): self.call('read_bounded',path,4)

    def test_publication_failure_retains_partial_without_completion_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); src=root/'input.png'; before=png(); src.write_bytes(before); out=root/'packet'
            with patch.object(r.os,'link',side_effect=OSError('unsupported filesystem')):
                with self.assertRaises(OSError): self.call('capture',src,out)
            self.assertEqual(src.read_bytes(),before)
            self.assertTrue((out/'receipt.pending').exists())
            self.assertFalse((out/'receipt.json').exists())
            with self.assertRaises((ValueError,OSError)): self.call('verify',out)
            with self.assertRaises(FileExistsError): self.call('capture',src,out)

    def test_concurrent_capture_claims_one_packet(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); src=root/'input.png'; src.write_bytes(png()); out=root/'packet'
            def capture_once(_):
                try: r.capture(src,out); return 'created'
                except FileExistsError: return 'exists'
            with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(capture_once,range(4)))
            self.assertEqual(results.count('created'),1)
            self.assertEqual(results.count('exists'),3)
            self.call('verify',out)

    def test_verify_does_not_change_packet(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); src=root/'input.png'; src.write_bytes(png()); out=root/'packet'
            self.call('capture',src,out)
            before={p.name:p.read_bytes() for p in out.iterdir()}
            self.call('verify',out)
            self.assertEqual(before,{p.name:p.read_bytes() for p in out.iterdir()})

    def test_cli_capture_and_verify_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); src=root/'input.png'; src.write_bytes(png('RGBA',6)); out=root/'packet'
            for args in [('capture','--image',str(src),'--out',str(out)),('verify',str(out))]:
                run=subprocess.run([sys.executable,str(ROOT/'scripts/repair_source.py'),*args],cwd=directory,text=True,capture_output=True)
                self.assertEqual(run.returncode,0,run.stderr)
                self.assertFalse(json.loads(run.stdout)['neural_inference'])

    def test_cli_error_is_structured_no_output(self):
        with tempfile.TemporaryDirectory() as directory:
            run=subprocess.run([sys.executable,str(ROOT/'scripts/repair_source.py'),'capture','--image',str(Path(directory)/'missing'),'--out',str(Path(directory)/'out')],text=True,capture_output=True)
            self.assertEqual(run.returncode,2,run.stderr)
            self.assertIn('error',json.loads(run.stdout))
            self.assertFalse((Path(directory)/'out').exists())

if __name__ == '__main__': unittest.main()
