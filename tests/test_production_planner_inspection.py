"""Read-only settings inspection through the real Production service and JS."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

import test_production as F


class PlannerInspectionTests(unittest.TestCase):
    setUp = F.PlannedSweepTests.setUp
    tearDown = F.PlannedSweepTests.tearDown

    def test_inspection_without_available_axes_creates_no_variants_jobs_or_rows(self):
        kb = json.loads(self.kb_bytes)
        kb['loras']['a.safetensors']['role'] = 'accelerator'
        (self.root/'presets/settings-kb.json').write_text(json.dumps(kb), encoding='utf-8')
        studio = F.FakeStudio(self.root, [])
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        report = studio.production.plan({'preset_id': 'planned', 'mode': 'inspect',
                                         'controls': {'lora': 1, 'lora_name': 'a.safetensors'}})
        self.assertEqual(report['mode'], 'inspect')
        self.assertEqual(report['variants'], [])
        self.assertEqual(report['axes_available'], [])
        self.assertEqual([r['id'] for r in report['axes_withheld']], ['steps', 'sampler'])
        self.assertFalse(report['generation_submitted']); self.assertFalse(report['reservation_created'])
        self.assertEqual(studio.production.list(), [])
        self.assertEqual(studio.jobs, {}); self.assertEqual(studio.queue.qsize(), 0)
        self.assertEqual(before, {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_composed_http_exposes_inspection_without_preparing_or_submitting(self):
        from http.client import HTTPConnection
        import threading
        studio = F.FakeStudio(self.root, [])
        self.patches[0].stop()  # Permit only the fixture HTTP thread, not Studio workers.
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        http = F.server.create_server(self.root, port=0, studio_factory=lambda _: studio)
        thread = threading.Thread(target=http.serve_forever); thread.start()
        connection = HTTPConnection('127.0.0.1', http.server_port, timeout=5)
        try:
            connection.request('POST', '/api/experiments/plan', json.dumps({'preset_id':'planned','mode':'inspect'}),
                               headers={'Host':'127.0.0.1:8191','Origin':'http://127.0.0.1:8191','Content-Type':'application/json'})
            reply = connection.getresponse(); report = json.loads(reply.read())
            self.assertEqual(reply.status, 200, report)
            self.assertEqual(report['mode'], 'inspect'); self.assertEqual(report['variants'], [])
            self.assertFalse(report['generation_submitted']); self.assertFalse(report['reservation_created'])
            self.assertFalse(studio.jobs); self.assertEqual(studio.queue.qsize(), 0)
            self.assertEqual(studio.production.list(), [])
            self.assertEqual(before, {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        finally:
            connection.close(); http.shutdown(); http.server_close(); thread.join(5)

    def test_inspection_with_available_axes_still_does_not_plan_a_grid(self):
        studio = F.FakeStudio(self.root, [])
        report = studio.production.plan({'preset_id': 'planned', 'mode': 'inspect'})
        self.assertEqual(len(report['axes_available']), 2)
        self.assertEqual(report['axes_withheld'], [])
        self.assertEqual(report['variants'], [])
        for option in ({'axes': ['steps']}, {'limit': 4}):
            with self.subTest(option=option), self.assertRaisesRegex(ValueError, 'Inspection does not select'):
                studio.production.plan({'preset_id': 'planned', 'mode': 'inspect', **option})

    def test_ordinary_plans_use_same_inspection_and_do_not_gain_authority(self):
        lab = F.FakeStudio(self.root, []).production
        inspect = lab.plan({'preset_id': 'planned', 'mode': 'inspect'})
        plan = lab.plan({'preset_id': 'planned', 'mode': 'grid'})
        for key in ('axes_available', 'axes_withheld', 'knowledge_sha256', 'notice'):
            self.assertEqual(plan[key], inspect[key])
        self.assertEqual(len(plan['variants']), 4)
        self.assertFalse(plan['generation_submitted']); self.assertFalse(plan['reservation_created'])


class PlannerDocumentationTests(unittest.TestCase):
    def test_advanced_panel_docs_name_all_three_actions(self):
        text=(Path(__file__).parents[1]/'docs/EXPERIMENTS.md').read_text(encoding='utf-8')
        self.assertIn('Three actions under **Advanced: plan several settings from the library**',text)
        for action in ('Inspect available settings','Plan from settings library','Remix LoRA weights'):
            self.assertIn('**'+action+'**',text)


class PlannerInspectionFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required for actual frontend contract')
    def test_inspection_retains_drafts_and_ignores_late_replies(self):
        result = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('production_planner_inspection.cjs'))],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
