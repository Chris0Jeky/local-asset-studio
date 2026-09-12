"""CI checks against the real repository catalog, graphs and existing brief validator."""
from pathlib import Path
import tempfile
import unittest
import copy
from scripts import character_study as c
from scripts import game_asset_pipeline as existing

ROOT = Path(__file__).resolve().parents[1]


class RepositoryContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name)
        canon = c.read_json(ROOT / 'research/character-consistency/canon.example.json')
        for ref in canon['references']:
            p = self.workspace / ref['path']; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b'synthetic contract fixture'); ref['sha256'] = c.file_sha(p)
        canon = c.attest_canon(canon, 'fixture-owner', 'human', 'Synthetic test only.')
        self.plan = c.make_plan(canon, c.read_json(ROOT / 'research/character-consistency/pilot.study.json'))

    def test_every_case_matches_existing_game_asset_brief(self):
        for case in self.plan['cases']:
            with self.subTest(case=case['id']):
                existing.validate_brief(c.case_brief(self.plan, case['id']), existing.catalog())

    def test_existing_native_templates_can_be_pinned_without_submission(self):
        seen = set()
        for case in self.plan['cases']:
            if case['preset_id'] in seen: continue
            seen.add(case['preset_id'])
            result = c.prepare_handoff(self.plan, case['id'], self.workspace, ROOT)
            self.assertEqual(result['preset_id'], case['preset_id'])
            self.assertFalse(result['submits_generation']); self.assertIsNone(result['submission_payload'])
            self.assertEqual(result['template_sha256'], c.file_sha(ROOT / result['template_path']))
        self.assertEqual(seen, {'qwen-1ref', 'flux-edit'})

    def test_handoff_rechecks_its_hash_current_pins_and_reference_roles(self):
        case = self.plan['cases'][0]
        handoff = c.prepare_handoff(self.plan, case['id'], self.workspace, ROOT)
        observed_case, preset = c.check_handoff(self.plan, handoff, ROOT)
        self.assertEqual(observed_case['id'], case['id']); self.assertEqual(preset['id'], handoff['preset_id'])
        for change in (lambda h: h['proposed_controls'].update(seed=0), lambda h: h['upload_requirements'][0].update(role='costume')):
            altered = copy.deepcopy(handoff); change(altered); altered['handoff_sha256'] = c.sha({k: v for k, v in altered.items() if k != 'handoff_sha256'})
            with self.assertRaises(ValueError): c.check_handoff(self.plan, altered, ROOT)


if __name__ == '__main__': unittest.main()
