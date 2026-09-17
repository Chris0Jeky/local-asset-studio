"""Early HTTP refusals drain only safely declared request bodies."""
import io
import unittest

from studio_prompt.http_extension import extend_handler
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

    def test_pathological_digit_length_cannot_escape_refusal(self):
        handler = request('/api/prompt/compile', b'x', safe=True, content_type='text/plain')
        handler.headers['Content-Length'] = '9' * 5000
        self.assertFalse(drain_declared_body(handler))
        self.assertEqual(handler.rfile.tell(), 0)
        status, value = handler.do_POST()
        self.assertEqual(status, 400)
        self.assertEqual(value['error'], 'application/json required')
        self.assertEqual(handler.rfile.tell(), 0)

    def test_exact_bound_and_zero_length_are_supported(self):
        handler = request('/unused', b'x' * DRAIN_LIMIT)
        self.assertTrue(drain_declared_body(handler))
        self.assertEqual(handler.rfile.tell(), DRAIN_LIMIT)
        empty = request('/unused', b'')
        self.assertTrue(drain_declared_body(empty))


if __name__ == '__main__':
    unittest.main()