"""Inert primary-case import proof through Production.create, with no model work."""
import copy
from io import BytesIO
import json
from pathlib import Path
import shutil
import threading
import unittest
from unittest.mock import patch
from PIL import Image

import test_production
from test_server import FakeStudio
from scripts import character_study as character


ROOT = Path(__file__).resolve().parents[1]
buffer = BytesIO(); Image.new('RGB', (8, 8), (20, 40, 80)).save(buffer, 'PNG'); PNG = buffer.getvalue()


class CharacterHandoffImportTests(unittest.TestCase):
    def setUp(self):
        test_production.ProductionTests.setUp(self); self.addCleanup(test_production.ProductionTests.tearDown, self)
        catalog = character.read_json(ROOT/'presets/catalog.json'); preset = next(p for p in catalog['presets'] if p['id'] == 'qwen-1ref')
        graph = ROOT/preset['graph']; target = self.root/preset['graph']; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(graph, target)
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets': [preset]}), encoding='utf-8')
        self.workspace = self.root/'canon-workspace'; canon = character.read_json(ROOT/'research/character-consistency/canon.example.json')
        for ref in canon['references']:
            path = self.workspace/ref['path']; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(PNG); ref['sha256'] = character.file_sha(path)
        self.plan = character.make_plan(character.attest_canon(canon, 'fixture-owner', 'human', 'Synthetic approval only.'), {
            'schema_version': 1, 'kind': 'character_study_request', 'study_id': 'fixture-study',
            'routes': [{'id': 'qwen-current', 'preset_id': 'qwen-1ref', 'notes': 'fixture'}],
            'tasks': [
                {'id': 'back', 'instruction': 'One neutral back view.', 'reference_ids': ['front'], 'required_checks': ['identity']},
                {'id': 'profile', 'instruction': 'One strict profile.', 'reference_ids': ['portrait-calm'], 'required_checks': ['identity']},
            ], 'seeds': [7], 'budget': {'max_generation_attempts': 2, 'max_repairs_per_case': 0, 'allow_paid_services': False}, 'hypotheses': ['fixture']})
        self.studio = FakeStudio(self.root, [])

    def payload(self, case):
        handoff = character.prepare_handoff(self.plan, case['id'], self.workspace, self.root)
        requirement = handoff['upload_requirements'][0]
        uploaded = self.studio.upload(requirement['id']+'.png', 'image/png', PNG)
        return {'character_plan': copy.deepcopy(self.plan), 'character_handoff': handoff,
                'uploads': [{'reference_id': requirement['id'], 'file': uploaded['file']}],
                'name': 'Fixture '+case['id'], 'max_seconds': 120}

    def test_imports_two_primary_cases_without_jobs_queue_or_reservations_and_shares_budget(self):
        first, second = self.plan['cases']; a = self.studio.production.create(self.payload(first)); b = self.studio.production.create(self.payload(second))
        self.assertEqual(self.studio.jobs, {}); self.assertTrue(self.studio.queue.empty())
        self.assertEqual(a['budget'], {'allowance': 2, 'reserved': 0}); self.assertEqual(b['budget'], {'allowance': 2, 'reserved': 0}); self.assertEqual(a['root_id'], b['root_id'])
        full = self.studio.production.get(a['id'], True); self.assertEqual(full['plan']['character_source']['case_id'], first['id']); self.assertEqual(full['plan']['character_source']['uploads'][0]['sha256'], character.file_sha(self.workspace/'examples/standard-extracted/front.png'))
        with self.assertRaisesRegex(ValueError, 'already imported'): self.studio.production.create(self.payload(first))
        self.patches[0].stop()  # Start only the two test callers; the fixture worker remains unstarted.
        barrier = threading.Barrier(3); errors = []
        def start(identifier):
            try: barrier.wait(); self.studio.production.start(identifier)
            except Exception as exc: errors.append(exc)
        threads = [threading.Thread(target=start, args=(item['id'],)) for item in (a, b)]
        for thread in threads: thread.start()
        barrier.wait()
        for thread in threads: thread.join()
        self.assertEqual(errors, []); self.assertEqual(self.studio.production.get(a['id'])['budget']['reserved'], 2)
        restarted = FakeStudio(self.root, [])
        restored = restarted.production.get(a['id'], True); self.assertEqual(restored['state']['status'], 'interrupted'); self.assertEqual(restored['plan']['character_source']['handoff']['handoff_sha256'], full['plan']['character_source']['handoff']['handoff_sha256'])

    def test_failed_preflight_rolls_back_before_project_or_budget_write(self):
        case = self.plan['cases'][0]; before = self.studio.production.list()
        with patch.object(self.studio, 'production_preflight', side_effect=ValueError('fixture preflight failure')):
            with self.assertRaisesRegex(ValueError, 'fixture preflight failure'): self.studio.production.create(self.payload(case))
        self.assertEqual(self.studio.production.list(), before); self.assertTrue(self.studio.queue.empty()); self.assertEqual(self.studio.jobs, {})


if __name__ == '__main__': unittest.main()
