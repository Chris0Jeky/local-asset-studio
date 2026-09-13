"""Inert recovery tests: no process, backend, or ComfyUI prompt is used."""
from __future__ import annotations

import errno
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).parents[1] / "app"))
from runtime_recovery import REFUSAL_PROBE_TIMEOUT, RuntimeRecovery


PROFILE = {"id": "primary", "name": "Main", "url": "http://127.0.0.1:8188"}


class Manager:
    def __init__(self):
        self.active = "primary"; self.profiles = {"primary": PROFILE}; self.busy = False
        self.online = False; self.error = None; self.matching = []; self.listener = None; self.launches = 0; self.routes = []; self.timeouts = []
        self.stats = {"system": {"comfyui_version": "test", "ram_free": 100}, "devices": [{"name": "test", "vram_free": 50}]}
    def request(self, profile, route, timeout):
        self.routes.append(route); self.timeouts.append(timeout)
        if self.online: return self.stats
        if self.error: raise self.error
        raise URLError(OSError(errno.ECONNREFUSED, "refused"))
    def process(self, profile):
        if isinstance(self.listener, Exception): raise self.listener
        return self.listener
    def configured_processes(self, profile): return list(self.matching)
    def available(self, profile): return True
    def readiness(self, profile): return {"message": "fixture ready"}
    def launch_recovery(self, profile):
        self.launches += 1
        return 9000 + self.launches


class Production:
    def list(self): return []


class Studio:
    def __init__(self, root, enabled=True):
        self.root = root; self.config = {"runtime_auto_recover": enabled, "runtime_recovery_max_attempts": 3,
                                        "runtime_recovery_backoff_seconds": 60, "runtime_recovery_startup_timeout_seconds": 30}
        self.config["runtime_recovery_autostart"] = False
        self.backends = Manager(); self.jobs = {}; self.production = Production(); self.lock = __import__("threading").RLock()
        self._schema = {"old": True}; self._schema_at = 4
    def _write_json_atomic(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(__import__("json").dumps(value), encoding="utf-8")


class RuntimeRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.studio = Studio(Path(self.tmp.name)); self.recovery = RuntimeRecovery(self.studio)
    def tearDown(self): self.tmp.cleanup()

    def test_repeated_offline_polls_launch_once_and_never_submit_prompt(self):
        self.recovery.tick()
        self.assertEqual(self.studio.backends.launches, 1)
        self.studio.backends.matching = [SimpleNamespace(pid=9001)]
        self.recovery.tick(); self.recovery.tick()
        self.assertEqual(self.studio.backends.launches, 1)
        self.assertEqual(set(self.studio.backends.routes), {"/system_stats"})
        self.assertEqual(self.recovery.snapshot()["status"], "startup")

    def test_refusal_probe_waits_for_the_windows_refusal_deadline(self):
        def windows_request(profile, route, timeout):
            if timeout < 2: raise URLError(TimeoutError('Windows has not returned refusal yet'))
            raise URLError(OSError(errno.ECONNREFUSED, 'refused'))
        self.studio.backends.request = windows_request
        self.recovery.tick()
        self.assertEqual(self.studio.backends.launches,1)

    def test_non_refused_timeout_never_authorizes_a_launch(self):
        self.studio.backends.error=URLError(TimeoutError('read timed out'))
        self.recovery.tick()
        self.assertEqual(self.studio.backends.timeouts,[REFUSAL_PROBE_TIMEOUT])
        self.assertEqual(self.studio.backends.launches,0)
        self.assertEqual(self.recovery.snapshot()['status'],'unreachable')

    def test_foreign_listener_and_fresh_work_are_preserved(self):
        self.studio.backends.listener = ValueError("Port is owned by another command")
        self.recovery.tick()
        self.assertEqual(self.recovery.snapshot()["status"], "foreign-or-ambiguous-listener")
        self.assertEqual(self.studio.backends.launches, 0)
        self.studio.backends.listener = None; self.studio.jobs["fresh"] = {"status": "running"}
        self.recovery.tick()
        self.assertEqual(self.recovery.snapshot()["status"], "crashed-absent-busy")
        self.assertEqual(self.studio.backends.launches, 0)

    def test_dead_starts_are_bounded_by_a_circuit_breaker(self):
        for _ in range(5): self.recovery.tick()
        self.assertEqual(self.studio.backends.launches, 3)
        self.assertEqual(self.recovery.snapshot()["status"], "breaker-open")

    def test_active_profile_change_during_scan_cannot_launch_stale_profile(self):
        manager=self.studio.backends; manager.profiles['hidream']={"id":"hidream","name":"HiDream","url":"http://127.0.0.1:8192"}
        scans=[]
        def scan(profile):
            scans.append(profile['id'])
            if len(scans)==1: manager.active='hidream'
            return []
        manager.configured_processes=scan
        self.recovery.tick()
        self.assertEqual(manager.active,'hidream')
        self.assertEqual(manager.launches,0)
        self.assertEqual(scans,['primary'])
        self.assertEqual(self.recovery.snapshot()['status'],'reconnecting')

    def test_startup_is_retained_and_healthy_reconnect_resets_attempts_and_schema(self):
        self.recovery.tick()
        self.studio.backends.matching = [SimpleNamespace(pid=9001)]
        self.recovery.tick()
        self.assertEqual(self.recovery.snapshot()["status"], "startup")
        self.studio.backends.matching = []; self.studio.backends.online = True
        self.recovery.tick()
        self.assertEqual(self.recovery.snapshot()["status"], "healthy")
        self.assertEqual(self.recovery.snapshot()["attempts"], 0)
        self.assertNotIn("startup_pid", self.recovery.snapshot())
        self.assertNotIn("startup_at", self.recovery.snapshot())
        self.assertIsNone(self.studio._schema); self.assertEqual(self.studio._schema_at, 0)

    def test_saved_healthy_state_is_checking_until_a_current_probe(self):
        self.recovery.state.update(
            status="healthy", message="Selected backend is healthy.", endpoint_identity="old",
            startup_pid=9001, startup_at=10, breaker_until=20, attempts=0,
        )
        self.studio._write_json_atomic(self.recovery.path, self.recovery.state)
        recovery = RuntimeRecovery(Studio(Path(self.tmp.name)))
        snapshot = recovery.snapshot()
        self.assertEqual(snapshot["status"], "checking")
        self.assertIn("historical", snapshot["message"])
        recovery.studio.backends.online = True
        recovery.tick()
        snapshot = recovery.snapshot()
        self.assertEqual(snapshot["status"], "healthy")
        self.assertNotIn("startup_pid", snapshot)
        self.assertNotIn("startup_at", snapshot)
        self.assertNotIn("breaker_until", snapshot)

    def test_volatile_memory_does_not_invalidate_schema_but_verified_restart_does(self):
        class Process:
            def __init__(self, pid, created_at): self.pid = pid; self.created_at = created_at
            def create_time(self): return self.created_at
        self.studio.backends.online = True
        self.studio.backends.listener = Process(40, 100.0)
        self.recovery.tick()
        first_identity = self.recovery.snapshot()["endpoint_identity"]
        self.studio._schema = {"current": True}; self.studio._schema_at = 8
        self.studio.backends.stats["system"]["ram_free"] = 10
        self.studio.backends.stats["devices"][0]["vram_free"] = 5
        self.recovery.tick()
        self.assertEqual(self.recovery.snapshot()["endpoint_identity"], first_identity)
        self.assertEqual(self.studio._schema, {"current": True}); self.assertEqual(self.studio._schema_at, 8)
        self.studio.backends.listener = Process(41, 200.0)
        self.recovery.tick()
        self.assertNotEqual(self.recovery.snapshot()["endpoint_identity"], first_identity)
        self.assertIsNone(self.studio._schema); self.assertEqual(self.studio._schema_at, 0)

    def test_observed_reconnect_invalidates_schema_without_process_identity(self):
        self.studio.backends.online = True
        self.recovery.tick()
        self.studio._schema = {"current": True}; self.studio._schema_at = 8
        self.studio.backends.online = False
        self.recovery.tick()
        self.studio.backends.online = True
        self.recovery.tick()
        self.assertIsNone(self.studio._schema); self.assertEqual(self.studio._schema_at, 0)

    def test_disabled_recovery_records_dead_backend_without_starting_it(self):
        studio = Studio(Path(self.tmp.name) / "disabled", enabled=False); recovery = RuntimeRecovery(studio)
        recovery.tick()
        self.assertEqual(studio.backends.launches, 0)
        self.assertEqual(recovery.snapshot()["status"], "crashed-absent")

    def test_disabled_recovery_does_not_restore_enabled_status_or_startup_identity(self):
        self.recovery.state.update(status="startup", message="Started backend", startup_pid=9001, startup_at=10, attempts=2)
        self.studio._write_json_atomic(self.recovery.path, self.recovery.state)
        studio = Studio(Path(self.tmp.name), enabled=False); recovery = RuntimeRecovery(studio)
        snapshot = recovery.snapshot()
        self.assertEqual(snapshot["status"], "disabled")
        self.assertEqual(snapshot["attempts"], 0)
        self.assertNotIn("message", snapshot)
        self.assertNotIn("startup_pid", snapshot)

    def test_identical_polls_refresh_state_but_append_one_log_line(self):
        r=self.recovery
        r._record("healthy","Selected backend is healthy.");first=__import__("json").loads(r.path.read_text(encoding="utf-8"))["updated_at"]
        r._record("healthy","Selected backend is healthy.");r._record("healthy","Selected backend is healthy.")
        self.assertEqual(len(r.log_path.read_text(encoding="utf-8").splitlines()),1)
        self.assertGreaterEqual(__import__("json").loads(r.path.read_text(encoding="utf-8"))["updated_at"],first)
        r._record("healthy","Selected backend is healthy.",pid=5);r._record("offline","Backend refused")
        lines=[__import__("json").loads(l) for l in r.log_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([l["status"] for l in lines],["healthy","healthy","offline"]);self.assertEqual(lines[1]["pid"],5);self.assertTrue(all("at" in l for l in lines))

if __name__ == "__main__": unittest.main()
