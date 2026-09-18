"""Regression coverage for every composed POST refusal named by #545."""
import unittest

from test_rejected_request_body_drain import request


ROUTES = (
    '/api/workflow-studio/control-preview',
    '/api/workflow-studio/setup-drafts',
    '/api/workflow-studio/document-runs',
    '/api/workflow-studio/documents',
    '/api/prompt/projects/create',
    '/api/prompt/projects/save',
    '/api/prompt/projects/restore',
)


class RemainingRejectedRequestBodyDrainTests(unittest.TestCase):
    def test_same_origin_refusals_consume_small_declared_bodies(self):
        body = b'{"untrusted":"body"}'
        for path in ROUTES:
            with self.subTest(path=path):
                handler = request(path, body)
                status, _ = handler.do_POST()
                self.assertEqual(status, 403)
                self.assertEqual(handler.rfile.read(), b'')

    def test_wrong_content_type_refusals_consume_small_declared_bodies(self):
        for path in ROUTES:
            with self.subTest(path=path):
                handler = request(path, b'not-json', safe=True, content_type='text/plain')
                status, value = handler.do_POST()
                self.assertEqual(status, 400)
                self.assertEqual(value['error'], 'application/json required')
                self.assertEqual(handler.rfile.read(), b'')


if __name__ == '__main__':
    unittest.main()
