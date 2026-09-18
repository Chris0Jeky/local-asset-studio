"""Offline specification tests; no media, providers or application services."""
import copy
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent


class ProductionBriefTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / 'brief.py'
        if not path.is_file():
            raise AssertionError('The offline asset-brief reader has not been implemented')
        spec = importlib.util.spec_from_file_location('asset_brief', path)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def setUp(self):
        self.rows, self.config = self.mod.load()

    def test_catalog_is_planned_and_has_154_unique_requests(self):
        self.assertEqual(len(self.rows), 154)
        self.assertEqual(len({r['id'] for r in self.rows}), 154)
        self.assertEqual(self.config['production_status'], 'planned')
        self.assertFalse(self.config['asset_bytes_present'])

    def test_every_request_resolves_an_actionable_brief(self):
        for row in self.rows:
            text = self.mod.render(row['id'], self.rows, self.config)
            for phrase in (row['id'], row['subject'], row['acceptance'], 'NOT PRODUCED', 'Deliverables', 'Selection'):
                self.assertIn(phrase, text, row['id'])

    def test_duplicate_identity_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.mod.validate(self.rows + [self.rows[0]], self.config)

    def test_invalid_world_descriptions_are_refused(self):
        for value in (None, 12, [], {}, '', '   ', 'x' * 2001):
            config = copy.deepcopy(self.config)
            config['worlds']['shared'] = value
            with self.subTest(value=type(value).__name__):
                with self.assertRaisesRegex(ValueError, 'world description'):
                    self.mod.validate(self.rows, config)

    def test_unknown_profile_and_anchor_are_refused(self):
        for key, value in [('profile', 'imaginary'), ('anchor', 'absent')]:
            rows = copy.deepcopy(self.rows)
            rows[0][key] = value
            with self.assertRaises(ValueError):
                self.mod.validate(rows, self.config)

    def test_dependency_cycle_is_refused(self):
        rows = copy.deepcopy(self.rows)
        rows[0]['anchor'] = rows[1]['id']
        rows[1]['anchor'] = rows[0]['id']
        with self.assertRaisesRegex(ValueError, 'cycle'):
            self.mod.validate(rows, self.config)

    def test_unknown_id_and_bad_wave_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'Unknown asset'):
            self.mod.render('not-here', self.rows, self.config)
        rows = copy.deepcopy(self.rows)
        rows[0]['wave'] = 'P99'
        with self.assertRaises(ValueError):
            self.mod.validate(rows, self.config)

    def test_planned_records_cannot_claim_actual_media(self):
        config = copy.deepcopy(self.config)
        config['asset_bytes_present'] = True
        with self.assertRaisesRegex(ValueError, 'planned'):
            self.mod.validate(self.rows, config)

    def test_separate_code_capture_and_media_work(self):
        by_id = {r['id']: r for r in self.rows}
        self.assertEqual(by_id['foundation-buttons']['method'], 'code')
        self.assertEqual(by_id['tutorial-pose']['method'], 'capture')
        self.assertEqual(by_id['retro-anime-loop']['method'], 'animate')
        self.assertIn('Do not use an image generator', self.mod.render('foundation-buttons', self.rows, self.config))
        self.assertIn('Record the real UI', self.mod.render('tutorial-pose', self.rows, self.config))

    def test_cli_is_read_only_and_prints_a_brief(self):
        before = {p.name: p.read_bytes() for p in ROOT.iterdir() if p.is_file()}
        result = subprocess.run([sys.executable, str(ROOT/'brief.py'), 'show', 'retro-anime-master'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Night Shift', result.stdout)
        self.assertEqual(before, {p.name: p.read_bytes() for p in ROOT.iterdir() if p.is_file()})

    def test_cli_invalid_id_has_clear_error(self):
        result = subprocess.run([sys.executable, str(ROOT/'brief.py'), 'show', '../absent'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Unknown asset', result.stderr)
        self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
