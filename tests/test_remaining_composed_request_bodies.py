"""EOF-short commands must not save drafts or reach execution/service owners."""
import copy
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from http_test_server import ThreadingHTTPServer
import test_composed_request_bodies as transport
import test_recipe_shortlist_apply as setups
from test_server import server
from studio_workflow.setup_drafts import PREFIX


class RemainingComposedRequestBodyTests(unittest.TestCase):
    def setUp(self):
        setups.SetupApplyTests.setUp(self)
        self.studio = self.s

        class Handler(server.extend_handler(server.Handler)):
            studio = self.studio

        self.http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.http.server_close)
        self.addCleanup(self.http.shutdown)

    post = transport.ComposedRequestBodyTests.post
    store = setups.SetupApplyTests.store
    command = setups.SetupApplyTests.command
    create = setups.SetupApplyTests.create

    def incomplete(self, path, payload):
        status, value = self.post(path, payload, missing=7)
        self.assertEqual(status, 400, value)
        self.assertEqual(value['error'], 'Incomplete request body')
        return value

    def dump(self):
        with self.s.assets.connection() as db:
            return list(db.iterdump())

    def test_truncated_setup_create_preserves_database_and_request_identity(self):
        repository = self.store()
        before = self.dump()
        payload = dict(action='create', workspace_id=self.scope,
                       request_id='create-http', draft=self.before)
        self.assertFalse(self.incomplete(PREFIX, payload)['generation_submitted'])
        self.assertEqual(self.dump(), before)
        self.assertEqual(repository.list()['drafts'], [])
        status, result = self.post(PREFIX, payload)
        self.assertEqual(status, 200, result)
        self.assertEqual(result['revision'], 1)
        self.assertFalse(result['replayed'])
        self.assertEqual(self.s.upload_count, 0)

    def test_truncated_setup_replace_preserves_head_history_and_receipts(self):
        created = self.create()
        changed = copy.deepcopy(self.before)
        changed['recipe']['controls']['positive'] = 'Changed'
        payload = dict(action='replace', workspace_id=self.scope, request_id='replace-http',
                       draft_id=created['draft_id'], expected_revision=1, draft=changed)
        before = self.dump()
        self.assertFalse(self.incomplete(PREFIX, payload)['generation_submitted'])
        self.assertEqual(self.dump(), before)
        self.assertEqual(self.store().get(created['draft_id'])['draft'], self.before)
        status, result = self.post(PREFIX, payload)
        self.assertEqual(status, 200, result)
        self.assertEqual(result['revision'], 2)
        self.assertEqual(result['draft'], changed)
        self.assertFalse(result['replayed'])
        self.assertEqual(self.store().get(created['draft_id'], 1)['draft'], self.before)
        self.assertEqual(self.s.upload_count, 0)

    def test_truncated_control_preview_never_reaches_planner(self):
        path = '/api/workflow-studio/control-preview'
        payload = {'value': 12}
        with patch('studio_workflow.control_http.request', return_value={'committed': False}) as planner:
            value = self.incomplete(path, payload)
            self.assertFalse(value['committed'])
            self.assertFalse(value['generation_submitted'])
            planner.assert_not_called()
            self.assertEqual(self.post(path, payload), (200, {'committed': False}))
            planner.assert_called_once_with(payload, self.studio)

    def test_truncated_workflow_commands_never_reach_dispatch(self):
        for action in ('import', 'run'):
            path = '/api/workflow-studio/' + action
            payload = {'ticket': 'inert-ticket', 'approved': True}
            with self.subTest(action=action), patch(
                    'studio_workflow.http_extension.post', return_value={'accepted': True}) as dispatch:
                value = self.incomplete(path, payload)
                if action == 'run':
                    self.assertNotIn('generation_submitted', value)
                    self.assertIn('recovery', value)
                else:
                    self.assertFalse(value['generation_submitted'])
                dispatch.assert_not_called()
                self.assertEqual(self.post(path, payload), (200, {'accepted': True}))
                dispatch.assert_called_once_with(path, payload, self.studio)

    def test_truncated_saved_run_commands_never_reach_preparation_or_dispatch(self):
        for suffix in ('', '/inert-record/run'):
            path = '/api/workflow-studio/document-runs' + suffix
            payload = {'request_id': 'inert-request'}
            with self.subTest(suffix=suffix), patch(
                    'studio_workflow.run_http.route', return_value={'accepted': True}) as dispatch:
                value = self.incomplete(path, payload)
                self.assertIs(value['dispatch_attempted'], False)
                dispatch.assert_not_called()
                self.assertEqual(self.post(path, payload), (200, {'accepted': True}))
                dispatch.assert_called_once_with(self.studio, path, payload)

    def test_truncated_reference_commands_never_reach_service_and_release_intake(self):
        intake = threading.BoundedSemaphore(1)
        service = SimpleNamespace(intake=intake, _create=Mock(), cancel=Mock(),
                                  release=Mock(), retire=Mock())
        self.studio.reference_jobs = service
        for action in ('create', 'cancel', 'release', 'retire'):
            path = '/api/prompt/reference-jobs/' + action
            payload = {'request_id': 'inert-' + action}
            command = getattr(service, '_create' if action == 'create' else action)
            command.return_value = {'accepted': True}
            with self.subTest(action=action):
                self.assertFalse(self.incomplete(path, payload)['generation_submitted'])
                command.assert_not_called()
                # Receiving the response can precede the handler's finally release.
                self.assertTrue(intake.acquire(timeout=5), 'EOF refusal leaked intake admission')
                intake.release()
                self.assertEqual(self.post(path, payload),
                                 (202 if action == 'create' else 200, {'accepted': True}))
                command.assert_called_once_with(payload)
                self.assertTrue(intake.acquire(timeout=5))
                intake.release()

    def test_truncated_resource_cleanup_never_initializes_controller(self):
        path = '/api/large-job-preparation'
        payload = {'request_id': 'inert-cleanup'}
        controller = SimpleNamespace(run=Mock(return_value={'generation_submitted': False}))
        with patch('large_job_preparation.controller_for', return_value=controller) as factory:
            self.assertFalse(self.incomplete(path, payload)['generation_submitted'])
            factory.assert_not_called()
            controller.run.assert_not_called()
            self.assertEqual(self.post(path, payload), (200, {'generation_submitted': False}))
            factory.assert_called_once_with(self.studio)
            controller.run.assert_called_once_with(payload)


if __name__ == '__main__':
    unittest.main()
