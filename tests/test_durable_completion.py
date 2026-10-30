"""#1763: observed outputs and terminal states publish through the synchronized writer; a failed publication never resubmits."""
import os
import unittest
from unittest.mock import patch
from urllib.error import URLError

import test_server
from test_server import FakeStudio, server

IDLE={'queue_running':[],'queue_pending':[]}
DONE=lambda pid:{pid:{'status':{'status_str':'success'},'outputs':{'9':{'images':[{'filename':pid+'.png','subfolder':'','type':'output'}]}}}}


class DurableCompletionTests(unittest.TestCase):
    setUp=test_server.ServerTests.setUp
    tearDown=test_server.ServerTests.tearDown
    studio=test_server.ServerTests.studio

    def run_job(self, replies, batch_count=1, publish=None, raises=None, fallback_fails=False):
        s=FakeStudio(self.root,replies);job=s.jobs[s.create_job({'preset_id':'demo','controls':{'seed':40},'batch_count':batch_count},enqueue=False)['id']]
        real=server.observation_state.publish;calls=[]
        def spy(path,value,*args):
            calls.append((path.name,[a for a,_ in s.requests if a][-1][0],value.get('status'),[x.get('status') for x in value.get('submissions',[])],len(value.get('outputs',[]))))
            return (publish or real)(path,value,*args)
        atomic=server.Studio._write_json_atomic
        def plain(self_,path,value):   # the best-effort unsynchronized copy of the uncertain state fails too
            if fallback_fails and path.name=='state.json' and value.get('status')=='uncertain':raise OSError('disk full')
            return atomic(self_,path,value)
        with patch.object(server.observation_state,'publish',side_effect=spy),patch.object(server.time,'sleep'),patch.object(server.Studio,'_write_json_atomic',plain):
            if raises:
                with self.assertRaises(raises):s._run(job)
            else:s._run(job)
        return s,job,[c for c in calls if c[0]=='state.json']

    def posts(self, s): return [a[0] for a,_ in s.requests if a and a[0]=='/prompt']

    def test_observed_outputs_and_terminal_state_publish_synchronized(self):
        s,job,calls=self.run_job([IDLE,{'prompt_id':'p1'},DONE('p1')])
        self.assertEqual(job['status'],'completed')
        # marker, receipt, then the observed outcome (submission completed, output indexed) and the terminal record, all synced.
        self.assertEqual(calls,[('state.json','/queue','submitting',[],0),('state.json','/prompt','running',['observing'],0),
                                ('state.json','/history/p1','running',['completed'],1),('state.json','/history/p1','completed',['completed'],1)])
        self.assertEqual(self.studio().jobs[job['id']]['status'],'completed')

    def test_polls_and_read_failures_stay_unsynchronized(self):
        # An empty poll and a failed read between members add no synchronized writes: four per member plus one terminal.
        s,job,calls=self.run_job([IDLE,{'prompt_id':'p1'},{},DONE('p1'),{'prompt_id':'p2'},URLError('reset'),DONE('p2')],batch_count=2)
        self.assertEqual(job['status'],'completed');self.assertEqual(len(calls),7)
        self.assertEqual([c[2] for c in calls],['submitting','running','running','submitting','running','running','completed'])

    def failing_outcome(self, when, how):
        real=server.observation_state.publish
        def publish(path,value,*args):
            if path.name!='state.json' or not when(value):return real(path,value,*args)
            if how=='fsync':
                with patch.object(server.observation_state.os,'fsync',side_effect=OSError('fsync failed')):return real(path,value,*args)
            if how=='replace':
                with patch.object(server.observation_state.file_replace,'replace',side_effect=PermissionError('replace refused')):return real(path,value,*args)
            raise ValueError('Out of range float values are not JSON compliant')
        return publish

    def assert_restart_safe(self, s, job, prompt_ids):
        self.assertEqual(job['status'],'uncertain');self.assertEqual(job['prompt_ids'],prompt_ids)
        self.assertIn('could not be saved durably',job['message']);self.assertIn('not resubmitted',job['message'])
        self.assertIsNone(s._observation_error(job))   # Resume observation is offered for the retained prompt IDs
        restored=self.studio().jobs[job['id']]
        self.assertEqual(restored['status'],'uncertain');self.assertEqual(restored['prompt_ids'],prompt_ids)
        self.assertFalse(server.submission_evidence.never_submitted(restored))
        self.assertEqual(list(s.runs.joinpath(job['id']).glob('*.tmp')),[])   # the writer cleans its own temp file

    def test_outcome_publication_failure_keeps_prompt_ids_and_sends_no_further_member(self):
        observed=lambda v:any(x.get('status')=='completed' for x in v.get('submissions',[]))
        for how in ('fsync','replace','value'):
            for fallback_fails in (False,True):
                with self.subTest(how=how,fallback_fails=fallback_fails):
                    s,job,_=self.run_job([IDLE,{'prompt_id':'p1'},DONE('p1'),{'prompt_id':'p2'},DONE('p2')],batch_count=2,publish=self.failing_outcome(observed,how),fallback_fails=fallback_fails)
                    self.assertEqual(self.posts(s),['/prompt']);self.assertEqual(job['submissions'][0]['status'],'completed')
                    self.assertEqual([o['filename'] for o in job['outputs']],['p1.png'])   # in-memory evidence is kept
                    self.assert_restart_safe(s,job,['p1'])

    def test_terminal_publication_failure_never_claims_completed(self):
        for how in ('fsync','replace'):
            with self.subTest(how=how):
                s,job,_=self.run_job([IDLE,{'prompt_id':'p1'},DONE('p1')],publish=self.failing_outcome(lambda v:v.get('status')=='completed',how))
                self.assertEqual(self.posts(s),['/prompt']);self.assertEqual(job['submissions'][0]['status'],'completed')
                self.assert_restart_safe(s,job,['p1'])

    def test_failed_history_publication_failure_is_uncertain_not_resubmitted(self):
        error={'p1':{'status':{'status_str':'error','messages':[]},'outputs':{}}}
        s,job,_=self.run_job([IDLE,{'prompt_id':'p1'},error],publish=self.failing_outcome(lambda v:v.get('status')=='failed','fsync'),raises=server.StudioError)
        self.assertEqual(self.posts(s),['/prompt']);self.assertEqual(job['submissions'][0]['status'],'failed')
        self.assert_restart_safe(s,job,['p1'])


if __name__=='__main__':
    unittest.main()
