"""Real catalog traversal and affected-node boundaries against source-derived fixtures.

This does not pretend the reduced corpus is a full installed object_info snapshot.
"""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from test_graph_validation import INFO, pipeline, video
from test_validate_live import validator

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless((ROOT/'presets/catalog.json').is_file(), 'Complete catalog checkout required')
class CatalogGraphIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.presets=pipeline.read_json(ROOT/'presets/catalog.json')['presets']

    def test_default_selection_and_structural_checks_cover_every_catalog_entry(self):
        selected=validator.select_presets(self.presets)
        self.assertEqual(selected,self.presets)
        seen=[]
        for preset in selected:
            graph=pipeline.read_json(pipeline.inside(ROOT,preset['graph']))
            with self.subTest(preset=preset['id']):self.assertFalse(pipeline.graph_check(graph)['node_snapshot_checked'])
            seen.append(preset['id'])
        self.assertEqual(seen,[p['id'] for p in self.presets])
        self.assertTrue(any('collection' not in p for p in selected))
        self.assertTrue(any(p.get('collection')=='workflow-lab' for p in selected))

    def test_incomplete_schema_reports_every_catalog_entry_without_false_success(self):
        # Deliberately no installed types: prove coverage and failures, not compatibility.
        report=validator.validate_catalog(ROOT,validator.select_presets(self.presets),{'FixtureSources':INFO['FixtureSources']})
        self.assertEqual(report['selected'],len(self.presets))
        self.assertEqual(report['failed'],len(self.presets))
        self.assertEqual([r['preset_id'] for r in report['results']],[p['id'] for p in self.presets])
        self.assertEqual(report['submissions'],0);self.assertFalse(report['inference_verified'])

    def test_actual_affected_nodes_pass_their_reduced_schema_boundary(self):
        slots={'SaveVideo':{'video':0},'SaveGLB':{'mesh':1},'ImageCropToMask':{'images':2,'masks':3}}
        found={name:[] for name in slots}
        for preset in self.presets:
            original=pipeline.read_json(pipeline.inside(ROOT,preset['graph']));before=copy.deepcopy(original)
            for node in original.values():
                name=node['class_type']
                if name not in slots:continue
                tested=copy.deepcopy(node)
                for field,slot in slots[name].items():
                    self.assertIsInstance(tested['inputs'][field],list)
                    tested['inputs'][field]=['fixture',slot]
                graph={'fixture':{'class_type':'FixtureSources','inputs':{}},'subject':tested}
                with self.subTest(preset=preset['id'],node=name):pipeline.graph_check(graph,INFO)
                found[name].append(preset['id'])
            self.assertEqual(original,before)
        for name,presets in found.items():self.assertTrue(presets,name+' needs at least one real catalog fixture')
        self.assertIn('wan22-i2v',found['SaveVideo']);self.assertIn('trellis-rgba',found['ImageCropToMask'])


@unittest.skipUnless((ROOT/'app/server.py').is_file(), 'Complete Studio checkout required')
class StudioGraphIntegrationTests(unittest.TestCase):
    def test_actual_studio_validation_delegates_to_same_checker_and_cached_schema(self):
        from test_server import server
        fixture=SimpleNamespace(node_info=Mock(return_value=copy.deepcopy(INFO)))
        graph=video(format='auto',codec='auto')
        with patch.object(pipeline,'graph_check',wraps=pipeline.graph_check) as check:
            result=server.Studio.validate_graph(fixture,graph)
        check.assert_called_once_with(graph,INFO);fixture.node_info.assert_called_once_with()
        self.assertTrue(result['node_snapshot_checked']);self.assertFalse(result['inference_verified'])
        # No Studio initialization, executor, actual backend or model call was needed.
        with self.assertRaisesRegex(ValueError,'Unknown dynamic'):
            server.Studio.validate_graph(fixture,video(format='invalid'))


if __name__=='__main__':unittest.main()
