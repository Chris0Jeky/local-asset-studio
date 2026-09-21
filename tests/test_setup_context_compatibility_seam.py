"""HTTP, SDK and read-agent parity for exact setup compatibility advice."""
import copy
import json
import unittest
from unittest.mock import patch

from studio_workflow import setup_context_compatibility as evaluator
from studio_workflow.agent_bridge import AgentBridge
from studio_workflow.http_extension import capabilities, post
from studio_workflow.sdk import WorkflowClient
from test_setup_context_compatibility import request


PATH = '/api/workflow-studio/setup-compatibility'
ZERO_AUTHORITY = (
    'provider_accessed',
    'file_hashed',
    'model_downloaded',
    'installation_authorized',
    'backend_switched',
    'selection_changed',
    'generation_submitted',
)


class UntouchableStudio:
    def __getattr__(self, name):
        raise AssertionError(f'read-only compatibility route touched Studio.{name}')


class SetupContextCompatibilitySeamTests(unittest.TestCase):
    def test_capability_advertises_the_read_only_context_evaluator(self):
        self.assertIs(capabilities().get('setup_context_compatibility'), True)

    def test_http_route_is_pure_and_matches_the_local_evaluator(self):
        value = request()
        before = copy.deepcopy(value)
        result = post(PATH, value, UntouchableStudio())
        self.assertEqual(result, evaluator.evaluate(before))
        self.assertEqual(value, before)
        for field in ZERO_AUTHORITY:
            self.assertIs(result[field], False, field)

    def test_sdk_and_read_agent_return_the_same_exact_report(self):
        value = request()
        expected = evaluator.evaluate(value)
        calls = []
        client = WorkflowClient()

        def transport(path, body):
            calls.append((path, copy.deepcopy(body)))
            return post(path, body, UntouchableStudio())

        client.request = transport
        self.assertEqual(client.setup_compatibility(value), expected)

        bridge = AgentBridge(client=client, mode='read')
        definition = bridge.definitions()['setup_compatibility']
        self.assertEqual(definition['mode'], 'read')
        self.assertFalse(definition['mutating'])
        self.assertEqual(definition['inputSchema']['properties']['request_json']['maxLength'], 1048576)
        output = bridge.invoke(
            'setup_compatibility',
            {'request_json': json.dumps(value, separators=(',', ':'))},
        )
        self.assertTrue(output['ok'], output)
        self.assertEqual(json.loads(output['data_json']), expected)
        self.assertEqual([path for path, _ in calls], [PATH, PATH])
        self.assertNotIn('ticket', output['data_json'])
        self.assertNotIn('command', output['data_json'])

    def test_client_rejects_a_self_consistent_but_changed_server_report(self):
        from studio_workflow.setup_context_client import observe

        value = request()
        changed = evaluator.evaluate(value)
        changed['selection_changed'] = True
        with self.assertRaisesRegex(ValueError, 'does not match'):
            observe(lambda *_: changed, value)

    def test_client_snapshots_before_transport_can_change_caller_state(self):
        from studio_workflow.setup_context_client import observe

        value = request()
        captured = copy.deepcopy(value)

        def transport(path, body):
            self.assertEqual(path, PATH)
            result = evaluator.evaluate(body)
            value['slot']['role'] = 'checkpoint'
            return result

        self.assertEqual(observe(transport, value), evaluator.evaluate(captured))

    def test_client_bounds_request_before_copy_or_transport(self):
        from studio_workflow.setup_context_client import observe

        value = request()
        value['slot']['goal'] = 'x' * (evaluator.MAX_INPUT_BYTES + 1)

        def transport(*_):
            self.fail('oversized setup context reached transport')

        with patch(
            'studio_workflow.setup_context_client.copy.deepcopy',
            side_effect=AssertionError('unbounded copy used'),
        ), self.assertRaisesRegex(ValueError, 'exceeds 1 MiB'):
            observe(transport, value)


if __name__ == '__main__':
    unittest.main()
