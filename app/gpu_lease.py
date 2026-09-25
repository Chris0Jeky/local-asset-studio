"""A bounded, loopback-only GPU lease that pauses Studio-owned ComfyUI for another local GPU tenant (issue #805).

A holder such as the local Qwen loader (local-llm-ops) asks the Studio to stop its own idle ComfyUI and keep it stopped
for a mandatory, bounded time-to-live. While the lease is held, runtime recovery does not relaunch the backend, backend
switches and new Studio generations are refused, and the worker never posts a prompt. Release or expiry hands the GPU
back: runtime recovery (when enabled) starts the selected backend on its next pass with its configured arguments.

The lease stops only processes this Studio can prove it launched, and only after the same idle checks a backend switch
uses: no queued, running or uncertain Studio work and an empty running+pending ComfyUI queue on every endpoint. It adds
no authentication: like every Studio mutation it relies on the loopback bind, the loopback Host check and the
same-origin Origin check.
"""
from __future__ import annotations

import json
import math
import re
import threading
import time

MIN_TTL_SECONDS = 60
MAX_TTL_SECONDS = 4 * 3600
STOP_WAIT_SECONDS = 15
HOLDER_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")


class GpuLeaseError(ValueError):
    """A refused lease command, or a Studio action refused because the GPU is leased. `stopped_processes` lists any stop that already happened."""

    def __init__(self, message, *, status=409, code="gpu_lease_refused", **details):
        super().__init__(message)
        self.status = status; self.code = code; self.details = details

    def response(self):
        return {"error": str(self), "code": self.code, **self.details}


def _stamp(seconds):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds))


class GpuLease:
    def __init__(self, studio, clock=time.time):
        self.studio = studio; self.clock = clock; self.lock = threading.RLock()
        self.path = studio.root / ".runtime" / "studio-gpu-lease.json"
        self.log_path = studio.root / ".runtime" / "studio-gpu-lease.log"
        self.record = None; self.last_release = None
        try: saved = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError): saved = None
        if isinstance(saved, dict):
            record = saved.get("record"); last = saved.get("last_release")
            if isinstance(last, dict): self.last_release = last
            # A lease survives a Studio restart so a restarted monitor cannot relaunch ComfyUI under a live holder.
            if self._valid_record(record): self.record = record
        with self.lock: self._expire()

    @staticmethod
    def _valid_record(record):
        if not isinstance(record, dict) or not isinstance(record.get("holder"), str) or not HOLDER_PATTERN.fullmatch(record["holder"]): return False
        expires = record.get("expires_at")
        return isinstance(expires, (int, float)) and not isinstance(expires, bool) and math.isfinite(expires)

    def _save(self):
        self.studio._write_json_atomic(self.path, {"record": self.record, "last_release": self.last_release})

    def _log(self, event, **details):
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as log:
                log.write(json.dumps({"at": self.clock(), "event": event, **details}, sort_keys=True, default=str) + "\n")
        except OSError: pass  # the state file is the authority; the log is an audit convenience

    def _expire(self):
        if self.record and self.clock() >= self.record["expires_at"]:
            holder = self.record["holder"]
            self.last_release = {"holder": holder, "reason": "expired", "at": self.clock(), "expires_at": self.record["expires_at"]}
            self.record = None; self._save(); self._log("expired", holder=holder)

    def active(self):
        """The current lease record (a copy), or None once it was released or its TTL passed."""
        with self.lock:
            self._expire()
            return dict(self.record) if self.record else None

    def refusal(self):
        """A human-readable reason Studio must not use the GPU now, or None."""
        record = self.active()
        if not record: return None
        remaining = max(0, int(record["expires_at"] - self.clock()))
        return (f"The GPU is leased to {record['holder']} until {_stamp(record['expires_at'])} ({remaining} s left); "
                "ComfyUI is paused. Nothing was submitted. Retry after the holder releases the lease or it expires")

    def require_available(self):
        record = self.active()
        if record:
            raise GpuLeaseError(self.refusal(), code="gpu_leased", holder=record["holder"], expires_at=record["expires_at"])

    def snapshot(self):
        with self.lock:
            self._expire()
            record = dict(self.record) if self.record else None
            recovery = getattr(self.studio, "runtime_recovery", None)
            result = {"held": record is not None, "holder": None, "acquired_at": None, "renewed_at": None, "expires_at": None,
                      "expires_at_utc": None, "ttl_seconds": None, "remaining_seconds": None, "stopped_processes": [],
                      "last_release": dict(self.last_release) if self.last_release else None,
                      "limits": {"min_ttl_seconds": MIN_TTL_SECONDS, "max_ttl_seconds": MAX_TTL_SECONDS},
                      "relaunch_on_release": "automatic" if getattr(recovery, "enabled", False) else "manual",
                      "access": "loopback only: Host 127.0.0.1:8191 or localhost:8191, same-origin Origin for mutations; no authentication"}
            if record:
                result.update({k: record.get(k) for k in ("holder", "acquired_at", "renewed_at", "expires_at", "ttl_seconds")})
                result["stopped_processes"] = list(record.get("stopped_processes", []))
                result["expires_at_utc"] = _stamp(record["expires_at"])
                result["remaining_seconds"] = max(0.0, round(record["expires_at"] - self.clock(), 1))
            return result

    @staticmethod
    def _holder(payload, allowed):
        if not isinstance(payload, dict): raise GpuLeaseError("A JSON object is required", status=400, code="invalid_lease_request")
        unknown = sorted(set(payload) - set(allowed))
        if unknown: raise GpuLeaseError("Unknown lease fields: " + ", ".join(unknown), status=400, code="invalid_lease_request")
        holder = payload.get("holder")
        if not isinstance(holder, str) or not HOLDER_PATTERN.fullmatch(holder):
            raise GpuLeaseError("holder must be 1-64 characters of a-z, 0-9, '.', '_' or '-', starting with a letter or digit",
                                status=400, code="invalid_lease_request")
        return holder

    def acquire(self, payload):
        """Stop verified-idle Studio-owned ComfyUI processes and hold the GPU for `ttl_seconds`; the same holder renews."""
        holder = self._holder(payload, ("holder", "ttl_seconds"))
        ttl = payload.get("ttl_seconds")
        if type(ttl) is not int or not MIN_TTL_SECONDS <= ttl <= MAX_TTL_SECONDS:
            raise GpuLeaseError(f"ttl_seconds is required: a whole number from {MIN_TTL_SECONDS} to {MAX_TTL_SECONDS}",
                                status=400, code="invalid_lease_request")
        manager = self.studio.backends
        # Studio's lock first, as everywhere else: no Studio job, switch or recovery launch can start while this runs.
        with self.studio.lock, self.lock:
            self._expire()
            if self.record and self.record["holder"] != holder:
                raise GpuLeaseError(f"The GPU is already leased to {self.record['holder']}", code="lease_held",
                                    holder=self.record["holder"], expires_at=self.record["expires_at"])
            if manager.busy: raise GpuLeaseError("A backend switch is running; nothing was stopped", code="backend_switch_active")
            if manager._local_work():
                raise GpuLeaseError("Studio has queued, running or unreconciled work; nothing was stopped", code="studio_work_active")
            try:
                manager._check_retained_startup(); manager._check_startup_processes()
                # Every endpoint, including work submitted directly through ComfyUI: running+pending must be empty.
                for profile in manager.profiles.values(): manager._idle(profile, allow_offline=True)
                manager._stopped_results()
                targets = [(key, profile, manager.process(profile)) for key, profile in manager.profiles.items()]
            except ValueError as exc:
                raise GpuLeaseError(str(exc)[:400] + ". Nothing was stopped", code="backend_not_idle") from exc
            stopped = []
            for key, profile, process in targets:
                if process is None: continue
                try:
                    manager._idle(profile)  # recheck just before termination, as a backend switch does
                    identity = {"profile": key, "pid": process.pid, "created_at": process.create_time(), "entry": profile["entry"]}
                except ValueError as exc:
                    raise GpuLeaseError(str(exc)[:400] + ". Processes already stopped: " + json.dumps(stopped), code="backend_not_idle",
                                        stopped_processes=stopped) from exc
                except Exception as exc:
                    raise GpuLeaseError("ComfyUI process identity could not be re-read; it was preserved: " + str(exc)[:200],
                                        code="backend_not_idle", stopped_processes=stopped) from exc
                try: process.terminate(); process.wait(timeout=STOP_WAIT_SECONDS)
                except Exception as exc:
                    # Termination may still complete later; the lease is not granted, so the holder must not load.
                    self._log("stop-unconfirmed", holder=holder, process=identity, error=str(exc)[:200])
                    raise GpuLeaseError(f"{profile['name']} did not confirm exit within {STOP_WAIT_SECONDS} s; the lease was not granted",
                                        status=500, code="stop_unconfirmed", stopped_processes=stopped) from exc
                stopped.append(identity)
            now = self.clock(); renewed = self.record is not None
            record = dict(self.record) if renewed else {"holder": holder, "acquired_at": now, "stopped_processes": []}
            record.update(renewed_at=now if renewed else None, ttl_seconds=ttl, expires_at=now + ttl)
            record["stopped_processes"] = record.get("stopped_processes", []) + stopped
            self.record = record; self._save()
            self._log("renewed" if renewed else "granted", holder=holder, ttl_seconds=ttl, stopped_processes=stopped)
            return dict(self.snapshot(), granted=True, renewed=renewed, stopped_now=stopped)

    def release(self, payload):
        """Release by the holder; idempotent when nothing is held. Relaunch stays with runtime recovery."""
        holder = self._holder(payload, ("holder",))
        with self.lock:
            self._expire()
            if not self.record: return dict(self.snapshot(), released=False)
            if self.record["holder"] != holder:
                raise GpuLeaseError(f"The GPU is leased to {self.record['holder']}, not {holder}", code="lease_held",
                                    holder=self.record["holder"], expires_at=self.record["expires_at"])
            self.last_release = {"holder": holder, "reason": "released", "at": self.clock(), "expires_at": self.record["expires_at"]}
            self.record = None; self._save(); self._log("released", holder=holder)
            return dict(self.snapshot(), released=True)
