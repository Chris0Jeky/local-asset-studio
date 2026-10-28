"""Archive through the fully composed production HTTP owner and actual SQLite."""
from http.client import HTTPConnection, RemoteDisconnected
import json
from pathlib import Path
import socket
import unittest
from urllib.parse import urlencode
import uuid

import test_asset_read_http as fixture
from http_refusal_transport import atomic_json_post


class ArchiveHTTPTests(unittest.TestCase):
    setUp=fixture.AssetReadHTTPTests.setUp
    tearDown=fixture.AssetReadHTTPTests.tearDown

    def request(self,method,path,data=None,privacy='regular'):
        connection=HTTPConnection('127.0.0.1',self.http.server_port,timeout=3)
        try:
            connection.request(method,path,json.dumps(data) if data is not None else None,
                               {'Host':'127.0.0.1:8191','Origin':'http://127.0.0.1:8191',
                                'Content-Type':'application/json','X-Studio-Privacy':privacy})
            response=connection.getresponse()
            return response.status,json.loads(response.read()),dict(response.getheaders())
        finally:connection.close()

    def command(self,action='archive',ids=None):
        ids=self.ids[:1] if ids is None else ids
        return {'workspace_id':self.scope,'request_id':uuid.uuid4().hex,'ids':ids,'action':action,
                'expected_revisions':{i:self.store.get(i,privacy='all')['metadata_revision'] for i in ids}}

    def test_archive_pages_selection_metadata_and_unarchive_share_one_owner(self):
        command=self.command();status,receipt,headers=self.request('POST','/api/assets/update',command)
        self.assertEqual(status,200,receipt);self.assertEqual(headers['Cache-Control'],'no-store')
        self.assertIsNotNone(receipt['current'][0]['archived_at'])
        status,active,_=self.request('GET','/api/assets/page?details=true');self.assertEqual(status,200)
        self.assertNotIn(self.ids[0],[row['id'] for row in active['assets']])
        status,archived,_=self.request('GET','/api/assets/page?archive=archived&details=true&include_collections=true')
        self.assertEqual(status,200);self.assertEqual([row['id'] for row in archived['assets']],self.ids[:1])
        status,selected,_=self.request('POST','/api/assets/selection',{'workspace_id':self.scope,'ids':self.ids[:1],'details':True})
        self.assertEqual(status,200);self.assertEqual(selected['items'][0]['state'],'active')
        self.assertIsNotNone(selected['items'][0]['asset']['archived_at'])
        status,metadata,_=self.request('GET','/api/assets/'+self.ids[0]+'/metadata?workspace_id='+self.scope)
        self.assertEqual(status,200);self.assertEqual(metadata['archived_at'],receipt['applied']['archived_at'])
        status,restored,_=self.request('POST','/api/assets/update',self.command('unarchive'))
        self.assertEqual(status,200);self.assertIsNone(restored['applied']['archived_at'])
        self.assertEqual((Path(self.temp.name)/'image.png').read_bytes(),b'original')

    def test_lost_post_response_is_observed_and_exact_replay_never_reapplies(self):
        command=self.command();base=self.http.RequestHandlerClass
        class LoseOnce(base):
            lose=True
            def _json(handler,status,value):
                if handler.path=='/api/assets/update' and status==200 and LoseOnce.lose:
                    LoseOnce.lose=False;handler.close_connection=True
                    handler.connection.shutdown(socket.SHUT_RDWR);return
                return super()._json(status,value)
        self.http.RequestHandlerClass=LoseOnce
        with self.assertRaises((RemoteDisconnected,ConnectionResetError)):
            self.request('POST','/api/assets/update',command)
        after=self.store.snapshot();status,receipt,_=self.request('GET','/api/assets/commands/'+command['request_id']+'?workspace_id='+self.scope)
        self.assertEqual(status,200);self.assertEqual(receipt['status'],'applied')
        status,replay,_=self.request('POST','/api/assets/update',command)
        self.assertEqual(status,200);self.assertEqual(replay,receipt);self.assertEqual(self.store.snapshot(),after)
        with self.store.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM asset_commands').fetchone()[0],1)

    def test_receipt_storage_failure_rolls_back_every_target_without_losing_originals(self):
        before=self.store.snapshot()
        with self.store.connection() as db:
            db.execute("CREATE TRIGGER reject_archive_receipt BEFORE INSERT ON asset_commands BEGIN SELECT RAISE(ABORT, 'synthetic receipt fault'); END")
        status,result,_=self.request('POST','/api/assets/update',self.command(ids=self.ids))
        self.assertEqual(status,503);self.assertEqual(result['code'],'asset_storage_unconfirmed')
        self.assertEqual(self.store.snapshot(),before);self.assertEqual((Path(self.temp.name)/'image.png').read_bytes(),b'original')

    def test_privacy_filters_cursors_and_receipts_remain_independent(self):
        private=self.store.register({'id':'private-archive-canary','privacy':'private','outputs':[{'filename':'image.png'}]},0,Path(self.temp.name)/'image.png')
        regular=self.command();self.request('POST','/api/assets/update',regular)
        first=self.request('GET','/api/assets/page?limit=1&archive=all')[1]
        command=self.command(ids=[private]);status,result,_=self.request('POST','/api/assets/update',command,privacy='private')
        self.assertEqual(status,200,result)
        status,second,_=self.request('GET','/api/assets/page?'+urlencode({'limit':1,'archive':'all','cursor':first['next_cursor']}))
        self.assertEqual(status,200);self.assertEqual(first['catalogue'],second['catalogue'])
        status,hidden,_=self.request('GET','/api/assets/commands/'+command['request_id']+'?workspace_id='+self.scope)
        self.assertEqual(status,200);self.assertEqual(hidden['status'],'unknown')
        self.assertNotIn(private,json.dumps(self.request('GET','/api/assets/page?archive=all')[1]))
        private_page=self.request('GET','/api/assets/page?archive=archived',privacy='private')[1]
        self.assertEqual([row['id'] for row in private_page['assets']],[private])
        for suffix in ('archive=wrong','archive=active&archive=all','archive=','archive=all&privacy=private'):
            self.assertEqual(self.request('GET','/api/assets/page?'+suffix)[0],400)
        before=self.store.snapshot(privacy='all')
        for host,origin in [('evil.test','http://127.0.0.1:8191'),('127.0.0.1:8191','https://evil.test')]:
            status,_=atomic_json_post(self.http.server_port,'/api/assets/update',json.dumps(self.command('unarchive')).encode(),host=host,origin=origin)
            self.assertEqual(status,403)
        self.assertEqual(self.store.snapshot(privacy='all'),before)


if __name__=='__main__':unittest.main()
