"""Mixed known/unknown receipt recovery using real job files and inert Comfy HTTP."""
import copy
import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import URLError
import test_production as fixtures
from test_server import FakeStudio, server, png

IDLE={'queue_running':[],'queue_pending':[]}
def completed(identifier='known'):
    return {identifier:{'status':{'status_str':'success','completed':True},
                        'outputs':{'9':{'images':[{'filename':'kept.png','subfolder':'','type':'output'}]}}}}

class MixedBatchTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ProductionTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.root=self.fixture.root
        output=self.root/'fake-comfy/output';output.mkdir();(output/'kept.png').write_bytes(png())
        self.studio=FakeStudio(self.root,[IDLE,{'prompt_id':'known'},completed(),URLError('second POST accepted; response lost')])
        self.job=self.studio.jobs[self.studio.create_job({'preset_id':'demo','controls':{},'batch_count':3},enqueue=False)['id']]
        self.studio._run(self.job)
        self.assertEqual(self.job['status'],'uncertain');self.assertEqual(self.job['pending_submission']['index'],1)
        self.assertEqual(self.fixture.post_count(self.studio),2)
    def summary(self):return self.studio.public(self.job).get('mixed_batch',{})
    def payload(self,request_id='request-0001',**extra):
        return dict(request_id=request_id,expected_revision=self.summary()['revision'],**extra)
    def unresolved(self):
        self.job['submissions'][0]['status']='observing';self.studio._save(self.job)
    def files(self):
        return {name:(self.studio.runs/self.job['id']/name).read_bytes() for name in ('state.json','recipe.json','workflow.json')}
    def no_posts_since(self,count):self.assertEqual(self.fixture.post_count(self.studio),count)
    def test_projection_separates_known_unknown_and_unsent_without_mutation(self):
        before=copy.deepcopy(self.job);files=self.files();requests=list(self.studio.requests)
        summary=self.summary()
        self.assertTrue(summary.get('can_observe'), 'Mixed batch has no safe known-part observation control')
        self.assertTrue(summary['can_dispose'])
        self.assertEqual(summary['known'],[{'index':0,'prompt_id':'known','status':'completed'}])
        self.assertEqual(summary['unknown_index'],1);self.assertEqual(summary['never_submitted_count'],1)
        self.assertNotIn('graph',json.dumps(summary));self.assertEqual(self.job,before);self.assertEqual(self.files(),files)
        self.assertEqual(self.studio.requests,requests)
    def test_existing_resume_and_abandon_guards_stay_closed(self):
        with self.assertRaisesRegex(server.StudioError,'unknown'):self.studio.resume_job(self.job['id'])
        with self.assertRaises(server.StudioError):self.studio.abandon_job(self.job['id'],'Preserve',True)
        with self.assertRaises(server.StudioError):self.studio._run(self.job)
        self.assertTrue(self.studio.queue.empty());self.no_posts_since(2)
    def test_restart_keeps_mixed_controls_without_replaying_submission(self):
        self.studio=FakeStudio(self.root,[]);self.job=self.studio.jobs[self.job['id']]
        self.assertEqual(self.job['status'],'uncertain')
        self.assertTrue(self.summary().get('can_dispose'), 'Restarted mixed batch still has no explicit local disposition')
        self.assertTrue(self.studio.queue.empty());self.assertEqual(self.studio.requests,[])
    def command(self,action,payload):return server.mixed_batch.command(self.studio,self.job['id'],action,payload)
    def consume(self):
        action,item=self.studio.queue.get_nowait();self.assertEqual(action,'observe-mixed')
        server.mixed_batch.run(self.studio,*item)
    def test_observation_is_explicit_bounded_and_does_not_reobserve_completed_receipts(self):
        originals=self.files();pending=copy.deepcopy(self.job['pending_submission']);requests=list(self.studio.requests)
        payload=self.payload();result=self.command('observe',payload)
        self.assertEqual(result['status'],'queued');self.assertEqual(self.studio.requests,requests)
        self.command('observe',payload);self.assertEqual(self.studio.queue.qsize(),1)
        self.consume();self.assertEqual(self.job['status'],'uncertain')
        self.command('observe',payload);self.assertTrue(self.studio.queue.empty())
        self.assertEqual(self.studio.requests,requests);self.assertEqual(self.job['pending_submission'],pending)
        for name in ('recipe.json','workflow.json'):self.assertEqual(self.files()[name],originals[name])
    def test_unresolved_known_receipt_gets_one_encoded_history_read_and_preserves_outputs(self):
        self.unresolved();identifier=' known /?%#☃ '
        self.job['prompt_ids']=[identifier];self.job['submissions'][0]['prompt_id']=identifier
        self.job['outputs']=[];self.studio._save(self.job);self.studio.replies=iter([completed(identifier)])
        payload=self.payload();self.command('observe',payload);self.consume()
        self.assertEqual(self.studio.requests[-1][0][0],'/history/%20known%20%2F%3F%25%23%E2%98%83%20')
        self.assertEqual(self.job['submissions'][0]['status'],'completed');self.assertEqual(self.job['status'],'uncertain')
        self.assertEqual(self.job['outputs'][0]['prompt_id'],identifier);self.no_posts_since(2)
        self.command('observe',self.payload('request-0002'));self.consume()
        self.assertEqual(len(self.job['outputs']),1);self.no_posts_since(2)
    def test_disposition_requires_exact_current_evidence_and_literal_acknowledgement(self):
        payload=self.payload(reason='Keep the unknown tail',acknowledge_unknown=True)
        before=copy.deepcopy(self.job);files=self.files()
        for ack in (False,1,'true',None):
            with self.subTest(ack=ack),self.assertRaises(ValueError):self.command('dispose',dict(payload,acknowledge_unknown=ack))
        for revision in ('0'*64,None,123):
            with self.assertRaises(ValueError):self.command('dispose',dict(payload,expected_revision=revision))
        self.assertEqual(self.job,before);self.assertEqual(self.files(),files)
        result=self.command('dispose',payload)
        self.assertEqual(result['status'],'abandoned');self.assertEqual(result['abandonment']['basis'],'mixed_batch_unknown')
        self.assertFalse(result['abandonment']['remote_cancelled']);self.assertFalse(result['abandonment']['new_work_authorized'])
        self.assertEqual(self.job['pending_submission'],before['pending_submission']);self.assertEqual(self.job['outputs'],before['outputs'])
        self.assertEqual(result,self.command('dispose',payload));self.assertTrue(self.studio.queue.empty());self.no_posts_since(2)
    def test_queued_observation_blocks_disposition_and_new_requests(self):
        self.unresolved();payload=self.payload();self.command('observe',payload)
        with self.assertRaises(ValueError):self.command('dispose',self.payload('dispose-0001',reason='Keep',acknowledge_unknown=True))
        with self.assertRaises(ValueError):self.command('observe',self.payload('request-0002'))
        self.assertEqual(self.studio.queue.qsize(),1);self.no_posts_since(2)
    def test_failed_command_persistence_does_not_change_memory_files_or_queue(self):
        for action in ('observe','dispose'):
            payload=self.payload(**({'reason':'Keep','acknowledge_unknown':True} if action=='dispose' else {}))
            before=copy.deepcopy(self.job);files=self.files()
            with patch.object(self.studio,'_write_json_atomic',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):self.command(action,payload)
            self.assertEqual(self.job,before);self.assertEqual(self.files(),files);self.assertTrue(self.studio.queue.empty())
    def test_history_failure_stays_unknown_and_does_not_drop_retained_evidence(self):
        self.unresolved();pending=copy.deepcopy(self.job['pending_submission']);outputs=copy.deepcopy(self.job['outputs'])
        replies=[URLError('offline'),{},[],{'known':{}},{'known':{'status':{'status_str':'success'},'outputs':{}}}]
        for i,reply in enumerate(replies):
            self.studio.replies=iter([reply]);self.command('observe',self.payload('request-'+str(i).zfill(4)));self.consume()
            self.assertEqual(self.job['status'],'uncertain');self.assertEqual(self.job['submissions'][0]['status'],'observing')
            self.assertEqual(self.job['pending_submission'],pending);self.assertEqual(self.job['outputs'],outputs)
        self.no_posts_since(2);self.assertEqual(len(self.studio.requests),4+len(replies))
    def test_input_history_descriptor_is_not_terminal_and_can_be_reobserved(self):
        self.unresolved();originals=self.files();outputs=copy.deepcopy(self.job['outputs'])
        pending=copy.deepcopy(self.job['pending_submission'])
        response=completed();response['known']['outputs']['9']['images'].append(
            {'filename':'reference.png','subfolder':'','type':'input'})
        self.studio.replies=iter([response]);self.command('observe',self.payload());self.consume()
        self.assertEqual(self.job['submissions'][0]['status'],'observing')
        self.assertEqual(self.job['status'],'uncertain');self.assertEqual(self.job['outputs'],outputs)
        self.assertIn('Invalid output location',self.job['mixed_batch_recovery']['history'][-1]['observations'][0]['message'])
        self.assertEqual(self.job['pending_submission'],pending)
        for name in ('recipe.json','workflow.json'):self.assertEqual(self.files()[name],originals[name])
        self.studio=FakeStudio(self.root,[completed()]);self.job=self.studio.jobs[self.job['id']]
        self.command('observe',self.payload('request-0002'));self.consume()
        self.assertEqual(self.job['submissions'][0]['status'],'completed')
        self.assertEqual(self.job['status'],'uncertain');self.assertEqual(len(self.job['outputs']),len(outputs))
        self.assertEqual(self.fixture.post_count(self.studio),0);self.assertEqual(len(self.studio.requests),1)
        self.assertTrue(self.studio.queue.empty())
    def test_supported_temp_history_output_can_be_materialized(self):
        self.unresolved();directory=self.root/'fake-comfy/temp';directory.mkdir()
        raw=png();(directory/'preview.png').write_bytes(raw)
        response=completed();response['known']['outputs']['9']['images']=[
            {'filename':'preview.png','subfolder':'','type':'temp'}]
        self.studio.replies=iter([response]);self.command('observe',self.payload());self.consume()
        output=self.job['outputs'][-1]
        self.assertEqual(self.job['submissions'][0]['status'],'completed')
        self.assertEqual(output['type'],'temp');self.assertNotIn('snapshot_error',output)
        self.assertEqual(self.studio.output_path(output,self.job).read_bytes(),raw)
        self.assertEqual(self.studio.assets.file(output['asset_id']).read_bytes(),raw);self.no_posts_since(2)
    def test_known_failure_never_certifies_unknown_tail(self):
        self.unresolved();self.studio.replies=iter([{'known':{'status':{'status_str':'error','completed':False,
            'messages':[['execution_error',{'node_type':'Sampler','exception_message':'test failure'}]]},'outputs':{}}}])
        self.command('observe',self.payload());self.consume()
        self.assertEqual(self.job['submissions'][0]['status'],'failed');self.assertEqual(self.job['status'],'uncertain')
        self.assertFalse(server.submission_evidence.terminal_failure(self.job));self.no_posts_since(2)
    def test_restart_preserves_command_identity_and_never_requeues_old_reads(self):
        payload=self.payload();self.command('observe',payload)
        self.studio=FakeStudio(self.root,[]);self.job=self.studio.jobs[self.job['id']]
        self.command('observe',payload);self.assertTrue(self.studio.queue.empty());self.assertEqual(self.studio.requests,[])
        self.command('observe',self.payload('request-0002'));self.consume();self.assertEqual(self.job['status'],'uncertain')
        disposition=self.payload('dispose-0001',reason='Retain mixed evidence',acknowledge_unknown=True)
        self.command('dispose',disposition);before=copy.deepcopy(self.job)
        self.studio=FakeStudio(self.root,[]);self.job=self.studio.jobs[self.job['id']]
        self.command('dispose',disposition);self.assertEqual(self.job,before);self.assertTrue(self.studio.queue.empty())
    def test_restart_preserves_exact_mixed_source_bytes_before_and_after_queueing(self):
        for queued in (False,True):
            with self.subTest(queued=queued):
                payload=self.payload()
                if queued:self.command('observe',payload)
                directory=self.studio.runs/self.job['id']
                for name in ('recipe.json','workflow.json'):
                    value=json.loads((directory/name).read_bytes())
                    (directory/name).write_text(json.dumps(value,sort_keys=True,indent=4)+'\n',encoding='utf-8')
                originals=self.files();pending=copy.deepcopy(self.job['pending_submission'])
                for restart in range(2):
                    self.studio=FakeStudio(self.root,[]);self.job=self.studio.jobs[self.job['id']]
                    self.assertEqual(self.job['status'],'uncertain')
                    self.assertEqual(self.job['pending_submission'],pending)
                    for name in ('recipe.json','workflow.json'):self.assertEqual(self.files()[name],originals[name])
                    if queued:self.command('observe',payload)
                    self.assertTrue(self.studio.queue.empty());self.assertEqual(self.studio.requests,[])
    def test_stale_or_changed_command_identity_cannot_be_reused(self):
        payload=self.payload();self.command('observe',payload);self.consume()
        with self.assertRaises(ValueError):self.command('dispose',dict(payload,reason='Changed action',acknowledge_unknown=True))
        with self.assertRaises(ValueError):self.command('observe',dict(payload,expected_revision='f'*64))
        with self.assertRaises(ValueError):self.command('observe',dict(payload,request_id='request-0002'))
        self.assertTrue(self.studio.queue.empty());self.no_posts_since(2)
    def test_malformed_mixed_shapes_never_gain_recovery_authority(self):
        original=copy.deepcopy(self.job)
        mutations=[{'pending_submission':{}},{'pending_submission':None},{'batch_count':True},
                   {'prompt_ids':['known','known']},{'submissions':[]},{'outputs':None}]
        for changes in mutations:
            self.job.clear();self.job.update(copy.deepcopy(original));self.job.update(changes)
            summary=self.summary();self.assertFalse(summary.get('can_observe'));self.assertFalse(summary.get('can_dispose'))
            with self.assertRaises(ValueError):self.command('observe',{'request_id':'request-0001','expected_revision':'0'*64})
        self.assertTrue(self.studio.queue.empty());self.no_posts_since(2)
    def owning_project(self):
        lab=self.studio.production;project=lab.create(self.fixture.intent());identifier=project['id'];lab.start(identifier)
        self.studio.queue.get_nowait()
        self.job['project_id']=identifier;self.studio._save(self.job)
        lab._mutate(identifier,status='uncertain',attempts={'0':{'job_id':self.job['id'],'status':'uncertain'}})
        return identifier
    def test_project_disposition_reconciles_without_worker_clock_or_new_stage(self):
        identifier=self.owning_project();lab=self.studio.production;before=lab.get(identifier)
        self.command('dispose',self.payload('dispose-0001',reason='Retain evidence',acknowledge_unknown=True));files=self.files()
        self.assertTrue(lab.get(identifier).get('can_reconcile_batch'))
        with patch.object(self.studio,'require_worker',side_effect=AssertionError('No worker needed')), \
             patch.object(lab,'_comparison_clock',side_effect=AssertionError('No clock charge')), \
             patch.object(self.studio,'check_production_bundle',side_effect=AssertionError('No generation preflight')):
            first=lab.resume(identifier);second=lab.resume(identifier);lab.run(identifier)
        self.assertEqual(first,second);self.assertEqual(first['state']['status'],'failed')
        self.assertEqual(first['state']['attempts']['0']['status'],'abandoned')
        self.assertFalse(first['state']['batch_terminal_reconciliation']['new_work_authorized'])
        self.assertEqual(first['state'].get('time_budget'),before['state'].get('time_budget'))
        self.assertEqual(first['budget'],before['budget']);self.assertEqual(self.files(),files)
        self.assertTrue(self.studio.queue.empty());self.assertEqual(len(self.studio.jobs),1);self.no_posts_since(2)
        restarted=FakeStudio(self.root,[])
        self.assertEqual(restarted.production.get(identifier)['state'],first['state']);self.assertEqual(restarted.requests,[])
    def test_unresolved_mixed_project_is_held_before_clock_or_preflight(self):
        identifier=self.owning_project();lab=self.studio.production;before=lab.get(identifier)
        with patch.object(lab,'_comparison_clock',side_effect=AssertionError('No clock charge')):
            with self.assertRaisesRegex(ValueError,'mixed batch'):lab.resume(identifier)
            lab.run(identifier)
        after=lab.get(identifier)
        self.assertEqual(after['state']['status'],'uncertain');self.assertEqual(after['budget'],before['budget'])
        self.assertTrue(self.studio.queue.empty());self.no_posts_since(2)
    def test_concurrent_duplicate_commands_write_once_and_preserve_workspace(self):
        self.fixture.patches[0].stop()
        asset=self.job['outputs'][0]['asset_id'];workspace=self.studio.assets.get(asset)
        raw=self.studio.assets.file(asset).read_bytes();pending=copy.deepcopy(self.job['pending_submission'])
        payload=self.payload('dispose-0001',reason='Preserve mixed batch',acknowledge_unknown=True)
        barrier=threading.Barrier(4);results=[];errors=[]
        def request():
            try:barrier.wait(timeout=3);results.append(self.command('dispose',payload))
            except BaseException as exc:errors.append(exc)
        threads=[threading.Thread(target=request) for _ in range(3)]
        for thread in threads:thread.start()
        barrier.wait(timeout=3)
        for thread in threads:thread.join(5);self.assertFalse(thread.is_alive())
        self.assertEqual(errors,[]);self.assertEqual(len(results),3)
        self.assertEqual(len(self.job['mixed_batch_recovery']['history']),1)
        self.assertEqual(self.studio.assets.get(asset),workspace);self.assertEqual(self.studio.assets.file(asset).read_bytes(),raw)
        self.assertEqual(self.job['pending_submission'],pending);self.assertTrue(self.studio.queue.empty())
    def test_dead_worker_refuses_observation_but_not_local_disposition(self):
        before=copy.deepcopy(self.job)
        with patch.object(self.studio,'require_worker_observation',side_effect=ValueError('worker unavailable')):
            with self.assertRaisesRegex(ValueError,'worker'):self.command('observe',self.payload())
            self.assertEqual(self.job,before)
            self.command('dispose',self.payload(reason='No more observation',acknowledge_unknown=True))
        self.assertEqual(self.job['status'],'abandoned');self.assertTrue(self.studio.queue.empty())
    def test_local_disposition_does_not_relax_backend_queue_interlocks(self):
        self.command('dispose',self.payload(reason='Preserve',acknowledge_unknown=True))
        with patch.object(self.studio.backends,'available',return_value=True), \
             patch.object(self.studio.backends,'_check_retained_startup'), \
             patch.object(self.studio.backends,'_check_startup_processes'), \
             patch.object(self.studio.backends,'request',return_value={'queue_running':[['foreign']],'queue_pending':[]}):
            with self.assertRaisesRegex(ValueError,'queue was preserved'):self.studio.backends.switch('hidream')
        self.assertFalse(self.studio.backends.busy)
    def test_stale_queued_command_cannot_observe_changed_submission_evidence(self):
        self.unresolved();self.command('observe',self.payload());self.job['pending_submission']['seed']=9876
        before=len(self.studio.requests)
        with self.assertRaisesRegex(ValueError,'changed'):self.consume()
        self.assertEqual(len(self.studio.requests),before);self.no_posts_since(2)
    def test_late_history_cannot_overwrite_changed_known_graph(self):
        self.unresolved();self.command('observe',self.payload());before=copy.deepcopy(self.job['outputs'])
        def change(*args,**kwargs):
            self.job['submissions'][0]['graph']['new']={'inputs':{'text':'changed while reading'}}
            return completed()
        with patch.object(self.studio,'_request',side_effect=change):
            with self.assertRaisesRegex(ValueError,'changed'):self.consume()
        self.assertEqual(self.job['outputs'],before);self.assertEqual(self.job['submissions'][0]['status'],'observing')
    def test_real_worker_dispatches_read_only_and_stale_queue_item_is_inert(self):
        self.unresolved();self.studio.replies=iter([completed()]);payload=self.payload();self.command('observe',payload)
        item=self.studio.queue.get_nowait();items=iter([item,item])
        def get(timeout=None):
            try:return next(items)
            except StopIteration:raise SystemExit('test consumer finished')
        with patch.object(self.studio.queue,'get',side_effect=get):
            with self.assertRaises(SystemExit):self.studio._work()
        self.assertEqual(self.job['status'],'uncertain');self.no_posts_since(2)
        self.assertEqual(len(self.studio.requests),5)
    def test_bad_history_output_is_not_partial_mutation_or_success(self):
        self.unresolved();before=copy.deepcopy(self.job['outputs'])
        response=completed();response['known']['outputs']['9']['images'].append({'filename':123,'type':'output'})
        self.studio.replies=iter([response]);self.command('observe',self.payload());self.consume()
        self.assertEqual(self.job['status'],'uncertain');self.assertEqual(self.job['submissions'][0]['status'],'observing')
        self.assertEqual(self.job['outputs'],before)
    def test_output_indexing_failure_keeps_uncertainty_and_retry_is_read_only(self):
        payload=self.payload();self.command('observe',payload)
        with patch.object(self.studio,'index_outputs',side_effect=OSError('locked output snapshot')):
            with self.assertRaises(OSError):self.consume()
        self.studio=FakeStudio(self.root,[]);self.job=self.studio.jobs[self.job['id']]
        self.command('observe',self.payload('request-0002'));self.consume()
        self.assertEqual(self.job['status'],'uncertain');self.assertEqual(self.studio.requests,[])
    def test_changed_disposed_graph_cannot_reconcile_owning_project(self):
        identifier=self.owning_project()
        self.command('dispose',self.payload(reason='Preserve',acknowledge_unknown=True))
        self.job['submissions'][0]['graph']['changed']={'inputs':{}}
        self.assertFalse(server.mixed_batch.disposed(self.job))
        self.assertFalse(self.studio.production.get(identifier)['can_reconcile_batch'])
        with self.assertRaisesRegex(ValueError,'mixed batch'):self.studio.production.resume(identifier)
    def test_project_requires_disposition_for_every_mixed_stage(self):
        identifier=self.owning_project();lab=self.studio.production
        other=copy.deepcopy(self.job);other['id']='d'*32;self.studio.jobs[other['id']]=other
        other['graph']=copy.deepcopy(lab._get(identifier)['plan']['stages'][1]['graph'])
        lab._mutate(identifier,attempts={'0':{'job_id':self.job['id'],'status':'uncertain'},
                                        '1':{'job_id':other['id'],'status':'uncertain'}})
        self.command('dispose',self.payload(reason='Preserve first',acknowledge_unknown=True))
        self.assertFalse(lab.get(identifier)['can_reconcile_batch'])
        with self.assertRaisesRegex(ValueError,'mixed batch'):lab.resume(identifier)
    def test_malformed_recovery_history_refuses_even_exact_revision_command(self):
        self.job['mixed_batch_recovery']={'version':1,'history':[{'request_id':'bad-00001'}]}
        revision=server.mixed_batch._hash(self.job)
        self.assertFalse(self.summary().get('can_dispose'))
        with self.assertRaisesRegex(ValueError,'history'):
            self.command('dispose',dict(request_id='dispose-0001',expected_revision=revision,reason='Preserve',acknowledge_unknown=True))
    def test_malformed_mixed_dispatch_cannot_end_shared_worker(self):
        self.command('observe',self.payload());good=self.studio.queue.get_nowait()
        items=iter([('observe-mixed',(self.job['id'],)),good])
        def get(timeout=None):
            try:return next(items)
            except StopIteration:raise SystemExit('test consumer finished')
        with patch.object(self.studio.queue,'get',side_effect=get):
            with self.assertRaises(SystemExit):self.studio._work()
        self.assertEqual(self.job['status'],'uncertain');self.no_posts_since(2)
    def test_observation_limit_keeps_local_exit_and_does_not_refund_or_drop_history(self):
        for i in range(server.mixed_batch.MAX_OBSERVATIONS):
            self.command('observe',self.payload('request-'+str(i).zfill(4)));self.consume()
        summary=self.summary();self.assertFalse(summary['can_observe']);self.assertTrue(summary['can_dispose'])
        with self.assertRaisesRegex(ValueError,'limit'):self.command('observe',self.payload('request-9999'))
        self.command('dispose',self.payload('dispose-0001',reason='Keep all receipts',acknowledge_unknown=True))
        self.assertEqual(len(self.job['mixed_batch_recovery']['history']),server.mixed_batch.MAX_OBSERVATIONS+1)
        self.assertTrue(server.mixed_batch.disposed(self.job));self.assertTrue(self.studio.queue.empty());self.no_posts_since(2)
    def test_recovery_does_not_accept_batches_larger_than_create_supports(self):
        self.job['batch_count']=5
        self.assertFalse(self.summary().get('can_observe'))
        self.assertFalse(self.summary().get('can_dispose'))
    def test_contradictory_terminal_history_remains_unknown(self):
        self.unresolved();self.studio.replies=iter([{'known':{'status':{'status_str':'error','completed':True,
            'messages':[['execution_error',{'exception_message':'contradictory fixture'}]]},'outputs':{}}}])
        self.command('observe',self.payload());self.consume()
        self.assertEqual(self.job['submissions'][0]['status'],'observing');self.assertEqual(self.job['status'],'uncertain')
    def test_worker_failure_preserves_original_recipe_and_workflow_bytes(self):
        directory=self.studio.runs/self.job['id']
        for name in ('recipe.json','workflow.json'):
            path=directory/name;path.write_text(json.dumps(json.loads(path.read_text()),separators=(',',':'))+'\n',encoding='utf-8')
        before=self.files();self.command('observe',self.payload())
        items=iter([self.studio.queue.get_nowait()])
        def get(timeout=None):
            try:return next(items)
            except StopIteration:raise SystemExit('test consumer finished')
        with patch.object(self.studio.queue,'get',side_effect=get), \
             patch.object(self.studio,'index_outputs',side_effect=OSError('snapshot locked')):
            with self.assertRaises(SystemExit):self.studio._work()
        self.assertEqual(self.job['status'],'uncertain');self.no_posts_since(2)
        for name in ('recipe.json','workflow.json'):self.assertEqual(self.files()[name],before[name])
    def test_restart_preserves_source_extensions_for_queued_running_and_uncertain_reads(self):
        self.unresolved();payload=self.payload();self.command('observe',payload)
        directory=self.studio.runs/self.job['id'];accepted=copy.deepcopy(self.job)
        originals={}
        for name in ('recipe.json','workflow.json'):
            value=json.loads((directory/name).read_text())
            if name=='recipe.json':value['retained_extension']={'source_note':'Do not normalize or drop me'}
            originals[name]=(json.dumps(value,separators=(',',':'))+'\n').encode()
        for phase in ('queued','running','uncertain'):
            with self.subTest(phase=phase):
                state=copy.deepcopy(accepted);state['status']=phase
                state['mixed_batch_recovery']['history'][-1]['status']='queued' if phase=='queued' else 'running'
                self.studio._write_json_atomic(directory/'state.json',{k:v for k,v in state.items() if k!='graph'})
                for name,content in originals.items():(directory/name).write_bytes(content)
                restarted=FakeStudio(self.root,[]);recovered=restarted.jobs[self.job['id']]
                self.assertEqual(recovered['status'],'uncertain')
                self.assertEqual(recovered['pending_submission'],accepted['pending_submission'])
                self.assertEqual(recovered['prompt_ids'],accepted['prompt_ids'])
                self.assertEqual(recovered['mixed_batch_recovery'],state['mixed_batch_recovery'])
                for name,content in originals.items():self.assertEqual((directory/name).read_bytes(),content)
                # Repeating the acknowledged identity retrieves, but never requeues, the old read.
                server.mixed_batch.command(restarted,self.job['id'],'observe',payload)
                self.assertTrue(restarted.queue.empty());self.assertEqual(restarted.requests,[])
    def test_restart_state_write_failure_preserves_source_files_and_pending_intent(self):
        self.command('observe',self.payload());directory=self.studio.runs/self.job['id'];before=self.files()
        with patch.object(FakeStudio,'_write_json_atomic',side_effect=OSError('state file locked on restart')):
            with self.assertRaisesRegex(OSError,'state file locked'):FakeStudio(self.root,[])
        self.assertEqual(self.files(),before);self.no_posts_since(2)
