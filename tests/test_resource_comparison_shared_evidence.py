import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'app'), str(ROOT)]
import resource_comparison as comparison


def trial(directory, job_id, marker):
    return {
        'directory': str(directory),
        'result_sha256': marker * 64,
        'job_id': job_id,
    }


def observation(prompt_marker):
    metric = {'sampled_min': 100, 'sampled_max': 120}
    return {
        'profile_summary': {
            'sampling': {'observed': 1, 'interval_seconds_after_completion': 1},
            'source': {'sampler_sha256': 'f' * 64},
            'metrics': {'commit_headroom_bytes': copy.deepcopy(metric)},
            'comfy': {'versions': {}, 'devices': []},
        },
        'runtime_observation': {'lost': False, 'profile_sha256': 'e' * 64},
        'source_observation': {'commit_at_capture': 'd' * 40},
        'submissions': [{
            'index': 0,
            'graph_sha256': 'c' * 64,
            'controls_sha256': 'b' * 64,
            'reference_manifest_sha256': 'a' * 64,
            'response': 'received',
            'prompt_id_sha256': prompt_marker * 64,
        }],
        'warnings': [],
        'finish_snapshot': {'status': 'completed', 'elapsed_seconds': 1.0},
    }


class SharedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plan_path = self.root / 'plan.json'
        self.base = trial(self.root / 'base', 'base', '1')
        self.one = trial(self.root / 'one', 'candidate-one', '2')
        self.two = trial(self.root / 'two', 'candidate-two', '3')

    def plan(self):
        return {
            'schema': comparison.PLAN_SCHEMA,
            'generation_allowance': 0,
            'pairs': [
                {'id': 'one', 'condition': 'unspecified',
                 'baseline': copy.deepcopy(self.base), 'candidate': copy.deepcopy(self.one)},
                {'id': 'two', 'condition': 'unspecified',
                 'baseline': copy.deepcopy(self.base), 'candidate': copy.deepcopy(self.two)},
            ],
        }

    def compare(self, plan, prompts=None):
        prompts = prompts or {'base': '4', 'candidate-one': '5', 'candidate-two': '6'}
        self.plan_path.write_text(json.dumps(plan), encoding='utf-8')
        calls = []
        original = comparison.inspect_observation

        def inspect(directory, *, expected_job_id, expected_result_sha256):
            calls.append((str(directory), expected_job_id, expected_result_sha256))
            return observation(prompts[expected_job_id])
        comparison.inspect_observation = inspect
        try:
            return comparison.compare_observations(self.plan_path), calls
        finally:
            comparison.inspect_observation = original

    def test_exact_shared_baseline_is_inspected_once_and_retained_per_pair(self):
        report, calls = self.compare(self.plan())
        self.assertEqual([call[1] for call in calls], ['base', 'candidate-one', 'candidate-two'])
        self.assertEqual(report['counts']['requested_observations'], 4)
        self.assertEqual(report['counts']['unique_observations'], 3)
        self.assertEqual(report['counts']['verified_observations'], 4)
        self.assertEqual(report['counts']['descriptive_pairs'], 2)
        self.assertTrue(report['evidence_complete'])
        for pair in report['pairs']:
            self.assertEqual(pair['baseline']['state'], 'verified')
            self.assertNotIn('reused_prompt_evidence', pair['baseline']['reasons'])

    def test_conflicting_component_reuse_is_still_refused_before_inspection(self):
        cases = []
        changed_job = self.plan(); changed_job['pairs'][1]['baseline']['result_sha256'] = '9' * 64
        cases.append(changed_job)
        changed_pin = self.plan(); changed_pin['pairs'][1]['baseline']['job_id'] = 'other-base'
        cases.append(changed_pin)
        changed_path = self.plan(); changed_path['pairs'][1]['baseline']['directory'] = str(self.root / 'elsewhere')
        cases.append(changed_path)
        for plan in cases:
            with self.subTest(plan=plan):
                self.plan_path.write_text(json.dumps(plan), encoding='utf-8')
                original = comparison.inspect_observation
                comparison.inspect_observation = lambda *args, **kwargs: self.fail('evidence read before validation')
                try:
                    with self.assertRaises(comparison.EvidenceError) as caught:
                        comparison.compare_observations(self.plan_path)
                    self.assertEqual(caught.exception.code, 'duplicate_trial_evidence')
                finally:
                    comparison.inspect_observation = original

    def test_operator_doc_allows_exact_shared_triples(self):
        text = (ROOT / 'docs/performance/PAIRED-OBSERVATIONS.md').read_text(encoding='utf-8')
        self.assertNotIn(
            'Pair IDs, job IDs, result pins and normalized directory identities must', text)
        self.assertIn('Exact `(job_id, result_sha256, directory)`', text)
        self.assertIn('inspected once', text)
        self.assertIn('duplicate_trial_evidence', text)
        report, calls = self.compare(self.plan())
        self.assertEqual(len(calls), 3, 'shared baseline is inspected once, not twice')
        self.assertEqual(report['counts']['unique_observations'], 3)
        self.assertEqual(report['counts']['verified_observations'], 4)

    def test_distinct_prompt_reuse_invalidates_all_occurrences_but_not_shared_baseline(self):
        report, calls = self.compare(self.plan(), prompts={
            'base': '4', 'candidate-one': '7', 'candidate-two': '7',
        })
        self.assertEqual(len(calls), 3)
        for pair in report['pairs']:
            self.assertEqual(pair['baseline']['state'], 'verified')
            self.assertEqual(pair['candidate']['state'], 'invalid')
            self.assertIsNone(pair['candidate']['observation'])
            self.assertIn('reused_prompt_evidence', pair['candidate']['reasons'])
        self.assertEqual(report['counts']['verified_observations'], 2)
        self.assertEqual(report['counts']['invalid_observations'], 2)


if __name__ == '__main__':
    unittest.main()
