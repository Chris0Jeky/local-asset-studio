"""Schema-cache causality, with inert process and endpoint observations."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from test_runtime_recovery import Studio, RuntimeRecovery


def process(pid=40, created=100.0):
    return SimpleNamespace(pid=pid, create_time=lambda: created)


class RuntimeIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.studio = Studio(Path(self.tmp.name))
        self.manager = self.studio.backends
        self.manager.online = True
        self.recovery = RuntimeRecovery(self.studio)

    def observe(self, identity):
        self.manager.listener = identity
        self.recovery.tick()
        self.assertEqual(self.recovery.snapshot()['status'], 'healthy')
        self.assertEqual(self.manager.launches, 0)
        self.assertEqual(set(self.manager.routes), {'/system_stats'})

    def cache(self):
        self.studio._schema = {'cached': True}
        self.studio._schema_at = 8

    def assert_cached(self):
        self.assertEqual(self.studio._schema, {'cached': True})
        self.assertEqual(self.studio._schema_at, 8)

    def assert_invalidated(self):
        self.assertIsNone(self.studio._schema)
        self.assertEqual(self.studio._schema_at, 0)

    def test_optional_process_metadata_loss_and_return_do_not_evict(self):
        self.observe(process())
        self.cache()
        unavailable = SimpleNamespace(pid=40, create_time=lambda: (_ for _ in ()).throw(PermissionError('denied')))
        for missing in (None, PermissionError('denied'), ValueError('metadata unavailable'), unavailable):
            with self.subTest(missing=repr(missing)):
                self.observe(missing)
                self.assert_cached()
                self.observe(process())
                self.assert_cached()

    def test_first_process_observation_enriches_without_rebuilding_schema(self):
        self.observe(None)
        self.cache()
        self.observe(process())
        self.assert_cached()

    def test_different_observed_process_after_unknown_interval_invalidates(self):
        self.observe(process())
        self.cache()
        self.observe(None)
        self.assert_cached()
        self.observe(process(41, 200.0))
        self.assert_invalidated()

    def test_reused_pid_with_new_creation_time_invalidates(self):
        self.observe(process())
        self.cache()
        self.observe(process(40, 200.0))
        self.assert_invalidated()

    def test_endpoint_and_version_changes_invalidate_without_process_metadata(self):
        self.observe(process())
        self.cache()
        profile = dict(self.manager.profiles['primary'], url='http://127.0.0.1:8999')
        self.manager.profiles = {'primary': profile}
        self.observe(None)
        self.assert_invalidated()
        self.cache()
        self.manager.stats['system']['comfyui_version'] = 'changed'
        self.observe(None)
        self.assert_invalidated()

    def test_observed_reconnect_invalidates_even_when_process_matches(self):
        self.observe(process())
        self.cache()
        self.manager.online = False
        self.recovery.tick()
        self.manager.online = True
        self.observe(process())
        self.assert_invalidated()

    def test_unknown_process_is_not_reported_as_last_seen_identity(self):
        self.observe(process())
        known = self.recovery.snapshot()['endpoint_identity']
        self.observe(None)
        current = self.recovery.snapshot()['endpoint_identity']
        self.assertNotEqual(current, known)
        self.assertEqual(current, self.recovery._identity(self.manager.profiles['primary'], self.manager.stats))


if __name__ == '__main__':
    unittest.main()
