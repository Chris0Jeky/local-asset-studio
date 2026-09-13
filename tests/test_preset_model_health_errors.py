"""A bad catalog graph produces a per-preset diagnostic, not global HTTP failure."""
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from test_server import FakeStudio, server


class GraphHealthErrorTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for name in ('config', 'presets', 'workflows/api', 'comfy/input'):
            (self.root/name).mkdir(parents=True)
        (self.root/'config/local.json').write_text(json.dumps({'comfy_root': str(self.root/'comfy')}), encoding='utf-8')
        self.graph = {'1': {'class_type': 'FixtureNode', 'inputs': {}}}
        self.presets = [{'id': name, 'name': name, 'graph': f'workflows/api/{name}.json'} for name in ('broken', 'healthy')]
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets': self.presets}), encoding='utf-8')
        for preset in self.presets:
            (self.root/preset['graph']).write_text(json.dumps(self.graph), encoding='utf-8')
        with patch.object(threading.Thread, 'start'): self.studio = FakeStudio(self.root, [])

    def assert_isolated(self):
        self.assertTrue(issubclass(server.StudioError, ValueError))
        with self.assertRaises(server.StudioError): self.studio.graph_for(self.presets[0])
        handler = type('GraphHealthHandler', (server.Handler,), {'studio': self.studio})
        http = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        worker = threading.Thread(target=http.serve_forever, daemon=True); worker.start()
        connection = HTTPConnection('127.0.0.1', http.server_port, timeout=5)
        try:
            with patch.object(self.studio, '_request', return_value={'system': {}}) as remote, \
                 patch.object(self.studio, 'node_info', return_value={'FixtureNode': {'input': {}, 'output': []}}):
                connection.request('GET', '/api/health', headers={'Host': '127.0.0.1:8191'})
                response = connection.getresponse(); report = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertTrue(report['online']); self.assertTrue(report['schema_available'])
            self.assertIn('broken', report['missing_models']); self.assertNotIn('healthy', report['missing_models'])
            self.assertIn('Dependency inspection unavailable', report['missing_models']['broken'][0])
            self.assertTrue(all(call.args[0] == '/system_stats' for call in remote.call_args_list))
        finally:
            connection.close(); http.shutdown(); http.server_close(); worker.join(5)
        self.assertFalse(self.studio.jobs); self.assertTrue(self.studio.queue.empty())

    def test_deleted_workflow_is_caught_as_valueerror_and_other_preset_stays_healthy(self):
        (self.root/self.presets[0]['graph']).unlink()
        self.assert_isolated()

    def test_invalid_workflow_is_caught_as_valueerror_and_other_preset_stays_healthy(self):
        (self.root/self.presets[0]['graph']).write_text('[]', encoding='utf-8')
        self.assert_isolated()


if __name__ == '__main__': unittest.main()
