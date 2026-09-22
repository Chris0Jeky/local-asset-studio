"""Catalog transfer URLs must satisfy the installed source-admission policy."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from download_contracts import download_source_provider, validate_pins

TARGETS = {
    'lenovo-krea2', 'pearly-esearu-style', 'pearly-petiflow2',
    'realism-engine-krea2-v3-1', 'realisticsnapshotkrea2', 'ringeko',
    'robertlu1021-fluorite-arknights-v1-0-epoch-10',
    'oneobsessionanima-v20', 'pearlyanimamix-v10',
}


class CatalogDownloadSourceTests(unittest.TestCase):
    def assets(self):
        return json.loads((ROOT / 'models/library.json').read_text(encoding='utf-8'))['assets']

    def test_every_nonempty_transfer_url_is_an_admissible_initial_source(self):
        for asset in self.assets():
            with self.subTest(asset=asset['id']):
                if asset['url']:
                    download_source_provider(asset['url'])
                else:
                    self.assertTrue(asset.get('terms'))

    def test_nine_historical_page_origins_are_explicit_manual_copies(self):
        by_id = {asset['id']: asset for asset in self.assets()}
        self.assertTrue(TARGETS <= by_id.keys())
        for identifier in sorted(TARGETS):
            with self.subTest(asset=identifier):
                asset = by_id[identifier]
                self.assertEqual(asset['url'], '')
                self.assertTrue(asset['source'].startswith('https://civitai.red/models/'))
                self.assertIn('manual copy only', asset['terms'].lower())
                self.assertIn('Owner copy from civitai.red on 2026-09-21', asset['terms'])
                validate_pins(asset)


if __name__ == '__main__':
    unittest.main()
