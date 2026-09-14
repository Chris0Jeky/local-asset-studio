"""Actual bundle-verification seam with real temporary PNGs and hashed receipts."""
from contextlib import closing
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import character_edit_pixels as pixels
from scripts.character_study import file_sha, sha, write_json


class BundleEqualityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name); (self.root / 'prepared').mkdir()
        self.plan = {'plan_sha256': 'a'*64, 'document': {'source': {'path': 'source.png', 'sha256': 'b'*64}}}
        self.transform = {'model_size': [1025, 7]}

    def publish(self, actual):
        path = self.root / 'prepared/context.png'; actual.save(path, format='PNG')
        bundle = {'schema_version': 1, 'kind': 'character_edit_bundle',
            'plan_sha256': self.plan['plan_sha256'], 'source': self.plan['document']['source'],
            'transform': self.transform, 'files': {'context.png': {'path': 'context.png', 'sha256': file_sha(path)}},
            'pillow_version': Image.__version__, 'neural_inference': False, 'semantic_approval': False}
        bundle['bundle_sha256'] = sha(bundle)
        write_json(self.root / 'prepared/bundle.json', bundle)
        return bundle

    def verify(self, expected):
        return pixels._verify_bundle(self.root, self.plan, 'prepared', {'context.png': expected}, self.transform)

    def test_real_verifier_bounds_byte_conversions_and_preserves_receipt(self):
        with closing(Image.new('RGBA', (1025,7), (17,31,47,0))) as expected:
            receipt = self.publish(expected); calls = []; original = Image.Image.tobytes
            before = file_sha(self.root / 'prepared/context.png')
            def observe(image, *args, **kwargs):
                calls.append(image.size); return original(image, *args, **kwargs)
            with patch.object(Image.Image, 'tobytes', observe): self.assertEqual(self.verify(expected), receipt)
            self.assertTrue(calls)
            self.assertTrue(all(w <= 512 and h <= 512 for w,h in calls), calls)
            self.assertEqual(file_sha(self.root / 'prepared/context.png'), before)
            self.assertEqual(expected.getpixel((0,0)), (17,31,47,0))

    def test_rehashed_hidden_rgb_forgery_is_refused(self):
        with closing(Image.new('RGBA', (1025,7), (17,31,47,0))) as expected, closing(expected.copy()) as actual:
            actual.putpixel((1024,6), (18,31,47,0)); self.publish(actual)
            with self.assertRaisesRegex(ValueError, 'Bundle pixels/profile changed'): self.verify(expected)

    def test_rehashed_transparency_only_forgery_is_refused(self):
        with closing(Image.new('RGB', (1025,7), (17,31,47))) as expected, closing(expected.copy()) as actual:
            actual.info['transparency'] = (17,31,47); self.publish(actual)
            with self.assertRaisesRegex(ValueError, 'Bundle pixels/profile changed'): self.verify(expected)

    def test_icc_comparison_remains_separate_and_required(self):
        with closing(Image.new('RGBA', (1025,7), (17,31,47,0))) as expected, closing(expected.copy()) as actual:
            actual.info['icc_profile'] = b'different-fixture-profile'; self.publish(actual)
            with self.assertRaisesRegex(ValueError, 'Bundle pixels/profile changed'): self.verify(expected)

    def test_decoded_verification_image_is_closed_on_success_and_refusal(self):
        for changed in (False, True):
            with self.subTest(changed=changed):
                # publish() is deliberately create-only, as production receipts are.
                for path in (self.root / 'prepared').iterdir(): path.unlink()
                with closing(Image.new('RGBA', (1025,7), (17,31,47,0))) as expected, closing(expected.copy()) as actual:
                    if changed: actual.putpixel((0,0), (18,31,47,0))
                    self.publish(actual); decoded=[]; original=pixels.png
                    def observe(path):
                        image=original(path); decoded.append(image); return image
                    with patch.object(pixels, 'png', observe):
                        if changed:
                            with self.assertRaisesRegex(ValueError, 'Bundle pixels/profile changed'): self.verify(expected)
                        else: self.verify(expected)
                    self.assertEqual(len(decoded),1)
                    with self.assertRaises(ValueError): decoded[0].getpixel((0,0))
                    self.assertEqual(expected.getpixel((0,0)), (17,31,47,0))

    def test_artifact_hash_is_not_bypassed(self):
        with closing(Image.new('RGBA', (1025,7))) as expected:
            self.publish(expected)
            (self.root / 'prepared/context.png').write_bytes(b'corrupt')
            with self.assertRaises(ValueError): self.verify(expected)


if __name__ == '__main__': unittest.main()
