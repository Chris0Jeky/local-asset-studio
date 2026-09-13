"""The SDK's structured errors do not break existing raw Client callers."""
import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from studio_workflow.client import Client, ClientError


class TransportCompatibilityTests(unittest.TestCase):
    def test_legacy_routes_keep_original_http_error(self):
        client = Client()
        response = HTTPError(client.base + '/api/workflow-studio/open', 400, 'Bad Request', {}, io.BytesIO(b'{"error":"duplicate"}'))
        with patch.object(client.opener, 'open', side_effect=response):
            with self.assertRaises(HTTPError) as caught: client.request('/api/workflow-studio/open', {'content': '{}'})
        self.assertIs(caught.exception, response); response.close()
    def test_document_routes_keep_machine_conflict_code(self):
        client = Client()
        response = HTTPError(client.base, 409, 'Conflict', {}, io.BytesIO(b'{"error":"stale","code":"revision_conflict"}'))
        with patch.object(client.opener, 'open', side_effect=response):
            with self.assertRaises(ClientError) as caught: client.request('/api/workflow-studio/documents/id/commands', {})
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(caught.exception.code, 'revision_conflict')
        self.assertTrue(response.closed)
