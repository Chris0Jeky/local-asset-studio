"""Scope is verified by production HTTP/SQLite, not only by the browser cache."""
import tempfile
import unittest
import test_asset_metadata_http as metadata_http
from test_server import server


class AssetWorkspaceHTTP(unittest.TestCase):
    setUp = metadata_http.AssetMetadataHTTP.setUp
    tearDown = metadata_http.AssetMetadataHTTP.tearDown
    request = metadata_http.AssetMetadataHTTP.request
    command = metadata_http.AssetMetadataHTTP.command

    def test_metadata_and_receipts_have_a_bound_read_scope(self):
        identity = self.store.snapshot()['workspace_id']
        command = self.command(workspace_id=identity)
        status, saved, _ = self.request('POST', '/api/assets/update', command)
        self.assertEqual(status, 200)
        query = '?workspace_id=' + identity
        for route in ['/api/assets/' + self.asset + '/metadata', '/api/assets/commands/' + command['request_id']]:
            status, data, headers = self.request('GET', route + query)
            self.assertEqual(status, 200); self.assertEqual(data['workspace_id'], identity)
            self.assertEqual(headers['Cache-Control'], 'no-store')
            status, data, _ = self.request('GET', route + '?workspace_id=' + 'b'*32)
            self.assertEqual(status, 409); self.assertEqual(data['code'], 'asset_workspace_conflict')
            self.assertNotIn('current', data)
        self.assertEqual(self.store.get(self.asset)['metadata_revision'], 1)

    def test_blank_or_repeated_scope_is_not_silently_treated_as_absent(self):
        route = '/api/assets/' + self.asset + '/metadata'
        for query in ['?workspace_id=', '?workspace_id=' + 'a'*32 + '&workspace_id=' + 'b'*32]:
            status, _, _ = self.request('GET', route + query)
            self.assertEqual(status, 400)

    def test_workspace_switch_between_requests_rejects_the_metadata_read(self):
        status, snapshot, _ = self.request('GET', '/api/workspace')
        self.assertEqual(status, 200)
        with tempfile.TemporaryDirectory() as root:
            replacement = server.AssetWorkspace(root)
            self.http.RequestHandlerClass.studio.assets = replacement
            try:
                for route in ['/api/assets/' + self.asset + '/metadata', '/api/assets/commands/' + 'c'*32]:
                    status, data, _ = self.request('GET', route + '?workspace_id=' + snapshot['workspace_id'])
                    self.assertEqual(status, 409); self.assertEqual(data['code'], 'asset_workspace_conflict')
                    self.assertNotIn('current', data)
            finally:
                self.http.RequestHandlerClass.studio.assets = self.store
