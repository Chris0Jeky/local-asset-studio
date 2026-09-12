"""The real Studio Handler and recipe serializers; only jobs/media are inert fixtures.

Use the existing test_server module's app import. No Studio constructor, worker,
ComfyUI process or inference is started. Ephemeral transport sends the Handler's
normal loopback Host/Origin headers to test its unchanged guard.
"""
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
from types import MethodType
import unittest

from test_server import server
from review_fixture import FixtureStudio, seed


class ReviewHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.studio=FixtureStudio(Path(self.temporary.name));self.identifier=seed(self.studio)
        for job in self.studio.jobs.values():
            graph=job['fixture_recipe']['graph']
            job.update(preset_id='inert-qa',controls={'seed':graph['1']['inputs']['seed']},batch_count=1,
                       created_at=1,graph=graph,submissions=[],references=[],parent_assets=[])
        self.studio.public=MethodType(server.Studio.public,self.studio)
        self.studio.export_recipe=MethodType(server.Studio.export_recipe,self.studio)
        handler=type('ReviewTestHandler',(server.Handler,),{'studio':self.studio})
        self.http=ThreadingHTTPServer(('127.0.0.1',0),handler);self.worker=threading.Thread(target=self.http.serve_forever,daemon=True);self.worker.start()
    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.worker.join(2);self.temporary.cleanup()
    def request(self,method,path,payload=None,headers=None):
        conn=HTTPConnection('127.0.0.1',self.http.server_port,timeout=10)
        try:
            options={'Host':'127.0.0.1:8191','Origin':'http://127.0.0.1:8191','Content-Type':'application/json',**(headers or {})}
            conn.request(method,path,json.dumps(payload) if payload is not None else None,options)
            reply=conn.getresponse();return reply.status,reply.read(),dict(reply.headers)
        finally:conn.close()
    def command(self,payload,**kwargs):return self.request('POST',f'/api/production/{self.identifier}/review',payload,**kwargs)
    def test_inspection_route_is_read_only_and_real_serializers_are_stable(self):
        status,data,_=self.command({'action':'inspect'});self.assertEqual(status,200);self.assertFalse(json.loads(data)['exists'])
        self.assertFalse(self.studio.production.reviews.exists(self.identifier))
        status,data,_=self.command({'action':'open'});self.assertEqual(status,200);opened=json.loads(data)
        self.assertNotIn('workflow',opened);self.assertNotIn('inert-prompt',data.decode())
        status,data,_=self.command({'action':'reveal','expected_revision':opened['revision']});self.assertEqual(status,200)
        revealed=json.loads(data);self.assertEqual(revealed['evidence']['stages'][0]['recipe']['version'],2)
        status,_,_=self.command({'action':'view','expected_revision':revealed['revision'],'crop':[0,0,10000,10000],'background':'light'})
        self.assertEqual(status,200);self.assertTrue(self.studio.queue.empty());self.assertEqual(self.studio.network_calls,0)
    def test_origin_and_host_are_enforced_before_open(self):
        for headers in ({'Origin':'https://evil.invalid'},{'Host':'evil.invalid'},{'Origin':'null'},{'Origin':'http://user@127.0.0.1:8191'}):
            with self.subTest(headers=headers):
                status,_,_=self.command({'action':'open'},headers=headers);self.assertEqual(status,403)
        self.assertFalse(self.studio.production.reviews.exists(self.identifier))
    def test_stale_revision_is_a_useful_http_error_not_an_overwrite(self):
        _,data,_=self.command({'action':'open'});revision=json.loads(data)['revision']
        payload={'action':'reveal','expected_revision':revision}
        self.assertEqual(self.command(payload)[0],200)
        status,data,_=self.command(payload);self.assertEqual(status,400);self.assertIn('Review conflict',json.loads(data)['error'])
        self.assertEqual(self.studio.production.reviews.inspect(self.identifier)['revision'],revision+1)
    def test_preview_is_served_through_existing_file_route_with_ranges(self):
        _,data,_=self.command({'action':'open'});url=json.loads(data)['candidates'][0]['preview_url']
        status,data,headers=self.request('GET',url);self.assertEqual(status,200);self.assertTrue(data.startswith(b'\x89PNG'));self.assertEqual(headers['Content-Type'],'image/png')
        self.assertNotIn(b'PRIVATE-SEED',data)
        status,data,headers=self.request('GET',url,headers={'Range':'bytes=0-7'})
        self.assertEqual(status,206);self.assertEqual(len(data),8);self.assertIn('Content-Range',headers)
    def test_static_entry_and_invalid_commands_do_not_generate(self):
        for path in ('/review.html','/review.js','/review.css'):
            status,data,_=self.request('GET',path);self.assertEqual(status,200);self.assertTrue(data)
        for payload in ([],None,{'action':'shell','command':'anything'},{'action':'open','unknown':1}):
            status,data,_=self.command(payload);self.assertEqual(status,400);self.assertIn('error',json.loads(data))
        self.assertEqual(self.studio.network_calls,0);self.assertTrue(self.studio.queue.empty())
    def test_private_mapping_and_unpublished_files_are_not_downloadable(self):
        _,data,_=self.command({'action':'open'});url=json.loads(data)['candidates'][0]['preview_url']
        status,_,_=self.request('GET',url.rsplit('/',1)[0]+'/mapping.json');self.assertEqual(status,400)
        status,_,_=self.request('GET',url.replace('/reviews/','/../reviews/'));self.assertEqual(status,400)
        status,_,_=self.request('GET',url,headers={'Host':'evil.invalid'});self.assertEqual(status,403)


if __name__=='__main__':unittest.main()
