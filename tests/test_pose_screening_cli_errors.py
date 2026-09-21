"""Regression coverage for zero-authority pose-screening CLI parse errors."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'pose_screening.py'
MANIFEST = ROOT / 'examples' / 'pose-control' / 'screening-manifest.json'


class PoseScreeningCliErrorTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=15,
        )

    def test_subparser_argument_errors_emit_unauthorized_json_receipts(self):
        cases = (
            ('plan', MANIFEST),
            ('validate-plan', MANIFEST),
        )
        for args in cases:
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                receipt = json.loads(result.stderr)
                self.assertIn('error', receipt)
                self.assertEqual(receipt['authority'], 'none')
                self.assertFalse(receipt['execution_authorized'])
                self.assertFalse(receipt['generation_submitted'])


if __name__ == '__main__':
    unittest.main()
