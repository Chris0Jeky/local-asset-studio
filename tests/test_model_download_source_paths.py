"""Initial model URLs must identify transfer endpoints, not provider HTML pages."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parents[1] / 'app'))
import download_contracts as contracts
import model_library as models


class CuratedSourcePathTests(unittest.TestCase):
    def test_civitai_model_pages_and_metadata_routes_are_not_download_sources(self):
        cases = (
            'https://civitai.com/models/123?modelVersionId=456',
            'https://civitai.red/models/123?modelVersionId=456',
            'https://civitai.com/api/v1/model-versions/456',
            'https://civitai.red/api/v1/models/123',
        )
        for url in cases:
            with self.subTest(url=url), self.assertRaisesRegex(
                    ValueError, 'download endpoint'):
                contracts.download_source_provider(url)

    def test_exact_civitai_version_download_routes_are_accepted(self):
        cases = (
            'https://civitai.com/api/download/models/456',
            'https://civitai.com/api/download/models/456?type=Model&format=SafeTensor',
            'https://civitai.red/api/download/models/456',
            'https://civitai.red/api/download/models/456?fileId=789',
        )
        for url in cases:
            with self.subTest(url=url):
                self.assertEqual(contracts.download_source_provider(url), 'civitai')

    def test_invalid_civitai_source_path_refuses_before_dns(self):
        resolver = Mock(side_effect=AssertionError('DNS must not run'))
        with self.assertRaisesRegex(ValueError, 'download endpoint'):
            contracts.validate_download_url(
                'https://civitai.red/models/123?modelVersionId=456',
                resolver=resolver,
            )
        resolver.assert_not_called()

    def test_huggingface_curated_source_contract_is_unchanged(self):
        self.assertEqual(
            contracts.download_source_provider(
                'https://huggingface.co/owner/repo/resolve/revision/model.safetensors'),
            'huggingface',
        )


class ModelLibraryAdmissionTests(unittest.TestCase):
    def test_missing_asset_with_civitai_page_url_is_manual_copy_only(self):
        body = b'inert model bytes'
        asset = {
            'id': 'page-url',
            'file': 'loras/page-url.safetensors',
            'bytes': len(body),
            'sha256': hashlib.sha256(body).hexdigest(),
            'url': 'https://civitai.red/models/123?modelVersionId=456',
        }
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'models').mkdir()
            (root / 'models/library.json').write_text(
                json.dumps({'assets': [asset]}), encoding='utf-8')
            library = models.ModelLibrary(root, root / 'comfy')
            blocked = library.install_block(asset, present=False)
        self.assertEqual(
            blocked,
            'No curated source is pinned; copy this file in by hand',
        )

    def test_missing_asset_with_exact_download_route_remains_installable(self):
        body = b'inert model bytes'
        asset = {
            'id': 'download-url',
            'file': 'loras/download-url.safetensors',
            'bytes': len(body),
            'sha256': hashlib.sha256(body).hexdigest(),
            'url': 'https://civitai.com/api/download/models/456',
        }
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'models').mkdir()
            library = models.ModelLibrary(root, root / 'comfy')
            self.assertIsNone(library.install_block(asset, present=False))


if __name__ == '__main__':
    unittest.main()
