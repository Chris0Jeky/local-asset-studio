"""Exact owned-process restart and response-loss reconciliation."""
from __future__ import annotations

from typing import Any

from backend_contracts import endpoint_ready, queue_is_idle
from large_job_prep_common import PreparationError, _number, _process_identity, _queue_summary


class LifecycleMixin:
    def _wait_for_restarted_backend(self, profile: dict[str, Any], launched_pid: int,
                                    old_identity: dict[str, Any]) -> dict[str, Any]:
        timeout = _number((getattr(self.studio, "config", {}) or {}).get(
            "large_job_restart_startup_timeout_seconds", 120), 1, 1800, 120)
        deadline = self.monotonic() + timeout
        last_error = "endpoint not ready"
        while self.monotonic() <= deadline:
            try:
                matching = self.studio.backends.configured_processes(profile)
                if len(matching) != 1:
                    raise PreparationError("Restarted backend ownership is ambiguous")
                configured_identity = _process_identity(matching[0])
                if configured_identity == old_identity or configured_identity["pid"] != launched_pid:
                    raise PreparationError("Newly online configured process is not the launched backend")
                listener = self.studio.backends.process(profile)
                if listener is None:
                    raise OSError("listener not bound")
                listener_identity = _process_identity(listener)
                if listener_identity != configured_identity:
                    raise PreparationError("Ready listener does not belong to the launched backend")
                stats = self.studio.backends.request(profile, "/system_stats", 3)
                if not endpoint_ready(stats):
                    raise OSError("system endpoint not ready")
                queue = self.studio.backends.request(profile, "/queue", 3)
                queue_is_idle(queue)
                return {
                    "profile_id": str(profile.get("id", ""))[:80],
                    "url": str(profile.get("url", ""))[:300],
                    "process": listener_identity,
                    "queue": _queue_summary(queue),
                }
            except PreparationError:
                raise
            except ValueError as exc:
                raise PreparationError("Restarted backend ownership or queue became invalid: " + str(exc)[:180]) from exc
            except Exception as exc:
                last_error = type(exc).__name__ + ": " + str(exc)[:160]
            remaining = deadline - self.monotonic()
            if remaining <= 0:
                break
            self.sleeper(min(1.0, remaining))
        raise PreparationError("Restarted backend did not become ready: " + last_error)

    def _restart(self, journal: dict[str, Any], receipt: dict[str, Any], context: dict[str, Any],
                 current: dict[str, Any]) -> dict[str, Any]:
        expected = current["backend"]["process"]
        backend, process = self._claim_backend(expected, current["backend"]["profile_id"],
                                               context.get("_history_absent", frozenset()))
        try:
            restarted = self._restart_held(journal, receipt, expected, backend, process)
        finally:
            # Released on readiness and on every failure; the snapshot below rechecks the gate.
            self._release_backend()

        # The restart already happened, so only in-flight work can still refuse readiness here.
        self._check_work("New Studio work arrived after restart; readiness was not granted")
        observation = self.observer(self.studio)
        evaluation = self._with_host_commit_floor(
            self._evaluate(context["workflow_identity"], context["_profile"], observation, context["reservations"]),
            observation, context.get("_host_commit_minimum_bytes"),
        )
        # #956: the final snapshot and work check are one Studio.lock-held
        # decision, so a concurrent switch cannot take backends.busy between them.
        # A job arriving during observation/evaluation would otherwise be missed
        # while the receipt still reports ready_after_restart. The restart already
        # happened, so only in-flight work can still refuse readiness here, and
        # this check runs after the gate release with no second terminate/launch.
        with self.studio.lock:
            final_backend, _ = self._backend_snapshot(
                expected_identity=restarted["process"], expected_profile_id=restarted["profile_id"]
            )
            self._check_work("Studio work changed while post-restart resources were being measured")
        return {"observation": observation, "evaluation": evaluation, "backend": final_backend}

    def _restart_held(self, journal: dict[str, Any], receipt: dict[str, Any], expected: dict[str, Any],
                      backend: dict[str, Any], process: Any) -> dict[str, Any]:
        profile = self.studio.backends.profiles[self.studio.backends.active]
        action = {
            "kind": "restart",
            "state": "terminate_intent_saved",
            "recorded_at": self.clock(),
            "old_process": expected,
            "queue": backend["queue"],
        }
        self._record_action(journal, receipt, action)
        try:
            process.terminate()
            process.wait(timeout=_number((getattr(self.studio, "config", {}) or {}).get(
                "large_job_restart_stop_timeout_seconds", 15), 1, 120, 15))
        except Exception as exc:
            # A wait failure is not proof that termination failed.  Re-observe;
            # only definitive absence permits the recovery launch below.
            try:
                listener = self.studio.backends.process(profile)
                matching = self.studio.backends.configured_processes(profile)
            except Exception as inspect_exc:
                action.update(state="termination_unknown", error=type(inspect_exc).__name__)
                self._persist(journal, receipt)
                raise PreparationError("Backend termination outcome is unknown; no launch was attempted") from exc
            if listener is not None or matching:
                action.update(state="termination_failed_or_alive", error=type(exc).__name__)
                self._persist(journal, receipt)
                raise PreparationError("Verified backend did not stop; it was preserved") from exc
        try:
            listener = self.studio.backends.process(profile)
            matching = self.studio.backends.configured_processes(profile)
        except Exception as exc:
            action.update(state="post_termination_identity_unknown", error=type(exc).__name__)
            self._persist(journal, receipt)
            raise PreparationError("Backend state after termination is unknown; no launch was attempted") from exc
        if listener is not None or matching:
            action.update(state="post_termination_process_present")
            self._persist(journal, receipt)
            raise PreparationError("A configured or listening process appeared after termination; no launch was attempted")
        action.update(state="terminated", terminated_at=self.clock())
        self._persist(journal, receipt)

        action.update(state="launch_intent_saved", launch_intent_at=self.clock())
        self._persist(journal, receipt)
        launched_pid: int | None = None
        attested_pid: int | None = None

        def _on_spawn(pid: Any) -> None:
            nonlocal attested_pid
            if type(pid) is int and pid > 0:
                attested_pid = pid
                action["attested_pid"] = pid

        try:
            launched_pid = self.studio.backends.launch_recovery(profile, on_spawn=_on_spawn)
        except Exception as exc:
            # Attested-launch reconciliation only: adopt a candidate after a lost
            # return when the same launch_recovery invocation attested its PID via
            # on_spawn immediately after spawn. A failure before attestation never
            # adopts a foreign listener; never call launch_recovery twice.
            if attested_pid is None:
                action.update(state="launch_unknown", error=type(exc).__name__)
                self._persist(journal, receipt)
                raise PreparationError("Backend launch outcome is unknown; retry is prohibited") from exc
            try:
                matching = self.studio.backends.configured_processes(profile)
                if len(matching) != 1:
                    launched_pid = None
                else:
                    candidate = _process_identity(matching[0])
                    if candidate != expected and candidate["pid"] == attested_pid:
                        launched_pid = candidate["pid"]
                    else:
                        launched_pid = None
            except Exception:
                launched_pid = None
            if launched_pid is None:
                action.update(state="launch_unknown", error=type(exc).__name__)
                self._persist(journal, receipt)
                raise PreparationError("Backend launch outcome is unknown; retry is prohibited") from exc
            action.update(launch_transport="lost_but_process_reconciled")
        if type(launched_pid) is not int or launched_pid <= 0:
            action.update(state="launch_invalid_identity")
            self._persist(journal, receipt)
            raise PreparationError("Backend launch returned an invalid process identity")
        action.update(state="launched_waiting", launched_pid=launched_pid)
        self._persist(journal, receipt)
        try:
            restarted = self._wait_for_restarted_backend(profile, launched_pid, expected)
        except PreparationError as exc:
            action.update(state="startup_failed", error=str(exc)[:220])
            self._persist(journal, receipt)
            raise
        action.update(state="ready", ready_at=self.clock(), new_process=restarted["process"])
        self._persist(journal, receipt)
        return restarted
