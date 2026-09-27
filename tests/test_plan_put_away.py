"""Put away for plans (#940): an owner-side, reversible hide flag on the desk and in Your plans.

Only `state.put_away` changes. Status, stages, attempts, reservations, files and review stay as recorded; nothing is
started, stopped or resubmitted. A later status change brings the plan back on its own. Run with discover
(`-p "test_plan_put_away.py"`): it reuses the test_production fixture.
"""
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

import test_production as fixtures
from test_server import FakeStudio, server


class PlanPutAwayTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ProductionTests(); self.fixture.setUp(); self.addCleanup(self.fixture.tearDown)
        self.studio = FakeStudio(self.fixture.root, []); self.lab = self.studio.production
        self.id = self.lab.create(self.fixture.intent())['id']

    def record(self):
        project = self.lab._get(self.id)
        return {'plan': project['plan'], 'state': {k: v for k, v in project['state'].items() if k != 'put_away'},
                'budget': self.lab.get(self.id)['budget'], 'queued': self.studio.queue.qsize(), 'requests': list(self.studio.requests),
                'plan_file': (self.lab.root / self.id / 'plan.json').read_bytes()}

    def test_put_away_changes_only_the_marker_is_idempotent_reversible_and_survives_restart(self):
        before = self.record(); plan = self.lab.get(self.id)
        self.assertEqual(plan['state']['status'], 'planned'); self.assertTrue(plan['can_put_away']); self.assertFalse(plan['put_away'])
        with patch('production.time.time', return_value=4321.5):
            away = self.lab.put_away(self.id, {'put_away': True})
        self.assertTrue(away['put_away']); self.assertEqual(away['put_away_at'], 4321.5)
        self.assertFalse(away['can_put_away']); self.assertTrue(away['can_bring_back'])
        self.assertEqual(self.record(), before)
        self.assertEqual(self.lab.put_away(self.id, {'put_away': True})['put_away_at'], 4321.5, 'a repeat keeps the first time')
        restarted = FakeStudio(self.fixture.root, []).production.get(self.id)
        self.assertTrue(restarted['put_away']); self.assertEqual(restarted['state']['status'], 'planned')
        back = self.lab.put_away(self.id, {'put_away': False})
        self.assertFalse(back['put_away']); self.assertIsNone(back['put_away_at']); self.assertTrue(back['can_put_away'])
        self.assertNotIn('put_away', self.lab._get(self.id)['state']); self.assertEqual(self.record(), before)

    def test_a_status_change_brings_a_put_away_plan_back(self):
        self.lab.put_away(self.id, {'put_away': True})
        self.lab._mutate(self.id, status='failed', message='A recorded stage failed.')
        plan = self.lab.get(self.id)
        self.assertFalse(plan['put_away'], 'the owner put away a planned plan, not this failure'); self.assertTrue(plan['can_put_away'])
        self.assertEqual(self.lab._get(self.id)['state']['put_away']['status'], 'planned', 'the marker stays as history')

    def test_the_same_status_after_a_resume_is_a_change_and_a_restart_is_not(self):
        # #1161 review (Codex): put away while interrupted, resumed, interrupted again must come back.
        self.lab._mutate(self.id, status='interrupted', message='Studio restarted. Inspect known jobs before explicitly resuming; nothing was resubmitted.')
        self.assertTrue(self.lab.put_away(self.id, {'put_away': True})['put_away'])
        restarted = FakeStudio(self.fixture.root, []).production
        self.assertTrue(restarted.get(self.id)['put_away'], 'a restart that changes nothing keeps it put away')
        restarted._mutate(self.id, status='queued', started_at=5000.0, message='Queued to resume')
        restarted._mutate(self.id, status='interrupted', message='Studio restarted. Inspect known jobs before explicitly resuming; nothing was resubmitted.')
        again = restarted.get(self.id)
        self.assertEqual(again['state']['status'], 'interrupted'); self.assertFalse(again['put_away']); self.assertTrue(again['can_put_away'])

    def test_put_away_sticks_while_the_public_view_rewrites_the_message(self):
        # #1161 review (Muse HIGH): the desk view prefixes `message` for a storage issue; the marker must be checked
        # against the stored state, not that presentation copy, or the plan never leaves the desk.
        self.lab._mutate(self.id, status='failed', message='A recorded stage failed.', storage_issue={'reason': 'plan.json unreadable'})
        away = self.lab.put_away(self.id, {'put_away': True})
        self.assertTrue(away['put_away']); self.assertTrue(away['state']['message'].startswith('Startup storage check:'))
        self.assertTrue(self.lab.get(self.id)['put_away']); self.assertTrue(FakeStudio(self.fixture.root, []).production.get(self.id)['put_away'])

    def test_a_running_plan_cannot_be_put_away_and_bad_bodies_are_refused(self):
        for status in ('queued', 'running', 'observing'):
            with self.subTest(status=status):
                self.lab._mutate(self.id, status=status)
                self.assertFalse(self.lab.get(self.id)['can_put_away'])
                with self.assertRaisesRegex(ValueError, 'running'): self.lab.put_away(self.id, {'put_away': True})
        self.lab._mutate(self.id, status='planned')
        for body in ({}, {'put_away': 'yes'}, {'put_away': 1}, [], None):
            with self.subTest(body=repr(body)), self.assertRaisesRegex(ValueError, 'true or false'): self.lab.put_away(self.id, body)
        with self.assertRaises(ValueError): self.lab.put_away('0' * 32, {'put_away': True})

    def test_http_route(self):
        sent = []
        def post(path, body):
            handler = server.Handler.__new__(server.Handler); handler.studio = self.studio; handler.path = path
            handler._safe_mutation = lambda: True; handler._body_json = lambda *a: body
            sent.clear(); handler._json = lambda status, obj: sent.append((status, obj)); handler.do_POST(); return sent[0]
        status, body = post('/api/production/%s/put-away' % self.id, {'put_away': True})
        self.assertEqual((status, body['put_away']), (200, True))
        self.assertEqual(post('/api/production/%s/put-away' % self.id, {'put_away': 'no'})[0], 400)
        self.assertEqual(post('/api/production/%s/x/put-away' % self.id, {'put_away': True})[0], 400)

class PlanPutAwayFrontendTests(unittest.TestCase):
    # Separate from the fixture: it patches Thread.start, which subprocess needs on Windows.
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend behavior checks')
    def test_plan_detail_and_list_frontend(self):
        result = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('production_put_away_frontend.cjs'))], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Plan put away changes only its marker', result.stdout)


if __name__ == '__main__':
    unittest.main()
