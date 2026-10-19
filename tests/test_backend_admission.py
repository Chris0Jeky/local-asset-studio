"""Server work admission observes shared switches before any browser status read."""
from contextlib import ExitStack
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_server import server, FakeStudio, GRAPH, PRESET
import backend_state


class BackendAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.root=Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        for name in ('config','presets','workflows/api','comfy/input','isolated/input'):
            (self.root/name).mkdir(parents=True,exist_ok=True)
        (self.root/'config/local.json').write_text(json.dumps({'comfy_root':str(self.root/'comfy'),'hidream_root':str(self.root/'isolated')}))
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[PRESET,dict(PRESET,id='isolated',backend_id='hidream')]}))
        (self.root/'workflows/api/demo-api.json').write_text(json.dumps(GRAPH))
        self.stack.enter_context(patch.object(threading.Thread,'start',lambda *_:None))
        self.launch=self.stack.enter_context(patch('backends.subprocess.Popen'))
        self.studio=FakeStudio(self.root,[]);self.manager=self.studio.backends;self.path=self.manager.state_path

    def post(self,path,payload=None):
        sent=[];handler=server.Handler.__new__(server.Handler);handler.studio=self.studio;handler.path=path
        handler._safe_mutation=lambda:True;handler._body_json=lambda:payload or {'preset_id':'demo'}
        handler._json=lambda status,value:sent.append((status,value));handler.do_POST()
        self.assertEqual(len(sent),1);return sent[0]

    def record(self,active='primary',operation=None):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.path.write_text(json.dumps({'active':active,'operation':operation}))

    def legacy(self):
        self.record(operation={'id':'legacy','status':'running','target':'hidream'})

    def uncertain_completion(self):
        manager=self.manager
        with self.studio.lock:manager._admit_shared();manager._begin_switch('hidream')
        replace=backend_state.file_replace.replace
        def publish(source,target):
            status=json.loads(Path(source).read_text())['operation']['status'];replace(source,target)
            if status=='completed':raise OSError('inert lost completion acknowledgement')
        process=SimpleNamespace(pid=902,create_time=lambda:99)
        with patch.object(manager,'available',return_value=True),patch.object(manager,'_idle',return_value=None), \
             patch.object(manager,'_check_startup_processes',return_value={}), \
             patch.object(manager,'process',side_effect=lambda p:process if p['id']=='hidream' else None), \
             patch.object(manager,'request',return_value={'system':{'ready':True},'devices':[]}), \
             patch.object(backend_state.file_replace,'replace',side_effect=publish):manager._switch('hidream')
        self.assertFalse(manager.busy);self.assertIsNotNone(manager.state_issue);self.assertEqual(manager.active,'primary')
        self.assertEqual(json.loads(self.path.read_text())['active'],'hidream');self.launch.assert_not_called()

    def test_uncertain_completion_refuses_the_first_http_job_until_explicit_resolution(self):
        self.uncertain_completion();raw=self.path.read_bytes()
        with patch.object(self.manager,'snapshot',side_effect=AssertionError('No browser status read')), \
             patch.object(self.manager,'request',side_effect=AssertionError('No runtime probe')):
            status,result=self.post('/api/jobs')
        self.assertEqual(status,400,result);self.assertIn('unconfirmed',result['error'])
        self.assertEqual(self.studio.jobs,{});self.assertTrue(self.studio.queue.empty())
        self.assertEqual(list(self.studio.runs.iterdir()),[]);self.assertEqual(self.path.read_bytes(),raw)
        self.assertEqual(self.studio.requests,[])
        command={'expected_sha256':hashlib.sha256(raw).hexdigest(),
                 'acknowledge_studios_closed':True,'acknowledge_runtimes_inspected':True}
        with patch.object(self.manager,'request',return_value={'system':{'ready':True},'devices':[]}):
            self.manager.resolve_switch_record(command)
        status,result=self.post('/api/jobs',{'preset_id':'isolated'})
        self.assertEqual(status,201,result)
        self.assertEqual(self.studio.jobs[result['id']]['comfy_url'],self.manager.profiles['hidream']['url'])
        self.launch.assert_not_called();self.assertEqual(self.studio.requests,[])

    def test_creation_and_preview_refuse_fresh_shared_blockers_without_mutating_switch_state(self):
        owner=dict(self.manager._owner,instance_id='another-studio')
        cases={
            'legacy':{'active':'primary','operation':{'status':'running','target':'hidream'}},
            'foreign':{'active':'primary','operation':{'status':'running','target':'hidream','owner':owner}},
            'inspection':{'active':'primary','operation':{'status':'interrupted','inspection_required':True}},
            'unknown-selection':{'active':'missing','operation':None},
            'different-selection':{'active':'hidream','operation':{'status':'completed','target':'hidream','owner':owner}},
            'malformed':{},
        }
        original_snapshot=self.manager._state_snapshot;original_operation=copy.deepcopy(self.manager.operation)
        read=self.manager._state.read
        def locked_read():
            self.assertTrue(self.studio.lock._is_owned(),'Admission must hold the job-registration lock')
            return read()
        for name,value in cases.items():
            with self.subTest(name=name):
                self.path.parent.mkdir(parents=True,exist_ok=True);self.path.write_text(json.dumps(value));raw=self.path.read_bytes()
                with patch.object(self.manager._state,'read',side_effect=locked_read), \
                     patch.object(self.manager,'snapshot',side_effect=AssertionError('No status fetch')), \
                     patch.object(self.manager,'request',side_effect=AssertionError('No runtime probe')):
                    for route in ('/api/jobs','/api/preview'):
                        status,result=self.post(route);self.assertEqual(status,400,(name,route,result))
                    with self.assertRaises(ValueError):self.studio.create_job({'preset_id':'demo'},enqueue=False)
                self.assertEqual(self.path.read_bytes(),raw);self.assertEqual(self.studio.jobs,{})
                self.assertTrue(self.studio.queue.empty());self.assertEqual(self.studio.requests,[])
                self.assertIs(self.manager._state_snapshot,original_snapshot);self.assertEqual(self.manager.operation,original_operation)
        self.launch.assert_not_called()

    def test_measured_preparation_preserves_known_refusals_and_unexpected_errors(self):
        self.legacy();raw=self.path.read_bytes()
        with patch.object(self.manager,'snapshot',side_effect=AssertionError('No status fetch')), \
             patch.object(self.manager,'request',side_effect=AssertionError('No runtime probe')):
            with self.assertRaisesRegex(server.PreparationError,'shared|legacy'):
                self.studio.prepare_for_large_job_preparation({'preset_id':'demo'})
        with patch.object(self.manager,'require_work_admission',side_effect=RuntimeError('inert unexpected bug')):
            with self.assertRaisesRegex(RuntimeError,'inert unexpected bug'):
                self.studio.prepare_for_large_job_preparation({'preset_id':'demo'})
        self.assertEqual(self.path.read_bytes(),raw);self.assertEqual(self.studio.jobs,{})
        self.assertTrue(self.studio.queue.empty());self.assertEqual(self.studio.requests,[])
        self.launch.assert_not_called()

    def test_first_run_and_normal_terminal_records_still_admit_work(self):
        for status in (None,'completed','failed','interrupted'):
            with self.subTest(status=status):
                if status:self.record(operation={'status':status,'target':'primary'})
                created=self.studio.create_job({'preset_id':'demo'},enqueue=False)
                self.assertEqual(self.studio.jobs[created['id']]['comfy_url'],'http://127.0.0.1:8188')
                self.assertEqual(self.studio.preview({'preset_id':'demo'})['submitted'],False)
        self.assertEqual(self.studio.requests,[]);self.launch.assert_not_called()

    def test_saved_selection_mismatch_keeps_explicit_reselection_available(self):
        self.record(active='hidream',operation={'status':'completed','target':'hidream'})
        with self.assertRaisesRegex(ValueError,'Switch explicitly'):
            self.studio.create_job({'preset_id':'demo'})
        with patch.object(self.manager,'available',return_value=True),patch.object(self.manager,'_idle',return_value=None), \
             patch.object(self.manager,'_check_startup_processes',return_value={}),patch.object(self.manager,'_stopped_results',return_value=None), \
             patch.object(self.manager,'request',return_value={'system':{'ready':True},'devices':[]}):
            self.manager.switch('primary')
        self.assertTrue(self.manager.busy);self.assertEqual(self.manager.operation['target'],'primary')
        self.assertEqual(self.studio.jobs,{});self.launch.assert_not_called()

    def test_production_start_checks_the_shared_hold_before_reserving_or_queueing(self):
        intent={'name':'Admission fixture','recipe':{'preset_id':'demo'},'axis':'seed','values':[1,2],'max_generations':2}
        with patch.object(self.studio,'production_preflight',return_value={'comfy_url':self.studio.comfy_url}), \
             patch.object(self.studio,'validate_graph',return_value=None):
            project=self.studio.production.create(intent)
        before=self.studio.production.get(project['id']);self.legacy()
        with self.assertRaisesRegex(ValueError,'shared|legacy'):self.studio.production.start(project['id'])
        after=self.studio.production.get(project['id'])
        self.assertEqual(after['state'],before['state']);self.assertEqual(after['budget'],before['budget'])
        self.assertTrue(self.studio.queue.empty());self.assertEqual(self.studio.jobs,{})
        self.assertEqual(self.studio.requests,[]);self.launch.assert_not_called()

    def test_queued_generation_refuses_a_new_shared_blocker_without_submission_or_local_hold(self):
        created=self.studio.create_job({'preset_id':'demo'},enqueue=False);job=self.studio.jobs[created['id']]
        self.legacy()
        with patch.object(self.studio,'_request',return_value={'queue_running':[],'queue_pending':[]}) as request:
            self.studio._run(job)
        self.assertEqual(job['status'],'failed');self.assertNotIn('pending_submission',job)
        self.assertEqual(job['prompt_ids'],[]);self.assertFalse(self.manager._local_work())
        request.assert_not_called();self.launch.assert_not_called()

    def test_shared_blocker_arriving_before_the_intent_never_sends_a_prompt(self):
        created=self.studio.create_job({'preset_id':'demo'},enqueue=False);job=self.studio.jobs[created['id']]
        with patch.object(self.studio,'_request',return_value={'queue_running':[],'queue_pending':[]}) as request, \
             patch.object(self.studio,'_evict_before_submit',side_effect=lambda *_:self.legacy()):
            self.studio._run(job)
        self.assertEqual(job['status'],'failed');self.assertNotIn('pending_submission',job)
        self.assertEqual(job['prompt_ids'],[]);self.assertFalse(self.manager._local_work())
        self.assertEqual([call.args[0] for call in request.call_args_list],['/queue'])
        self.launch.assert_not_called()

    def test_known_prompt_observation_remains_available_during_a_shared_hold(self):
        created=self.studio.create_job({'preset_id':'demo'},enqueue=False);job=self.studio.jobs[created['id']]
        job.update(status='uncertain',prompt_ids=['known'],submissions=[{'index':0,'prompt_id':'known','status':'observing','graph':job['graph'],'seed':1}])
        self.legacy()
        status,result=self.post('/api/jobs/'+job['id']+'/resume')
        self.assertEqual(status,202,result);self.assertEqual(self.studio.queue.get_nowait(),('observe',job['id']))
        self.assertEqual(job['prompt_ids'],['known']);self.assertEqual(self.studio.requests,[]);self.launch.assert_not_called()

    def test_later_batch_refusal_keeps_the_first_receipt_and_output_as_partial(self):
        created=self.studio.create_job({'preset_id':'demo','batch_count':2},enqueue=False);job=self.studio.jobs[created['id']]
        output={'filename':'kept.png','prompt_id':'known'}
        def completed(job,submission):
            submission['status']='completed';job['outputs'].append(output);self.legacy();return True
        with patch.object(self.studio,'_request',side_effect=[{'queue_running':[],'queue_pending':[]},{'prompt_id':'known'}]) as request, \
             patch.object(self.studio,'_wait_history',side_effect=completed):self.studio._run(job)
        self.assertEqual(job['status'],'partial');self.assertEqual(job['prompt_ids'],['known'])
        self.assertEqual(job['submissions'][0]['status'],'completed');self.assertEqual(job['outputs'],[output])
        self.assertNotIn('pending_submission',job);self.assertIn('output 2',job['message'])
        self.assertFalse(self.manager._local_work());self.assertEqual([call.args[0] for call in request.call_args_list],['/queue','/prompt'])
        self.launch.assert_not_called()


if __name__=='__main__':unittest.main()
