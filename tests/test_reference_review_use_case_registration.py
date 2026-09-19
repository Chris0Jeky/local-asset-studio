"""Contract for the measured Prompt Lab reference-review journey."""
import json
import unittest
from pathlib import Path
import sys
from types import SimpleNamespace

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

    def test_ci_runs_exactly_the_measured_case(self):
        """The lane's gate is the runner's own exit code now, so what the workflow still has to promise is
        that it measures this one journey and no other. Draft PR #615 asserted the same property as
        `matrix['cases'] == 1` inside the gate step this branch removes; it belongs here instead."""
        workflow = (ROOT / '.github/workflows/reference-review-use-case.yml').read_text(encoding='utf-8')
        self.assertIn('--case ' + CASE_ID, workflow)
        self.assertEqual(workflow.count('--case '), 1, 'the lane must measure exactly one journey')
        self.assertIn('tests/reference_review_browser.py', workflow)

    def test_fixture_reuses_the_production_body_length_guard(self):
        """Only `_content_length` is inherited: the host and origin guards are rebound to the served
        port and pinned by the probes below, not by identity with production's."""
        from test_server import server

        handler, _ = runner.build_handler()
        fixture_base = next(cls for cls in handler.__mro__ if cls.__name__ == 'PromptFixtureBase')
        self.assertIs(fixture_base._content_length, server.Handler._content_length)

    def test_fixture_guards_admit_the_port_the_fixture_actually_serves(self):
        """Production's host guard hard-codes :8191; the fixture binds an ephemeral port."""
        handler, _ = runner.build_handler()
        fixture_base = next(cls for cls in handler.__mro__ if cls.__name__ == 'PromptFixtureBase')
        probe = fixture_base.__new__(fixture_base)
        probe.server = SimpleNamespace(server_port=45678)

        probe.headers = {'Host': '127.0.0.1:45678', 'Origin': 'http://127.0.0.1:45678'}
        self.assertTrue(probe._safe_host())
        self.assertTrue(probe._safe_mutation())

        probe.headers = {'Host': '127.0.0.1:8191', 'Origin': 'http://127.0.0.1:8191'}
        self.assertFalse(probe._safe_host(), 'A request for another port must not be admitted')

        probe.headers = {'Host': '127.0.0.1:45678', 'Origin': 'http://evil.invalid'}
        self.assertFalse(probe._safe_mutation(), 'A cross-origin mutation must still be refused')

        probe.headers = {'Host': '127.0.0.1:8191', 'Origin': 'http://127.0.0.1:45678'}
        self.assertFalse(probe._safe_mutation(), 'A mutation must fail its host check too, not only its origin check')


if __name__ == '__main__':
    unittest.main()
