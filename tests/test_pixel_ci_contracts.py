"""Guard the explicit pixel-helper Windows workflow wiring without YAML dependencies."""
import fnmatch
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PixelCiContracts(unittest.TestCase):
    def test_both_triggers_cover_helper_tests_and_frozen_oracle(self):
        text = (ROOT / '.github/workflows/character-edit-contracts.yml').read_text()
        sections = {'pull_request': text.split('  pull_request:\n', 1)[1].split('  push:\n', 1)[0],
                    'push': text.split('  push:\n', 1)[1].split('permissions:\n', 1)[0]}
        for event, section in sections.items():
            patterns = re.findall(r"^      - '([^']+)'$", section, re.M)
            for path in ('scripts/pixel_diff.py', 'tests/test_pixel_diff.py',
                         'tests/test_pixel_equality.py', 'tests/test_bundle_equality.py',
                         'tests/test_pixel_ci_contracts.py', 'tests/fixtures/bundle_equality_baseline.py'):
                with self.subTest(event=event, path=path):
                    self.assertTrue(any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns), path)

    def test_windows_lane_executes_all_new_suites_and_prior_ones(self):
        text = (ROOT / '.github/workflows/character-edit-contracts.yml').read_text()
        self.assertIn('runs-on: windows-latest', text)
        for pattern in ('test_pixel_*.py', 'test_bundle_equality.py', 'test_character_edit*.py', 'test_character_krita*.py'):
            with self.subTest(pattern=pattern):
                self.assertIn('python -m unittest discover -s tests -p "' + pattern + '" -v', text)

    def test_equality_tests_require_the_production_function(self):
        text = (ROOT / 'tests/test_pixel_equality.py').read_text()
        self.assertNotIn("getattr(pixel_diff, 'same_pixels', legacy_same)", text)
        self.assertIn('return pixel_diff.same_pixels(a, b)', text)


if __name__ == '__main__': unittest.main()
