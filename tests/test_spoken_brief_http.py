"""Real HTTP checks over synthetic, verified archives; no Studio worker."""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import importlib.util
import json
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from urllib.parse import urlencode
from unittest.mock import patch

import test_spoken_brief_exports as fixtures
from spoken_brief_archive import inspect_run
from spoken_brief_compile import canonical_digest
from spoken_brief_exports import load_playback
from spoken_brief_qa import FINDINGS


class InertHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def _safe_host(self): return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'
    def _safe_mutation(self): return self._safe_host() and self.headers.get('Origin') == 'http://' + self.headers['Host']
    def _json(self, code, value):
        raw = json.dumps(value).encode()
        self.send_response(code); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self): self._json(418, {'base': True})
    def do_POST(self): self._json(418, {'base': True})


class SpokenHTTPTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('studio_spoken.http'), 'Spoken HTTP extension is missing')
        self.m = importlib.import_module('studio_spoken.http')
        self.f = fixtures.ExportTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.archive = inspect_run(self.f.directory); self.pin = self.archive['chapters_sha256']
        self.key = self.f.directory.relative_to(self.f.source.parent).as_posix()
        handler = self.m.extend_handler(InertHandler)
        handler.studio = SimpleNamespace(config={'spoken_briefs': {'archive_root': str(self.f.source.parent)}})
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01})
        self.thread.start(); self.addCleanup(self.stop)
        self.origin = f'http://127.0.0.1:{self.server.server_port}'

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(5)
        self.assertFalse(self.thread.is_alive())

    def request(self, route, *, query=None, method='GET', body=None, headers=None):
        path = '/api/spoken-briefs' + route
        if query: path += '?' + urlencode(query)
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse(); return response.status, dict(response.getheaders()), response.read()
        finally: conn.close()

    def mutation(self, route='/bookmark', value=None, **kwargs):
        headers = {'Origin': self.origin, 'Content-Type': 'application/json'}
        headers.update(kwargs.pop('headers', {}))
        return self.request(route, query={'key': self.key}, method='POST',
            body=json.dumps(value if value is not None else self.bookmark()), headers=headers, **kwargs)

    def bookmark(self):
        return {'archive_sha256': self.pin, 'expected_playback_sha256': canonical_digest(load_playback(self.f.directory)),
                'sample': 5, 'rate': 1, 'loop': None}

    def audio_query(self): return {'key': self.key, 'archive_sha256': self.pin, 'target': 'master'}

    def test_only_explicit_archive_read_discovers_content(self):
        with patch('studio_spoken.core.ArchiveAccess.archives', side_effect=AssertionError('No scan on load')):
            code, _, raw = self.request('/capabilities')
        self.assertEqual(200, code); self.assertTrue(json.loads(raw)['enabled'])
        code, _, raw = self.request('/archives')
        self.assertEqual(200, code); self.assertEqual(self.key, json.loads(raw)['archives'][0]['key'])
        code, _, raw = self.request('/archive', query={'key': self.key})
        self.assertEqual(self.pin, json.loads(raw)['archive_sha256']); self.assertEqual(200, code)
        self.assertFalse((self.f.directory / 'playback.json').exists())

    def test_unrelated_routes_delegate_without_changing_existing_handler(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            conn.request('GET', '/api/unrelated'); response = conn.getresponse(); response.read()
            self.assertEqual(418, response.status)
        finally: conn.close()

    def test_unknown_owned_routes_and_query_fields_are_refused(self):
        self.assertEqual(404, self.request('/unknown')[0])
        self.assertEqual(400, self.request('/archive', query=[('key', self.key), ('key', self.key)])[0])
        self.assertEqual(400, self.request('/capabilities', query={'auto_start': '1'})[0])
        self.assertEqual(400, self.request('/archive', query={'key': '../outside'})[0])
        self.assertEqual(404, self.mutation('/start')[0])

    def test_host_and_exact_origin_are_required(self):
        self.assertEqual(403, self.request('/archives', headers={'Host': 'evil.example'})[0])
        for origin in ('https://127.0.0.1', 'null', self.origin + '/', 'http://localhost:' + str(self.server.server_port)):
            self.assertEqual(403, self.mutation(headers={'Origin': origin})[0])
        self.assertFalse((self.f.directory / 'playback.json').exists())

    def test_strict_json_and_bounded_framing(self):
        headers = {'Origin': self.origin, 'Content-Type': 'application/json'}
        for raw in ('{"sample":1,"sample":2}', '{"sample":NaN}', '[]', '{"sample":' + '9' * 5000 + '}', '{"x":"\\ud800"}'):
            code, _, _ = self.request('/bookmark', query={'key': self.key}, method='POST', body=raw, headers=headers)
            self.assertEqual(400, code)
        self.assertEqual(413, self.request('/bookmark', query={'key': self.key}, method='POST',
            body='x' * (self.m.MAX_BODY_BYTES + 1), headers=headers)[0])
        self.assertEqual(400, self.mutation(headers={'Content-Type': 'text/plain'})[0])
        self.assertEqual(400, self.mutation(headers={'Transfer-Encoding': 'identity'})[0])
        self.assertFalse((self.f.directory / 'playback.json').exists())

    def test_bookmark_conflict_is_visible_and_keeps_newer_state(self):
        body = self.bookmark()
        self.assertEqual(200, self.mutation(value=body)[0])
        body['sample'] = 8
        code, _, raw = self.mutation(value=body)
        self.assertEqual(409, code); self.assertFalse(json.loads(raw)['generation_submitted'])
        self.assertEqual(5, load_playback(self.f.directory)['sample'])

    def test_review_does_not_submit_generation(self):
        segment = self.archive['segments'][0]
        body = {'archive_sha256': self.pin, 'target': segment['id'], 'audio_sha256': segment['audio_sha256'],
                'decision': 'replace', 'findings': {k: 'not-reviewed' for k in FINDINGS},
                'reviewer': 'owner', 'reason': 'Check the word', 'report_sha256': None}
        code, _, raw = self.mutation('/review', body)
        self.assertEqual(200, code); identifier = json.loads(raw)['id']
        code, _, raw = self.request('/review', query={'key': self.key, 'archive_sha256': self.pin, 'id': identifier})
        self.assertEqual('replace', json.loads(raw)['decision']); self.assertEqual(200, code)
        self.assertFalse((self.f.directory / 'replacements').exists())

    def test_full_audio_and_ranges_use_actual_checked_bytes(self):
        expected = self.f.output.read_bytes(); query = self.audio_query()
        code, headers, raw = self.request('/audio', query=query)
        self.assertEqual(200, code); self.assertEqual(expected, raw)
        self.assertEqual('audio/wav', headers['Content-Type']); self.assertEqual('no-store', headers['Cache-Control'])
        for range_header, data in [('bytes=0-43', expected[:44]), ('bytes=44-', expected[44:]), ('bytes=-9', expected[-9:])]:
            code, headers, raw = self.request('/audio', query=query, headers={'Range': range_header})
            self.assertEqual(206, code); self.assertEqual(data, raw); self.assertIn('Content-Range', headers)
        code, headers, raw = self.request('/audio', query=query, method='HEAD', headers={'Range': 'bytes=0-3'})
        self.assertEqual(200, code); self.assertEqual(b'', raw); self.assertEqual(str(len(expected)), headers['Content-Length'])

    def test_invalid_range_stale_identity_and_corrupt_media_never_serve_audio(self):
        for header in ('bytes=9999999-', 'bytes=3-2', 'bytes=0-1,4-5', 'bytes=-0', 'bytes=' + '9'*10000 + '-', 'cats=0-1'):
            code, headers, raw = self.request('/audio', query=self.audio_query(), headers={'Range': header})
            self.assertEqual(416, code); self.assertTrue(headers['Content-Range'].startswith('bytes */'))
        query = self.audio_query(); query['archive_sha256'] = 'e' * 64
        self.assertEqual(409, self.request('/audio', query=query)[0])
        self.f.output.write_bytes(b'invalid')
        self.assertEqual(400, self.request('/audio', query=self.audio_query())[0])

    def test_audio_if_range_mismatch_gets_full_current_bytes(self):
        code, _, raw = self.request('/audio', query=self.audio_query(), headers={'Range': 'bytes=0-3', 'If-Range': '"old"'})
        self.assertEqual(200, code); self.assertEqual(self.f.output.read_bytes(), raw)

    def test_chapters_and_audio_downloads_are_identity_named(self):
        query = {'key': self.key, 'archive_sha256': self.pin}
        code, headers, raw = self.request('/chapters', query=query)
        self.assertEqual(200, code); self.assertEqual(self.pin, json.loads(raw)['chapters_sha256'])
        self.assertIn(self.archive['manifest_sha256'][:12], headers['Content-Disposition'])
        query = self.audio_query(); query['download'] = '1'
        code, headers, _ = self.request('/audio', query=query)
        self.assertEqual(200, code); self.assertTrue(headers['Content-Disposition'].startswith('attachment;'))

    def test_duplicate_host_or_content_length_are_rejected(self):
        for duplicated in ('Host', 'Content-Length', 'Origin'):
            conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
            try:
                conn.putrequest('POST', '/api/spoken-briefs/bookmark?' + urlencode({'key': self.key}), skip_host=True)
                values = {'Host': self.origin.removeprefix('http://'), 'Content-Length': '2', 'Origin': self.origin, 'Content-Type': 'application/json'}
                for name, value in values.items():
                    conn.putheader(name, value)
                    if name == duplicated: conn.putheader(name, value)
                conn.endheaders(b'{}'); response = conn.getresponse(); response.read()
                self.assertIn(response.status, (400, 403))
            finally: conn.close()

    def test_unrelated_head_retains_base_unsupported_method_response(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            conn.request('HEAD', '/unrelated'); response = conn.getresponse(); response.read()
            self.assertEqual(501, response.status)
        finally: conn.close()


if __name__ == '__main__': unittest.main()
