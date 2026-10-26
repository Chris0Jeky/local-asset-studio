"""Frozen same-seed study recipes through the ordinary Studio ticket binder."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_server as fixtures
from studio_workflow.execution import prepare_ticket

REPO = Path(__file__).resolve().parents[1]
STUDY = REPO / 'experiments/curated/hidream-step-comparison'


class HiDreamComparisonTests(unittest.TestCase):
    setUp = fixtures.ServerTests.setUp
    tearDown = fixtures.ServerTests.tearDown
    studio = fixtures.ServerTests.studio

    def test_same_seed_recipes_bind_only_a_step_change(self):
        for steps in (8, 20):
            self.assertTrue((STUDY / f'recipe-{steps}.json').is_file(), 'Missing frozen HiDream comparison recipe')
        recipes = [json.loads((STUDY / f'recipe-{steps}.json').read_bytes()) for steps in (8, 20)]
        first, second = copy.deepcopy(recipes)
        self.assertEqual(first['controls'].pop('steps'), 8)
        self.assertEqual(second['controls'].pop('steps'), 20)
        self.assertEqual(first, second)
        self.assertEqual(first['preset_id'], 'hidream-o1-concept')
        self.assertEqual(first['batch_count'], 1)
        self.assertEqual(first['controls']['seed'], 2026091131)
        self.assertEqual((first['controls']['width'], first['controls']['height']), (2048, 2048))
        catalog = json.loads((REPO / 'presets/catalog.json').read_bytes())
        preset = next(p for p in catalog['presets'] if p['id'] == first['preset_id'])
        graph_path = self.root / preset['graph']
        graph_path.write_bytes((REPO / preset['graph']).read_bytes())
        (self.root / 'presets/catalog.json').write_text(json.dumps({'presets': [preset]}))
        (self.root / '.runtime').mkdir()
        (self.root / '.runtime/backend-state.json').write_text(json.dumps({'active': 'hidream'}))
        studio = self.studio()
        with patch.object(studio, 'options', return_value={'loras': []}):
            tickets = [prepare_ticket(studio, recipe) for recipe in recipes]
            graphs = [studio.prepare(ticket['recipe'])[1] for ticket in tickets]
        for ticket in tickets:
            self.assertFalse(ticket['generation_submitted'])
            self.assertEqual(ticket['pins']['backend_id'], 'hidream')
            self.assertEqual(ticket['pins']['backend_url'], 'http://127.0.0.1:8192')
            self.assertEqual(ticket['pins']['template_sha256'], first['expected_template_sha256'])
        self.assertEqual(first['expected_template_sha256'], hashlib.sha256(graph_path.read_bytes()).hexdigest())
        for graph, steps in zip(graphs, (8, 20)):
            self.assertEqual(graph['3']['inputs'].pop('steps'), steps)
            self.assertEqual(graph['3']['inputs']['image'], '0')
            self.assertEqual(graph['1']['inputs']['attention'], 'sdpa')
            self.assertFalse(graph['1']['inputs']['download_if_missing'])
        self.assertEqual(*graphs)
        self.assertEqual(studio.jobs, {})
        self.assertTrue(studio.queue.empty())
