"""Retained negative outcomes close Production without granting continuation (#110)."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch
from urllib.error import URLError

import test_production as fixtures
from test_server import FakeStudio, server


class TerminalObservationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ProductionTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.studio=FakeStudio(self.fixture.root,[{'queue_running':[],'queue_pending':[]},{'prompt_id':'retained'},URLError('history lost')])
        self.lab=self.studio.production;self.project=self.lab.create(self.fixture.intent())
        self.identifier=self.project['id'];self.lab.start(self.identifier);self.lab.run(self.identifier)
        self.job=self.studio.jobs[self.lab.get(self.identifier)['state']['attempts']['0']['job_id']]
        self.studio.stop_tracking(self.job['id'],'Inspect this attempt before continuing')
    def terminal(self,status):
        if status=='partial':
            # Retained legacy multi-output receipt: only the known first prompt
            # was submitted. Current comparison planning is still single-output.
            self.job['batch_count']=2;self.studio._save(self.job)
        self.studio.resume_job(self.job['id'])
        self.studio.replies=iter([{'retained':{'status':{'status_str':'error' if status=='failed' else 'success'},'outputs':{}}}])
        if status=='failed':
            with self.assertRaises(server.StudioError):self.studio._resume(self.job)
        else:self.studio._resume(self.job)
        self.assertEqual(self.job['status'],status)
    def snapshot(self):
        files={name:(self.studio.runs/self.job['id']/name).read_bytes() for name in ('state.json','recipe.json','workflow.json')}
        return {'files':files,'plan':(self.lab.root/self.identifier/'plan.json').read_bytes(),
                'job':copy.deepcopy(self.job),'budget':self.lab.get(self.identifier)['budget'],
                'queued':self.studio.queue.qsize(),'posts':self.fixture.post_count(self.studio)}
    def assert_preserved(self,before):
        after=self.snapshot();self.assertEqual(after,before)
        state=self.lab.get(self.identifier)['state'];self.assertEqual(state['status'],'failed')
        self.assertEqual(state['attempts']['0']['status'],self.job['status'])
        self.assertEqual(state['attempts']['0']['prompt_ids'],['retained'])
        self.assertEqual(state.get('tracking_stop_authorizations',[]),[])
        self.assertEqual(len(self.studio.jobs),1);self.assertEqual(len(state['attempts']),1)
        self.assertIn('repair',state['message'].lower())
    def test_explicit_failed_reconciliation_does_not_enqueue_or_authorize(self):
        self.terminal('failed');before=self.snapshot();result=self.lab.resume(self.identifier)
        self.assertEqual(result['state']['status'],'failed');self.assert_preserved(before)
    def test_partial_reconciliation_preserves_known_outputs_and_unsent_tail(self):
        self.terminal('partial')
        self.job['outputs']=[{'filename':'retained.png','type':'output','subfolder':'','prompt_id':'retained'}];self.studio._save(self.job)
        before=self.snapshot();self.lab.resume(self.identifier);self.assert_preserved(before)
    def test_stale_queued_pass_reconciles_before_bundle_check_and_clock(self):
        self.terminal('failed');before=self.snapshot();state=copy.deepcopy(self.lab.get(self.identifier)['state'])
        with patch.object(self.studio,'check_production_bundle') as preflight,self.assertNoGeneration():self.lab.run(self.identifier)
        preflight.assert_not_called();self.assert_preserved(before)
        after=self.lab.get(self.identifier)['state']
        self.assertEqual(after['started_at'],state['started_at']);self.assertEqual(after['time_budget'],state['time_budget'])
    def assertNoGeneration(self):return patch.object(self.studio,'_run',side_effect=AssertionError('No generation is permitted'))
    def assert_terminal_reconciliation_survives_restart(self,status):
        self.terminal(status)
        if status=='partial':self.job['outputs']=[{'filename':'retained.png','type':'output','subfolder':'','prompt_id':'retained'}];self.studio._save(self.job)
        before=self.snapshot();restarted=FakeStudio(self.fixture.root,[]);lab=restarted.production
        with patch.object(restarted,'require_worker',side_effect=AssertionError('No work admission needed')):
            first=lab.resume(self.identifier);second=lab.resume(self.identifier)
        self.assertEqual(first,second);self.assertEqual(first['state']['status'],'failed')
        again=FakeStudio(self.fixture.root,[])
        self.assertEqual(again.production.get(self.identifier)['state'],first['state'])
        self.assertEqual(again.production.get(self.identifier)['budget'],before['budget'])
        restored=again.jobs[self.job['id']]
        self.assertEqual(restored['prompt_ids'],before['job']['prompt_ids']);self.assertEqual(restored['submissions'],before['job']['submissions'])
        self.assertEqual(restored['outputs'],before['job']['outputs']);self.assertEqual(restored['tracking_disposition'],before['job']['tracking_disposition'])
        self.assertEqual((again.production.root/self.identifier/'plan.json').read_bytes(),before['plan'])
        self.assertEqual(again.requests,[]);self.assertTrue(again.queue.empty());self.assertTrue(restarted.queue.empty())
    def test_terminal_reconciliation_is_durable_idempotent_and_needs_no_worker(self):
        self.assert_terminal_reconciliation_survives_restart('failed')
    def test_partial_terminal_reconciliation_survives_restart_without_new_work(self):
        self.assert_terminal_reconciliation_survives_restart('partial')
    def test_failed_state_write_leaves_previous_project_and_receipts_intact(self):
        self.terminal('failed');before=self.snapshot();project=self.lab.get(self.identifier)
        with patch.object(self.lab,'_state',side_effect=OSError('database unavailable')):
            with self.assertRaisesRegex(OSError,'database unavailable'):self.lab.resume(self.identifier)
        self.assertEqual(self.lab.get(self.identifier),project);self.assertEqual(self.snapshot(),before)
        self.lab.resume(self.identifier);self.assert_preserved(before)
    def test_pending_unknown_tail_cannot_be_relabelled_terminal(self):
        self.terminal('failed');self.job['pending_submission']={};self.studio._save(self.job)
        before=self.snapshot();state=copy.deepcopy(self.lab.get(self.identifier)['state'])
        with self.assertRaisesRegex(ValueError,'Resume observation'):self.lab.resume(self.identifier)
        self.assertEqual(self.lab.get(self.identifier)['state'],state);self.assertEqual(self.snapshot(),before)
    def test_malformed_terminal_receipts_do_not_authorize_or_close(self):
        self.terminal('failed');original=copy.deepcopy(self.job)
        for key,value in (('prompt_ids',[]),('prompt_ids',['different']),('submissions',[]),('submissions',[None]),
                          ('submissions',[dict(original['submissions'][0],status='observing')])):
            with self.subTest(key=key,value=value):
                self.job.clear();self.job.update(copy.deepcopy(original));self.job[key]=value
                before=self.lab._get(self.identifier)['state'];queued=self.studio.queue.qsize()
                with self.assertRaisesRegex(ValueError,'Resume observation'):self.lab.resume(self.identifier)
                self.assertEqual(self.lab._get(self.identifier)['state'],before);self.assertEqual(self.studio.queue.qsize(),queued)


class TerminalFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required for real frontend handler contracts')
    def test_terminal_outcome_controls(self):
        subprocess.run(['node',str(Path(__file__).with_name('production_terminal_frontend.cjs'))],check=True)


class TerminalHTTPTests(unittest.TestCase):
    def reconcile(self,outcome):
        from http.client import HTTPConnection
        from http.server import ThreadingHTTPServer
        import threading
        fixture=TerminalObservationTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.terminal(outcome);before=fixture.snapshot();state=fixture.lab._get(fixture.identifier)['state']
        fixture.fixture.patches[0].stop()
        handler=type('TerminalHandler',(server.Handler,),{'studio':fixture.studio})
        http=ThreadingHTTPServer(('127.0.0.1',0),handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        def close():http.shutdown();http.server_close();thread.join(2)
        self.addCleanup(close)
        def request(method):
            conn=HTTPConnection('127.0.0.1',http.server_port,timeout=5)
            try:
                route='/api/production/'+fixture.identifier+('/resume' if method=='POST' else '')
                conn.request(method,route,'{}' if method=='POST' else None,{'Host':'127.0.0.1:8191','Origin':'http://127.0.0.1:8191','Content-Type':'application/json'})
                response=conn.getresponse();self.assertEqual(response.status,202 if method=='POST' else 200);return json.loads(response.read())
            finally:conn.close()
        observed=request('GET');self.assertTrue(observed['can_reconcile_tracking'])
        self.assertEqual(fixture.lab._get(fixture.identifier)['state'],state,'A GET projects eligibility only')
        result=request('POST');self.assertEqual(result['state']['status'],'failed');self.assertFalse(result['can_reconcile_tracking'])
        self.assertEqual(request('POST'),result);fixture.assert_preserved(before)
    def test_failed_reconciliation_uses_existing_http_command_without_queuing(self):self.reconcile('failed')
    def test_partial_reconciliation_uses_existing_http_command_without_queuing(self):self.reconcile('partial')
