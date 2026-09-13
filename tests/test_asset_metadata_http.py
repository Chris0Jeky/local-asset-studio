"""Exercise the production HTTP handler, actual SQLite and strict Host/Origin checks."""
import json
import tempfile
import threading
import unittest
import uuid
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from test_server import server


class AssetMetadataHTTP(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.store=server.AssetWorkspace(root);source=root/'image.png';source.write_bytes(b'original')
        self.asset=self.store.register({'id':'job','outputs':[{'filename':'image.png'}]},0,source)
        class Handler(server.Handler):
            studio=SimpleNamespace(assets=self.store)
        self.http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()

    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join(2);self.temp.cleanup()

    def request(self, method, path, data=None, host='127.0.0.1:8191', origin='http://127.0.0.1:8191'):
        connection=HTTPConnection('127.0.0.1',self.http.server_port,timeout=3)
        try:
            connection.request(method,path,json.dumps(data) if data is not None else None,
                               {'Host':host,'Origin':origin,'Content-Type':'application/json'})
            response=connection.getresponse();return response.status,json.loads(response.read()),dict(response.getheaders())
        finally:connection.close()

    def command(self, **fields):
        return dict(ids=[self.asset], action='edit', notes='changed', request_id=uuid.uuid4().hex,
                    expected_revisions={self.asset:0}, **fields)

    def test_unconditional_write_returns_428_without_mutation(self):
        status,data,headers=self.request('POST','/api/assets/update',{'ids':[self.asset],'action':'edit','notes':'bad'})
        self.assertEqual(status,428);self.assertEqual(data['code'],'asset_precondition_required')
        self.assertEqual(headers['Cache-Control'],'no-store');self.assertEqual(self.store.get(self.asset)['notes'],'')

    def test_conflict_receipt_read_and_exact_replay(self):
        command=self.command();status,first,_=self.request('POST','/api/assets/update',command);self.assertEqual(status,200)
        stale=self.command();status,data,_=self.request('POST','/api/assets/update',stale)
        self.assertEqual(status,409);self.assertEqual(data['code'],'asset_revision_conflict')
        self.assertEqual(data['current'][0]['metadata_revision'],1)
        status,observed,headers=self.request('GET','/api/assets/commands/'+command['request_id'])
        self.assertEqual(observed,first);self.assertEqual(headers['Cache-Control'],'no-store')
        status,replayed,_=self.request('POST','/api/assets/update',command)
        self.assertEqual(replayed,first);self.assertEqual(self.store.get(self.asset)['metadata_revision'],1)

    def test_remote_origin_or_host_never_writes(self):
        for host,origin in [('evil.test','http://127.0.0.1:8191'),('127.0.0.1:8191','https://evil.test'),('127.0.0.1:8191','')]:
            status,_,_=self.request('POST','/api/assets/update',self.command(),host=host,origin=origin);self.assertEqual(status,403)
        status,_,_=self.request('GET','/api/assets/commands/'+'a'*32,host='evil.test');self.assertEqual(status,403)
        self.assertEqual(self.store.get(self.asset)['metadata_revision'],0)

    def test_metadata_read_is_bounded_and_receipt_unknown_is_not_retry_authority(self):
        status,data,_=self.request('GET','/api/assets/'+self.asset+'/metadata');self.assertEqual(status,200)
        self.assertEqual(data['metadata_revision'],0)
        for key in ['path','source','url','graph']:self.assertNotIn(key,data)
        status,data,_=self.request('GET','/api/assets/commands/'+'a'*32);self.assertEqual(data['status'],'unknown')
        self.assertEqual(self.store.get(self.asset)['metadata_revision'],0)

    def test_malformed_and_changed_request_id_are_structured(self):
        status,_,_=self.request('POST','/api/assets/update',[]);self.assertEqual(status,400)
        command=self.command();self.request('POST','/api/assets/update',command)
        status,data,_=self.request('POST','/api/assets/update',dict(command,notes='replacement'))
        self.assertEqual(status,409);self.assertEqual(data['code'],'asset_request_reused')

    def test_sqlite_receipt_failure_is_unconfirmed_503_and_rolls_back(self):
        with self.store.connection() as db:
            db.execute("CREATE TRIGGER reject_receipt BEFORE INSERT ON asset_commands BEGIN SELECT RAISE(ABORT, 'receipt fault'); END")
        status,data,_=self.request('POST','/api/assets/update',self.command())
        self.assertEqual(status,503);self.assertEqual(data['code'],'asset_storage_unconfirmed')
        self.assertEqual(self.store.get(self.asset)['metadata_revision'],0)
        self.assertEqual(self.store.get(self.asset)['notes'],'')
