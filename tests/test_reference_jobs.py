"""Durable analysis uses the actual Studio worker and Workspace, with inert sensors."""
import base64
import copy
import hashlib
import io
import json
import threading
import unittest
from unittest.mock import patch
from PIL import Image
import test_server as fixtures
from studio_prompt import reference_analysis as analysis
from studio_prompt.schema import digest

GIB = 1024**3
MODEL = 'local-vlm:4b'
CONFIG = {'model': MODEL, 'model_digest': 'd'*64, 'port':11434,
          'min_available_ram_bytes':4*GIB, 'min_commit_headroom_bytes':8*GIB,
          'min_free_vram_bytes':4*GIB, 'timeout_seconds':60}


class ReferenceJobTests(unittest.TestCase):
    # Inherit only fixture setup, not the entire server test suite.
    def setUp(self):
        fixtures.ServerTests.setUp(self)
        self.studio_instance = fixtures.server.Studio(self.root)
        self.studio_instance.config['reference_helper'] = copy.deepcopy(CONFIG)
        self.assertTrue(hasattr(self.studio_instance, 'reference_jobs'), 'Studio must own durable reference analysis')
        self.service = self.studio_instance.reference_jobs
        with self.studio_instance.assets.connection() as db:
            self.scope = self.studio_instance.assets._workspace_id(db)
        self.refs=[];self.images=[];observations=[]
        for n, role in enumerate(('identity','pose')):
            buf=io.BytesIO();Image.new('RGB',(16+n,32),(n+1,4,9)).save(buf,format='PNG');raw=buf.getvalue()
            key='picture-'+str(n+1)
            self.refs.append({'id':key,'path':key+'.png','sha256':hashlib.sha256(raw).hexdigest(),'role_hint':'auto'})
            self.images.append({'reference_id':key,'media_base64':base64.b64encode(raw).decode()})
            observations.append({'reference_id':key,'suggested_role':role,'description':'A figure', 'tags':[],
                'facets':{'subject':'silver-haired traveller'} if n==0 else {'action':'leaning over a desk'},
                'uncertain_facets':[],'unknowns':[]})
        self.payload={'workspace_id':self.scope,'request_id':'analysis-request-0001',
                      'request':analysis.new_request('use that pose',self.refs),'images':self.images}
        self.answer={'done':True,'message':{'content':json.dumps({'summary':'Traveller leaning over a desk',
            'assumptions':[],'questions':[],'images':observations})}}
        self.sensor=patch('studio_prompt.reference_jobs.resources',return_value={
            'available_ram_bytes':20*GIB,'commit_headroom_bytes':30*GIB,'free_vram_bytes':12*GIB})
        self.sensor.start();self.addCleanup(self.sensor.stop)
        self.studio_instance._request=lambda *a,**kw:{'queue_running':[],'queue_pending':[]}
        self.calls=[]
        def transport(port,method,path,payload=None,timeout=90):
            self.calls.append((method,path))
            if path=='/api/tags':return {'models':[{'name':MODEL,'digest':'d'*64}]}
            if path=='/api/ps':return {'models':[]}
            if path=='/api/chat':return copy.deepcopy(self.answer)
            raise AssertionError(path)
        self.transport=transport
        self.http=patch('studio_prompt.reference_jobs.http_json',side_effect=transport)
        self.http.start();self.addCleanup(self.http.stop)

    def create(self):return self.service.create(self.payload)
    def get(self):return self.service.get(self.scope,self.payload['request_id'])
    def run_one(self):self.service.run(self.payload['request_id'])

    def test_create_and_reads_do_not_infer_or_generate(self):
        value=self.create();self.assertEqual(value['state']['status'],'queued')
        self.assertFalse(value['generation_submitted']);self.assertEqual(self.calls,[])
        self.assertEqual(self.studio_instance.queue.get_nowait(),('reference-analysis',self.payload['request_id']))
        self.assertEqual(self.get()['request'],self.payload['request']);self.assertEqual(self.calls,[])

    def test_replay_same_identity_does_not_queue_twice(self):
        self.create();self.create();self.assertEqual(self.studio_instance.queue.qsize(),1)
        changed=copy.deepcopy(self.payload);changed['request']['brief']='different'
        with self.assertRaisesRegex(ValueError,'different'):self.service.create(changed)
        self.assertEqual(self.calls,[])

    def test_missing_config_disables_before_any_request(self):
        del self.studio_instance.config['reference_helper']
        self.assertFalse(self.service.capabilities()['enabled'])
        with self.assertRaises(ValueError):self.create()
        self.assertEqual(self.calls,[]);self.assertTrue(self.studio_instance.queue.empty())

    def test_exact_reference_hash_and_count_checked(self):
        self.payload['images'][0]['media_base64']=self.payload['images'][1]['media_base64']
        with self.assertRaisesRegex(ValueError,'changed'):self.create()
        self.assertEqual(self.calls,[]);self.assertTrue(self.studio_instance.queue.empty())

    def test_worker_one_call_and_retained_result(self):
        self.create();self.run_one();value=self.get()
        self.assertEqual(value['state']['status'],'completed');self.assertFalse(value['state']['resource_hold'])
        self.assertEqual(len(value['result']['analysis']['answer']['images']),2)
        self.assertEqual(self.calls.count(('POST','/api/chat')),1)
        self.run_one();self.assertEqual(self.calls.count(('POST','/api/chat')),1)

    def test_post_has_durable_marker_before_transport(self):
        original=self.transport
        def checked(*args,**kwargs):
            if args[2]=='/api/chat':
                saved=self.get();self.assertTrue(saved['state']['resource_hold'])
                self.assertEqual(saved['state']['status'],'submitting')
                self.assertEqual(saved['state']['inference_attempts'],1)
            return original(*args,**kwargs)
        with patch('studio_prompt.reference_jobs.http_json',side_effect=checked):self.create();self.run_one()

    def test_missing_model_never_pulled(self):
        self.create()
        with patch('studio_prompt.reference_jobs.http_json',return_value={'models':[]}):self.run_one()
        self.assertEqual(self.get()['state']['status'],'failed');self.assertFalse(self.get()['state']['resource_hold'])
        self.assertEqual(self.get()['state']['inference_attempts'],0)

    def test_changed_configuration_after_queue_wait_refuses(self):
        self.create();self.studio_instance.config['reference_helper']['model_digest']='f'*64;self.run_one()
        self.assertEqual(self.get()['state']['status'],'failed');self.assertEqual(self.calls,[])

    def test_admission_refuses_unknown_and_low_headroom(self):
        for amount in (None, 0):
            with self.subTest(amount=amount):
                self.payload['request_id']='pressure-'+str(amount)+'-00000000'
                self.create()
                with patch('studio_prompt.reference_jobs.resources',return_value={
                    'available_ram_bytes':amount,'commit_headroom_bytes':30*GIB,'free_vram_bytes':12*GIB}):self.run_one()
                self.assertEqual(self.get()['state']['status'],'failed');self.assertEqual(self.get()['state']['inference_attempts'],0)
        self.assertNotIn(('POST','/api/chat'),self.calls)

    def test_external_queue_work_refuses_before_model(self):
        self.create();self.studio_instance._request=lambda *a,**kw:{'queue_running':[{}],'queue_pending':[]}
        self.run_one();self.assertEqual(self.get()['state']['status'],'failed');self.assertNotIn(('POST','/api/chat'),self.calls)

    def test_loss_is_uncertain_and_blocks_future_work(self):
        self.create()
        original=self.transport
        def loss(*args,**kwargs):
            if args[2]=='/api/chat':raise OSError('reply lost')
            return original(*args,**kwargs)
        with patch('studio_prompt.reference_jobs.http_json',side_effect=loss):self.run_one()
        value=self.get();self.assertEqual(value['state']['status'],'uncertain');self.assertTrue(value['state']['resource_hold'])
        with self.assertRaises(ValueError):self.studio_instance.require_worker()
        with self.assertRaises(ValueError):self.studio_instance.create_job({'preset_id':'demo','controls':{}})
        self.run_one();self.assertEqual(self.get()['state']['inference_attempts'],1)
        self.assertTrue(self.studio_instance.backends._local_work())

    def test_unload_request_is_not_treated_as_observed_release(self):
        self.create();original=self.transport;seen=False
        def resident(*args,**kwargs):
            nonlocal seen
            if args[2]=='/api/chat':seen=True
            if args[2]=='/api/ps' and seen:return {'models':[{'name':MODEL}]}
            return original(*args,**kwargs)
        with patch('studio_prompt.reference_jobs.http_json',side_effect=resident):self.run_one()
        value=self.get();self.assertEqual(value['state']['status'],'completed');self.assertTrue(value['state']['resource_hold'])
        self.service.release({'workspace_id':self.scope,'request_id':self.payload['request_id'],
            'expected_state_sha256':value['state_sha256'],'acknowledge_unknown':False})
        self.assertFalse(self.get()['state']['resource_hold'])

    def test_queued_cancel_never_dispatches(self):
        self.create();value=self.get()
        self.service.cancel({'workspace_id':self.scope,'request_id':self.payload['request_id'],'expected_state_sha256':value['state_sha256']})
        self.run_one();self.assertEqual(self.get()['state']['status'],'cancelled');self.assertEqual(self.calls,[])

    def test_restart_never_requeues(self):
        self.create()
        from studio_prompt.reference_jobs import ReferenceJobs
        restarted=ReferenceJobs(self.studio_instance)
        self.assertEqual(restarted.get(self.scope,self.payload['request_id'])['state']['status'],'cancelled')
        self.assertEqual(self.studio_instance.queue.qsize(),1)  # Only the original in-memory delivery remains.

    def test_actual_worker_dispatches_the_analysis_action(self):
        self.create()
        class EndWorker(BaseException):pass
        with patch.object(self.studio_instance.queue,'get',side_effect=[('reference-analysis',self.payload['request_id']),EndWorker()]):
            with self.assertRaises(EndWorker):self.studio_instance._work()
        self.assertEqual(self.get()['state']['status'],'completed')
        self.assertEqual(self.calls.count(('POST','/api/chat')),1)

    def test_wrong_workspace_refuses_reads_and_writes(self):
        self.create()
        with self.assertRaises(ValueError):self.service.get('a'*32,self.payload['request_id'])
        self.payload['workspace_id']='a'*32
        with self.assertRaises(ValueError):self.create()
        self.assertEqual(self.calls,[])

    def tearDown(self): fixtures.ServerTests.tearDown(self)

    def test_unknown_release_needs_specific_acknowledgement_and_empty_residency(self):
        self.create(); self.answer={'done':False}; self.run_one(); saved=self.get()
        command={'workspace_id':self.scope,'request_id':self.payload['request_id'],
                 'expected_state_sha256':saved['state_sha256'],'acknowledge_unknown':False}
        with self.assertRaisesRegex(ValueError,'Confirm'):self.service.release(command)
        command['acknowledge_unknown']=True
        self.service.release(command)
        self.assertFalse(self.get()['state']['resource_hold'])
        self.assertEqual(self.get()['state']['status'],'uncertain')
        self.assertEqual(self.get()['state']['inference_attempts'],1)
        self.studio_instance.require_worker()
        self.run_one();self.assertEqual(self.calls.count(('POST','/api/chat')),1)

    def test_restart_keeps_lost_reply_hold_and_never_replays(self):
        self.create();self.answer={'done':False};self.run_one()
        from studio_prompt.reference_jobs import ReferenceJobs
        restarted=ReferenceJobs(self.studio_instance)
        self.assertTrue(restarted.busy(holds_only=True));self.assertEqual(self.get()['state']['inference_attempts'],1)
        restarted.run(self.payload['request_id']);self.assertEqual(self.calls.count(('POST','/api/chat')),1)

    def test_changed_journal_payload_is_not_dispatched(self):
        self.create()
        with self.studio_instance.assets.connection() as db:
            db.execute('UPDATE reference_jobs_v1 SET payload=?', ('{"model":"other"}',))
        self.run_one();self.assertEqual(self.get()['state']['status'],'failed');self.assertEqual(self.calls,[])

    def test_changed_journal_request_and_context_are_not_accepted(self):
        self.create()
        with self.studio_instance.assets.connection() as db:
            db.execute('UPDATE reference_jobs_v1 SET request=?', ('{"brief":"changed"}',))
        self.run_one();self.assertEqual(self.get()['state']['status'],'failed');self.assertEqual(self.calls,[])

    def test_resource_thresholds_are_read_fresh_after_inventory(self):
        self.create(); readings=[]
        def sensor(studio):readings.append(list(self.calls));return {'available_ram_bytes':20*GIB,'commit_headroom_bytes':30*GIB,'free_vram_bytes':12*GIB}
        with patch('studio_prompt.reference_jobs.resources',side_effect=sensor):self.run_one()
        self.assertIn(('GET','/api/tags'),readings[-1]);self.assertIn(('GET','/api/ps'),readings[-1])

    def test_automatic_runtime_recovery_observes_analysis_ownership(self):
        self.create();self.assertTrue(self.studio_instance.runtime_recovery._fresh_work())

    def test_only_one_active_analysis_and_capacity_is_explicit(self):
        self.create();second=copy.deepcopy(self.payload);second['request_id']='analysis-request-0002'
        with self.assertRaises(ValueError):self.service.create(second)
        self.run_one()
        with patch('studio_prompt.reference_jobs.MAX_JOBS',1):
            with self.assertRaisesRegex(ValueError,'full'):self.service.create(second)
        self.assertEqual(self.calls.count(('POST','/api/chat')),1)

    def test_stale_cancel_does_not_change_completed_work(self):
        self.create();old=self.get()['state_sha256'];self.run_one()
        with self.assertRaisesRegex(ValueError,'changed'):self.service.cancel({'workspace_id':self.scope,
            'request_id':self.payload['request_id'],'expected_state_sha256':old})
        self.assertEqual(self.get()['state']['status'],'completed')

    def test_store_failure_before_post_never_contacts_model(self):
        self.create();original=self.service._save_state
        def fail(db,key,state):
            if state['status']=='submitting':raise OSError('fixture marker write failed')
            return original(db,key,state)
        with patch.object(self.service,'_save_state',side_effect=fail):self.run_one()
        self.assertEqual(self.get()['state']['inference_attempts'],0)
        self.assertNotIn(('POST','/api/chat'),self.calls)

    def test_store_failure_after_post_cannot_release_resources(self):
        self.create();original=self.service._save_state
        def fail(db,key,state):
            if state['status']=='completed':raise OSError('fixture final write failed')
            return original(db,key,state)
        with patch.object(self.service,'_save_state',side_effect=fail):self.run_one()
        self.assertTrue(self.get()['state']['resource_hold']);self.assertEqual(self.get()['state']['inference_attempts'],1)

    def test_cancel_during_admission_cannot_cancel_a_remote_request(self):
        self.create();original=self.transport
        def cancel(*args,**kwargs):
            if args[2]=='/api/tags':
                saved=self.get()
                with self.assertRaisesRegex(ValueError,'queued'):self.service.cancel({'workspace_id':self.scope,
                    'request_id':self.payload['request_id'],'expected_state_sha256':saved['state_sha256']})
            return original(*args,**kwargs)
        with patch('studio_prompt.reference_jobs.http_json',side_effect=cancel):self.run_one()
        self.assertEqual(self.get()['state']['status'],'completed')

    def test_no_helpers_from_public_capabilities_or_status_reads(self):
        self.create()
        for _ in range(3):self.service.capabilities();self.get()
        self.assertEqual(self.calls,[])

    def test_real_loopback_worker_transport_and_clean_derivatives(self):
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        requests=[]; response=self.answer
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def send(self,value):
                body=json.dumps(value).encode();self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            def do_GET(self):self.send({'models':[{'name':MODEL,'digest':'d'*64}]} if self.path=='/api/tags' else {'models':[]})
            def do_POST(self):
                requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))));self.send(response)
        http=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=http.serve_forever)
        self.start.stop();thread.start()
        try:
            self.studio_instance.config['reference_helper']['port']=http.server_port
            from studio_prompt.local_helper import http_json
            with patch('studio_prompt.reference_jobs.http_json',side_effect=http_json):self.create();self.run_one()
            self.assertEqual(self.get()['state']['status'],'completed')
            self.assertEqual(len(requests),1);self.assertEqual(len(requests[0]['messages'][1]['images']),2)
            self.assertEqual(requests[0]['keep_alive'],0);self.assertNotIn('tools',requests[0])
            for encoded in requests[0]['messages'][1]['images']:
                with Image.open(io.BytesIO(base64.b64decode(encoded))) as image:self.assertEqual(image.mode,'RGB')
        finally:http.shutdown();thread.join();http.server_close()

    def test_resource_reader_keeps_ram_commit_and_device_counters_separate(self):
        from types import SimpleNamespace
        self.sensor.stop()
        from studio_prompt.reference_jobs import resources
        self.studio_instance._request=lambda *a,**kw:{'devices':[{'vram_free':123}]}
        with patch('psutil.virtual_memory',return_value=SimpleNamespace(available=456)),patch('host_memory.read',return_value={'available_bytes':789}):
            self.assertEqual(resources(self.studio_instance),{'available_ram_bytes':456,'commit_headroom_bytes':789,'free_vram_bytes':123})
            self.studio_instance._request=lambda *a,**kw:{'devices':[{},{}]}
            self.assertIsNone(resources(self.studio_instance)['free_vram_bytes'])

    def test_release_does_not_hold_sqlite_writer_across_helper_observation(self):
        self.create();original=self.transport
        def resident(*args,**kwargs):
            if args[2]=='/api/ps' and self.get()['state']['response_done']:
                return {'models':[{'name':MODEL}]}
            return original(*args,**kwargs)
        with patch('studio_prompt.reference_jobs.http_json',side_effect=resident):self.run_one()
        value=self.get()
        def no_writer(*args):
            with self.studio_instance.assets.connection() as db:
                db.execute('PRAGMA busy_timeout=1');db.execute('BEGIN IMMEDIATE');db.rollback()
            return True
        with patch.object(self.service,'_empty',side_effect=no_writer):
            self.service.release({'workspace_id':self.scope,'request_id':self.payload['request_id'],
                'expected_state_sha256':value['state_sha256'],'acknowledge_unknown':False})
        self.assertFalse(self.get()['state']['resource_hold'])

    def test_capabilities_expose_a_bounded_recovery_handle_without_media(self):
        self.create();summary=self.service.capabilities()['recent'][0]
        self.assertEqual(summary['request_id'],self.payload['request_id'])
        self.assertEqual(summary['status'],'queued');self.assertNotIn('payload',summary);self.assertEqual(self.calls,[])
