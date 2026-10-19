"""Shared switch ownership, using small state files and inert backend doubles."""
from contextlib import ExitStack, contextmanager
import copy
import errno
import json
import multiprocessing
import os
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.error import URLError

import psutil

sys.path.insert(0, str(Path(__file__).parents[1] / 'app'))
from backends import BackendManager
from runtime_recovery import RuntimeRecovery
import backend_state


def hold_writer(path, ready, release, crash=False):
    with backend_state.writer_lock(Path(path)):
        ready.set()
        if not release.wait(10):os._exit(72)
        if crash:os._exit(73)


def race_writer(path, ready, start, results, action):
    store=backend_state.Store(path);expected=store.read();ready.put(True)
    if not start.wait(10):os._exit(72)
    try:
        if action=='reserve':
            operation={'id':str(os.getpid()),'owner':backend_state.current_owner(),'target':'primary','status':'running','phase':'checking'}
            store.reserve(expected,operation)
        else:
            with patch.object(backend_state,'owner_status',return_value='absent'):store.reconcile(expected)
        results.put('published')
    except backend_state.StateError as exc:results.put(type(exc).__name__)


class BackendStateIOTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.path=Path(self.temporary.name).resolve()/'backend-state.json';self.store=backend_state.Store(self.path)

    def operation(self):
        return {'id':'operation-a','owner':SharedBackendStateTests.owner(),'target':'primary','status':'running','phase':'checking'}

    def initial(self):
        operation=self.operation();self.path.write_text(json.dumps({'active':'primary','operation':operation}))
        return self.store.read(),{'id':operation['id'],'owner':operation['owner']}

    def test_another_process_cannot_enter_the_held_writer_lock(self):
        context=multiprocessing.get_context('spawn');ready=context.Event();release=context.Event()
        process=context.Process(target=hold_writer,args=(str(self.path),ready,release))
        process.start()
        try:
            self.assertTrue(ready.wait(5),'inert lock holder did not start')
            with self.assertRaisesRegex(backend_state.StateError,'busy'):
                with backend_state.writer_lock(self.path,timeout=0.03):self.fail('second writer entered')
        finally:
            release.set();process.join(5)
            if process.is_alive():process.terminate();process.join(5)
        self.assertEqual(process.exitcode,0)

    def test_process_crash_releases_ownership_without_removing_lock_file(self):
        context=multiprocessing.get_context('spawn');ready=context.Event();release=context.Event()
        process=context.Process(target=hold_writer,args=(str(self.path),ready,release,True));process.start()
        try:
            self.assertTrue(ready.wait(5));lock=self.path.with_name(self.path.name+'.lock');identity=lock.stat().st_ino
            release.set();process.join(5);self.assertEqual(process.exitcode,73)
            with backend_state.writer_lock(self.path,timeout=0):self.assertEqual(lock.stat().st_ino,identity)
        finally:
            release.set()
            if process.is_alive():process.terminate();process.join(5)

    def test_two_real_writers_or_reconcilers_publish_only_one_transition(self):
        context=multiprocessing.get_context('spawn')
        for action in ('reserve','reconcile'):
            with self.subTest(action=action):
                self.path.unlink(missing_ok=True)
                if action=='reconcile':self.initial()
                ready=context.Queue();results=context.Queue();start=context.Event()
                processes=[context.Process(target=race_writer,args=(str(self.path),ready,start,results,action)) for _ in range(2)]
                for process in processes:process.start()
                try:
                    for _ in processes:self.assertTrue(ready.get(timeout=5))
                    start.set();outcomes=[results.get(timeout=5) for _ in processes]
                    self.assertCountEqual(outcomes,['published','StateConflict'])
                    landed=self.store.read().value;self.assertEqual(landed['revision'],1)
                    self.assertEqual(landed['operation']['status'],'running' if action=='reserve' else 'interrupted')
                finally:
                    start.set()
                    for process in processes:
                        process.join(5)
                        if process.is_alive():process.terminate();process.join(5)
                    ready.close();results.close()
                self.assertTrue(all(process.exitcode==0 for process in processes))

    def test_replacement_while_reconciler_waits_is_not_overwritten(self):
        expected,_=self.initial();replacement=copy.deepcopy(expected.value);replacement['operation']['id']='operation-b'
        writer_lock=backend_state.writer_lock
        def replaced(*args,**kwargs):
            self.path.write_text(json.dumps(replacement));return writer_lock(*args,**kwargs)
        with patch.object(backend_state,'writer_lock',side_effect=replaced),patch.object(backend_state,'owner_status',return_value='absent'):
            with self.assertRaises(backend_state.StateConflict):self.store.reconcile(expected)
        self.assertEqual(self.store.read().value,replacement)

    def test_progress_changed_during_flush_is_not_overwritten_even_for_same_operation(self):
        expected,token=self.initial();replacement=copy.deepcopy(expected.value);replacement['revision']=7
        replacement['operation']['message']='newer progress';flushed=os.fsync
        def changed(descriptor):
            flushed(descriptor);self.path.write_text(json.dumps(replacement))
        operation=dict(expected.value['operation'],message='stale progress')
        with patch.object(backend_state.os,'fsync',side_effect=changed):
            with self.assertRaises(backend_state.StateConflict):self.store.update(expected,token,operation)
        self.assertEqual(self.store.read().value,replacement)

    def test_failed_flush_preserves_original_and_lost_replace_reply_is_not_replayed(self):
        expected,token=self.initial();raw=self.path.read_bytes();operation=dict(expected.value['operation'],message='updated')
        with patch.object(backend_state.os,'fsync',side_effect=OSError('inert full disk')):
            with self.assertRaises(backend_state.StateError):self.store.update(expected,token,operation)
        self.assertEqual(self.path.read_bytes(),raw)
        replace=backend_state.file_replace.replace;calls=[]
        def lost_reply(source,target):
            calls.append(True);replace(source,target);raise OSError('inert lost acknowledgement')
        with patch.object(backend_state.file_replace,'replace',side_effect=lost_reply):
            with self.assertRaises(backend_state.StateUnconfirmed):self.store.update(expected,token,operation)
        self.assertEqual(calls,[True]);self.assertEqual(self.store.read().value['operation']['message'],'updated')
        self.assertEqual(list(self.path.parent.glob('.backend-state-*.tmp')),[])

    def test_changed_lock_cannot_authorize_publication(self):
        expected,token=self.initial();flushed=os.fsync;refused=[]
        def changed(descriptor):
            flushed(descriptor);lock=self.path.with_name(self.path.name+'.lock')
            try:lock.unlink()
            except PermissionError:refused.append(True);return
            lock.write_bytes(b'new lock')
        with patch.object(backend_state.os,'fsync',side_effect=changed):
            try:self.store.update(expected,token,dict(expected.value['operation'],message='updated'))
            except backend_state.StateError:self.assertEqual(self.store.read().value,expected.value)
            else:self.assertEqual(os.name,'nt');self.assertTrue(refused)

    def test_windows_primitive_is_nonblocking_and_unlocks_the_same_byte(self):
        calls=[]
        fake=SimpleNamespace(LK_NBLCK=7,LK_UNLCK=9,locking=lambda fd,mode,size:calls.append((mode,size,os.lseek(fd,0,os.SEEK_CUR))))
        with patch.object(backend_state,'WINDOWS',True),patch.dict(sys.modules,{'msvcrt':fake}):
            with backend_state.writer_lock(self.path,timeout=0):pass
        self.assertEqual(calls,[(7,1,0),(9,1,0)])
        fake.locking=Mock(side_effect=OSError(errno.EACCES,'held'))
        with patch.object(backend_state,'WINDOWS',True),patch.dict(sys.modules,{'msvcrt':fake}):
            with self.assertRaisesRegex(backend_state.StateError,'busy'):
                with backend_state.writer_lock(self.path,timeout=0):self.fail('entered held Windows lock')
        self.assertEqual(fake.locking.call_count,1)

    def test_malformed_owner_never_becomes_absence(self):
        for field,value in (('pid',True),('pid',-1),('created_at',float('nan')),('created_at',10**1000),('version',True),('instance_id','')):
            owner=self.operation()['owner'];owner[field]=value
            with self.subTest(field=field),patch('backend_state.psutil.Process') as process:
                self.assertEqual(backend_state.owner_status(owner),'unknown');process.assert_not_called()

    def test_unreadable_duplicate_or_invalid_state_is_not_first_run(self):
        self.assertIsNone(self.store.read().identity)
        for raw in ('','{bad','[]','{}','{"active":""}','{"active":"primary","active":"hidream"}','{"operation":false}','{"revision":true}','{"operation":{"owner":{"created_at":NaN}}}'):
            with self.subTest(raw=raw):
                self.path.write_text(raw)
                with self.assertRaises(backend_state.StateError):self.store.read()

    def test_missing_psutil_allows_module_import_but_never_confirms_an_owner(self):
        name='backend_state_without_psutil'
        spec=importlib.util.spec_from_file_location(name,Path(backend_state.__file__))
        isolated=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'psutil':None,name:isolated}):spec.loader.exec_module(isolated)
        self.assertIsNone(isolated.current_owner())
        self.assertEqual(isolated.owner_status(self.operation()['owner']),'unknown')
        self.initial();raw=self.path.read_bytes();store=isolated.Store(self.path);expected=store.read()
        self.assertEqual(store.reconcile(expected).value,expected.value)
        self.assertFalse(isolated.resolution_allowed(expected,isolated.current_owner()))
        with self.assertRaisesRegex(isolated.StateError,'identify'):
            store.reserve(expected,dict(self.operation(),owner=isolated.current_owner()))
        self.assertEqual(self.path.read_bytes(),raw)


class SharedBackendStateTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        (self.root / '.runtime').mkdir()
        self.path = self.root / '.runtime/backend-state.json'
        self.thread = self.stack.enter_context(patch('backends.threading.Thread'))
        self.launch = self.stack.enter_context(patch('backends.subprocess.Popen'))
        self.launch.return_value.pid = 901; self.launch.return_value.poll.return_value = 1
        self.manager = self.make_manager()

    def make_manager(self):
        def write(path, value):
            path.parent.mkdir(parents=True, exist_ok=True)
            pending = path.with_suffix('.tmp'); pending.write_text(json.dumps(value)); pending.replace(path)
        studio = SimpleNamespace(root=self.root, comfy_root=self.root/'comfy', config={}, jobs={},
                                 lock=threading.RLock(), production=SimpleNamespace(list=lambda: []),
                                 _write_json_atomic=write)
        manager = BackendManager(studio); studio.backends = manager
        return manager

    @staticmethod
    def owner(pid=987654321):
        return {'version': 1, 'pid': pid, 'created_at': 123.0, 'instance_id': 'other-studio'}

    def record(self, **operation):
        value = {'active': 'primary', 'operation': dict(id='switch-a', target='hidream', status='running',
                 started_at=1.0, owner=self.owner(), phase='checking', **operation)}
        self.path.write_text(json.dumps(value)); return value

    @contextmanager
    def owner_probe(self, result):
        process = psutil.Process
        def observe(pid=None, *args, **kwargs):
            if pid == 987654321:
                if isinstance(result, Exception): raise result
                return SimpleNamespace(create_time=lambda: result)
            return process(pid, *args, **kwargs)
        with patch('psutil.Process', side_effect=observe): yield

    @contextmanager
    def inert(self, manager):
        with ExitStack() as stack:
            for method, value in (('available', True), ('_idle', None), ('_stopped_results', None),
                                  ('process', None), ('configured_processes', [])):
                stack.enter_context(patch.object(manager, method, return_value=value))
            stack.enter_context(patch.object(manager, 'request', return_value={'system': {'ready': True}, 'devices': []}))
            yield

    def test_live_foreign_owner_is_displayed_and_cannot_be_replaced(self):
        saved = self.record(); raw = self.path.read_bytes()
        with self.owner_probe(123.0): manager = self.make_manager()
        self.assertEqual(manager.operation['status'], 'running')
        with self.inert(manager), self.assertRaisesRegex(ValueError, 'switch|owner'):
            manager.switch('primary')
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertEqual(manager.operation, saved['operation'])
        self.thread.assert_not_called(); self.launch.assert_not_called()

    def test_two_studios_cannot_reserve_the_same_idle_state(self):
        other = self.make_manager()
        with self.inert(self.manager): self.manager.switch('hidream')
        reserved = self.path.read_bytes()
        with self.inert(other), self.assertRaisesRegex(ValueError, 'switch|changed|owner'):
            other.switch('primary')
        self.assertEqual(self.path.read_bytes(), reserved)
        self.assertEqual(self.thread.call_count, 1)

    def test_explicit_retry_after_a_reservation_conflict_reads_the_completed_winner(self):
        reserve=self.manager._state.reserve
        def race(expected,operation):
            self.path.write_text(json.dumps({'active':'primary','operation':{'id':'winner','status':'completed','target':'primary'}}))
            return reserve(expected,operation)
        with self.inert(self.manager),patch.object(self.manager._state,'reserve',side_effect=race):
            with self.assertRaises(backend_state.StateConflict):self.manager.switch('hidream')
        self.thread.assert_not_called()
        with self.inert(self.manager):self.manager.switch('hidream')
        self.assertEqual(self.thread.call_count,1)
        self.assertEqual(json.loads(self.path.read_text())['operation']['owner'],self.manager._owner)

    def test_clean_reservation_failure_allows_a_fresh_explicit_retry(self):
        writer_lock=backend_state.writer_lock
        for fault in ('writer-lock','temporary-flush'):
            with self.subTest(fault=fault):
                self.path.write_text(json.dumps({'active':'primary','operation':{'id':'settled','status':'completed','target':'primary'}}))
                manager=self.make_manager();raw=self.path.read_bytes();self.thread.reset_mock()
                read=manager._state.read
                def observed():
                    self.assertTrue(manager.studio.lock._is_owned(),'Reservation failure is re-observed under the Studio lock')
                    return read()
                with ExitStack() as faults:
                    if fault=='writer-lock':
                        faults.enter_context(writer_lock(self.path))
                        faults.enter_context(patch.object(backend_state,'writer_lock',side_effect=lambda path:writer_lock(path,timeout=0)))
                    else:faults.enter_context(patch.object(backend_state.os,'fsync',side_effect=OSError('inert temporary flush failure')))
                    with self.inert(manager),patch.object(manager._state,'read',side_effect=observed), \
                         patch.object(backend_state.file_replace,'replace') as replace:
                        with self.assertRaises(backend_state.StateError) as failure:manager.switch('hidream')
                        self.assertNotIsInstance(failure.exception,backend_state.StateUnconfirmed)
                        replace.assert_not_called()
                self.assertEqual(self.path.read_bytes(),raw);self.thread.assert_not_called();self.launch.assert_not_called()
                self.assertFalse(manager.busy);self.assertIsNone(manager.state_issue)
                self.assertIsNone(manager._owned_operation);self.assertIsNone(manager._uncertain_publication)
                expected=manager._state_snapshot
                with manager.studio.lock:manager.require_work_admission()
                self.assertIs(manager._state_snapshot,expected,'Work admission cannot adopt a switch worker snapshot')
                with self.inert(manager):manager.switch('hidream')
                self.assertEqual(self.thread.call_count,1)
                self.assertEqual(json.loads(self.path.read_text())['operation']['owner'],manager._owner)
        self.launch.assert_not_called()

    def test_clean_reservation_followup_read_failure_does_not_latch_after_recovery(self):
        manager=self.manager;read=manager._state.read;failed=[]
        def flush(descriptor):
            failed.append(True);raise OSError('inert temporary flush failure')
        def observed():
            self.assertTrue(manager.studio.lock._is_owned())
            if failed:raise backend_state.StateError('inert followup read unavailable')
            return read()
        with self.inert(manager),patch.object(backend_state.os,'fsync',side_effect=flush), \
             patch.object(manager._state,'read',side_effect=observed),patch.object(backend_state.file_replace,'replace') as replace:
            with self.assertRaisesRegex(backend_state.StateError,'flush failure'):manager.switch('hidream')
            self.assertIsNone(manager._state_snapshot)
            with manager.studio.lock:
                for admit in (manager._admit_shared,manager.require_work_admission):
                    with self.assertRaisesRegex(backend_state.StateError,'followup read unavailable'):admit()
            replace.assert_not_called()
        self.assertFalse(self.path.exists());self.thread.assert_not_called();self.launch.assert_not_called()
        self.assertIsNone(manager.state_issue);self.assertIsNone(manager._uncertain_publication)
        with manager.studio.lock:manager.require_work_admission()
        self.assertIsNone(manager._state_snapshot,'Pure work admission must not install a new expected record')
        with self.inert(manager):manager.switch('hidream')
        self.assertEqual(self.thread.call_count,1);self.assertEqual(json.loads(self.path.read_text())['operation']['owner'],manager._owner)

    def test_clean_reservation_failure_does_not_bypass_new_shared_blockers(self):
        manager=self.manager
        with self.inert(manager),patch.object(backend_state.os,'fsync',side_effect=OSError('inert temporary flush failure')):
            with self.assertRaises(backend_state.StateError):manager.switch('hidream')
        self.assertIsNone(manager.state_issue)
        cases=[('unreadable','{invalid'),
               ('unknown-owner',{'active':'primary','operation':{'status':'running','owner':{'version':99}}}),
               ('legacy',{'active':'primary','operation':{'status':'running'}}),
               ('mismatch',{'active':'hidream','operation':{'status':'completed','target':'hidream'}})]
        for name,value in cases:
            with self.subTest(name=name):
                self.path.write_text(value if isinstance(value,str) else json.dumps(value));raw=self.path.read_bytes()
                with manager.studio.lock,self.assertRaises(backend_state.StateError):manager.require_work_admission()
                if name!='mismatch':
                    with self.inert(manager),self.assertRaises(backend_state.StateError):manager.switch('hidream')
                self.assertEqual(self.path.read_bytes(),raw)
        self.thread.assert_not_called();self.launch.assert_not_called()

    def test_unknown_local_owner_reservation_failure_retains_its_hold(self):
        manager=self.manager;manager._owner=None
        with self.inert(manager),self.assertRaisesRegex(backend_state.StateError,'identify'):manager.switch('hidream')
        self.assertIn('identify',manager.state_issue)
        with manager.studio.lock:
            for admit in (manager._admit_shared,manager.require_work_admission):
                with self.assertRaisesRegex(backend_state.StateError,'identify'):admit()
        self.assertFalse(self.path.exists());self.thread.assert_not_called();self.launch.assert_not_called()

    def test_dead_owner_before_launch_is_reconciled_without_runtime_actions(self):
        saved = self.record(); saved['active'] = 'hidream'
        saved['operation']['stopped_processes'] = [{'pid': 34, 'created_at': 5}]
        self.path.write_text(json.dumps(saved))
        with self.owner_probe(psutil.NoSuchProcess(987654321)): manager = self.make_manager()
        landed = json.loads(self.path.read_text())
        self.assertEqual(landed['active'], 'hidream')
        self.assertEqual(landed['operation']['status'], 'interrupted')
        self.assertEqual(landed['operation']['stopped_processes'], saved['operation']['stopped_processes'])
        self.assertEqual(landed['operation']['owner'], saved['operation']['owner'])
        self.assertEqual(landed['operation']['started_at'], 1.0)
        self.assertFalse(landed['operation']['inspection_required'])
        self.assertIn('reconciled_at', landed['operation'])
        self.assertEqual(manager.operation, landed['operation'])
        self.thread.assert_not_called(); self.launch.assert_not_called()

    def test_launch_intent_survives_dead_owner_reconciliation_and_blocks_recovery(self):
        saved = self.record(); saved['operation'].update(phase='launch-intent', log_directory='retained-log')
        self.path.write_text(json.dumps(saved))
        with self.owner_probe(psutil.NoSuchProcess(987654321)): manager = self.make_manager()
        landed = json.loads(self.path.read_text())
        self.assertEqual(landed['operation']['status'], 'interrupted')
        self.assertTrue(landed['operation']['inspection_required'])
        self.assertEqual(landed['operation']['log_directory'], 'retained-log')
        manager.studio.config.update(runtime_auto_recover=True, runtime_recovery_autostart=False)
        recovery = RuntimeRecovery(manager.studio)
        with self.inert(manager), patch.object(manager, 'request', side_effect=URLError(ConnectionRefusedError(errno.ECONNREFUSED, 'fixture'))), \
             patch.object(manager, 'launch_recovery') as launch:
            result = recovery.tick()
        self.assertEqual(result['status'], 'other-backend-active'); launch.assert_not_called()
        self.assertIn('inspection', result['message'].lower())
        with self.inert(manager), self.assertRaisesRegex(ValueError, 'inspection'):
            manager.switch('primary')

    def test_legacy_ownerless_record_remains_unchanged_and_blocks_switch(self):
        saved = self.record(); saved['operation'].pop('owner')
        self.path.write_text(json.dumps(saved)); raw = self.path.read_bytes()
        manager = self.make_manager()
        self.assertEqual(manager.operation['status'], 'running')
        with self.inert(manager), self.assertRaisesRegex(ValueError, 'owner|legacy'):
            manager.switch('hidream')
        self.assertEqual(self.path.read_bytes(), raw); self.thread.assert_not_called()

    def test_unreadable_state_blocks_switch_and_recovery(self):
        self.path.write_text('{invalid'); manager = self.make_manager()
        with self.inert(manager), self.assertRaisesRegex(ValueError, 'state|read'):
            manager.switch('hidream')
        manager.studio.config.update(runtime_auto_recover=True, runtime_recovery_autostart=False)
        recovery = RuntimeRecovery(manager.studio)
        with self.inert(manager), patch.object(manager, 'request', side_effect=URLError(ConnectionRefusedError(errno.ECONNREFUSED, 'fixture'))), \
             patch.object(manager, 'launch_recovery') as launch:
            self.assertEqual(recovery.tick()['status'], 'other-backend-active')
        launch.assert_not_called(); self.assertEqual(self.path.read_text(), '{invalid')

    def test_unknown_or_reused_owner_identity_is_preserved(self):
        for result in (psutil.AccessDenied(987654321), 456.0, float('nan')):
            with self.subTest(result=result):
                self.record(); raw = self.path.read_bytes()
                with self.owner_probe(result): manager = self.make_manager()
                self.assertEqual(manager.operation['status'], 'running')
                self.assertEqual(self.path.read_bytes(), raw)

    def test_unreadable_observer_identity_cannot_reconcile_a_recorded_owner(self):
        self.record(); raw=self.path.read_bytes()
        with patch.object(backend_state,'current_owner',return_value=None),self.owner_probe(psutil.NoSuchProcess(987654321)):
            manager=self.make_manager()
            with self.inert(manager):self.assertFalse(manager.snapshot()['shared_state']['resolvable'])
            with self.assertRaisesRegex(ValueError,'live|unverified'):
                manager.resolve_switch_record(self.acknowledgement())
        self.assertEqual(self.path.read_bytes(),raw)
        self.assertEqual(manager.operation['status'],'running')
        self.thread.assert_not_called();self.launch.assert_not_called()

    def test_stale_worker_progress_does_not_overwrite_or_launch(self):
        with self.inert(self.manager): self.manager.switch('hidream')
        replacement = self.record(); raw = self.path.read_bytes()
        with self.inert(self.manager): self.manager._switch('hidream')
        self.assertEqual(self.path.read_bytes(), raw)
        self.launch.assert_not_called(); self.assertFalse(self.manager.busy)

    def test_stale_worker_failure_does_not_overwrite_newer_operation(self):
        with self.inert(self.manager): self.manager.switch('hidream')
        self.record(); raw = self.path.read_bytes()
        with patch.object(self.manager, 'available', side_effect=ValueError('inert preflight failure')):
            self.manager._switch('hidream')
        self.assertEqual(self.path.read_bytes(), raw); self.launch.assert_not_called()

    def test_launch_intent_is_durable_before_process_creation(self):
        with self.inert(self.manager): self.manager.switch('hidream')
        observed = []
        def launch(*args, **kwargs):
            observed.append(json.loads(self.path.read_text())['operation'])
            raise OSError('inert creation failure')
        self.launch.side_effect = launch
        with self.inert(self.manager): self.manager._switch('hidream')
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0].get('phase'), 'launch-intent')
        self.assertEqual(observed[0]['owner']['pid'], os.getpid())
        self.assertTrue(json.loads(self.path.read_text())['operation']['inspection_required'])

    def acknowledgement(self):
        return {'expected_sha256':hashlib.sha256(self.path.read_bytes()).hexdigest(),
                'acknowledge_studios_closed':True,'acknowledge_runtimes_inspected':True}

    def test_legacy_resolution_is_explicit_preserves_evidence_and_allows_later_switch(self):
        saved=self.record();saved['operation'].pop('owner');saved['operation']['log_directory']='keep-this-log'
        self.path.write_text(json.dumps(saved));manager=self.make_manager()
        with self.inert(manager): result=manager.resolve_switch_record(self.acknowledgement())
        resolved=json.loads(self.path.read_text())
        self.assertEqual(resolved['active'],saved['active'])
        self.assertEqual(resolved['operation']['log_directory'],'keep-this-log')
        self.assertEqual(resolved['operation']['status'],'interrupted')
        self.assertTrue(resolved['operation']['resolution']['acknowledge_runtimes_inspected'])
        self.assertFalse(result['shared_state']['resolvable'])
        self.thread.assert_not_called();self.launch.assert_not_called()
        with self.inert(manager):manager.switch('hidream')
        self.assertEqual(json.loads(self.path.read_text())['operation']['owner']['pid'],os.getpid())

    def test_resolution_requires_both_exact_acknowledgements(self):
        saved=self.record();saved['operation'].pop('owner');self.path.write_text(json.dumps(saved))
        manager=self.make_manager();raw=self.path.read_bytes()
        for field in ('acknowledge_studios_closed','acknowledge_runtimes_inspected'):
            for value in (False,'true',1,None):
                command=self.acknowledgement();command[field]=value
                with self.subTest(field=field,value=value),self.assertRaisesRegex(ValueError,'Confirm'):
                    manager.resolve_switch_record(command)
                self.assertEqual(self.path.read_bytes(),raw)

    def test_live_or_unknown_recorded_owner_cannot_be_resolved_by_acknowledgement(self):
        for result in (123.0,456.0,psutil.AccessDenied(987654321)):
            with self.subTest(result=result),self.owner_probe(result):
                self.record();manager=self.make_manager();raw=self.path.read_bytes()
                with self.inert(manager):self.assertFalse(manager.snapshot()['shared_state']['resolvable'])
                with self.assertRaisesRegex(ValueError,'live|unverified'):
                    manager.resolve_switch_record(self.acknowledgement())
                self.assertEqual(self.path.read_bytes(),raw)

    def test_stale_operator_acknowledgement_does_not_resolve_replacement(self):
        saved=self.record();saved['operation'].pop('owner');self.path.write_text(json.dumps(saved))
        command=self.acknowledgement();saved['operation']['id']='switch-b'
        self.path.write_text(json.dumps(saved));raw=self.path.read_bytes();manager=self.make_manager()
        with self.assertRaisesRegex(ValueError,'changed'):manager.resolve_switch_record(command)
        self.assertEqual(self.path.read_bytes(),raw)

    def test_unconfirmed_own_reservation_can_be_resolved_only_after_the_worker_is_inactive(self):
        replace=backend_state.file_replace.replace
        def lost_reply(source,target):
            replace(source,target);raise OSError('inert lost acknowledgement')
        with self.inert(self.manager),patch.object(backend_state.file_replace,'replace',side_effect=lost_reply):
            with self.assertRaises(backend_state.StateUnconfirmed):self.manager.switch('hidream')
        self.assertFalse(self.manager.busy);self.thread.assert_not_called();self.launch.assert_not_called()
        self.assertEqual(json.loads(self.path.read_text())['operation']['status'],'running')
        self.assertEqual(self.manager._uncertain_publication,hashlib.sha256(self.path.read_bytes()).hexdigest())
        with self.manager.studio.lock:
            for admit in (self.manager._admit_shared,self.manager.require_work_admission):
                with self.assertRaisesRegex(backend_state.StateError,'unconfirmed'):admit()
        with self.inert(self.manager):result=self.manager.resolve_switch_record(self.acknowledgement())
        self.assertFalse(result['shared_state']['blocker']);self.assertIsNone(self.manager.state_issue)
        with self.inert(self.manager):self.manager.switch('hidream')
        with self.assertRaisesRegex(ValueError,'still running'):self.manager.resolve_switch_record(self.acknowledgement())

    def test_own_launch_publication_uncertainty_keeps_evidence_until_explicit_inspection(self):
        with self.inert(self.manager):self.manager.switch('hidream')
        replace=backend_state.file_replace.replace
        def lost_reply(source,target):
            phase=json.loads(Path(source).read_text())['operation'].get('phase')
            replace(source,target)
            if phase=='launched':raise OSError('inert lost acknowledgement')
        with self.inert(self.manager),patch.object(backend_state.file_replace,'replace',side_effect=lost_reply):self.manager._switch('hidream')
        self.assertFalse(self.manager.busy);saved=json.loads(self.path.read_text())['operation']
        self.assertEqual(saved['status'],'running');self.assertEqual(saved['phase'],'launched');self.assertEqual(saved['pid'],901)
        self.assertIsNotNone(self.manager.state_issue)
        with self.inert(self.manager):result=self.manager.resolve_switch_record(self.acknowledgement())
        resolved=json.loads(self.path.read_text())['operation']
        self.assertEqual(resolved['pid'],901);self.assertEqual(resolved['log_directory'],saved['log_directory'])
        self.assertEqual(resolved['status'],'interrupted');self.assertFalse(result['shared_state']['blocker'])
        self.assertEqual(self.launch.call_count,1,'resolution performs no runtime action')

    def uncertain_terminal_publication(self,status,loss='reply',operation_target=None):
        manager=self.make_manager()
        with self.inert(manager):manager.switch('hidream')
        if operation_target is not None:manager.operation['target']=operation_target
        replace=backend_state.file_replace.replace;read=manager._state.read;pending_read=[]
        def publish(source,target):
            candidate=json.loads(Path(source).read_text());replace(source,target)
            if candidate['operation']['status']==status:
                if loss=='reply':raise OSError('inert lost terminal publication acknowledgement')
                pending_read.append(True)
        def observe():
            if pending_read:
                pending_read.pop();raise backend_state.StateError('inert lost landed read')
            return read()
        process=SimpleNamespace(pid=902,create_time=lambda:99)
        with self.inert(manager),patch.object(backend_state.file_replace,'replace',side_effect=publish), \
             patch.object(manager._state,'read',side_effect=observe), \
             patch.object(manager,'process',side_effect=lambda profile:process if profile['id']=='hidream' else None):
            if status=='failed':
                with patch.object(manager,'available',side_effect=ValueError('inert preflight failure')):manager._switch('hidream')
            else:manager._switch('hidream')
        self.assertFalse(manager.busy);self.assertIsNotNone(manager.state_issue)
        self.assertEqual(json.loads(self.path.read_text())['operation']['status'],status)
        return manager

    def test_terminal_publication_uncertainty_can_be_inspected_without_changing_its_outcome(self):
        for status in ('completed','failed'):
            for loss in ('reply','landed-read'):
                with self.subTest(status=status,loss=loss):
                    manager=self.uncertain_terminal_publication(status,loss)
                    saved=json.loads(self.path.read_text());active=manager.active
                    if status=='failed':manager.studio.jobs['other']={'status':'queued'}
                    with self.inert(manager):self.assertTrue(manager.snapshot()['shared_state']['resolvable'])
                    with self.inert(manager):result=manager.resolve_switch_record(self.acknowledgement())
                    landed=json.loads(self.path.read_text())
                    self.assertEqual(landed['active'],saved['active']);self.assertEqual(manager.active,saved['active'] if status=='completed' else active)
                    for key,value in saved['operation'].items():self.assertEqual(landed['operation'][key],value,key)
                    self.assertTrue(landed['operation']['resolution']['acknowledge_runtimes_inspected'])
                    self.assertIsNone(manager.state_issue);self.assertFalse(result['shared_state']['resolvable'])
                    self.assertFalse(result['shared_state']['blocker'])
        self.launch.assert_not_called()

    def test_completed_resolution_aligns_the_runtime_captured_by_the_next_job(self):
        from server import Studio
        manager=self.uncertain_terminal_publication('completed');studio=manager.studio;target=manager.profiles['hidream']
        self.assertEqual(manager.active,'primary');studio._schema={'old':'schema'};studio._schema_at=99
        with self.inert(manager):manager.resolve_switch_record(self.acknowledgement())
        studio.runs=self.root/'runs';studio.runs.mkdir()
        studio.prepare=Mock(return_value=({'id':'routing-fixture'}, {}, self.root/'workflow.json', {}, 1))
        studio.host_commit_preflight=Mock(return_value=None);studio._save=Mock();studio.public=lambda job:job
        studio._create_job=lambda payload,enqueue,job_id:Studio._create_job(studio,payload,enqueue,job_id)
        job=Studio.create_job(studio,{'preset_id':'routing-fixture'},enqueue=False)
        self.assertEqual(job['comfy_url'],target['url'])
        self.assertEqual(job['comfy_root'],target['root'])
        self.assertEqual(manager.active,'hidream');self.assertEqual(studio.library.backend_id,'hidream')
        self.assertEqual(studio.library.models,Path(target['root'])/'models')
        self.assertIsNone(studio._schema);self.assertEqual(studio._schema_at,0)
        self.launch.assert_not_called()

    def test_completed_alignment_waits_for_local_work_and_can_be_retried_after_it_settles(self):
        for work in ('queued','running','reference','production'):
            with self.subTest(work=work):
                self.path.unlink(missing_ok=True);manager=self.uncertain_terminal_publication('completed');studio=manager.studio
                if work in ('queued','running'):studio.jobs['other']={'status':work}
                elif work=='reference':studio.reference_jobs=SimpleNamespace(busy=lambda:True)
                else:studio.production=SimpleNamespace(list=lambda:[{'state':{'status':'running'}}])
                raw=self.path.read_bytes()
                with self.inert(manager),self.assertRaisesRegex(ValueError,'work|reconcile'):
                    manager.resolve_switch_record(self.acknowledgement())
                self.assertEqual(self.path.read_bytes(),raw);self.assertEqual(manager.active,'primary')
                with self.inert(manager):self.assertTrue(manager.snapshot()['shared_state']['resolvable'])
                studio.jobs.clear();studio.reference_jobs=None;studio.production=SimpleNamespace(list=lambda:[])
                with self.inert(manager):manager.resolve_switch_record(self.acknowledgement())
                self.assertEqual(manager.active,'hidream');self.assertIsNone(manager.state_issue)
        self.launch.assert_not_called()

    def test_completed_alignment_constructs_the_library_before_publishing_or_changing_routing(self):
        manager=self.uncertain_terminal_publication('completed');studio=manager.studio;raw=self.path.read_bytes()
        before=(manager.active,studio.comfy_url,studio.comfy_root,studio.library,studio._schema,studio._schema_at)
        with self.inert(manager),patch('model_library.ModelLibrary',side_effect=OSError('inert library preparation failure')):
            with self.assertRaisesRegex(OSError,'library preparation'):manager.resolve_switch_record(self.acknowledgement())
        self.assertEqual(self.path.read_bytes(),raw)
        self.assertEqual((manager.active,studio.comfy_url,studio.comfy_root,studio.library,studio._schema,studio._schema_at),before)
        with self.inert(manager):self.assertTrue(manager.snapshot()['shared_state']['resolvable'])
        with self.inert(manager):manager.resolve_switch_record(self.acknowledgement())
        self.assertEqual(manager.active,'hidream');self.launch.assert_not_called()

    def test_normal_completion_constructs_the_library_before_publishing_the_new_selection(self):
        manager=self.manager;studio=manager.studio
        before=(manager.active,studio.comfy_url,studio.comfy_root,studio.library,studio._schema,studio._schema_at)
        process=SimpleNamespace(pid=902,create_time=lambda:99)
        with self.inert(manager):manager.switch('hidream')
        with self.inert(manager),patch.object(manager,'process',side_effect=lambda profile:process if profile['id']=='hidream' else None), \
             patch('model_library.ModelLibrary',side_effect=OSError('inert library preparation failure')):
            manager._switch('hidream')
        saved=json.loads(self.path.read_text())
        self.assertEqual(saved['active'],'primary')
        self.assertEqual(saved['operation']['status'],'failed')
        self.assertIn('library preparation',saved['operation']['message'])
        self.assertEqual((manager.active,studio.comfy_url,studio.comfy_root,studio.library,studio._schema,studio._schema_at),before)
        self.assertFalse(manager.busy);self.launch.assert_not_called()

    def test_completed_alignment_requires_a_known_matching_saved_target(self):
        for mismatch in ('unknown-profile','different-target'):
            with self.subTest(mismatch=mismatch):
                self.path.unlink(missing_ok=True)
                manager=self.uncertain_terminal_publication('completed',operation_target='primary' if mismatch=='different-target' else None)
                if mismatch=='unknown-profile':del manager.profiles['hidream']
                raw=self.path.read_bytes();studio=manager.studio
                before=(manager.active,studio.comfy_url,studio.comfy_root,studio.library)
                with self.inert(manager),self.assertRaisesRegex(ValueError,'known saved environment'):
                    manager.resolve_switch_record(self.acknowledgement())
                self.assertEqual(self.path.read_bytes(),raw);self.assertIsNotNone(manager.state_issue)
                self.assertEqual((manager.active,studio.comfy_url,studio.comfy_root,studio.library),before)
        self.launch.assert_not_called()

    def test_legacy_resolution_remains_state_only_while_local_work_exists(self):
        saved=self.record();saved['operation'].pop('owner');self.path.write_text(json.dumps(saved))
        manager=self.make_manager();manager.studio.jobs['other']={'status':'queued'}
        with self.inert(manager):manager.resolve_switch_record(self.acknowledgement())
        self.assertEqual(manager.active,'primary');self.assertEqual(manager.studio.library.backend_id,'primary')
        self.assertEqual(json.loads(self.path.read_text())['operation']['status'],'interrupted')
        self.launch.assert_not_called()

    def test_terminal_resolution_refuses_changed_records_and_an_ordinary_error_hold(self):
        for change in ('record','ordinary-error'):
            with self.subTest(change=change):
                manager=self.uncertain_terminal_publication('completed')
                if change=='record':
                    saved=json.loads(self.path.read_text());saved['operation']['message']='Newer terminal evidence'
                    self.path.write_text(json.dumps(saved))
                else:manager._state_failed(backend_state.StateError('ordinary observation failure'))
                raw=self.path.read_bytes()
                with self.inert(manager):self.assertFalse(manager.snapshot()['shared_state']['resolvable'])
                with self.assertRaises(ValueError):manager.resolve_switch_record(self.acknowledgement())
                self.assertEqual(self.path.read_bytes(),raw)

    def test_normal_and_foreign_terminal_records_cannot_use_the_private_publication_exception(self):
        for status in ('completed','failed','interrupted'):
            for foreign in (False,True):
                with self.subTest(status=status,foreign=foreign):
                    owner=dict(self.manager._owner)
                    if foreign:owner['instance_id']='another-manager-in-the-same-process'
                    self.path.write_text(json.dumps({'active':'primary','operation':{'id':'terminal','status':status,'owner':owner}}))
                    observed=self.manager._state.read();raw=self.path.read_bytes()
                    with self.inert(self.manager):self.assertFalse(self.manager.snapshot()['shared_state']['resolvable'])
                    with self.assertRaises(ValueError):self.manager.resolve_switch_record(self.acknowledgement())
                    if foreign:
                        self.assertFalse(backend_state.resolution_allowed(observed,self.manager._owner,observed.identity[1]))
                    self.assertEqual(self.path.read_bytes(),raw)

    def test_lost_terminal_resolution_reply_requires_a_fresh_explicit_acknowledgement(self):
        manager=self.uncertain_terminal_publication('completed');command=self.acknowledgement()
        studio=manager.studio;before=(manager.active,studio.comfy_url,studio.comfy_root,studio.library)
        original=json.loads(self.path.read_text())['operation'];replace=backend_state.file_replace.replace
        def lost_reply(source,target):
            replace(source,target);raise OSError('inert lost resolution acknowledgement')
        with self.inert(manager),patch.object(backend_state.file_replace,'replace',side_effect=lost_reply):
            with self.assertRaises(backend_state.StateUnconfirmed):manager.resolve_switch_record(command)
        self.assertEqual((manager.active,studio.comfy_url,studio.comfy_root,studio.library),before)
        with self.inert(manager):self.assertTrue(manager.snapshot()['shared_state']['resolvable'])
        raw=self.path.read_bytes()
        with self.assertRaises(backend_state.StateConflict):manager.resolve_switch_record(command)
        self.assertEqual(self.path.read_bytes(),raw)
        with self.inert(manager):manager.resolve_switch_record(self.acknowledgement())
        landed=json.loads(self.path.read_text())['operation']
        for key,value in original.items():self.assertEqual(landed[key],value,key)
        self.assertEqual(manager.active,'hidream');self.assertEqual(studio.comfy_url,manager.profiles['hidream']['url'])
        self.assertIsNone(manager.state_issue);self.launch.assert_not_called()

    def test_lost_own_running_resolution_reply_can_settle_its_exact_interrupted_record(self):
        manager=self.manager;replace=backend_state.file_replace.replace
        def lost_reply(source,target):
            replace(source,target);raise OSError('inert lost acknowledgement')
        with self.inert(manager),patch.object(backend_state.file_replace,'replace',side_effect=lost_reply):
            with self.assertRaises(backend_state.StateUnconfirmed):manager.switch('hidream')
            self.assertFalse(manager.busy)
            with self.assertRaises(backend_state.StateUnconfirmed):manager.resolve_switch_record(self.acknowledgement())
        saved=json.loads(self.path.read_text());self.assertEqual(saved['operation']['status'],'interrupted')
        with self.inert(manager):self.assertTrue(manager.snapshot()['shared_state']['resolvable'])
        manager.studio.jobs['other']={'status':'queued'}
        with self.inert(manager):manager.resolve_switch_record(self.acknowledgement())
        landed=json.loads(self.path.read_text())
        self.assertEqual(landed['active'],saved['active'])
        for key in ('status','message','owner','started_at','inspection_required'):
            self.assertEqual(landed['operation'][key],saved['operation'][key])
        self.assertIsNone(manager.state_issue);self.thread.assert_not_called();self.launch.assert_not_called()
        self.assertEqual(manager.active,'primary');self.assertEqual(manager.studio.library.backend_id,'primary')


if __name__ == '__main__': unittest.main()
