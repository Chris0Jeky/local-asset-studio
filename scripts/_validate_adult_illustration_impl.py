#!/usr/bin/env python3
"""Validate the non-executing controlled adult illustration research manifests.

This validator is intentionally standard-library-only and offline. It validates research
contracts; it does not inspect installed models, contact ComfyUI, or grant execution.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any


MANIFEST_DIR = Path("research") / "adult-illustration"
REQUIRED_MANIFESTS = (
    "programme.json",
    "control-ontology.json",
    "route-candidates.json",
    "benchmark-corpus.json",
    "genre-packs.json",
    "lora-qualification-example.json",
)
MAX_MANIFEST_BYTES = 1_048_576
MAX_ITEMS = 512
BASELINE_RE = re.compile(r"^[0-9a-f]{40}$")


def _finite_number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return math.isfinite(value)


def _path_label(filename: str) -> str:
    return f"{MANIFEST_DIR.as_posix()}/{filename}"


def _load_manifest(root: Path, filename: str, errors: list[str]) -> dict[str, Any] | None:
    path = root / MANIFEST_DIR / filename
    label = _path_label(filename)
    if not path.is_file():
        errors.append(f"{label}: missing required manifest")
        return None
    try:
        size = path.stat().st_size
    except OSError as exc:
        errors.append(f"{label}: cannot stat manifest: {exc}")
        return None
    if size > MAX_MANIFEST_BYTES:
        errors.append(
            f"{label}: manifest exceeds {MAX_MANIFEST_BYTES} byte offline contract"
        )
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: invalid UTF-8 JSON: {exc}")
        return None
    if not isinstance(payload, dict):
        errors.append(f"{label}: top level must be an object")
        return None
    return payload


def _validate_common(filename: str, payload: dict[str, Any], errors: list[str]) -> None:
    label = _path_label(filename)
    schema = payload.get("schema")
    if not isinstance(schema, str) or not schema.startswith("studio.adult-illustration-"):
        errors.append(f"{label}: schema must start with studio.adult-illustration-")
    if not isinstance(payload.get("kind"), str) or not payload["kind"]:
        errors.append(f"{label}: kind must be a non-empty string")
    if payload.get("executable") is not False:
        errors.append(f"{label}: research manifests must declare executable false")
    if payload.get("authority") != "none":
        errors.append(f"{label}: research manifests must declare authority none")
    raw_date = payload.get("research_date")
    try:
        if not isinstance(raw_date, str):
            raise ValueError
        date.fromisoformat(raw_date)
    except ValueError:
        errors.append(f"{label}: research_date must be an ISO YYYY-MM-DD date")
    baseline = payload.get("source_baseline")
    if not isinstance(baseline, str) or BASELINE_RE.fullmatch(baseline) is None:
        errors.append(f"{label}: source_baseline must be a lowercase 40-hex commit SHA")


def _unique_ids(
    items: Any,
    *,
    filename: str,
    collection: str,
    singular: str,
    errors: list[str],
) -> set[str]:
    label = _path_label(filename)
    if not isinstance(items, list):
        errors.append(f"{label}: {collection} must be an array")
        return set()
    if len(items) > MAX_ITEMS:
        errors.append(f"{label}: {collection} exceeds {MAX_ITEMS} items")
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{label}: {collection}[{index}] must be an object")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            errors.append(f"{label}: {singular} at index {index} has no non-empty id")
            continue
        if item_id in seen:
            errors.append(f"{label}: duplicate {singular} id {item_id!r}")
        seen.add(item_id)
    return seen


def _validate_controls(
    payload: dict[str, Any], errors: list[str]
) -> tuple[set[str], set[str], list[str]]:
    filename = "control-ontology.json"
    label = _path_label(filename)
    mechanisms_raw = payload.get("mechanism_types")
    if not isinstance(mechanisms_raw, list) or not all(
        isinstance(value, str) and value for value in mechanisms_raw
    ):
        errors.append(f"{label}: mechanism_types must be non-empty strings")
        mechanisms: set[str] = set()
    else:
        mechanisms = set(mechanisms_raw)
        if len(mechanisms) != len(mechanisms_raw):
            errors.append(f"{label}: duplicate mechanism type")
    controls_raw = payload.get("controls")
    control_ids = _unique_ids(
        controls_raw,
        filename=filename,
        collection="controls",
        singular="control",
        errors=errors,
    )
    if isinstance(controls_raw, list):
        for index, control in enumerate(controls_raw):
            if not isinstance(control, dict):
                continue
            control_id = control.get("id", f"index {index}")
            used = control.get("mechanisms")
            if not isinstance(used, list) or not used:
                errors.append(f"{label}: control {control_id!r} needs mechanisms")
                continue
            unknown = sorted(
                value for value in used if not isinstance(value, str) or value not in mechanisms
            )
            if unknown:
                errors.append(
                    f"{label}: control {control_id!r} uses unknown mechanisms {unknown}"
                )
    adult = payload.get("adult_requirement")
    if not isinstance(adult, dict):
        errors.append(f"{label}: adult_requirement must be an object")
    else:
        if adult.get("required") is not True:
            errors.append(f"{label}: adult requirement must be enabled")
        if adult.get("visual_inference_allowed") is not False:
            errors.append(f"{label}: visual age inference must remain disabled")
        if adult.get("ambiguous_or_youthful") != "refuse":
            errors.append(f"{label}: ambiguous or youthful identity must refuse")
        if adult.get("multi_adult_consent_context_required") is not True:
            errors.append(f"{label}: multi-adult consent context must remain required")
        if adult.get("public_fixture_class") != "sensual_non_explicit":
            errors.append(f"{label}: public fixture class must remain sensual_non_explicit")
    evidence_raw = payload.get("evidence_states")
    if not isinstance(evidence_raw, list) or not all(
        isinstance(value, str) and value for value in evidence_raw
    ):
        errors.append(f"{label}: evidence_states must be non-empty strings")
        evidence_states: list[str] = []
    else:
        evidence_states = list(evidence_raw)
        if len(set(evidence_states)) != len(evidence_states):
            errors.append(f"{label}: duplicate evidence state")
    return control_ids, mechanisms, evidence_states


def _validate_routes(
    payload: dict[str, Any],
    control_evidence_states: list[str],
    errors: list[str],
) -> set[str]:
    filename = "route-candidates.json"
    label = _path_label(filename)
    order = payload.get("evidence_order")
    if not isinstance(order, list) or not all(
        isinstance(value, str) and value for value in order
    ):
        errors.append(f"{label}: evidence_order must contain non-empty strings")
        order_values: list[str] = []
    else:
        order_values = list(order)
        if len(set(order_values)) != len(order_values):
            errors.append(f"{label}: duplicate evidence state in evidence_order")
        if control_evidence_states and order_values != control_evidence_states:
            errors.append(f"{label}: evidence_order must match control ontology evidence_states")
    candidates = payload.get("candidates")
    route_ids = _unique_ids(
        candidates,
        filename=filename,
        collection="candidates",
        singular="route",
        errors=errors,
    )
    if isinstance(candidates, list):
        for index, route in enumerate(candidates):
            if not isinstance(route, dict):
                continue
            route_id = route.get("id", f"index {index}")
            if route.get("executable") is not False:
                errors.append(f"{label}: route {route_id!r} must remain executable false")
            state = route.get("evidence_state")
            if state not in order_values:
                errors.append(
                    f"{label}: route {route_id!r} has unknown evidence state {state!r}"
                )
            source_url = route.get("source_url")
            if not isinstance(source_url, str) or not source_url.startswith("https://"):
                errors.append(
                    f"{label}: route {route_id!r} source_url must use https"
                )
            installed = route.get("installed")
            if installed not in (None, True, False):
                errors.append(
                    f"{label}: route {route_id!r} installed must be true, false or null"
                )
    return route_ids


def _validate_benchmarks(
    payload: dict[str, Any], control_ids: set[str], errors: list[str]
) -> set[str]:
    filename = "benchmark-corpus.json"
    label = _path_label(filename)
    cases = payload.get("cases")
    case_ids = _unique_ids(
        cases,
        filename=filename,
        collection="cases",
        singular="case",
        errors=errors,
    )
    if isinstance(cases, list):
        for index, case in enumerate(cases):
            if not isinstance(case, dict):
                continue
            case_id = case.get("id", f"index {index}")
            if case.get("content_class") != "sensual_non_explicit":
                errors.append(
                    f"{label}: case {case_id!r} must use sensual_non_explicit public content"
                )
            if case.get("public_fixture") != "synthetic_manifest_only":
                errors.append(
                    f"{label}: case {case_id!r} must remain a synthetic manifest fixture"
                )
            if case.get("real_sources_in_git") is not False:
                errors.append(f"{label}: case {case_id!r} must not store real sources in Git")
            if case.get("authorized_candidate_cap") != 0:
                errors.append(
                    f"{label}: case {case_id!r} authorized_candidate_cap must remain zero"
                )
            proposed = case.get("proposed_smoke_candidates")
            if not isinstance(proposed, int) or isinstance(proposed, bool) or not 0 <= proposed <= 32:
                errors.append(
                    f"{label}: case {case_id!r} proposed_smoke_candidates must be 0..32"
                )
            subjects = case.get("subjects")
            if not isinstance(subjects, list) or not subjects:
                errors.append(f"{label}: case {case_id!r} must declare adult subjects")
                subjects = []
            for subject_index, subject in enumerate(subjects):
                if (
                    not isinstance(subject, dict)
                    or subject.get("adult_assertion") != "reviewed_required"
                ):
                    errors.append(
                        f"{label}: case {case_id!r} subject {subject_index} "
                        "is missing reviewed adult assertion"
                    )
            if len(subjects) > 1 and case.get("consent_context") != "required":
                errors.append(
                    f"{label}: multi-subject case {case_id!r} requires consent context"
                )
            required = case.get("required_controls")
            if not isinstance(required, list) or not all(
                isinstance(value, str) and value for value in required
            ):
                errors.append(f"{label}: case {case_id!r} required_controls is invalid")
                required = []
            for control_id in required:
                if control_id not in control_ids:
                    errors.append(
                        f"{label}: case {case_id!r} references unknown control {control_id!r}"
                    )
    measures = payload.get("measures")
    if not isinstance(measures, list) or not all(
        isinstance(value, str) and value for value in measures
    ):
        errors.append(f"{label}: measures must contain non-empty strings")
    elif len(set(measures)) != len(measures):
        errors.append(f"{label}: duplicate measure")
    return case_ids


def _validate_packs(
    payload: dict[str, Any],
    case_ids: set[str],
    route_ids: set[str],
    errors: list[str],
) -> set[str]:
    filename = "genre-packs.json"
    label = _path_label(filename)
    packs = payload.get("packs")
    pack_ids = _unique_ids(
        packs,
        filename=filename,
        collection="packs",
        singular="pack",
        errors=errors,
    )
    if isinstance(packs, list):
        for index, pack in enumerate(packs):
            if not isinstance(pack, dict):
                continue
            pack_id = pack.get("id", f"index {index}")
            if pack.get("executable") is not False:
                errors.append(f"{label}: pack {pack_id!r} must remain executable false")
            if pack.get("adult_assertion_required") is not True:
                errors.append(f"{label}: pack {pack_id!r} must require adult assertion")
            if pack.get("content_class") != "sensual_non_explicit":
                errors.append(
                    f"{label}: pack {pack_id!r} must use sensual_non_explicit public content"
                )
            if pack.get("authorized_candidate_cap") != 0:
                errors.append(
                    f"{label}: pack {pack_id!r} authorized_candidate_cap must remain zero"
                )
            benchmark_cases = pack.get("benchmark_cases")
            if not isinstance(benchmark_cases, list) or not benchmark_cases:
                errors.append(f"{label}: pack {pack_id!r} needs benchmark cases")
                benchmark_cases = []
            for case_id in benchmark_cases:
                if case_id not in case_ids:
                    errors.append(
                        f"{label}: pack {pack_id!r} references unknown benchmark {case_id!r}"
                    )
            compatible = pack.get("compatible_routes")
            if not isinstance(compatible, list):
                errors.append(f"{label}: pack {pack_id!r} compatible_routes must be an array")
                compatible = []
            for route_id in compatible:
                if route_id not in route_ids:
                    errors.append(
                        f"{label}: pack {pack_id!r} references unknown route {route_id!r}"
                    )
            modules = pack.get("modules")
            if not isinstance(modules, list) or not all(
                isinstance(value, str) and value for value in modules
            ):
                errors.append(f"{label}: pack {pack_id!r} modules must be non-empty strings")
    return pack_ids


def _validate_adapter(
    payload: dict[str, Any], route_ids: set[str], errors: list[str]
) -> None:
    filename = "lora-qualification-example.json"
    label = _path_label(filename)
    adapter = payload.get("adapter")
    if not isinstance(adapter, dict):
        errors.append(f"{label}: adapter must be an object")
        return
    if adapter.get("authorized_candidate_cap") != 0:
        errors.append(f"{label}: adapter authorized_candidate_cap must remain zero")
    tested = adapter.get("tested_weights")
    if not isinstance(tested, list) or len(tested) < 2 or not all(
        _finite_number(value) for value in tested
    ):
        errors.append(
            f"{label}: adapter tested_weights needs at least two finite numbers"
        )
    else:
        if any(value < -4.0 or value > 4.0 for value in tested):
            errors.append(f"{label}: adapter tested_weights must stay bounded to -4..4")
        if any(left >= right for left, right in zip(tested, tested[1:])):
            errors.append(f"{label}: adapter tested_weights must be strictly increasing")
    promoted = adapter.get("promoted")
    if promoted is not False:
        errors.append(
            f"{label}: synthetic adapter template promoted must remain false"
        )
    base_routes = adapter.get("base_route_ids")
    if not isinstance(base_routes, list):
        errors.append(f"{label}: adapter base_route_ids must be an array")
    else:
        for route_id in base_routes:
            if route_id not in route_ids:
                errors.append(f"{label}: adapter references unknown route {route_id!r}")


def _validate_programme(payload: dict[str, Any], errors: list[str]) -> None:
    filename = "programme.json"
    label = _path_label(filename)
    if payload.get("epic") != 403 or payload.get("parent_issue") != 14:
        errors.append(f"{label}: programme must remain scoped to epic #403 under #14")
    issues = payload.get("issues")
    expected_issues = {
        "intent_controls": 404,
        "routes": 405,
        "adapters": 406,
        "geometry": 407,
        "multi_reference": 408,
        "evaluation": 409,
        "genre_packs": 410,
        "training": 411,
        "finishing": 412,
        "agents": 413,
        "prompt_dialects": 432,
        "source_intake": 433,
        "research_discovery": 435,
    }
    if not isinstance(issues, dict):
        errors.append(f"{label}: issues must be an object")
    else:
        missing = sorted(set(expected_issues) - set(issues))
        unknown = sorted(set(issues) - set(expected_issues))
        if missing:
            errors.append(f"{label}: missing issue owners {missing}")
        if unknown:
            errors.append(f"{label}: unknown issue owners {unknown}")
        for key, expected in expected_issues.items():
            if key in issues and issues[key] != expected:
                errors.append(
                    f"{label}: issue owner {key!r} must remain #{expected}"
                )
    if payload.get("entry_document") != "docs/adult-illustration/README.md":
        errors.append(f"{label}: entry_document must point to adult illustration README")


def validate_paths(root: Path) -> list[str]:
    """Return deterministic validation errors for the research manifests under *root*."""
    root = Path(root)
    errors: list[str] = []
    documents: dict[str, dict[str, Any]] = {}
    for filename in REQUIRED_MANIFESTS:
        payload = _load_manifest(root, filename, errors)
        if payload is not None:
            documents[filename] = payload
            _validate_common(filename, payload, errors)

    controls: set[str] = set()
    evidence_states: list[str] = []
    if "control-ontology.json" in documents:
        controls, _, evidence_states = _validate_controls(
            documents["control-ontology.json"], errors
        )

    route_ids: set[str] = set()
    if "route-candidates.json" in documents:
        route_ids = _validate_routes(
            documents["route-candidates.json"], evidence_states, errors
        )

    case_ids: set[str] = set()
    if "benchmark-corpus.json" in documents:
        case_ids = _validate_benchmarks(
            documents["benchmark-corpus.json"], controls, errors
        )

    if "genre-packs.json" in documents:
        _validate_packs(
            documents["genre-packs.json"], case_ids, route_ids, errors
        )

    if "lora-qualification-example.json" in documents:
        _validate_adapter(
            documents["lora-qualification-example.json"], route_ids, errors
        )

    if "programme.json" in documents:
        _validate_programme(documents["programme.json"], errors)

    return sorted(set(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate static controlled adult illustration research manifests."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (defaults to the parent of scripts/)",
    )
    args = parser.parse_args(argv)
    errors = validate_paths(args.root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("adult illustration manifests: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
