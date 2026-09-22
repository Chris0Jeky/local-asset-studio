"""Validate raw model-source spelling before a URL parser can normalize it."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import download_contracts as contracts
import model_library as models

SOURCE = 'https://civitai.com/api/download/models/456'
NORMALIZED_ALIASES = (
    ' ' + SOURCE, '\x00' + SOURCE,
    SOURCE.replace('/456', '/4\t56'),
    SOURCE.replace('/456', '/4\n56'),
    SOURCE.replace('/456', '/4\r56'),
)


class ModelUrlSpellingTests(unittest.TestCase):
    def test_five_normalized_aliases_are_refused_before_dns(self):
        for url in NORMALIZED_ALIASES:
            with self.subTest(url=repr(url)):
                resolver = Mock(side_effect=AssertionError('No DNS before admission'))
                with self.assertRaises(ValueError):
                    contracts.validate_download_url(url, resolver=resolver)
                resolver.assert_not_called()

    def test_raw_controls_in_every_component_refuse_without_normalization(self):
        for char in ('\x00', '\t', '\r', '\n', ' ', '\x7f'):
            for url in (char + SOURCE, SOURCE + char,
                        SOURCE.replace('civitai', 'civ' + char + 'itai'),
                        SOURCE + '?fileId=7' + char + '89'):
                with self.subTest(url=repr(url)), self.assertRaises(ValueError):
                    contracts.download_source_provider(url)

    def test_empty_userinfo_and_empty_fragment_do_not_alias_the_endpoint(self):
        for url in (SOURCE.replace('https://', 'https://@'),
                    SOURCE.replace('https://', 'https://:@'), SOURCE + '#'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                contracts.download_source_provider(url)

    def test_url_types_fail_as_value_errors(self):
        for value in (None, True, 123, [], {}, SOURCE.encode()):
            with self.subTest(value=value), self.assertRaises(ValueError):
                contracts.download_source_provider(value)

    def test_valid_queries_and_existing_provider_routes_stay_valid(self):
        for url, provider in (
            (SOURCE, 'civitai'),
            (SOURCE.replace('.com/', '.red/') + '?fileId=789&type=Model&format=SafeTensor', 'civitai'),
            (SOURCE + '?value=a%20b%23c%09d', 'civitai'),
            ('https://huggingface.co/owner/repo/resolve/rev/model%20name.safetensors', 'huggingface'),
        ):
            with self.subTest(url=url):
                self.assertEqual(contracts.download_source_provider(url), provider)
        resolver = Mock(return_value=[(2, 1, 6, '', ('93.184.216.34', 443))])
        self.assertEqual(contracts.validate_download_url(
            'https://b2.civitai.com/file/fixture?signature=a%2Bb%3D', 'civitai', resolver), 'civitai')

    def test_bad_manifest_source_creates_no_lease_receipt_or_worker(self):
        data = b'inert'
        for url in NORMALIZED_ALIASES:
            with self.subTest(url=repr(url)), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'models').mkdir()
                asset = {'id': 'raw-url', 'file': 'loras/raw-url.safetensors',
                         'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'url': url}
                (root / 'models/library.json').write_text(json.dumps({'assets': [asset]}), encoding='utf-8')
                library = models.ModelLibrary(root, root / 'comfy')
                with patch.object(models, 'InstallLease') as lease, patch.object(models.threading, 'Thread') as worker:
                    with self.assertRaisesRegex(ValueError, 'copy this file in by hand'):
                        library.start_install('raw-url')
                lease.assert_not_called()
                worker.assert_not_called()
                self.assertEqual(list(library.state.iterdir()), [])
                self.assertFalse(library.models.exists())

    def test_present_model_verification_does_not_depend_on_raw_source_admission(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'models').mkdir()
            library = models.ModelLibrary(root, root / 'comfy')
            asset = {'id': 'raw-url', 'file': 'loras/raw-url.safetensors', 'url': NORMALIZED_ALIASES[0]}
            self.assertIsNone(library.install_block(asset, present=True))


if __name__ == '__main__':
    unittest.main()
