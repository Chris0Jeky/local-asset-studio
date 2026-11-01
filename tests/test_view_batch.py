"""scripts/view_batch.py against an in-process stub of the Studio's upload, job and image routes.

The stub records every upload and every job creation, so the tests can prove ordering, the Origin header, that a rerun
submits nothing, and above all that no uncertain outcome is ever submitted a second time.
"""
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from http.server import BaseHTTPRequestHandler
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from http_test_server import ThreadingHTTPServer
spec=importlib.util.spec_from_file_location('view_batch_fixture',ROOT/'scripts/view_batch.py')
vb=importlib.util.module_from_spec(spec);spec.loader.exec_module(vb)
ORIGIN='http://127.0.0.1:8191'


class StubStudio:
    """Scripted Studio. `final[view]` is the status its job settles on (default completed); a view in `drop` gets its
    job created but the reply is cut, which is exactly an uncertain submission."""
    def __init__(self):
        self.uploads=[];self.creations=[];self.jobs={};self.final={};self.drop=set();self.bad_origin=0;self.stalls=0;self.abandonment=None

    def handler(self):
        stub=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def reply(self,code,body,kind='application/json'):
                raw=body if isinstance(body,bytes) else json.dumps(body).encode()
                self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            def do_POST(self):
                body=self.rfile.read(int(self.headers.get('Content-Length','0')))
                if self.headers.get('Origin')!=ORIGIN: stub.bad_origin+=1;return self.reply(403,{'error':'Local same-origin request required'})
                if self.path=='/api/upload':
                    name='%032x_%s'%(len(stub.uploads),self.headers['X-Filename']);stub.uploads.append((name,body,self.headers['Content-Type']))
                    return self.reply(201,{'file':name})
                payload=json.loads(body);stub.creations.append(payload)
                view=next(Path(n).stem.split('_',1)[1] for n,_,_ in stub.uploads if n==payload['controls']['reference'])
                job_id='job-%d'%len(stub.creations);stub.jobs[job_id]=dict(view=view,polls=0)
                if view in stub.drop: self.close_connection=True;return
                self.reply(201,{'id':job_id,'status':'queued'})
            def do_GET(self):
                parts=self.path.split('/')
                job=stub.jobs.get(parts[3]) if len(parts)>3 else None
                if not job: return self.reply(404,{'error':'Unknown job'})
                if parts[2]=='image': return self.reply(200,b'out-'+job['view'].encode(),'image/png')
                if stub.stalls: stub.stalls-=1;return self.reply(503,{'error':'busy'})
                job['polls']+=1;status=stub.final.get(job['view'],'completed') if job['polls']>1 else 'running'
                self.reply(200,{'id':parts[3],'status':status,'elapsed_seconds':12.5,'abandonment':stub.abandonment,'prompt_ids':['p-'+parts[3]],'message':'scripted '+status,'outputs':[{'filename':'x.png'}] if status=='completed' else []})
        return Handler


class ViewBatchTests(unittest.TestCase):
    def setUp(self):
        self.stub=StubStudio();self.server=ThreadingHTTPServer(('127.0.0.1',0),self.stub.handler())
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(lambda:(self.server.shutdown(),self.server.server_close()))
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.inp=self.root/'views';self.inp.mkdir();self.out=self.root/'painted'
        for name in ('b.png','a.png','c.jpg'): (self.inp/name).write_bytes(b'src-'+name.encode())

    def run_batch(self,*extra,expect_stop=None):
        argv=['--preset','union-repaint-wai','--in',str(self.inp),'--out',str(self.out),'--url','http://127.0.0.1:%d'%self.server.server_port,
              '--poll','0.01','--prompt','a knight','--set','denoise=0.45','--set','seed=1',*extra]
        printed=io.StringIO()
        with redirect_stdout(printed):
            if expect_stop is None: return vb.main(argv),printed.getvalue()
            with self.assertRaises(SystemExit) as stop: vb.main(argv)
        self.assertRegex(str(stop.exception),expect_stop);return stop.exception,printed.getvalue()

    def manifest(self): return json.loads((self.out/'manifest.json').read_text(encoding='utf-8'))

    def test_runs_views_in_sorted_order_and_records_the_manifest(self):
        (self.inp/'views.json').write_text(json.dumps({'b':{'positive':'a knight, side view','seed':7}}))
        self.run_batch()
        self.assertEqual([Path(n).name.split('_',1)[1] for n,_,_ in self.stub.uploads],['a.png','b.png','c.jpg'])
        self.assertEqual([t for _,_,t in self.stub.uploads],['image/png','image/png','image/jpeg'])
        self.assertEqual(self.stub.bad_origin,0)
        sent=self.stub.creations
        self.assertEqual([c['controls']['reference'] for c in sent],[n for n,_,_ in self.stub.uploads])
        self.assertEqual(sent[0],{'preset_id':'union-repaint-wai','batch_count':1,'controls':{'positive':'a knight','denoise':0.45,'seed':1,'reference':self.stub.uploads[0][0]}})
        self.assertEqual((sent[1]['controls']['positive'],sent[1]['controls']['seed'],sent[1]['controls']['denoise']),('a knight, side view',7,0.45))
        for view in 'abc': self.assertEqual((self.out/(view+'.png')).read_bytes(),('out-'+view).encode())
        data=self.manifest();self.assertEqual((data['preset'],list(data['views'])),('union-repaint-wai',['a','b','c']))
        self.assertEqual(data['controls'],{'positive':'a knight','denoise':0.45,'seed':1})
        b=data['views']['b']
        self.assertEqual((b['status'],b['job_id'],b['prompt_id'],b['source_sha256'],b['output_sha256']),
                         ('completed','job-2','p-job-2',hashlib.sha256(b'src-b.png').hexdigest(),hashlib.sha256(b'out-b').hexdigest()))
        self.assertEqual((Path(b['source']),Path(b['output'])),(self.inp/'b.png',self.out/'b.png'));self.assertIsInstance(b['seconds'],float)
        self.assertEqual(b['controls']['seed'],7);self.assertNotIn('reference',b['controls'])
        self.assertFalse((self.out/'manifest.json.tmp').exists())

    def test_rerun_skips_completed_views_and_a_changed_control_needs_force(self):
        self.run_batch();first=self.manifest()
        self.run_batch();self.assertEqual((len(self.stub.uploads),len(self.stub.creations)),(3,3));self.assertEqual(self.manifest()['views'],first['views'])
        self.run_batch('--set','seed=2',expect_stop='Refusing to overwrite .*a\\.png')
        self.assertEqual(len(self.stub.creations),3)
        self.run_batch('--set','seed=2','--force');self.assertEqual(len(self.stub.creations),6)
        self.assertEqual(self.manifest()['views']['a']['controls']['seed'],2)

    def test_existing_output_is_never_overwritten_and_nothing_is_submitted(self):
        self.out.mkdir();(self.out/'b.png').write_bytes(b'mine')
        self.run_batch(expect_stop='Refusing to overwrite .*b\\.png')
        self.assertEqual((self.stub.uploads,self.stub.creations),([],[]));self.assertEqual((self.out/'b.png').read_bytes(),b'mine')
        self.run_batch('--force');self.assertEqual((self.out/'b.png').read_bytes(),b'out-b')

    def test_stops_at_the_first_failed_job_with_the_manifest_intact(self):
        self.stub.final['b']='failed'
        self.run_batch(expect_stop='View b failed \\(job job-2, failed\\): scripted failed')
        self.assertEqual(len(self.stub.creations),2)
        views=self.manifest()['views'];self.assertEqual({k:v['status'] for k,v in views.items()},{'a':'completed','b':'failed'})
        self.assertFalse((self.out/'b.png').exists())
        self.stub.final['b']='completed'  # a known failure may be run again; completed views stay skipped
        self.run_batch();self.assertEqual(len(self.stub.creations),4)

    def test_unknown_job_state_stops_and_is_never_resubmitted(self):
        self.stub.final['b']='uncertain'
        self.run_batch(expect_stop='job job-2 is uncertain.*Not resubmitted')
        self.assertEqual(len(self.stub.creations),2)
        self.assertEqual(self.manifest()['views']['b']['status'],'uncertain')
        self.run_batch(expect_stop='job job-2 is uncertain')  # the rerun polls the same job, it does not create another
        self.assertEqual(len(self.stub.creations),2)
        self.stub.final['b']='completed'
        self.run_batch();self.assertEqual(len(self.stub.creations),3)  # only c is new: b resumed on its own job
        self.assertEqual(self.manifest()['views']['b']['job_id'],'job-2')

    def test_a_slow_studio_is_polled_again_without_a_second_job(self):
        self.stub.stalls=5
        self.run_batch()
        self.assertEqual(self.stub.stalls,0)
        self.assertEqual(len(self.stub.creations),len(self.stub.uploads))

    def test_a_silent_studio_stops_the_run_and_resubmits_nothing(self):
        self.stub.stalls=10**6
        self.run_batch('--silence','0',expect_stop='Lost sight of job job-1')
        self.assertEqual(len(self.stub.creations),1)

    def test_an_abandoned_job_of_unknown_outcome_is_never_resubmitted(self):
        self.stub.final['a']='abandoned';self.stub.abandonment={'basis':'outcome_unknown'}
        self.run_batch(expect_stop='an outcome this run cannot confirm')
        self.run_batch(expect_stop='an outcome this run cannot confirm')
        self.assertEqual(len(self.stub.creations),1)

    def test_a_job_abandoned_as_never_submitted_may_run_again(self):
        self.stub.final['a']='abandoned';self.stub.abandonment={'basis':'never_submitted'}
        self.run_batch(expect_stop='View a failed')
        del self.stub.final['a'];self.stub.abandonment=None
        self.run_batch()
        self.assertEqual(len(self.stub.creations),4)

    def test_a_second_run_on_the_same_folder_is_refused(self):
        self.out.mkdir();(self.out/'.view_batch.lock').write_text('')
        self.run_batch(expect_stop='Another run holds')
        self.assertEqual(self.stub.creations,[])

    def test_seconds_is_the_jobs_own_time_and_the_lock_is_released(self):
        self.run_batch()
        manifest=json.loads((self.out/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual({v['seconds'] for v in manifest['views'].values()},{12.5})
        self.assertFalse((self.out/'.view_batch.lock').exists())

    def test_lost_submit_reply_is_never_resubmitted(self):
        self.stub.drop.add('b')
        self.run_batch(expect_stop='Submission of b.png has an unknown outcome.*Not resubmitted')
        self.assertEqual(len(self.stub.creations),2);self.assertEqual(self.manifest()['views']['b']['status'],'submitting')
        self.run_batch(expect_stop='Not resubmitting: an earlier submission whose outcome is unknown')
        self.assertEqual(len(self.stub.creations),2)

    def test_dry_run_prints_the_plan_and_submits_nothing(self):
        _,printed=self.run_batch('--dry-run')
        self.assertEqual((self.stub.uploads,self.stub.creations,self.out.exists()),([],[],False))
        self.assertEqual([line.split()[:2] for line in printed.splitlines()],[['run','a'],['run','b'],['run','c']])
        self.assertIn('"denoise": 0.45',printed)

    def test_views_json_must_name_real_pictures(self):
        (self.inp/'views.json').write_text(json.dumps({'frnot':{'seed':1}}))
        self.run_batch(expect_stop='views.json names pictures that are not in the folder: frnot')


if __name__=='__main__': unittest.main()
