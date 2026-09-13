"""Explicit-switch startup races, using only inert process and HTTP doubles."""
from contextlib import ExitStack
import errno
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).parents[1] / 'app'))
from backends import BackendManager


class StartupInterlockTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        def write(path, value):
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(value), encoding='utf-8'); temporary.replace(path)
        self.studio = SimpleNamespace(root=root, comfy_root=root/'comfy', config={}, jobs={},
                                      lock=threading.Lock(), production=SimpleNamespace(list=lambda: []),
                                      _write_json_atomic=write)
        self.manager = BackendManager(self.studio)
        self.listeners = {}; self.starting = {}; self.routes = []
        self.stack.enter_context(patch.object(self.manager, 'available', return_value=True))
        self.stack.enter_context(patch.object(self.manager, 'process', side_effect=lambda p: self.listeners.get(p['id'])))
        self.scan = self.stack.enter_context(patch.object(self.manager, 'configured_processes', side_effect=self.configured))
        self.request = self.stack.enter_context(patch.object(self.manager, 'request', side_effect=self.observe))
        self.launch = self.stack.enter_context(patch('backends.subprocess.Popen'))
        self.launch.return_value.pid = 500
        self.launch.return_value.poll.return_value = 1
        self.thread = self.stack.enter_context(patch('backends.threading.Thread'))
        self.activate = self.stack.enter_context(patch.object(self.manager, 'activate'))

    @staticmethod
    def process(pid, created=1):
        result = Mock(); result.pid = pid; result.create_time.return_value = created
        return result

    def configured(self, profile):
        listener = self.listeners.get(profile['id'])
        return ([listener] if listener else []) + self.starting.get(profile['id'], [])

    def observe(self, profile, route, *args):
        self.routes.append(route)
        if profile['id'] not in self.listeners:
            raise URLError(ConnectionRefusedError(errno.ECONNREFUSED, 'inert refused endpoint'))
        return {'system': {'python_version': 'fixture'}} if route == '/system_stats' else {'queue_running': [], 'queue_pending': []}

    def run_worker(self):
        self.manager.operation = {'id': 'startup-test', 'target': 'hidream', 'status': 'running'}
        self.manager.busy = True
        self.manager._switch('hidream')

    def preserved(self):
        self.launch.assert_not_called(); self.activate.assert_not_called()
        for process in list(self.listeners.values()) + [p for group in self.starting.values() for p in group]:
            process.terminate.assert_not_called()
        self.assertNotIn('/prompt', self.routes)
        self.assertEqual(self.manager.active, 'primary')

    def test_public_switch_refuses_unrecorded_target_startup(self):
        self.listeners['primary'] = self.process(100)
        self.starting['hidream'] = [self.process(200)]
        with self.assertRaisesRegex(ValueError, 'startup|starting'):
            self.manager.switch('hidream')
        self.preserved(); self.thread.assert_not_called()
        self.assertIsNone(self.manager.operation); self.assertFalse(self.manager.busy)
        self.assertFalse(self.manager.state_path.exists())

    def test_public_switch_refuses_startup_in_a_different_family(self):
        self.listeners['primary'] = self.process(100)
        self.starting['h3'] = [self.process(300)]
        with self.assertRaisesRegex(ValueError, 'H3'):
            self.manager.switch('hidream')
        self.preserved(); self.thread.assert_not_called()

    def test_worker_rechecks_startup_after_request_admission(self):
        self.listeners['primary'] = self.process(100)
        self.starting['hidream'] = [self.process(200)]
        self.run_worker(); self.preserved()
        self.assertEqual(self.manager.operation['status'], 'failed')
        self.assertIn('startup', self.manager.operation['message'])
        self.assertFalse(self.manager.busy)
        saved = json.loads(self.manager.state_path.read_text())
        self.assertEqual(saved['active'], 'primary')
        self.assertEqual(saved['operation']['status'], 'failed')

    def test_duplicate_startup_beside_ready_target_preserves_every_process(self):
        self.listeners.update(primary=self.process(100), hidream=self.process(200))
        self.starting['hidream'] = [self.process(201)]
        self.run_worker(); self.preserved()
        self.assertEqual(self.manager.operation['status'], 'failed')

    def test_pid_reuse_is_not_matching_process_identity(self):
        self.listeners.update(primary=self.process(100), hidream=self.process(200, 1))
        self.scan.side_effect = lambda p: [self.process(200, 2)] if p['id'] == 'hidream' else self.configured(p)
        self.run_worker(); self.preserved()
        self.assertIn('startup', self.manager.operation['message'])

    def test_unknown_process_identity_does_not_authorize_switch(self):
        self.listeners['primary'] = self.process(100)
        self.scan.side_effect = ValueError('Configured process identity is unknown')
        with self.assertRaisesRegex(ValueError, 'unknown'):
            self.manager.switch('hidream')
        self.preserved(); self.thread.assert_not_called()

    def test_startup_arriving_during_final_idle_check_is_preserved(self):
        self.listeners['primary'] = self.process(100)
        primary_checks = 0
        def observe(profile, route, *args):
            nonlocal primary_checks
            if profile['id'] == 'primary' and route == '/queue':
                primary_checks += 1
                if primary_checks == 2:self.starting['hidream'] = [self.process(200)]
            return self.observe(profile, route, *args)
        self.request.side_effect = observe
        self.run_worker(); self.preserved()
        self.assertIn('startup', self.manager.operation['message'])

    def test_startup_arriving_after_start_intent_blocks_popen(self):
        save = self.manager._save
        def persist():
            save()
            if self.manager.operation.get('message', '').startswith('Starting '):
                self.starting['hidream'] = [self.process(200)]
        with patch.object(self.manager, '_save', side_effect=persist):self.run_worker()
        self.preserved(); self.assertIn('startup', self.manager.operation['message'])

    def test_ready_matching_target_is_reused_without_launch(self):
        self.listeners['hidream'] = self.process(200)
        self.run_worker()
        self.activate.assert_called_once_with('hidream'); self.launch.assert_not_called()
        self.assertEqual(self.manager.operation['status'], 'completed')
        self.assertIn('inference was not checked', self.manager.operation['message'])
        self.assertNotIn('/prompt', self.routes)

    def test_restart_does_not_need_a_retained_switch_pid_to_protect_startup(self):
        self.studio._write_json_atomic(self.manager.state_path, {'active': 'primary', 'operation': None})
        restored = BackendManager(self.studio)
        with patch.object(restored, 'available', return_value=True), \
             patch.object(restored, 'process', return_value=None), \
             patch.object(restored, 'configured_processes', return_value=[self.process(200)]), \
             patch.object(restored, 'request', side_effect=self.observe):
            with self.assertRaisesRegex(ValueError, 'startup'):restored.switch('hidream')
        self.preserved(); self.thread.assert_not_called()

    def test_manual_queued_work_still_blocks_without_termination(self):
        self.listeners['primary'] = self.process(100)
        self.request.side_effect = lambda *args: {'queue_running': [], 'queue_pending': [['manual-job']]}
        with self.assertRaisesRegex(ValueError, 'preserved'):self.manager.switch('hidream')
        self.preserved(); self.thread.assert_not_called()


if __name__ == '__main__':unittest.main()
