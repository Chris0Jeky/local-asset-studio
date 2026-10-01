"""The real composed Studio handler exposes the read-only family contract."""
import tempfile
import threading
import unittest
from pathlib import Path

import test_asset_metadata_http as metadata_http
from test_asset_family import FamilyFixture
from test_server import server


class AssetFamilyHTTPTests(unittest.TestCase):
    request = metadata_http.AssetMetadataHTTP.request
    tearDown = metadata_http.AssetMetadataHTTP.tearDown

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.studio = FamilyFixture(self.temp.name)
        self.http = server.create_server(Path(self.temp.name), host='127.0.0.1', port=0,
                                        studio_factory=lambda _: self.studio)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True); self.thread.start()

    def test_family_and_recall_have_real_production_routes_and_no_store_headers(self):
        before = self.studio.assets.snapshot()
        for action in ('family', 'recall'):
            path = '/api/assets/'+action+'/'+self.studio.ids[-1]+'?workspace_id='+self.studio.scope
            status, result, headers = self.request('GET', path)
            self.assertEqual(status, 200, result)
            self.assertFalse(result['generation_submitted']); self.assertTrue(result['observation_only'])
            self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(before, self.studio.assets.snapshot())

    def test_duplicate_unknown_malformed_and_foreign_queries_refuse_without_mutation(self):
        prefix = '/api/assets/family/'+self.studio.ids[-1]+'?'
        for query in ('', 'workspace_id='+self.studio.scope+'&workspace_id='+self.studio.scope,
                      'workspace_id='+self.studio.scope+'&children=yes', 'workspace_id=%FF',
                      'workspace_id='+self.studio.scope+'&run=true', 'workspace_id=%GG'):
            status, result, _ = self.request('GET', prefix+query)
            self.assertEqual(status, 400, result)
        status, result, _ = self.request('GET', prefix+'workspace_id='+'b'*32)
        self.assertEqual(status, 409); self.assertNotIn('nodes', result)
        status, _, _ = self.request('GET', prefix+'workspace_id='+self.studio.scope, host='evil.test')
        self.assertEqual(status, 403)
        status, _, _ = self.request('POST', prefix+'workspace_id='+self.studio.scope, {})
        self.assertEqual(status, 405)


if __name__ == '__main__': unittest.main()
