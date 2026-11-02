import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from studio_workflow import dcc_lab as lab

ROOT = Path(__file__).resolve().parents[1]


class DccLabTests(unittest.TestCase):
    def test_catalogue_has_falsifiable_bounded_experiments(self):
        programme = lab.load_programme()
        self.assertEqual(len(programme['experiments']), 10)
        self.assertGreaterEqual(len(programme['opportunities']), 20)
        self.assertFalse(programme['automatic_execution'])
        for row in programme['experiments']:
            for key in ('question', 'hypothesis', 'stop', 'next_decision'):
                self.assertTrue(row[key])
            self.assertLessEqual(row['budget']['max_jobs'], 64)

    def test_invalid_status_budget_duplicate_and_reference_refused(self):
        original = lab.load_programme()
        for mutate in (lambda p: p['experiments'].append(p['experiments'][0]),
                       lambda p: p['experiments'][0].update(status='qualified'),
                       lambda p: p['experiments'][0]['budget'].update(max_jobs=True),
                       lambda p: p['experiments'][0].update(sources=['missing']),
                       lambda p: p['experiments'][0].update(stop='')):
            changed = copy.deepcopy(original); mutate(changed)
            with self.assertRaises(ValueError): lab.validate_programme(changed)

    def test_plan_binds_whole_programme_and_never_submits(self):
        programme = lab.load_programme()
        first = lab.experiment_intent(programme, 'scene-baseline')
        self.assertFalse(first['executable'])
        self.assertFalse(first['generation_submitted'])
        changed = copy.deepcopy(programme); changed['experiments'][0]['hypothesis'] += ' revised'
        second = lab.experiment_intent(changed, 'scene-baseline')
        self.assertNotEqual(first['plan_sha256'], second['plan_sha256'])

    def test_cli_validate_and_exclusive_plan_output(self):
        command = [sys.executable, '-m', 'studio_workflow.dcc_lab']
        checked = subprocess.run(command + ['validate'], cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(json.loads(checked.stdout)['experiments'], 10)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'intent.json'
            argv = command + ['plan-experiment', 'scene-baseline', '--out', str(output)]
            first = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=15)
            self.assertEqual(first.returncode, 0, first.stderr)
            before = output.read_bytes()
            second = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=15)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(output.read_bytes(), before)


    def test_intent_is_snapshot_not_mutable_programme_alias(self):
        programme = lab.load_programme()
        intent = lab.experiment_intent(programme, 'scene-baseline')
        before = json.dumps(intent, sort_keys=True)
        programme['experiments'][0]['steps'].append('Later mutation')
        self.assertEqual(json.dumps(intent, sort_keys=True), before)

    def test_research_evidence_cannot_self_promote(self):
        programme = lab.load_programme()
        programme['sources'][0]['evidence'] = 'locally_verified'
        with self.assertRaises(ValueError): lab.validate_programme(programme)
