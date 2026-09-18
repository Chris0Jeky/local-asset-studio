"""Contract for the measured Prompt Lab reference-review journey."""
import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import studio_use_cases as runner

CASE_ID = 'reference-analysis-review-and-apply'


class ReferenceReviewUseCaseRegistration(unittest.TestCase):
    def test_manifest_registers_the_journey(self):
        manifest = json.loads((ROOT / 'research/ux/use-cases.json').read_text(encoding='utf-8'))
        cases = {case['id']: case for case in manifest['cases']}
        self.assertIn(CASE_ID, cases)
        case = cases[CASE_ID]
        self.assertEqual(case['starting_view'], 'prompt-lab')
        self.assertGreaterEqual(len(case['steps']), 7)
        wording = ' '.join(step['intent'] + ' ' + step['expect'] for step in case['steps']).lower()
        for expected in ('analysis', 'original', 'preview', 'apply'):
            self.assertIn(expected, wording)

    def test_runner_and_documentation_cover_the_same_journey(self):
        self.assertIn(CASE_ID, runner.DRIVERS)
        docs = (ROOT / 'docs/UX-USE-CASE-MATRIX.md').read_text(encoding='utf-8')
        self.assertIn('`' + CASE_ID + '`', docs)

    def test_ci_runs_the_measured_case(self):
        workflow = (ROOT / '.github/workflows/reference-review-use-case.yml').read_text(encoding='utf-8')
        self.assertIn('--case ' + CASE_ID, workflow)
        self.assertIn('tests/reference_review_browser.py', workflow)

    def test_fixture_reuses_production_transport_guards(self):
        from test_server import server

        handler, _ = runner.build_handler()
        fixture_base = next(cls for cls in handler.__mro__ if cls.__name__ == 'PromptFixtureBase')
        self.assertIs(fixture_base._safe_host, server.Handler._safe_host)
        self.assertIs(fixture_base._safe_mutation, server.Handler._safe_mutation)
        self.assertIs(fixture_base._content_length, server.Handler._content_length)


if __name__ == '__main__':
    unittest.main()
