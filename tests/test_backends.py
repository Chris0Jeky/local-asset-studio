import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from test_server import server, FakeStudio, GRAPH, PRESET
from backends import BackendManager


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        for name in ('config','presets','workflows/api','comfy'):(self.root/name).mkdir(parents=True,exist_ok=True)
        (self.root/'config/local.json').write_text(json.dumps({'comfy_root':str(self.root/'comfy')}))
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[PRESET]}))
        (self.root/'workflows/api/demo-api.json').write_text(json.dumps(GRAPH))
        self.threads=patch.object(threading.Thread,'start',lambda *_:None);self.threads.start()
        self.studio=FakeStudio(self.root,[{'queue_running':[],'queue_pending':[]},{'prompt_id':'old-runtime'}, {'old-runtime':{'status':{'status_str':'success'},'outputs':{}}}])
    def tearDown(self):
        self.threads.stop();self.tmp.cleanup()

    def test_only_exact_entry_python_and_loopback_process_are_owned(self):
        profile=self.studio.backends.profiles['primary'];argv=[profile['python'],profile['entry'],'--listen','127.0.0.1','--port','8188']
        self.assertTrue(BackendManager.matches_configured_process(profile,profile['python'],argv,profile['root']))
        for bad in ([profile['python'],'another.py',*argv[2:]], [*argv[:-1],'8199'], [*argv[:3],'0.0.0.0',*argv[4:]]):
            self.assertFalse(BackendManager.matches_configured_process(profile,profile['python'],bad,profile['root']))
        self.assertFalse(BackendManager.matches_configured_process(profile,str(self.root/'foreign.exe'),argv,profile['root']))

    def test_local_uncertain_and_external_queue_each_prevent_switch(self):
        manager=self.studio.backends
        with patch.object(manager,'available',return_value=True),patch.object(manager,'request',return_value={'queue_running':[],'queue_pending':[]}):
            self.studio.jobs['unknown']={'status':'uncertain'}
            with self.assertRaisesRegex(ValueError,'reconcile'):manager.switch('hidream')
            self.studio.jobs.clear()
            with patch.object(manager,'request',return_value={'queue_pending':[['external-job']]}):
                with self.assertRaisesRegex(ValueError,'queue was preserved'):manager.switch('hidream')
            self.assertFalse(manager.busy)

    def test_generation_cannot_enter_during_switch_and_old_job_keeps_backend(self):
        manager=self.studio.backends;manager.busy=True
        with self.assertRaisesRegex(ValueError,'switch is running'):self.studio.create_job({'preset_id':'demo'})
        self.assertTrue(self.studio.queue.empty());manager.busy=False
        job=self.studio.create_job({'preset_id':'demo'});internal=self.studio.jobs[job['id']]
        original=internal['comfy_url'];manager.activate('hidream')
        self.studio._run(internal)
        self.assertTrue(self.studio.requests)
        for args,kwargs in self.studio.requests:
            if args[0].startswith(('/queue','/prompt','/history')):self.assertEqual(kwargs['base_url'],original)
        with self.assertRaisesRegex(ValueError,'Main library'):self.studio.prepare({'preset_id':'demo'})

    def test_restart_keeps_interrupted_switch_and_does_not_launch(self):
        state=self.root/'.runtime/backend-state.json';state.parent.mkdir(exist_ok=True)
        state.write_text(json.dumps({'active':'hidream','operation':{'status':'running','target':'primary'}}))
        manager=BackendManager(self.studio)
        self.assertEqual(manager.active,'hidream');self.assertEqual(manager.operation['status'],'interrupted')
        self.assertFalse(manager.busy)
