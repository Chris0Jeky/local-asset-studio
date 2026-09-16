"""Report retention and CLI diagnostics for paired resource observations."""
import copy
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
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
        with patch.object(comparison, 'MAX_REPORT_BYTES', (full_size + compact_size) // 2):
            result = comparison._fit_report(copy.deepcopy(original))
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
        self.assertLessEqual(len(comparison.encode_report(result)), comparison.MAX_REPORT_BYTES)

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

    def load_cli(self):
        path = ROOT / 'scripts/compare-resource-observations.py'
        spec = importlib.util.spec_from_file_location('comparison_cli_reporting_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_cli_preserves_incomplete_and_report_size_diagnostics(self):
        cli = self.load_cli()
        cases = [
            (comparison.EvidenceError('artifact_missing', incomplete=True), 'incomplete'),
            (comparison.EvidenceError('plan_invalid'), 'invalid_plan'),
            (comparison.EvidenceError('report_too_large'), 'report_unavailable'),
        ]
        for error, state in cases:
            with self.subTest(state=state), patch.object(cli, 'compare_observations', side_effect=error):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = cli.main(['missing-plan.json'])
                self.assertEqual(code, 2)
                value = json.loads(output.getvalue())
                self.assertEqual(value['state'], state)
                self.assertEqual(value['reason'], error.code)
                self.assertFalse(value['qualified_benchmark'])
                self.assertFalse(value['execution_authority'])


if __name__ == '__main__':
    unittest.main()
