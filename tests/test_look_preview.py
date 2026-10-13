"""Presentation references never alter or reidentify a saved Look."""
import copy
import json
import unittest
import test_looks as fixture
ROOT, TEXT, looks = fixture.ROOT, fixture.TEXT, fixture.looks


class LookPreviewTests(unittest.TestCase):
    setUp = fixture.LookTests.setUp

    def seed(self):
        self.seed_data = json.loads((ROOT / 'presets/looks.json').read_text(encoding='utf-8'))
        (self.root / 'presets/looks.json').write_text(json.dumps(self.seed_data))
        (self.root / 'presets/catalog.json').write_text(json.dumps({'presets': [dict(TEXT, id='zimage-fast')]}))
        return looks.listing(self.studio)['looks'][0]

    def test_unchanged_shipped_look_gets_a_separate_visual_reference(self):
        card = self.seed()
        preview = card.get('visual_reference')
        self.assertIsNotNone(preview, 'The unchanged shipped Look needs its optional display-only reference')
        self.assertEqual(preview['src'], '/static/look-previews/night-shift-ma-responsive-1024.webp')
        self.assertEqual(card['lineage'], self.seed_data['looks'][0]['lineage'])
        self.assertNotIn('visual_reference', self.studio.assets.card(card['id']))
        prepared = looks.prepare(self.studio, {'id': card['id'], 'scene': 'a rainy rooftop'})
        self.assertNotIn('visual_reference', prepared)
        self.assertFalse(prepared['generation_submitted'])
        self.assertEqual(self.requests, [])

    def test_edited_content_does_not_inherit_the_reference(self):
        card = self.seed()
        looks.command(self.studio, {'action': 'edit', 'id': card['id'], 'name': 'My own Look', 'expected_revision': card['revision']})
        self.assertNotIn('visual_reference', looks.listing(self.studio)['looks'][0])

    def test_put_away_reference_is_suppressed_and_restore_recovers_it(self):
        card = self.seed()
        saved = looks.command(self.studio, {'action': 'trash', 'id': card['id'], 'expected_revision': card['revision']})
        self.assertNotIn('visual_reference', looks.listing(self.studio)['looks'][0])
        looks.command(self.studio, {'action': 'restore', 'id': card['id'], 'expected_revision': saved['revision']})
        self.assertIn('visual_reference', looks.listing(self.studio)['looks'][0])

    def test_reused_id_with_different_lineage_does_not_claim_the_reference(self):
        self.seed_data = json.loads((ROOT / 'presets/looks.json').read_text(encoding='utf-8'))
        other = copy.deepcopy(self.seed_data)
        other['looks'][0]['lineage'][0]['sha256'] = '0' * 64
        (self.root / 'presets/looks.json').write_text(json.dumps(other))
        (self.root / 'presets/catalog.json').write_text(json.dumps({'presets': [dict(TEXT, id='zimage-fast')]}))
        self.assertNotIn('visual_reference', looks.listing(self.studio)['looks'][0])


if __name__ == '__main__':
    unittest.main()
