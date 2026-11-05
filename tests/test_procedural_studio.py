"""Real Studio, SQLite, Library and loopback routes with an inert factory seam."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from unittest.mock import patch

from http_test_server import ThreadingHTTPServer
from test_server import FakeStudio, GRAPH, PRESET, server
from test_procedural_operation import fake_build, procedural, setup_runtime


def configured_studio(root):
    for name in ('presets','workflows/api','config','fake-comfy/input'):(root / name).mkdir(parents=True,exist_ok=True)
    config, validator = setup_runtime(root)
    (root / 'config/local.json').write_text(json.dumps({**config,'comfy_root':str(root / 'fake-comfy')}))
    (root / 'presets/catalog.json').write_text(json.dumps({'presets':[PRESET]}))
    (root / 'workflows/api/demo-api.json').write_text(json.dumps(GRAPH))
    with patch.object(threading.Thread,'start',lambda *_:None):studio = FakeStudio(root,[])
    return studio,validator


class ProceduralStudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root = Path(self.tmp.name)
        self.studio,validator = configured_studio(self.root)
        patched = patch.object(procedural,'VALIDATOR_DIR',validator);patched.start();self.addCleanup(patched.stop)
        handler = type('ProceduralHTTPHandler',(server.extend_handler(server.Handler),),{'studio':self.studio})
        self.http = ThreadingHTTPServer(('127.0.0.1',0),handler)
        self.thread = threading.Thread(target=self.http.serve_forever,kwargs={'poll_interval':.01},daemon=True);self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.http.shutdown();self.http.server_close();self.thread.join(3)

    def request(self,path,body=None,headers=None):
        connection = HTTPConnection('127.0.0.1',self.http.server_port,timeout=10)
        fields = {'Host':'127.0.0.1:8191','Origin':'http://127.0.0.1:8191',**(headers or {})}
        try:
            if body is not None:body=json.dumps(body);fields['Content-Type']='application/json'
            connection.request('POST' if body is not None else 'GET',path,body,fields)
            response=connection.getresponse();raw=response.read()
            value=json.loads(raw) if response.getheader('Content-Type','').startswith('application/json') else raw
            return response.status,value
        finally:connection.close()

    def intent(self, **extra):return {'name':'Studio crate','generator':'prop','params':{'kind':1},'render':True, **extra}

    def test_catalog_and_validation_are_read_only_even_without_runtime(self):
        self.studio.config = {}
        with patch.object(procedural.factory,'build') as build:
            status,catalog = self.request('/api/procedural');self.assertEqual(status,200)
            self.assertEqual(len(catalog['generators']),8);self.assertFalse(catalog['runtime']['ready'])
            status,checked = self.request('/api/procedural/validate',self.intent());self.assertEqual(status,200)
            self.assertEqual(checked['intent']['params']['kind'],1)
            self.assertFalse(checked['generation_submitted'])
        self.assertEqual(self.studio.production.list(),[]);self.assertEqual(self.studio.jobs,{})
        self.assertTrue(self.studio.queue.empty());build.assert_not_called()

    def test_prepare_and_start_are_distinct_requests_on_the_existing_coordinator(self):
        with patch.object(procedural.factory,'build') as build:
            status,project = self.request('/api/procedural',self.intent())
            self.assertEqual(status,201);self.assertEqual(project['kind'],'procedural')
            self.assertEqual(project['state']['status'],'planned');self.assertTrue(self.studio.queue.empty())
            self.assertEqual(project['budget'],{'allowance':0,'reserved':0})
            status,started = self.request(f'/api/production/{project["id"]}/start',{})
            self.assertEqual(status,202);self.assertEqual(started['state']['status'],'queued')
            self.assertEqual(self.studio.queue.get_nowait(),('production',project['id']))
            status,again = self.request(f'/api/production/{project["id"]}/start',{})
            self.assertEqual(status,400);self.assertIn('already',again['error'])
        build.assert_not_called();self.assertEqual(self.studio.requests,[])

    def test_private_creation_and_external_origin_are_refused_before_preparation(self):
        for headers in ({'X-Studio-Creation-Privacy':'private'},{'Origin':'https://example.test'}):
            status,_ = self.request('/api/procedural',self.intent(),headers)
            self.assertIn(status,(400,403))
        status,_ = self.request('/api/procedural',self.intent(privacy='private'));self.assertEqual(status,400)
        self.assertEqual(self.studio.production.list(),[]);self.assertTrue(self.studio.queue.empty())

    def test_invalid_parameters_and_missing_tools_do_not_create_projects(self):
        for payload in (self.intent(params={'height':'0.6'}),self.intent(script='print(1)'),self.intent(params={'detail':49})):
            status,_ = self.request('/api/procedural',payload);self.assertEqual(status,400)
        self.studio.config.pop('blender')
        status,failed = self.request('/api/procedural',self.intent());self.assertEqual(status,400);self.assertIn('Blender',failed['error'])
        self.assertEqual(self.studio.production.list(),[])

    def test_build_publishes_library_assets_and_downloads_without_comfy(self):
        project = self.studio.production.procedural(self.intent());identifier = project['id']
        self.studio.production.start(identifier)
        def build(*args,**kwargs):
            attempt=self.studio.production.get(identifier)['state']['attempts']['0']
            self.assertTrue((self.studio.runs / attempt['job_id'] / 'state.json').is_file())
            return fake_build(*args,**kwargs)
        with patch.object(procedural.factory,'build',side_effect=build):self.studio.production.run(identifier)
        result = self.studio.production.get(identifier)
        self.assertEqual(result['state']['status'],'completed')
        self.assertEqual(result['state']['procedural_verification']['state'],'incomplete')
        attempt=result['state']['attempts']['0'];job=self.studio.jobs[attempt['job_id']]
        self.assertEqual(len(job['outputs']),4)
        for output in job['outputs']:
            asset=self.studio.assets.get(output['asset_id'])
            self.assertEqual(asset['job_id'],job['id']);self.assertEqual(asset['privacy'],'regular')
            status,raw=self.request(f'/api/assets/{asset["id"]}/file');self.assertEqual(status,200)
            self.assertEqual(raw,self.studio.output_path(output,job).read_bytes())
        self.assertEqual(self.request(f'/api/production/{identifier}/files/export.zip')[0],200)
        self.assertEqual(self.studio.requests,[])
        server.Studio._validate_job_record(job)

    def test_changed_published_artifact_is_refused(self):
        project=self.studio.production.procedural(self.intent());identifier=project['id']
        self.studio.production.start(identifier)
        with patch.object(procedural.factory,'build',side_effect=fake_build):self.studio.production.run(identifier)
        path=self.studio.production.root / identifier / 'procedural/asset_LOD0.glb';path.write_bytes(b'changed')
        status,failed=self.request(f'/api/production/{identifier}/files/procedural/asset_LOD0.glb')
        self.assertEqual(status,400);self.assertIn('changed',failed['error'])

    def test_restart_keeps_the_completed_native_recipe_and_library_identity(self):
        project=self.studio.production.procedural(self.intent());identifier=project['id']
        self.studio.production.start(identifier)
        with patch.object(procedural.factory,'build',side_effect=fake_build):self.studio.production.run(identifier)
        before=self.studio.production.get(identifier);job_id=before['state']['attempts']['0']['job_id']
        with patch.object(threading.Thread,'start',lambda *_:None):restarted=FakeStudio(self.root,[])
        job=restarted.jobs[job_id]
        self.assertEqual(job['status'],'completed');self.assertEqual(job['native_recipe'],self.studio.jobs[job_id]['native_recipe'])
        self.assertEqual([o['asset_id'] for o in job['outputs']],[o['asset_id'] for o in self.studio.jobs[job_id]['outputs']])
        self.assertEqual(restarted.production.get(identifier)['state']['status'],'completed')
        self.assertEqual(restarted.requests,[]);self.assertTrue(restarted.queue.empty())

    def test_plan_storage_loss_blocks_start_and_keeps_the_existing_project(self):
        project=self.studio.production.procedural(self.intent());identifier=project['id']
        (self.studio.production.root / identifier / 'plan.json').write_text('{}')
        status,failed=self.request(f'/api/production/{identifier}/start',{})
        self.assertEqual(status,400);self.assertIn('differs',failed['error']);self.assertTrue(self.studio.queue.empty())
        self.assertEqual(self.studio.production.get(identifier)['state']['status'],'planned')

    def test_interrupted_attempt_reconciles_once_without_rebuilding(self):
        project=self.studio.production.procedural(self.intent());identifier=project['id']
        self.studio.production.start(identifier)
        with patch.object(procedural.factory,'build',side_effect=fake_build),patch.object(self.studio.assets,'register',side_effect=KeyboardInterrupt('parent lost')):
            with self.assertRaises(KeyboardInterrupt):self.studio.production.run(identifier)
        self.studio.production._mutate(identifier,status='interrupted')
        self.studio.production.resume(identifier)
        with patch.object(procedural.factory,'build') as build:self.studio.production.run(identifier)
        build.assert_not_called();self.assertEqual(self.studio.production.get(identifier)['state']['status'],'completed')
        self.assertEqual(self.studio.requests,[])

    def test_partial_library_publication_resumes_idempotently_after_restart(self):
        project=self.studio.production.procedural(self.intent());identifier=project['id']
        self.studio.production.start(identifier);self.studio.queue.get_nowait()
        register=self.studio.assets.register
        def fail_second(job,index,source):
            if index==1:raise OSError('second Library insert unavailable')
            return register(job,index,source)
        with patch.object(procedural.factory,'build',side_effect=fake_build) as build,patch.object(self.studio.assets,'register',side_effect=fail_second):
            self.studio.production.run(identifier)
        self.assertEqual(build.call_count,1)
        result=self.studio.production.get(identifier);job_id=result['state']['attempts']['0']['job_id'];job=self.studio.jobs[job_id]
        self.assertEqual(result['state']['status'],'uncertain');self.assertFalse(job.get('failure_files'))
        published=self.studio.assets.snapshot()['assets'];self.assertEqual(len(published),1)
        first_id=published[0]['id'];self.assertEqual([o['asset_id'] for o in job['outputs']],[first_id])
        self.assertEqual(job['outputs'][0]['filename'],'asset_LOD0.glb')
        receipt=json.loads((self.studio.production.root/identifier/'procedural-job.json').read_bytes())
        self.assertEqual(receipt['outputs'][0]['asset_id'],first_id);self.assertFalse(receipt.get('failure_files'))
        with patch.object(threading.Thread,'start',lambda *_:None):restarted=FakeStudio(self.root,[])
        self.assertEqual(len(restarted.assets.snapshot()['assets']),1,'Startup must not publish the remaining native paths')
        self.assertEqual(restarted.jobs[job_id]['outputs'][0]['asset_id'],first_id)
        restarted.production.resume(identifier)
        with patch.object(procedural.factory,'build') as build:restarted.production.run(identifier)
        build.assert_not_called();self.assertEqual(restarted.production.get(identifier)['state']['status'],'completed')
        outputs=restarted.jobs[job_id]['outputs'];self.assertEqual(len(outputs),4);self.assertEqual(outputs[0]['asset_id'],first_id)
        self.assertEqual(len(restarted.assets.snapshot()['assets']),4);self.assertEqual(len({o['asset_id'] for o in outputs}),4)
        self.assertEqual(restarted.requests,[])

    def test_final_publication_receipt_failure_keeps_every_library_identity(self):
        project=self.studio.production.procedural(self.intent());identifier=project['id']
        self.studio.production.start(identifier);self.studio.queue.get_nowait();write=procedural._write
        def fail_final(path,value):
            write(path,value)
            if value.get('publication_status')=='published':raise OSError('final receipt barrier unavailable')
        with patch.object(procedural.factory,'build',side_effect=fake_build),patch.object(procedural,'_write',side_effect=fail_final):
            self.studio.production.run(identifier)
        result=self.studio.production.get(identifier);job_id=result['state']['attempts']['0']['job_id'];job=self.studio.jobs[job_id]
        self.assertEqual(result['state']['status'],'uncertain');self.assertFalse(job.get('failure_files'))
        ids=[o['asset_id'] for o in job['outputs']];self.assertEqual(len(ids),4)
        self.assertEqual({a['id'] for a in self.studio.assets.snapshot()['assets']},set(ids))
        self.studio.production.resume(identifier)
        with patch.object(procedural.factory,'build') as build:self.studio.production.run(identifier)
        build.assert_not_called();self.assertEqual(self.studio.production.get(identifier)['state']['status'],'completed')
        self.assertEqual([o['asset_id'] for o in self.studio.jobs[job_id]['outputs']],ids)
        self.assertEqual(len(self.studio.assets.snapshot()['assets']),4)

    def test_lost_publication_receipt_and_bad_retained_output_keep_prior_library_evidence(self):
        project=self.studio.production.procedural(self.intent());identifier=project['id']
        self.studio.production.start(identifier);self.studio.queue.get_nowait();write=procedural._write
        def fail_after_first_insert(path,value):
            if self.studio.assets.snapshot()['assets']:raise OSError('receipt storage unavailable after first insert')
            return write(path,value)
        with patch.object(procedural.factory,'build',side_effect=fake_build),patch.object(procedural,'_write',side_effect=fail_after_first_insert):
            self.studio.production.run(identifier)
        result=self.studio.production.get(identifier);job_id=result['state']['attempts']['0']['job_id']
        self.assertEqual(result['state']['status'],'uncertain');self.assertEqual(len(self.studio.jobs[job_id]['outputs']),1)
        first_id=self.studio.jobs[job_id]['outputs'][0]['asset_id'];self.assertEqual(len(self.studio.assets.snapshot()['assets']),1)
        directory=self.studio.production.root/identifier;receipt=(directory/'procedural-job.json').read_bytes()
        target=directory/'procedural/asset_LOD1.glb';original=target.read_bytes();target.write_bytes(b'changed after partial publication')
        with patch.object(threading.Thread,'start',lambda *_:None):restarted=FakeStudio(self.root,[])
        restarted.production.resume(identifier)
        with patch.object(procedural.factory,'build') as build,patch.object(restarted.assets,'register',wraps=restarted.assets.register) as register:
            restarted.production.run(identifier)
        build.assert_not_called();register.assert_not_called()
        self.assertEqual(restarted.production.get(identifier)['state']['status'],'uncertain')
        self.assertEqual([o['asset_id'] for o in restarted.jobs[job_id]['outputs']],[first_id])
        self.assertEqual(len(restarted.assets.snapshot()['assets']),1)
        self.assertEqual((directory/'procedural-job.json').read_bytes(),receipt,'Revalidation cannot overwrite retained publication evidence')
        target.write_bytes(original);restarted.production.resume(identifier)
        with patch.object(procedural.factory,'build') as build:restarted.production.run(identifier)
        build.assert_not_called();self.assertEqual(restarted.production.get(identifier)['state']['status'],'completed')
        self.assertEqual(restarted.jobs[job_id]['outputs'][0]['asset_id'],first_id)
        self.assertEqual(len(restarted.assets.snapshot()['assets']),4)


if __name__=='__main__':unittest.main()
