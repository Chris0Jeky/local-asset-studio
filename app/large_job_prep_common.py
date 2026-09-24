"""Pure values and bounded evidence helpers for large-job preparation."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from typing import Any

import resource_admission

SCHEMA = "studio.large-job-preparation/v1"
JOURNAL_SCHEMA = "studio.large-job-preparation-journal/v1"
REQUEST_ID = re.compile(r"[a-z0-9](?:[a-z0-9._-]{0,126}[a-z0-9])?\Z")
MAX_RECORDS = 32
MAX_REQUEST_BYTES = 128 * 1024
MAX_RECEIPT_BYTES = 512 * 1024
MAX_JOURNAL_BYTES = 2 * 1024 * 1024
ACTIVE_JOB_STATES = {"queued", "waiting", "submitting", "running", "uncertain", "partial"}
TERMINAL_PRODUCTION_STATES = {"completed", "failed", "abandoned", "not_submitted"}
TERMINAL_SUBMISSION_STATES = {"completed", "failed"}
SAFE_DECISIONS = {"observed_safe", "estimated_safe"}


class PreparationError(ValueError):
    """A fail-closed request or runtime-state error."""


def _canonical(value: Any, limit: int) -> bytes:
    try:
        data = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PreparationError("Large-job preparation data is not canonical JSON") from exc
    if len(data) > limit:
        raise PreparationError("Large-job preparation data exceeds its byte limit")
    return data


def _digest(value: Any, limit: int = MAX_RECEIPT_BYTES) -> str:
    return hashlib.sha256(_canonical(value, limit)).hexdigest()


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not REQUEST_ID.fullmatch(value):
        raise PreparationError("request_id must be a bounded lowercase identifier")
    return value


def _boolean(value: Any, name: str) -> bool:
    if type(value) is not bool:
        raise PreparationError(name + " must be true or false")
    return value


def _number(value: Any, low: float, high: float, fallback: float) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        return fallback
    return float(value)


def _normalize_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PreparationError("Large-job preparation request must be an object")
    allowed = {"request_id", "recipe", "dry_run", "allow_release", "allow_restart", "mode"}
    if set(value) - allowed or not {"request_id", "recipe"} <= set(value):
        raise PreparationError("Large-job preparation request has missing or unsupported fields")
    recipe = value["recipe"]
    if not isinstance(recipe, dict):
        raise PreparationError("recipe must be a Studio recipe object")
    normalized = {
        "request_id": _identifier(value["request_id"]),
        "recipe": copy.deepcopy(recipe),
        "dry_run": _boolean(value.get("dry_run", True), "dry_run"),
        "allow_release": _boolean(value.get("allow_release", False), "allow_release"),
        "allow_restart": _boolean(value.get("allow_restart", False), "allow_restart"),
        "mode": value.get("mode", "explicit"),
    }
    if normalized["mode"] not in ("explicit", "idle_policy"):
        raise PreparationError("mode must be explicit or idle_policy")
    if normalized["mode"] == "idle_policy" and normalized["allow_restart"]:
        raise PreparationError("Idle retained-commit policy cannot authorize a backend restart")
    _canonical(normalized, MAX_REQUEST_BYTES)
    return normalized


def _process_identity(process: Any) -> dict[str, Any]:
    try:
        pid = process.pid
        created_at = process.create_time()
    except Exception as exc:
        raise PreparationError("Backend process creation identity is unavailable") from exc
    if type(pid) is not int or pid <= 0 or type(created_at) not in (int, float) or not math.isfinite(created_at):
        raise PreparationError("Backend process creation identity is invalid")
    return {"pid": pid, "created_at": float(created_at)}


def _queue_summary(queue: Any) -> dict[str, Any]:
    if not isinstance(queue, dict):
        raise PreparationError("ComfyUI queue response is invalid")
    running = queue.get("queue_running")
    pending = queue.get("queue_pending")
    if type(running) is not list or type(pending) is not list:
        raise PreparationError("ComfyUI queue response is invalid")
    # The hash detects a changing queue without persisting prompt contents.
    return {
        "running": len(running),
        "pending": len(pending),
        "sha256": _digest({"queue_running": running, "queue_pending": pending}),
    }


def _available(observation: dict[str, Any]) -> dict[str, int | None]:
    def counter(value: Any) -> int | None:
        if type(value) in (int, float) and math.isfinite(value) and value >= 0:
            return int(value)
        return None

    return {
        "physical_ram_bytes": counter((observation.get("physical_ram") or {}).get("available_bytes")),
        "windows_commit_bytes": counter((observation.get("windows_commit") or {}).get("available_bytes")),
        "vram_bytes": counter((observation.get("vram") or {}).get("available_bytes")),
    }


def _delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, int | None]:
    left, right = _available(before), _available(after)
    return {
        key: None if left[key] is None or right[key] is None else right[key] - left[key]
        for key in resource_admission.DIMENSIONS
    }


def _required_failures(evaluation: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for stage in evaluation.get("stage_evaluations") or []:
        for dimension, fact in (stage.get("dimensions") or {}).items():
            if fact.get("state") in ("unsafe", "unknown"):
                result.add(dimension)
    return result


def _proved_relief(before: dict[str, Any], after: dict[str, Any], evaluation: dict[str, Any]) -> bool:
    deltas = _delta(before, after)
    failing = _required_failures(evaluation)
    return bool(failing) and any(deltas.get(dimension) is not None and deltas[dimension] > 0 for dimension in failing)
