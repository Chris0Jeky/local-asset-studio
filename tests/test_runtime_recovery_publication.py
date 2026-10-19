"""Causal recovery publication tests; all backends and launches are inert."""
from contextlib import contextmanager
import copy
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
from server import Studio as RealStudio
from test_runtime_recovery import Studio


class RuntimeRecoveryPublicationTests(unittest.TestCase):
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
