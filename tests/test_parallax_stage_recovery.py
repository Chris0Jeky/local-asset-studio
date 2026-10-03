"""Shipped frontend behavior, plus the existing server's no-generation stage contract."""
from pathlib import Path
import shutil
import subprocess
import unittest

import test_parallax as fixture

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'Node is required for frontend contracts')
class FrontendStageRecoveryTests(unittest.TestCase):
    def test_stage_card_actions_and_deferred_response_ownership(self):
        result = subprocess.run([shutil.which('node'), '--test', str(ROOT/'tests/parallax_stage_recovery.cjs')],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('# fail 0', result.stdout)


class ServerStageRecoveryTests(unittest.TestCase):
    setUp = fixture.RouteTests.setUp
    studio = fixture.RouteTests.studio
    source = fixture.RouteTests.source
    prepared = fixture.RouteTests.prepared
    payload = fixture.RouteTests.payload

    def test_completed_split_retains_each_explicit_stage_and_source_without_submission(self):
        studio = self.studio()
        prepared = self.prepared(studio)
        studio.jobs['stage-recovery'] = {'id': 'stage-recovery', 'status': 'completed',
                                       'parallax': prepared['claim'], 'parallax_finish': {'job_id': 'already-split'}}
        before = set(studio.jobs)
        for stage in ('plate', 'isolate'):
            result = fixture.parallax.next_stage(studio, {'job_id': 'stage-recovery', 'stage': stage})
            self.assertEqual(result['plan'], prepared['plan'])
            self.assertEqual(result['claim']['stage'], stage)
            self.assertEqual(result['words'], fixture.parallax.words(stage, prepared['plan']['objects']))
            self.assertFalse(result['generation_submitted'])
            body = self.payload(result)
            studio.prepare(body)
        self.assertEqual(set(studio.jobs), before)
        self.assertTrue(studio.queue.empty())
        self.assertEqual(studio.requests, [])
