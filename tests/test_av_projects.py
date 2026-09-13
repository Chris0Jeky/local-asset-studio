"""Shared scene edits, owned queue execution and provenance on synthetic media."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import unittest
import wave
import zipfile
from unittest.mock import patch

from http_refusal_transport import atomic_json_post
import test_production
from test_server import FakeStudio, png
from studio_av import project as av
from studio_av.render import _run_owned, RenderCancelled


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'Configured FFmpeg fixture required')
class SceneTests(unittest.TestCase):
    def setUp(self):
        test_production.ProductionTests.setUp(self)
        self.studio=FakeStudio(self.root,[])
        self.patches[0].stop()
        self.studio.config.update({n:shutil.which(n) for n in ('ffmpeg','ffprobe')})
        self.scenes=self.studio.production.av
        self.asset=self.studio.import_image('source.png','image/png',png())['asset']

    def tearDown(self):test_production.ProductionTests.tearDown(self)

    def create(self,**kw):
        return self.scenes.create(dict(action='create',name='Scene fixture',asset_ids=[self.asset['id']],frames_per_shot=24,**kw))

    def change(self,doc,action='edit',**kw):
        return self.scenes.command(doc['id'],dict(action=action,expected_revision=doc['revision'],actor='agent',**kw))

    @staticmethod
    def fixture_render(project,directory,out,**kwargs):
        out.mkdir(parents=True,exist_ok=True)
        (out/'preview.mp4').write_bytes(b'inert preview')
        (out/'mix.wav').write_bytes(b'inert audio')
        return {'fixture':True}

    def test_create_is_snapshot_and_never_queues_or_generates(self):
        doc=self.create();self.assertEqual(doc['revision'],0)
        self.assertEqual(self.studio.queue.qsize(),0);self.assertEqual(self.studio.requests,[])
        self.assertEqual(doc['sources'][0]['asset_id'],self.asset['id'])
        self.assertEqual(self.scenes.source(doc['id'],'source0').read_bytes(),png())
        self.assertEqual(self.studio.production.get(doc['id'])['budget']['reserved'],0)
        for method in (self.studio.production.start,self.studio.production.resume):
            with self.assertRaises(ValueError):method(doc['id'])

    def test_revision_conflict_and_restore_keep_append_only_history(self):
        doc=self.create();changed=self.change(doc,section='shots',clip_id='shot0',changes={'frames':48})
        with self.assertRaisesRegex(ValueError,'Scene conflict'):
            self.change(doc,section='shots',clip_id='shot0',changes={'frames':12})
        restored=self.change(changed,'restore',source_revision=0)
        self.assertEqual(restored['revision'],2);self.assertEqual(restored['timing']['frames'],24)
        self.assertEqual([e['revision'] for e in restored['history']],[2,1,0])
        self.assertEqual(restored['history'][1]['actor'],'agent')
        self.assertEqual(self.studio.queue.qsize(),0)

    def test_two_clients_racing_have_exactly_one_revision_winner(self):
        from concurrent.futures import ThreadPoolExecutor
        doc=self.create()
        def update(frames):
            try:return self.change(doc,section='shots',clip_id='shot0',changes={'frames':frames})['revision']
            except ValueError as exc:
                self.assertIn('Scene conflict',str(exc));return 'conflict'
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(update,[36,48]))
        self.assertCountEqual(results,[1,'conflict']);self.assertEqual(len(self.scenes.inspect(doc['id'])['history']),2)

    def test_http_commands_share_cas_and_serve_only_hashed_source_ranges(self):
        from http.client import HTTPConnection
        from http.server import ThreadingHTTPServer
        from test_server import server
        handler=type('SceneHTTPFixture',(server.Handler,),{'studio':self.studio})
        http=ThreadingHTTPServer(('127.0.0.1',0),handler)
        worker=threading.Thread(target=http.serve_forever,daemon=True);worker.start()
        def request(method,path,payload=None,headers=None):
            conn=HTTPConnection('127.0.0.1',http.server_port,timeout=10)
            try:
                origin='http://127.0.0.1:8191'
                conn.request(method,path,json.dumps(payload) if payload else None,{'Host':'127.0.0.1:8191','Origin':origin,'Content-Type':'application/json',**(headers or {})})
                response=conn.getresponse();return response.status,response.read()
            finally:conn.close()
        try:
            status,raw=request('POST','/api/av',{'action':'create','name':'HTTP scene','asset_ids':[self.asset['id']],'frames_per_shot':24})
            self.assertEqual(status,201);doc=json.loads(raw)
            command={'action':'edit','expected_revision':0,'section':'shots','clip_id':'shot0','changes':{'frames':48}}
            status,raw=request('POST','/api/av/'+doc['id'],command)
            self.assertEqual(status,200);self.assertEqual(json.loads(raw)['revision'],1)
            status,raw=request('POST','/api/av/'+doc['id'],command)
            self.assertEqual(status,400);self.assertIn('Scene conflict',raw.decode())
            status,data=request('GET',doc['sources'][0]['url'],headers={'Range':'bytes=0-7'})
            self.assertEqual(status,206);self.assertEqual(data,png()[:8])
            self.assertEqual(atomic_json_post(http.server_port,'/api/av/'+doc['id'],json.dumps(command).encode(),origin='https://evil.invalid')[0],403)
            self.assertEqual(request('GET','/api/production/'+doc['id']+'/files/inputs/source0.png')[0],400)
            self.assertEqual(self.studio.queue.qsize(),0)
        finally:http.shutdown();http.server_close();worker.join(2)

    def test_proposal_is_read_only_and_bad_edit_is_atomic(self):
        doc=self.create();proposal=self.change(doc,'preview',section='shots',clip_id='shot0',changes={'frames':48})
        self.assertTrue(proposal['proposal']);self.assertEqual(proposal['timing']['frames'],48)
        self.assertEqual(self.scenes.inspect(doc['id'])['revision'],0)
        with self.assertRaises(ValueError):self.change(doc,section='shots',clip_id='shot0',changes={'frames':48,'source_in':1})
        self.assertEqual(self.scenes.inspect(doc['id'])['timing']['frames'],24)

    def test_split_move_and_overlay_bounds_are_validated_together(self):
        doc=self.create();doc=self.change(doc,'split',section='shots',clip_id='shot0',at=12)
        self.assertEqual(doc['timing']['frames'],24);second=doc['project']['shots'][1]['id']
        doc=self.change(doc,'move',clip_id=second,index=0)
        self.assertEqual(doc['project']['shots'][0]['id'],second)
        doc=self.change(doc,'add',section='overlays',asset_key='source0')
        overlay=doc['project']['overlays'][0]['id']
        with self.assertRaises(ValueError):self.change(doc,section='overlays',clip_id=overlay,changes={'x':639})
        self.assertEqual(self.scenes.inspect(doc['id'])['revision'],doc['revision'])

    def test_export_reuses_revision_pack_and_detects_tampering(self):
        doc=self.create();export=self.change(doc,'export');again=self.change(doc,'export')
        self.assertEqual(export['export_url'],again['export_url'])
        relative=export['export_url'].split('/files/')[1].split('?')[0]
        path=self.studio.production.file(doc['id'],relative)
        with zipfile.ZipFile(path) as pack:
            self.assertEqual(pack.read('inputs/source0.png'),png())
            self.assertEqual(json.loads(pack.read('history.json'))[0]['revision'],0)
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'artifact changed'):self.change(doc,'export')

    def test_source_change_prevents_edit_render_and_download(self):
        doc=self.create();self.scenes.source(doc['id'],'source0').write_bytes(b'changed')
        for operation in (lambda:self.change(doc,section='shots',clip_id='shot0',changes={'frames':48}),
                          lambda:self.change(doc,'render'),lambda:self.scenes.source(doc['id'],'source0')):
            with self.assertRaises(ValueError):operation()
        self.assertEqual(self.studio.queue.qsize(),0)

    def test_queue_cancellation_and_restart_never_resubmit(self):
        doc=self.create();queued=self.change(doc,'render');attempt=queued['render']['id']
        self.assertEqual(self.studio.queue.get_nowait(),('production',doc['id']))
        with self.assertRaisesRegex(ValueError,'active render'):self.change(doc,'render')
        with self.assertRaisesRegex(ValueError,'no longer active'):self.scenes.cancel(doc['id'],'wrong-attempt')
        self.scenes.cancel(doc['id'],attempt)
        with patch('av_projects.render') as render:self.studio.production.run(doc['id'])
        render.assert_not_called();self.assertEqual(self.scenes.inspect(doc['id'])['render']['status'],'cancelled')
        queued=self.change(doc,'render')
        with patch.object(threading.Thread,'start',lambda *_:None):restarted=FakeStudio(self.root,[])
        self.assertEqual(restarted.queue.qsize(),0)
        self.assertEqual(restarted.production.av.inspect(doc['id'])['render']['status'],'interrupted')
        self.assertEqual(restarted.production.get(doc['id'])['state']['status'],'interrupted')
        self.assertEqual(restarted.requests,[])

    def test_real_render_pins_revision_and_publishes_parent_lineage(self):
        doc=self.create();queued=self.change(doc,'render');attempt=queued['render']['id']
        changed=self.change(doc,section='shots',clip_id='shot0',changes={'frames':48})
        self.studio.production.run(doc['id']);result=self.scenes.inspect(doc['id'])
        self.assertEqual(result['render']['status'],'completed',result['render'])
        self.assertEqual(result['revision'],1);self.assertTrue(result['render']['stale'])
        self.assertEqual(result['render']['preview_revision'],0)
        job=self.studio.jobs[attempt];self.assertEqual(job['parent_assets'],[self.asset['id']])
        self.assertEqual(job['native_recipe']['revision'],0)
        self.assertEqual(job['native_recipe']['receipt']['audio_qc']['samples'],48000)
        self.assertTrue(all(o.get('asset_id') for o in job['outputs']))
        self.assertEqual(self.studio.assets.get(job['outputs'][0]['asset_id'])['lineage'],[self.asset['id']])
        self.assertEqual(self.studio.requests,[])
        # A cancelled newer attempt must keep the older preview clearly stale.
        queued=self.change(changed,'render');self.scenes.cancel(doc['id'],queued['render']['id'])
        self.studio.production.run(doc['id']);last=self.scenes.inspect(doc['id'])
        self.assertEqual(last['render']['preview_url'],result['render']['preview_url'])

    def test_publication_first_save_failure_does_not_index_assets(self):
        doc=self.create();queued=self.change(doc,'render');attempt=queued['render']['id'];before={a['id'] for a in self.studio.assets.snapshot()['assets']}
        original_save=self.studio._save;calls=[]
        def save(job):
            calls.append(job['status'])
            if len(calls)==1:raise OSError('first durable save failed')
            return original_save(job)
        with patch('av_projects.render',side_effect=self.fixture_render),patch.object(self.studio,'_save',side_effect=save):
            self.studio.production.run(doc['id'])
        self.assertEqual({a['id'] for a in self.studio.assets.snapshot()['assets']},before)
        state=json.loads((self.studio.runs/attempt/'state.json').read_text())
        self.assertEqual(state['status'],'failed');self.assertEqual(state['publication_status'],'failed')
        self.assertEqual(state['native_recipe']['source_assets'][0]['asset_id'],self.asset['id'])

    def _restart_with_register_spy(self):
        from test_server import server
        calls=[];original=server.AssetWorkspace.register
        def register(workspace,job,index,source):
            if job.get('operation') == 'native.av-preview.v1':calls.append((job['id'],index))
            return original(workspace,job,index,source)
        with patch.object(server.AssetWorkspace,'register',register),patch.object(threading.Thread,'start',lambda *_:None):
            restarted=FakeStudio(self.root,[])
        return restarted,calls

    def test_restart_does_not_republish_failed_av_attempt_after_first_save_failure(self):
        doc=self.create();queued=self.change(doc,'render');attempt=queued['render']['id']
        before={a['id'] for a in self.studio.assets.snapshot()['assets']}
        with patch('av_projects.render',side_effect=self.fixture_render),patch.object(self.studio,'_save',side_effect=OSError('first durable save failed')):
            self.studio.production.run(doc['id'])
        state_path=self.studio.runs/attempt/'state.json';before_state=json.loads(state_path.read_text())
        restarted,calls=self._restart_with_register_spy()
        self.assertEqual(calls,[])
        self.assertEqual({a['id'] for a in restarted.assets.snapshot()['assets']},before)
        self.assertEqual(json.loads(state_path.read_text()),before_state)

    def test_restart_does_not_republish_partial_failed_av_attempt(self):
        doc=self.create();queued=self.change(doc,'render');attempt=queued['render']['id']
        original_register=self.studio.assets.register
        def register(job,index,source):
            if index==1:raise OSError('second output register failed')
            return original_register(job,index,source)
        original_save=self.studio._save;save_calls=[]
        def save(job):
            save_calls.append(job['status'])
            if len(save_calls)==2:raise OSError('later durable save failed')
            return original_save(job)
        with patch('av_projects.render',side_effect=self.fixture_render),patch.object(self.studio.assets,'register',side_effect=register),patch.object(self.studio,'_save',side_effect=save):
            self.studio.production.run(doc['id'])
        state_path=self.studio.runs/attempt/'state.json';before_state=json.loads(state_path.read_text())
        before={a['id'] for a in self.studio.assets.snapshot()['assets']}
        restarted,calls=self._restart_with_register_spy()
        self.assertEqual(calls,[])
        self.assertEqual({a['id'] for a in restarted.assets.snapshot()['assets']},before)
        self.assertEqual(json.loads(state_path.read_text()),before_state)

    def test_restart_indexes_completed_and_legacy_av_attempts(self):
        doc=self.create();queued=self.change(doc,'render');attempt=queued['render']['id']
        with patch('av_projects.render',side_effect=self.fixture_render):self.studio.production.run(doc['id'])
        legacy_id='a'*32;out=self.studio.experiments/'projects'/legacy_id/'renders/legacy';out.mkdir(parents=True)
        (out/'preview.mp4').write_bytes(b'inert preview');(out/'mix.wav').write_bytes(b'inert audio')
        legacy={'id':'legacy-av','operation':'native.av-preview.v1','project_id':legacy_id,'status':'completed','created_at':time.time(),
                'preset_id':'av-preview','preset_name':'Legacy preview','controls':{},'batch_count':1,'prompt_ids':[],'submissions':[],
                'parent_assets':[],'references':[],'graph_path':'','graph':{},'native_recipe':{},
                'outputs':[{'filename':'preview.mp4','native_path':'renders/legacy/preview.mp4','type':'output','media_type':'video'},
                           {'filename':'mix.wav','native_path':'renders/legacy/mix.wav','type':'output','media_type':'audio'}]}
        self.studio.jobs[legacy['id']]=legacy;(self.studio.runs/legacy['id']).mkdir();self.studio._save(legacy)
        restarted,calls=self._restart_with_register_spy()
        self.assertCountEqual([job_id for job_id,index in calls], [attempt,attempt,legacy['id'],legacy['id']])
        self.assertTrue(all(restarted.jobs[job_id]['outputs'][index].get('asset_id') for job_id,index in calls))

    def test_publication_register_and_later_save_failure_retains_recipe_and_partial_assets(self):
        doc=self.create();queued=self.change(doc,'render');attempt=queued['render']['id']
        original_register=self.studio.assets.register
        def register(job,index,source):
            if index==1:raise OSError('second output register failed')
            return original_register(job,index,source)
        original_save=self.studio._save;calls=[]
        def save(job):
            calls.append(job['status'])
            if len(calls)==2:raise OSError('later durable save failed')
            return original_save(job)
        with patch('av_projects.render',side_effect=self.fixture_render),patch.object(self.studio.assets,'register',side_effect=register),patch.object(self.studio,'_save',side_effect=save):
            self.studio.production.run(doc['id'])
        state=json.loads((self.studio.runs/attempt/'state.json').read_text())
        self.assertEqual(state['status'],'failed');self.assertEqual(state['publication_status'],'failed')
        self.assertEqual(state['native_recipe']['source_assets'][0]['asset_id'],self.asset['id'])
        self.assertEqual(state['outputs'][0]['asset_id'],self.studio.jobs[attempt]['outputs'][0]['asset_id'])
        self.assertIn('publication_error',state['diagnostics'])
        self.assertEqual(self.studio.assets.get(state['outputs'][0]['asset_id'])['lineage'],[self.asset['id']])
        restarted=FakeStudio(self.root,[])
        self.assertEqual(restarted.jobs[attempt]['native_recipe']['source_assets'][0]['asset_id'],self.asset['id'])
        self.assertEqual(restarted.jobs[attempt]['outputs'][0]['asset_id'],state['outputs'][0]['asset_id'])

    def test_audio_source_range_is_checked_before_revision_commit(self):
        # Register a synthetic output through the same Workspace path as runtime audio.
        audio=self.root/'fake-comfy/output/tone.wav';audio.parent.mkdir()
        with wave.open(str(audio),'wb') as w:w.setparams((1,2,48000,0,'NONE',''));w.writeframes(b'\0'*96000)
        job={'id':'synthetic-audio','preset_id':'fixture','preset_name':'Fixture','created_at':time.time(),'controls':{},'outputs':[{'filename':'tone.wav','type':'output','media_type':'audio'}]}
        self.studio.index_outputs(job);audio_id=job['outputs'][0]['asset_id']
        doc=self.scenes.create({'action':'create','name':'Audio fixture','asset_ids':[self.asset['id'],audio_id],'frames_per_shot':24})
        clip=doc['project']['audio'][0]['id']
        with self.assertRaisesRegex(ValueError,'Audio source too short'):
            self.change(doc,section='audio',clip_id=clip,changes={'source_sample':1})
        doc=self.change(doc,section='audio',clip_id=clip,changes={'bus':'dialogue','gain_db':-6,'samples':24000,'fade_out':100})
        doc=self.change(doc,'split',section='audio',clip_id=clip,at=12000)
        self.assertEqual([c['source_sample'] for c in doc['project']['audio']],[0,12000])
        self.assertEqual([c['fade_out'] for c in doc['project']['audio']],[0,100])


class OwnedProcessTests(unittest.TestCase):
    def test_cancel_and_timeout_stop_only_owned_child_and_retain_log(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for cancel,error,name in ((lambda:True,RenderCancelled,'cancel'),(None,subprocess.TimeoutExpired,'timeout')):
                with self.assertRaises(error):_run_owned([sys.executable,'-c','import time; time.sleep(30)'],root/(name+'.log'),1,cancel)
                self.assertTrue((root/(name+'.log')).is_file())
