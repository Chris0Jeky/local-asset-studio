"""Fault contracts for the owned voice runner; no weights/network in tests."""
import json
import importlib.metadata
from pathlib import Path
import subprocess
import sys
import threading
import unittest
import wave
from unittest.mock import patch
import test_production
from test_server import FakeStudio
from studio_av.project import file_hash
import voice_baseline


class VoiceTests(unittest.TestCase):
    def setUp(self):
        test_production.ProductionTests.setUp(self);self.studio=FakeStudio(self.root,[]);self.production=self.studio.production
        (self.root/'scripts').mkdir();(self.root/'scripts/kokoro_baseline.py').write_text('# inert fixture',encoding='utf-8')
        files={}
        for role in ('config','model','voice'):
            path=self.root/(role+'.bin');path.write_bytes(role.encode());files[role]={'path':str(path),'bytes':path.stat().st_size,'sha256':file_hash(path)}
        (self.root/'scripts/voice_runtime_probe.py').write_bytes((Path(__file__).parents[1]/'scripts/voice_runtime_probe.py').read_bytes())
        self.manifest={'schema_version':1,'model_id':'hexgrad/Kokoro-82M','revision':'a'*40,'python':sys.executable,'voice':'af_heart','lang_code':'a','files':files,'versions':{'pip':importlib.metadata.version('pip')},'license':{'id':'fixture'}}
        self.manifest_path=self.root/'bundle.json';self.manifest_path.write_text(json.dumps(self.manifest),encoding='utf-8')
        self.studio.config.update(voice_baseline_bundle=str(self.manifest_path),ffmpeg=sys.executable)
    def tearDown(self):test_production.ProductionTests.tearDown(self)
    def prepare(self):return self.production.voice_baseline({'name':'Original voice test','speaker_id':'atelier-witch','lines':[{'id':'hello','text':'The lantern is ready.'}]})
    def fake_execute(self,command,log,timeout,cancel):
        log.write_text('inert execution',encoding='utf-8')
        if '--output' in command:
            output=Path(command[command.index('--output')+1]);output.mkdir()
            path=output/'hello.wav'
            with wave.open(str(path),'wb') as w:w.setparams((1,2,24000,0,'NONE',''));w.writeframes(b'\0'*4800)
            (output/'receipt.json').write_text(json.dumps({'lines':[{'id':'hello','sha256':file_hash(path),'samples':2400}]}),encoding='utf-8')
        else:
            path=Path(command[-1])
            with wave.open(str(path),'wb') as w:w.setparams((1,2,48000,0,'NONE',''));w.writeframes(b'\0'*9600)
    def test_prepare_is_pinned_and_does_not_run_or_queue(self):
        with patch('voice_baseline._run_owned') as run:prepared=self.prepare()
        run.assert_not_called();self.assertEqual(prepared['state']['status'],'planned');self.assertEqual(self.studio.queue.qsize(),0)
        plan=self.production._get(prepared['id'])['plan'];self.assertEqual(plan['lines'][0]['id'],'hello')
        self.assertEqual(plan['bundle']['files'],self.manifest['files']);self.assertEqual(plan['observed_versions'],self.manifest['versions']);self.assertEqual(self.studio.requests,[])
    def test_page_capabilities_does_not_load_or_hash_models(self):
        with patch('voice_baseline.file_hash',side_effect=AssertionError('unexpected hash')):self.assertTrue(voice_baseline.capabilities(self.studio)['configured'])
    def test_bad_line_ids_and_unbounded_requests_fail_before_writes(self):
        for lines in ([{'id':'../escape','text':'x'}],[{'id':'a','text':'x'}]*2,[{'id':'a','text':'x'*601}]):
            with self.assertRaises(ValueError):self.production.voice_baseline({'name':'Test','speaker_id':'speaker','lines':lines})
        self.assertEqual(self.production.list(),[])
    def test_changed_model_rejects_prepare_and_execution(self):
        prepared=self.prepare();Path(self.manifest['files']['model']['path']).write_bytes(b'other')
        with self.assertRaisesRegex(ValueError,'changed'):self.prepare()
        self.production.start(prepared['id'])
        with patch('voice_baseline._run_owned') as run:self.production.run(prepared['id'])
        run.assert_not_called();self.assertEqual(self.production.get(prepared['id'])['state']['status'],'failed')
        self.assertEqual(self.production.get(prepared['id'])['state']['attempts']['0']['status'],'failed')

    def test_manifest_package_drift_rejects_prepare_and_observed_drift_rejects_start(self):
        self.manifest['versions']['pip']='not-the-installed-version';self.manifest_path.write_text(json.dumps(self.manifest),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'package versions changed from the bundle manifest'):self.prepare()
        self.manifest['versions']['pip']=importlib.metadata.version('pip');self.manifest_path.write_text(json.dumps(self.manifest),encoding='utf-8')
        prepared=self.prepare();self.production.start(prepared['id'])
        with patch('voice_baseline.observed_versions',return_value={'pip':'new-version'}),patch('voice_baseline._run_owned') as run:
            self.production.run(prepared['id'])
        run.assert_not_called();attempt=self.production.get(prepared['id'])['state']['attempts']['0']
        self.assertEqual(attempt['status'],'failed');self.assertEqual(self.production.get(prepared['id'])['state']['status'],'failed')
    def test_owned_queue_outputs_dry_and_scene_copies_with_full_recipe(self):
        prepared=self.prepare();self.production.start(prepared['id'])
        self.assertEqual(self.studio.queue.get_nowait(),('production',prepared['id']))
        with patch('voice_baseline._run_owned',side_effect=self.fake_execute):self.production.run(prepared['id'])
        project=self.production.get(prepared['id']);self.assertEqual(project['state']['status'],'completed',project)
        self.assertEqual(project['state']['attempts']['0']['status'],'completed')
        job=next(iter(self.studio.jobs.values()));self.assertEqual(job['operation'],voice_baseline.OPERATION)
        self.assertEqual(job['native_recipe']['lines'][0]['text'],'The lantern is ready.')
        self.assertEqual([o['filename'] for o in job['outputs']],['hello.wav','hello-scene.wav'])
        self.assertTrue(all(o.get('asset_id') for o in job['outputs']));self.assertEqual(self.studio.requests,[])
        artifact=project['state']['artifacts'][0];path=self.production.file(prepared['id'],artifact['path']);path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'artifact changed'):self.production.file(prepared['id'],artifact['path'])
    def test_timeout_is_durable_and_never_automatically_repeated(self):
        prepared=self.prepare();self.production.start(prepared['id'])
        with patch('voice_baseline._run_owned',side_effect=subprocess.TimeoutExpired('owned child',180)) as run:self.production.run(prepared['id'])
        self.assertEqual(run.call_count,1);self.assertEqual(self.production.get(prepared['id'])['state']['status'],'failed')
        self.assertTrue((self.production.root/prepared['id']/'request.json').is_file())
        with patch('voice_baseline._run_owned') as run:self.production.run(prepared['id'])
        run.assert_not_called();self.assertEqual(self.production.get(prepared['id'])['state']['status'],'failed')
        with self.assertRaisesRegex(ValueError,'Only an interrupted'):self.production.resume(prepared['id'])
        self.assertTrue(next(iter(self.studio.jobs.values()))['native_recipe']['bundle'])
    def test_cancel_before_execution_does_not_start_child(self):
        prepared=self.prepare();self.production.start(prepared['id']);self.production.stop(prepared['id'])
        with patch('voice_baseline._run_owned') as run:self.production.run(prepared['id'])
        run.assert_not_called();state=self.production.get(prepared['id'])['state'];self.assertEqual(state['status'],'cancelled');self.assertEqual(state['attempts']['0']['status'],'cancelled')

    def test_only_unstarted_voice_plan_can_explicitly_resume(self):
        prepared=self.prepare();self.production._mutate(prepared['id'],status='interrupted')
        resumed=self.production.resume(prepared['id']);self.assertEqual(resumed['state']['status'],'queued')
        self.assertEqual(self.studio.queue.get_nowait(),('production',prepared['id']))
        unsafe=self.prepare();self.production._attempt(unsafe['id'],0,operation=voice_baseline.OPERATION,job_id='a'*32,status='running')
        self.production._mutate(unsafe['id'],status='interrupted')
        with self.assertRaisesRegex(ValueError,'durable voice attempt'):self.production.resume(unsafe['id'])
        self.assertTrue(self.studio.queue.empty())

    def test_queued_voice_resume_does_not_duplicate_the_owned_queue_item(self):
        prepared=self.prepare();self.production.start(prepared['id'])
        with self.assertRaisesRegex(ValueError,'Only an interrupted'):self.production.resume(prepared['id'])
        self.assertEqual(self.studio.queue.qsize(),1)

    def test_voice_resume_eligibility_refuses_every_durable_execution_marker(self):
        prepared=self.prepare();self.production._mutate(prepared['id'],status='interrupted')
        self.assertTrue(self.production.get(prepared['id'])['voice_resume']['eligible'])
        cases=(
            ('request',lambda identifier:(self.production.root/identifier/'request.json').write_text('{}')),
            ('attempt',lambda identifier:self.production._attempt(identifier,0,status='interrupted')),
            ('job',lambda identifier:(self.studio.runs/voice_baseline.uuid.uuid5(voice_baseline.uuid.NAMESPACE_URL,'studio-voice:'+identifier).hex).mkdir()),
            ('output',lambda identifier:(self.production.root/identifier/'voice').mkdir()),
        )
        for marker,write in cases:
            take=self.prepare();self.production._mutate(take['id'],status='interrupted');write(take['id'])
            eligibility=self.production.get(take['id'])['voice_resume']
            self.assertFalse(eligibility['eligible'],marker)
            with self.assertRaisesRegex(ValueError,'will not retry|durable voice attempt'):self.production.resume(take['id'])

    def test_restart_marks_nested_running_voice_attempt_interrupted_without_queueing(self):
        prepared=self.prepare();self.production.start(prepared['id'])
        self.production._attempt(prepared['id'],0,operation=voice_baseline.OPERATION,job_id='a'*32,status='running',started_at=1)
        recovered=FakeStudio(self.root,[]).production.get(prepared['id'])
        self.assertEqual(recovered['state']['status'],'interrupted')
        self.assertEqual(recovered['state']['attempts']['0']['status'],'interrupted')
        self.assertIn('no inference was resumed',recovered['state']['message'])
        self.assertTrue(FakeStudio(self.root,[]).queue.empty())

    def test_stop_during_workspace_publication_preserves_registered_outputs(self):
        prepared=self.prepare();self.production.start(prepared['id']);original=self.studio.index_outputs
        def index_then_stop(job):
            original(job);self.production.stop(prepared['id'])
        with patch.object(self.studio,'index_outputs',side_effect=index_then_stop),patch('voice_baseline._run_owned',side_effect=self.fake_execute):
            self.production.run(prepared['id'])
        project=self.production.get(prepared['id']);job=next(iter(self.studio.jobs.values()))
        self.assertEqual(project['state']['status'],'completed');self.assertTrue(project['state']['cancellation_too_late'])
        self.assertEqual(project['state']['attempts']['0']['status'],'completed')
        self.assertEqual(job['publication_status'],'published');self.assertTrue(job['cancellation_too_late']);self.assertTrue(all(output.get('asset_id') for output in job['outputs']))

    def test_partial_workspace_publication_never_claims_stop_was_too_late(self):
        prepared=self.prepare();self.production.start(prepared['id'])
        def partial_index(job):
            job['outputs'][0]['asset_id']='retained-first-output';self.production.stop(prepared['id'])
        with patch.object(self.studio,'index_outputs',side_effect=partial_index),patch('voice_baseline._run_owned',side_effect=self.fake_execute):
            self.production.run(prepared['id'])
        project=self.production.get(prepared['id']);job=next(iter(self.studio.jobs.values()))
        self.assertEqual(project['state']['status'],'failed')
        self.assertNotIn('cancellation_too_late',project['state'])
        self.assertEqual(job['publication_status'],'failed')
        self.assertEqual(job['outputs'][0]['asset_id'],'retained-first-output')
