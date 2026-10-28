"""Real loopback requests exercise private history and direct-ID disclosure."""
import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

from http_test_server import ThreadingHTTPServer
import test_server as fixture


class PrivateCreationHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);root=Path(self.tmp.name)
        for name in ('presets','workflows/api','config','fake-comfy/input'):(root/name).mkdir(parents=True,exist_ok=True)
        (root/'config/local.json').write_text(json.dumps({'comfy_root':str(root/'fake-comfy')}))
        (root/'presets/catalog.json').write_text(json.dumps({'presets':[fixture.PRESET]}))
        (root/'workflows/api/demo-api.json').write_text(json.dumps(fixture.GRAPH))
        with patch.object(threading.Thread,'start',lambda *_:None):self.studio=fixture.server.Studio(root)
        self.regular=self.studio.create_job({'preset_id':'demo','controls':{'positive':'regular canary'}},enqueue=False)
        self.private=self.studio.create_job({'preset_id':'demo','controls':{'positive':'private canary'},'privacy':'private'},enqueue=False)
        handler=type('PrivacyHTTPHandler',(fixture.server.extend_handler(fixture.server.Handler),),{'studio':self.studio})
        self.http=ThreadingHTTPServer(('127.0.0.1',0),handler)
        self.thread=threading.Thread(target=self.http.serve_forever,kwargs={'poll_interval':.01},daemon=True);self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.http.shutdown();self.http.server_close();self.thread.join(3)

    def request(self,path,*,headers=None,body=None,method='GET'):
        conn=HTTPConnection('127.0.0.1',self.http.server_port,timeout=5)
        try:
            fields={'Host':'127.0.0.1:8191','Origin':'http://127.0.0.1:8191',**(headers or {})}
            if body is not None:body=json.dumps(body);fields['Content-Type']='application/json'
            conn.request(method,path,body,fields);response=conn.getresponse()
            return response.status,response.read(),dict(response.getheaders())
        finally:conn.close()

    def test_default_history_and_etag_do_not_disclose_private_runs(self):
        status,body,headers=self.request('/api/jobs')
        self.assertEqual(status,200);self.assertEqual([j['id'] for j in json.loads(body)],[self.regular['id']])
        self.assertNotIn(b'private canary',body)
        self.studio.jobs[self.private['id']]['controls']['positive']='changed private canary'
        status,body,_=self.request('/api/jobs',headers={'If-None-Match':headers['ETag']})
        self.assertEqual(status,304);self.assertEqual(body,b'')

    def test_private_and_all_history_are_explicit_and_distinct(self):
        for scope,ids in [('regular',{self.regular['id']}),('private',{self.private['id']}),('all',{self.regular['id'],self.private['id']})]:
            with self.subTest(scope=scope):
                status,body,_=self.request('/api/jobs',headers={'X-Studio-Privacy':scope})
                self.assertEqual(status,200);self.assertEqual({j['id'] for j in json.loads(body)},ids)

    def test_known_private_job_and_recipe_look_missing_without_scope(self):
        for suffix in ('','/recipe'):
            path='/api/jobs/'+self.private['id']+suffix
            status,body,_=self.request(path);self.assertEqual(status,404);self.assertNotIn(b'private canary',body)
            status,body,_=self.request(path+'?privacy=private');self.assertEqual(status,200);self.assertIn(b'private canary',body)

    def test_mixed_job_ids_never_authorize_one_job_and_return_another(self):
        regular,private=self.regular['id'],self.private['id']
        for path in ('/api/jobs/'+regular+'/'+private,'/api/jobs/'+regular+'/unknown/'+private,
                     '/api/jobs/'+regular+'//'+private,'/api/jobs/'+private+'/'+regular):
            for scope in ('regular','private','all'):
                with self.subTest(path=path,scope=scope):
                    status,raw,_=self.request(path,headers={'X-Studio-Privacy':scope})
                    self.assertEqual(status,404)
                    self.assertNotIn(b'private canary',raw)
        status,raw,_=self.request('/api/jobs/'+regular)
        self.assertEqual(status,200);self.assertEqual(json.loads(raw)['id'],regular)

    def test_noncanonical_targets_are_rejected_before_composed_document_dispatch(self):
        # The composed document owner normalizes urlsplit(path), unlike a raw-prefix guard.
        from studio_workflow.document_http import PREFIX, store
        from test_workflow_documents import INFO, GRAPH, catalog, new_document
        repository=store(self.studio)
        before=repository.list()
        document=new_document(GRAPH,catalog(INFO,'primary'),'Private target canary')
        targets=('http://127.0.0.1:8191'+PREFIX, PREFIX+'#ignored-fragment',
                 'https://localhost'+PREFIX, 'http://evil.test'+PREFIX)
        for target in targets:
            with self.subTest(target=target):
                status,raw,_=self.request(target,headers={'X-Studio-Creation-Privacy':'private'},
                                        body={'request_id':'private-target-probe','document':document},method='POST')
                self.assertEqual(status,400)
                self.assertEqual(json.loads(raw).get('code'),'privacy_invalid_target')
                self.assertEqual(repository.list(),before)
                status,raw,_=self.request(target)
                self.assertEqual(status,400)
                self.assertEqual(json.loads(raw).get('code'),'privacy_invalid_target')
        # Canonical regular reads still reach the existing owner.
        status,raw,_=self.request(PREFIX)
        self.assertEqual(status,200);self.assertEqual(json.loads(raw),before)
        status,raw,_=self.request(PREFIX,headers={'X-Studio-Creation-Privacy':'private'},body={},method='POST')
        self.assertEqual(status,400)
        self.assertEqual(json.loads(raw).get('code'),'private_workflow_unsupported')

    def test_private_upload_media_requires_scope_and_is_not_cached(self):
        value=self.studio.upload('private-image','image/png',fixture.png(),privacy='private')
        path='/api/uploads/'+value['file']
        self.assertIn(self.request(path)[0],(400,404))
        status,raw,headers=self.request(path+'?privacy=private')
        self.assertEqual(status,200);self.assertEqual(raw,fixture.png());self.assertEqual(headers['Cache-Control'],'no-store')
        status,_,headers=self.request(path+'?privacy=private',headers={'Range':'bytes=9000-10000'})
        self.assertEqual(status,416);self.assertEqual(headers['Cache-Control'],'no-store')

    def test_creation_header_captured_into_job_and_conflicting_payload_refused(self):
        headers={'X-Studio-Creation-Privacy':'private'}
        status,body,_=self.request('/api/jobs',headers=headers,body={'preset_id':'demo'},method='POST')
        self.assertEqual(status,201);self.assertEqual(json.loads(body).get('privacy'),'private')
        before=set(self.studio.jobs)
        status,_,_=self.request('/api/jobs',headers=headers,body={'preset_id':'demo','privacy':'regular'},method='POST')
        self.assertEqual(status,400);self.assertEqual(set(self.studio.jobs),before)

    def test_hidden_job_cannot_be_mutated_by_default_scope(self):
        before=dict(self.studio.jobs[self.private['id']])
        status,body,_=self.request('/api/jobs/'+self.private['id']+'/abandon',body={'reason':'test'},method='POST')
        self.assertEqual(status,400);self.assertEqual(self.studio.jobs[self.private['id']],before)
        missing,missing_body,_=self.request('/api/jobs/unknown/abandon',body={'reason':'test'},method='POST')
        self.assertEqual((status,body),(missing,missing_body))

    def test_reference_copy_honors_body_classification_and_rejects_conflicts(self):
        asset=self.studio.import_image('regular.png','image/png',fixture.png())['asset']
        status,raw,_=self.request('/api/assets/reference',body={'id':asset['id'],'privacy':'private'},method='POST')
        self.assertEqual(status,200);value=json.loads(raw);self.assertEqual(value.get('privacy'),'private')
        status,_,_=self.request('/api/assets/reference',body={'id':asset['id'],'privacy':'private'},
                               headers={'X-Studio-Creation-Privacy':'regular'},method='POST')
        self.assertEqual(status,400)
        status,raw,_=self.request('/api/references/check',body={'files':[value['file']],'privacy':'private'},method='POST')
        self.assertEqual(status,200);self.assertTrue(json.loads(raw)[0]['available'])


if __name__=='__main__':unittest.main()
