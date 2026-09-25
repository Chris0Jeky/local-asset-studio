"""Conditional GET /api/jobs via a strong ETag over the exact response bytes (#971)."""
import hashlib
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_server import GRAPH, PRESET, server


class JobsEtagHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        for name in ('presets', 'workflows/api', 'config', 'fake-comfy/input'):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        (self.root / 'config/local.json').write_text(json.dumps({'comfy_root': str(self.root / 'fake-comfy')}))
        (self.root / 'presets/catalog.json').write_text(json.dumps({'presets': [PRESET]}))
        (self.root / 'workflows/api/demo-api.json').write_text(json.dumps(GRAPH))
        with patch.object(threading.Thread, 'start', lambda *_: None):
            self.studio = server.Studio(self.root)
        self.studio.create_job({'preset_id': 'demo', 'controls': {}}, enqueue=False)
        self.studio.create_job({'preset_id': 'demo', 'controls': {}}, enqueue=False)
        handler = type('JobsEtagHandler', (server.Handler,), {'studio': self.studio})
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close)

    def tearDown(self):
        self.tmp.cleanup()

    def close(self):
        if self.thread.is_alive():
            self.http.shutdown()
        self.http.server_close()
        self.thread.join(3)

    def request(self, headers=None):
        connection = HTTPConnection('127.0.0.1', self.http.server_port, timeout=5)
        try:
            connection.request('GET', '/api/jobs', None,
                               {'Host': '127.0.0.1:8191', **(headers or {})})
            if connection.sock:
                try:
                    connection.sock.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
            response = connection.getresponse()
            return response.status, response.read(), {k.lower(): v for k, v in response.getheaders()}
        finally:
            connection.close()

    def expected(self):
        return [self.studio.public(x) for x in
                sorted(self.studio.jobs.values(), key=lambda j: j['created_at'], reverse=True)]

    def test_first_response_carries_strong_etag_over_exact_bytes(self):
        status, body, headers = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(headers.get('content-type'), 'application/json')
        self.assertEqual(json.loads(body), self.expected())
        etag = headers.get('etag')
        self.assertEqual(etag, '"' + hashlib.sha256(body).hexdigest() + '"')

    def test_identical_conditional_get_is_bodyless_304_with_same_etag(self):
        _, body, headers = self.request()
        etag = headers['etag']
        status, replay, replay_headers = self.request({'If-None-Match': etag})
        self.assertEqual(status, 304)
        self.assertEqual(replay, b'')
        self.assertEqual(replay_headers.get('etag'), etag)
        try:
            json.loads(replay)
        except ValueError:
            pass
        else:
            self.fail('304 must carry no JSON body')

    def test_changed_public_row_returns_200_with_different_etag(self):
        _, _, headers = self.request()
        stale = headers['etag']
        job = next(iter(self.studio.jobs.values()))
        job['message'] = 'Changed public row for conditional polling'
        self.studio._save(job)
        status, body, fresh_headers = self.request({'If-None-Match': stale})
        self.assertEqual(status, 200)
        self.assertNotEqual(fresh_headers.get('etag'), stale)
        self.assertEqual(fresh_headers.get('etag'), '"' + hashlib.sha256(body).hexdigest() + '"')
        self.assertIn('Changed public row for conditional polling',
                      [row['message'] for row in json.loads(body)])
        status, replay, replay_headers = self.request({'If-None-Match': fresh_headers['etag']})
        self.assertEqual(status, 304)
        self.assertEqual(replay, b'')
        self.assertEqual(replay_headers.get('etag'), fresh_headers['etag'])


class JobsEtagFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is needed to exercise shipped browser polling')
    def test_conditional_polling_preserves_state_on_304(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node', 'tests/jobs_etag_frontend.cjs'],
                                cwd=root, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
