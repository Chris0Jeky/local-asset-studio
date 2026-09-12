"""Fault contracts for the owned voice runner; no weights/network in tests."""
import json
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
        self.manifest={'schema_version':1,'model_id':'hexgrad/Kokoro-82M','revision':'a'*40,'python':sys.executable,'voice':'af_heart','lang_code':'a','files':files,'versions':{},'license':{'id':'fixture'}}
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
        self.assertEqual(plan['bundle']['files'],self.manifest['files']);self.assertEqual(self.studio.requests,[])
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
    def test_owned_queue_outputs_dry_and_scene_copies_with_full_recipe(self):
        prepared=self.prepare();self.production.start(prepared['id'])
        self.assertEqual(self.studio.queue.get_nowait(),('production',prepared['id']))
        with patch('voice_baseline._run_owned',side_effect=self.fake_execute):self.production.run(prepared['id'])
        project=self.production.get(prepared['id']);self.assertEqual(project['state']['status'],'completed',project)
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
        run.assert_not_called();self.assertEqual(self.production.get(prepared['id'])['state']['status'],'interrupted')
        with self.assertRaisesRegex(ValueError,'never automatically repeated'):self.production.resume(prepared['id'])
        self.assertTrue(next(iter(self.studio.jobs.values()))['native_recipe']['bundle'])
    def test_cancel_before_execution_does_not_start_child(self):
        prepared=self.prepare();self.production.start(prepared['id']);self.production.stop(prepared['id'])
        with patch('voice_baseline._run_owned') as run:self.production.run(prepared['id'])
        run.assert_not_called();self.assertEqual(self.production.get(prepared['id'])['state']['status'],'cancelled')
