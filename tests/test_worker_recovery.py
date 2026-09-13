"""Causal #95 contracts: real queue dispatch, receipts and HTTP construction; no GPU."""
import copy
from http.client import HTTPConnection, IncompleteRead
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import io
import shutil
import threading
import unittest
from unittest.mock import patch
from urllib.parse import unquote

import test_production as fixtures
from test_server import FakeStudio, server


class WorkerRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ProductionTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.root=self.fixture.root;self.studio=FakeStudio(self.root,[])
    def job(self):
        return self.studio.jobs[self.studio.create_job({'preset_id':'demo','controls':{}},enqueue=False)['id']]
    def dispatch(self, items):
        with patch.object(self.studio.queue,'get',side_effect=[*items,KeyboardInterrupt]):
            with self.assertRaises(KeyboardInterrupt):self.studio._work()
    def dead_worker(self):
        # A genuinely started/finished thread, not an is_alive() stub.
        self.fixture.patches[0].stop()
        worker=threading.Thread(target=lambda:None);worker.start();worker.join(2)
        self.assertIsNotNone(worker.ident);self.assertFalse(worker.is_alive());self.studio.worker=worker
    def test_job_failure_recording_error_does_not_lose_next_queue_item(self):
        bad=self.job();good=self.job();save=self.studio._save;run=self.studio._run
        self.studio.replies=iter([{'queue_running':[],'queue_pending':[]},{'prompt_id':'next'},
                                 {'next':{'status':{'status_str':'success'},'outputs':{}}}])
        def execute(job):
            if job['id']==bad['id']:raise RuntimeError('pre-submission failure')
            return run(job)
        def persist(job):
            if job['id']==bad['id']:raise OSError('disk full while recording failure')
            return save(job)
        with patch.object(self.studio,'_run',side_effect=execute),patch.object(self.studio,'_save',side_effect=persist):
            self.dispatch([('generate',bad['id']),('generate',good['id'])])
        self.assertEqual(good['status'],'completed')
        self.assertEqual([args[0] for args,_ in self.studio.requests],['/queue','/prompt','/history/next'])
        self.assertEqual(json.loads((self.studio.runs/bad['id']/'state.json').read_bytes())['status'],'queued')
        self.assertEqual(self.studio.worker_failure['id'],bad['id'])
        self.assertIn('disk full',self.studio.worker_failure['recording_error'])
    def test_project_failure_recording_error_does_not_kill_dispatch(self):
        good=self.job();seen=[]
        with patch.object(self.studio.production,'run',side_effect=RuntimeError('executor failed')), \
             patch.object(self.studio.production,'_mutate',side_effect=OSError('database locked')), \
             patch.object(self.studio,'_run',side_effect=lambda job:seen.append(job['id'])):
            self.dispatch([('production','a'*32),('generate',good['id'])])
        self.assertEqual(seen,[good['id']]);self.assertEqual(self.studio.worker_failure['action'],'production')
        self.assertIn('database locked',self.studio.worker_failure['recording_error'])
    def test_unknown_project_does_not_kill_worker(self):
        good=self.job();seen=[]
        with patch.object(self.studio,'_run',side_effect=lambda job:seen.append(job['id'])):
            self.dispatch([('production','a'*32),('generate',good['id'])])
        self.assertEqual(seen,[good['id']])
    def test_secondary_diagnostic_failure_cannot_escape_dispatch(self):
        good=self.job();seen=[]
        with patch.object(self.studio.production,'run',side_effect=RuntimeError('execution')), \
             patch.object(self.studio.production,'_mutate',side_effect=OSError('storage')), \
             patch.object(server.sys,'stderr',type('BrokenLog',(),{'write':lambda *_:(_ for _ in ()).throw(OSError('log locked'))})()), \
             patch.object(self.studio,'_run',side_effect=lambda job:seen.append(job['id'])):
            self.dispatch([('production','a'*32),('generate',good['id'])])
        self.assertEqual(seen,[good['id']])
    def test_comparison_observation_processing_error_stays_uncertain(self):
        self.studio.replies=iter([{'queue_running':[],'queue_pending':[]},{'prompt_id':'retained'},OSError('history unavailable')])
        lab=self.studio.production;project=lab.create(self.fixture.intent());lab.start(project['id']);lab.run(project['id'])
        job=self.studio.jobs[lab.get(project['id'])['state']['attempts']['0']['job_id']]
        before=copy.deepcopy(job['submissions']);lab.resume(project['id'])
        self.studio.replies=iter([{'retained':{'status':[], 'outputs':{}}}])
        self.dispatch([('production',project['id'])])
        self.assertEqual(job['status'],'uncertain');self.assertEqual(job['submissions'],before)
        self.assertEqual(lab.get(project['id'])['state']['status'],'uncertain')
        self.assertEqual(self.fixture.post_count(self.studio),1);self.assertEqual(len(self.studio.jobs),1)

    def test_unexpected_post_boundary_error_keeps_pending_intent_uncertain(self):
        job=self.job();pending={'index':0,'graph':copy.deepcopy(job['graph'])}
        def fail(current):
            current.update(status='submitting',pending_submission=copy.deepcopy(pending));self.studio._save(current)
            raise RuntimeError('unexpected transport adapter error')
        with patch.object(self.studio,'_run',side_effect=fail):self.dispatch([('generate',job['id'])])
        self.assertEqual(job['status'],'uncertain');self.assertEqual(job['pending_submission'],pending)
        saved=json.loads((self.studio.runs/job['id']/'state.json').read_bytes())
        self.assertEqual(saved['status'],'uncertain');self.assertEqual(saved['pending_submission'],pending)
        self.assertEqual(self.studio.requests,[])
    def test_confirmed_terminal_failure_is_not_downgraded_to_unknown(self):
        job=self.job()
        self.studio.replies=iter([{'queue_running':[],'queue_pending':[]},{'prompt_id':'failed'},
                                 {'failed':{'status':{'status_str':'error'}}}])
        self.dispatch([('generate',job['id'])])
        self.assertEqual(job['status'],'failed');self.assertEqual(job['submissions'][0]['status'],'failed')
        self.assertIsNotNone(job['finished_at'])
    def test_worker_error_is_visible_without_claiming_comfy_is_offline(self):
        with patch.object(self.studio.production,'run',side_effect=ValueError('x'*1000)), \
             patch.object(self.studio.production,'_mutate',side_effect=OSError('y'*1000)):
            self.dispatch([('production','a'*32)])
        self.studio.replies=iter([{'system':{},'devices':[]},{}])
        health=self.studio.health()
        self.assertTrue(health['online']);self.assertTrue(health['worker_alive']);self.assertTrue(health['degraded'])
        self.assertEqual(health['worker_failure'],self.studio.worker_failure)
        self.assertLessEqual(len(health['worker_failure']['recording_error']),500)
    def test_dead_worker_rejects_start_before_reservation_and_enqueue(self):
        lab=self.studio.production;project=lab.create(self.fixture.intent());before=lab.get(project['id'])
        self.dead_worker()
        with self.assertRaisesRegex(ValueError,'worker'):lab.start(project['id'])
        self.assertEqual(lab.get(project['id']),before);self.assertEqual(self.studio.queue.qsize(),0)
    def test_dead_worker_rejects_resume_before_state_change(self):
        lab=self.studio.production;project=lab.create(self.fixture.intent());lab.start(project['id'])
        lab._mutate(project['id'],status='interrupted');before=lab.get(project['id']);queued=self.studio.queue.qsize()
        self.dead_worker()
        with self.assertRaisesRegex(ValueError,'worker'):lab.resume(project['id'])
        self.assertEqual(lab.get(project['id']),before);self.assertEqual(self.studio.queue.qsize(),queued)
    def test_dead_worker_rejects_observation_without_consuming_stop_consent(self):
        job=self.job();job.update(status='uncertain',prompt_ids=['known'],submissions=[{'prompt_id':'known','status':'observing'}]);self.studio._save(job)
        self.studio.stop_tracking(job['id'],'pause');before=copy.deepcopy(job)
        disk=(self.studio.runs/job['id']/'state.json').read_bytes();self.dead_worker()
        with self.assertRaisesRegex(ValueError,'worker'):self.studio.resume_job(job['id'])
        self.assertEqual(job,before);self.assertEqual((self.studio.runs/job['id']/'state.json').read_bytes(),disk)
        self.assertEqual(self.studio.queue.qsize(),0)
    def test_malformed_history_transports_preserve_observation_uncertainty(self):
        errors=(IncompleteRead(b'{'),UnicodeDecodeError('utf8',b'\xff',0,1,'invalid'),json.JSONDecodeError('bad','{',0))
        for error in errors:
            with self.subTest(error=type(error).__name__):
                job=self.job();job.update(status='uncertain',prompt_ids=['known'],submissions=[{'prompt_id':'known','status':'observing'}]);self.studio._save(job)
                self.studio.replies=iter([error]);self.studio._resume(job)
                self.assertEqual(job['status'],'uncertain');self.assertEqual(job['prompt_ids'],['known'])
                self.assertNotIn('finished_at',job)
        self.assertFalse(any(args[0]=='/prompt' for args,_ in self.studio.requests))
    def test_history_id_is_one_encoded_path_component_and_exact_receipt_key(self):
        # Real HTTPConnection validates a raw target (spaces/newlines would fail).
        job=self.job();ids=[' known ','a/b?x=1#fragment','%already%20encoded','日本語\t\r\n']
        for prompt_id in ids:
            with self.subTest(prompt_id=prompt_id):
                submission={'prompt_id':prompt_id,'status':'observing'}
                targets=[]
                def request(path,**kwargs):
                    connection=HTTPConnection('127.0.0.1');connection.putrequest('GET',path)
                    targets.append(path);return {prompt_id:{'status':{'status_str':'success'},'outputs':{}}}
                with patch.object(self.studio,'_request',side_effect=request):self.assertTrue(self.studio._wait_history(job,submission))
                self.assertEqual(unquote(targets[0][len('/history/'):]),prompt_id)
                self.assertEqual(targets[0].count('/'),2);self.assertNotIn('?',targets[0]);self.assertNotIn('#',targets[0])
                self.assertEqual(submission['prompt_id'],prompt_id);self.assertEqual(submission['status'],'completed')

    def test_real_worker_survives_secondary_failure_without_replacement(self):
        bad=self.job();good=self.job();reached=threading.Event();release=threading.Event();threads=[]
        def execute(job):
            threads.append(threading.get_ident())
            if job['id']==bad['id']:raise RuntimeError('first failed')
            reached.set();release.wait(3)
        self.fixture.patches[0].stop()
        with patch.object(self.studio.queue,'get',side_effect=[('generate',bad['id']),('generate',good['id']),SystemExit]), \
             patch.object(self.studio,'_run',side_effect=execute),patch.object(self.studio,'_save',side_effect=OSError('locked')), \
             patch.object(server.sys,'stderr',io.StringIO()):
            worker=threading.Thread(target=self.studio._work,daemon=True);self.studio.worker=worker;worker.start()
            try:
                self.assertTrue(reached.wait(3),'same consumer must reach the second item')
                self.assertTrue(worker.is_alive());self.assertEqual(threads,[worker.ident,worker.ident])
            finally:release.set();worker.join(3)
            self.assertFalse(worker.is_alive())
    def test_production_unexpected_submission_error_keeps_uncertainty(self):
        lab=self.studio.production;project=lab.create(self.fixture.intent());lab.start(project['id'])
        def fail(job):
            job.update(status='submitting',pending_submission={'index':0,'graph':copy.deepcopy(job['graph'])})
            self.studio._save(job);raise RuntimeError('unexpected response handler')
        with patch.object(self.studio,'_run',side_effect=fail):lab.run(project['id'])
        result=lab.get(project['id']);job=next(iter(self.studio.jobs.values()))
        self.assertEqual(result['state']['status'],'uncertain');self.assertEqual(job['status'],'uncertain')
        self.assertEqual(len(self.studio.jobs),1);self.assertEqual(result['budget']['reserved'],2)
        self.assertIn('pending_submission',job);self.assertEqual(self.studio.requests,[])
    def project_save_fault(self, known):
        lab=self.studio.production;project=lab.create(self.fixture.intent());lab.start(project['id'])
        good=self.job();save=self.studio._save;seen=[];retained={}
        def execute(job):
            if job['id']==good['id']:seen.append(job['id']);return
            if known:job.update(status='running',prompt_ids=['known'],submissions=[{'prompt_id':'known','status':'observing'}])
            else:job.update(status='submitting',pending_submission={'index':0,'graph':copy.deepcopy(job['graph'])})
            save(job);retained.update(id=job['id'],state=(self.studio.runs/job['id']/'state.json').read_bytes())
            raise RuntimeError('execution processing failed after possible submission')
        def persist(job):
            if job.get('status')=='uncertain':raise OSError('run directory is full; SQLite remains writable')
            return save(job)
        with patch.object(self.studio,'_run',side_effect=execute),patch.object(self.studio,'_save',side_effect=persist):
            self.dispatch([('production',project['id']),('generate',good['id'])])
        result=lab.get(project['id']);job=self.studio.jobs[retained['id']]
        self.assertEqual(result['state']['status'],'uncertain')
        self.assertIn('run directory is full',result['state']['message'])
        self.assertEqual(job['status'],'uncertain');self.assertEqual(result['budget']['reserved'],2)
        self.assertEqual(seen,[good['id']]);self.assertEqual(len(self.studio.jobs),2)
        self.assertEqual((self.studio.runs/job['id']/'state.json').read_bytes(),retained['state'])
        preserved={name:(self.studio.runs/job['id']/name).read_bytes() for name in ('recipe.json','workflow.json')}
        restarted=FakeStudio(self.root,[]);recovered=restarted.production.get(project['id'])
        self.assertEqual(recovered['state']['status'],'uncertain');self.assertEqual(recovered['budget'],result['budget'])
        self.assertEqual(restarted.jobs[job['id']]['prompt_ids'],['known'] if known else [])
        for _ in range(2):
            restarted.replies=iter([OSError('history unavailable')])
            restarted.production.resume(project['id']);restarted.production.run(project['id'])
            self.assertEqual(restarted.production.get(project['id'])['state']['status'],'uncertain')
        self.assertFalse(any(args[0]=='/prompt' for args,_ in restarted.requests))
        self.assertEqual(restarted.production.get(project['id'])['budget'],result['budget'])
        self.assertEqual(len(restarted.jobs),2)
        self.assertEqual({name:(restarted.runs/job['id']/name).read_bytes() for name in preserved},preserved)
    def test_pending_project_save_failure_preserves_durable_uncertainty(self):
        self.project_save_fault(False)
    def test_known_project_save_failure_preserves_durable_uncertainty(self):
        self.project_save_fault(True)

    def test_history_round_trip_uses_original_id_not_another_path_or_query(self):
        seen=[];prompt_id=' /id?other=1#fragment % plus+日本語 '
        class History(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_GET(self):
                seen.append(self.path)
                identity=unquote(self.path[len('/history/'):])
                data=json.dumps({identity:{'status':{'status_str':'success'},'outputs':{}}}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        self.fixture.patches[0].stop()
        http=ThreadingHTTPServer(('127.0.0.1',0),History);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        try:
            job=self.job();job['comfy_url']='http://127.0.0.1:'+str(http.server_port)
            submission={'prompt_id':prompt_id,'status':'observing'};job.update(prompt_ids=[prompt_id],submissions=[submission])
            with patch.object(self.studio,'_request',server.Studio._request.__get__(self.studio)):
                self.assertTrue(self.studio._wait_history(job,submission))
            self.assertEqual(len(seen),1);self.assertEqual(seen[0].count('/'),2)
            self.assertEqual(submission['status'],'completed')
            saved=json.loads((self.studio.runs/job['id']/'state.json').read_bytes())
            self.assertEqual(saved['prompt_ids'],[prompt_id]);self.assertEqual(saved['submissions'][0]['prompt_id'],prompt_id)
        finally:http.shutdown();http.server_close();thread.join(2)
    def test_history_wrong_shapes_remain_unknown(self):
        for response in ([],None,True,{'known':[]},{'known':'not history'}):
            with self.subTest(response=response):
                job=self.job();job.update(status='uncertain',prompt_ids=['known'],submissions=[{'prompt_id':'known','status':'observing'}])
                self.studio.replies=iter([response]);self.studio._resume(job)
                self.assertEqual(job['status'],'uncertain');self.assertEqual(job['submissions'][0]['status'],'observing')
        self.assertFalse(any(args[0]=='/prompt' for args,_ in self.studio.requests))
    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg fixture required')
    def test_dead_worker_rejects_scene_render_without_inserting_attempt(self):
        from test_server import png
        self.studio.config.update({name:shutil.which(name) for name in ('ffmpeg','ffprobe')})
        asset=self.studio.import_image('source.png','image/png',png())['asset']
        av=self.studio.production.av;doc=av.create({'action':'create','name':'Scene','asset_ids':[asset['id']],'frames_per_shot':24})
        before=av.inspect(doc['id']);self.dead_worker()
        with self.assertRaisesRegex(ValueError,'worker'):av.request_render(doc['id'],{'expected_revision':0})
        self.assertEqual(av.inspect(doc['id']),before);self.assertEqual(self.studio.queue.qsize(),0)
        with self.studio.production.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM av_renders').fetchone()[0],0)


class VoiceWorkerAdmissionTests(unittest.TestCase):
    def setUp(self):
        import test_voice_baseline
        self.fixture=test_voice_baseline.VoiceTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
    def test_direct_voice_resume_does_not_mutate_an_unserviceable_queue(self):
        import voice_baseline
        f=self.fixture;project=f.prepare();f.production._mutate(project['id'],status='interrupted')
        before=f.production.get(project['id']);f.patches[0].stop()
        worker=threading.Thread(target=lambda:None);worker.start();worker.join(2);f.studio.worker=worker
        for resume in (f.production.resume,lambda identifier:voice_baseline.resume(f.production,identifier)):
            with self.assertRaisesRegex(ValueError,'worker'):resume(project['id'])
        self.assertEqual(f.production.get(project['id']),before);self.assertEqual(f.studio.queue.qsize(),0)
