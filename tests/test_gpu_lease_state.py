"""Issue #979: durable lease transitions and recovery precedence, using inert fakes."""
import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import test_gpu_lease as fixtures
from gpu_lease import GpuLease, GpuLeaseError, MAX_TTL_SECONDS
from runtime_recovery import RuntimeRecovery


class LeaseStateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.studio = fixtures.LeaseStudio(Path(temporary.name)); self.now = [10000.0]
        self.lease = GpuLease(self.studio, clock=lambda: self.now[0])
        self.payload = {'holder': 'local-qwen', 'ttl_seconds': 600}

    def test_failed_grant_does_not_publish_an_in_memory_lease(self):
        with patch.object(self.studio, '_write_json_atomic', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.lease.acquire(self.payload)
        self.assertIsNone(self.lease.record)
        self.assertFalse(self.lease.path.exists())
        self.assertFalse(self.lease.log_path.exists())

    def test_failed_renewal_preserves_the_committed_deadline(self):
        self.lease.acquire(self.payload)
        before = copy.deepcopy(self.lease.record); raw = self.lease.path.read_bytes()
        self.now[0] += 100
        with patch.object(self.studio, '_write_json_atomic', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.lease.acquire(self.payload)
        self.assertEqual(self.lease.record, before)
        self.assertEqual(self.lease.path.read_bytes(), raw)
        self.assertEqual(self.studio.backends.processes['primary'].terminated, 1)

    def test_failed_release_preserves_the_committed_lease_and_last_release(self):
        self.lease.acquire(self.payload)
        before = copy.deepcopy(self.lease.record); raw = self.lease.path.read_bytes()
        with patch.object(self.studio, '_write_json_atomic', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.lease.release({'holder': 'local-qwen'})
        self.assertEqual(self.lease.record, before)
        self.assertIsNone(self.lease.last_release)
        self.assertEqual(self.lease.path.read_bytes(), raw)
        self.assertEqual(self.lease.active(), before)

    def test_failed_expiry_retains_state_until_expiry_can_be_committed(self):
        self.lease.acquire(self.payload)
        before = copy.deepcopy(self.lease.record); raw = self.lease.path.read_bytes()
        self.now[0] += 600
        with patch.object(self.studio, '_write_json_atomic', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.lease.active()
        self.assertEqual(self.lease.record, before)
        self.assertIsNone(self.lease.last_release)
        self.assertEqual(self.lease.path.read_bytes(), raw)
        self.assertIsNone(self.lease.active())
        self.assertEqual(self.lease.last_release['reason'], 'expired')

    def test_same_holder_renewal_does_not_reobserve_or_stop_backends(self):
        self.lease.acquire(self.payload)
        before = copy.deepcopy(self.lease.record)
        self.studio.backends.busy = True; self.studio.backends.work = True
        self.studio.backends.queue_busy = True
        self.now[0] += 100
        with patch.object(self.studio.backends, '_local_work', side_effect=AssertionError('renewal checked work')):
            try: renewed = self.lease.acquire(self.payload)
            except GpuLeaseError as exc: self.fail(f'Existing holder renewal was refused: {exc}')
        self.assertTrue(renewed['renewed']); self.assertEqual(renewed['stopped_now'], [])
        self.assertEqual(renewed['acquired_at'], before['acquired_at'])
        self.assertEqual(renewed['expires_at'], self.now[0] + 600)
        self.assertEqual(renewed['stopped_processes'], before['stopped_processes'])
        self.assertEqual(self.studio.backends.processes['primary'].terminated, 1)
        with self.assertRaises(GpuLeaseError) as caught:
            self.lease.acquire({'holder': 'another-tool', 'ttl_seconds': 600})
        self.assertEqual(caught.exception.code, 'lease_held')

    def test_expired_holder_must_pass_fresh_acquisition_checks(self):
        self.lease.acquire(self.payload); self.now[0] += 600
        self.studio.backends.work = True
        with self.assertRaises(GpuLeaseError) as caught:
            self.lease.acquire(self.payload)
        self.assertEqual(caught.exception.code, 'studio_work_active')
        self.assertIsNone(self.lease.active())
        self.assertEqual(self.lease.last_release['reason'], 'expired')
        self.assertEqual(self.studio.backends.processes['primary'].terminated, 1)

    def test_invalid_renewal_does_not_change_the_committed_lease(self):
        self.lease.acquire(self.payload); before = copy.deepcopy(self.lease.record)
        raw = self.lease.path.read_bytes()
        for ttl in (True, 60.0, 59, MAX_TTL_SECONDS + 1, None):
            with self.subTest(ttl=ttl), self.assertRaises(GpuLeaseError) as caught:
                self.lease.acquire({'holder': 'local-qwen', 'ttl_seconds': ttl})
            self.assertEqual(caught.exception.code, 'invalid_lease_request')
            self.assertEqual(self.lease.record, before)
            self.assertEqual(self.lease.path.read_bytes(), raw)

    def test_loaded_deadline_is_clamped_and_the_clamp_survives_restart(self):
        self.lease.acquire(self.payload)
        saved = json.loads(self.lease.path.read_text())
        saved['record']['expires_at'] = self.now[0] + MAX_TTL_SECONDS * 10
        self.lease.path.write_text(json.dumps(saved))
        restarted = GpuLease(self.studio, clock=lambda: self.now[0])
        deadline = self.now[0] + MAX_TTL_SECONDS
        self.assertEqual(restarted.active()['expires_at'], deadline)
        self.assertEqual(json.loads(self.lease.path.read_text())['record']['expires_at'], deadline)
        self.now[0] += 100
        again = GpuLease(self.studio, clock=lambda: self.now[0])
        self.assertEqual(again.active()['expires_at'], deadline)
        self.assertEqual(again.active()['acquired_at'], saved['record']['acquired_at'])

    def test_arbitrarily_large_integer_deadline_is_bounded_without_float_overflow(self):
        self.lease.acquire(self.payload)
        saved = json.loads(self.lease.path.read_text()); saved['record']['expires_at'] = 10 ** 400
        self.lease.path.write_text(json.dumps(saved))
        try: restarted = GpuLease(self.studio, clock=lambda: self.now[0])
        except OverflowError as exc: self.fail(f'Integer deadline overflowed during validation: {exc}')
        self.assertEqual(restarted.active()['expires_at'], self.now[0] + MAX_TTL_SECONDS)


class RecoveryLeasePriorityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.studio = fixtures.recovery_fixtures.Studio(Path(temporary.name))
        self.studio.gpu_lease = GpuLease(self.studio)
        self.recovery = RuntimeRecovery(self.studio)

    def hold(self):
        self.studio.gpu_lease.record = {'holder': 'local-qwen', 'expires_at': time.time() + 600}

    def test_healthy_endpoint_cannot_hide_a_held_lease_or_reset_recovery(self):
        self.hold(); self.studio.backends.online = True
        self.recovery.state.update(attempts=2, startup_pid=9001)
        before_schema = self.studio._schema
        result = self.recovery.tick()
        self.assertEqual(result['status'], 'leased')
        self.assertIn('local-qwen', result['message'])
        self.assertEqual(result['attempts'], 2); self.assertEqual(result['startup_pid'], 9001)
        self.assertIs(self.studio._schema, before_schema)
        self.assertEqual(self.studio.backends.routes, [])
        self.assertEqual(self.studio.backends.launches, 0)

    def test_lease_taken_during_health_probe_wins_over_healthy_result(self):
        self.studio.backends.online = True
        original = self.studio.backends.request
        def request(*args):
            self.hold(); return original(*args)
        self.studio.backends.request = request
        self.recovery.state['attempts'] = 2
        result = self.recovery.tick()
        self.assertEqual(result['status'], 'leased')
        self.assertEqual(result['attempts'], 2)
        self.assertEqual(self.studio.backends.launches, 0)

    def test_release_restores_health_observation(self):
        self.hold(); self.studio.backends.online = True
        self.assertEqual(self.recovery.tick()['status'], 'leased')
        self.studio.gpu_lease.release({'holder': 'local-qwen'})
        self.assertEqual(self.recovery.tick()['status'], 'healthy')
        self.assertEqual(self.studio.backends.routes, ['/system_stats'])
