"""Shared browser responses also support handlers that delegate without inheriting."""
import io
import json
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
        body=json.dumps({'workspace_id':attributes.get('workspace_id','1'*32),'ids':['missing']}).encode()
        handler = SimpleNamespace(path='/api/assets/selection', headers={'Content-Length':str(len(body))},
                                  rfile=io.BytesIO(body), json=lambda value: value, **attributes)
        yield fixture.Handler.do_POST(handler)

    def test_delegating_handler_uses_default_workspace(self):
        for response in self.responses({}):
            self.assertEqual(response['workspace_id'], '1' * 32)

    def test_delegating_handler_preserves_workspace_override(self):
        for response in self.responses({'workspace_id': '2' * 32}):
            self.assertEqual(response['workspace_id'], '2' * 32)
