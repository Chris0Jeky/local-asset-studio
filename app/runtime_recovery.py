"""Bounded, opt-in recovery for the selected local ComfyUI backend.

This is deliberately narrower than BackendManager.switch: recovery never changes
backend family, stops no process, scans no ports, and never submits a prompt.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

from backend_contracts import connection_refused, endpoint_ready

REFUSAL_PROBE_TIMEOUT = 3


class RuntimeRecovery:
    """Observe one configured backend and, only when opted in, restart a dead one."""

    def __init__(self, studio):
        self.studio = studio
        config = studio.config
        self.enabled = config.get("runtime_auto_recover") is True
        self.autostart = config.get("runtime_recovery_autostart", True) is True
        self.interval = self._number(config.get("runtime_recovery_poll_seconds", 15), 2, 300, 15)
        self.backoff = self._number(config.get("runtime_recovery_backoff_seconds", 30), 2, 3600, 30)
        self.startup_timeout = self._number(config.get("runtime_recovery_startup_timeout_seconds", 120), 10, 1800, 120)
        self.max_attempts = int(self._number(config.get("runtime_recovery_max_attempts", 3), 1, 10, 3))
        self.path = studio.root / ".runtime" / "runtime-recovery.json"
        self.log_path = studio.root / ".runtime" / "runtime-recovery.log"
        self.lock = threading.Lock()
        # Cache observations are local to this monitor session, never launch authority.
        self._schema_endpoint_identity = None
        self._schema_process_identity = None
        self.state = {"status": "disabled" if not self.enabled else "idle", "attempts": 0, "events": []}
        if self.enabled:
            try:
                saved = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(saved, dict): self.state.update({k: v for k, v in saved.items() if k != "events"})
            except (OSError, ValueError):
                pass
            if self.state.get("status") == "healthy":
                self.state.update(
                    status="checking",
                    message="Saved health is historical; waiting for a current endpoint observation.",
                )
        if self.enabled and self.autostart:
            self.thread = threading.Thread(target=self._monitor, daemon=True, name="studio-runtime-recovery")
            self.thread.start()

    @staticmethod
    def _number(value, low, high, fallback):
        try: value = float(value)
        except (TypeError, ValueError): return fallback
        return value if low <= value <= high else fallback

    def snapshot(self):
        result = dict(self.state)
        result["enabled"] = self.enabled
        result["active_backend"] = self.studio.backends.active
        return result

    def _record(self, status, message, **extra):
        now = time.time()
        self.state.update(status=status, message=message, updated_at=now, **extra)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.studio._write_json_atomic(self.path, self.state)
        # The state file carries freshness; the log records changes, not every identical poll.
        event = {"status": status, "message": message, **extra}
        if event == getattr(self, "_last_event", None): return
        with self.log_path.open("a", encoding="utf-8") as log:
            log.write(json.dumps({"at": now, **event}, sort_keys=True, default=str) + "\n")
        self._last_event = json.loads(json.dumps(event, sort_keys=True, default=str))  # only after the line is written

    def reset(self):
        """An explicit same-origin retry only clears the breaker; it cannot switch families."""
        with self.lock:
            self.state.pop("breaker_until", None)
            self.state.pop("startup_pid", None)
            self.state.pop("startup_at", None)
            self.state["attempts"] = 0
            self._last_event = None  # an explicit operator action is always logged, even when repeated
            self._record("idle", "Recovery breaker reset. The configured monitor will re-observe the selected backend.")
            return self.snapshot()

    def _monitor(self):
        # A failed probe is never a reason to spin; each pass is bounded by interval/backoff.
        while True:
            try: self.tick()
            except Exception as exc:
                with self.lock: self._record("blocked", "Recovery monitor observation failed: " + str(exc)[:200])
            time.sleep(self.interval)

    def _leased(self):
        lease = getattr(self.studio, "gpu_lease", None)
        record = lease.active() if lease else None
        if not record: return None
        return (f"ComfyUI is paused: the GPU is leased to {record['holder']} until "
                f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(record['expires_at']))}. Recovery resumes after release or expiry.")

    def _fresh_work(self):
        if getattr(self.studio, "reference_jobs", None) and self.studio.reference_jobs.busy(): return True
        # Retained uncertain records intentionally do not suppress recovery of a truly dead runtime.
        jobs = list(self.studio.jobs.values())
        if any(job.get("status") in ("queued", "waiting", "submitting", "running") for job in jobs): return True
        return any(item.get("state", {}).get("status") in ("queued", "running", "observing") for item in self.studio.production.list())

    @staticmethod
    def _identity(profile, stats, process=None):
        system = stats.get("system") if isinstance(stats, dict) else None
        if not isinstance(system, dict): return None
        stable_system = {key: system[key] for key in (
            "os", "comfyui_version", "required_frontend_version", "installed_frontend_version",
            "python_version", "pytorch_version", "embedded_python", "argv",
        ) if key in system}
        stable_devices = []
        for device in stats.get("devices", []):
            if isinstance(device, dict):
                stable_devices.append({key: device[key] for key in ("name", "type", "index") if key in device})
        observed = {"backend": profile.get("id"), "url": profile.get("url"), "system": stable_system, "devices": stable_devices}
        if process is not None:
            try: pid, created_at = process.pid, process.create_time()
            except Exception:
                # Process identity is optional enrichment. Never guess it from a partial observation.
                pass
            else:
                if isinstance(pid, int) and not isinstance(pid, bool) and isinstance(created_at, (int, float)) and not isinstance(created_at, bool):
                    observed["process"] = {"pid": pid, "created_at": created_at}
        return hashlib.sha256(json.dumps(observed, sort_keys=True, default=str).encode()).hexdigest()

    def _ready(self, profile, stats):
        try: process = self.studio.backends.process(profile)
        except (OSError, ValueError): process = None
        endpoint = self._identity(profile, stats)
        identity = self._identity(profile, stats, process)
        observed_process = identity if identity != endpoint else None
        continuous = self.state.get("status") == "healthy" and endpoint == self._schema_endpoint_identity
        changed_process = (observed_process is not None and self._schema_process_identity is not None
                           and observed_process != self._schema_process_identity)
        if not continuous or changed_process:
            self.studio._schema = None
            self.studio._schema_at = 0
        # Missing optional metadata is not a process change. Retain the last
        # observation only for comparison with a later *observed* identity.
        # Reconnects/endpoints reset it; snapshots still report current evidence.
        if not continuous: self._schema_process_identity = None
        if observed_process is not None: self._schema_process_identity = observed_process
        self._schema_endpoint_identity = endpoint
        for key in ("startup_pid", "startup_at", "breaker_until"):
            self.state.pop(key, None)
        self._record("healthy", "Selected backend is healthy.", endpoint_identity=identity, attempts=0)

    def tick(self):
        """One monitor pass. It is invoked only by the opt-in monitor or its tests."""
        with self.lock:
            manager = self.studio.backends
            profile = manager.profiles[manager.active]
            now = time.time()
            if manager.busy:
                self._record("reconnecting", "Backend switch is active; recovery is waiting.")
                return self.snapshot()
            leased = self._leased()
            if leased:
                self._record("leased", leased)
                return self.snapshot()
            ready = False
            try:
                # Windows can surface a one-second urllib timeout before it reports
                # the connection refusal that authorizes a bounded recovery launch.
                stats = manager.request(profile, "/system_stats", REFUSAL_PROBE_TIMEOUT)
                ready = endpoint_ready(stats)
                error = ValueError("Endpoint did not return a ready system payload")
            except (OSError, ValueError) as exc:
                error = exc

            # A GPU lease (app/gpu_lease.py) paused this backend on purpose: never relaunch it under the holder.
            leased = self._leased()
            if leased:
                self._record("leased", leased)
                return self.snapshot()

            if ready:
                self._ready(profile, stats)
                return self.snapshot()

            # A listener that cannot be proven to be this exact launcher is a hard stop.
            try:
                listener = manager.process(profile)
                matching = manager.configured_processes(profile)
            except ValueError as exc:
                self._record("foreign-or-ambiguous-listener", str(exc))
                return self.snapshot()

            startup_pid = self.state.get("startup_pid")
            if isinstance(startup_pid, int) and any(process.pid == startup_pid for process in matching):
                if now - float(self.state.get("startup_at", now)) < self.startup_timeout:
                    self._record("startup", "Recovery-started process is still loading; it is retained.")
                    return self.snapshot()
                self._open_breaker("Startup timed out; process is preserved for inspection.")
                return self.snapshot()
            if matching or listener:
                self._record("unreachable-but-alive", "Configured backend process is alive but endpoint is unavailable; it was preserved.")
                return self.snapshot()
            if not connection_refused(error):
                self._record("unreachable", "Endpoint is unavailable without proof of a dead backend; no start was attempted.")
                return self.snapshot()
            if self._fresh_work():
                self._record("crashed-absent-busy", "Backend appears absent, but fresh Studio work exists; recovery will not start it.")
                return self.snapshot()
            if not self.enabled:
                self._record("crashed-absent", "Selected backend appears absent. Automatic recovery is disabled.")
                return self.snapshot()
            if now < float(self.state.get("breaker_until", 0)):
                self._record("breaker-open", "Recovery attempts are paused after bounded failures.")
                return self.snapshot()
            if int(self.state.get("attempts", 0)) >= self.max_attempts:
                self._open_breaker("Recovery attempt limit reached; inspect retained logs before reset.")
                return self.snapshot()
            if not manager.available(profile):
                self._record("blocked", "Selected backend is not installed completely: " + manager.readiness(profile)["message"])
                return self.snapshot()

            # Recheck every launch predicate while holding Studio's existing interlock.
            with self.studio.lock:
                if manager.active != profile['id'] or manager.busy or self._leased() or self._fresh_work() or manager.process(profile) or manager.configured_processes(profile):
                    self._record("reconnecting", "Recovery launch conditions changed; no process was started.")
                    return self.snapshot()
                pid = manager.launch_recovery(profile)
            self._record("startup", "Started the selected configured backend; waiting for its read-only health endpoint.",
                         startup_pid=pid, startup_at=now, attempts=int(self.state.get("attempts", 0)) + 1)
            return self.snapshot()

    def _open_breaker(self, message):
        self._record("breaker-open", message, breaker_until=time.time() + self.backoff)
