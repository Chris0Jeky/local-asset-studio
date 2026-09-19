"""Measured `/free` and optional exact-owner restart decisions."""
from __future__ import annotations

import copy
from typing import Any

from large_job_prep_common import SAFE_DECISIONS, _delta, _number, _proved_relief


class ActionMixin:
    def _execute_cleanup(self, journal: dict[str, Any], receipt: dict[str, Any],
                         request: dict[str, Any], context: dict[str, Any],
                         before_evaluation: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        expected_identity = context["backend"]["process"]
        checked, _ = self._recheck(expected_identity, context["backend"]["profile_id"])
        release_action = {
            "kind": "release",
            "state": "intent_saved",
            "recorded_at": self.clock(),
            "process": expected_identity,
            "queue": checked["queue"],
            "command": {"route": "/free", "unload_models": True, "free_memory": True},
        }
        self._record_action(journal, receipt, release_action)
        try:
            self.studio._request(
                "/free",
                method="POST",
                data={"unload_models": True, "free_memory": True},
                timeout=60,
                base_url=checked["url"],
                allow_empty=True,
            )
        except Exception as exc:
            release_action.update(state="response_unknown", error=type(exc).__name__)
            self._persist(journal, receipt)
            return self._finish(
                journal, receipt, state="unknown", decision="unknown", ready=False,
                reason="The /free response was lost or failed. Its effect is unknown; restart and automatic retry were refused.",
                phase="release_response_unknown",
            )
        release_action.update(state="response_received", responded_at=self.clock())
        self._persist(journal, receipt)
        settle = _number(config.get("large_job_release_settle_seconds", 2), 0, 30, 2)
        if settle:
            self.sleeper(settle)
        after_release = self._after_action(
            context, expected_identity, context["backend"]["profile_id"]
        )
        receipt["after_release"] = copy.deepcopy(after_release)
        receipt["release_delta_bytes"] = _delta(context["observation"], after_release["observation"])
        release_action.update(
            state="measured",
            measured_relief=_proved_relief(
                context["observation"], after_release["observation"], before_evaluation
            ),
        )
        self._persist(journal, receipt)
        after_decision = after_release["evaluation"]["decision"]
        if after_decision in SAFE_DECISIONS and release_action["measured_relief"]:
            return self._finish(
                journal, receipt, state="completed", decision=after_decision, ready=True,
                reason="Owned cache release was followed by measured resource relief and a fresh safe evaluation.",
                phase="ready_after_release",
            )
        if after_decision == "unknown":
            return self._finish(
                journal, receipt, state="unknown", decision="unknown", ready=False,
                reason="Post-release counters are unavailable; HTTP success is not treated as resource recovery.",
                phase="post_release_unknown",
            )
        if not request["allow_restart"]:
            return self._finish(
                journal, receipt, state="refused", decision=after_decision, ready=False,
                reason="Measured release was insufficient and this request did not authorize restart.",
                phase="restart_not_authorized",
            )
        if config.get("enable_large_job_backend_restart") is not True:
            return self._finish(
                journal, receipt, state="refused", decision=after_decision, ready=False,
                reason="Verified owned-backend restart is separately disabled in local configuration.",
                phase="restart_disabled",
            )

        restarted = self._restart(journal, receipt, context, after_release)
        receipt["after_restart"] = copy.deepcopy(restarted)
        receipt["restart_delta_bytes"] = _delta(after_release["observation"], restarted["observation"])
        self._persist(journal, receipt)
        final_decision = restarted["evaluation"]["decision"]
        relief = _proved_relief(
            after_release["observation"], restarted["observation"], after_release["evaluation"]
        )
        if final_decision in SAFE_DECISIONS and relief:
            return self._finish(
                journal, receipt, state="completed", decision=final_decision, ready=True,
                reason="The exact owned backend restarted, became idle, and fresh counters proved sufficient capacity.",
                phase="ready_after_restart",
            )
        reason = (
            "Post-restart counters are unavailable; readiness remains unknown."
            if final_decision == "unknown"
            else "Restart completed but measured capacity is still below the exact stage-aware profile."
        )
        return self._finish(
            journal, receipt,
            state="unknown" if final_decision == "unknown" else "refused",
            decision=final_decision,
            ready=False,
            reason=reason,
            phase="restart_insufficient",
        )
