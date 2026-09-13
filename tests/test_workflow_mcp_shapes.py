"""Malformed successful HTTP replies preserve the bridge recovery envelope."""
import unittest
from studio_workflow.agent_bridge import AgentBridge
from studio_workflow.core import canonical, digest


class Reply:
    def __init__(self, value): self.value = value; self.calls = 0
    def request(self, *args): self.calls += 1; return self.value


class MalformedReplyTests(unittest.TestCase):
    def test_wrong_node_collection_shape_is_a_structured_read_failure(self):
        client = Reply({'schema_sha256': 'a' * 64, 'nodes': []})
        result = AgentBridge(client).invoke('studio_nodes', {})
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['code'], 'request_failed')
        self.assertEqual(client.calls, 1)

    def test_wrong_job_shape_after_run_retains_ticket_recovery(self):
        client = Reply({'job': ['not a job object']})
        ticket = {'request_id': 'original-ticket'}
        result = AgentBridge(client, 'execute').invoke('recipe_run', {
            'ticket_json': canonical(ticket).decode(), 'approved_ticket_sha256': digest(ticket)})
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['code'], 'outcome_unknown')
        self.assertEqual(result['context']['request_id'], 'original-ticket')
        self.assertEqual(result['context']['ticket_sha256'], digest(ticket))
        self.assertIn('recovery', result['error']); self.assertEqual(client.calls, 1)
