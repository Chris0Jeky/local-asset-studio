"""Fault-injected manager tests: no model, process termination or GPU required."""
import errno
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.error import URLError

sys.path.insert(0,str(Path(__file__).parents[1]/'app'))
import backend_contracts as contracts
from backends import BackendManager

IDLE={'queue_running':[],'queue_pending':[]}
HEALTH={'system':{'python_version':'test'}}


class FixtureStudio:
    def __init__(self,root,**config):
        self.root=root;self.comfy_root=root/'comfy';self.jobs={};self.lock=threading.Lock()
        self.config={'comfy_root':str(self.comfy_root),'python':str(root/'python.exe'),
                     'hidream_root':str(root/'isolated/ComfyUI'),'qwen21_root':str(root/'qwen21/ComfyUI'),**config}
        self.production=SimpleNamespace(list=lambda:[])
    def _write_json_atomic(self,path,data):
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(data));temporary.replace(path)


class BackendSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.studio=FixtureStudio(self.root);self.manager=BackendManager(self.studio)
        # These fixtures own fake listeners, not the Windows/Linux runner's process table.
        # Nonempty startup scans are exercised in test_backend_startup_interlock.py.
        scan=patch('psutil.process_iter',return_value=[]);scan.start();self.addCleanup(scan.stop)
        for profile in self.manager.profiles.values():
            for item in self.manager.readiness(profile)['requirements']:
                path=Path(item['path'])
                if item['role'] in ('Transformers overlay','Comfy Kitchen overlay'):path.mkdir(parents=True,exist_ok=True)
                else:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'inert fixture')
    def tearDown(self):self.temp.cleanup()
    def process(self,pid=123,created=1):
        proc=Mock();proc.pid=pid;proc.create_time.return_value=created;return proc
    def run_switch(self,request=None,process=None):
        self.manager.operation={'id':'test-switch','status':'running'};self.manager.busy=True
        with patch.object(self.manager,'request',side_effect=request or (lambda p,r,*a: HEALTH if r=='/system_stats' else IDLE)), \
             patch.object(self.manager,'process',side_effect=process or (lambda p:self.process() if p['id']=='hidream' else None)), \
             patch.object(self.manager,'activate') as activate,patch('backends.subprocess.Popen') as launch:
            self.manager._switch('hidream')
            return activate,launch

    def test_queue_requires_both_lists(self):
        for value in (None,[],False,{}, {'queue_running':[]}, {'queue_running':[],'queue_pending':None},
                      {'queue_running':False,'queue_pending':[]},{'queue_running':{},'queue_pending':[]}):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'unknown'):contracts.queue_is_idle(value)
        self.assertTrue(contracts.queue_is_idle(IDLE))
    def test_queue_busy_even_with_other_field_missing(self):
        for key in IDLE:
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'queue was preserved'):contracts.queue_is_idle({key:[['manual']]})
    def test_loopback_urls_and_primary_port(self):
        for url in ('https://127.0.0.1:8188','http://localhost:8188','http://0.0.0.0:8188','http://127.0.0.1',
                    'http://127.0.0.1:8188/x','http://user@127.0.0.1:8188','http://127.0.0.1:8188?q=a',
                    'http://127.0.0.1:0','http://127.0.0.1:99999',None):
            with self.subTest(url=url),self.assertRaises(ValueError):contracts.loopback_port(url)
        manager=BackendManager(FixtureStudio(self.root,comfy_url='http://127.0.0.1:8288/'))
        self.assertEqual(manager.profiles['primary']['port'],8288)
        self.assertEqual(manager.profiles['primary']['url'],'http://127.0.0.1:8288')
        with self.assertRaisesRegex(ValueError,'distinct'):BackendManager(FixtureStudio(self.root,comfy_url='http://127.0.0.1:8192'))
    def test_h3_every_required_file_is_checked_without_loading(self):
        profile=self.manager.profiles['h3'];report=self.manager.readiness(profile)
        self.assertTrue(report['ready']);self.assertEqual(len(contracts.H3_FILES),5)
        self.assertIsNone(report['runtime_compatible']);self.assertIsNone(report['hash_verified'])
        for item in report['requirements']:
            path=Path(item['path']);body=path.read_bytes();path.write_bytes(b'')
            with self.subTest(role=item['role']):
                current=self.manager.readiness(profile);self.assertFalse(current['ready']);self.assertIn(item['role'],current['message'])
            path.write_bytes(body)
    def test_qwen21_needs_its_overlay_and_three_pack_files_inside_the_isolated_root(self):
        profile=self.manager.profiles['qwen21'];report=self.manager.readiness(profile)
        self.assertEqual((profile['port'],profile['url']),(8196,'http://127.0.0.1:8196'))
        self.assertTrue(report['ready']);self.assertEqual(len(contracts.QWEN21_FILES),3)
        roles=[item['role'] for item in report['requirements']]
        self.assertEqual(roles,['Python interpreter','ComfyUI entry','Studio launcher','Comfy Kitchen overlay','diffusion','text encoder','decoder'])
        for item in report['requirements'][3:]:
            self.assertTrue(Path(item['path']).resolve().is_relative_to(Path(profile['root']).resolve()),item)
        overlay=Path(profile['root'])/'python_packages/comfy_kitchen';overlay.rmdir();overlay.write_bytes(b'not a package')
        current=self.manager.readiness(profile);self.assertFalse(current['ready']);self.assertIn('Comfy Kitchen overlay',current['message'])
        overlay.unlink();overlay.mkdir()
        for role,relative in contracts.QWEN21_FILES:
            path=Path(profile['root'])/relative;body=path.read_bytes();path.write_bytes(b'')
            with self.subTest(role=role):
                current=self.manager.readiness(profile);self.assertFalse(current['ready']);self.assertIn(role,current['message'])
            path.write_bytes(body)
    def test_qwen21_launch_is_owned_only_through_its_exact_comfy_root(self):
        profile=self.manager.profiles['qwen21'];argv=[profile['python'],'-s',profile['entry'],'--comfy-root',profile['root']]
        self.assertTrue(BackendManager.matches_configured_process(profile,profile['python'],argv,profile['root']))
        for bad in (argv[:-1]+[str(self.root/'isolated/ComfyUI')],argv[:3]+['--install-root',profile['root']],argv+['--comfy-root',profile['root']]):
            with self.subTest(bad=bad):self.assertFalse(BackendManager.matches_configured_process(profile,profile['python'],bad,profile['root']))
    def test_qwen21_switch_launches_its_launcher_with_the_isolated_root(self):
        self.manager.operation={'id':'test-switch','status':'running'};self.manager.busy=True
        launched=Mock(pid=4321);launched.poll.return_value=1
        with patch.object(self.manager,'request',side_effect=lambda p,r,*a: HEALTH if r=='/system_stats' else IDLE),              patch.object(self.manager,'process',return_value=None),patch.object(self.manager,'activate') as activate,              patch('backends.subprocess.Popen',return_value=launched) as popen:
            self.manager._switch('qwen21')
        profile=self.manager.profiles['qwen21']
        self.assertEqual(popen.call_args.args[0],[profile['python'],'-s',profile['entry'],'--comfy-root',profile['root']])
        self.assertEqual(popen.call_args.kwargs['cwd'],profile['root'])
        activate.assert_not_called();self.assertEqual(self.manager.operation['status'],'failed')
    def test_missing_target_stops_before_thread_or_process_work(self):
        profile=self.manager.profiles['h3'];(Path(profile['root'])/contracts.H3_FILES[1][1]).unlink()
        with patch('backends.threading.Thread') as thread,patch.object(self.manager,'process') as process:
            with self.assertRaisesRegex(ValueError,'text encoder'):self.manager.switch('h3')
        thread.assert_not_called();process.assert_not_called();self.assertFalse(self.manager.busy)
    def test_snapshot_separates_presence_from_online_and_inference(self):
        with patch.object(self.manager,'request',return_value={'system':'wrong schema'}):snapshot=self.manager.snapshot()
        for profile in snapshot['profiles']:
            self.assertTrue(profile['installed']);self.assertFalse(profile['online']);self.assertIsNone(profile['readiness']['runtime_compatible'])
    def test_unknown_queue_never_launches_worker(self):
        for reply in ({},[],{'queue_running':[]}):
            with patch.object(self.manager,'request',return_value=reply),patch('backends.threading.Thread') as thread:
                with self.assertRaises(ValueError):self.manager.switch('hidream')
                thread.assert_not_called();self.assertFalse(self.manager.busy)
    def test_timeout_is_not_offline(self):
        with patch.object(self.manager,'request',side_effect=TimeoutError()),patch.object(self.manager,'process',return_value=None):
            with self.assertRaisesRegex(ValueError,'unknown'):self.manager._idle(self.manager.profiles['h3'],allow_offline=True)
    def test_connection_refused_requires_no_listener(self):
        error=URLError(ConnectionRefusedError(errno.ECONNREFUSED,'refused'))
        with patch.object(self.manager,'request',side_effect=error):
            with patch.object(self.manager,'process',return_value=None):self.assertFalse(self.manager._idle(self.manager.profiles['h3'],allow_offline=True))
            with patch.object(self.manager,'process',return_value=self.process()):
                with self.assertRaisesRegex(ValueError,'unknown'):self.manager._idle(self.manager.profiles['h3'],allow_offline=True)
    def test_generic_network_error_is_not_offline(self):
        with patch.object(self.manager,'request',side_effect=OSError('unexplained')),patch.object(self.manager,'process',return_value=None):
            with self.assertRaisesRegex(ValueError,'unknown'):self.manager._idle(self.manager.profiles['h3'],allow_offline=True)
    def test_busy_or_local_work_blocks_switch(self):
        for state in ('queued','waiting','submitting','running','uncertain'):
            self.studio.jobs={'a':{'status':state}}
            with self.subTest(state=state),self.assertRaisesRegex(ValueError,'reconcile'):self.manager.switch('hidream')
        self.studio.jobs={};self.manager.busy=True
        with self.assertRaisesRegex(ValueError,'already running'):self.manager.switch('hidream')
    def test_uncertain_job_with_stopped_tracking_does_not_block_switch(self):
        stopped={'status':'uncertain','tracking_disposition':{'status':'stopped','reason':'not in ComfyUI queue or history'}}
        self.studio.jobs={'a':stopped};self.assertFalse(self.manager._local_work())
        with patch.object(self.manager,'request',return_value=IDLE),patch('backends.threading.Thread') as thread:self.manager.switch('hidream')
        thread.assert_called_once()
        for disposition in (None,{'status':'resumed'},'stopped'):
            self.studio.jobs={'a':dict(stopped,tracking_disposition=disposition)}
            with self.subTest(disposition=disposition):self.assertTrue(self.manager._local_work())
        self.studio.jobs={'a':dict(stopped,status='running')};self.assertTrue(self.manager._local_work())
        # A stopped record never hides a prompt that is still live in a ComfyUI queue: the endpoint check refuses.
        self.studio.jobs={'a':stopped}
        for busy in ({'queue_running':[['still-running']],'queue_pending':[]},{'queue_running':[],'queue_pending':[['still-queued']]}):
            with self.subTest(queue=busy),patch.object(self.manager,'request',return_value=busy),patch('backends.threading.Thread') as thread:
                with self.assertRaises(ValueError):self.manager.switch('hidream')
                thread.assert_not_called()
    def test_failed_intent_write_releases_gate(self):
        with patch.object(self.manager,'request',return_value=IDLE),patch.object(self.manager,'_save',side_effect=OSError('disk full')),patch('backends.threading.Thread') as thread:
            with self.assertRaises(OSError):self.manager.switch('hidream')
        thread.assert_not_called();self.assertFalse(self.manager.busy);self.assertIsNone(self.manager.operation)
    def test_failed_thread_start_is_durable_and_releases_gate(self):
        with patch.object(self.manager,'request',return_value=IDLE),patch('backends.threading.Thread.start',side_effect=RuntimeError('thread failed')):
            with self.assertRaises(RuntimeError):self.manager.switch('hidream')
        self.assertFalse(self.manager.busy);self.assertEqual(json.loads(self.manager.state_path.read_text())['operation']['status'],'failed')
    def test_restart_is_observation_only_even_with_bad_state_shape(self):
        for value in ([],{'active':'hidream','operation':'bad'},{'active':'hidream','operation':{'status':'running'}}):
            self.studio._write_json_atomic(self.manager.state_path,value)
            with patch('backends.subprocess.Popen') as launch,patch('backends.threading.Thread') as thread:manager=BackendManager(self.studio)
            launch.assert_not_called();thread.assert_not_called();self.assertFalse(manager.busy)
            if isinstance(value,dict) and isinstance(value['operation'],dict):self.assertEqual(manager.operation['status'],'interrupted')
    def test_executed_script_not_later_python_argument(self):
        p=self.manager.profiles['primary'];good=[p['python'],'-s',p['entry'],'--listen','127.0.0.1','--port',str(p['port'])]
        self.assertTrue(self.manager.matches_configured_process(p,p['python'],good,p['root']))
        for argv in ([p['python'],'other.py',*good[2:]], [p['python'],'-c','pass',*good[2:]],
                     [*good,'--listen','0.0.0.0'],[*good,'--port','1234'],[p['python'],'-m','other',*good[2:]]):
            with self.subTest(argv=argv):self.assertFalse(self.manager.matches_configured_process(p,p['python'],argv,p['root']))
    def test_relative_isolated_root_is_relative_to_process_cwd(self):
        p=self.manager.profiles['hidream'];argv=[p['python'],p['entry'],'--install-root','..']
        self.assertTrue(self.manager.matches_configured_process(p,p['python'],argv,p['root']))
        self.assertFalse(self.manager.matches_configured_process(p,p['python'],argv+['--install-root','/other'],p['root']))
    def test_inaccessible_listener_is_not_absent(self):
        import psutil
        listener=SimpleNamespace(status='LISTEN',laddr=SimpleNamespace(port=8188,ip='127.0.0.1'),pid=555)
        for error in (psutil.AccessDenied(555),psutil.NoSuchProcess(555)):
            with patch.object(psutil,'net_connections',return_value=[listener]),patch.object(psutil,'Process',side_effect=error):
                with self.assertRaisesRegex(ValueError,'could not be verified'):self.manager.process(self.manager.profiles['primary'])
    def test_wildcard_missing_pid_and_ambiguous_listeners_are_preserved(self):
        import psutil
        def listener(ip='127.0.0.1',pid=555):return SimpleNamespace(status='LISTEN',laddr=SimpleNamespace(port=8188,ip=ip),pid=pid)
        for listeners in ([listener('0.0.0.0')],[listener('::')],[listener(pid=None)],[listener(),listener(pid=556)]):
            with patch.object(psutil,'net_connections',return_value=listeners),patch.object(psutil,'Process') as process:
                with self.assertRaises(ValueError):self.manager.process(self.manager.profiles['primary'])
                process.assert_not_called()
    def test_foreign_target_is_detected_before_stopping_main(self):
        main=self.process()
        def observe(p):
            if p['id']=='hidream':raise ValueError('foreign target')
            return main if p['id']=='primary' else None
        activate,launch=self.run_switch(process=observe)
        main.terminate.assert_not_called();activate.assert_not_called();launch.assert_not_called()
        self.assertEqual(self.manager.operation['status'],'failed');self.assertFalse(self.manager.busy)
    def test_process_replacement_stops_nothing(self):
        original=self.process();replacement=self.process(created=2);calls=0
        def observe(p):
            nonlocal calls
            if p['id']!='primary':return None
            calls+=1;return original if calls==1 else replacement
        activate,launch=self.run_switch(process=observe)
        original.terminate.assert_not_called();replacement.terminate.assert_not_called();launch.assert_not_called();activate.assert_not_called()
        self.assertIn('changed',self.manager.operation['message'])
    def test_manual_work_arriving_before_termination_is_preserved(self):
        main=self.process();count=0
        def request(p,r,*args):
            nonlocal count
            if p['id']=='primary' and r=='/queue':
                count+=1
                if count>1:return {'queue_running':[['manual']],'queue_pending':[]}
            return IDLE
        activate,launch=self.run_switch(request=request,process=lambda p:main if p['id']=='primary' else None)
        main.terminate.assert_not_called();launch.assert_not_called();activate.assert_not_called()
        self.assertIn('preserved',self.manager.operation['message'])
    def test_reused_target_requires_health_not_just_matching_process(self):
        activate,launch=self.run_switch(request=lambda *a: IDLE)
        activate.assert_not_called();launch.assert_not_called();self.assertIn('not ready',self.manager.operation['message'])
    def test_reused_idle_healthy_target_completes_without_launch(self):
        activate,launch=self.run_switch()
        activate.assert_called_once_with('hidream');launch.assert_not_called()
        self.assertEqual(self.manager.operation['status'],'completed');self.assertIn('inference was not checked',self.manager.operation['message'])
    def test_failed_startup_preserves_live_process_without_blind_cleanup(self):
        child=self.process(pid=900);child.poll.return_value=None
        self.manager.operation={'id':'timeout','status':'running'};self.manager.busy=True
        def request(p,r,*a):return IDLE if r=='/queue' else {'system':None}
        with patch.object(self.manager,'request',side_effect=request),patch.object(self.manager,'process',return_value=None), \
             patch('backends.subprocess.Popen',return_value=child),patch('backends.time.sleep'),patch.object(self.manager,'activate') as activate:
            self.manager._switch('hidream')
        child.terminate.assert_not_called();activate.assert_not_called();self.assertFalse(self.manager.busy)
        self.assertEqual(self.manager.operation['preserved_pid'],900);self.assertEqual(self.manager.operation['status'],'failed')
    def test_new_local_work_at_worker_start_blocks_all_process_actions(self):
        self.studio.jobs={'new':{'status':'queued'}}
        activate,launch=self.run_switch()
        activate.assert_not_called();launch.assert_not_called();self.assertIn('New Studio work',self.manager.operation['message'])
    def test_retained_startup_before_listener_blocks_new_switch(self):
        import psutil
        self.manager.operation={'status':'interrupted','target':'hidream','pid':900}
        child=self.process(pid=900);profile=self.manager.profiles['hidream']
        child.exe.return_value=profile['python'];child.cwd.return_value=profile['root']
        child.cmdline.return_value=[profile['python'],profile['entry'],'--install-root',str(Path(profile['root']).parent)]
        with patch.object(psutil,'Process',return_value=child),patch.object(self.manager,'process',return_value=None),patch('backends.threading.Thread') as thread:
            with self.assertRaisesRegex(ValueError,'retained startup'):self.manager.switch('primary')
        child.terminate.assert_not_called();thread.assert_not_called();self.assertFalse(self.manager.busy)
    def test_retained_idle_listener_is_observed_without_stopping(self):
        import psutil
        self.manager.operation={'status':'failed','target':'hidream','preserved_pid':900}
        child=self.process(pid=900)
        with patch.object(psutil,'Process',return_value=child),patch.object(self.manager,'matches_configured_process',return_value=True), \
             patch.object(self.manager,'process',return_value=child),patch.object(self.manager,'request',return_value=IDLE) as request:
            self.manager._check_retained_startup()
        request.assert_called_once();child.terminate.assert_not_called()
    def test_retained_startup_missing_pid_and_denied_inspection(self):
        import psutil
        self.manager.operation={'status':'failed','target':'hidream','pid':900}
        with patch.object(psutil,'Process',side_effect=psutil.NoSuchProcess(900)):self.manager._check_retained_startup()
        with patch.object(psutil,'Process',side_effect=psutil.AccessDenied(900)):
            with self.assertRaisesRegex(ValueError,'Cannot inspect'):self.manager._check_retained_startup()
    def test_ready_endpoint_must_belong_to_launched_process(self):
        child=self.process(pid=900);child.poll.return_value=None
        self.manager.operation={'id':'ownership','status':'running'};self.manager.busy=True
        with patch.object(self.manager,'request',side_effect=lambda p,r,*a:HEALTH if r=='/system_stats' else IDLE), \
             patch.object(self.manager,'process',return_value=None),patch('backends.subprocess.Popen',return_value=child), \
             patch.object(self.manager,'activate') as activate:
            self.manager._switch('hidream')
        activate.assert_not_called();child.terminate.assert_not_called()
        self.assertEqual(self.manager.operation['status'],'failed');self.assertEqual(self.manager.operation['preserved_pid'],900)
    def test_new_launcher_success_requires_matching_idle_listener(self):
        child=self.process(pid=900);child.poll.return_value=None;observations=0
        def observe(profile):
            nonlocal observations
            if profile['id']!='hidream':return None
            observations+=1;return child if observations>=3 else None
        self.manager.operation={'id':'success','status':'running'};self.manager.busy=True
        with patch.object(self.manager,'request',side_effect=lambda p,r,*a:HEALTH if r=='/system_stats' else IDLE), \
             patch.object(self.manager,'process',side_effect=observe),patch('backends.subprocess.Popen',return_value=child) as launch, \
             patch.object(self.manager,'activate') as activate:
            self.manager._switch('hidream')
        launch.assert_called_once();activate.assert_called_once_with('hidream');child.terminate.assert_not_called()
        self.assertEqual(self.manager.operation['status'],'completed');self.assertFalse(self.manager.busy)
    def test_real_loopback_http_request_limits_and_redirect_refusal(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path=='/redirect':
                    self.send_response(302);self.send_header('Location','/queue');self.end_headers();return
                body=(b'x'*(1024*1024+1) if self.path=='/large' else json.dumps(IDLE).encode())
                self.send_response(200);self.end_headers()
                try:self.wfile.write(body)
                except (BrokenPipeError,ConnectionResetError):pass
            def log_message(self,*a):pass
        http=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        try:
            profile={'url':f'http://127.0.0.1:{http.server_port}'}
            self.assertEqual(self.manager.request(profile,'/queue'),IDLE)
            with self.assertRaises(OSError) as caught:self.manager.request(profile,'/redirect')
            self.addCleanup(caught.exception.close)
            self.assertTrue(caught.exception.closed)
            with self.assertRaisesRegex(ValueError,'observation limit'):self.manager.request(profile,'/large')
        finally:http.shutdown();http.server_close();thread.join(2)


if __name__=='__main__':unittest.main()
