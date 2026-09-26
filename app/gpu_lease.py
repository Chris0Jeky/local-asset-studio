"""A bounded, loopback-only GPU lease that pauses Studio-owned ComfyUI for another local GPU tenant (issue #805).

A holder such as the local Qwen loader (local-llm-ops) asks the Studio to stop its own idle ComfyUI and keep it stopped
for a mandatory, bounded time-to-live. While the lease is held, runtime recovery does not relaunch the backend, backend
switches and new Studio generations are refused, and the worker never posts a prompt. Release or expiry hands the GPU
back: runtime recovery (when enabled) starts the selected backend on its next pass with its configured arguments.

The lease stops only processes this Studio can prove it launched, and only after the same idle checks a backend switch
uses: no queued, running or uncertain Studio work and an empty running+pending ComfyUI queue on every endpoint. One exception
applies to the lease alone (#979): an 'uncertain' job with no recorded activity for STALE_UNCERTAIN_SECONDS no longer blocks
a grant; its prompt IDs still get the in-memory history check, and the grant names it in `ignored_stale_uncertain`. It adds
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
# An 'uncertain' job idle this long no longer blocks a lease grant (owner decision 2026-09-25, #979). Nothing about the
# job changes: it stays 'uncertain', resumable and blocking for backend switches and every other admission path.
STALE_UNCERTAIN_SECONDS = 24 * 3600


def _finite(value):
    try: return type(value) in (int, float) and math.isfinite(value)
    except OverflowError: return False  # an int too large for a float is not a usable time


def last_activity(job):
    """The latest time a job record says anything happened to it, or None when it carries no finite time.

    Reads creation, start, finish, the pending-submission marker and every tracking stop/resume event. The owner's
    put-away acknowledgement is not activity: it records that someone looked, not that work moved."""
    stamps = [job.get(key) for key in ("created_at", "started_at", "finished_at")]
    pending = job.get("pending_submission")
    if isinstance(pending, dict): stamps.append(pending.get("marked_at"))
    disposition = job.get("tracking_disposition")
    if isinstance(disposition, dict):
        stamps.append(disposition.get("recorded_at"))
        history = disposition.get("history")
        if isinstance(history, list): stamps.extend(event.get("recorded_at") for event in history if isinstance(event, dict))
    stamps = [stamp for stamp in stamps if _finite(stamp)]
    return max(stamps) if stamps else None


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
            if self._valid_record(record):
                # Persist the absolute cap once: repeated restarts must not extend it.
                ceiling = self.clock() + MAX_TTL_SECONDS
                if record["expires_at"] > ceiling:
                    record = dict(record, expires_at=ceiling)
                    self._save(record, self.last_release)
                else: self.record = record
        with self.lock: self._expire()

    @staticmethod
    def _valid_record(record):
        if not isinstance(record, dict) or not isinstance(record.get("holder"), str) or not HOLDER_PATTERN.fullmatch(record["holder"]): return False
        expires = record.get("expires_at")
        return type(expires) is int or (type(expires) is float and math.isfinite(expires))

    def _save(self, record, last_release):
        # Durable state is authoritative; a failed write cannot publish a transition.
        self.studio._write_json_atomic(self.path, {"record": record, "last_release": last_release})
        self.record = record; self.last_release = last_release

    def _log(self, event, **details):
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as log:
                log.write(json.dumps({"at": self.clock(), "event": event, **details}, sort_keys=True, default=str) + "\n")
        except OSError: pass  # the state file is the authority; the log is an audit convenience

    def _expire(self):
        if self.record and self.clock() >= self.record["expires_at"]:
            holder = self.record["holder"]
            last = {"holder": holder, "reason": "expired", "at": self.clock(), "expires_at": self.record["expires_at"]}
            self._save(None, last); self._log("expired", holder=holder)

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
                      "limits": {"min_ttl_seconds": MIN_TTL_SECONDS, "max_ttl_seconds": MAX_TTL_SECONDS,
                                 "stale_uncertain_seconds": STALE_UNCERTAIN_SECONDS},
                      "relaunch_on_release": "automatic" if getattr(recovery, "enabled", False) else "manual",
                      "access": "loopback only: Host 127.0.0.1:8191 or localhost:8191, same-origin Origin for mutations; no authentication"}
            if record:
                result.update({k: record.get(k) for k in ("holder", "acquired_at", "renewed_at", "expires_at", "ttl_seconds")})
                result["stopped_processes"] = list(record.get("stopped_processes", []))
                result["expires_at_utc"] = _stamp(record["expires_at"])
                result["remaining_seconds"] = max(0.0, round(record["expires_at"] - self.clock(), 1))
            return result

    def stale_uncertain(self, now):
        """Sorted ids of 'uncertain' jobs whose last activity is at least STALE_UNCERTAIN_SECONDS before `now`.

        A record with no finite time, or one dated in the future, is not stale. A stopped-tracking record is left out: it
        never blocks, so the age rule does not change anything for it."""
        stale = []
        for job in list(getattr(self.studio, "jobs", {}).values()):
            if not isinstance(job, dict) or job.get("status") != "uncertain" or type(job.get("id")) is not str: continue
            disposition = job.get("tracking_disposition")
            if isinstance(disposition, dict) and disposition.get("status") == "stopped": continue
            last = last_activity(job)
            if last is not None and now - last >= STALE_UNCERTAIN_SECONDS: stale.append(job["id"])
        return sorted(stale)

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
            if self.record:
                now = self.clock()
                record = dict(self.record, renewed_at=now, ttl_seconds=ttl, expires_at=now + ttl)
                self._save(record, self.last_release)
                self._log("renewed", holder=holder, ttl_seconds=ttl, stopped_processes=[])
                return dict(self.snapshot(), granted=True, renewed=True, stopped_now=[], ignored_stale_uncertain=[])
            if manager.busy: raise GpuLeaseError("A backend switch is running; nothing was stopped", code="backend_switch_active")
            # Only the lease ages out old 'uncertain' records; the manager re-reads each status, so one resumed since is not exempt.
            stale = tuple(self.stale_uncertain(self.clock()))
            if manager._local_work(ignore_job_ids=stale):
                raise GpuLeaseError("Studio has queued, running or unreconciled work; nothing was stopped", code="studio_work_active",
                                    ignored_stale_uncertain=list(stale))
            try:
                manager._check_retained_startup(); manager._check_startup_processes()
                # Every endpoint, including work submitted directly through ComfyUI: running+pending must be empty.
                for profile in manager.profiles.values(): manager._idle(profile, allow_offline=True)
                manager._stopped_results(extra_job_ids=stale)
                targets = [(key, profile, manager.process(profile)) for key, profile in manager.profiles.items()]
            except ValueError as exc:
                raise GpuLeaseError(str(exc)[:400] + ". Nothing was stopped", code="backend_not_idle") from exc
            stopped = []
            def checked_identity(key, profile, process):
                try:
                    manager._idle(profile)
                    return {"profile": key, "pid": process.pid, "created_at": process.create_time(), "entry": profile["entry"]}
                except ValueError as exc:
                    raise GpuLeaseError(str(exc)[:400] + ". Processes already stopped: " + json.dumps(stopped), code="backend_not_idle",
                                        stopped_processes=stopped) from exc
                except Exception as exc:
                    raise GpuLeaseError("ComfyUI process identity could not be re-read; it was preserved: " + str(exc)[:200],
                                        code="backend_not_idle", stopped_processes=stopped) from exc
            # Finish every strict idle/identity check before the first physical
            # stop. Keep the immediate checks too: external work can still race.
            for key, profile, process in targets:
                if process is not None: checked_identity(key, profile, process)
            for key, profile, process in targets:
                if process is None: continue
                identity = checked_identity(key, profile, process)
                try: process.terminate(); process.wait(timeout=STOP_WAIT_SECONDS)
                except Exception as exc:
                    # Termination may still complete later; the lease is not granted, so the holder must not load.
                    self._log("stop-unconfirmed", holder=holder, process=identity, error=str(exc)[:200])
                    raise GpuLeaseError(f"{profile['name']} did not confirm exit within {STOP_WAIT_SECONDS} s; the lease was not granted",
                                        status=500, code="stop_unconfirmed", stopped_processes=stopped) from exc
                stopped.append(identity)
            now = self.clock()
            record = {"holder": holder, "acquired_at": now, "stopped_processes": stopped,
                      "renewed_at": None, "ttl_seconds": ttl, "expires_at": now + ttl}
            self._save(record, self.last_release)
            self._log("granted", holder=holder, ttl_seconds=ttl, stopped_processes=stopped, ignored_stale_uncertain=list(stale))
            return dict(self.snapshot(), granted=True, renewed=False, stopped_now=stopped, ignored_stale_uncertain=list(stale))

    def release(self, payload):
        """Release by the holder; idempotent when nothing is held. Relaunch stays with runtime recovery."""
        holder = self._holder(payload, ("holder",))
        with self.lock:
            self._expire()
            if not self.record: return dict(self.snapshot(), released=False)
            if self.record["holder"] != holder:
                raise GpuLeaseError(f"The GPU is leased to {self.record['holder']}, not {holder}", code="lease_held",
                                    holder=self.record["holder"], expires_at=self.record["expires_at"])
            last = {"holder": holder, "reason": "released", "at": self.clock(), "expires_at": self.record["expires_at"]}
            self._save(None, last); self._log("released", holder=holder)
            return dict(self.snapshot(), released=True)
