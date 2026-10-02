"""Consumed HTTP errors release their responses, even while retaining the cause."""
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import spoken_brief_transport as transport
import test_collection_command_http as collection_http
from spoken_brief_fixture import Fixture


class ErrorBody(io.BytesIO):
    def __init__(self, raw, failure=None):
        super().__init__(raw)
        self.failure = failure
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        if self.failure is not None:
            raise self.failure
        return super().read(size)


class HTTPErrorOwnershipTests(unittest.TestCase):
    def error(self, raw=b'{"error":"explicit rejection"}', code=400, failure=None):
        body = ErrorBody(raw, failure)
        error = HTTPError('http://127.0.0.1:8191/test', code, 'synthetic response', {}, body)
        self.addCleanup(error.close)
        return error, body

    def client(self, error):
        client = transport.StudioClient()
        client.opener = SimpleNamespace(open=Mock(side_effect=error))
        return client

    def test_json_errors_close_after_bounded_read_and_keep_classification_and_cause(self):
        for code, expected in ((400, transport.StudioRejected), (503, transport.SpokenBriefError),
                               (302, transport.SpokenBriefError)):
            with self.subTest(code=code):
                error, body = self.error(code=code)
                client = self.client(error)
                with self.assertRaises(expected) as caught:
                    client.post_json('/test', {'request_id': 'retained-command'})
                self.assertIs(type(caught.exception), expected)
                self.assertEqual(str(caught.exception), 'explicit rejection')
                self.assertIs(caught.exception.__cause__, error)
                self.assertEqual(body.read_sizes, [transport.MAX_ERROR_BYTES + 1])
                client.opener.open.assert_called_once()
                self.assertTrue(body.closed, 'Consumed error response remains open')

    def test_unusable_error_json_closes_and_retains_status_fallback(self):
        for raw in (b'{', b'\xff', b'[]', b'{}', b'x' * 17):
            with self.subTest(raw=raw):
                error, body = self.error(raw)
                client = self.client(error)
                with patch.object(transport, 'MAX_ERROR_BYTES', 16):
                    with self.assertRaisesRegex(transport.StudioRejected, 'Studio returned HTTP 400 for /test') as caught:
                        client.get_json('/test')
                self.assertIs(caught.exception.__cause__, error)
                self.assertEqual(body.read_sizes, [17])
                client.opener.open.assert_called_once()
                self.assertTrue(body.closed, 'Malformed or oversized response remains open')

    def test_error_body_read_failure_closes_without_retrying_or_reclassifying(self):
        failure = OSError('synthetic read failure')
        error, body = self.error(failure=failure)
        client = self.client(error)
        with self.assertRaises(OSError) as caught:
            client.post_json('/test', {})
        self.assertIs(caught.exception, failure)
        self.assertEqual(body.read_sizes, [transport.MAX_ERROR_BYTES + 1])
        client.opener.open.assert_called_once()
        self.assertTrue(body.closed, 'Failed error-body read leaves its response open')

    def test_artifact_http_error_closes_without_reading_and_keeps_the_cause(self):
        error, body = self.error(code=404)
        client = self.client(error)
        with self.assertRaisesRegex(transport.SpokenBriefError, 'Cannot download retained voice artifact /test') as caught:
            client.get_bytes('/test')
        self.assertIs(type(caught.exception), transport.SpokenBriefError)
        self.assertIs(caught.exception.__cause__, error)
        self.assertEqual(body.read_sizes, [])
        client.opener.open.assert_called_once()
        self.assertTrue(body.closed, 'Artifact error retains an open response through its cause')

    def test_collection_helper_closes_consumed_errors_and_parse_or_read_failures(self):
        for raw, failure in ((b'{"error":"synthetic collection refusal"}', None), (b'{', None),
                             (b'', OSError('synthetic collection read failure'))):
            with self.subTest(raw=raw, failure=failure):
                error, body = self.error(raw, failure=failure)
                with patch.object(collection_http, 'urlopen', side_effect=error) as opener:
                    if failure is not None:
                        with self.assertRaises(OSError) as caught:
                            collection_http.CollectionHTTPTests.call(SimpleNamespace(origin='http://127.0.0.1:8191'))
                        self.assertIs(caught.exception, failure)
                    elif raw == b'{':
                        with self.assertRaises(json.JSONDecodeError):
                            collection_http.CollectionHTTPTests.call(SimpleNamespace(origin='http://127.0.0.1:8191'))
                    else:
                        result = collection_http.CollectionHTTPTests.call(SimpleNamespace(origin='http://127.0.0.1:8191'))
                        self.assertEqual(result, (400, {'error': 'synthetic collection refusal'}))
                opener.assert_called_once()
                self.assertTrue(body.closed, 'Collection helper leaves its consumed error open')

    def test_real_http_errors_are_closed_while_retained_as_causes(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        client = transport.StudioClient(fixture.base_url)
        cases = ((400, 'POST', '/api/voice-baseline', transport.StudioRejected),
                 (503, 'POST', '/api/voice-baseline', transport.SpokenBriefError),
                 (302, 'GET', '/api/identity', transport.SpokenBriefError),
                 (404, 'artifact', '/missing.wav', transport.SpokenBriefError))
        for code, method, path, expected in cases:
            with self.subTest(code=code, method=method):
                fixture.create_rejection = code
                fixture.identity_redirect = '/redirected-identity' if code == 302 else None
                before = len(fixture.requests)
                with self.assertRaises(expected) as caught:
                    if method == 'POST': client.post_json(path, {})
                    elif method == 'artifact': client.get_bytes(path)
                    else: client.get_json(path)
                error = caught.exception.__cause__
                self.assertIsInstance(error, HTTPError)
                self.addCleanup(error.close)
                self.assertEqual(error.code, code)
                self.assertIs(type(caught.exception), expected)
                self.assertEqual(len(fixture.requests) - before, 1, 'Error response retried or followed a redirect')
                self.assertTrue(error.closed, 'Real HTTP error retains an open response through its cause')


if __name__ == '__main__': unittest.main()
