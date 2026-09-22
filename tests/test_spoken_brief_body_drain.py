"""Spoken Brief refusals drain an unread declared body before closing (#837), and never read a consumed one twice."""
from email.message import Message
import io
import json
from types import SimpleNamespace
import unittest

from studio_spoken import http as spoken
from studio_workflow.http_body import DRAIN_LIMIT


class Base:
    def _json(self, status, value):
        self.response = status, value
        return self.response

    def do_POST(self):
        raise AssertionError('Spoken Brief route fell through')

    def do_GET(self):
        raise AssertionError('Spoken Brief route fell through')


class Handler(spoken.extend_handler(Base)):
    origin_ok = True

    def _spoken_origin(self): return self.origin_ok
    def _spoken_host(self): return True


def request(body, *, trailing=b'', length=None, method_path='/api/spoken-briefs/bookmark?key=brief', content_type='application/json'):
    handler = Handler(); handler.path = method_path
    headers = Message(); headers['Content-Length'] = str(len(body) if length is None else length); headers['Content-Type'] = content_type
    handler.headers = headers; handler.rfile = io.BytesIO(body + trailing)
    handler.connection = SimpleNamespace(gettimeout=lambda: None, settimeout=lambda value: None)
    return handler


class SpokenBriefBodyDrainTests(unittest.TestCase):
    def test_oversized_refusal_consumes_the_declared_body(self):
        body = b'x' * (spoken.MAX_BODY_BYTES + 1)
        handler = request(body, trailing=b'NEXT')
        status, value = handler.do_POST()
        self.assertEqual(status, 413); self.assertFalse(value['generation_submitted'])
        self.assertEqual(handler.rfile.read(), b'NEXT'); self.assertTrue(handler.close_connection)

    def test_pre_read_refusals_consume_small_declared_bodies(self):
        cases = (
            (request(b'{"sample":1}', content_type='text/plain'), 400),
            (request(b'{"sample":1}', method_path='/api/spoken-briefs/start?key=brief'), 404),
        )
        for handler, code in cases:
            with self.subTest(code=code, path=handler.path):
                status, _ = handler.do_POST()
                self.assertEqual(status, code); self.assertEqual(handler.rfile.read(), b'')
        refused = request(b'{"sample":1}'); refused.origin_ok = False
        self.assertEqual(refused.do_POST()[0], 403); self.assertEqual(refused.rfile.read(), b'')

    def test_consumed_body_is_not_read_again_after_a_json_refusal(self):
        for raw in (b'{"sample":1,"sample":2}', b'{"sample":NaN}', b'{"sample":1'):
            with self.subTest(raw=raw):
                handler = request(raw, trailing=b'NEXT REQUEST')
                status, _ = handler.do_POST()
                self.assertEqual(status, 400); self.assertEqual(handler.rfile.read(), b'NEXT REQUEST')

    def test_claims_beyond_the_drain_limit_are_not_read(self):
        handler = request(b'x' * 16, length=DRAIN_LIMIT + 1)
        self.assertEqual(handler.do_POST()[0], 413); self.assertEqual(handler.rfile.tell(), 0)
        self.assertTrue(handler.close_connection)

    def test_read_request_with_a_body_is_refused_and_drained(self):
        handler = request(b'{"a":1}', method_path='/api/spoken-briefs/archives')
        status, value = handler.do_GET()
        self.assertEqual(status, 400); self.assertIn('do not accept a body', value['error'])
        self.assertEqual(handler.rfile.read(), b'')
        json.dumps(value)


if __name__ == '__main__':
    unittest.main()
