"""Offline execution/retention faults; mocked Blender output is never native evidence."""
import copy
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import blender_material_qualification as qualification


def observation():
    return {'blender': {'version_string': 'fixture', 'build_hash': 'fixture'},
            'label': {'kind': 'material-mismatch', 'object': 'Badge', 'slot': 0, 'from': 'BadgeGreen', 'to': 'BodyTextured'},
            'retention': {'BadgeGreen': True, 'BodyTextured': False, 'A_UnusedMaterial': False},
            'materials': {stage: ['BadgeGreen', 'BodyTextured'] for stage in ('before', 'seeded', 'reopened', 'repaired')},
            'checksums': {'before': 'a' * 64, 'seeded': 'b' * 64, 'reopened': 'b' * 64, 'repaired': 'a' * 64}}


class MaterialQualificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.output = self.root / 'evidence'
        self.binary = self.root / 'blender'; self.binary.write_bytes(b'offline executable placeholder')

    def result(self, command, **kwargs):
        out = Path(command[-1]); (out / 'assets').mkdir()
        for name in ('lab-asset.blend', 'damaged.blend', 'repaired.blend', 'lab-checker.png'):
            (out / 'assets' / name).write_bytes(b'offline artifact placeholder')
        (out / 'material-repair.json').write_text(json.dumps(observation()))
        return subprocess.CompletedProcess(command, 0, 'fixture stdout', 'fixture stderr')

    def run_qualification(self, side_effect=None):
        with patch.object(qualification, 'run_blender', side_effect=side_effect or self.result):
            return qualification.qualify(self.binary, self.output)

    def test_success_retains_plan_source_hashes_logs_and_artifact_identities(self):
        receipt = self.run_qualification()
        self.assertEqual(receipt['state'], 'passed')
        plan = json.loads((self.output / 'plan.json').read_text())
        self.assertEqual(plan['timeout_seconds'], 120)
        self.assertEqual(plan['command'][-1], str(self.output))
        self.assertIn('--offline-mode', plan['command'])
        self.assertTrue(plan['source_sha256'])
        self.assertEqual(receipt['returncode'], 0)
        self.assertIn('assets/repaired.blend', receipt['outputs'])
        self.assertEqual((self.output / 'blender-stdout.log').read_text(), 'fixture stdout')
        self.assertEqual((self.output / 'blender-stderr.log').read_text(), 'fixture stderr')

    def test_existing_directory_is_refused_without_replacing_evidence(self):
        self.output.mkdir(); preserved = self.output / 'receipt.json'; preserved.write_text('old evidence')
        with self.assertRaises(FileExistsError): self.run_qualification()
        self.assertEqual(preserved.read_text(), 'old evidence')

    def test_manual_tilde_path_launches_and_records_the_validated_expanded_binary(self):
        launched = []
        def expanded_path(command, **kwargs):
            launched.append(command[0])
            return self.result(command, **kwargs)
        # Model home expansion without creating files in the actual user's home.
        original_expanduser = Path.expanduser
        def expanduser(path):
            return self.binary if str(path) == '~/apps/blender' else original_expanduser(path)
        with patch.object(Path, 'expanduser', expanduser):
            with patch.object(qualification, 'run_blender', side_effect=expanded_path):
                receipt = qualification.qualify('~/apps/blender', self.output)
        self.assertEqual(receipt['state'], 'passed')
        self.assertEqual(launched, [str(self.binary.resolve())])
        plan = json.loads((self.output / 'plan.json').read_text())
        self.assertEqual(plan['command'][0], launched[0])

    def test_native_error_retains_exit_and_logs_without_claiming_pass(self):
        receipt = self.run_qualification(lambda command, **kwargs: subprocess.CompletedProcess(command, 17, 'partial', 'native failure'))
        self.assertEqual(receipt['state'], 'failed'); self.assertEqual(receipt['returncode'], 17)
        self.assertIn('17', receipt['error'])
        self.assertEqual((self.output / 'blender-stderr.log').read_text(), 'native failure')

    def test_timeout_preserves_partial_streams_and_failure_receipt(self):
        def timeout(command, **kwargs): raise subprocess.TimeoutExpired(command, 120, output=b'partial stdout', stderr=b'partial stderr')
        receipt = self.run_qualification(timeout)
        self.assertEqual(receipt['state'], 'failed'); self.assertEqual(receipt['returncode'], 'timeout')
        self.assertEqual((self.output / 'blender-stdout.log').read_text(), 'partial stdout')
        self.assertTrue((self.output / 'receipt.json').is_file())

    def test_zero_exit_without_observation_or_artifacts_is_failure(self):
        receipt = self.run_qualification(lambda command, **kwargs: subprocess.CompletedProcess(command, 0, '', ''))
        self.assertEqual(receipt['state'], 'failed')

    def test_valid_observation_cannot_hide_missing_native_artifact(self):
        def missing_artifact(command, **kwargs):
            result = self.result(command, **kwargs)
            (self.output / 'assets/repaired.blend').unlink()
            return result
        receipt = self.run_qualification(missing_artifact)
        self.assertEqual(receipt['state'], 'failed')
        self.assertIn('Missing native artifact repaired.blend', receipt['error'])
        self.assertTrue((self.output / 'material-repair.json').is_file())

    def test_changed_membership_retention_or_checksum_is_rejected(self):
        variants = []
        for key, stage, value in [('materials', 'repaired', ['BodyTextured']), ('retention', 'A_UnusedMaterial', True),
                                  ('checksums', 'repaired', 'c' * 64), ('checksums', 'reopened', 'c' * 64),
                                  ('checksums', 'seeded', 'a' * 64)]:
            damaged = copy.deepcopy(observation()); damaged[key][stage] = value; variants.append(damaged)
        for damaged in variants:
            with self.subTest(damaged=damaged), self.assertRaises(ValueError): qualification.validate_observation(damaged)

    def test_missing_blender_retains_failed_attempt(self):
        receipt = qualification.qualify(self.root / 'missing-blender', self.output)
        self.assertEqual(receipt['state'], 'failed')
        self.assertTrue((self.output / 'plan.json').is_file())

    def test_required_native_guard_fails_without_configured_executable(self):
        environment = dict(os.environ, LAS_REQUIRE_MATERIAL_NATIVE='1')
        environment.pop('LAS_BLENDER_LAB_EXE', None)
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p',
                                 'test_blender_corpus.py', '-k', 'material_swap_repair', '-v'],
                                cwd=ROOT, env=environment, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Required material qualification lacks', result.stderr)

    def test_probe_startup_failure_retains_stage_without_claiming_observation(self):
        self.output.mkdir()
        with patch.dict(sys.modules, {'bpy': SimpleNamespace()}), patch.object(qualification.lab.bpy_side, 'Worker', side_effect=RuntimeError('startup failed')):
            with patch.object(sys, 'argv', ['blender', '--', str(self.output)]), self.assertRaisesRegex(RuntimeError, 'startup failed'):
                runpy.run_path(str(qualification.PROBE), run_name='__main__')
        status = json.loads((self.output / 'probe-status.json').read_text())
        self.assertEqual(status['state'], 'failed'); self.assertEqual(status['stage'], 'starting')
        self.assertIn('startup failed', status['error'])
        self.assertFalse((self.output / 'material-repair.json').exists())


if __name__ == '__main__': unittest.main()
