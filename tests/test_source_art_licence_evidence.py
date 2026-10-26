"""Keep source-art terms evidence attached to the bytes and recipes it describes."""
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'docs/adaptive-studio/assets'
EVIDENCE = ASSETS / 'LICENCE-EVIDENCE-1512.md'


class SourceArtLicenceEvidenceTests(unittest.TestCase):
    def test_atelier_receipts_link_terms_without_inventing_model_ids(self):
        receipts = list((ASSETS / 'production/20261002-atelier/receipts').glob('*.json'))
        self.assertEqual(len(receipts), 6)
        for path in receipts:
            with self.subTest(receipt=path.name):
                receipt = json.loads(path.read_text(encoding='utf-8'))
                link = receipt['source']['terms_evidence']
                self.assertIsInstance(link, str, 'missing dated OpenAI terms evidence')
                target, anchor = link.split('#')
                self.assertEqual((path.parent / target).resolve(), EVIDENCE)
                self.assertEqual(anchor, 'openai')
                self.assertTrue(EVIDENCE.is_file())
                self.assertIsNone(receipt['production']['reported_model'])

    def test_krea_generator_and_official_styles_link_read_licence(self):
        assets = json.loads((ROOT / 'models/library.json').read_text(encoding='utf-8'))['assets']
        official = [a for a in assets if a.get('repo') == 'Comfy-Org/Krea-2'
                    and a.get('license') == 'Krea 2 Community']
        self.assertTrue(any(a['id'] == 'krea-turbo' for a in official))
        for asset in official:
            with self.subTest(model=asset['id']):
                self.assertIn('docs/adaptive-studio/assets/LICENCE-EVIDENCE-1512.md#krea-2',
                              asset.get('terms', ''))
                self.assertNotIn('LICENSE.pdf not read', asset.get('terms', ''))

    def test_recover_displayed_assets_match_original_recipes_and_hashes(self):
        folder = ASSETS / 'production/20261014-recover-fixture-tutorial'
        fixture = json.loads((folder / 'RECOVER-FIXTURE.json').read_text(encoding='utf-8'))
        recording = json.loads((folder / 'recording-receipt.json').read_text(encoding='utf-8'))
        review = fixture.get('licence_review', {})
        self.assertEqual(review.get('qwen_image_21_outputs'), [])
        displayed = review.get('displayed_assets', [])
        requested = {r['path'].removeprefix('/api/') for r in recording['http_requests']
                     if r['path'].startswith('/api/examples/')}
        self.assertEqual({a['path'] for a in displayed}, requested)
        for asset in displayed:
            with self.subTest(asset=asset['path']):
                self.assertEqual(hashlib.sha256((ROOT / asset['path']).read_bytes()).hexdigest(),
                                 asset['sha256'])
                recipe = json.loads((ROOT / asset['recipe']).read_text(encoding='utf-8'))
                submission = recipe['submissions'][0]
                self.assertEqual(asset['prompt_id'], submission['prompt_id'])
                loaders = [v['inputs'] for v in submission['graph'].values()
                           if 'Loader' in v['class_type']]
                self.assertTrue(any(asset['generator_file'] in inputs.values() for inputs in loaders))
                self.assertFalse(any('2.1' in str(inputs) for inputs in loaders))
        self.assertEqual(fixture['seeded_state']['outputs'], [])
        self.assertFalse(recording['generation_submitted'])


if __name__ == '__main__':
    unittest.main()
