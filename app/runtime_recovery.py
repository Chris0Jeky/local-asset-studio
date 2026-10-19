"""Bounded, opt-in recovery for the selected local ComfyUI backend.

This is deliberately narrower than BackendManager.switch: recovery never changes
backend family, stops no process, scans no ports, and never submits a prompt.
"""
from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
import uuid
from pathlib import Path

from backend_contracts import connection_refused, endpoint_ready
import backend_state
import recovery_state

REFUSAL_PROBE_TIMEOUT = 3
DEFAULT_PORT = 8191


class RuntimeRecovery:
    """Observe one configured backend and, only when opted in, restart a dead one."""

    def __init__(self, studio):
        self.studio = studio
        config = studio.config
        self.enabled = config.get("runtime_auto_recover") is True
        # Only the Studio on the default port owns recovery; a preview on another --port needs an explicit true (#1584).
        self.autostart = config.get("runtime_recovery_autostart", getattr(studio, "port", DEFAULT_PORT) == DEFAULT_PORT) is True
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
        self._hold_reason = None
        self._pending_attempt = None
        self._retained_state_issue = None
        self._log_error = None
        self.state = {"status": "disabled" if not self.enabled else "idle", "attempts": 0, "events": []}
        if self.enabled:
            try:
                saved = recovery_state.read(self.path)
                if saved is not None:
                    # Preserve the original evidence before even historical health
                    # normalization can replace a status-only legacy signal.
                    legacy = recovery_state.legacy_attempt(saved)
                    if legacy is not None: saved['legacy_attempt'] = legacy
                    self.state.update({k: v for k, v in saved.items() if k != "events"})
                    if saved.get('last_attempt') or saved.get('legacy_attempt'):
                        self._hold_reason = ('Saved recovery attempt evidence is historical. Inspect the configured runtime and '
                                             'runtime-recovery.log, then use Reset recovery; a current healthy observation also clears this hold.')
            except (OSError, ValueError, RecursionError) as exc:
                self._retained_state_issue = ('Cannot read retained recovery state: ' + str(exc)[:200] + '. Preserve the record and '
                                             'runtime-recovery.log for inspection. With Studio stopped, copy and repair or move '
                                             'the invalid runtime-recovery.json, then restart Studio. Reset recovery cannot overwrite it.')
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
        result = copy.deepcopy(self.state)
        if self._pending_attempt is not None: result['last_attempt'] = copy.deepcopy(self._pending_attempt)
        if self._retained_state_issue or self._hold_reason:
            result.update(inspection_required=True, message=self._retained_state_issue or self._hold_reason)
            if self._retained_state_issue or result['status'] != 'checking': result['status'] = 'breaker-open'
        if self._log_error: result['log_error'] = self._log_error
        result["enabled"] = self.enabled
        result["active_backend"] = self.studio.backends.active
        return result

    def _record(self, status, message, *, _clear=(), _release=False, _force_log=False, **extra):
        if self._retained_state_issue: raise ValueError(self._retained_state_issue)
        now = time.time()
        candidate = copy.deepcopy(self.state)
        legacy = recovery_state.legacy_attempt(candidate)
        if legacy is not None: candidate['legacy_attempt'] = legacy
        if self._pending_attempt is not None:
            candidate['last_attempt'] = copy.deepcopy(self._pending_attempt)
            if not _release: candidate['attempts'] = max(candidate['attempts'], self._pending_attempt['number'])
        if self._hold_reason and not _release: candidate['launch_pending'] = True
        for key in _clear: candidate.pop(key, None)
        candidate.update(status=status, message=message, updated_at=now, **extra)
        try: recovery_state.publish(self.path, candidate)
        except Exception:
            self._hold_reason = ('Recovery state publication is unconfirmed. Inspect runtime-recovery.json, runtime-recovery.log '
                                 'and the configured runtime before Reset recovery; no further automatic start is allowed.')
            raise
        self.state = candidate
        if _release: self._hold_reason = None; self._pending_attempt = None
        # The state file carries freshness; the log records changes, not every identical poll.
        event = {"status": status, "message": message, "attempts": candidate['attempts'], **extra}
        if 'last_attempt' in candidate: event['last_attempt'] = copy.deepcopy(candidate['last_attempt'])
        if 'legacy_attempt' in candidate: event['legacy_attempt'] = copy.deepcopy(candidate['legacy_attempt'])
        if not _force_log and event == getattr(self, "_last_event", None) and not self._log_error: return
        try:
            line = json.dumps({"at": now, **event}, sort_keys=True, allow_nan=False) + "\n"
            with self.log_path.open("a", encoding="utf-8") as log:
                if log.write(line) != len(line): raise OSError('Recovery log append was incomplete')
                log.flush()
        except (OSError, UnicodeError) as exc:
            self._log_error = str(exc)[:200]
            return  # Diagnostic failure cannot undo the committed state or repeat a launch.
        self._last_event = copy.deepcopy(event)  # only after write, flush and close succeeded
        self._log_error = None

    def reset(self):
        """An explicit same-origin retry only clears the breaker; it cannot switch families."""
        with self.lock:
            if not self.enabled:
                raise ValueError('Recovery is disabled; Reset recovery is unavailable and the saved record was preserved.')
            self._record("idle", "Recovery breaker reset. The configured monitor will re-observe the selected backend.",
                         _clear=('breaker_until', 'startup_pid', 'startup_at', 'launch_pending'),
                         _release=True, _force_log=True, attempts=0)
            return self.snapshot()

    def _monitor(self):
        # A failed probe is never a reason to spin; each pass is bounded by interval/backoff.
        while True:
            try: self.tick()
            except Exception as exc:
                with self.lock:
                    try: self._record("blocked", "Recovery monitor observation failed: " + str(exc)[:200])
                    except Exception: pass  # A failed diagnostic write must still reach the bounded wait.
            time.sleep(self.interval)

    def _leased(self):
        lease = getattr(self.studio, "gpu_lease", None)
        record = lease.active() if lease else None
        if not record: return None
        return (f"ComfyUI is paused: the GPU is leased to {record['holder']} until "
                f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(record['expires_at']))}. Recovery resumes after release or expiry.")

    def _other_backend(self, profile, *, probe=True):
        """Explain any shared selection, switch or unproven alternate runtime that blocks a launch.

        The final interlock repeats the shared-state and process checks with probe=False;
        bounded network observations stay outside Studio's lock.
        """
        manager = self.studio.backends
        if getattr(manager, 'state_issue', None): return 'Shared backend state requires inspection: ' + manager.state_issue
        try: state = backend_state.read(getattr(manager, 'state_path', self.studio.root / '.runtime/backend-state.json')).value
        except backend_state.StateError as exc: return 'Shared backend state requires inspection: ' + str(exc)
        reason = backend_state.blocker(state)
        if reason: return reason
        saved = state.get('active')
        if saved and saved not in manager.profiles: return 'Shared backend state selects an unknown environment; inspect the saved selection.'
        if isinstance(saved, str) and saved in manager.profiles and saved != profile["id"]:
            return (f"Shared backend state selects '{saved}', while this Studio still selects '{profile['id']}'. "
                    "If that backend has stopped, select the intended environment explicitly in Models & setup, "
                    "or restart this Studio to follow the saved selection. Reset recovery does not change the selection.")
        for other in manager.profiles.values():
            if other["id"] == profile["id"]: continue
            if probe:
                try: stats = manager.request(other, "/system_stats", REFUSAL_PROBE_TIMEOUT)
                except (OSError, ValueError) as exc:
                    if not connection_refused(exc):
                        return f"Backend '{other['id']}' health is unknown after a failed probe; inspect it in Models & setup before switching explicitly."
                else:
                    if endpoint_ready(stats): return f"Backend '{other['id']}' is online; recovery will not start '{profile['id']}' over it."
                    return f"Backend '{other['id']}' health is unknown after an incomplete response; inspect it in Models & setup before switching explicitly."
            try:
                if manager.process(other) or manager.configured_processes(other):
                    return f"Backend '{other['id']}' still has a listener or configured process; recovery will not start '{profile['id']}' over it."
            except (OSError, ValueError):
                return f"Backend '{other['id']}' process ownership is unknown; inspect it in Models & setup before switching explicitly."
        return None

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
        self._record("healthy", "Selected backend is healthy.", endpoint_identity=identity, attempts=0,
                     _clear=('startup_pid', 'startup_at', 'breaker_until', 'launch_pending'), _release=True)
        if not continuous or changed_process:
            self.studio._schema = None
            self.studio._schema_at = 0
        # Missing optional metadata is not a process change. Retain the last
        # observation only for comparison with a later *observed* identity.
        # Reconnects/endpoints reset it; snapshots still report current evidence.
        if not continuous: self._schema_process_identity = None
        if observed_process is not None: self._schema_process_identity = observed_process
        self._schema_endpoint_identity = endpoint

    def tick(self):
        """One monitor pass. It is invoked only by the opt-in monitor or its tests."""
        with self.lock:
            if self._retained_state_issue: return self.snapshot()
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

            # Acquisition takes this same interlock before stopping a backend.
            # Keep the final lease check and health publication indivisible to it.
            with self.studio.lock:
                leased = self._leased()
                if leased:
                    self._record("leased", leased)
                    return self.snapshot()
                if ready:
                    if manager.active != profile['id'] or manager.busy:
                        self._record("reconnecting", "Backend changed during its health probe; recovery will re-observe it.")
                    else:
                        self._ready(profile, stats)
                    return self.snapshot()

            if self._hold_reason:
                self._record('breaker-open', self._hold_reason, launch_pending=True)
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
            with self.studio.lock:
                if manager.active != profile['id'] or manager.busy:
                    self._record("reconnecting", "Backend changed during its process scan; recovery will re-observe it.")
                    return self.snapshot()
            other = self._other_backend(profile)
            if other:
                self._record("other-backend-active", other)
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
                other = self._other_backend(profile, probe=False)
                if other:
                    self._record("other-backend-active", other)
                    return self.snapshot()
                # Charge one intent through the required barriers before the existing launcher.
                # An error at either publication or spawn retains this identity and closes
                # automatic launch allowance until fresh health or a published explicit reset.
                self._pending_attempt = {'version': 1, 'id': uuid.uuid4().hex, 'backend': profile['id'],
                                         'number': self.state['attempts'] + 1, 'at': time.time()}
                try:
                    self._record('launching', 'Recorded one recovery attempt; starting the selected configured backend.',
                                 launch_pending=True)
                    def on_spawn(pid): self._pending_attempt['pid'] = pid
                    pid = manager.launch_recovery(profile, on_spawn=on_spawn)
                    self._record("startup", "Started the selected configured backend; waiting for its read-only health endpoint.",
                                 startup_pid=pid, startup_at=time.time(), launch_pending=False)
                except Exception:
                    self._hold_reason = ('Recovery launch or its record is unconfirmed. Inspect the configured runtime, '
                                         'runtime-recovery.json and runtime-recovery.log before Reset recovery; no automatic retry is allowed.')
                    raise
                self._pending_attempt = None
            return self.snapshot()

    def _open_breaker(self, message):
        self._record("breaker-open", message, breaker_until=time.time() + self.backoff)
