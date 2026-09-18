"""Paired observations use the real recorder/inspector, not qualified GPU trials."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_resource_receipts as fixtures

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'app'), str(ROOT)]


def binding(path):
    return {'directory': str(path), 'result_sha256': hashlib.sha256((path / 'result.json').read_bytes()).hexdigest(),
            'job_id': fixtures.read(path / 'result.json')['job_id']}


def plan_for(a, b):
    return {'schema': 'studio.resource-comparison-plan/v1', 'generation_allowance': 0,
            'pairs': [{'id': 'pair-1', 'condition': 'unspecified', 'baseline': binding(a), 'candidate': binding(b)}]}


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('resource_comparison'), 'Paired observation consumer is absent')
        self.api = __import__('resource_comparison')
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.a = fixtures.make_observation(self.root, 'base', elapsed=10)
        self.b = fixtures.make_observation(self.root, 'candidate', elapsed=8)
        self.plan = plan_for(self.a, self.b)
        self.path = self.root / 'pairs.json'

    def compare(self):
        self.path.write_text(json.dumps(self.plan), encoding='utf-8')
        return self.api.compare_observations(self.path)

    def mutate_profile(self, path, change):
        raw = [json.loads(line) for line in (path / 'profile.jsonl').read_bytes().splitlines()]
        change(raw)
        data = b''.join(fixtures.producer.encoded(record) for record in raw)
        (path / 'profile.jsonl').write_bytes(data)
        fixtures.write(path / 'summary.json', fixtures.producer.summarize_resource_profile(io.BytesIO(data)))
        fixtures.rehash(path)
        self.plan['pairs'][0]['candidate'] = binding(path)

    def test_verified_pairs_report_descriptive_differences_and_no_speedup(self):
        self.mutate_profile(self.b, lambda rows: rows[1]['host_commit'].update(committed_bytes=120, available_bytes=80))
        before = {str(p): p.read_bytes() for d in (self.a, self.b) for p in d.iterdir()}
        result = self.compare(); pair = result['pairs'][0]
        self.assertEqual(result['schema'], 'studio.resource-comparison/v1')
        self.assertEqual(result['manifest_sha256'], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(result['counts']['verified_observations'], 2)
        self.assertEqual(pair['comparison']['state'], 'descriptive')
        self.assertEqual(pair['comparison']['host_metrics']['commit_headroom_bytes']['sampled_min_delta'], -20)
        self.assertEqual(pair['comparison']['coordinator_elapsed_delta_seconds'], -2)
        self.assertFalse(result['qualified_benchmark']); self.assertFalse(result['execution_authority'])
        self.assertFalse(pair['condition_verified'])
        self.assertNotIn('speedup', result); self.assertNotIn('mean', result)
        self.assertEqual(before, {str(p): p.read_bytes() for d in (self.a, self.b) for p in d.iterdir()})

    def test_all_invalid_missing_and_uncertain_rows_remain_counted(self):
        c = fixtures.make_observation(self.root, 'missing'); d = fixtures.make_observation(self.root, 'uncertain', status='uncertain')
        self.plan['pairs'].append({'id': 'pair-2', 'condition': 'warm_same_model', 'baseline': binding(c), 'candidate': binding(d)})
        (self.b / 'summary.json').write_bytes(b'{')
        (c / 'result.json').unlink()
        result = self.compare()
        self.assertEqual(len(result['pairs']), 2)
        self.assertEqual(result['counts']['invalid_observations'], 1)
        self.assertEqual(result['counts']['incomplete_observations'], 1)
        self.assertEqual(result['counts']['verified_observations'], 2)
        self.assertEqual(result['pairs'][1]['candidate']['observation']['finish_snapshot']['status'], 'uncertain')
        self.assertFalse(result['evidence_complete'])
        self.assertEqual(result['counts']['withheld_pairs'], 2)

    def test_uncertain_response_does_not_claim_elapsed_improvement(self):
        values = fixtures.events(self.b); values.pop(1); values[-1]['coordinator_exit_status'] = 'uncertain'
        fixtures.put_events(self.b, values); self.plan = plan_for(self.a, self.b)
        pair = self.compare()['pairs'][0]
        self.assertEqual(pair['candidate']['observation']['submissions'][0]['response'], 'not_recorded')
        self.assertIsNone(pair['comparison']['coordinator_elapsed_delta_seconds'])
        self.assertIn('coordinator_elapsed_not_comparable', pair['comparison']['warnings'])

    def test_failed_snapshot_is_retained_without_success_only_average(self):
        values = fixtures.events(self.b); values[-1]['coordinator_exit_status'] = 'failed'
        fixtures.put_events(self.b, values); self.plan = plan_for(self.a, self.b)
        pair = self.compare()['pairs'][0]
        self.assertEqual(pair['candidate']['observation']['finish_snapshot']['status'], 'failed')
        self.assertIsNone(pair['comparison']['coordinator_elapsed_delta_seconds'])

    def test_saved_workload_mismatch_withholds_all_deltas(self):
        values = fixtures.events(self.b); values[0]['graph_sha256'] = 'd' * 64
        context = fixtures.read(self.b / 'context.json'); context['intent'] = values[0]
        fixtures.write(self.b / 'context.json', context); fixtures.put_events(self.b, values)
        self.plan = plan_for(self.a, self.b)
        pair = self.compare()['pairs'][0]
        self.assertEqual(pair['comparison']['state'], 'withheld')
        self.assertIn('saved_workload_mismatch', pair['comparison']['blockers'])
        self.assertEqual(pair['comparison']['host_metrics'], {})

    def test_unknown_and_zero_counters_keep_coverage_and_null_delta(self):
        self.mutate_profile(self.b, lambda rows: rows[1].update(host_commit={'unknown_reason': 'PRIVATE'}))
        metric = self.compare()['pairs'][0]['comparison']['host_metrics']['commit_headroom_bytes']
        self.assertIsNone(metric['sampled_min_delta']); self.assertEqual(metric['candidate']['unknown_samples'], 1)
        self.mutate_profile(self.b, lambda rows: rows[1].update(host_commit={
            'limit_bytes': 200, 'committed_bytes': 200, 'available_bytes': 0, 'unknown_reason': None}))
        metric = self.compare()['pairs'][0]['comparison']['host_metrics']['commit_headroom_bytes']
        self.assertEqual(metric['sampled_min_delta'], -100)

    def test_metadata_only_and_lost_runtime_withhold_unsafe_pair_arithmetic(self):
        self.mutate_profile(self.b, lambda rows: rows.pop())
        result = fixtures.read(self.b / 'result.json'); result['runtime_binding']['lost'] = True
        fixtures.write(self.b / 'result.json', result); self.plan = plan_for(self.a, self.b)
        pair = self.compare()['pairs'][0]
        self.assertEqual(pair['comparison']['state'], 'withheld')
        self.assertIn('no_observed_samples', pair['comparison']['blockers'])
        self.assertEqual(pair['candidate']['observation']['profile_summary']['sampling']['observed'], 0)

    def test_different_runtime_is_disclosed_not_a_claim_of_causality(self):
        result = fixtures.read(self.b / 'result.json'); result['runtime_binding']['profile_sha256'] = 'd' * 64
        fixtures.write(self.b / 'result.json', result); self.plan = plan_for(self.a, self.b)
        pair = self.compare()['pairs'][0]
        self.assertIn('runtime_profile', pair['comparison']['observed_differences'])
        self.assertFalse(pair['qualified_benchmark'])
        self.assertEqual(pair['comparison']['state'], 'descriptive')

    def test_duplicate_job_result_and_pair_ids_refused_before_any_evidence_reads(self):
        for key in ('job_id', 'result_sha256'):
            value = copy.deepcopy(self.plan)
            value['pairs'][0]['candidate'][key] = value['pairs'][0]['baseline'][key]
            self.path.write_text(json.dumps(value), encoding='utf-8')
            with patch.object(self.api, 'inspect_observation', side_effect=AssertionError('should not read')):
                with self.assertRaises(self.api.EvidenceError): self.api.compare_observations(self.path)
        self.plan['pairs'].append(copy.deepcopy(self.plan['pairs'][0]))
        with self.assertRaises(self.api.EvidenceError): self.compare()

    def test_reused_actual_prompt_identity_invalidates_both_observations(self):
        values = fixtures.events(self.b); values[1]['prompt_id'] = 'base-prompt'
        values[1]['prompt_id_sha256'] = fixtures.producer.digest('base-prompt')
        fixtures.put_events(self.b, values); self.plan = plan_for(self.a, self.b)
        result = self.compare()
        self.assertEqual(result['counts']['invalid_observations'], 2)
        for side in ('baseline', 'candidate'):
            self.assertIn('reused_prompt_evidence', result['pairs'][0][side]['reasons'])
        self.assertEqual(result['counts']['withheld_pairs'], 1)

    def test_changed_result_pin_is_invalid_not_automatically_rebound(self):
        original = self.plan['pairs'][0]['candidate']['result_sha256']
        fixtures.rehash(self.b)
        pair = self.compare()['pairs'][0]
        self.assertEqual(pair['candidate']['state'], 'invalid')
        self.assertEqual(pair['candidate']['expected_result_sha256'], original)
        self.assertIn('result_pin_mismatch', pair['candidate']['reasons'])

    def test_manifest_schema_bounds_and_no_execution_authority(self):
        changes = [lambda p: p.update(generation_allowance=1), lambda p: p.update(generation_allowance=False),
                   lambda p: p.update(schema='future'), lambda p: p.update(pairs=[]),
                   lambda p: p.update(pairs=p['pairs'] * 9), lambda p: p.update(execute=True),
                   lambda p: p['pairs'][0].update(condition='proven_warm'),
                   lambda p: p['pairs'][0]['candidate'].update(directory='PRIVATE\0'),
                   lambda p: p['pairs'][0]['candidate'].update(result_sha256='short')]
        original = copy.deepcopy(self.plan)
        for change in changes:
            self.plan = copy.deepcopy(original); change(self.plan)
            with self.subTest(change=change), self.assertRaises(self.api.EvidenceError): self.compare()
        self.path.write_bytes(b' ' * (64 * 1024 + 1))
        with self.assertRaises(self.api.EvidenceError): self.api.compare_observations(self.path)
        for raw in (b'{"pairs":[],"pairs":[]}', b'{"a":NaN}', b'[' * 2000):
            self.path.write_bytes(raw)
            with self.assertRaises(self.api.EvidenceError): self.api.compare_observations(self.path)

    def test_declared_conditions_are_kept_separate_without_pooled_means(self):
        self.plan['pairs'][0]['condition'] = 'cold_first_generation'
        report = self.compare()
        self.assertEqual(report['pairs'][0]['declared_condition'], 'cold_first_generation')
        self.assertFalse(report['pairs'][0]['condition_verified'])
        self.assertNotIn('average_seconds', json.dumps(report))

    def test_relative_paths_use_manifest_location_and_cli_is_exclusive(self):
        for side in ('baseline', 'candidate'):
            self.plan['pairs'][0][side]['directory'] = str(Path(self.plan['pairs'][0][side]['directory']).relative_to(self.root))
        self.path.write_text(json.dumps(self.plan), encoding='utf-8')
        script = ROOT / 'scripts/compare-resource-observations.py'; output = self.root / 'comparison.json'
        self.assertTrue(script.is_file(), 'Paired observation CLI is absent')
        command = [sys.executable, str(script), str(self.path), '--output', str(output)]
        result = subprocess.run(command, cwd=ROOT.parent, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        before = output.read_bytes(); report = json.loads(before)
        self.assertEqual(report['counts']['verified_observations'], 2)
        self.assertNotIn(str(self.root), json.dumps(report))
        result = subprocess.run(command, cwd=ROOT.parent, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0); self.assertEqual(output.read_bytes(), before)

    def test_cli_invalid_report_returns_nonzero_but_keeps_the_report(self):
        self.path.write_text(json.dumps(self.plan), encoding='utf-8')
        (self.b / 'summary.json').unlink()
        script = ROOT / 'scripts/compare-resource-observations.py'; output = self.root / 'partial.json'
        self.assertTrue(script.is_file(), 'Paired observation CLI is absent')
        result = subprocess.run([sys.executable, str(script), str(self.path), '--output', str(output)],
                                cwd=self.root, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertTrue(output.exists()); self.assertEqual(fixtures.read(output)['counts']['invalid_observations'], 1)

    def test_maximum_eight_pairs_and_missing_artifacts_remain_bounded(self):
        self.plan['pairs'] = []
        for index in range(8):
            a = fixtures.make_observation(self.root, f'left-{index}')
            b = fixtures.make_observation(self.root, f'right-{index}')
            self.plan['pairs'].append({'id': f'pair-{index}', 'condition': 'unspecified',
                                       'baseline': binding(a), 'candidate': binding(b)})
        result = self.compare()
        self.assertEqual(result['counts']['requested_pairs'], 8)
        self.assertEqual(result['counts']['verified_observations'], 16)
        self.assertLess(len(json.dumps(result).encode()), self.api.MAX_REPORT_BYTES)
        self.assertTrue(result['evidence_complete'])

    def test_changed_sampler_prevents_arithmetic(self):
        self.mutate_profile(self.b, lambda rows: rows[0].update(sampler_sha256='f' * 64))
        result = self.compare()['pairs'][0]['comparison']
        self.assertEqual(result['state'], 'withheld')
        self.assertIn('sampler_source_mismatch', result['blockers'])

    def test_short_sampling_is_visible_but_not_a_failed_job(self):
        self.mutate_profile(self.b, lambda rows: rows[0].update(samples_requested=2))
        context = fixtures.read(self.b / 'context.json'); context['limits']['samples'] = 2
        fixtures.write(self.b / 'context.json', context); fixtures.rehash(self.b)
        self.plan = plan_for(self.a, self.b)
        report = self.compare(); row = report['pairs'][0]['candidate']
        self.assertEqual(row['state'], 'verified')
        self.assertFalse(row['observation']['profile_summary']['sampling']['complete'])
        self.assertEqual(row['observation']['finish_snapshot']['status'], 'completed')
        self.assertIn('sampling_incomplete', row['observation']['warnings'])

    @unittest.skipUnless(hasattr(os, 'symlink'), 'Symlinks unavailable')
    def test_parent_links_are_not_erased_by_path_normalization(self):
        target = self.root / 'target'; target.mkdir()
        link = self.root / 'link'
        try: link.symlink_to(target, target_is_directory=True)
        except OSError as error: self.skipTest(str(error))
        relative = self.b.relative_to(self.root)
        self.plan['pairs'][0]['candidate']['directory'] = str(link / '..' / relative)
        row = self.compare()['pairs'][0]['candidate']
        self.assertEqual(row['state'], 'invalid')
        self.assertIn('directory_not_plain', row['reasons'])

    def test_shipped_example_stays_unbound_and_retains_both_missing_rows(self):
        example = ROOT / 'docs/performance/paired-observations.example.json'
        self.path.write_bytes(example.read_bytes())
        report = self.api.compare_observations(self.path)
        self.assertEqual(report['counts']['incomplete_observations'], 2)
        self.assertEqual(report['counts']['withheld_pairs'], 1)
        self.assertFalse(report['qualified_benchmark'])
        self.assertEqual(report['generation_allowance_added'], 0)

    def test_cli_never_imports_live_owners_or_performs_network_process_operations(self):
        self.path.write_text(json.dumps(self.plan), encoding='utf-8')
        script = ROOT / 'scripts/compare-resource-observations.py'
        self.assertTrue(script.is_file(), 'Paired observation CLI is absent')
        guard = '''import sys,runpy
class Guard:
 def find_spec(self,name,path=None,target=None):
  if name.split('.')[0] in {'server','job_resources','resource_probe','torch','psutil','subprocess','http','socket'}:
   raise AssertionError('live dependency '+name)
sys.meta_path.insert(0,Guard())
def audit(event,args):
 if event in {'socket.connect','socket.bind','subprocess.Popen','os.system'}: raise AssertionError(event)
sys.addaudithook(audit)
sys.argv=sys.argv[1:]
runpy.run_path(sys.argv[0],run_name='__main__')
'''
        result = subprocess.run([sys.executable,'-c',guard,str(script),str(self.path)], cwd=self.root,
                                capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(json.loads(result.stdout)['execution_authority'])


if __name__ == '__main__': unittest.main()
