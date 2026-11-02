"""The policy study exercises real pixels offline, keeps originals, and exposes misses."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
try:
    import render_critic_study as study
except ImportError:
    study = None


class StudyTests(unittest.TestCase):
    def setUp(self): self.assertIsNotNone(study, 'owned-pixel study not implemented')

    def run_study(self, root, sizes=(96, 256)):
        with patch('urllib.request.urlopen', side_effect=AssertionError('study must be offline')):
            return study.run(root, sizes=sizes)

    def test_study_exposes_the_small_defect_tradeoff(self):
        with tempfile.TemporaryDirectory() as d:
            result = self.run_study(Path(d) / 'study')
            rows = {r['id']: r for r in result['cases']}
            self.assertFalse(rows['256-clean']['receipt']['changed'])
            self.assertTrue(rows['256-sparse26']['receipt']['changed'])
            self.assertEqual(rows['256-sparse26']['hypotheses']['0.004']['status'], 'below_floor')
            self.assertEqual(rows['256-defect171']['hypotheses']['0.004']['status'], 'below_floor')
            self.assertEqual(rows['96-defect171']['hypotheses']['0.004']['status'], 'changed')
            self.assertTrue(rows['256-alpha-loss']['receipt']['changed'])
            self.assertEqual(rows['256-size-mismatch']['hypotheses']['0.004']['status'], 'changed')
            self.assertFalse(result['native_calibration']); self.assertFalse(result['default_policy_changed'])

    def test_hashes_and_raw_receipts_are_retained(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'study'; result = self.run_study(root, sizes=(96,))
            self.assertTrue((root / 'index.html').is_file())
            self.assertTrue((root / 'summary.json').is_file())
            for artifact in result['artifacts']:
                p = root / artifact['path']
                self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), artifact['sha256'])
            for row in result['cases']:
                source = json.loads((root / row['receipt_path']).read_text())
                self.assertEqual(source, row['receipt'])

    def test_repeated_run_is_deterministic_but_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            first, second = Path(d) / 'a', Path(d) / 'b'
            a, b = self.run_study(first, sizes=(96,)), self.run_study(second, sizes=(96,))
            self.assertEqual(a, b)
            summary = (first / 'summary.json').read_bytes()
            with self.assertRaises(FileExistsError): self.run_study(first, sizes=(96,))
            self.assertEqual(summary, (first / 'summary.json').read_bytes())

    def test_invalid_budget_is_refused_before_any_directory(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'no-output'
            for sizes in ((), (0,), (8192,), (96, 96), (True,), ('96',)):
                with self.subTest(sizes=sizes), self.assertRaises(ValueError): self.run_study(root, sizes=sizes)
                self.assertFalse(root.exists())


if __name__ == '__main__': unittest.main()
