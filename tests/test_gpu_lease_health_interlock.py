"""Lease acquisition cannot cross recovery's final health publication boundary."""
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import test_gpu_lease as fixtures
from gpu_lease import GpuLease
from runtime_recovery import RuntimeRecovery


class HealthPublicationInterlockTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.studio = fixtures.recovery_fixtures.Studio(Path(temporary.name))
        self.studio.backends.online = True
        idle = fixtures.FakeManager()
        for name in ('_local_work', '_check_retained_startup', '_check_startup_processes', '_idle', '_stopped_results'):
            setattr(self.studio.backends, name, getattr(idle, name))
        self.studio.gpu_lease = GpuLease(self.studio)
        self.recovery = RuntimeRecovery(self.studio)
        self.payload = {'holder': 'local-qwen', 'ttl_seconds': 600}

    def attempt_acquisition(self):
        """Try once from another thread; no sleeps or blocked worker may survive."""
        results = []; errors = []
        def acquire():
            entered = self.studio.lock.acquire(blocking=False)
            try:
                if entered: self.studio.gpu_lease.acquire(self.payload)
                results.append(entered)
            except BaseException as exc: errors.append(exc)
            finally:
                if entered: self.studio.lock.release()
        thread = threading.Thread(target=acquire, name='lease-health-boundary-test')
        thread.start(); thread.join(5)
        self.assertFalse(thread.is_alive(), 'Acquisition probe did not finish')
        self.assertEqual(errors, [])
        return results

    def test_final_lease_check_excludes_a_competing_acquisition(self):
        original = self.recovery._leased; attempts = []
        def leased():
            result = original()
            if self.studio.backends.routes:
                attempts.extend(self.attempt_acquisition())
            return result
        with patch.object(self.recovery, '_leased', side_effect=leased):
            result = self.recovery.tick()
        self.assertEqual(attempts, [False])
        self.assertEqual(result['status'], 'healthy')
        self.assertIsNone(self.studio.gpu_lease.active())
        self.assertTrue(self.studio.gpu_lease.acquire(self.payload)['granted'])
        self.assertEqual(self.recovery.tick()['status'], 'leased')

    def test_health_publication_keeps_the_same_acquisition_interlock(self):
        original = self.recovery._ready; attempts = []
        def ready(*args):
            attempts.extend(self.attempt_acquisition())
            return original(*args)
        with patch.object(self.recovery, '_ready', side_effect=ready):
            result = self.recovery.tick()
        self.assertEqual(attempts, [False])
        self.assertEqual(result['status'], 'healthy')
        self.assertIsNone(self.studio.gpu_lease.active())
        self.assertTrue(self.studio.gpu_lease.acquire(self.payload)['granted'])
        self.assertEqual(self.recovery.tick()['status'], 'leased')
