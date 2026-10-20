"""Causal recovery publication tests; all backends and launches are inert."""
from contextlib import contextmanager
import copy
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import runtime_recovery
from server import Handler, PORT, Studio as RealStudio
from test_runtime_recovery import Studio


class RuntimeRecoveryPublicationTests(unittest.TestCase):
    LEGACY_RECORDS = (
        {'status': 'startup', 'attempts': 1, 'startup_pid': 9001, 'startup_at': 10, 'updated_at': 12, 'breaker_until': 20},
        {'status': 'breaker-open', 'attempts': 2},
        {'status': 'idle', 'attempts': 0, 'launch_pending': True},
        {'status': 'launching', 'attempts': 0},
        {'status': 'startup', 'attempts': 0},
        {'status': 'healthy', 'attempts': 0, 'startup_pid': 9001},
    )

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.studio = Studio(Path(self.directory.name))
        # Exercise the real historical writer on unchanged production in the RED run.
        self.studio._write_json_atomic = RealStudio._write_json_atomic.__get__(self.studio)
        self.recovery = runtime_recovery.RuntimeRecovery(self.studio)
        self.recovery._record('idle', 'Seeded previous observation.', attempts=0)
        self._inert_launcher()

    def _inert_launcher(self, failure=None, *, after_spawn=False):
        def launch(profile, on_spawn=None):
            self.studio.backends.launches += 1
            if failure is not None and not after_spawn: raise failure
            pid = 9000 + self.studio.backends.launches
            if on_spawn is not None: on_spawn(pid)
            if failure is not None: raise failure
            return pid
        self.studio.backends.launch_recovery = launch

    def _bytes(self): return self.recovery.path.read_bytes()
    def _saved(self): return json.loads(self._bytes())

    def _retained(self, value, *, enabled=True):
        root = Path(tempfile.mkdtemp(dir=self.directory.name))
        path = root / '.runtime' / 'runtime-recovery.json'
        if value is not None:
            path.parent.mkdir()
            path.write_bytes(value if isinstance(value, bytes) else json.dumps(value).encode())
        return runtime_recovery.RuntimeRecovery(Studio(root, enabled=enabled))

    @staticmethod
    def _retry_route(recovery, *, origin=None):
        # Use the real route and origin guard; only HTTP transport is in memory.
        handler = Handler.__new__(Handler)
        handler.studio = SimpleNamespace(runtime_recovery=recovery)
        handler.path = '/api/runtime-recovery/retry'
        handler.headers = {'Host': f'127.0.0.1:{PORT}', 'Origin': origin or f'http://127.0.0.1:{PORT}', 'Content-Length': '0'}
        handler.rfile = io.BytesIO()
        sent = []
        handler._json = lambda status, body: sent.append((status, body))
        handler.do_POST()
        return sent[0]

    def _returns(self, operation, *args, **kwargs):
        try: return operation(*args, **kwargs)
        except Exception as exc: self.fail('The observation must return without promoting a diagnostic fault: ' + repr(exc))

    @contextmanager
    def _sync_failure(self, kind, occurrence=1):
        original = os.fsync
        count = 0
        def sync(descriptor):
            nonlocal count
            actual = 'file' if stat.S_ISREG(os.fstat(descriptor).st_mode) else 'parent'
            if actual == kind:
                count += 1
                if count == occurrence: raise OSError(kind + ' sync fault')
            return original(descriptor)
        with patch('os.fsync', side_effect=sync): yield

    def test_file_sync_failure_keeps_live_record_log_and_prior_bytes(self):
        r = self.recovery
        before, raw, log, last = copy.deepcopy(r.state), self._bytes(), r.log_path.read_bytes(), copy.deepcopy(r._last_event)
        with self._sync_failure('file'), self.assertRaisesRegex(OSError, 'file sync fault'):
            r._record('startup', 'Candidate only.', attempts=1, startup_pid=9001)
        self.assertEqual(r.state, before)
        self.assertEqual(self._bytes(), raw)
        self.assertEqual(r.log_path.read_bytes(), log)
        self.assertEqual(r._last_event, last)

    @unittest.skipIf(os.name == 'nt', 'Native POSIX parent barrier')
    def test_visible_record_after_parent_failure_is_not_live_or_logged(self):
        r = self.recovery
        before, log, last = copy.deepcopy(r.state), r.log_path.read_bytes(), copy.deepcopy(r._last_event)
        with self._sync_failure('parent'), self.assertRaisesRegex(OSError, 'parent sync fault'):
            r._record('startup', 'Visible but unconfirmed.', attempts=1, startup_pid=9001)
        self.assertEqual(r.state, before)
        self.assertEqual(self._saved()['status'], 'startup')
        self.assertEqual(r.log_path.read_bytes(), log)
        self.assertEqual(r._last_event, last)

    def test_failed_reset_preserves_attempts_startup_breaker_and_log_identity(self):
        r = self.recovery
        r._record('breaker-open', 'Inspect previous start.', attempts=3, startup_pid=9001, startup_at=10, breaker_until=20)
        before, last = copy.deepcopy(r.state), copy.deepcopy(r._last_event)
        with self._sync_failure('file'), self.assertRaisesRegex(OSError, 'file sync fault'):
            r.reset()
        self.assertEqual(r.state, before)
        self.assertEqual(r._last_event, last)
        self.assertEqual(self._saved(), before)
        self.assertEqual(self.studio.backends.launches, 0)

    def test_failed_healthy_publication_preserves_attempts_and_startup(self):
        r = self.recovery
        r._record('startup', 'Loading.', attempts=2, startup_pid=9001, startup_at=10, breaker_until=20)
        before = copy.deepcopy(r.state)
        self.studio.backends.online = True
        with self._sync_failure('file'), self.assertRaisesRegex(OSError, 'file sync fault'):
            r.tick()
        self.assertEqual(r.state, before)
        self.assertEqual(self._saved(), before)
        self.assertEqual(self.studio.backends.launches, 0)

    def test_failed_health_publication_still_invalidates_observed_runtime_schema(self):
        for observation in ('first-health', 'endpoint-change', 'process-change'):
            for phase in ('file', 'post-replace'):
                with self.subTest(observation=observation, phase=phase):
                    r = self._retained(None)
                    r.studio.backends.online = True
                    r.studio.backends.listener = SimpleNamespace(pid=40, create_time=lambda: 100.0)
                    if observation != 'first-health': r.tick()
                    if observation == 'endpoint-change': r.studio.backends.stats['system']['comfyui_version'] = 'replacement'
                    if observation == 'process-change': r.studio.backends.listener = SimpleNamespace(pid=41, create_time=lambda: 200.0)
                    r.studio._schema = {'previous-runtime': {}}
                    r.studio._schema_at = runtime_recovery.time.monotonic()
                    r.studio._schema_lock = runtime_recovery.threading.Lock()
                    current_schema = {'replacement-runtime': {}}
                    r.studio._request = lambda route, timeout: current_schema
                    before = copy.deepcopy(r.state)
                    original = Path.replace
                    def replace(path, target):
                        original(path, target)
                        raise OSError('post-replace fault')
                    failure = self._sync_failure('file') if phase == 'file' else patch.object(Path, 'replace', replace)
                    with failure, self.assertRaisesRegex(OSError, 'file sync fault|post-replace fault'): r.tick()
                    self.assertEqual(r.state, before, 'Failed health publication cannot release recovery authority')
                    self.assertTrue(r.snapshot()['inspection_required'])
                    self.assertEqual(r.studio.backends.launches, 0)
                    self.assertIsNone(r.studio._schema, 'A current replacement observation must invalidate the old schema even when its record fails')
                    self.assertEqual(r.studio._schema_at, 0)
                    self.assertEqual(RealStudio.node_info(r.studio), current_schema)

    def test_failed_continuous_health_publication_preserves_current_schema(self):
        r = self.recovery
        self.studio.backends.online = True
        r.tick()
        self.studio._schema = {'current-runtime': {}}
        self.studio._schema_at = runtime_recovery.time.monotonic()
        before = copy.deepcopy(r.state)
        with self._sync_failure('file'), self.assertRaisesRegex(OSError, 'file sync fault'): r.tick()
        self.assertEqual(r.state, before)
        self.assertEqual(self.studio._schema, {'current-runtime': {}})
        self.assertGreater(self.studio._schema_at, 0)

    def test_failed_disconnect_publication_cannot_mask_a_later_reconnect(self):
        r = self.recovery
        self.studio.backends.online = True
        r.tick()
        self.studio._schema = {'previous-runtime': {}}
        self.studio._schema_at = runtime_recovery.time.monotonic()
        self.studio.backends.online = False
        before = copy.deepcopy(r.state)
        with patch('os.fsync', side_effect=OSError('storage unavailable')):
            with self.assertRaisesRegex(OSError, 'storage unavailable'): r.tick()
            with self.assertRaisesRegex(OSError, 'storage unavailable'):
                r._record('blocked', 'Monitor diagnostic also cannot publish.')
        self.assertEqual(r.state, before)
        self.studio.backends.online = True
        r.tick()
        self.assertEqual(r.snapshot()['status'], 'healthy')
        self.assertIsNone(self.studio._schema, 'A failed disconnect record cannot make reconnected runtime schema continuous')
        self.assertEqual(self.studio._schema_at, 0)

    def test_log_open_failure_preserves_committed_state_and_retries_only_the_log(self):
        r = self.recovery
        old_event = copy.deepcopy(r._last_event)
        original = Path.open
        def open_file(path, *args, **kwargs):
            if path == r.log_path and args and args[0] == 'a': raise OSError('log open fault')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', open_file):
            self._returns(r._record, 'healthy', 'Current observation.', attempts=0)
        self.assertEqual(r.state, self._saved())
        self.assertEqual(r.state['status'], 'healthy')
        self.assertEqual(r._last_event, old_event)
        self.assertIn('log open fault', r.snapshot()['log_error'])
        r._record('healthy', 'Current observation.', attempts=0)
        self.assertNotIn('log_error', r.snapshot())
        self.assertEqual(len(r.log_path.read_text(encoding='utf-8').splitlines()), 2)

    def test_launch_log_retains_the_attempt_number_and_identity_after_commit(self):
        r = self.recovery
        r.tick()
        lines = [json.loads(line) for line in r.log_path.read_text(encoding='utf-8').splitlines()]
        intent, terminal = lines[-2:]
        self.assertEqual(intent.get('attempts'), 1)
        self.assertEqual(terminal.get('attempts'), 1)
        self.assertEqual(intent.get('last_attempt', {}).get('id'), r.state['last_attempt']['id'])
        self.assertEqual(terminal.get('last_attempt', {}).get('pid'), 9001)

    def test_log_write_flush_and_close_faults_preserve_committed_state(self):
        r = self.recovery
        original = Path.open
        for phase in ('write', 'short-write', 'flush', 'close'):
            with self.subTest(phase=phase):
                previous = copy.deepcopy(r._last_event)
                @contextmanager
                def open_file(path, *args, **kwargs):
                    with original(path, *args, **kwargs) as stream:
                        if path != r.log_path or not args or args[0] != 'a': yield stream; return
                        proxy = Mock(wraps=stream)
                        if phase == 'write': proxy.write.side_effect = OSError('log write fault')
                        if phase == 'short-write': proxy.write.side_effect = lambda raw: stream.write(raw[:3])
                        if phase == 'flush': proxy.flush.side_effect = OSError('log flush fault')
                        yield proxy
                    if path == r.log_path and phase == 'close': raise OSError('log close fault')
                with patch.object(Path, 'open', open_file): self._returns(r._record, 'blocked', 'Diagnostic ' + phase)
                self.assertEqual(r.state, self._saved())
                self.assertEqual(r.state['message'], 'Diagnostic ' + phase)
                self.assertEqual(r._last_event, previous)
                self.assertTrue(r.snapshot().get('log_error'))

    def test_launch_intent_and_attempt_are_published_before_the_inert_spawn(self):
        r = self.recovery
        calls = []
        original = os.fsync
        def sync(descriptor):
            calls.append('file' if stat.S_ISREG(os.fstat(descriptor).st_mode) else 'parent')
            return original(descriptor)
        def launch(profile, on_spawn=None):
            saved = self._saved()
            self.assertTrue(saved.get('launch_pending'), 'A durable recovery intent must precede launch')
            self.assertEqual(saved['attempts'], 1)
            self.assertEqual(saved['last_attempt']['backend'], 'primary')
            self.assertIn('file', calls)
            if os.name != 'nt': self.assertIn('parent', calls)
            self.assertTrue(self.studio.lock._is_owned())
            self.studio.backends.launches += 1
            on_spawn(9001)
            return 9001
        self.studio.backends.launch_recovery = launch
        with patch('os.fsync', side_effect=sync): r.tick()
        self.assertEqual((r.state['status'], r.state['attempts'], self.studio.backends.launches), ('startup', 1, 1))
        self.assertFalse(r.state.get('launch_pending'))
        self.assertEqual(r.state['last_attempt']['pid'], 9001)

    def test_prelaunch_file_failure_starts_nothing_and_does_not_retry_on_later_poll(self):
        r = self.recovery
        before = copy.deepcopy(r.state)
        with self._sync_failure('file'), self.assertRaisesRegex(OSError, 'file sync fault'): r.tick()
        self.assertEqual(self.studio.backends.launches, 0)
        self.assertEqual(r.state, before)
        r.tick(); r.tick()
        self.assertEqual(self.studio.backends.launches, 0)
        self.assertTrue(r.snapshot()['inspection_required'])

    @unittest.skipIf(os.name == 'nt', 'Native POSIX parent barrier')
    def test_unconfirmed_prelaunch_intent_survives_later_observations_and_restart(self):
        r = self.recovery
        before = copy.deepcopy(r.state)
        with self._sync_failure('parent'), self.assertRaisesRegex(OSError, 'parent sync fault'): r.tick()
        self.assertEqual(self.studio.backends.launches, 0)
        self.assertEqual(r.state, before)
        pending = self._saved()['last_attempt']
        self.studio.backends.busy = True; r.tick()
        self.studio.backends.busy = False; r.tick()
        self.assertTrue(self._saved()['launch_pending'])
        self.assertEqual(self._saved()['last_attempt'], pending)
        self.assertEqual(self._saved()['attempts'], 1)
        restarted = runtime_recovery.RuntimeRecovery(self.studio)
        restarted.tick()
        self.assertTrue(restarted.snapshot()['inspection_required'])
        self.assertEqual(self.studio.backends.launches, 0)

    def test_launcher_error_before_spawn_keeps_charged_intent_and_blocks_further_attempts(self):
        r = self.recovery
        self._inert_launcher(OSError('spawn outcome unknown'))
        with self.assertRaisesRegex(OSError, 'spawn outcome unknown'): r.tick()
        self.assertEqual(r.state['attempts'], 1)
        self.assertTrue(r.state['launch_pending'])
        r.tick(); r.tick()
        self.assertEqual(self.studio.backends.launches, 1)
        self.assertTrue(r.snapshot()['inspection_required'])

    def test_launcher_error_after_spawn_retains_exact_pid_and_never_relaunches(self):
        r = self.recovery
        self._inert_launcher(OSError('pidfile fault'), after_spawn=True)
        with self.assertRaisesRegex(OSError, 'pidfile fault'): r.tick()
        self.assertIn('last_attempt', r.snapshot())
        self.assertEqual(r.snapshot()['last_attempt']['pid'], 9001)
        self.assertTrue(r.snapshot()['inspection_required'])
        r.tick(); r.tick()
        self.assertEqual(self.studio.backends.launches, 1)
        self.assertEqual(self._saved()['last_attempt']['pid'], 9001)
        restarted = runtime_recovery.RuntimeRecovery(self.studio)
        restarted.tick()
        self.assertEqual(self.studio.backends.launches, 1)

    def test_terminal_file_failure_retains_charged_attempt_and_spawn_evidence(self):
        r = self.recovery
        with self._sync_failure('file', occurrence=2), self.assertRaisesRegex(OSError, 'file sync fault'): r.tick()
        self.assertEqual((self.studio.backends.launches, r.state['attempts']), (1, 1))
        self.assertTrue(r.state['launch_pending'])
        self.assertEqual(r.snapshot()['last_attempt']['pid'], 9001)
        r.tick(); r.tick()
        self.assertEqual(self.studio.backends.launches, 1)

    @unittest.skipIf(os.name == 'nt', 'Native POSIX parent barrier')
    def test_visible_terminal_state_is_historical_on_restart_after_parent_failure(self):
        r = self.recovery
        with self._sync_failure('parent', occurrence=2), self.assertRaisesRegex(OSError, 'parent sync fault'): r.tick()
        self.assertEqual(self._saved()['status'], 'startup')
        self.assertFalse(self._saved().get('launch_pending'))
        restarted = runtime_recovery.RuntimeRecovery(self.studio)
        restarted.tick(); restarted.tick()
        self.assertEqual(self.studio.backends.launches, 1)
        self.assertEqual(restarted.snapshot()['attempts'], 1)
        self.assertTrue(restarted.snapshot()['inspection_required'])

    def test_post_replace_terminal_error_blocks_restart_on_every_platform(self):
        r = self.recovery
        original = Path.replace
        def replace(path, target):
            value = json.loads(path.read_bytes())
            result = original(path, target)
            if value.get('status') == 'startup': raise OSError('terminal replacement unconfirmed')
            return result
        with patch.object(Path, 'replace', replace), self.assertRaisesRegex(OSError, 'terminal replacement unconfirmed'): r.tick()
        self.assertEqual(self._saved()['status'], 'startup')
        self.assertEqual(r.state['status'], 'launching')
        self.assertEqual(r.snapshot()['last_attempt']['pid'], 9001)
        restarted = runtime_recovery.RuntimeRecovery(self.studio)
        restarted.tick()
        self.assertTrue(restarted.snapshot()['inspection_required'])
        self.assertEqual(self.studio.backends.launches, 1)

    def test_observational_status_changes_cannot_clear_an_uncertain_attempt(self):
        r = self.recovery
        self._inert_launcher(OSError('spawn uncertain'), after_spawn=True)
        with self.assertRaisesRegex(OSError, 'spawn uncertain'): r.tick()
        attempt = r.snapshot()['last_attempt']
        for status in ('reconnecting', 'leased', 'other-backend-active', 'blocked'):
            with self.subTest(status=status):
                r._record(status, 'Read-only observation.')
                self.assertEqual(self._saved()['last_attempt'], attempt)
                self.assertTrue(self._saved()['launch_pending'])
                self.assertEqual(self._saved()['attempts'], 1)
                self.assertTrue(r.snapshot()['inspection_required'])
        self.assertEqual(self.studio.backends.launches, 1)

    def test_log_failure_after_spawn_does_not_undo_terminal_record_or_repeat_launch(self):
        r = self.recovery
        original = Path.open
        def open_file(path, *args, **kwargs):
            if path == r.log_path and args and args[0] == 'a' and self.studio.backends.launches:
                raise OSError('terminal log fault')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', open_file): self._returns(r.tick)
        self.assertEqual((r.state['status'], r.state['attempts']), ('startup', 1))
        self.assertEqual(r.state, self._saved())
        self.assertIn('terminal log fault', r.snapshot()['log_error'])
        self.studio.backends.matching = [SimpleNamespace(pid=9001)]
        r.tick(); r.tick()
        self.assertEqual(self.studio.backends.launches, 1)

    def test_failed_monitor_diagnostic_still_reaches_the_bounded_sleep(self):
        class StopMonitor(BaseException): pass
        with patch.object(self.recovery, 'tick', side_effect=OSError('observation fault')) as tick, \
             patch.object(self.recovery, '_record', side_effect=OSError('diagnostic fault')), \
             patch.object(runtime_recovery.time, 'sleep', side_effect=StopMonitor) as sleep:
            with self.assertRaises(StopMonitor): self._returns(self.recovery._monitor)
        tick.assert_called_once()
        sleep.assert_called_once_with(self.recovery.interval)

    def test_explicit_reset_preserves_attempt_identity_and_releases_only_after_publication(self):
        r = self.recovery
        r.tick()
        self.assertIn('last_attempt', r.state)
        identity = copy.deepcopy(r.state['last_attempt'])
        restarted = runtime_recovery.RuntimeRecovery(self.studio)
        self.assertTrue(restarted.snapshot()['inspection_required'])
        with self._sync_failure('file'), self.assertRaisesRegex(OSError, 'file sync fault'): restarted.reset()
        self.assertTrue(restarted.snapshot()['inspection_required'])
        reset = restarted.reset()
        self.assertFalse(reset.get('inspection_required', False))
        self.assertEqual(reset['attempts'], 0)
        self.assertEqual(reset['last_attempt'], identity)
        self.assertEqual(self._saved()['last_attempt'], identity)
        restarted.tick()
        self.assertEqual(self.studio.backends.launches, 2)

    def test_fresh_health_preserves_attempt_identity_and_releases_only_after_publication(self):
        r = self.recovery
        r.tick()
        self.assertIn('last_attempt', r.state)
        identity = copy.deepcopy(r.state['last_attempt'])
        restarted = runtime_recovery.RuntimeRecovery(self.studio)
        self.studio.backends.online = True
        with self._sync_failure('file'), self.assertRaisesRegex(OSError, 'file sync fault'): restarted.tick()
        self.assertTrue(restarted.snapshot()['inspection_required'])
        result = restarted.tick()
        self.assertEqual(result['status'], 'healthy')
        self.assertEqual(result['attempts'], 0)
        self.assertFalse(result.get('inspection_required', False))
        self.assertEqual(result['last_attempt'], identity)
        again = runtime_recovery.RuntimeRecovery(self.studio)
        self.studio.backends.online = False
        again.tick()
        self.assertTrue(again.snapshot()['inspection_required'])
        self.assertEqual(self.studio.backends.launches, 1)

    @unittest.skipIf(os.name == 'nt', 'Native POSIX parent barrier')
    def test_visible_failed_reset_cannot_erase_attempt_evidence_on_restart(self):
        r = self.recovery
        r.tick()
        self.assertIn('last_attempt', r.state)
        identity = copy.deepcopy(r.state['last_attempt'])
        with self._sync_failure('parent'), self.assertRaisesRegex(OSError, 'parent sync fault'): r.reset()
        self.assertEqual(self._saved()['attempts'], 0)
        self.assertEqual(self._saved()['last_attempt'], identity)
        restarted = runtime_recovery.RuntimeRecovery(self.studio)
        restarted.tick()
        self.assertTrue(restarted.snapshot()['inspection_required'])
        self.assertEqual(self.studio.backends.launches, 1)

    def test_legacy_evidence_survives_successful_reset_health_and_later_observations(self):
        for source in self.LEGACY_RECORDS:
            for operation in ('reset', 'health'):
                with self.subTest(source=source, operation=operation):
                    r = self._retained(source)
                    expected = {'version': 1, 'evidence': source}
                    self.assertTrue(r.snapshot()['inspection_required'])
                    if operation == 'reset': result = r.reset()
                    else:
                        r.studio.backends.online = True
                        result = r.tick()
                    self.assertFalse(result.get('inspection_required', False))
                    self.assertEqual(result['attempts'], 0)
                    self.assertEqual(result.get('legacy_attempt'), expected)
                    self.assertNotIn('last_attempt', result, 'Legacy evidence cannot invent an attested attempt identity')
                    for status in ('reconnecting', 'leased', 'other-backend-active', 'blocked'):
                        r._record(status, 'Observation after a completed release.')
                        self.assertEqual(json.loads(r.path.read_bytes())['legacy_attempt'], expected)
                    r.reset()
                    r.studio.backends.online = True
                    self.assertEqual(r.tick()['legacy_attempt'], expected)
                    events = [json.loads(line) for line in r.log_path.read_text(encoding='utf-8').splitlines()]
                    self.assertEqual(events[-1].get('legacy_attempt'), expected)
                    r.studio.backends.online = False
                    restarted = runtime_recovery.RuntimeRecovery(r.studio)
                    restarted.tick()
                    self.assertTrue(restarted.snapshot()['inspection_required'])
                    self.assertEqual(r.studio.backends.launches, 0)

    def _failed_legacy_release(self, phase):
        for source in self.LEGACY_RECORDS:
            for operation in ('reset', 'health'):
                with self.subTest(source=source, operation=operation, phase=phase):
                    r = self._retained(source)
                    before = copy.deepcopy(r.state)
                    r.studio.backends.online = operation == 'health'
                    original = Path.replace
                    def replace(path, target):
                        original(path, target)
                        raise OSError('post-replace fault')
                    failure = self._sync_failure('parent') if phase == 'parent' else patch.object(Path, 'replace', replace)
                    with failure, self.assertRaisesRegex(OSError, 'parent sync fault|post-replace fault'):
                        r.reset() if operation == 'reset' else r.tick()
                    self.assertEqual(r.state, before)
                    self.assertTrue(r.snapshot()['inspection_required'])
                    visible = json.loads(r.path.read_bytes())
                    self.assertEqual(visible['attempts'], 0)
                    self.assertEqual(visible['status'], 'idle' if operation == 'reset' else 'healthy')
                    r.studio.backends.online = False
                    restarted = runtime_recovery.RuntimeRecovery(r.studio)
                    restarted.tick(); restarted.tick()
                    self.assertEqual(r.studio.backends.launches, 0, 'Readable release bytes cannot replenish legacy launch allowance')
                    self.assertTrue(restarted.snapshot()['inspection_required'])
                    self.assertEqual(visible.get('legacy_attempt'), {'version': 1, 'evidence': source})

    @unittest.skipIf(os.name == 'nt', 'Native POSIX parent barrier')
    def test_legacy_release_parent_failure_cannot_replenish_allowance_on_restart(self):
        self._failed_legacy_release('parent')

    def test_legacy_release_post_replace_error_cannot_replenish_allowance_on_restart(self):
        self._failed_legacy_release('post-replace')

    def test_status_only_legacy_history_is_preserved_before_an_observation_changes_status(self):
        for status in ('startup', 'launching'):
            for observation in ('reconnecting', 'leased', 'other-backend-active', 'blocked'):
                with self.subTest(status=status, observation=observation):
                    source = {'status': status, 'attempts': 0}
                    r = self._retained(source)
                    r._record(observation, 'Historical state is still held.')
                    self.assertTrue(r.snapshot()['inspection_required'])
                    self.assertEqual(json.loads(r.path.read_bytes()).get('legacy_attempt'), {'version': 1, 'evidence': source})
                    r.reset()
                    self.assertEqual(r.snapshot()['legacy_attempt'], {'version': 1, 'evidence': source})
                    self.assertEqual(r.studio.backends.launches, 0)

    def test_disabled_reset_preserves_valid_legacy_malformed_missing_and_unreadable_records(self):
        valid = {'status': 'launching', 'attempts': 1, 'launch_pending': True,
                 'last_attempt': {'version': 1, 'id': 'a' * 32, 'backend': 'primary', 'number': 1, 'at': 10, 'pid': 9001}}
        for name, source in (('versioned', valid), ('legacy', self.LEGACY_RECORDS[0]), ('malformed', b'{'),
                             ('missing', None), ('unreadable', valid)):
            with self.subTest(record=name):
                r = self._retained(source, enabled=False)
                raw = r.path.read_bytes() if r.path.exists() else None
                original = Path.open
                def open_file(path, *args, **kwargs):
                    if name == 'unreadable' and path == r.path and args and args[0] == 'rb':
                        raise PermissionError('retained record unreadable')
                    return original(path, *args, **kwargs)
                refused = None
                with patch.object(Path, 'open', open_file):
                    r = runtime_recovery.RuntimeRecovery(r.studio)
                    try: r.reset()
                    except ValueError as exc: refused = str(exc)
                self.assertEqual(r.path.read_bytes() if r.path.exists() else None, raw)
                self.assertIsNotNone(refused, 'Disabled Reset must refuse before publication')
                self.assertIn('disabled', refused.lower())
                self.assertEqual(r.snapshot()['status'], 'disabled')
                self.assertFalse(r.snapshot()['enabled'])
                self.assertNotIn('last_attempt', r.snapshot())
                self.assertNotIn('startup_pid', r.snapshot())
                self.assertFalse(r.log_path.exists())
                self.assertEqual(r.studio.backends.routes, [])
                self.assertEqual(r.studio.backends.launches, 0)

    def test_retry_route_refuses_disabled_reset_without_erasing_retained_evidence(self):
        source = {'status': 'startup', 'attempts': 1, 'startup_pid': 9001,
                  'last_attempt': {'version': 1, 'id': 'a' * 32, 'backend': 'primary', 'number': 1, 'at': 10, 'pid': 9001}}
        for retained in (source, b'{'):
            with self.subTest(retained=retained):
                r = self._retained(retained, enabled=False)
                raw = r.path.read_bytes()
                code, body = self._retry_route(r)
                self.assertEqual(code, 400)
                self.assertIn('disabled', body['error'].lower())
                self.assertEqual(r.path.read_bytes(), raw)
                self.assertEqual(r.snapshot()['status'], 'disabled')
                self.assertEqual(r.studio.backends.launches, 0)

    def test_retry_route_keeps_same_origin_guard_and_enabled_legacy_release(self):
        source = self.LEGACY_RECORDS[0]
        r = self._retained(source)
        raw = r.path.read_bytes()
        code, _ = self._retry_route(r, origin='https://foreign.invalid')
        self.assertEqual(code, 403)
        self.assertEqual(r.path.read_bytes(), raw)
        code, body = self._retry_route(r)
        self.assertEqual(code, 202)
        self.assertEqual(body['attempts'], 0)
        self.assertFalse(body.get('inspection_required', False))
        self.assertEqual(body.get('legacy_attempt'), {'version': 1, 'evidence': source})
        self.assertEqual(r.studio.backends.launches, 0)

    def test_invalid_retained_records_preserve_bytes_and_never_replenish_attempts(self):
        path = self.recovery.path
        invalid = [b'{', b'[]', b'{"status":"idle","attempts":-1}', b'{"status":"idle","attempts":true}',
                   b'{"status":"idle","attempts":"3"}', b'{"status":"idle","attempts":NaN}',
                   b'{"status":"idle","attempts":0,"startup_at":Infinity}',
                   b'{"status":"idle","attempts":0,"attempts":1}',
                   json.dumps({'status': 'idle', 'attempts': 0, 'message': 'x' * (128 * 1024)}).encode()]
        for raw in invalid:
            with self.subTest(raw=raw[:100]):
                path.write_bytes(raw)
                recovery = runtime_recovery.RuntimeRecovery(self.studio)
                result = self._returns(recovery.tick)
                self.assertTrue(result.get('inspection_required'))
                self.assertIn('inspect', result['message'].lower())
                with self.assertRaises(ValueError): recovery.reset()
                self.assertEqual(path.read_bytes(), raw)
                self.assertEqual(self.studio.backends.launches, 0)

    def test_unreadable_retained_record_is_preserved_without_probe_or_launch(self):
        original = Path.open
        raw = self._bytes()
        def open_file(path, *args, **kwargs):
            if path == self.recovery.path: raise PermissionError('retained record unreadable')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', open_file):
            recovery = runtime_recovery.RuntimeRecovery(self.studio)
            result = recovery.tick()
        self.assertTrue(result['inspection_required'])
        self.assertIn('With Studio stopped', result['message'])
        self.assertEqual(self._bytes(), raw)
        self.assertEqual(self.studio.backends.routes, [])
        self.assertEqual(self.studio.backends.launches, 0)


if __name__ == '__main__': unittest.main()
