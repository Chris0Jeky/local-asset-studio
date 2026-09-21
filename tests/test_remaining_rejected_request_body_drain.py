"""Regression coverage for composed POST refusal transport boundaries."""
from types import SimpleNamespace
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

MEDIA_TYPE_CASES = (
    ('/api/workflow-studio/control-preview', {'committed': False, 'generation_submitted': False}),
    ('/api/workflow-studio/setup-drafts', {'generation_submitted': False}),
    ('/api/workflow-studio/document-runs', {'dispatch_attempted': False}),
    ('/api/workflow-studio/documents', {'generation_submitted': False}),
    ('/api/prompt/projects/create', {
        'generation_submitted': False,
        'inference_submitted': False,
        'execution_authorized': False,
    }),
    ('/api/prompt/reference-jobs/retire', {'generation_submitted': False}),
    ('/api/prompt/compile', {'generation_submitted': False}),
    ('/api/assets/split-figures', {'generation_submitted': False}),
)


class Intake:
    def __init__(self, admitted=True):
        self.admitted = admitted
        self.releases = 0

    def acquire(self, blocking=False):
        return self.admitted

    def release(self):
        self.releases += 1


def reference_studio(admitted=True):
    return SimpleNamespace(reference_jobs=SimpleNamespace(intake=Intake(admitted)))


def media_request(path):
    handler = request(path, b'not-json', safe=True, content_type='text/plain')
    handler.studio = reference_studio()
    return handler


class RemainingRejectedRequestBodyDrainTests(unittest.TestCase):
    def test_same_origin_refusals_consume_small_declared_bodies(self):
        body = b'{"untrusted":"body"}'
        for path in ROUTES:
            with self.subTest(path=path):
                handler = request(path, body)
                status, _ = handler.do_POST()
                self.assertEqual(status, 403)
                self.assertEqual(handler.rfile.read(), b'')

    def test_wrong_content_type_refusals_consume_body_and_retain_safety_flags(self):
        for path, expected in MEDIA_TYPE_CASES:
            with self.subTest(path=path):
                handler = media_request(path)
                status, value = handler.do_POST()
                self.assertEqual(status, 400)
                self.assertEqual(value['error'], 'application/json required')
                self.assertEqual(handler.rfile.read(), b'')
                for key, expected_value in expected.items():
                    self.assertIs(value.get(key), expected_value)

    def test_invalid_project_routes_consume_body_and_retain_safety_flags(self):
        for path in ('/api/prompt/projects/unknown', '/api/prompt/projects/create?unexpected=1'):
            with self.subTest(path=path):
                handler = request(path, b'{}', safe=True)
                status, value = handler.do_POST()
                self.assertEqual(status, 400)
                self.assertEqual(value['code'], 'invalid_project_command')
                self.assertIs(value['generation_submitted'], False)
                self.assertIs(value['inference_submitted'], False)
                self.assertIs(value['execution_authorized'], False)
                self.assertEqual(handler.rfile.read(), b'')

    def test_reference_route_and_busy_refusals_consume_small_declared_bodies(self):
        handler = request('/api/prompt/reference-jobs/unknown', b'{}', safe=True)
        handler.studio = reference_studio()
        status, value = handler.do_POST()
        self.assertEqual(status, 400)
        self.assertEqual(value['error'], 'Unknown reference command route')
        self.assertIs(value['generation_submitted'], False)
        self.assertEqual(handler.rfile.read(), b'')

        handler = request('/api/prompt/reference-jobs/create', b'{}', safe=True)
        handler.studio = reference_studio(admitted=False)
        status, value = handler.do_POST()
        self.assertEqual(status, 409)
        self.assertEqual(value['error'], 'Reference intake is busy. Nothing was queued.')
        self.assertIs(value['generation_submitted'], False)
        self.assertEqual(handler.rfile.read(), b'')

    def test_refusal_write_failure_is_not_reclassified_or_written_twice(self):
        cases = [path for path, _ in MEDIA_TYPE_CASES]
        cases.extend(['/api/prompt/projects/unknown'])
        for path in cases:
            with self.subTest(path=path):
                handler = (media_request(path) if path != '/api/prompt/projects/unknown'
                           else request(path, b'{}', safe=True))
                handler.studio = reference_studio()
                calls = []

                def failed_write(status, value):
                    calls.append((status, value))
                    if len(calls) == 1:
                        raise BrokenPipeError('peer closed during refusal')
                    return status, value

                handler._json = failed_write
                with self.assertRaises(BrokenPipeError):
                    handler.do_POST()
                self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
