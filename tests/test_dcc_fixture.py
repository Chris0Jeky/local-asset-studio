from pathlib import Path
import tempfile
import unittest

from studio_workflow import dcc_fixture


class FixtureStudyTests(unittest.TestCase):
    def test_seeded_study_retains_failures_without_claiming_native_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'study'
            result = dcc_fixture.run_study(out)
            self.assertTrue(result['expectations_met'])
            self.assertFalse(result['native_execution'])
            self.assertEqual(len(result['cases']), 8)
            self.assertEqual(result['cases']['unchanged']['observed'], 'within_declared_tolerance')
            self.assertEqual(result['cases']['same-count-topology']['observed'], 'different')
            self.assertEqual(result['cases']['missing-holdout']['observed'], 'incomplete')
            self.assertEqual(result['cases']['camera-shift']['observed'], 'incomparable')
            self.assertEqual(result['cases']['tampered-file']['observed'], 'refused')
            self.assertTrue((out / 'study.json').is_file())
            self.assertTrue((out / 'baseline' / 'front.png').is_file())
            with self.assertRaises(FileExistsError): dcc_fixture.run_study(out)

    def test_fixture_images_and_observations_are_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a', Path(tmp) / 'b'
            dcc_fixture.run_study(a); dcc_fixture.run_study(b)
            for relative in ('baseline/evidence.json', 'baseline/scene.json', 'baseline/front.png'):
                self.assertEqual((a / relative).read_bytes(), (b / relative).read_bytes())
