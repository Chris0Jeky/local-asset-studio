"""Full Studio composition with a non-running worker and synthetic installed nodes."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from studio_workflow.core import canonical
from studio_workflow.document_http import store as documents
from studio_workflow.run_http import PREFIX

FULL_CHECKOUT = (Path(__file__).parents[1] / 'app/server.py').is_file()


@unittest.skipUnless(FULL_CHECKOUT, 'Requires the complete Studio checkout')
class DocumentRunIntegrationTests(unittest.TestCase):
    def setUp(self):
        from test_workflow_preset_integration import PresetIntegrationTests
        PresetIntegrationTests.setUp(self)
        self.source = documents(self.studio).create({'request_id': 'saved-source', 'document': self.doc})
        self.value = {'request_id': 'prepared-run', 'document_id': self.source['id'],
                      'expected_revision': 1, 'preset_id': 'example'}
    def request(self, path, value=None, origin='http://127.0.0.1:8191'):
        req = Request(self.url + path, data=canonical(value) if value is not None else None,
            headers={'Content-Type': 'application/json', 'Host': '127.0.0.1:8191', 'Origin': origin})
        try:
            with urlopen(req, timeout=5) as response: return response.status, json.loads(response.read())
        except HTTPError as exc:
            with exc: return exc.code, json.loads(exc.read())
    def test_real_handler_queue_job_and_observation(self):
        code, result = self.request(PREFIX, self.value); self.assertEqual(code, 200, result)
        self.assertFalse(self.studio.jobs)
        report = result['record']['report']; payload = {'ticket': report['ticket'], 'approved': True}
        code, first = self.request('/api/workflow-studio/run', payload); self.assertEqual(code, 200, first)
        self.assertEqual(first['job']['id'], report['job_id'])
        self.assertTrue(self.request('/api/workflow-studio/run', payload)[1]['replayed'])
        code, observed = self.request(PREFIX + '/prepared-run/observe'); self.assertEqual(code, 200, observed)
        self.assertEqual(observed['observation']['state'], 'observed')
        self.assertEqual(observed['observation']['job']['id'], report['job_id'])
        self.assertEqual(self.studio.queue.qsize(), 1); self.assertEqual(len(self.studio.jobs), 1)
    def test_real_security_resource_failure_and_revision_conflict(self):
        self.assertEqual(self.request(PREFIX, self.value, 'https://untrusted.invalid')[0], 403)
        with patch.object(self.studio, 'host_commit_preflight', side_effect=self.server_module.StudioError('Resource gate')):
            code, result = self.request(PREFIX, self.value)
            self.assertEqual(code, 400, result); self.assertIn('Resource gate', result['error'])
        self.assertFalse(self.studio.jobs)
        self.assertEqual(self.request(PREFIX + '/prepared-run')[0], 404)
        documents(self.studio).command(self.source['id'], {'request_id': 'edit', 'expected_revision': 1,
            'commands': [{'op': 'rename', 'name': 'Later'}]})
        self.assertEqual(self.request(PREFIX, self.value)[0], 409)
        self.assertFalse(self.studio.jobs); self.assertEqual(self.studio.queue.qsize(), 0)
