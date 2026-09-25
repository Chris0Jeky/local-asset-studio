"""Strict zero-authority benchmark-result contracts for Adult Illustration."""
from __future__ import annotations

import copy
from datetime import date
import hashlib
import json
import math
import re
from typing import Any, Mapping


RESULT_SCHEMA = "studio.adult-illustration-benchmark-result/v1"
CORPUS_SCHEMA = "studio.adult-illustration-benchmark-corpus/v0"
ROUTES_SCHEMA = "studio.adult-illustration-route-candidates/v0"
MAX_CANDIDATES = 512
MAX_CASES = 64
MAX_MEASUREMENTS = 128
MAX_REFERENCES = 64
SHA1 = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
AUTHORITY_FIELDS = (
    "download_authorized",
    "install_authorized",
    "execution_authorized",
    "generation_submitted",
    "training_authorized",
    "promotion_authorized",
)
TOP_FIELDS = {
    "schema",
    "kind",
    "executable",
    "authority",
    "research_date",
    "source_baseline",
    "issue",
    "synthetic",
    "corpus",
    "study",
    "candidates",
    "accounting",
    "measurements",
    "decision",
    "notes",
    *AUTHORITY_FIELDS,
    "result_id",
}
CORPUS_FIELDS = {"path", "git_blob_sha", "case_ids"}
STUDY_FIELDS = {
    "id",
    "phase",
    "route_id",
    "route_manifest_git_blob_sha",
    "prompt_variant",
    "declared_candidate_cap",
    "route_config_sha256",
    "graph_sha256",
    "source_set_sha256",
    "external_campaign_id",
    "external_authorization_ref",
}
CANDIDATE_FIELDS = {
    "id",
    "ordinal",
    "case_id",
    "seed",
    "status",
    "failure_class",
    "output_ref",
    "accepted",
    "human_reviewed",
    "adult_envelope",
    "artistic_accepted",
    "rights_reviewed",
    "evidence_refs",
}
ACCOUNTING_FIELDS = {
    "attempted_candidates",
    "retained_candidates",
    "accepted_candidates",
    "attempted_distinct_tasks",
    "accepted_distinct_tasks",
    "owner_interactions",
    "wait_seconds",
    "cleanup_minutes",
}
MEASUREMENT_FIELDS = {
    "id",
    "state",
    "value",
    "numerator",
    "denominator",
    "unit",
    "uncertainty",
    "evidence_refs",
}
DECISION_FIELDS = {
    "outcome",
    "target_type",
    "target_id",
    "scope",
    "evidence_refs",
    "human_approved",
    "promotion_authorized",
}
PHASES = {"smoke", "finalist", "adapter", "repair", "finishing"}
PROMPT_VARIANTS = {
    "unchanged_brief",
    "manual_clarification",
    "compiled_projection",
    "not_applicable",
}
FAILURE_STATUSES = {
    "refused",
    "unsupported_control",
    "no_op",
    "oom",
    "crash",
    "uncertain_submission",
    "binding_fault",
    "cancelled",
}
CANDIDATE_STATUSES = {"completed", *FAILURE_STATUSES}
ADULT_STATES = {"pass", "fail", "unreviewed", "unobserved", "uncertain"}
MEASUREMENT_STATES = {"unobserved", "not_applicable", "observed", "uncertain"}
DECISION_OUTCOMES = {
    "insufficient_evidence",
    "promote_route",
    "narrow_scope",
    "keep_experimental",
    "reject_route",
    "reject_control",
}
TARGET_TYPES = {"route", "control", "adapter", "workflow"}
DECISION_TARGET_TYPES = {
    "promote_route": "route",
    "reject_route": "route",
    "reject_control": "control",
}


def canonical_bytes(value: Any) -> bytes:
    """Return deterministic strict JSON bytes."""

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError(f"benchmark result is not finite canonical JSON: {exc}") from exc


def git_blob_sha(data: bytes) -> str:
    """Return the Git blob SHA-1 for exact raw file bytes."""

    if not isinstance(data, bytes):
        raise TypeError("Git blob input must be bytes")
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _exact(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} has missing or unknown fields")
    return value


def _text(value: Any, label: str, maximum: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or len(value) > maximum
        or "\x00" in value
        or "\r" in value
        or "\n" in value
    ):
        raise ValueError(f"{label} must be bounded single-line text")
    return value


def _optional_text(value: Any, label: str, maximum: int = 512) -> str | None:
    return None if value is None else _text(value, label, maximum)


def _count(value: Any, label: str, maximum: int = MAX_CANDIDATES) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 0 <= value <= maximum
    ):
        raise ValueError(f"{label} must be an integer in 0..{maximum}")
    return value


def _nonnegative_number(value: Any, label: str) -> int | float | None:
    if value is None:
        return None
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"{label} must be null or a finite non-negative number")
    return value


def _sha1(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA1.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase 40-hex Git blob SHA")
    return value


def _optional_sha256(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be null or a lowercase 64-hex SHA-256")
    return value


def _strings(
    value: Any,
    label: str,
    *,
    maximum: int = MAX_REFERENCES,
    allow_empty: bool = True,
) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"{label} must be a bounded array")
    result = [_text(item, label) for item in value]
    if not allow_empty and not result:
        raise ValueError(f"{label} must not be empty")
    if len(set(result)) != len(result):
        raise ValueError(f"{label} contains duplicates")
    return result


def _manifest_ids(
    corpus: Any,
    routes: Any,
) -> tuple[set[str], list[str], set[str], str]:
    if not isinstance(corpus, dict) or corpus.get("schema") != CORPUS_SCHEMA:
        raise ValueError("unsupported Adult Illustration benchmark corpus")
    if corpus.get("executable") is not False or corpus.get("authority") != "none":
        raise ValueError("benchmark corpus must remain non-executing and zero-authority")
    if corpus.get("issue") != 409:
        raise ValueError("benchmark corpus issue owner must remain #409")
    corpus_baseline = corpus.get("source_baseline")
    if not isinstance(corpus_baseline, str) or SHA1.fullmatch(corpus_baseline) is None:
        raise ValueError("benchmark corpus source baseline must be lowercase 40-hex")
    cases = corpus.get("cases")
    if not isinstance(cases, list) or not cases or len(cases) > MAX_CANDIDATES:
        raise ValueError("benchmark corpus cases must be a bounded non-empty array")
    case_ids: list[str] = []
    for item in cases:
        if not isinstance(item, dict):
            raise ValueError("benchmark corpus case must be an object")
        case_ids.append(_text(item.get("id"), "benchmark case id", 128))
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("benchmark corpus contains duplicate case IDs")
    measures = _strings(
        corpus.get("measures"),
        "benchmark measure IDs",
        maximum=MAX_MEASUREMENTS,
        allow_empty=False,
    )

    if not isinstance(routes, dict) or routes.get("schema") != ROUTES_SCHEMA:
        raise ValueError("unsupported Adult Illustration route manifest")
    if routes.get("executable") is not False or routes.get("authority") != "none":
        raise ValueError("route manifest must remain non-executing and zero-authority")
    if routes.get("issue") != 405:
        raise ValueError("route manifest issue owner must remain #405")
    route_baseline = routes.get("source_baseline")
    if not isinstance(route_baseline, str) or SHA1.fullmatch(route_baseline) is None:
        raise ValueError("route manifest source baseline must be lowercase 40-hex")
    if route_baseline != corpus_baseline:
        raise ValueError("benchmark corpus and route manifest source baselines do not match")
    candidates = routes.get("candidates")
    if not isinstance(candidates, list) or not candidates or len(candidates) > MAX_CANDIDATES:
        raise ValueError("route candidates must be a bounded non-empty array")
    route_ids: list[str] = []
    for item in candidates:
        if not isinstance(item, dict):
            raise ValueError("route candidate must be an object")
        route_ids.append(_text(item.get("id"), "route candidate id", 128))
    if len(set(route_ids)) != len(route_ids):
        raise ValueError("route manifest contains duplicate route IDs")
    return set(case_ids), measures, set(route_ids), corpus_baseline


def _validate_measurement_value(value: Any, label: str) -> Any:
    if value is None or isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{label} must be finite")
        return value
    if isinstance(value, str):
        return _text(value, label, 1_024)
    raise ValueError(f"{label} must be null or a bounded scalar JSON value")


def _validate_measurements(
    raw: Any,
    expected_ids: list[str],
) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or len(raw) != len(expected_ids):
        raise ValueError("measurements must contain every corpus measure exactly once")
    values: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        value = _exact(item, MEASUREMENT_FIELDS, f"measurement {index}")
        measure_id = _text(value.get("id"), "measurement id", 128)
        if measure_id in seen:
            raise ValueError(f"duplicate measurement {measure_id!r}")
        seen.add(measure_id)
        if measure_id not in expected_ids:
            raise ValueError(f"unknown benchmark measure {measure_id!r}")
        state = value.get("state")
        if state not in MEASUREMENT_STATES:
            raise ValueError(f"measurement {measure_id!r} has invalid state")
        observed_value = _validate_measurement_value(
            value.get("value"), f"measurement {measure_id!r} value"
        )
        numerator = value.get("numerator")
        denominator = value.get("denominator")
        if numerator is not None:
            numerator = _count(numerator, f"measurement {measure_id!r} numerator")
        if denominator is not None:
            denominator = _count(
                denominator,
                f"measurement {measure_id!r} denominator",
            )
        if (numerator is None) != (denominator is None):
            raise ValueError(
                f"measurement {measure_id!r} numerator and denominator must appear together"
            )
        if denominator is not None:
            if denominator == 0:
                raise ValueError(f"measurement {measure_id!r} denominator must be positive")
            if numerator is not None and numerator > denominator:
                raise ValueError(
                    f"measurement {measure_id!r} numerator cannot exceed denominator"
                )
        unit = _optional_text(value.get("unit"), f"measurement {measure_id!r} unit", 64)
        uncertainty = _optional_text(
            value.get("uncertainty"),
            f"measurement {measure_id!r} uncertainty",
            1_024,
        )
        evidence = _strings(
            value.get("evidence_refs"),
            f"measurement {measure_id!r} evidence refs",
        )
        if state == "unobserved":
            if any(
                field is not None
                for field in (observed_value, numerator, denominator, unit, uncertainty)
            ) or evidence:
                raise ValueError(
                    f"unobserved measurement {measure_id!r} must use null fields and no evidence"
                )
        elif state == "not_applicable":
            if any(
                field is not None
                for field in (observed_value, numerator, denominator, unit)
            ) or uncertainty is None:
                raise ValueError(
                    f"not-applicable measurement {measure_id!r} needs only a reason"
                )
        elif state == "observed":
            if observed_value is None and numerator is None:
                raise ValueError(
                    f"observed measurement {measure_id!r} needs a value or ratio"
                )
            if not evidence:
                raise ValueError(
                    f"observed measurement {measure_id!r} requires evidence"
                )
        elif uncertainty is None or not evidence:
            raise ValueError(
                f"uncertain measurement {measure_id!r} requires uncertainty and evidence"
            )
        values.append(copy.deepcopy(value))
    if seen != set(expected_ids):
        raise ValueError("measurements do not match the benchmark corpus measure set")
    return values


def validate_benchmark_result(
    result: Any,
    corpus: Any,
    routes: Any,
    *,
    corpus_blob_sha: str,
    route_blob_sha: str,
) -> dict[str, Any]:
    """Validate one result against exact corpus and route-manifest identities."""

    case_ids, measure_ids, route_ids, expected_baseline = _manifest_ids(
        corpus, routes
    )
    expected_corpus_blob = _sha1(corpus_blob_sha, "corpus blob identity")
    expected_route_blob = _sha1(route_blob_sha, "route manifest blob identity")
    value = _exact(result, TOP_FIELDS, "benchmark result")
    if value.get("schema") != RESULT_SCHEMA:
        raise ValueError("unsupported Adult Illustration benchmark result schema")
    synthetic = value.get("synthetic")
    if not isinstance(synthetic, bool):
        raise ValueError("benchmark result synthetic flag must be boolean")
    expected_kind = (
        "synthetic-benchmark-result-example" if synthetic else "benchmark-result"
    )
    if value.get("kind") != expected_kind:
        raise ValueError("benchmark result kind does not match its synthetic state")
    if value.get("executable") is not False or value.get("authority") != "none":
        raise ValueError("benchmark result must be non-executing with authority none")
    if value.get("issue") != 409:
        raise ValueError("benchmark result issue owner must remain #409")
    baseline = value.get("source_baseline")
    if not isinstance(baseline, str) or SHA1.fullmatch(baseline) is None:
        raise ValueError("benchmark result source baseline must be lowercase 40-hex")
    if baseline != expected_baseline:
        raise ValueError("benchmark result source baseline does not match frozen manifests")
    research_date = value.get("research_date")
    try:
        if not isinstance(research_date, str):
            raise ValueError
        date.fromisoformat(research_date)
    except ValueError as exc:
        raise ValueError(
            "benchmark result research date must be an ISO calendar date"
        ) from exc
    for field in AUTHORITY_FIELDS:
        if value.get(field) is not False:
            raise ValueError(f"benchmark result must keep {field} false")

    corpus_ref = _exact(value.get("corpus"), CORPUS_FIELDS, "corpus reference")
    if corpus_ref.get("path") != "research/adult-illustration/benchmark-corpus.json":
        raise ValueError("benchmark result corpus path is unsupported")
    if _sha1(corpus_ref.get("git_blob_sha"), "corpus Git blob SHA") != expected_corpus_blob:
        raise ValueError("benchmark result corpus identity is stale or mismatched")
    selected_cases = _strings(
        corpus_ref.get("case_ids"),
        "selected benchmark case IDs",
        maximum=MAX_CASES,
        allow_empty=False,
    )
    unknown_cases = sorted(set(selected_cases) - case_ids)
    if unknown_cases:
        raise ValueError(f"benchmark result references unknown cases {unknown_cases}")

    study = _exact(value.get("study"), STUDY_FIELDS, "benchmark study")
    _text(study.get("id"), "benchmark study id", 128)
    if study.get("phase") not in PHASES:
        raise ValueError("benchmark study phase is invalid")
    route_id = _text(study.get("route_id"), "benchmark route id", 128)
    if route_id not in route_ids:
        raise ValueError(f"benchmark result references unknown route {route_id!r}")
    if _sha1(
        study.get("route_manifest_git_blob_sha"),
        "route manifest Git blob SHA",
    ) != expected_route_blob:
        raise ValueError("benchmark result route manifest identity is stale or mismatched")
    if study.get("prompt_variant") not in PROMPT_VARIANTS:
        raise ValueError("benchmark prompt variant is invalid")
    declared_cap = _count(
        study.get("declared_candidate_cap"),
        "declared candidate cap",
    )
    route_config = _optional_sha256(
        study.get("route_config_sha256"), "route configuration identity"
    )
    graph = _optional_sha256(study.get("graph_sha256"), "graph identity")
    source_set = _optional_sha256(
        study.get("source_set_sha256"), "source-set identity"
    )
    campaign_id = _optional_text(
        study.get("external_campaign_id"), "external campaign id", 256
    )
    authorization = _optional_text(
        study.get("external_authorization_ref"),
        "external authorization reference",
        1_024,
    )
    if synthetic:
        if any(
            item is not None
            for item in (route_config, graph, source_set, campaign_id, authorization)
        ):
            raise ValueError(
                "synthetic benchmark result cannot claim route, source or authorization evidence"
            )
    elif any(
        item is None
        for item in (route_config, graph, source_set, campaign_id, authorization)
    ):
        raise ValueError(
            "non-synthetic benchmark result requires frozen route, graph, source and campaign evidence"
        )

    raw_candidates = value.get("candidates")
    if not isinstance(raw_candidates, list) or len(raw_candidates) > MAX_CANDIDATES:
        raise ValueError("benchmark candidates must be a bounded array")
    if len(raw_candidates) > declared_cap:
        raise ValueError("actual candidates exceed the declared candidate cap")
    candidate_ids: set[str] = set()
    accepted_count = 0
    attempted_cases: set[str] = set()
    accepted_cases: set[str] = set()
    validated_candidates: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_candidates, start=1):
        candidate = _exact(raw, CANDIDATE_FIELDS, f"candidate {index}")
        candidate_id = _text(candidate.get("id"), "candidate id", 128)
        if candidate_id in candidate_ids:
            raise ValueError(f"duplicate candidate id {candidate_id!r}")
        candidate_ids.add(candidate_id)
        if isinstance(candidate.get("ordinal"), bool) or candidate.get("ordinal") != index:
            raise ValueError("candidate ordinals must be contiguous and match array order")
        case_id = _text(candidate.get("case_id"), "candidate case id", 128)
        if case_id not in selected_cases or case_id not in case_ids:
            raise ValueError(f"candidate references unknown or unselected case {case_id!r}")
        attempted_cases.add(case_id)
        seed = candidate.get("seed")
        if seed is not None and (
            not isinstance(seed, int)
            or isinstance(seed, bool)
            or not 0 <= seed <= (1 << 64) - 1
        ):
            raise ValueError("candidate seed must be null or an unsigned 64-bit integer")
        status = candidate.get("status")
        if status not in CANDIDATE_STATUSES:
            raise ValueError(f"candidate {candidate_id!r} has invalid status")
        failure = candidate.get("failure_class")
        if status == "completed":
            if failure is not None:
                raise ValueError("completed candidate failure class must be null")
            _text(candidate.get("output_ref"), "completed candidate output ref", 1_024)
        else:
            if failure != status:
                raise ValueError("candidate failure class must match its failure status")
            if candidate.get("output_ref") is not None:
                raise ValueError("failed candidate output ref must be null")
        for field in (
            "accepted",
            "human_reviewed",
            "artistic_accepted",
            "rights_reviewed",
        ):
            if not isinstance(candidate.get(field), bool):
                raise ValueError(f"candidate {field} must be boolean")
        adult_state = candidate.get("adult_envelope")
        if adult_state not in ADULT_STATES:
            raise ValueError("candidate adult envelope state is invalid")
        evidence = _strings(
            candidate.get("evidence_refs"),
            f"candidate {candidate_id!r} evidence refs",
            allow_empty=False,
        )
        accepted = candidate["accepted"]
        if accepted:
            if (
                status != "completed"
                or candidate["human_reviewed"] is not True
                or candidate["artistic_accepted"] is not True
                or adult_state != "pass"
            ):
                raise ValueError(
                    "accepted candidate requires completed human-reviewed artistic acceptance and adult-envelope pass"
                )
            accepted_count += 1
            accepted_cases.add(case_id)
        if candidate["artistic_accepted"] and not candidate["human_reviewed"]:
            raise ValueError("artistic acceptance requires human review")
        if not candidate["human_reviewed"] and adult_state in {"pass", "fail"}:
            raise ValueError("adult-envelope pass or fail requires human review")
        if not evidence:
            raise ValueError("candidate evidence refs must not be empty")
        validated_candidates.append(copy.deepcopy(candidate))

    accounting = _exact(value.get("accounting"), ACCOUNTING_FIELDS, "benchmark accounting")
    attempted = _count(accounting.get("attempted_candidates"), "attempted candidates")
    retained = _count(accounting.get("retained_candidates"), "retained candidates")
    accepted = _count(accounting.get("accepted_candidates"), "accepted candidates")
    attempted_tasks = _count(
        accounting.get("attempted_distinct_tasks"),
        "attempted distinct tasks",
        MAX_CASES,
    )
    accepted_tasks = _count(
        accounting.get("accepted_distinct_tasks"),
        "accepted distinct tasks",
        MAX_CASES,
    )
    if attempted != len(validated_candidates):
        raise ValueError("attempted candidate count does not match retained records")
    if retained != len(validated_candidates):
        raise ValueError("retained candidate count must include every attempt")
    if accepted != accepted_count:
        raise ValueError("accepted candidate count does not match candidate reviews")
    if attempted_tasks != len(attempted_cases):
        raise ValueError("attempted distinct-task count does not match candidate cases")
    if accepted_tasks != len(accepted_cases):
        raise ValueError("accepted distinct-task count does not match accepted cases")
    _count(accounting.get("owner_interactions"), "owner interactions", 100_000)
    _nonnegative_number(accounting.get("wait_seconds"), "wait seconds")
    _nonnegative_number(accounting.get("cleanup_minutes"), "cleanup minutes")

    _validate_measurements(value.get("measurements"), measure_ids)

    decision = _exact(value.get("decision"), DECISION_FIELDS, "benchmark decision")
    outcome = decision.get("outcome")
    if outcome not in DECISION_OUTCOMES:
        raise ValueError("benchmark decision outcome is invalid")
    target_type = decision.get("target_type")
    if target_type not in TARGET_TYPES:
        raise ValueError("benchmark decision target type is invalid")
    required_target_type = DECISION_TARGET_TYPES.get(outcome)
    if required_target_type is not None and target_type != required_target_type:
        raise ValueError(
            f"benchmark decision outcome {outcome!r} requires target type "
            f"{required_target_type!r}"
        )
    target_id = _text(decision.get("target_id"), "benchmark decision target id", 128)
    if target_type == "route" and target_id not in route_ids:
        raise ValueError("benchmark decision references an unknown route")
    scope = _strings(decision.get("scope"), "benchmark decision scope")
    decision_evidence = _strings(
        decision.get("evidence_refs"), "benchmark decision evidence refs"
    )
    if not isinstance(decision.get("human_approved"), bool):
        raise ValueError("benchmark decision human_approved must be boolean")
    if decision.get("promotion_authorized") is not False:
        raise ValueError("benchmark result cannot authorize promotion")
    if synthetic:
        if (
            outcome != "insufficient_evidence"
            or decision["human_approved"] is not False
            or scope
            or decision_evidence
        ):
            raise ValueError(
                "synthetic benchmark result cannot approve or imply promotion"
            )
    elif outcome != "insufficient_evidence" and (
        decision["human_approved"] is not True or not decision_evidence
    ):
        raise ValueError(
            "a consequential benchmark decision requires human approval and evidence"
        )

    _strings(value.get("notes"), "benchmark result notes", maximum=32, allow_empty=False)
    result_id = value.get("result_id")
    if not isinstance(result_id, str) or SHA256.fullmatch(result_id) is None:
        raise ValueError("benchmark result_id must be lowercase 64-hex SHA-256")
    unsigned = copy.deepcopy(value)
    unsigned.pop("result_id")
    if hashlib.sha256(canonical_bytes(unsigned)).hexdigest() != result_id:
        raise ValueError("benchmark result_id does not match canonical content")
    return copy.deepcopy(value)


def render_benchmark_result(
    result: Any,
    corpus: Any,
    routes: Any,
    *,
    corpus_blob_sha: str,
    route_blob_sha: str,
) -> str:
    """Validate and render one result deterministically."""

    value = validate_benchmark_result(
        result,
        corpus,
        routes,
        corpus_blob_sha=corpus_blob_sha,
        route_blob_sha=route_blob_sha,
    )
    return json.dumps(
        value,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
    ) + "\n"


__all__ = [
    "RESULT_SCHEMA",
    "canonical_bytes",
    "git_blob_sha",
    "render_benchmark_result",
    "validate_benchmark_result",
]
