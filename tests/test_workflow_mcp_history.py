"""Read every supported history through bounded MCP pages without truncation."""
import copy
import json
import unittest
from studio_workflow.agent_bridge import AgentBridge, MAX_REPLY
from studio_workflow.core import canonical


class HistoryClient:
    def __init__(self, rows): self.rows = rows; self.calls = []
    def request(self, path, body=None):
        self.calls.append((path, body))
        return {'id': 'example', 'head_revision': max((r['revision'] for r in self.rows), default=0),
                'generation_submitted': False, 'revisions': copy.deepcopy(self.rows)}


class MCPHistoryTests(unittest.TestCase):
    def test_large_history_is_readable_completely_with_bounded_pages(self):
        # Synthetic maximum-count history, shaped like bounded node-change summaries.
        summary = {'changed_nodes': ['x' * 96 + str(i) for i in range(48)], 'omitted': {'changed_nodes': 208}}
        rows = [{'revision': r, 'summary': summary} for r in range(1, 1025)]
        self.assertGreater(len(canonical(rows)), MAX_REPLY)
        client = HistoryClient(rows); bridge = AgentBridge(client)
        before = None; seen = []
        while True:
            args = {'document_id': 'example', 'limit': 100}
            if before is not None: args['before_revision'] = before
            result = bridge.invoke('workflow_history', args)
            self.assertTrue(result['ok'], result)
            self.assertLess(len(result['data_json'].encode()), MAX_REPLY)
            page = json.loads(result['data_json']); self.assertLessEqual(len(page['revisions']), 100)
            self.assertEqual(page['revisions'][0]['summary'], summary)
            seen.extend(r['revision'] for r in page['revisions'])
            before = page['next_before_revision']
            if before is None: break
        self.assertEqual(seen, list(range(1024, 0, -1)))
        self.assertEqual(len(client.calls), 11)
        self.assertTrue(all(path == '/api/workflow-studio/documents/example/history' and body is None for path, body in client.calls))

    def test_append_cannot_shift_an_existing_revision_cursor(self):
        client = HistoryClient([{'revision': r} for r in range(1, 6)])
        bridge = AgentBridge(client)
        first = json.loads(bridge.invoke('workflow_history', {'document_id': 'example', 'limit': 2})['data_json'])
        client.rows.append({'revision': 6})
        second = json.loads(bridge.invoke('workflow_history', {'document_id': 'example', 'limit': 2,
                             'before_revision': first['next_before_revision']})['data_json'])
        self.assertEqual([r['revision'] for r in first['revisions'] + second['revisions']], [5, 4, 3, 2])
        self.assertEqual(second['head_revision'], 6)
        empty = json.loads(bridge.invoke('workflow_history', {'document_id': 'example', 'before_revision': 1})['data_json'])
        self.assertEqual(empty['revisions'], []); self.assertIsNone(empty['next_before_revision'])

    def test_history_bounds_are_checked_before_request(self):
        client = HistoryClient([]); bridge = AgentBridge(client)
        for extra in ({'limit': 0}, {'limit': 101}, {'limit': True}, {'before_revision': 0}, {'before_revision': True}):
            self.assertFalse(bridge.invoke('workflow_history', {'document_id': 'example', **extra})['ok'])
        self.assertEqual(client.calls, [])
