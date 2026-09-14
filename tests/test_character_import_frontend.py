"""Actual import handlers plus the existing Production/Workspace HTTP contracts, with inert sources."""
import base64
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import threading
import unittest

import test_character_handoff_import as handoff_fixture
from test_server import server


@unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend behavior checks')
class CharacterImportFrontendTests(unittest.TestCase):
    def test_import_controls(self):
        result = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('character_import_frontend.cjs'))],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Character import controls preserve', result.stdout)


@unittest.skipUnless(shutil.which('node'), 'Node.js is required for the real HTTP import proof')
class CharacterImportHttpTests(unittest.TestCase):
    setUp = handoff_fixture.CharacterHandoffImportTests.setUp
    character_preflight = handoff_fixture.CharacterHandoffImportTests.character_preflight
    payload = handoff_fixture.CharacterHandoffImportTests.payload

    def test_browser_handlers_import_through_real_routes_without_jobs(self):
        payload = self.payload(self.plan['cases'][0])
        fixture = self.root/'browser-import-fixture.json'
        fixture.write_text(json.dumps({'plan': payload['character_plan'], 'handoff': payload['character_handoff'],
                                      'plan_text': json.dumps(payload['character_plan']), 'handoff_text': json.dumps(payload['character_handoff']),
                                      'references': [{'bytes': base64.b64encode(handoff_fixture.PNG).decode(), 'type': 'image/png'}]}), encoding='utf-8')
        self.patches[0].stop()  # Only the inert HTTP server starts; Studio's worker was never started.
        handler = type('CharacterImportHandler', (server.Handler,), {'studio': self.studio, 'log_message': lambda *a: None})
        http = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        worker = threading.Thread(target=http.serve_forever, daemon=True); worker.start()
        try:
            result = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('character_import_frontend.cjs')),
                                     '--http', str(fixture), f'http://127.0.0.1:{http.server_port}'],
                                    capture_output=True, text=True, timeout=25)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Character import real HTTP path', result.stdout)
            projects = self.studio.production.list()
            self.assertEqual(len(projects), 1)
            self.assertEqual(projects[0]['budget'], {'allowance': 2, 'reserved': 0})
            self.assertEqual(projects[0]['state']['status'], 'planned')
            self.assertEqual(self.studio.jobs, {}); self.assertTrue(self.studio.queue.empty())
        finally:
            http.shutdown(); http.server_close(); worker.join(2)
        self.assertFalse(worker.is_alive())
