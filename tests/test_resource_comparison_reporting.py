"""Report retention and CLI diagnostics for paired resource observations."""
import copy
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'app'), str(ROOT)]
import resource_comparison as comparison


def row(job, payload):
    return {
        'expected_job_id': job,
        'expected_result_sha256': job[0] * 64,
        'state': 'verified',
        'reasons': [],
        'observation': {'payload': payload},
    }


def report(payload='x' * 4096):
    return {
        'schema': comparison.SCHEMA,
        'manifest_sha256': 'f' * 64,
        'counts': {
            'requested_pairs': 1,
            'requested_observations': 2,
            'verified_observations': 2,
            'invalid_observations': 0,
            'incomplete_observations': 0,
            'descriptive_pairs': 1,
            'withheld_pairs': 0,
        },
        'pairs': [{
            'id': 'pair-1',
            'declared_condition': 'unspecified',
            'condition_verified': False,
            'qualified_benchmark': False,
            'baseline': row('base', payload),
            'candidate': row('candidate', payload),
            'comparison': {
                'state': 'descriptive',
                'blockers': [],
                'warnings': [],
                'observed_differences': [],
                'host_metrics': {'bulk': payload},
                'devices': [{'bulk': payload}],
                'coordinator_elapsed_delta_seconds': -2,
            },
        }],
        'evidence_complete': True,
        'qualified_benchmark': False,
        'execution_authority': False,
        'generation_allowance_added': 0,
        'report_compacted': False,
        'limitations': ['original limitation'],
    }


class ReportingTests(unittest.TestCase):
    def test_report_encoder_matches_the_exact_cli_bytes(self):
        value = {'schema': comparison.SCHEMA, 'label': 'caf\u00e9'}
        self.assertEqual(
            comparison.encode_report(value),
            ('{"schema":"' + comparison.SCHEMA + '","label":"caf\\u00e9"}\n').encode('ascii'),
        )

    def test_oversize_report_compacts_but_retains_every_row_disposition(self):
        original = report()
        compact = comparison._compact_report(copy.deepcopy(original))
        full_size = len(comparison.encode_report(original))
        compact_size = len(comparison.encode_report(compact))
        self.assertLess(compact_size, full_size)
        bound = (full_size + compact_size) // 2
        with patch.object(comparison, 'MAX_REPORT_BYTES', bound):
            result = comparison._fit_report(copy.deepcopy(original))
            self.assertLessEqual(len(comparison.encode_report(result)), bound)
        self.assertTrue(result['report_compacted'])
        self.assertEqual(result['counts'], original['counts'])
        pair = result['pairs'][0]
        self.assertEqual(pair['id'], 'pair-1')
        for side in ('baseline', 'candidate'):
            self.assertEqual(pair[side]['state'], 'verified')
            self.assertIsNone(pair[side]['observation'])
        self.assertEqual(pair['comparison']['state'], 'descriptive')
        self.assertEqual(pair['comparison']['host_metrics'], {})
        self.assertEqual(pair['comparison']['devices'], [])
        self.assertIn('report_metrics_omitted', pair['comparison']['warnings'])

    def test_unrepresentable_compact_report_keeps_distinct_failure_reason(self):
        with patch.object(comparison, 'MAX_REPORT_BYTES', 1):
            with self.assertRaises(comparison.EvidenceError) as caught:
                comparison._fit_report(report('x'))
        self.assertEqual(caught.exception.code, 'report_too_large')

    def test_reused_prompt_invalidation_drops_the_no_longer_verified_payload(self):
        prompt = 'a' * 64
        left = row('base', 'private-left')
        right = row('candidate', 'private-right')
        left['observation'] = {'submissions': [{'prompt_id_sha256': prompt}]}
        right['observation'] = {'submissions': [{'prompt_id_sha256': prompt}]}
        pairs = [{'baseline': left, 'candidate': right}]
        comparison._reject_reused_prompts(pairs)
        for value in (left, right):
            self.assertEqual(value['state'], 'invalid')
            self.assertIn('reused_prompt_evidence', value['reasons'])
            self.assertIsNone(value['observation'])

    def test_reused_prompt_report_names_the_dropped_payload(self):
        metric = {'sampled_min': 100, 'sampled_max': 120}
        payload = {
            'profile_summary': {
                'sampling': {'observed': 1, 'interval_seconds_after_completion': 1},
                'source': {'sampler_sha256': 'f' * 64},
                'metrics': {'commit_headroom_bytes': copy.deepcopy(metric)},
                'comfy': {'versions': {}, 'devices': []},
            },
            'runtime_observation': {'lost': False, 'profile_sha256': 'e' * 64},
            'source_observation': {'commit_at_capture': 'd' * 40},
            'submissions': [{
                'index': 0, 'graph_sha256': 'c' * 64, 'controls_sha256': 'b' * 64,
                'reference_manifest_sha256': 'a' * 64, 'response': 'received',
                'prompt_id_sha256': '7' * 64,
            }],
            'warnings': [],
            'finish_snapshot': {'status': 'completed', 'elapsed_seconds': 1.0},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = {
                'schema': comparison.PLAN_SCHEMA,
                'generation_allowance': 0,
                'pairs': [
                    {'id': 'one', 'condition': 'unspecified',
                     'baseline': {'directory': str(root / 'a'), 'result_sha256': '1' * 64, 'job_id': 'base-a'},
                     'candidate': {'directory': str(root / 'b'), 'result_sha256': '2' * 64, 'job_id': 'cand-b'}},
                    {'id': 'two', 'condition': 'unspecified',
                     'baseline': {'directory': str(root / 'c'), 'result_sha256': '3' * 64, 'job_id': 'base-c'},
                     'candidate': {'directory': str(root / 'd'), 'result_sha256': '4' * 64, 'job_id': 'cand-d'}},
                ],
            }
            path = root / 'plan.json'
            path.write_text(json.dumps(plan), encoding='utf-8')
            original = comparison.inspect_observation
            comparison.inspect_observation = lambda *args, **kwargs: copy.deepcopy(payload)
            try:
                result = comparison.compare_observations(path)
            finally:
                comparison.inspect_observation = original
        for pair in result['pairs']:
            for side in ('baseline', 'candidate'):
                self.assertEqual(pair[side]['state'], 'invalid')
                self.assertIsNone(pair[side]['observation'])
                self.assertIn('reused_prompt_evidence', pair[side]['reasons'])
        self.assertTrue(any('reused_prompt_evidence' in line for line in result['limitations']))
        self.assertTrue(any('omitted' in line for line in result['limitations']))
        self.assertTrue(any('pair slot is retained' in line for line in result['limitations']))

    def load_cli(self):
        path = ROOT / 'scripts/compare-resource-observations.py'
        spec = importlib.util.spec_from_file_location('comparison_cli_reporting_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_cli_preserves_source_integrity_separately_from_report_disposition(self):
        cli = self.load_cli()
        cases = [
            (comparison.EvidenceError('artifact_missing', incomplete=True), 'report_unavailable', 'incomplete'),
            (comparison.EvidenceError('artifact_unreadable'), 'report_unavailable', 'invalid'),
            (comparison.EvidenceError('file_changed'), 'report_unavailable', 'invalid'),
            (comparison.EvidenceError('plan_invalid'), 'invalid_plan', 'invalid'),
            (comparison.EvidenceError('report_too_large'), 'report_unavailable', 'invalid'),
        ]
        for error, state, integrity in cases:
            with self.subTest(state=state, code=error.code), patch.object(cli, 'compare_observations', side_effect=error):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = cli.main(['missing-plan.json'])
                self.assertEqual(code, 2)
                value = json.loads(output.getvalue())
                self.assertEqual(value['state'], state)
                self.assertEqual(value['integrity'], integrity)
                self.assertEqual(value['reason'], error.code)
                self.assertFalse(value['qualified_benchmark'])
                self.assertFalse(value['execution_authority'])
                self.assertNotEqual(value['state'], 'incomplete')

    def test_real_cli_missing_plan_is_unavailable_readable_bad_plan_is_invalid(self):
        script = ROOT / 'scripts/compare-resource-observations.py'
        self.assertTrue(script.is_file(), 'Comparison CLI is absent')
        missing = Path(tempfile.mkdtemp()) / 'nope.json'
        absent = subprocess.run([sys.executable, str(script), str(missing)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(absent.returncode, 2, absent.stderr)
        missing_report = json.loads(absent.stdout)
        self.assertEqual(missing_report['state'], 'report_unavailable')
        self.assertEqual(missing_report['integrity'], 'incomplete')
        self.assertEqual(missing_report['reason'], 'artifact_missing')
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / 'plan.json'
            bad.write_text('{"schema":"nope","generation_allowance":0,"pairs":[]}', encoding='utf-8')
            invalid = subprocess.run([sys.executable, str(script), str(bad)],
                                     capture_output=True, text=True, timeout=10)
        self.assertEqual(invalid.returncode, 2, invalid.stderr)
        invalid_report = json.loads(invalid.stdout)
        self.assertEqual(invalid_report['state'], 'invalid_plan')
        self.assertEqual(invalid_report['integrity'], 'invalid')
        self.assertNotEqual(invalid_report['state'], missing_report['state'])


if __name__ == '__main__':
    unittest.main()
