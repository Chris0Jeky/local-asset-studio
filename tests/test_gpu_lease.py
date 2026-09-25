"""GPU lease (issue #805): inert fakes only. No real process is stopped, no ComfyUI endpoint is probed, no prompt is posted."""
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from gpu_lease import MAX_TTL_SECONDS, MIN_TTL_SECONDS, GpuLease, GpuLeaseError
from runtime_recovery import RuntimeRecovery
import test_runtime_recovery as recovery_fixtures
from test_server import GRAPH, PRESET, FakeStudio, server


class FakeProcess:
    def __init__(self, pid=4242, exits=True):
        self.pid = pid; self.exits = exits; self.terminated = 0; self.waited = []
    def create_time(self): return 1000.0
    def terminate(self): self.terminated += 1
    def wait(self, timeout):
        self.waited.append(timeout)
        if not self.exits: raise TimeoutError("process is still running")


class FakeManager:
    """Only the BackendManager seams the lease uses; every check is scripted."""
    def __init__(self):
        self.busy = False; self.work = False; self.queue_busy = False; self.startup_error = None
        self.profiles = {"primary": {"id": "primary", "name": "Main library", "entry": "C:/fake/ComfyUI/main.py"},
                         "hidream": {"id": "hidream", "name": "HiDream", "entry": "C:/fake/hidream-launch.py"}}
        self.processes = {"primary": FakeProcess()}; self.idle_calls = []
    def _local_work(self): return self.work
    def _check_retained_startup(self): pass
    def _check_startup_processes(self):
        if self.startup_error: raise ValueError(self.startup_error)
        return {}
    def _idle(self, profile, allow_offline=False):
        self.idle_calls.append((profile["id"], allow_offline))
        if self.queue_busy: raise ValueError("ComfyUI has active or queued work. Its queue was preserved.")
        return True
    def _stopped_results(self): pass
    def process(self, profile):
        process = self.processes.get(profile["id"])
        return None if process is None or (process.terminated and process.exits) else process


class LeaseStudio:
    def __init__(self, root):
        self.root = root; self.lock = threading.RLock(); self.backends = FakeManager()
        self.runtime_recovery = SimpleNamespace(enabled=True)
    def _write_json_atomic(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value), encoding="utf-8")


class GpuLeaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.now = [10_000.0]; self.studio = LeaseStudio(Path(self.tmp.name))
        self.lease = GpuLease(self.studio, clock=lambda: self.now[0])
    def refused(self, call, payload, status, code):
        with self.assertRaises(GpuLeaseError) as caught: call(payload)
        self.assertEqual((caught.exception.status, caught.exception.code), (status, code)); return caught.exception

    def test_request_validation_refuses_before_any_backend_check(self):
        for payload in (None, [], {"holder": "local-qwen"}, {"holder": "local-qwen", "ttl_seconds": True},
                        {"holder": "local-qwen", "ttl_seconds": 600.0}, {"holder": "local-qwen", "ttl_seconds": "600"},
                        {"holder": "local-qwen", "ttl_seconds": MIN_TTL_SECONDS - 1}, {"holder": "local-qwen", "ttl_seconds": MAX_TTL_SECONDS + 1},
                        {"holder": "Local Qwen", "ttl_seconds": 600}, {"holder": "", "ttl_seconds": 600}, {"holder": "x" * 65, "ttl_seconds": 600},
                        {"holder": "local-qwen", "ttl_seconds": 600, "force": True}):
            with self.subTest(payload=payload): self.refused(self.lease.acquire, payload, 400, "invalid_lease_request")
        self.assertEqual(self.studio.backends.idle_calls, []); self.assertEqual(self.studio.backends.processes["primary"].terminated, 0)
        self.assertFalse(self.lease.snapshot()["held"])

    def test_idle_backend_is_stopped_and_the_lease_is_recorded_and_persisted(self):
        result = self.lease.acquire({"holder": "local-qwen", "ttl_seconds": 3600})
        process = self.studio.backends.processes["primary"]
        self.assertEqual((process.terminated, process.waited), (1, [15]))
        self.assertTrue(result["granted"]); self.assertFalse(result["renewed"]); self.assertTrue(result["held"])
        self.assertEqual((result["holder"], result["expires_at"], result["remaining_seconds"]), ("local-qwen", 13_600.0, 3600.0))
        self.assertEqual(result["stopped_now"], [{"profile": "primary", "pid": 4242, "created_at": 1000.0, "entry": "C:/fake/ComfyUI/main.py"}])
        # Every endpoint was checked idle (offline allowed), then the running one rechecked strictly before termination.
        self.assertEqual(self.studio.backends.idle_calls, [("primary", True), ("hidream", True), ("primary", False)])
        saved = json.loads((self.studio.root / ".runtime/gpu-lease.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["record"]["holder"], "local-qwen")
        self.assertIn('"event": "granted"', (self.studio.root / ".runtime/gpu-lease.log").read_text(encoding="utf-8"))

    def test_busy_queue_unverified_listener_studio_work_and_switch_refuse_without_stopping(self):
        manager = self.studio.backends; payload = {"holder": "local-qwen", "ttl_seconds": 600}
        manager.queue_busy = True
        self.assertIn("active or queued work", str(self.refused(self.lease.acquire, payload, 409, "backend_not_idle")))
        manager.queue_busy = False; manager.startup_error = "Port 8188 is owned by another command. Studio will not stop it."
        self.refused(self.lease.acquire, payload, 409, "backend_not_idle")
        manager.startup_error = None; manager.work = True
        self.refused(self.lease.acquire, payload, 409, "studio_work_active")
        manager.work = False; manager.busy = True
        self.refused(self.lease.acquire, payload, 409, "backend_switch_active")
        self.assertEqual(manager.processes["primary"].terminated, 0); self.assertFalse(self.lease.snapshot()["held"])
        self.assertFalse((self.studio.root / ".runtime/gpu-lease.json").exists())

    def test_unconfirmed_exit_does_not_grant_the_lease(self):
        self.studio.backends.processes["primary"] = FakeProcess(exits=False)
        error = self.refused(self.lease.acquire, {"holder": "local-qwen", "ttl_seconds": 600}, 500, "stop_unconfirmed")
        self.assertEqual(error.details["stopped_processes"], []); self.assertFalse(self.lease.snapshot()["held"])

    def test_one_holder_at_a_time_and_the_same_holder_renews(self):
        self.lease.acquire({"holder": "local-qwen", "ttl_seconds": 600})
        error = self.refused(self.lease.acquire, {"holder": "other-tool", "ttl_seconds": 600}, 409, "lease_held")
        self.assertEqual(error.details["holder"], "local-qwen")
        self.now[0] += 300
        renewed = self.lease.acquire({"holder": "local-qwen", "ttl_seconds": 900})
        self.assertTrue(renewed["renewed"]); self.assertEqual(renewed["stopped_now"], [])
        self.assertEqual((renewed["acquired_at"], renewed["renewed_at"], renewed["expires_at"]), (10_000.0, 10_300.0, 11_200.0))
        self.assertEqual(len(renewed["stopped_processes"]), 1)  # the original stop stays on the record
        self.assertEqual(self.studio.backends.processes["primary"].terminated, 1)

    def test_release_requires_the_holder_and_is_idempotent(self):
        self.assertFalse(self.lease.release({"holder": "local-qwen"})["released"])
        self.lease.acquire({"holder": "local-qwen", "ttl_seconds": 600})
        self.refused(self.lease.release, {"holder": "other-tool"}, 409, "lease_held")
        self.refused(self.lease.release, {"holder": "local-qwen", "ttl_seconds": 1}, 400, "invalid_lease_request")
        released = self.lease.release({"holder": "local-qwen"})
        self.assertTrue(released["released"]); self.assertFalse(released["held"]); self.assertEqual(released["relaunch_on_release"], "automatic")
        self.assertEqual(released["last_release"]["reason"], "released"); self.assertIsNone(self.lease.active())
        self.lease.require_available()

    def test_ttl_expiry_releases_and_refusal_names_the_holder_until_then(self):
        self.lease.acquire({"holder": "local-qwen", "ttl_seconds": 60})
        with self.assertRaises(GpuLeaseError) as caught: self.lease.require_available()
        self.assertEqual(caught.exception.code, "gpu_leased"); self.assertIn("local-qwen", str(caught.exception))
        self.assertIn("Nothing was submitted", self.lease.refusal())
        self.now[0] += 60
        self.assertIsNone(self.lease.refusal()); self.assertEqual(self.lease.snapshot()["last_release"]["reason"], "expired")
        self.lease.require_available()

    def test_lease_survives_a_studio_restart_only_until_it_expires(self):
        self.lease.acquire({"holder": "local-qwen", "ttl_seconds": 600})
        restarted = GpuLease(self.studio, clock=lambda: self.now[0])
        self.assertEqual(restarted.active()["holder"], "local-qwen")
        self.now[0] += 600
        later = GpuLease(self.studio, clock=lambda: self.now[0])
        self.assertIsNone(later.active()); self.assertEqual(later.snapshot()["last_release"]["reason"], "expired")
        (self.studio.root / ".runtime/gpu-lease.json").write_text('{"record": {"holder": "local-qwen", "expires_at": "never"}}', encoding="utf-8")
        self.assertIsNone(GpuLease(self.studio, clock=lambda: self.now[0]).active())


class RecoverySuppressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.studio = recovery_fixtures.Studio(Path(self.tmp.name)); self.recovery = RuntimeRecovery(self.studio)
        self.studio.gpu_lease = GpuLease(self.studio)
    def hold(self, seconds=600):
        self.studio.gpu_lease.record = {"holder": "local-qwen", "acquired_at": time.time(), "expires_at": time.time() + seconds, "stopped_processes": []}

    def test_a_held_lease_stops_the_monitor_relaunching_the_backend(self):
        self.hold()
        for _ in range(3): self.recovery.tick()
        self.assertEqual(self.studio.backends.launches, 0)
        snapshot = self.recovery.snapshot()
        self.assertEqual((snapshot["status"], snapshot["attempts"]), ("leased", 0)); self.assertIn("local-qwen", snapshot["message"])

    def test_release_or_expiry_hands_the_backend_back_to_recovery(self):
        self.hold(); self.recovery.tick()
        self.studio.gpu_lease.release({"holder": "local-qwen"}); self.recovery.tick()
        self.assertEqual(self.studio.backends.launches, 1)
        self.studio.backends.matching = []; self.studio.backends.online = True; self.recovery.tick()
        self.assertEqual(self.recovery.snapshot()["status"], "healthy")
        self.studio.backends.online = False; self.recovery.state.pop("startup_pid", None)
        self.hold(-1); self.recovery.tick()
        self.assertEqual(self.studio.backends.launches, 2); self.assertEqual(self.studio.gpu_lease.snapshot()["last_release"]["reason"], "expired")

    def test_a_lease_taken_during_the_scan_blocks_the_launch_recheck(self):
        manager = self.studio.backends; original = manager.configured_processes
        def scan(profile):
            self.hold(); return original(profile)
        manager.configured_processes = scan
        self.recovery.tick()
        self.assertEqual(manager.launches, 0); self.assertEqual(self.recovery.snapshot()["status"], "reconnecting")


def inert_backends(studio, process=None, queue_busy=False):
    """Replace every BackendManager seam that could observe or stop a real process on this PC."""
    manager = studio.backends; calls = []
    def idle(profile, allow_offline=False):
        calls.append(profile["id"])
        if queue_busy: raise ValueError("ComfyUI has active or queued work. Its queue was preserved.")
        return True
    manager._idle = idle; manager._check_retained_startup = lambda: None
    manager._check_startup_processes = lambda: {}; manager._stopped_results = lambda: None
    manager.process = lambda profile: process if profile["id"] == "primary" and process and not process.terminated else None
    manager.available = lambda profile: True
    return calls


class ServerLeaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root = Path(self.tmp.name)
        (self.root / "presets").mkdir(); (self.root / "workflows/api").mkdir(parents=True)
        (self.root / "config").mkdir(); (self.root / "fake-comfy/input").mkdir(parents=True)
        (self.root / "config/local.json").write_text(json.dumps({"comfy_root": str(self.root / "fake-comfy")}))
        (self.root / "presets/catalog.json").write_text(json.dumps({"presets": [PRESET]}))
        (self.root / "workflows/api/demo-api.json").write_text(json.dumps(GRAPH))
        with patch.object(threading.Thread, "start", lambda *_: None): self.studio = FakeStudio(self.root, [])
        self.process = FakeProcess(); self.idle_calls = inert_backends(self.studio, self.process)

    def serve(self):
        handler = type("LeaseHandler", (server.Handler,), {"studio": self.studio})
        http = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        worker = threading.Thread(target=http.serve_forever, daemon=True); worker.start()
        self.addCleanup(lambda: (http.shutdown(), http.server_close(), worker.join(2)))
        return http.server_port

    def request(self, port, method, path, payload=None, headers=None):
        connection = HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            options = {"Host": "127.0.0.1:8191", "Origin": "http://127.0.0.1:8191", "Content-Type": "application/json", **(headers or {})}
            connection.request(method, path, None if payload is None else json.dumps(payload), options)
            response = connection.getresponse(); return response.status, json.loads(response.read())
        finally: connection.close()

    def test_worker_never_posts_a_prompt_for_a_job_that_raced_the_lease(self):
        queued = self.studio.jobs[self.studio.create_job({"preset_id": "demo", "controls": {}}, enqueue=False)["id"]]
        with self.assertRaises(GpuLeaseError) as caught: self.studio.gpu_lease.acquire({"holder": "local-qwen", "ttl_seconds": 600})
        self.assertEqual(caught.exception.code, "studio_work_active"); self.assertEqual(self.process.terminated, 0)
        queued.update(status="abandoned"); self.studio._save(queued)
        self.studio.gpu_lease.acquire({"holder": "local-qwen", "ttl_seconds": 600})
        # A non-HTTP caller (the workflow MCP ticket path) can still create a job after the lease was granted.
        job = self.studio.jobs[self.studio.create_job({"preset_id": "demo", "controls": {}}, enqueue=False)["id"]]
        self.studio._run(job)
        self.assertEqual(job["status"], "not_submitted"); self.assertIn("leased to local-qwen", job["message"])
        self.assertIn("Nothing was submitted", job["message"]); self.assertNotIn("pending_submission", job)
        self.assertEqual(self.studio.requests, [])

    def test_backend_switch_is_refused_while_leased(self):
        self.studio.gpu_lease.acquire({"holder": "local-qwen", "ttl_seconds": 600})
        with self.assertRaises(GpuLeaseError) as caught: self.studio.backends.switch("primary")
        self.assertEqual(caught.exception.code, "gpu_leased"); self.assertFalse(self.studio.backends.busy)

    def test_http_contract_acquire_report_refuse_jobs_and_release(self):
        port = self.serve()
        self.assertEqual(self.request(port, "GET", "/api/gpu-lease")[1]["held"], False)
        status, body = self.request(port, "POST", "/api/gpu-lease", {"holder": "local-qwen", "ttl_seconds": 1800})
        self.assertEqual(status, 200); self.assertTrue(body["granted"]); self.assertEqual(body["stopped_now"][0]["pid"], 4242)
        self.assertEqual(self.process.terminated, 1)
        status, body = self.request(port, "GET", "/api/gpu-lease")
        self.assertEqual((status, body["held"], body["holder"], body["ttl_seconds"]), (200, True, "local-qwen", 1800))
        self.assertTrue(self.request(port, "GET", "/api/backends")[1]["gpu_lease"]["held"])
        status, body = self.request(port, "POST", "/api/jobs", {"preset_id": "demo", "controls": {}})
        self.assertEqual((status, body["code"], body["holder"]), (409, "gpu_leased", "local-qwen")); self.assertEqual(self.studio.jobs, {})
        status, body = self.request(port, "POST", "/api/gpu-lease", {"holder": "other-tool", "ttl_seconds": 600})
        self.assertEqual((status, body["code"]), (409, "lease_held"))
        self.assertEqual(self.request(port, "POST", "/api/gpu-lease", {"holder": "local-qwen"})[0], 400)
        status, body = self.request(port, "POST", "/api/gpu-lease/release", {"holder": "local-qwen"})
        self.assertEqual((status, body["released"], body["held"]), (200, True, False))
        self.assertEqual(self.studio.requests, [])

    def test_http_busy_queue_is_a_409_and_mutations_keep_the_loopback_origin_guard(self):
        port = self.serve(); inert_backends(self.studio, self.process, queue_busy=True)
        status, body = self.request(port, "POST", "/api/gpu-lease", {"holder": "local-qwen", "ttl_seconds": 600})
        self.assertEqual((status, body["code"]), (409, "backend_not_idle")); self.assertEqual(self.process.terminated, 0)
        for headers in ({"Origin": "http://evil.invalid"}, {"Host": "evil.invalid:8191"}, {"Origin": ""}):
            with self.subTest(headers=headers):
                self.assertEqual(self.request(port, "POST", "/api/gpu-lease", {"holder": "local-qwen", "ttl_seconds": 600}, headers)[0], 403)
        self.assertEqual(self.request(port, "GET", "/api/gpu-lease", headers={"Host": "evil.invalid:8191"})[0], 403)
        self.assertEqual(self.process.terminated, 0); self.assertFalse(self.studio.gpu_lease.snapshot()["held"])


if __name__ == "__main__":
    unittest.main()
