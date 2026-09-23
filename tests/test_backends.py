import errno
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError
from test_server import server, FakeStudio, GRAPH, PRESET
from backends import PRIMARY_RESERVE_VRAM, BackendManager
import gpu_memory
from runtime_recovery import RuntimeRecovery


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

    def test_opt_in_auto_reserve_covers_what_other_processes_hold_on_the_gpu(self):
        # "auto" (opt-in since the Krea 2 measurement, docs/RUNTIME-PRECONDITIONS.md section 8):
        # 3.02 GiB held elsewhere + the 0.7 GiB margin -> 3.8.
        self.assertEqual(self.studio.backends.profiles['primary']['reserve_vram'],0.6);self.assertEqual(PRIMARY_RESERVE_VRAM,0.6)
        profile=dict(self.studio.backends.profiles['primary'],reserve_vram='auto')
        reading={'adapters':{'0x0_0x102fb_0':{2304:{'dedicated_bytes':2282*2**20,'shared_bytes':0},30868:{'dedicated_bytes':811*2**20,'shared_bytes':0}}},'unknown_reason':None}
        with patch('backends.gpu_memory.read',return_value=reading):argv=BackendManager.primary_argv(profile)
        self.assertEqual(argv.count('--reserve-vram'),1)
        self.assertEqual(argv[argv.index('--reserve-vram')+1],'3.8')
        self.assertTrue(BackendManager.matches_configured_process(profile,profile['python'],argv,profile['root']))
        with patch('backends.gpu_memory.read',return_value={'adapters':None,'unknown_reason':'counters unavailable'}):argv=BackendManager.primary_argv(profile)
        self.assertEqual(argv[argv.index('--reserve-vram')+1],format(gpu_memory.FALLBACK_GIB,'g'))

    def test_configured_primary_reserve_is_used_verbatim_and_validated(self):
        profile=dict(self.studio.backends.profiles['primary'],reserve_vram=BackendManager.configured_reserve('0.6'))
        with patch('backends.gpu_memory.read') as read:argv=BackendManager.primary_argv(profile)
        read.assert_not_called();self.assertEqual(argv[argv.index('--reserve-vram')+1],'0.6')
        for bad in (True,-1,13,'many',float('nan'),None,[1]):
            with self.subTest(bad=bad),self.assertRaises(ValueError):BackendManager.configured_reserve(bad)

    def test_primary_pinned_memory_flag_is_explicit_and_default_off(self):
        profile=self.studio.backends.profiles['primary']
        self.assertNotIn('--disable-pinned-memory',BackendManager.primary_argv(profile))
        profile['disable_pinned_memory']=True
        self.assertIn('--disable-pinned-memory',BackendManager.primary_argv(profile))

    def test_default_primary_reserve_is_the_measured_fixed_0_6(self):
        profile=self.studio.backends.profiles['primary']
        with patch('backends.gpu_memory.read') as read:argv=BackendManager.primary_argv(profile)
        read.assert_not_called();self.assertEqual(argv[argv.index('--reserve-vram')+1],'0.6')

    def test_switch_actually_launches_primary_with_the_reserve_flag(self):
        # primary_argv alone would stay green if the call site were reverted; assert what Popen receives.
        manager=self.studio.backends;manager.profiles['primary']['pidfile']=str(self.root/'comfyui.pid');manager.profiles['primary']['reserve_vram']='auto'
        manager.operation={'id':'test','target':'primary','status':'running','started_at':0.0,'message':'test'}
        launched=MagicMock(pid=4321);launched.poll.return_value=1
        reserve={'reserve_gib':3.8,'basis':'measured','others_bytes':3*2**30,'adapter':'a','unknown_reason':None}
        with patch.object(manager,'available',return_value=True),patch.object(manager,'_idle',return_value=True), \
             patch.object(manager,'process',return_value=None),patch.object(manager,'configured_processes',return_value=[]), \
             patch('backends.gpu_memory.launch_reserve_gib',return_value=reserve), \
             patch('backends.subprocess.Popen',return_value=launched) as popen:
            manager._switch('primary')
        argv=popen.call_args.args[0]
        self.assertEqual(argv[argv.index('--reserve-vram')+1],'3.8')
        self.assertEqual(manager.operation['launch_reserve']['reserve_gib'],3.8);self.assertEqual(manager.snapshot()['last_launch_reserve']['basis'],'measured')
        self.assertEqual(argv[:3],[manager.profiles['primary']['python'],'-s',manager.profiles['primary']['entry']])
        self.assertEqual(manager.operation['status'],'failed');self.assertFalse(manager.busy)

    def test_local_uncertain_and_external_queue_each_prevent_switch(self):
        manager=self.studio.backends
        with patch.object(manager,'available',return_value=True),patch.object(manager,'configured_processes',return_value=[]), \
             patch.object(manager,'request',return_value={'queue_running':[],'queue_pending':[]}):
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

    def test_prelisten_protected_python_candidate_blocks_recovery_launch(self):
        import psutil
        manager=self.studio.backends;profile=manager.profiles['primary'];candidate=MagicMock()
        candidate.name.return_value=Path(profile['python']).name
        candidate.exe.side_effect=psutil.AccessDenied(pid=17)
        recovery=RuntimeRecovery(self.studio);launch=MagicMock()
        with patch('psutil.process_iter',return_value=[candidate]),patch.object(manager,'request',side_effect=URLError(OSError(errno.ECONNREFUSED,'refused'))), \
             patch.object(manager,'process',return_value=None),patch.object(manager,'launch_recovery',launch):
            result=recovery.tick()
        self.assertEqual(result['status'],'foreign-or-ambiguous-listener')
        launch.assert_not_called()

    def test_unrelated_protected_process_is_not_a_configured_launcher_candidate(self):
        import psutil
        manager=self.studio.backends;candidate=MagicMock();candidate.name.return_value='node.exe';candidate.exe.side_effect=psutil.AccessDenied(pid=18)
        with patch('psutil.process_iter',return_value=[candidate]):
            self.assertEqual(manager.configured_processes(manager.profiles['primary']),[])
        candidate.exe.assert_not_called()

    def test_process_without_a_readable_name_remains_ambiguous(self):
        import psutil
        manager=self.studio.backends;candidate=MagicMock();candidate.name.side_effect=psutil.AccessDenied(pid=18)
        with patch('psutil.process_iter',return_value=[candidate]):
            with self.assertRaisesRegex(ValueError,'identity could not be read'):manager.configured_processes(manager.profiles['primary'])

    def test_blank_psutil_name_uses_windows_name_fallback_to_exclude_known_nonpython(self):
        manager=self.studio.backends;candidate=MagicMock();candidate.pid=284;candidate.name.return_value='';candidate.exe.side_effect=AssertionError('non-Python must not need identity inspection')
        with patch('psutil.process_iter',return_value=[candidate]),patch.object(manager,'windows_process_name',return_value='Secure System') as fallback:
            self.assertEqual(manager.configured_processes(manager.profiles['primary']),[])
        fallback.assert_called_once_with(284);candidate.exe.assert_not_called()

    def test_blank_psutil_name_fallback_python_still_blocks_protected_identity(self):
        import psutil
        manager=self.studio.backends;candidate=MagicMock();candidate.pid=20;candidate.name.return_value='';candidate.exe.side_effect=psutil.AccessDenied(pid=20)
        with patch('psutil.process_iter',return_value=[candidate]),patch.object(manager,'windows_process_name',return_value='python'):
            with self.assertRaisesRegex(ValueError,'candidate configured Python'):manager.configured_processes(manager.profiles['primary'])

    def test_blank_psutil_name_without_windows_fallback_remains_ambiguous(self):
        manager=self.studio.backends;candidate=MagicMock();candidate.pid=21;candidate.name.return_value=''
        with patch('psutil.process_iter',return_value=[candidate]),patch.object(manager,'windows_process_name',return_value=None):
            with self.assertRaisesRegex(ValueError,'process name could not be read'):manager.configured_processes(manager.profiles['primary'])

    def test_windows_name_fallback_is_hidden_bounded_and_uses_only_observed_pid(self):
        result=MagicMock(returncode=0,stdout='Secure System\n')
        with patch('backends.os.name','nt'),patch('backends.subprocess.run',return_value=result) as run:
            self.assertEqual(BackendManager.windows_process_name(284),'Secure System')
        command=run.call_args.args[0]
        self.assertEqual(command[:4],['powershell.exe','-NoProfile','-NonInteractive','-Command'])
        self.assertIn('GetProcessById(284)',command[4])
        self.assertEqual(run.call_args.kwargs['timeout'],2)
        self.assertEqual(run.call_args.kwargs['creationflags'],getattr(__import__('subprocess'),'CREATE_NO_WINDOW',0))

    def test_vanished_process_does_not_block_prelisten_scan(self):
        import psutil
        manager=self.studio.backends;candidate=MagicMock();candidate.name.side_effect=psutil.NoSuchProcess(pid=19)
        with patch('psutil.process_iter',return_value=[candidate]):
            self.assertEqual(manager.configured_processes(manager.profiles['primary']),[])
