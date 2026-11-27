"""Offline contract tests; all source identifiers below are synthetic test data."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

try:
    import plan
except ModuleNotFoundError:
    plan = None

HERE = Path(__file__).resolve().parent


def fixture_owner(suite):
    owner = plan.owner_template(suite)
    owner['expected_identity']['workspace'] = 'C:\\P35-test-fixture\\local-asset-studio'
    for index, (key, value) in enumerate(owner['reference_bindings'].items()):
        value.update(file=f'{index + 1:032x}_fixture.png',
                     sha256=hashlib.sha256(('synthetic:' + key).encode()).hexdigest())
    for index, (key, value) in enumerate(owner['guides'].items()):
        value.update(file=f'{index + 101:032x}_drawn-pose.png',
                     sha256=hashlib.sha256(('synthetic-guide:' + key).encode()).hexdigest())
    owner['default_style'] = {'file': 'f' * 32 + '_fixture-style.png',
                              'sha256': hashlib.sha256(b'synthetic-style').hexdigest()}
    for key, value in owner['characters'].items():
        value.update(description='Original adult fictional test character ' + key,
                     outfit='teal travel coat and brass clasp',
                     style='clean cel shading with two or three tones',
                     details=['violet eyes', 'clasp on the left lapel'])
    return owner


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(plan, 'offline plan compiler is not implemented')
        self.bundle = json.loads((HERE / 'routes.json').read_text(encoding='utf-8'))
        self.suite = json.loads((HERE / 'suite.json').read_text(encoding='utf-8'))

    def test_source_graphs_have_exact_hashes_and_valid_bindings(self):
        result = plan.validate_bundle(HERE, self.bundle)
        self.assertEqual(result['routes'], 4)
        self.assertEqual(result['graphs'], 4)
        self.assertEqual(result['source_revision'], '0270760a3d4fd9e005a1788bba59d8242b77c2f4')

    def test_missing_bound_input_is_rejected(self):
        self.bundle['routes'][0]['bindings']['width'] = ['missing', 'width']
        with self.assertRaisesRegex(ValueError, 'binding'):
            plan.validate_bundle(HERE, self.bundle)

    def test_changed_source_graph_is_rejected(self):
        self.bundle['routes'][0]['graph_sha256'] = 'a' * 64
        with self.assertRaisesRegex(ValueError, 'hash'):
            plan.validate_bundle(HERE, self.bundle)

    def test_template_graph_cannot_escape_bundle(self):
        self.bundle['routes'][0]['graph'] = '../routes.json'
        with self.assertRaisesRegex(ValueError, 'graph path'):
            plan.validate_bundle(HERE, self.bundle)

    def test_graph_cycles_and_dangling_edges_are_rejected(self):
        graph = {'1': {'class_type': 'A', 'inputs': {'x': ['2', 0]}},
                 '2': {'class_type': 'B', 'inputs': {'x': ['1', 0]}}}
        with self.assertRaisesRegex(ValueError, 'cycle'):
            plan.validate_graph(graph)
        graph['2']['inputs']['x'] = ['3', 0]
        with self.assertRaisesRegex(ValueError, 'link'):
            plan.validate_graph(graph)

    def test_smoke_is_twelve_slots_and_no_missing_sources_are_invented(self):
        result = plan.compile_plan(self.suite, self.bundle)
        self.assertEqual(result['selected_slots'], 12)
        self.assertEqual(result['full_suite_slots'], 240)
        self.assertFalse(result['ready'])
        self.assertIsNone(result['owner_run'])
        self.assertEqual(result['output_claim'], 'planned')

    def test_complete_smoke_binds_existing_presets_and_two_seeds(self):
        result = plan.compile_plan(self.suite, self.bundle, fixture_owner(self.suite))
        self.assertTrue(result['ready'], result['blockers'])
        run = result['owner_run']
        self.assertEqual(run['max_attempts'], 12)
        self.assertEqual(len(run['chunks']), 6)
        self.assertEqual({v['controls']['seed'] for c in run['chunks'] for v in c['payload']['variants']},
                         {2026112501, 2026112502})
        self.assertEqual({c['payload']['recipe']['preset_id'] for c in run['chunks']},
                         {'combine-klein', 'combine-klein-9b-copypose'})
        self.assertTrue(all(len(c['expected_inputs']) == 2 for c in run['chunks']))
        self.assertTrue(all(c['payload']['max_generations'] == 2 for c in run['chunks']))
        self.assertTrue(all(len(c['expected_graph_sha256']) == 2 for c in run['chunks']))
        self.assertTrue(all(c['expected_graph_sha256'][0] != c['expected_graph_sha256'][1] for c in run['chunks']))
        self.assertTrue(all(len(c['expected_models']) >= 3 for c in run['chunks']))
        self.assertEqual(run['plan_id'], plan.stable_hash({k: v for k, v in run.items() if k != 'plan_id'}))

    def test_invalid_studio_workspace_or_extra_identity_keys_block_before_runner(self):
        for workspace in ('relative/studio', 'C:relative-studio', '/tmp/studio\x00', '/' + 'x' * 2048):
            with self.subTest(workspace=workspace):
                owner = fixture_owner(self.suite)
                owner['expected_identity']['workspace'] = workspace
                result = plan.compile_plan(self.suite, self.bundle, owner)
                self.assertFalse(result['ready'])
                self.assertIsNone(result['owner_run'])
                self.assertTrue(any(blocker['code'] == 'missing_studio_identity' for blocker in result['blockers']))
        owner = fixture_owner(self.suite)
        owner['expected_identity']['extra'] = 'not part of the Studio identity contract'
        result = plan.compile_plan(self.suite, self.bundle, owner)
        self.assertFalse(result['ready'])
        self.assertIsNone(result['owner_run'])

    def test_owner_workspace_accepts_absolute_native_and_windows_paths(self):
        for workspace in (str(HERE.resolve()), r'C:\AI\local-asset-studio'):
            with self.subTest(workspace=workspace):
                owner = fixture_owner(self.suite)
                owner['expected_identity']['workspace'] = workspace
                result = plan.compile_plan(self.suite, self.bundle, owner)
                self.assertTrue(result['ready'], result['blockers'])

    def test_qwen_three_seed_allowance_covers_warm_upper_estimate_and_headroom(self):
        result = plan.compile_plan(self.suite, self.bundle, fixture_owner(self.suite),
                                   profile='full', route_ids=['qwen-3ref'], case_ids=['ordinary-neutral'],
                                   seed_count=3, allow_heavy=True)
        self.assertTrue(result['ready'], result['blockers'])
        self.assertEqual(result['estimated_warm_seconds_range'], [2700, 7200])
        self.assertEqual(result['conservative_chunk_budget_seconds'], 7800)
        self.assertEqual(result['owner_run']['max_seconds'], 7800)
        self.assertEqual(result['owner_run']['chunks'][0]['payload']['max_seconds'], 7800)
        self.assertFalse(result['estimates_are_measurements'])

    def test_larger_qwen_allowance_preserves_the_four_hour_campaign_cap(self):
        result = plan.compile_plan(self.suite, self.bundle, fixture_owner(self.suite),
                                   profile='full', route_ids=['qwen-3ref'],
                                   case_ids=['ordinary-neutral', 'ordinary-reach'], seed_count=3, allow_heavy=True)
        self.assertFalse(result['ready'])
        self.assertIsNone(result['owner_run'])
        self.assertEqual(result['conservative_chunk_budget_seconds'], 15600)
        self.assertTrue(any(blocker['code'] == 'time_budget_exceeded' for blocker in result['blockers']))

    def test_plans_are_deterministic_and_do_not_mutate_inputs(self):
        owner = fixture_owner(self.suite)
        before = copy.deepcopy((self.suite, self.bundle, owner))
        a = plan.compile_plan(self.suite, self.bundle, owner)
        b = plan.compile_plan(self.suite, self.bundle, owner)
        self.assertEqual(a, b)
        self.assertEqual((self.suite, self.bundle, owner), before)
        owner['characters']['canon-a']['outfit'] = 'different coat'
        self.assertNotEqual(a['plan_sha256'], plan.compile_plan(self.suite, self.bundle, owner)['plan_sha256'])

    def test_prospective_protocol_is_frozen_before_trial_identity_without_claiming_execution(self):
        owner = fixture_owner(self.suite)
        original = copy.deepcopy((self.suite, self.bundle, owner))
        planned = plan.compile_plan(self.suite, self.bundle, owner)
        prospective = plan.compile_plan(self.suite, self.bundle, owner, prospective=True)
        self.assertTrue(prospective['ready'], prospective['blockers'])
        self.assertEqual(planned['bound_suite']['evidence_mode'], 'planned')
        self.assertEqual(prospective['bound_suite']['evidence_mode'], 'prospective')
        self.assertNotEqual(planned['suite_sha256'], prospective['suite_sha256'])
        self.assertNotEqual(planned['campaign_id'], prospective['campaign_id'])
        self.assertNotEqual(planned['trial_ledger'][0]['id'], prospective['trial_ledger'][0]['id'])
        self.assertNotEqual(planned['owner_run']['plan_id'], prospective['owner_run']['plan_id'])
        self.assertEqual(prospective['output_claim'], 'planned')
        self.assertEqual(prospective['image_evidence'], planned['image_evidence'])
        self.assertEqual(prospective['image_evidence']['generation'], 'planned')
        self.assertEqual(prospective['image_evidence']['visual_review'], 'unreviewed')
        self.assertTrue(all(trial['output_claim'] == 'planned' for trial in prospective['trial_ledger']))
        self.assertEqual((self.suite, self.bundle, owner), original)

    def test_prospective_protocol_requires_an_explicit_boolean(self):
        for value in ('true', 1, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                plan.compile_plan(self.suite, self.bundle, prospective=value)

    def test_skeleton_image_order_is_reversed_without_redetection(self):
        result = plan.compile_plan(self.suite, self.bundle, fixture_owner(self.suite),
                                   route_ids=['klein9-skeleton'], case_ids=['ordinary-neutral'], seed_count=2)
        self.assertTrue(result['ready'], result['blockers'])
        chunk = result['owner_run']['chunks'][0]
        request = chunk['payload']['recipe']
        self.assertIn('Image 1 is the corrected pose skeleton', request['controls']['positive'])
        self.assertTrue(request['references'][0]['file'].endswith('_drawn-pose.png'))
        self.assertIn('fixture.png', request['controls']['last_reference'])
        self.assertEqual(chunk['detector_behavior'], 'not-applicable')

    def test_stale_or_wrong_skeleton_renderer_blocks(self):
        owner = fixture_owner(self.suite)
        owner['guides']['ordinary-neutral']['renderer'] = 'unqualified-other-renderer/v1'
        result = plan.compile_plan(self.suite, self.bundle, owner,
                                   route_ids=['klein9-skeleton'], case_ids=['ordinary-neutral'])
        self.assertFalse(result['ready'])
        self.assertTrue(any('renderer' in b['reason'] for b in result['blockers']))

    def test_qwen_is_explicit_heavy_opt_in_and_three_references(self):
        owner = fixture_owner(self.suite)
        args = dict(route_ids=['qwen-3ref'], case_ids=['ordinary-neutral'], seed_count=2)
        blocked = plan.compile_plan(self.suite, self.bundle, owner, **args)
        self.assertFalse(blocked['ready'])
        ready = plan.compile_plan(self.suite, self.bundle, owner, allow_heavy=True, **args)
        self.assertTrue(ready['ready'], ready['blockers'])
        chunk = ready['owner_run']['chunks'][0]
        self.assertEqual([r['role'] for r in chunk['payload']['recipe']['references']], ['identity', 'pose', 'style'])
        self.assertEqual(len(chunk['expected_inputs']), 3)
        route = next(r for r in self.bundle['routes'] if r['id'] == 'qwen-3ref')
        graph = plan.materialize_graph(route, plan.read_json(HERE / route['graph']),
                                      chunk['payload']['recipe'], 2026112501)
        self.assertIn('Picture 1 — identity', graph['6']['inputs']['prompt'])
        self.assertNotEqual(plan.stable_hash(graph), plan.studio_hash(graph))
        self.assertEqual(chunk['expected_graph_sha256'][0],
                         hashlib.sha256(json.dumps(graph, sort_keys=True, separators=(',', ':')).encode()).hexdigest())

    def test_extra_style_is_not_silently_discarded_by_two_reference_route(self):
        result = plan.compile_plan(self.suite, self.bundle, fixture_owner(self.suite),
                                   route_ids=['klein4-reference'], case_ids=['ordinary-reach'])
        self.assertFalse(result['ready'])
        self.assertTrue(any('style' in b['reason'] for b in result['blockers']))

    def test_extra_composition_and_costume_references_are_not_discarded(self):
        for role in ('composition', 'costume'):
            with self.subTest(role=role):
                suite = copy.deepcopy(self.suite)
                case = next(c for c in suite['cases'] if c['id'] == 'ordinary-neutral')
                case['references'].append({'id': 'extra-' + role, 'subject_id': 'canon-a',
                    'roles': [role], 'sha256': None, 'source_group': 'extra-' + role, 'claims': {}})
                result = plan.compile_plan(suite, self.bundle, fixture_owner(suite),
                    route_ids=['klein4-reference'], case_ids=['ordinary-neutral'])
                self.assertFalse(result['ready'])
                self.assertIsNone(result['owner_run'])

    def test_contradictory_outfit_claims_block_submission(self):
        case = next(c for c in self.suite['cases'] if c['id'] == 'ordinary-neutral')
        case['references'][0]['claims'] = {'outfit': {'coat': 'red'}}
        case['references'][1]['roles'].append('outfit')
        case['references'][1]['claims'] = {'outfit': {'coat': 'blue'}}
        result = plan.compile_plan(self.suite, self.bundle, fixture_owner(self.suite),
            route_ids=['klein4-reference'], case_ids=['ordinary-neutral'])
        self.assertFalse(result['ready'])
        self.assertTrue(any('conflict' in b['reason'] for b in result['blockers']))

    def test_multi_character_cells_are_visible_and_unsupported(self):
        ids = [c['id'] for c in self.suite['cases'] if c['family'] == 'multi-character']
        result = plan.compile_plan(self.suite, self.bundle, fixture_owner(self.suite),
                                   route_ids=['klein9-copy-pose'], case_ids=ids, seed_count=3)
        self.assertEqual(result['selected_slots'], 6)
        self.assertEqual(len(result['trial_ledger']), 6)
        self.assertFalse(result['ready'])
        self.assertTrue(all(t['status'] == 'unsupported' for t in result['trial_ledger']))

    def test_native_input_cannot_silently_drop_an_assigned_facet(self):
        for native_role, extra_role, route, case_id in (
            ('identity', 'composition', 'klein4-reference', 'ordinary-neutral'),
            ('pose', 'outfit', 'klein4-reference', 'ordinary-neutral'),
            ('pose', 'costume', 'klein9-copy-pose', 'ordinary-neutral'),
            ('pose', 'detail', 'klein9-skeleton', 'ordinary-neutral'),
            ('style', 'outfit', 'qwen-3ref', 'ordinary-reach'),
            ('style', 'composition', 'qwen-3ref', 'ordinary-reach'),
        ):
            with self.subTest(native_role=native_role, extra_role=extra_role, route=route):
                suite = copy.deepcopy(self.suite)
                case = next(case for case in suite['cases'] if case['id'] == case_id)
                source = next(ref for ref in case['references'] if native_role in ref['roles'])
                source['roles'].append(extra_role)
                result = plan.compile_plan(suite, self.bundle, fixture_owner(suite),
                                           route_ids=[route], case_ids=[case_id], allow_heavy=True)
                self.assertFalse(result['ready'])
                self.assertIsNone(result['owner_run'])
                self.assertEqual(len(result['trial_ledger']), 2)
                self.assertTrue(all(trial['status'] == 'unsupported' for trial in result['trial_ledger']))
                self.assertTrue(any('facet' in blocker['reason'] and extra_role in blocker['reason']
                                    for blocker in result['blockers']))

    def test_native_identity_keeps_its_declared_outfit_costume_and_detail_facets(self):
        for outfit_role in ('outfit', 'costume'):
            with self.subTest(outfit_role=outfit_role):
                suite = copy.deepcopy(self.suite)
                case = next(case for case in suite['cases'] if case['id'] == 'ordinary-neutral')
                source = next(ref for ref in case['references'] if 'identity' in ref['roles'])
                source['roles'] = ['identity', outfit_role, 'detail']
                result = plan.compile_plan(suite, self.bundle, fixture_owner(suite),
                                           route_ids=['klein4-reference'], case_ids=[case['id']])
                self.assertTrue(result['ready'], result['blockers'])
                bound_case = next(case for case in result['bound_suite']['cases'] if case['id'] == 'ordinary-neutral')
                self.assertEqual(bound_case['route_inputs']['klein4-reference'][0]['roles'], source['roles'])

    def test_unknown_route_or_case_and_duplicate_selection_refuse(self):
        for args in ({'route_ids': ['typo']}, {'case_ids': ['typo']},
                     {'route_ids': ['klein4-reference', 'klein4-reference']}, {'seed_count': 1}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                plan.compile_plan(self.suite, self.bundle, **args)

    def test_changed_reference_hash_changes_plan_identity(self):
        owner = fixture_owner(self.suite)
        before = plan.compile_plan(self.suite, self.bundle, owner)
        owner['reference_bindings']['canon-a']['sha256'] = 'b' * 64
        after = plan.compile_plan(self.suite, self.bundle, owner)
        self.assertNotEqual(before['plan_sha256'], after['plan_sha256'])
        self.assertNotEqual(before['campaign_id'], after['campaign_id'])

    def test_unsafe_upload_names_nonfinite_and_duplicate_inputs_refuse(self):
        owner = fixture_owner(self.suite)
        owner['reference_bindings']['canon-a']['file'] = '../outside.png'
        result = plan.compile_plan(self.suite, self.bundle, owner)
        self.assertFalse(result['ready'])
        owner = fixture_owner(self.suite)
        owner['characters']['canon-a']['bad'] = float('nan')
        with self.assertRaises(ValueError):
            plan.compile_plan(self.suite, self.bundle, owner)
        owner = fixture_owner(self.suite)
        owner['reference_bindings']['pose-ordinary-neutral'] = copy.deepcopy(owner['reference_bindings']['canon-a'])
        result = plan.compile_plan(self.suite, self.bundle, owner)
        self.assertFalse(result['ready'])
        self.assertTrue(any('same source' in b['reason'] for b in result['blockers']))

    def test_full_plan_keeps_all_240_cells_and_requires_bounded_shards(self):
        result = plan.compile_plan(self.suite, self.bundle, fixture_owner(self.suite), profile='full', allow_heavy=True)
        self.assertEqual(len(result['trial_ledger']), 240)
        self.assertFalse(result['ready'])
        self.assertTrue(any(b['code'] == 'time_budget_exceeded' for b in result['blockers']))

    def test_art_claims_never_promote_from_a_plan(self):
        result = plan.compile_plan(self.suite, self.bundle, fixture_owner(self.suite))
        self.assertEqual(result['image_evidence'], {'generation': 'planned', 'visual_review': 'unreviewed',
                                                  'project_acceptance': None, 'licence_clearance': None})
        self.assertIsNone(result['measured_runtime_seconds'])
        self.assertIsNone(result['measured_peak_vram_gib'])

    def test_bounded_json_duplicate_keys_and_oversized_inputs_refuse(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'x.json'
            p.write_text('{"x":1,"x":2}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                plan.read_json(p)
            p.write_text('[' + '0,' * 700000 + '0]', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'large'):
                plan.read_json(p)


if __name__ == '__main__':
    unittest.main()
