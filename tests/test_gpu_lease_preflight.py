"""Issue #979: preflight all listeners before any stop; never hide late partial stops."""
import tempfile
import unittest
from pathlib import Path

import test_gpu_lease as fixtures
from gpu_lease import GpuLease, GpuLeaseError


class LeaseStopPreflightTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.studio = fixtures.LeaseStudio(Path(temporary.name))
        self.manager = self.studio.backends
        self.manager.processes['hidream'] = fixtures.FakeProcess(pid=5252)
        self.lease = GpuLease(self.studio, clock=lambda: 10000.0)
        self.payload = {'holder': 'local-qwen', 'ttl_seconds': 600}

    def test_second_listener_strict_idle_failure_preserves_both_processes(self):
        original = self.manager._idle
        def idle(profile, allow_offline=False):
            if profile['id'] == 'hidream' and not allow_offline:
                raise ValueError('Second endpoint changed after the broad idle scan')
            return original(profile, allow_offline=allow_offline)
        self.manager._idle = idle
        with self.assertRaises(GpuLeaseError) as caught:
            self.lease.acquire(self.payload)
        self.assertEqual(caught.exception.code, 'backend_not_idle')
        self.assertEqual(caught.exception.details['stopped_processes'], [])
        self.assertTrue(all(p.terminated == 0 for p in self.manager.processes.values()))
        self.assertIsNone(self.lease.active()); self.assertFalse(self.lease.path.exists())

    def test_second_listener_identity_failure_preserves_both_processes(self):
        def unreadable(): raise PermissionError('Identity unavailable')
        self.manager.processes['hidream'].create_time = unreadable
        with self.assertRaises(GpuLeaseError) as caught:
            self.lease.acquire(self.payload)
        self.assertEqual(caught.exception.code, 'backend_not_idle')
        self.assertEqual(caught.exception.details['stopped_processes'], [])
        self.assertTrue(all(p.terminated == 0 for p in self.manager.processes.values()))
        self.assertIsNone(self.lease.active())

    def test_all_preflight_checks_finish_before_the_first_termination(self):
        strict = []; original = self.manager._idle
        def idle(profile, allow_offline=False):
            if not allow_offline: strict.append(profile['id'])
            return original(profile, allow_offline=allow_offline)
        self.manager._idle = idle
        primary = self.manager.processes['primary']; stop = primary.terminate
        def terminate():
            self.assertEqual(strict, ['primary', 'hidream', 'primary'])
            stop()
        primary.terminate = terminate
        result = self.lease.acquire(self.payload)
        self.assertTrue(result['granted'])
        self.assertEqual(strict, ['primary', 'hidream', 'primary', 'hidream'])
        self.assertEqual([p['pid'] for p in result['stopped_now']], [4242, 5252])
        self.assertTrue(all(p.terminated == 1 for p in self.manager.processes.values()))

    def test_late_idle_failure_still_reports_partial_stop_without_granting(self):
        original = self.manager._idle
        def idle(profile, allow_offline=False):
            if (profile['id'] == 'hidream' and not allow_offline
                    and self.manager.processes['primary'].terminated):
                raise ValueError('External work arrived after preflight')
            return original(profile, allow_offline=allow_offline)
        self.manager._idle = idle
        with self.assertRaises(GpuLeaseError) as caught:
            self.lease.acquire(self.payload)
        self.assertEqual(caught.exception.code, 'backend_not_idle')
        self.assertEqual([p['pid'] for p in caught.exception.details['stopped_processes']], [4242])
        self.assertEqual(self.manager.processes['primary'].terminated, 1)
        self.assertEqual(self.manager.processes['hidream'].terminated, 0)
        self.assertIsNone(self.lease.active()); self.assertFalse(self.lease.path.exists())
