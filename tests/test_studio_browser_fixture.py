"""Shared browser responses also support handlers that delegate without inheriting."""
import io
import unittest
from types import SimpleNamespace

import studio_browser_smoke as fixture


class WorkspaceIdentityTests(unittest.TestCase):
    def responses(self, attributes):
        for path in ('/api/assets/page', '/api/collections', '/api/workspace', '/'):
            handler = SimpleNamespace(path=path, json=lambda value: value, **attributes)
            if path == '/':
                # The shell previously crashed while constructing the API response map.
                handler.send_response = lambda status: None
                handler.send_header = lambda *args: None
                handler.end_headers = lambda: None
                handler.wfile = io.BytesIO()
                fixture.Handler.do_GET(handler)
                self.assertTrue(handler.wfile.getvalue())
            else:
                yield fixture.Handler.do_GET(handler)
        handler = SimpleNamespace(path='/api/assets/selection', headers={'Content-Length': '10'},
                                  rfile=io.BytesIO(b'{"ids":[]}'), json=lambda value: value, **attributes)
        yield fixture.Handler.do_POST(handler)

    def test_delegating_handler_uses_default_workspace(self):
        for response in self.responses({}):
            self.assertEqual(response['workspace_id'], '1' * 32)

    def test_delegating_handler_preserves_workspace_override(self):
        for response in self.responses({'workspace_id': '2' * 32}):
            self.assertEqual(response['workspace_id'], '2' * 32)

    def test_delegating_handler_serves_bounded_family_in_the_observed_workspace(self):
        for suffix,children in (('',None),('&children=true',[])):
            with self.subTest(suffix=suffix):
                handler=SimpleNamespace(path='/api/assets/family/asset-1?workspace_id='+'2'*32+suffix,
                                        workspace_id='2'*32,json=lambda value,status=200:(status,value))
                status,response=fixture.Handler.do_GET(handler)
                self.assertEqual(status,200);self.assertEqual(response['workspace_id'],'2'*32)
                self.assertEqual(response['asset_id'],'asset-1');self.assertEqual([node['id'] for node in response['nodes']],['asset-1'])
                self.assertEqual(response['children'],children);self.assertEqual(response['edges'],[])
                self.assertTrue(response['observation_only']);self.assertFalse(response['generation_submitted'])
                self.assertFalse(response['media_bytes_verified']);self.assertEqual(response['children_scanned'],0)
