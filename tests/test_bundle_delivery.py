"""Showcase serialization and actual Studio HTTP delivery; no Studio runtime starts."""
import importlib.util
import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('bundle_showcase_build', ROOT / 'scripts/build-bundle-showcase.py')
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


class ShowcaseModuleTests(unittest.TestCase):
    def test_checked_in_module_matches_canonical_json(self):
        self.assertEqual((ROOT / 'app/static/bundle-showcase.js').read_text(encoding='utf-8'),
                         build.render((ROOT / 'app/static/bundle-showcase.json').read_text(encoding='utf-8')))

    def test_generated_source_contains_only_serialized_json(self):
        malicious = {'version': 1, 'examples': {'x': {'caption': '</script>"; throw Error("bad") //\u2028'}}}
        emitted = build.render(json.dumps(malicious))
        payload = emitted.split('export default ', 1)[1].removesuffix(';\n')
        self.assertEqual(json.loads(payload), malicious)
        self.assertNotIn('\u2028', emitted)

    def test_invalid_schema_and_nonfinite_numbers_refuse(self):
        for source in ('[]', '{"version":2,"examples":{}}', '{"version":1,"examples":[]}',
                       '{"version":1,"examples":{"x":NaN}}'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                build.render(source)

    def test_check_is_read_only(self):
        file = ROOT / 'app/static/bundle-showcase.js'
        before = file.stat().st_mtime_ns
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/build-bundle-showcase.py'), '--check'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(file.stat().st_mtime_ns, before)


@unittest.skipUnless((ROOT / 'app/server.py').is_file(), 'Full Studio source checkout required')
class ShowcaseHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('bundle_delivery_server', ROOT / 'app/server.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Real Handler, real file serving, inert Studio: every runtime access is forbidden.
        class NoRuntime:
            def __getattr__(self, name):
                raise AssertionError('Unexpected Studio runtime access: ' + name)
        cls.handler = type('BundleDeliveryHandler', (module.Handler,), {'studio': NoRuntime()})
        cls.http = ThreadingHTTPServer(('127.0.0.1', 0), cls.handler)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown(); cls.http.server_close(); cls.thread.join(timeout=5)

    def get(self, path, host='127.0.0.1:8191'):
        connection = HTTPConnection('127.0.0.1', self.http.server_port, timeout=5)
        try:
            connection.request('GET', path, headers={'Host': host})
            response = connection.getresponse()
            return response.status, response.getheader('Content-Type'), response.read()
        finally:
            connection.close()

    def test_browser_payload_is_served_with_javascript_mime_and_exact_bytes(self):
        status, mime, body = self.get('/static/bundle-showcase.js')
        self.assertEqual(status, 200)
        self.assertIn(mime, ('text/javascript', 'application/javascript'))
        self.assertEqual(body, (ROOT / 'app/static/bundle-showcase.js').read_bytes())

    def test_raw_json_remains_denied(self):
        self.assertEqual(self.get('/static/bundle-showcase.json')[0], 404)

    def test_foreign_host_remains_denied(self):
        self.assertEqual(self.get('/static/bundle-showcase.js', 'attacker.invalid')[0], 403)

    def test_path_escape_and_unknown_file_remain_denied(self):
        self.assertEqual(self.get('/static/../../config/local.json')[0], 400)
        self.assertEqual(self.get('/static/bundle-not-found.js')[0], 404)
