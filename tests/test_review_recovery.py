"""Deterministic journal and dispatch-boundary contracts in the ordinary suite."""
import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('node'), 'Node required')
class ReviewRecoveryContracts(unittest.TestCase):
    def test_core(self):
        self.run_contract('review_recovery_core.cjs', 'passed: 11')

    def test_checkpoint_before_dispatch(self):
        self.run_contract('review_recovery_hooks.cjs', 'passed: 3')

    def run_contract(self, name, marker):
        result = subprocess.run([shutil.which('node'), str(Path(__file__).with_name(name))],
                                capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(marker, result.stdout)
