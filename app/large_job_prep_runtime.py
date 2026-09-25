"""Fail-closed Studio, queue, ownership and admission observations."""
from __future__ import annotations

import copy
from typing import Any

from backend_contracts import queue_is_idle
import resource_admission
from large_job_prep_common import (
    AT_REST_PRODUCTION_STATES, BLOCKS_ALL, BLOCKS_RESTART, IN_FLIGHT_JOB_STATES,
    IN_FLIGHT_PRODUCTION_STATES, TERMINAL_SUBMISSION_STATES, UNRESOLVED_JOB_STATES,
    UNRESOLVED_PRODUCTION_STATES, PreparationError, WorkBlockedError, _blocker_summary,
    _process_identity, _queue_summary,
)


class RuntimeMixin:
    def _work_blockers(self) -> list[dict[str, str]]:
        """Classify every Studio record as blocking all actions, only restart, or nothing."""
        blockers: list[dict[str, str]] = []

        def add(kind: str, identifier: Any, status: str, blocks: str) -> None:
            blockers.append({"kind": kind, "id": str(identifier)[:128], "status": status[:64], "blocks": blocks})

        jobs = getattr(self.studio, "jobs", {})
        if not isinstance(jobs, dict):
            raise PreparationError("Studio job state is unavailable")
        for identifier, job in jobs.items():
            if not isinstance(job, dict):
                raise PreparationError("Studio job state is invalid")
            status = str(job.get("status", "unknown"))
            submissions = job.get("submissions") or []
            open_submissions = [item for item in submissions if not isinstance(item, dict)
                                or item.get("status") not in TERMINAL_SUBMISSION_STATES] if isinstance(submissions, list) else [None]
            # A pending marker retained on a locally abandoned job is a terminal disposition (as for put-away).
            pending = job.get("pending_submission") is not None and status != "abandoned"
            # Only an observing receipt on an unresolved job at rest waits for Resume observation;
            # any other open submission may still be submitting.
            submitting = any(not isinstance(item, dict) or item.get("status") != "observing"
                             or status not in UNRESOLVED_JOB_STATES for item in open_submissions)
            if pending or status in IN_FLIGHT_JOB_STATES or submitting:
                add("studio_job", identifier, status, BLOCKS_ALL)
            elif status in UNRESOLVED_JOB_STATES or open_submissions:
                add("studio_job", identifier, status, BLOCKS_RESTART)
        reference_jobs = getattr(self.studio, "reference_jobs", None)
        if reference_jobs is not None:
            try:
                if reference_jobs.busy():
                    add("reference_job", "active", "busy_or_retained", BLOCKS_ALL)
            except Exception as exc:
                raise PreparationError("Reference-job state is unavailable") from exc
        production = getattr(self.studio, "production", None)
        if production is not None:
            try:
                items = production.list()
            except Exception as exc:
                raise PreparationError("Production state is unavailable") from exc
            if not isinstance(items, list):
                raise PreparationError("Production state is invalid")
            for item in items:
                if not isinstance(item, dict) or not isinstance(item.get("state"), dict):
                    raise PreparationError("Production state contains an invalid project record")
                state = item["state"]
                status = str(state.get("status", "unknown"))
                identifier = item.get("id", "unknown")
                if state.get("pending_submission") or status in IN_FLIGHT_PRODUCTION_STATES:
                    add("production", identifier, status, BLOCKS_ALL)
                elif status in UNRESOLVED_PRODUCTION_STATES:
                    add("production", identifier, status, BLOCKS_RESTART)
                elif status not in AT_REST_PRODUCTION_STATES:
                    add("production", identifier, status, BLOCKS_ALL)  # unrecognized: fail closed
        return blockers

    def _check_work(self, message: str, *, restart: bool = False) -> dict[str, Any]:
        """Refuse on in-flight work, and before a restart on unresolved work; return the summary."""
        blockers = self._work_blockers()
        summary = _blocker_summary(blockers)
        if summary["blocks_all"]:
            raise WorkBlockedError(message, summary)
        if restart and summary["blocks_restart"]:
            raise WorkBlockedError(
                "Uncertain, partial or interrupted Studio work may still need ComfyUI history for Resume "
                "observation; the backend restart was refused. Resolve or abandon it first.",
                summary, "restart_blocked_by_unresolved_work",
            )
        return summary

    def _backend_snapshot(self, *, expected_identity: dict[str, Any] | None = None,
                          expected_profile_id: str | None = None) -> tuple[dict[str, Any], Any]:
        manager = getattr(self.studio, "backends", None)
        if manager is None or manager.busy:
            raise PreparationError("Backend manager is unavailable or switching")
        profile = manager.profiles.get(manager.active)
        if not isinstance(profile, dict):
            raise PreparationError("Selected backend profile is unavailable")
        profile_id = str(profile.get("id", ""))
        if expected_profile_id is not None and profile_id != expected_profile_id:
            raise PreparationError("Selected backend profile changed since the prior check")
        try:
            queue = manager.request(profile, "/queue", 5)
            queue_is_idle(queue)
            process = manager.process(profile)
            matching = manager.configured_processes(profile)
        except Exception as exc:
            raise PreparationError("Selected backend queue or ownership is unknown: " + str(exc)[:220]) from exc
        if process is None:
            raise PreparationError("Selected backend has no verified owned listener")
        identity = _process_identity(process)
        matching_identities = [_process_identity(candidate) for candidate in matching]
        if len(matching_identities) != 1 or matching_identities[0] != identity:
            raise PreparationError("Selected backend ownership is ambiguous; all processes were preserved")
        if expected_identity is not None and identity != expected_identity:
            raise PreparationError("Selected backend process changed since the prior check")
        record = {
            "profile_id": profile_id[:80],
            "url": str(profile.get("url", ""))[:300],
            "process": identity,
            "queue": _queue_summary(queue),
        }
        return record, process

    def _reservation_snapshot(self) -> dict[str, Any]:
        owners: dict[str, dict[str, int]] = {}
        jobs = getattr(self.studio, "jobs", {})
        definitive = getattr(resource_admission, "_definitive_terminal", lambda job: False)
        for owner_id, job in jobs.items():
            history = job.get("resource_admission") if isinstance(job, dict) else None
            if not isinstance(history, list) or not history or definitive(job):
                continue
            last = history[-1]
            if not isinstance(last, dict) or last.get("state") not in resource_admission.ACTIVE_STATES:
                continue
            reservation = last.get("reservation")
            if isinstance(reservation, dict) and all(type(reservation.get(key)) is int and reservation[key] >= 0
                                                     for key in resource_admission.DIMENSIONS):
                owners[str(owner_id)] = {key: reservation[key] for key in resource_admission.DIMENSIONS}
        controller = getattr(self.studio, "_stage_resource_admission", None)
        ledger = getattr(controller, "ledger", None)
        if ledger is not None and hasattr(ledger, "lock") and hasattr(ledger, "reservations"):
            with ledger.lock:
                for owner_id, record in ledger.reservations.items():
                    reservation = record.get("reservation") if isinstance(record, dict) else None
                    if isinstance(reservation, dict) and all(type(reservation.get(key)) is int and reservation[key] >= 0
                                                             for key in resource_admission.DIMENSIONS):
                        owners[str(owner_id)] = {key: reservation[key] for key in resource_admission.DIMENSIONS}
        totals = {key: sum(value[key] for value in owners.values()) for key in resource_admission.DIMENSIONS}
        return {"owners": sorted(owners), "totals": totals}

    @staticmethod
    def _evaluate(identity: dict[str, Any], profile: dict[str, Any], observation: dict[str, Any],
                  reservations: dict[str, Any]) -> dict[str, Any]:
        ledger = resource_admission.ReservationLedger()
        if any(reservations["totals"].values()):
            # The merged ledger restores only validated, hash-bound receipts, so the
            # aggregate of reservations held elsewhere is expressed as one.
            owner = "existing-reservations"
            record = {
                "schema": resource_admission.SCHEMA,
                "owner_id": owner,
                "kind": "aggregate",
                "state": "reserved",
                "identity_sha256": resource_admission._digest({"owners": reservations["owners"]}),
                "reservation": {key: reservations["totals"][key] for key in resource_admission.DIMENSIONS},
            }
            record["receipt_sha256"] = resource_admission._digest(record)
            ledger.restore(owner, record)
        raw = ledger.admit("large-job-preparation", identity, profile, observation)
        return {
            "decision": raw["decision"],
            "state": raw["state"],
            "profile_basis": raw["profile_basis"],
            "stage_evaluations": raw["stage_evaluations"],
            "reservation": raw["reservation"],
            "reservations_before": raw["reservations_before"],
        }

    def _context(self, recipe: dict[str, Any]) -> dict[str, Any]:
        self._check_work("In-flight Studio work (queued, submitting or running) blocks resource cleanup")
        first_backend, _ = self._backend_snapshot()
        preset, graph, _path, _controls, _batch = self.studio.prepare(copy.deepcopy(recipe))
        observation = self.observer(self.studio)
        identity = resource_admission.workflow_identity(
            self.studio, preset, graph, observation.get("runtime") or {}
        )
        if identity.get("backend_id") != first_backend["profile_id"]:
            # Releasing or restarting the selected backend proves nothing for a job bound elsewhere.
            raise PreparationError("The prepared workflow targets a backend other than the selected owned backend")
        try:
            profile = resource_admission.profile_for(self.studio, identity)
        except ValueError as exc:
            raise PreparationError(str(exc)) from exc
        reservations = self._reservation_snapshot()
        second_backend, _ = self._backend_snapshot(
            expected_identity=first_backend["process"], expected_profile_id=first_backend["profile_id"]
        )
        blockers = self._check_work("Studio work changed while preparation was being observed")
        result = {
            "blockers": blockers,
            "workflow_identity": identity,
            "profile": None if profile is None else {
                "profile_sha256": profile["profile_sha256"],
                "basis": profile["basis"],
                "source": profile["source"],
            },
            "observation": observation,
            "reservations": reservations,
            "backend": second_backend,
            "evaluation": None,
        }
        if profile is not None:
            result["evaluation"] = self._evaluate(identity, profile, observation, reservations)
        result["_profile"] = profile
        return result

    def _recheck(self, expected_identity: dict[str, Any], expected_profile_id: str) -> tuple[dict[str, Any], Any]:
        message = "New Studio work arrived; lifecycle action was refused"
        self._check_work(message)
        with self.studio.lock:
            self._check_work(message)
            return self._backend_snapshot(
                expected_identity=expected_identity, expected_profile_id=expected_profile_id
            )

    def _claim_backend(self, expected_identity: dict[str, Any], expected_profile_id: str) -> tuple[dict[str, Any], Any]:
        """Recheck and take the switch gate in one critical section.

        ``backends.busy`` is the gate ``Studio.prepare``, ``switch``, reference jobs and
        runtime recovery already honour, so no new job or recovery launch can start
        while the owned backend is being stopped and relaunched.
        """
        with self.studio.lock:
            # Unresolved work at rest blocks only this action: a restart discards ComfyUI history.
            self._check_work("New Studio work arrived; lifecycle action was refused", restart=True)
            backend, process = self._recheck(expected_identity, expected_profile_id)
            manager = self.studio.backends
            if manager.busy:
                raise PreparationError("Backend manager became busy; lifecycle action was refused")
            manager.busy = True
        return backend, process

    def _release_backend(self) -> None:
        with self.studio.lock:
            self.studio.backends.busy = False

    def _after_action(self, context: dict[str, Any], expected_identity: dict[str, Any],
                      expected_profile_id: str) -> dict[str, Any]:
        backend, _ = self._recheck(expected_identity, expected_profile_id)
        observation = self.observer(self.studio)
        profile = context["_profile"]
        evaluation = self._evaluate(
            context["workflow_identity"], profile, observation, context["reservations"]
        )
        backend_after, _ = self._backend_snapshot(
            expected_identity=expected_identity, expected_profile_id=expected_profile_id
        )
        self._check_work("Studio work changed while post-action resources were being measured")
        return {"observation": observation, "evaluation": evaluation, "backend": backend_after,
                "queue_before_observation": backend["queue"]}
