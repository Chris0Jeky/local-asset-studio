"""Causal behavior tests. Every label and byte identity here is synthetic."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

import qualification as q

AXES = ('identity', 'outfit_detail', 'pose_geometry', 'style', 'anatomy_contact', 'composition')
FAMILIES = ('ordinary', 'unusual', 'foreshortened', 'occluded', 'contact-heavy', 'floor', 'seated', 'lying', 'dynamic-action', 'multi-character')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def sha(text): return hashlib.sha256(text.encode()).hexdigest()


def suite(bound=False):
    result = json.loads(Path(__file__).with_name('suite.json').read_text())
    if bound:
        result['evidence_mode'] = 'synthetic'
        result['route_pins'] = {name: sha(name) for name in result['routes']}
        for character in result['canon']: character['reference_sha256'] = sha(character['id'])
        for case in result['cases']:
            for reference in case['references']: reference['sha256'] = sha(reference['id'])
    return result


def expected_trial(document, case_index=0, route_index=0, seed_index=0):
    case = document['cases'][case_index]
    route = document['routes'][route_index]
    value = {'suite_sha256': digest(document), 'case_sha256': digest(case),
             'references_sha256': digest(case['references']), 'case_id': case['id'],
             'route_id': route, 'route_sha256': document['route_pins'][route],
             'seed': document['seeds'][seed_index], 'rubric_sha256': q.rubric_fingerprint(document['minimum_score'])}
    return {'id': digest(value), **value, 'case': copy.deepcopy(case), 'minimum_score': document['minimum_score']}


def receipt(trial, status='completed', score=4, reviewer_kind='human'):
    lineage = {key: trial[key] for key in ('suite_sha256', 'case_sha256', 'references_sha256', 'route_sha256', 'seed', 'rubric_sha256')}
    lineage.update({key: sha(key) for key in ('graph_sha256', 'model_set_sha256', 'preprocessing_sha256', 'settings_sha256', 'environment_sha256')})
    lineage.update(job_id='synthetic-job', prompt_id='synthetic-prompt')
    output = sha(trial['id']) if status == 'completed' else None
    review = {'reviewer_id': 'synthetic-reviewer', 'reviewer_kind': reviewer_kind, 'reviewer_role': 'reviewer',
              'output_sha256': output, 'case_sha256': trial['case_sha256'],
              'scores': {subject: {axis: score for axis in AXES} for subject in trial['case']['subject_ids']},
              'notes': 'Synthetic test observation; no actual artwork was viewed.'} if output else None
    return {'trial_id': trial['id'], 'status': status, 'lineage': lineage, 'output_sha256': output, 'review': review,
            'cost': {'attempts': 1 if status != 'unsupported' else 0, 'retry_count': 0,
                     'runtime_seconds': None if status == 'unsupported' else 10.0,
                     'peak_vram_bytes': None if status == 'unsupported' else 1000,
                     'peak_ram_bytes': None if status == 'unsupported' else 2000, 'operator_seconds': 2.0},
            'reason': 'Synthetic test receipt'}


def calibration(inverted=False, source='synthetic'):
    cohort = [{'asset_id': f'asset-{i}', 'output_sha256': sha(f'image-{i}'), 'source_group': f'lineage-{i}',
               'split': 'holdout', 'owner_mark': 'keep' if i % 2 == 0 else 'not_this',
               'owner_id': 'synthetic-owner', 'label_source': source} for i in range(4)]
    spec = {'schema': 'studio.metric-calibration/v1', 'id': 'synthetic-rubric', 'kind': 'subjective_rubric',
            'source': source, 'threshold': 0.75, 'direction': 'higher',
            'frozen_at': '2026-11-25T00:00:00Z', 'holdout_revealed_at': '2026-11-25T02:00:00Z',
            'development_groups': ['development-a'], 'cohort': cohort, 'owner_declaration': None}
    spec['spec_sha256'] = digest(spec)
    rows = [{'asset_id': c['asset_id'], 'output_sha256': c['output_sha256'], 'source_group': c['source_group'],
             'value': (0.9 if c['owner_mark'] == 'keep' else 0.1) if not inverted else (0.1 if c['owner_mark'] == 'keep' else 0.9),
             'spec_sha256': spec['spec_sha256'], 'scored_at': '2026-11-25T01:00:00Z'} for c in cohort]
    return spec, rows


class QualificationTests(unittest.TestCase):
    def mapping(self, value): self.assertIsInstance(value, dict); return value

    def test_canonical_hash_is_order_independent_and_not_lossy(self):
        self.assertEqual(q.canonical_hash({'z': 2, 'a': 1}), hashlib.sha256(b'{"a":1,"z":2}').hexdigest())
        for value in ({'x': float('nan')}, {'x': float('inf')}, {1: 'a', '1': 'b'}):
            with self.subTest(value=value), self.assertRaises(ValueError): q.canonical_hash(value)

    def test_unicode_hash_matches_route_compiler_utf8_contract(self):
        self.assertEqual(q.canonical_hash({'name': 'épée'}), hashlib.sha256('{"name":"épée"}'.encode('utf-8')).hexdigest())

    def test_actual_route_input_hash_cannot_be_omitted_from_receipt(self):
        doc = suite(True)
        doc['cases'][0]['route_inputs'] = {'klein4-reference': [{'source_group': 'guide-a', 'sha256': sha('corrected-guide'), 'representation': 'precomputed-skeleton'}]}
        report = self.mapping(q.validate_suite(doc)); trial = report['trials'][0]
        self.assertIn('route_inputs_sha256', trial)
        value = receipt(trial)
        with self.assertRaises(ValueError): q.score_case(trial, value)

    def test_strict_json_refuses_duplicate_keys_and_nan(self):
        for raw in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError): q.loads(raw)

    def test_suite_keeps_240_slots_and_twenty_missing_cases(self):
        report = self.mapping(q.validate_suite(suite()))
        self.assertEqual(len(report['trials']), 240)
        self.assertEqual(report['coverage']['cases_per_family'], {f: 2 for f in FAMILIES})
        self.assertEqual(len({t['id'] for t in report['trials']}), 240)
        self.assertFalse(report['ready'])
        self.assertIn('missing_reference_bytes', report['blockers'])
        self.assertEqual(report['suite_sha256'], digest(suite()))

    def test_suite_rejects_duplicate_seed_case_and_nonfinite_score_threshold(self):
        for mutation in ('seed', 'case', 'nan'):
            doc = suite()
            if mutation == 'seed': doc['seeds'][1] = doc['seeds'][0]
            elif mutation == 'case': doc['cases'][1]['id'] = doc['cases'][0]['id']
            else: doc['minimum_score'] = float('nan')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): q.validate_suite(doc)

    def test_omitting_hard_family_blocks_suite(self):
        doc = suite(True); doc['cases'] = [c for c in doc['cases'] if c['family'] != 'occluded']
        result = self.mapping(q.validate_suite(doc))
        self.assertFalse(result['ready']); self.assertIn('occluded', result['coverage']['missing_families'])

    def test_role_alias_preserves_subject_and_explicit_conflict(self):
        refs = [{'id': 'a', 'subject_id': 'canon-a', 'roles': ['outfit'], 'sha256': sha('a'), 'source_group': 'ga', 'claims': {'outfit': {'hat': 'red'}}},
                {'id': 'b', 'subject_id': 'canon-a', 'roles': ['costume'], 'sha256': sha('b'), 'source_group': 'gb', 'claims': {'costume': {'hat': 'blue'}}}]
        result = self.mapping(q.resolve_roles(refs, {'id': 'route', 'supported_roles': ['costume'], 'max_references': 2, 'per_subject': True}))
        self.assertFalse(result['runnable']); self.assertEqual(result['references'][0]['roles'], ['costume'])
        self.assertEqual(result['references'][0]['subject_id'], 'canon-a'); self.assertIn('explicit_role_conflict', result['blockers'])

    def test_subjects_do_not_create_conflict_but_need_per_subject_support(self):
        refs = [{'id': c, 'subject_id': c, 'roles': ['identity'], 'sha256': sha(c), 'source_group': c, 'claims': {'identity': {'hair': c}}} for c in ('canon-a', 'canon-b')]
        result = self.mapping(q.resolve_roles(refs, {'id': 'route', 'supported_roles': ['identity'], 'max_references': 2, 'per_subject': False}))
        self.assertFalse(result['runnable']); self.assertIn('per_subject_unsupported', result['blockers'])
        self.assertNotIn('explicit_role_conflict', result['blockers'])

    def test_unknown_scene_detail_roles_and_capacity_are_not_silent_fallbacks(self):
        refs = [{'id': c, 'subject_id': None, 'roles': [c], 'sha256': sha(c), 'source_group': c, 'claims': {}} for c in ('scene', 'detail')]
        result = self.mapping(q.resolve_roles(refs, {'id': 'route', 'supported_roles': ['identity'], 'max_references': 1, 'per_subject': False}))
        self.assertEqual(set(result['blockers']), {'unsupported_role', 'reference_capacity_exceeded'})

    def test_synthetic_perfect_alignment_cannot_authenticate_owner(self):
        result = self.mapping(q.calibrate_metric(*calibration()))
        self.assertEqual(result['agreement'], 1.0); self.assertFalse(result['gating_enabled'])
        self.assertEqual(result['status'], 'synthetic_only'); self.assertFalse(result['owner_authenticated'])

    def test_inverted_metric_is_killed_and_false_passes_are_visible(self):
        result = self.mapping(q.calibrate_metric(*calibration(True)))
        self.assertEqual(result['status'], 'disabled'); self.assertEqual(result['disagreements'], 4)
        self.assertEqual(result['false_passes'], 2); self.assertFalse(result['gating_enabled'])

    def test_single_contradiction_kills_metric(self):
        spec, rows = calibration(); rows[0]['value'] = 0.0
        result = self.mapping(q.calibrate_metric(spec, rows))
        self.assertEqual(result['status'], 'disabled'); self.assertEqual(result['disagreements'], 1)

    def test_available_train_contradiction_kills_with_perfect_holdout(self):
        spec, rows = calibration()
        spec['cohort'].append({'asset_id': 'train-contradiction', 'output_sha256': sha('train-output'),
            'source_group': 'train-group', 'split': 'train', 'owner_mark': 'not_this',
            'owner_id': 'synthetic-owner', 'label_source': 'synthetic'})
        spec['spec_sha256'] = digest({k:v for k,v in spec.items() if k != 'spec_sha256'})
        for row in rows: row['spec_sha256'] = spec['spec_sha256']
        rows.append({'asset_id': 'train-contradiction', 'output_sha256': sha('train-output'), 'source_group': 'train-group',
            'value': 0.9, 'spec_sha256': spec['spec_sha256'], 'scored_at': '2026-11-25T01:00:00Z'})
        result = self.mapping(q.calibrate_metric(spec, rows))
        self.assertEqual(result['status'], 'disabled'); self.assertEqual(result['agreement'], 1.0)
        self.assertEqual(result['false_passes'], 1); self.assertEqual(result['expected'], 4)

    def test_duplicate_output_bytes_cannot_fill_distinct_trial_cells(self):
        doc = suite(True); one = receipt(expected_trial(doc)); two = receipt(expected_trial(doc, seed_index=1))
        two['output_sha256'] = one['output_sha256']; two['review']['output_sha256'] = one['output_sha256']
        with self.assertRaises(ValueError): q.summarize(doc, [one, two])

    def test_missing_owner_labels_cannot_pass(self):
        spec, rows = calibration(source='owner_library')
        result = self.mapping(q.calibrate_metric(spec, rows))
        self.assertFalse(result['gating_enabled']); self.assertIn('owner_declaration_unavailable', result['blockers'])

    def test_simulated_owner_declaration_cannot_gate_an_unbound_rubric(self):
        spec, rows = calibration(source='owner_library')
        statement = 'Synthetic test statement, never actual owner evidence.'
        spec['owner_declaration'] = {'owner_id': 'synthetic-owner', 'snapshot_sha256': digest(spec['cohort']),
            'statement': statement, 'statement_sha256': sha(statement), 'source_reference': 'synthetic-test-only',
            'kind': 'recorded_owner_statement', 'confirms_own_marks': True}
        spec['spec_sha256'] = digest({k:v for k,v in spec.items() if k != 'spec_sha256'})
        for row in rows: row['spec_sha256'] = spec['spec_sha256']
        result = self.mapping(q.calibrate_metric(spec, rows))
        self.assertFalse(result['gating_enabled']); self.assertFalse(result['owner_authenticated'])

    def test_concordant_rubric_without_route_family_scope_cannot_enable_gate(self):
        spec, rows = calibration(source='owner_library'); statement = 'Synthetic test only.'
        spec['rubric_sha256'] = q.rubric_fingerprint()
        spec['owner_declaration'] = {'owner_id': 'synthetic-owner', 'snapshot_sha256': digest(spec['cohort']),
            'statement': statement, 'statement_sha256': sha(statement), 'source_reference': 'synthetic-test-only',
            'kind': 'recorded_owner_statement', 'confirms_own_marks': True}
        spec['spec_sha256'] = digest({k:v for k,v in spec.items() if k != 'spec_sha256'})
        for row in rows: row['spec_sha256'] = spec['spec_sha256']
        result = self.mapping(q.calibrate_metric(spec, rows))
        self.assertFalse(result['gating_enabled']); self.assertIn('calibration_scope_unavailable', result['blockers'])

    def test_narrow_or_foreign_calibration_scope_cannot_open_broader_suite(self):
        doc = suite(True)
        for foreign in (False, True):
            spec, rows = calibration()
            spec['rubric_sha256'] = q.rubric_fingerprint()
            spec['scope'] = {'suite_sha256': sha('another-suite') if foreign else digest(doc),
                'route_ids': [doc['routes'][0]], 'families': ['ordinary'], 'implementation_sha256': sha('metric-code'),
                'preprocessing_sha256': sha('display-originals'), 'model_sha256': None, 'method': 'human_rubric'}
            for mark in spec['cohort']: mark.update(route_id=doc['routes'][0], family='ordinary')
            spec['spec_sha256'] = digest({k:v for k,v in spec.items() if k != 'spec_sha256'})
            for row in rows: row['spec_sha256'] = spec['spec_sha256']
            report = self.mapping(q.summarize(doc, [], q.calibrate_metric(spec, rows)))
            with self.subTest(foreign=foreign):
                self.assertIn('calibration_route_family_scope_mismatch', report['blockers'])
                self.assertFalse(report['qualification_complete'])

    def test_declared_scope_cannot_claim_unrepresented_hard_family(self):
        spec, rows = calibration(); spec['rubric_sha256'] = q.rubric_fingerprint()
        spec['scope'] = {'suite_sha256': sha('suite'), 'route_ids': ['route-a'], 'families': ['ordinary', 'foreshortened'],
            'implementation_sha256': sha('metric-code'), 'preprocessing_sha256': sha('display'), 'model_sha256': None, 'method': 'human_rubric'}
        for mark in spec['cohort']: mark.update(route_id='route-a', family='ordinary')
        spec['spec_sha256'] = digest({k:v for k,v in spec.items() if k != 'spec_sha256'})
        for row in rows: row['spec_sha256'] = spec['spec_sha256']
        report = self.mapping(q.calibrate_metric(spec, rows))
        self.assertIn('calibration_scope_coverage_incomplete', report['blockers']); self.assertFalse(report['gating_enabled'])

    def test_trial_threshold_cannot_be_relaxed_without_changing_identity(self):
        doc = suite(True); doc['minimum_score'] = 4
        trial = expected_trial(doc); value = receipt(trial, score=3); trial['minimum_score'] = 3
        with self.assertRaises(ValueError): q.score_case(trial, value)

    def test_unsupported_trial_cannot_claim_generation_runtime(self):
        trial = expected_trial(suite(True)); value = receipt(trial, 'unsupported')
        value['cost']['runtime_seconds'] = 10
        with self.assertRaises(ValueError): q.score_case(trial, value)

    def test_missing_or_abstained_holdout_is_in_denominator(self):
        for kind in ('missing', 'abstain'):
            spec, rows = calibration()
            if kind == 'missing': rows.pop()
            else: rows[-1]['value'] = None
            result = self.mapping(q.calibrate_metric(spec, rows))
            self.assertEqual(result['expected'], 4); self.assertEqual(result['scored'], 3)
            self.assertFalse(result['gating_enabled']); self.assertIsNone(result['agreement'])

    def test_calibration_refuses_duplicate_contradictory_and_leaked_marks(self):
        for kind in ('duplicate', 'contradictory', 'group_leak', 'bytes_leak'):
            spec, rows = calibration()
            if kind in ('duplicate', 'contradictory'):
                duplicate = copy.deepcopy(spec['cohort'][0])
                if kind == 'contradictory': duplicate['owner_mark'] = 'not_this'
                spec['cohort'].append(duplicate)
            elif kind == 'group_leak': spec['development_groups'].append(spec['cohort'][0]['source_group'])
            else: spec['cohort'][1]['output_sha256'] = spec['cohort'][0]['output_sha256']
            spec['spec_sha256'] = digest({k: v for k, v in spec.items() if k != 'spec_sha256'})
            with self.subTest(kind=kind), self.assertRaises(ValueError): q.calibrate_metric(spec, rows)

    def test_calibration_refuses_stale_spec_nan_and_post_reveal_scoring(self):
        for kind in ('stale', 'nan', 'revealed'):
            spec, rows = calibration()
            if kind == 'stale': spec['threshold'] = 0.6
            elif kind == 'nan': rows[0]['value'] = float('nan')
            else: rows[0]['scored_at'] = '2026-11-25T03:00:00Z'
            with self.subTest(kind=kind), self.assertRaises(ValueError): q.calibrate_metric(spec, rows)

    def test_human_scores_remain_six_independent_axes(self):
        trial = expected_trial(suite(True)); value = receipt(trial)
        value['review']['scores']['canon-a']['pose_geometry'] = 1
        result = self.mapping(q.score_case(trial, value))
        self.assertFalse(result['rubric_pass']); self.assertEqual(result['axis_minimum']['identity'], 4)
        self.assertEqual(result['axis_minimum']['pose_geometry'], 1); self.assertIsNone(result['owner_acceptance'])
        self.assertIn('geometry', {r['failure'] for r in result['repairs']})
        self.assertTrue(result['repair_policy']['preserve_accepted_regions'])

    def test_agent_or_missing_axis_cannot_become_human_review(self):
        for kind in ('agent', 'missing'):
            trial = expected_trial(suite(True)); value = receipt(trial, reviewer_kind='agent' if kind == 'agent' else 'human')
            if kind == 'missing': value['review']['scores']['canon-a']['identity'] = None
            result = self.mapping(q.score_case(trial, value))
            self.assertIsNone(result['rubric_pass']); self.assertTrue(result['human_review_required'])

    def test_human_kind_cannot_masquerade_over_explicit_agent_role(self):
        trial = expected_trial(suite(True)); value = receipt(trial)
        value['review']['reviewer_role'] = 'agent'
        with self.assertRaises(ValueError): q.score_case(trial, value)

    def test_missing_route_cost_does_not_hide_behind_complete_art_scores(self):
        doc = suite(True); doc['evidence_mode'] = 'prospective'
        spec, _ = calibration(source='owner_library'); spec['cohort'] = []; rows = []
        for route in doc['routes']:
            for family in FAMILIES:
                for label in ('keep', 'not_this'):
                    identifier = f'{route}-{family}-{label}'
                    spec['cohort'].append({'asset_id': identifier, 'output_sha256': sha(identifier), 'source_group': identifier,
                        'split': 'holdout', 'owner_mark': label, 'owner_id': 'synthetic-owner', 'label_source': 'owner_library',
                        'route_id': route, 'family': family})
        spec['rubric_sha256'] = q.rubric_fingerprint()
        spec['scope'] = {'suite_sha256': digest(doc), 'route_ids': doc['routes'], 'families': list(FAMILIES),
            'implementation_sha256': sha('synthetic-metric'), 'preprocessing_sha256': sha('synthetic-display'),
            'model_sha256': None, 'method': 'human_rubric'}
        statement = 'Synthetic unit-test declaration, never actual owner evidence.'
        spec['owner_declaration'] = {'owner_id': 'synthetic-owner', 'snapshot_sha256': digest(spec['cohort']),
            'statement': statement, 'statement_sha256': sha(statement), 'source_reference': 'synthetic-test-only',
            'kind': 'recorded_owner_statement', 'confirms_own_marks': True}
        spec['spec_sha256'] = digest({k:v for k,v in spec.items() if k != 'spec_sha256'})
        for mark in spec['cohort']:
            rows.append({'asset_id': mark['asset_id'], 'output_sha256': mark['output_sha256'], 'source_group': mark['source_group'],
                'value': 0.9 if mark['owner_mark'] == 'keep' else 0.1, 'spec_sha256': spec['spec_sha256'], 'scored_at': '2026-11-25T01:00:00Z'})
        calibrated = q.calibrate_metric(spec, rows)
        self.assertFalse(calibrated['owner_authenticated'])
        trials = q.validate_suite(doc)['trials']; receipts = [receipt(trial) for trial in trials]
        receipts[0]['cost']['peak_ram_bytes'] = None
        result = self.mapping(q.summarize(doc, receipts, calibrated))
        self.assertFalse(result['qualification_complete'])
        self.assertFalse(result['routes']['klein4-reference']['qualification_complete'])
        self.assertTrue(result['routes']['qwen-3ref']['qualification_complete'])

    def test_stale_sources_output_and_nonfinite_human_scores_refuse(self):
        for kind in ('source', 'output', 'nan', 'bool'):
            trial = expected_trial(suite(True)); value = receipt(trial)
            if kind == 'source': value['lineage']['references_sha256'] = sha('changed')
            elif kind == 'output': value['review']['output_sha256'] = sha('changed')
            else: value['review']['scores']['canon-a']['identity'] = float('nan') if kind == 'nan' else True
            with self.subTest(kind=kind), self.assertRaises(ValueError): q.score_case(trial, value)

    def test_multi_character_requires_every_subject_review(self):
        doc = suite(True); index = next(i for i, c in enumerate(doc['cases']) if c['family'] == 'multi-character')
        trial = expected_trial(doc, index); value = receipt(trial)
        value['review']['scores'].pop(trial['case']['subject_ids'][-1])
        result = self.mapping(q.score_case(trial, value))
        self.assertIsNone(result['rubric_pass']); self.assertTrue(result['human_review_required'])

    def test_summary_retains_missing_failed_and_unsupported_denominators(self):
        doc = suite(True); trials = [expected_trial(doc, i) for i in (0, 1, 18)]
        rows = [receipt(trials[0]), receipt(trials[1], 'failed'), receipt(trials[2], 'unsupported')]
        result = self.mapping(q.summarize(doc, rows))
        self.assertEqual(result['planned'], 240); self.assertEqual(result['status_counts']['missing'], 237)
        self.assertEqual(result['status_counts']['failed'], 1); self.assertEqual(result['status_counts']['unsupported'], 1)
        first = result['routes']['klein4-reference']
        self.assertEqual(first['planned'], 60); self.assertEqual(first['rubric_pass_rate_lower_bound'], 1 / 60)
        self.assertEqual(first['families']['multi-character']['planned'], 6)
        self.assertIsNone(result['cost']['runtime_seconds_total']); self.assertEqual(result['cost']['runtime_seconds_observed'], 20.0)
        self.assertFalse(result['qualification_complete'])

    def test_summary_refuses_duplicate_receipt_and_caller_forged_calibration(self):
        doc = suite(True); row = receipt(expected_trial(doc))
        with self.assertRaises(ValueError): q.summarize(doc, [row, row])
        result = self.mapping(q.summarize(doc, [], {'gating_enabled': True}))
        self.assertFalse(result['qualification_complete']); self.assertIn('calibration_not_recomputed', result['blockers'])

    def test_geometry_pck_uses_declared_box_without_alignment(self):
        obs = {'pose': {'bbox': [0, 0, 100, 100], 'normalization': 'bbox_diagonal', 'alignment': 'none',
                        'threshold': 0.05, 'min_confidence': 0.5, 'min_visible': 2,
                        'joints': [{'id': 'left', 'expected': [10, 10], 'actual': [10, 10], 'visible': True, 'confidence': 1.0},
                                   {'id': 'right', 'expected': [90, 90], 'actual': [100, 90], 'visible': True, 'confidence': 1.0}]}}
        result = self.mapping(q.automatic_metrics(obs))
        self.assertEqual(result['pose']['pck'], 0.5); self.assertTrue(result['diagnostics_only'])
        self.assertIsNone(result['art_acceptance'])
        obs['pose']['alignment'] = 'procrustes'
        with self.assertRaises(ValueError): q.automatic_metrics(obs)

    def test_low_confidence_or_hidden_joints_cannot_manufacture_perfect_pose(self):
        obs = {'pose': {'bbox': [0, 0, 100, 100], 'normalization': 'bbox_diagonal', 'alignment': 'none',
                        'threshold': 0.05, 'min_confidence': 0.5, 'min_visible': 2,
                        'joints': [{'id': 'a', 'expected': [10, 10], 'actual': [10, 10], 'visible': True, 'confidence': 0.1},
                                   {'id': 'b', 'expected': [90, 90], 'actual': None, 'visible': True, 'confidence': 0.0}]}}
        result = self.mapping(q.automatic_metrics(obs))
        self.assertIsNone(result['pose']['pck']); self.assertEqual(result['pose']['declared_visible'], 2)

    def test_mask_palette_and_protected_pixels_are_exact_diagnostics(self):
        obs = {'silhouette': {'reference': [1, 1, 0, 0], 'candidate': [1, 0, 1, 0], 'confidence': 1.0},
               'palette': {'reference_lab': [50, 10, 20], 'candidate_lab': [53, 14, 20], 'confidence': 1.0},
               'protected_pixels': {'source_size': [2, 1], 'candidate_size': [2, 1], 'alignment': 'same_canvas',
                                    'pixel_format': 'RGBA8', 'color_space': 'sRGB', 'mask': [1, 0],
                                    'source_pixels': [[0, 0, 0, 255], [0, 0, 0, 255]],
                                    'candidate_pixels': [[0, 0, 0, 255], [1, 0, 0, 255]]}}
        result = self.mapping(q.automatic_metrics(obs))
        self.assertAlmostEqual(result['silhouette']['iou'], 1 / 3)
        self.assertEqual(result['palette']['delta_e76'], 5.0)
        self.assertTrue(result['protected_pixels']['unchanged']); self.assertEqual(result['protected_pixels']['changed'], 0)
        obs['protected_pixels']['candidate_size'] = [1, 2]
        with self.assertRaises(ValueError): q.automatic_metrics(obs)

    def test_empty_and_nonfinite_automatic_evidence_remains_unknown(self):
        result = self.mapping(q.automatic_metrics({}))
        self.assertIsNone(result['pose']); self.assertTrue(result['human_review_required'])
        for obs in ({'silhouette': {'reference': [0], 'candidate': [0], 'confidence': 1}},
                    {'palette': {'reference_lab': [0, 0, 0], 'candidate_lab': [0, 0, 0], 'confidence': 0.1}}):
            result = self.mapping(q.automatic_metrics(obs))
            field = 'iou' if 'silhouette' in obs else 'delta_e76'; key = next(iter(obs))
            self.assertIsNone(result[key][field])
        with self.assertRaises(ValueError): q.automatic_metrics({'palette': {'reference_lab': [float('nan'), 0, 0], 'candidate_lab': [0, 0, 0], 'confidence': 1}})


if __name__ == '__main__': unittest.main()
