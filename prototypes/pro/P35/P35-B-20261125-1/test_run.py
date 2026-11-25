"""Behavioral checks for the public offline/owner entry point."""
import copy
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import plan
import qualification
from test_plan import fixture_owner
from test_qualification import receipt as fixture_receipt

try:
    import run as entry
except ModuleNotFoundError:
    entry = None

HERE = Path(__file__).resolve().parent


class EntryPointTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(entry, 'Public entry point is not implemented')
        self.suite = plan.read_json(HERE / 'suite.json')
        self.bundle = plan.read_json(HERE / 'routes.json')

    def compiled(self):
        return plan.compile_plan(self.suite, self.bundle, fixture_owner(self.suite))

    def reseal(self, value):
        if value.get('owner_run') is not None:
            inner = value['owner_run']
            inner['plan_id'] = plan.stable_hash({key: item for key, item in inner.items() if key != 'plan_id'})
        value['plan_sha256'] = plan.stable_hash({key: item for key, item in value.items() if key != 'plan_sha256'})
        return value

    def rematerialize(self, value):
        for chunk in value['owner_run']['chunks']:
            route = next(route for route in self.bundle['routes'] if route['id'] == chunk['route_id'])
            chunk['expected_graph_sha256'] = [plan.studio_hash(plan.materialize_graph(
                route, plan.read_json(HERE / route['graph']), chunk['payload']['recipe'], variant['controls']['seed']))
                for variant in chunk['payload']['variants']]
        return self.reseal(value)

    def test_missing_owner_start_creates_no_network_authority(self):
        with tempfile.TemporaryDirectory() as td, mock.patch('http.client.HTTPConnection') as http:
            missing = Path(td) / 'does-not-exist.json'
            self.assertEqual(entry.main(['owner-start', '--owner', str(missing), '--prospective']), 2)
            http.assert_not_called()

    def test_offline_summary_keeps_full_denominator_and_all_gates_disabled(self):
        result = entry.offline_evidence(HERE)
        self.assertEqual(result['qualification-summary.json']['planned'], 240)
        self.assertEqual(result['qualification-summary.json']['status_counts']['missing'], 240)
        self.assertFalse(result['qualification-summary.json']['qualification_complete'])
        self.assertFalse(result['route-summary.json']['image_generation_submitted'])
        demo = result['calibration-demo.json']['examples']
        self.assertEqual(demo['synthetic_inverted']['disagreements'], 4)
        self.assertEqual(demo['synthetic_perfect']['agreement'], 1.0)
        self.assertIsNone(demo['owner_labels_unavailable']['agreement'])
        self.assertTrue(all(not value['gating_enabled'] for value in demo.values()))

    def test_frontier_recipes_remain_excluded_from_current_runs(self):
        result = entry.frontier_report(HERE)
        self.assertEqual(len(result['recipes']), 2)
        self.assertFalse(result['runtime_admitted'])
        self.assertTrue(all(row['graph_nodes'] > 0 for row in result['recipes']))
        changed = plan.read_json(HERE / 'frontier-recipes.json')
        changed['runtime_admitted'] = True
        with mock.patch.object(plan, 'read_json', return_value=changed), self.assertRaises(ValueError):
            entry.frontier_report(HERE)

    def test_plan_hash_and_suite_lineage_are_rechecked(self):
        result = self.compiled()
        self.assertEqual(entry.validate_compiled(result)['campaign_id'], result['campaign_id'])
        result['selected_slots'] -= 1
        with self.assertRaisesRegex(ValueError, 'hash'):
            entry.validate_compiled(result)

    def test_rehashed_ledger_case_cannot_score_another_cases_graph(self):
        value = self.compiled()
        original = copy.deepcopy(value['trial_ledger'][0])
        value['trial_ledger'][0]['case_id'] = 'foreshortened-arm'
        self.reseal(value)
        pins = entry.expected_execution(value)[(original['route_id'], 'foreshortened-arm', original['seed'])]
        receipt = fixture_receipt(original)
        receipt['lineage']['route_inputs_sha256'] = original['route_inputs_sha256']
        receipt['lineage'].update({key: pins[key] for key in ('graph_sha256', 'model_set_sha256', 'settings_sha256')})
        with self.assertRaisesRegex(ValueError, 'ledger|immutable'):
            entry.score_receipts(value, [receipt], None)

    def test_foreign_owner_run_is_not_accepted_as_another_frozen_suite(self):
        value = self.compiled()
        owner = fixture_owner(self.suite)
        owner['reference_bindings']['canon-a'].update(file='f' * 32 + '_different.png', sha256='b' * 64)
        foreign = plan.compile_plan(self.suite, self.bundle, owner)
        value['owner_run'] = foreign['owner_run']
        self.reseal(value)
        with self.assertRaisesRegex(ValueError, 'campaign'):
            entry.validate_compiled(value)
        value['owner_run']['campaign_id'] = value['campaign_id']
        for chunk in value['owner_run']['chunks']:
            chunk['name'] = f"P35 {value['campaign_id'][:16]} {chunk['id']}"
            chunk['payload']['name'] = chunk['name']
        self.reseal(value)
        with self.assertRaisesRegex(ValueError, 'input|source|reference'):
            entry.validate_compiled(value)

    def test_missing_or_duplicate_chunks_cannot_change_the_selected_denominator(self):
        for mutation in ('missing', 'duplicate'):
            with self.subTest(mutation=mutation):
                value = self.compiled()
                if mutation == 'missing':
                    value['owner_run']['chunks'].pop()
                else:
                    duplicate = copy.deepcopy(value['owner_run']['chunks'][0])
                    duplicate['id'] = 'copied-chunk'
                    duplicate['name'] = f"P35 {value['campaign_id'][:16]} copied-chunk"
                    duplicate['payload']['name'] = duplicate['name']
                    value['owner_run']['chunks'][1] = duplicate
                self.reseal(value)
                with self.assertRaisesRegex(ValueError, 'chunk|selection'):
                    entry.validate_compiled(value)

    def test_rehashed_route_pin_must_match_the_frozen_bundle(self):
        value = self.compiled()
        selected = {(trial['route_id'], trial['case_id'], trial['seed']) for trial in value['trial_ledger']}
        value['bound_suite']['route_pins']['klein4-reference'] = '0' * 64
        frozen = qualification.validate_suite(value['bound_suite'])
        value['suite_sha256'] = frozen['suite_sha256']
        value['trial_ledger'] = [{**trial, 'status': 'planned', 'output_claim': 'planned'} for trial in frozen['trials']
                                 if (trial['route_id'], trial['case_id'], trial['seed']) in selected]
        self.reseal(value)
        with self.assertRaisesRegex(ValueError, 'route'):
            entry.validate_compiled(value)

    def test_self_consistent_model_graph_or_predictable_control_changes_refuse(self):
        for mutation in ('model', 'graph', 'control'):
            with self.subTest(mutation=mutation):
                value = self.compiled()
                chunk = value['owner_run']['chunks'][0]
                if mutation == 'model':
                    chunk['expected_models'][0]['sha256'] = '0' * 64
                    self.reseal(value)
                elif mutation == 'graph':
                    chunk['expected_graph_sha256'][0] = '0' * 64
                    self.reseal(value)
                else:
                    chunk['payload']['recipe']['controls']['cfg'] = 3.0
                    self.rematerialize(value)
                with self.assertRaises(ValueError):
                    entry.validate_compiled(value)

    def test_native_reference_order_and_roles_are_not_caller_reassignable(self):
        for mutation in ('order', 'role'):
            with self.subTest(mutation=mutation):
                value = plan.compile_plan(self.suite, self.bundle, fixture_owner(self.suite),
                                           route_ids=['qwen-3ref'], case_ids=['ordinary-neutral'], allow_heavy=True)
                references = value['owner_run']['chunks'][0]['payload']['recipe']['references']
                if mutation == 'order':
                    references[0], references[1] = references[1], references[0]
                else:
                    references[0]['role'] = 'style'
                self.rematerialize(value)
                with self.assertRaisesRegex(ValueError, 'reference|recipe'):
                    entry.validate_compiled(value)

    def test_declared_prompt_is_bound_without_claiming_semantic_authentication(self):
        value = self.compiled()
        value['owner_run']['chunks'][0]['payload']['recipe']['controls']['positive'] = 'A deliberately declared revised prompt.'
        self.rematerialize(value)
        self.assertIs(entry.validate_compiled(value), value)

    def test_native_compiler_plans_remain_valid_for_every_current_route(self):
        for route_id, case_id in [(route['id'], 'ordinary-neutral') for route in self.bundle['routes']] + [('qwen-3ref', 'ordinary-reach')]:
            with self.subTest(route_id=route_id, case_id=case_id):
                value = plan.compile_plan(self.suite, self.bundle, fixture_owner(self.suite),
                                           route_ids=[route_id], case_ids=[case_id], allow_heavy=True, prospective=True)
                self.assertTrue(value['ready'], value['blockers'])
                self.assertIs(entry.validate_compiled(value), value)

    def test_review_template_never_invents_execution_or_human_scores(self):
        result = self.compiled()
        template = entry.review_template(result)
        self.assertEqual(len(template['rows']), 12)
        for row in template['rows']:
            receipt = row['receipt']
            self.assertIsNone(receipt['status'])
            self.assertIsNone(receipt['output_sha256'])
            self.assertIsNone(receipt['review'])
            self.assertTrue(all(value is None for value in receipt['cost'].values()))
            self.assertTrue(all(value is None for scores in row['review_fields']['scores'].values() for value in scores.values()))
            self.assertIn('graph_sha256', row['expected_execution'])
            self.assertIsNone(receipt['lineage']['graph_sha256'])

    def test_completed_receipt_graph_mismatch_cannot_be_scored(self):
        result = self.compiled()
        row = entry.review_template(result)['rows'][0]
        receipt = row['receipt']
        receipt.update(status='completed', output_sha256='a' * 64, reason='Synthetic test fixture')
        receipt['lineage']['graph_sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'graph'):
            entry.score_receipts(result, [receipt], None)

    def test_empty_receipts_remain_unqualified(self):
        result = entry.score_receipts(self.compiled(), [], None)
        self.assertEqual(result['planned'], 240)
        self.assertFalse(result['qualification_complete'])
        self.assertIsNone(result['owner_acceptance'])
        self.assertIsNone(result['licence_clearance'])

    def test_generated_outputs_refuse_to_escape_runtime_and_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / '.runtime' / 'receipt.json'
            plan.runtime_write(target, {'x': 1}, root)
            plan.runtime_write(target, {'x': 1}, root)
            with self.assertRaisesRegex(ValueError, 'Different output'):
                plan.runtime_write(target, {'x': 2}, root)
            with self.assertRaisesRegex(ValueError, '.runtime'):
                plan.runtime_write(root / 'outside.json', {'x': 1}, root)

    def test_hash_manifest_detects_changed_golden_and_regenerated_output(self):
        with tempfile.TemporaryDirectory() as td:
            package = Path(td)
            (package / 'evidence').mkdir()
            data = {'example.json': {'measured': None}}
            raw = entry.json_bytes(data['example.json'])
            (package / 'evidence/example.json').write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            (package / 'HASHES.sha256').write_text(digest + '  ' + entry.PACKAGE_REL + '/evidence/example.json\n', encoding='utf-8')
            self.assertEqual(entry.check_hashes(package, data), {'checked': 1, 'matches': True})
            with self.assertRaisesRegex(ValueError, 'regenerated'):
                entry.check_hashes(package, {'example.json': {'measured': 1}})
            (package / 'evidence/example.json').write_bytes(raw + b'\n')
            with self.assertRaisesRegex(ValueError, 'committed'):
                entry.check_hashes(package, data)

    def verification_fixture(self, phase=None, fail_test=True):
        marker = 'Retain this synthetic failing test marker'
        prior_bytecode_setting = os.environ.get('PYTHONDONTWRITEBYTECODE')
        class DeliberateFailure(unittest.TestCase):
            def runTest(self):
                if fail_test:
                    self.fail(marker)
        with tempfile.TemporaryDirectory() as td, contextlib.ExitStack() as stack:
            root = Path(td)
            stack.enter_context(mock.patch.object(entry, 'ROOT', root))
            stack.enter_context(mock.patch.object(entry, 'RUNTIME', root / '.runtime' / 'verification'))
            stack.enter_context(mock.patch.object(entry.unittest.defaultTestLoader, 'discover', return_value=unittest.TestSuite([DeliberateFailure()])))
            def offline_output(_package):
                self.assertEqual(os.environ.get('PYTHONDONTWRITEBYTECODE'), '1')
                if phase == 'evidence':
                    raise ValueError('Synthetic evidence failure')
                return {'fixture.json': {'synthetic': True}}
            stack.enter_context(mock.patch.object(entry, 'offline_evidence', side_effect=offline_output))
            stack.enter_context(mock.patch('source_contract_check.check_contract', **(
                {'side_effect': ValueError('Synthetic source failure')} if phase == 'source'
                else {'return_value': {'graph_comparisons': 8}})))
            stack.enter_context(mock.patch.object(entry, 'check_hashes', **(
                {'side_effect': ValueError('Synthetic hash failure')} if phase == 'hashes'
                else {'return_value': {'checked': 2, 'matches': True}})))
            if phase == 'output':
                original_write = plan.runtime_write
                def failed_output(path, value, repo_root):
                    if 'deterministic' in Path(path).parts:
                        raise OSError('Synthetic deterministic output failure')
                    return original_write(path, value, repo_root)
                stack.enter_context(mock.patch.object(plan, 'runtime_write', side_effect=failed_output))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            code = entry.main(['verify', '--source-root', str(root)])
            self.assertEqual(os.environ.get('PYTHONDONTWRITEBYTECODE'), prior_bytecode_setting)
            receipts = []
            for path in root.rglob('*.json'):
                value = json.loads(path.read_text())
                if value.get('schema') == 'p35.software-verification/v1':
                    receipts.append(value)
            self.assertEqual(len(receipts), 1)
            if fail_test:
                self.assertIn(marker, receipts[0]['test_log'])
            return code, receipts[0]

    def test_verify_retains_failed_test_log_when_a_later_phase_fails(self):
        for phase in ('evidence', 'source', 'hashes', 'output'):
            with self.subTest(phase=phase):
                code, receipt = self.verification_fixture(phase)
                self.assertEqual(code, 2)
                self.assertFalse(receipt['passed'])
                self.assertEqual(receipt['failures'], 1)
                self.assertIsNotNone(receipt['verification_error'])

    def test_verify_test_failure_returns_one_and_retains_log(self):
        code, receipt = self.verification_fixture()
        self.assertEqual(code, 1)
        self.assertFalse(receipt['passed'])
        self.assertEqual(receipt['failures'], 1)

    def test_verify_success_requires_all_phases_to_succeed(self):
        code, receipt = self.verification_fixture(fail_test=False)
        self.assertEqual(code, 0)
        self.assertTrue(receipt['passed'])


if __name__ == '__main__':
    unittest.main()
