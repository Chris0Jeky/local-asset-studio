"""Idempotent decision flow for measured large-job preparation."""
from __future__ import annotations

import copy
from typing import Any

from large_job_prep_common import (
    MAX_REQUEST_BYTES, SAFE_DECISIONS, SCHEMA, PreparationError, WorkBlockedError, _digest,
    _normalize_request,
)


class FlowMixin:
    def run(self, value: Any) -> dict[str, Any]:
        request = _normalize_request(value)
        request_sha256 = _digest(request, MAX_REQUEST_BYTES)
        with self.lock:
            journal = self._load()
            existing = next((item for item in journal["records"]
                             if item.get("request_id") == request["request_id"]), None)
            if existing is not None:
                if existing.get("request_sha256") != request_sha256:
                    raise PreparationError("request_id was already used for different content")
                if existing.get("state") == "in_progress":
                    existing = copy.deepcopy(existing)
                    existing.update(
                        state="unknown",
                        phase="interrupted",
                        finished_at=self.clock(),
                        final={
                            "decision": "unknown",
                            "ready": False,
                            "reason": "A saved lifecycle intent was interrupted. Inspect the receipt and runtime; no action was replayed.",
                            "generation_submitted": False,
                        },
                    )
                    self._persist(journal, existing)
                result = copy.deepcopy(existing)
                result["replayed"] = True
                return result

            receipt: dict[str, Any] = {
                "schema": SCHEMA,
                "request_id": request["request_id"],
                "request_sha256": request_sha256,
                "recipe_sha256": _digest(request["recipe"], MAX_REQUEST_BYTES),
                "mode": request["mode"],
                "dry_run": request["dry_run"],
                "requested_actions": {
                    "release": request["allow_release"],
                    "restart": request["allow_restart"],
                },
                "state": "in_progress",
                "phase": "started",
                "started_at": self.clock(),
                "actions": [],
                "generation_submitted": False,
            }
            self._persist(journal, receipt)
            try:
                context = self._context(request["recipe"])
                profile = context.pop("_profile")
                # Keep the validated profile available to internal continuation
                # without duplicating its full stages in the durable public receipt.
                context["_profile"] = profile
                receipt["blockers"] = context.pop("blockers")
                receipt["before"] = {key: copy.deepcopy(value) for key, value in context.items()
                                     if not key.startswith("_")}
                self._persist(journal, receipt)
                if profile is None:
                    return self._finish(
                        journal, receipt, state="refused", decision="unknown", ready=False,
                        reason="No exact stage-aware admission profile matches this workflow/runtime identity.",
                        phase="profile_unknown",
                    )
                before_evaluation = context["evaluation"]
                if before_evaluation["decision"] in SAFE_DECISIONS:
                    return self._finish(
                        journal, receipt, state="completed", decision=before_evaluation["decision"], ready=True,
                        reason="Fresh counters and the exact stage-aware profile are already sufficient; no cleanup ran.",
                        phase="ready_without_action",
                    )
                if before_evaluation["decision"] == "unknown":
                    return self._finish(
                        journal, receipt, state="refused", decision="unknown", ready=False,
                        reason="Required resource counters are unavailable; cleanup cannot be authorized from unknown evidence.",
                        phase="resource_unknown",
                    )
                if not request["allow_release"]:
                    return self._finish(
                        journal, receipt, state="refused", decision=before_evaluation["decision"], ready=False,
                        reason="Capacity is insufficient and this request did not authorize owned cache release.",
                        phase="release_not_authorized",
                    )
                config = getattr(self.studio, "config", {}) or {}
                if request["dry_run"]:
                    # Unresolved work at rest leaves /free allowed but a restart refused while the
                    # selected backend may still hold its history (read-only /history checks).
                    restart_blocked = False
                    if request["allow_restart"]:
                        try:
                            checked = self._check_work("Studio work changed while preparation was being observed",
                                                       restart=True)
                            checked.pop("_history_absent")
                            receipt["blockers"] = checked
                        except WorkBlockedError as exc:
                            if exc.phase != "restart_blocked_by_unresolved_work":
                                raise
                            receipt["blockers"], restart_blocked = exc.blockers, True
                    receipt["planned_actions"] = ["release_owned_backend_cache"] + (
                        ["restart_verified_owned_backend"] if request["allow_restart"] and not restart_blocked else []
                    )
                    receipt["restart_blocked_by_unresolved_work"] = restart_blocked
                    receipt["local_authorization"] = {
                        "cleanup_enabled": config.get("enable_large_job_resource_cleanup") is True,
                        "idle_policy_enabled": config.get("enable_idle_retained_commit_cleanup") is True,
                        "restart_enabled": config.get("enable_large_job_backend_restart") is True,
                    }
                    return self._finish(
                        journal, receipt, state="completed", decision=before_evaluation["decision"], ready=False,
                        reason="Dry run completed without calling /free, terminating, launching or submitting anything.",
                        phase="dry_run",
                    )
                if config.get("enable_large_job_resource_cleanup") is not True:
                    return self._finish(
                        journal, receipt, state="refused", decision=before_evaluation["decision"], ready=False,
                        reason="Owned resource cleanup is disabled in local configuration.",
                        phase="cleanup_disabled",
                    )
                if request["mode"] == "idle_policy" and config.get("enable_idle_retained_commit_cleanup") is not True:
                    return self._finish(
                        journal, receipt, state="refused", decision=before_evaluation["decision"], ready=False,
                        reason="Idle retained-commit cleanup is separately disabled.",
                        phase="idle_policy_disabled",
                    )

                return self._execute_cleanup(journal, receipt, request, context, before_evaluation, config)
            except PreparationError as exc:
                if getattr(exc, "blockers", None) is not None:
                    receipt["blockers"] = exc.blockers
                return self._finish(
                    journal, receipt, state="refused", decision="unknown", ready=False,
                    reason=str(exc), phase=getattr(exc, "phase", "refused"),
                )
            except Exception as exc:
                return self._finish(
                    journal, receipt, state="unknown", decision="unknown", ready=False,
                    reason="Preparation failed with " + type(exc).__name__ + "; inspect the receipt and runtime before retrying.",
                    phase="unexpected_failure",
                )
