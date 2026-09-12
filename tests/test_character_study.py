"""Offline contracts only; synthetic attestations are not neural execution evidence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts import character_study as c

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'research/character-consistency'


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.canon = c.read_json(DATA / 'canon.example.json')
        for ref in self.canon['references']:
            path = self.root / ref['path']; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('synthetic reference ' + ref['id']).encode())
            ref['sha256'] = c.file_sha(path)
        self.request = c.read_json(DATA / 'pilot.study.json')
        self.canon = c.attest_canon(self.canon, 'fixture-owner', 'human', 'Synthetic test attestation, not artwork approval.')
        self.plan = c.make_plan(self.canon, self.request)
        self.case = self.plan['cases'][0]

    def record(self, number=1, case=None, kind='primary', parent=None, state='completed', decision='selected', who='agent'):
        case = case or self.case
        evidence = self.root / f'evidence-{number}.json'; evidence.write_text('{"fixture":true}')
        out = self.root / f'output-{number}.png'; out.write_bytes(b'synthetic output, no inference')
        output = {'path': out.name, 'sha256': c.file_sha(out)}
        return {'id': f'attempt-{number}', 'plan_sha256': self.plan['plan_sha256'], 'case_id': case['id'],
                'kind': kind, 'state': state, 'parent_attempt_id': parent,
                'prompt_id': f'fixture-prompt-{number}' if state == 'completed' else None,
                'output': output if state == 'completed' else None,
                'execution_evidence': {'path': evidence.name, 'sha256': c.file_sha(evidence)},
                'elapsed_seconds': 10, 'cleanup_seconds': 2,
                'review': {'reviewer': 'fixture-reviewer', 'reviewer_kind': who, 'decision': decision,
                           'checks': {key: 'pass' for key in case['required_checks']}, 'note': 'Synthetic review.',
                           'output_sha256': output['sha256']} if state == 'completed' and kind != 'warmup' else None}

    def test_plan_is_deterministic_and_matches_checked_in_example(self):
        self.assertEqual(self.plan, c.make_plan(self.canon, self.request))
        original = c.make_plan(c.read_json(DATA / 'canon.example.json'), c.read_json(DATA / 'pilot.study.json'))
        self.assertEqual(original['plan_sha256'], 'b9c7a51b2b8819ef17508d41c88082eca4391ce8c99dc524de6ecfcf6a660f4c')
        self.assertEqual(len(self.plan['cases']), 12)
        self.assertEqual(len({case['id'] for case in self.plan['cases']}), 12)
        self.assertFalse(self.plan['submits_generation'])

    def test_plan_does_not_alias_inputs(self):
        self.request['tasks'][0]['reference_ids'].append('changed')
        self.assertNotIn('changed', self.plan['cases'][0]['reference_ids'])
        c.check_plan(self.plan)

    def test_rehashed_forged_derived_cases_rejected(self):
        plan = copy.deepcopy(self.plan); plan['cases'][0]['seed'] += 1
        plan['plan_sha256'] = c.sha({k: v for k, v in plan.items() if k != 'plan_sha256'})
        with self.assertRaises(ValueError): c.check_plan(plan)

    def test_changed_design_invalidates_approval(self):
        self.canon['identity']['description'] += ' new hair'
        with self.assertRaisesRegex(ValueError, 'Stale'): c.validate_canon(self.canon)

    def test_agent_selection_is_not_approval(self):
        selected = c.attest_canon(self.canon, 'fixture-agent', 'agent', 'Selection only.')
        report = c.preflight(c.make_plan(selected, self.request), self.root)
        self.assertFalse(report['reference_and_canon_checks_passed'])
        self.assertFalse(report['submission_authorized'])

    def test_changed_reference_blocks_preflight(self):
        (self.root / self.canon['references'][0]['path']).write_bytes(b'changed')
        self.assertFalse(c.preflight(self.plan, self.root)['reference_and_canon_checks_passed'])

    def test_missing_reference_blocks_preflight(self):
        (self.root / self.canon['references'][0]['path']).unlink()
        self.assertFalse(c.preflight(self.plan, self.root)['reference_and_canon_checks_passed'])

    def test_total_budget_cannot_be_multiplied(self):
        self.request['budget']['max_generation_attempts'] = 11
        with self.assertRaisesRegex(ValueError, 'matrix'): c.make_plan(self.canon, self.request)

    def test_bool_budget_seed_and_nonfinite_json_rejected(self):
        for value in (True, -1, 2**53):
            req = copy.deepcopy(self.request); req['seeds'] = [value]
            with self.assertRaises(ValueError): c.make_plan(self.canon, req)
        for raw in ('{"x":1,"x":2}', '{"x":NaN}'):
            p = self.root / 'bad.json'; p.write_text(raw)
            with self.assertRaises(ValueError): c.read_json(p)

    def test_unknown_duplicate_fields_and_references_rejected(self):
        for field, value in [('seeds', [1, 1]), ('unknown', True)]:
            req = copy.deepcopy(self.request); req[field] = value
            with self.assertRaises(ValueError): c.make_plan(self.canon, req)
        req = copy.deepcopy(self.request); req['tasks'][0]['reference_ids'] = ['unknown']
        with self.assertRaises(ValueError): c.make_plan(self.canon, req)

    def test_portable_paths(self):
        for value in ('../escape', '/tmp/x', 'C:/x', 'x\\y', 'a//b', './x', 'NUL.txt', 'a./x', 'a:stream', 'a\0b'):
            with self.subTest(value=value), self.assertRaises(ValueError): c.relative(value)

    def test_exclusive_outputs(self):
        p = self.root / 'once.json'; c.write_json(p, {'x': 1})
        with self.assertRaises(FileExistsError): c.write_json(p, {'x': 2})
        self.assertEqual(c.read_json(p), {'x': 1})

    def test_empty_results_remain_unmeasured(self):
        result = c.summarize(self.plan, [], self.root)
        self.assertIsNone(result['first_pass_selection_rate'])
        self.assertIsNone(result['total_elapsed_seconds'])
        self.assertIsNone(result['seconds_per_selected_case'])
        self.assertEqual(result['attempts_remaining'], 12)

    def test_metrics_and_agent_selection_separate(self):
        result = c.summarize(self.plan, [self.record()], self.root)
        self.assertEqual(result['selected_cases'], 1); self.assertEqual(result['human_accepted_cases'], 0)
        self.assertEqual(result['first_pass_selection_rate'], 1)
        self.assertEqual(result['seconds_per_selected_case'], 12)
        self.assertAlmostEqual(result['planned_case_coverage'], 1 / 12)

    def test_missing_measurement_is_not_zero(self):
        rec = self.record(); rec['elapsed_seconds'] = None
        result = c.summarize(self.plan, [rec], self.root)
        self.assertIsNone(result['total_elapsed_seconds']); self.assertIsNone(result['seconds_per_selected_case'])

    def test_invalid_measurements(self):
        for value in (True, -1, float('inf'), float('nan')):
            rec = self.record(); rec['elapsed_seconds'] = value
            with self.assertRaises(ValueError): c.summarize(self.plan, [rec], self.root)

    def test_hard_requirements_are_not_averaged(self):
        for value in ('fail', 'uncertain', 'not_visible'):
            rec = self.record(); rec['review']['checks'][self.case['required_checks'][0]] = value
            with self.assertRaisesRegex(ValueError, 'hard requirement'): c.summarize(self.plan, [rec], self.root)

    def test_agent_cannot_claim_human_acceptance(self):
        with self.assertRaisesRegex(ValueError, 'human acceptance'):
            c.summarize(self.plan, [self.record(decision='accepted')], self.root)
        result = c.summarize(self.plan, [self.record(decision='accepted', who='human')], self.root)
        self.assertEqual(result['human_accepted_cases'], 1)

    def test_stale_output_review_and_tampered_evidence(self):
        rec = self.record(); rec['review']['output_sha256'] = '0' * 64
        with self.assertRaises(ValueError): c.summarize(self.plan, [rec], self.root)
        rec = self.record(); (self.root / rec['execution_evidence']['path']).write_text('changed')
        with self.assertRaises(ValueError): c.summarize(self.plan, [rec], self.root)

    def test_duplicate_primary_and_wrong_plan_rejected(self):
        rec = self.record(); other = self.record(2)
        with self.assertRaises(ValueError): c.summarize(self.plan, [rec, other], self.root)
        rec['plan_sha256'] = '0' * 64
        with self.assertRaises(ValueError): c.summarize(self.plan, [rec], self.root)

    def test_uncertain_attempt_consumes_budget_and_blocks_retry(self):
        rec = self.record(state='submission_uncertain')
        result = c.summarize(self.plan, [rec], self.root)
        self.assertEqual(result['attempts_used'], 1)
        self.assertEqual(result['unresolved_submission_case_ids'], [self.case['id']])
        with self.assertRaisesRegex(ValueError, 'reconciled'):
            c.summarize(self.plan, [rec, self.record(2)], self.root)

    def test_warmups_and_failures_are_counted(self):
        rec = self.record(kind='warmup', state='failed')
        result = c.summarize(self.plan, [rec], self.root)
        self.assertEqual(result['attempts_used'], 1); self.assertEqual(result['selected_cases'], 0)
        records = [self.record(i, kind='warmup', state='failed') for i in range(1, 14)]
        with self.assertRaisesRegex(ValueError, 'Plan-wide'): c.summarize(self.plan, records, self.root)

    def test_repair_requires_parent_and_its_own_allowance(self):
        original = self.record(decision='rejected'); repair = self.record(2, kind='repair', parent=original['id'])
        with self.assertRaisesRegex(ValueError, 'repair allowance'): c.summarize(self.plan, [original, repair], self.root)
        req = copy.deepcopy(self.request); req['budget']['max_repairs_per_case'] = 1
        self.plan = c.make_plan(self.canon, req); self.case = self.plan['cases'][0]
        original = self.record(decision='rejected'); repair = self.record(2, kind='repair', parent=original['id'])
        result = c.summarize(self.plan, [original, repair], self.root)
        self.assertEqual(result['first_pass_selection_rate'], 0); self.assertEqual(result['selected_cases'], 1)
        self.assertEqual(result['attempts_used'], 2)
        with self.assertRaisesRegex(ValueError, 'parent'): c.summarize(self.plan, [repair], self.root)

    def test_case_brief_uses_existing_contract_and_role_order(self):
        brief = c.case_brief(self.plan, self.case['id'])
        self.assertEqual(brief['route'], 'reference-image')
        self.assertEqual([r['id'] for r in brief['references']], self.case['reference_ids'])
        self.assertEqual(brief['references'][0]['kind'], 'image')
        self.assertIn(self.plan['plan_sha256'], brief['constraints'][-1])

    def scoped_plan(self):
        return c.make_plan(self.canon, c.read_json(DATA / 'portrait-prompt-scope.study.json'))

    def test_v2_scoped_prompt_selects_canon_without_replacing_or_weakening_it(self):
        plan = self.scoped_plan()
        full = next(case for case in plan['cases'] if case['task_id'] == 'wink-full-context')
        scoped = next(case for case in plan['cases'] if case['task_id'] == 'wink-portrait-context')
        full_brief = c.case_brief(plan, full['id']); brief = c.case_brief(plan, scoped['id'])
        self.assertEqual(plan['schema_version'], 2); self.assertEqual(brief['schema_version'], 1)
        self.assertEqual(plan['canon'], self.canon)
        self.assertIn('White upper-leg stockings and navy boots with gold top trim', full_brief['description'])
        self.assertIn('Full-figure illustration', full_brief['description'])
        self.assertIn('Retain the accepted face geometry', brief['description'])
        self.assertIn('Navy fitted sleeveless bodice, pale trim and green throat bow', brief['description'])
        self.assertIn('Clean anime contours and cel-like shading.', brief['description'])
        self.assertNotIn('navy boots', brief['description'])
        self.assertNotIn('Full-figure illustration', brief['description'])
        self.assertEqual(brief['constraints'], [self.canon['checks'][key] for key in scoped['required_checks']] + [
            'One panel only; no lettering. Return to the approved canon, not an unreviewed derivative.',
            'Budget belongs to study ' + plan['plan_sha256'] + '; do not multiply it by the number of case briefs.'])

    def test_v2_unscoped_prompt_text_matches_v1_and_scope_order_is_canonical(self):
        request = copy.deepcopy(self.request); request['schema_version'] = 2
        v2 = c.make_plan(self.canon, request)
        v1_case = next(case for case in self.plan['cases'] if case['route_id'] == 'klein-current' and case['task_id'] == 'wink' and case['seed'] == 12001)
        v2_case = next(case for case in v2['cases'] if case['route_id'] == 'klein-current' and case['task_id'] == 'wink' and case['seed'] == 12001)
        self.assertEqual(c.case_brief(self.plan, v1_case['id'])['description'], c.case_brief(v2, v2_case['id'])['description'])
        request['tasks'][0]['prompt_scope'] = {
            'style': {'description': True, 'invariant_indexes': [0]},
            'costume': {'description': False, 'invariant_indexes': [3, 1, 0]},
            'identity': {'description': False, 'invariant_indexes': [3, 1, 0, 2]}}
        scoped = c.make_plan(self.canon, request); brief = c.case_brief(scoped, scoped['cases'][0]['id'])
        for earlier, later in [('Light-blue long hair', 'Blue eyes'), ('Blue eyes', 'Dark-blue spherical'),
                               ('Dark-blue spherical', 'Retain the accepted face'),
                               ('Retain the accepted face', 'Navy fitted sleeveless')]:
            self.assertLess(brief['description'].index(earlier), brief['description'].index(later))

    def test_v2_scope_rejects_malformed_selection_and_does_not_alias_inputs(self):
        request = c.read_json(DATA / 'portrait-prompt-scope.study.json')
        bad_scopes = [
            {'unknown': {'description': True, 'invariant_indexes': []}},
            {'identity': {'description': True, 'invariant_indexes': [], 'extra': True}},
            {'identity': {'description': True, 'invariant_indexes': [True]}},
            {'identity': {'description': False, 'invariant_indexes': [0, 0]}},
            {'identity': {'description': False, 'invariant_indexes': [4]}},
            {'identity': {'description': False, 'invariant_indexes': '0'}},
            {'identity': {'description': 1, 'invariant_indexes': [0]}},
            {'identity': {'description': False, 'invariant_indexes': []}},
        ]
        for scope in bad_scopes:
            altered = copy.deepcopy(request); altered['tasks'][1]['prompt_scope'] = scope
            with self.subTest(scope=scope), self.assertRaises(ValueError): c.make_plan(self.canon, altered)
        v1 = copy.deepcopy(self.request); v1['tasks'][0]['prompt_scope'] = request['tasks'][1]['prompt_scope']
        with self.assertRaises(ValueError): c.make_plan(self.canon, v1)
        for version in (True, 1.0, 3):
            altered = copy.deepcopy(request); altered['schema_version'] = version
            with self.subTest(version=version), self.assertRaises(ValueError): c.make_plan(self.canon, altered)
        plan = c.make_plan(self.canon, request)
        request['tasks'][1]['prompt_scope']['identity']['invariant_indexes'].append(0)
        self.assertEqual(plan['cases'][1]['prompt_scope']['identity']['invariant_indexes'], [0, 1, 2, 3])
        c.check_plan(plan)

    def test_v2_scope_and_rehashed_audit_forgery_are_rejected(self):
        plan = self.scoped_plan(); case = next(item for item in plan['cases'] if item['task_id'] == 'wink-portrait-context')
        changed_request = c.read_json(DATA / 'portrait-prompt-scope.study.json')
        changed_request['tasks'][1]['prompt_scope']['costume']['invariant_indexes'] = [1]
        changed_scope_plan = c.make_plan(self.canon, changed_request)
        self.assertNotEqual(plan['plan_sha256'], changed_scope_plan['plan_sha256'])
        self.assertNotEqual(case['id'], changed_scope_plan['cases'][1]['id'])
        changed = copy.deepcopy(plan); changed['cases'][1]['prompt_scope']['style']['description'] = False
        changed['plan_sha256'] = c.sha({key: value for key, value in changed.items() if key != 'plan_sha256'})
        with self.assertRaises(ValueError): c.check_plan(changed)
        (self.root / 'presets').mkdir(exist_ok=True); (self.root / 'workflows/api').mkdir(parents=True, exist_ok=True)
        c.write_json(self.root / 'workflows/api/test.json', {'1': {'class_type': 'Fixture', 'inputs': {'text': '', 'seed': 1, 'image': ''}}})
        c.write_json(self.root / 'presets/catalog.json', {'presets': [{'id': case['preset_id'], 'graph': 'workflows/api/test.json',
                     'positive': ['1', 'text'], 'seed': ['1', 'seed'], 'reference': ['1', 'image']}]})
        handoff = c.prepare_handoff(plan, case['id'], self.root, self.root)
        self.assertEqual(handoff['prompt_context']['mode'], 'selected-canon')
        self.assertIsNone(handoff['prompt_context']['sections']['identity']['description'])
        self.assertEqual(handoff['prompt_context']['sections']['costume']['invariants'], [{
            'index': 0, 'text': self.canon['costume']['invariants'][0]}])
        self.assertNotIn('representation', handoff['prompt_context']['sections'])
        full_case = next(item for item in plan['cases'] if item['task_id'] == 'wink-full-context')
        full_handoff = c.prepare_handoff(plan, full_case['id'], self.root, self.root)
        self.assertEqual(full_handoff['prompt_context']['mode'], 'all-canon')
        self.assertEqual(full_handoff['prompt_context']['sections']['representation']['description'], self.canon['representation']['description'])
        forged = copy.deepcopy(handoff); forged['prompt_context']['sections']['costume']['invariants'][0]['text'] = 'forged'
        forged['handoff_sha256'] = c.sha({key: value for key, value in forged.items() if key != 'handoff_sha256'})
        with self.assertRaisesRegex(ValueError, 'Handoff differs'): c.check_handoff(plan, forged, self.root)

    def fake_repo(self):
        (self.root / 'presets').mkdir(exist_ok=True)
        (self.root / 'workflows/api').mkdir(parents=True, exist_ok=True)
        graph = {'1': {'class_type': 'Fixture', 'inputs': {'text': 'original', 'seed': 1, 'image': 'placeholder.png'}}}
        c.write_json(self.root / 'workflows/api/test.json', graph)
        preset = {'id': self.case['preset_id'], 'graph': 'workflows/api/test.json',
                  'positive': ['1', 'text'], 'seed': ['1', 'seed'], 'reference': ['1', 'image']}
        c.write_json(self.root / 'presets/catalog.json', {'presets': [preset]})
        return preset

    def test_handoff_pins_template_without_armed_payload(self):
        self.fake_repo(); before = c.file_sha(self.root / 'workflows/api/test.json')
        handoff = c.prepare_handoff(self.plan, self.case['id'], self.root, self.root)
        self.assertEqual(handoff['template_sha256'], before)
        self.assertEqual(c.file_sha(self.root / 'workflows/api/test.json'), before)
        self.assertFalse(handoff['submits_generation']); self.assertIsNone(handoff['submission_payload'])
        self.assertEqual(set(handoff['proposed_controls']), {'positive', 'seed'})
        self.assertEqual(len(handoff['upload_requirements']), 1)

    def test_handoff_rejects_wrong_reference_count_and_stale_binding(self):
        preset = self.fake_repo()
        for change in ({'reference_slots': [{'binding': ['1', 'image']}] * 2}, {'positive': ['1', 'missing']}):
            updated = {**preset, **change}
            (self.root / 'presets/catalog.json').write_text(json.dumps({'presets': [updated]}))
            with self.assertRaises(ValueError): c.prepare_handoff(self.plan, self.case['id'], self.root, self.root)


if __name__ == '__main__': unittest.main()
