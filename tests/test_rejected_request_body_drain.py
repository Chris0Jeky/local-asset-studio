"""Early HTTP refusals drain only safely declared request bodies."""
import io
from email.message import Message
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from studio_prompt.http_extension import extend_handler
from studio_workflow import http_body
from studio_workflow.http_body import DRAIN_LIMIT, drain_declared_body


class Base:
    safe = False

    def _safe_mutation(self):
        return self.safe

    def _json(self, status, value):
        self.response = status, value
        return self.response

    def do_POST(self):
        raise AssertionError('Recognized reference route fell through')


Handler = extend_handler(Base)


def request(path, body, *, safe=False, content_type='application/json'):
    handler = Handler()
    handler.safe = safe
    handler.path = path
    handler.headers = {
        'Content-Length': str(len(body)),
        'Content-Type': content_type,
    }
    handler.rfile = io.BytesIO(body)
    return handler


class RejectedRequestBodyDrainTests(unittest.TestCase):
    def test_same_origin_refusals_consume_small_declared_bodies(self):
        body = b'{"untrusted":"body"}'
        for path in (
            '/api/prompt/reference-review/preview',
            '/api/prompt/reference-jobs/retire',
            '/api/workflow-studio/setup-proposal',
        ):
            with self.subTest(path=path):
                handler = request(path, body)
                status, _ = handler.do_POST()
                self.assertEqual(status, 403)
                self.assertEqual(handler.rfile.read(), b'')
                self.assertFalse(getattr(handler, 'close_connection', False))

    def test_wrong_content_type_refusals_consume_small_declared_bodies(self):
        for path in (
            '/api/prompt/compile',
            '/api/workflow-studio/setup-proposal',
        ):
            with self.subTest(path=path):
                handler = request(path, b'not-json', safe=True, content_type='text/plain')
                status, value = handler.do_POST()
                self.assertEqual(status, 400)
                self.assertEqual(value['error'], 'application/json required')
                self.assertEqual(handler.rfile.read(), b'')
                self.assertFalse(getattr(handler, 'close_connection', False))

    def test_oversized_or_malformed_claim_is_never_drained(self):
        for length in (str(DRAIN_LIMIT + 1), '-1', 'not-a-number', '²'):
            with self.subTest(length=length):
                handler = request('/unused', b'x')
                handler.headers['Content-Length'] = length
                self.assertFalse(drain_declared_body(handler))
                self.assertEqual(handler.rfile.tell(), 0)

    def test_transfer_encoding_is_never_drained_even_with_content_length(self):
        handler = request('/api/prompt/compile', b'chunk framing', safe=True, content_type='text/plain')
        handler.headers['Transfer-Encoding'] = 'chunked'
        self.assertFalse(drain_declared_body(handler))
        self.assertEqual(handler.rfile.tell(), 0)
        status, value = handler.do_POST()
        self.assertEqual(status, 400)
        self.assertEqual(value['error'], 'application/json required')
        self.assertEqual(handler.rfile.tell(), 0)
        self.assertTrue(handler.close_connection)

    def test_duplicate_content_lengths_are_never_drained(self):
        handler = request('/api/prompt/compile', b'ab', safe=True, content_type='text/plain')
        headers = Message()
        headers['Content-Type'] = 'text/plain'
        headers['Content-Length'] = '1'
        headers['Content-Length'] = '2'
        handler.headers = headers
        self.assertFalse(drain_declared_body(handler))
        self.assertEqual(handler.rfile.tell(), 0)
        status, value = handler.do_POST()
        self.assertEqual(status, 400)
        self.assertEqual(value['error'], 'application/json required')
        self.assertEqual(handler.rfile.tell(), 0)
        self.assertTrue(handler.close_connection)

    def test_pathological_digit_length_cannot_escape_refusal(self):
        handler = request('/api/prompt/compile', b'x', safe=True, content_type='text/plain')
        handler.headers['Content-Length'] = '9' * 5000
        self.assertFalse(drain_declared_body(handler))
        self.assertEqual(handler.rfile.tell(), 0)
        status, value = handler.do_POST()
        self.assertEqual(status, 400)
        self.assertEqual(value['error'], 'application/json required')
        self.assertEqual(handler.rfile.tell(), 0)
        self.assertTrue(handler.close_connection)

    def test_failed_drain_marks_connection_non_reusable(self):
        handler = request('/api/prompt/compile', b'x', safe=True, content_type='text/plain')
        handler.headers['Content-Length'] = '2'
        status, value = handler.do_POST()
        self.assertEqual(status, 400)
        self.assertEqual(value['error'], 'application/json required')
        self.assertEqual(handler.rfile.read(), b'')
        self.assertTrue(handler.close_connection)

    def test_exact_bound_and_zero_length_are_supported(self):
        handler = request('/unused', b'x' * DRAIN_LIMIT)
        self.assertTrue(drain_declared_body(handler))
        self.assertEqual(handler.rfile.tell(), DRAIN_LIMIT)
        empty = request('/unused', b'')
        self.assertTrue(drain_declared_body(empty))

    def test_slow_progress_cannot_reset_the_total_drain_deadline(self):
        class Connection:
            def __init__(self):
                self.timeout = None
                self.values = []

            def gettimeout(self):
                return self.timeout

            def settimeout(self, value):
                self.timeout = value
                self.values.append(value)

        class SlowReader:
            def __init__(self):
                self.read_calls = 0
                self.read1_calls = 0

            def read(self, amount):
                self.read_calls += 1
                return b'x'

            def read1(self, amount):
                self.read1_calls += 1
                return b'x'

        handler = request('/unused', b'xxx')
        handler.connection = Connection()
        handler.rfile = SlowReader()
        clock = iter((0.0, 0.0, 0.6, 1.01))
        fake_time = SimpleNamespace(monotonic=lambda: next(clock))
        with patch.object(http_body, 'time', fake_time, create=True):
            self.assertFalse(drain_declared_body(handler))
        self.assertEqual(handler.rfile.read_calls, 0)
        self.assertEqual(handler.rfile.read1_calls, 2)
        self.assertAlmostEqual(handler.connection.values[0], 1.0)
        self.assertAlmostEqual(handler.connection.values[1], 0.4)
        self.assertIsNone(handler.connection.values[-1])


if __name__ == '__main__':
    unittest.main()
