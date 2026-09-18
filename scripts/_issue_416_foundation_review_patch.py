#!/usr/bin/env python3
"""Temporary branch-only correction for the remaining PR #416 review findings."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LANDSCAPE = ROOT / "docs" / "adult-illustration" / "MODEL-AND-TECHNIQUE-LANDSCAPE.md"
README = ROOT / "docs" / "adult-illustration" / "README.md"
EVALUATION = ROOT / "docs" / "adult-illustration" / "EVALUATION.md"
CORPUS = ROOT / "research" / "adult-illustration" / "benchmark-corpus.json"
PACKS = ROOT / "research" / "adult-illustration" / "genre-packs.json"
ROUTES = ROOT / "research" / "adult-illustration" / "route-candidates.json"
CASE_ID = "adult-street-fashion-urban-night"

STALE_ANIMA = (
    "**Anima Turbo** is a source-reviewed candidate for composition search. "
    "Its card describes"
)
STALE_HEADING = "Source-reviewed first-wave baselines:"
STALE_GATE = (
    "**A0 — contracts:** intent/control ontology, source-reviewed candidates, "
    "finite corpus, validator and agent runbook."
)
DISCOVERY_NOTE = (
    "Entries whose manifest state is `discovered` remain moving-source research "
    "leads. Card-derived statements below are provider claims awaiting an immutable "
    "revision or retained snapshot; they are not completed source review."
)

CASE: dict[str, Any] = {
    "id": CASE_ID,
    "kind": "genre",
    "public_fixture": "synthetic_manifest_only",
    "content_class": "sensual_non_explicit",
    "subjects": [
        {
            "id": "adult-a",
            "adult_assertion": "reviewed_required",
        }
    ],
    "consent_context": "not_applicable",
    "fixed_scenario": {
        "wardrobe": "composed_street_fashion_outfit",
        "environment": "recognizable_street_level_urban_setting",
        "lighting": "mixed_urban_practicals_affect_subject_and_scene",
        "framing": "outfit_readable_editorial_frame",
    },
    "required_controls": [
        "subject.identity",
        "subject.adult_assertion",
        "wardrobe.construction",
        "wardrobe.coverage",
        "camera.composition",
        "scene.environment",
        "lighting.palette",
        "style.rendering",
    ],
    "proposed_smoke_candidates": 2,
    "authorized_candidate_cap": 0,
    "real_sources_in_git": False,
}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: expected an object")
    return value


def dump(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def find_by_id(items: Any, item_id: str, label: str) -> dict[str, Any]:
    if not isinstance(items, list):
        raise SystemExit(f"{label}: expected an array")
    matches = [item for item in items if isinstance(item, dict) and item.get("id") == item_id]
    if len(matches) != 1:
        raise SystemExit(f"{label}: expected exactly one {item_id!r}, found {len(matches)}")
    return matches[0]


def assert_old() -> None:
    landscape = LANDSCAPE.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    corpus = load(CORPUS)
    packs = load(PACKS)
    if STALE_ANIMA not in landscape or STALE_HEADING not in landscape:
        raise SystemExit("Expected stale source-review prose is not present")
    if STALE_GATE not in readme:
        raise SystemExit("Expected stale A0 source-review wording is not present")
    case_ids = {
        item.get("id")
        for item in corpus.get("cases", [])
        if isinstance(item, dict)
    }
    if CASE_ID in case_ids:
        raise SystemExit("Street-specific benchmark already exists")
    street = find_by_id(packs.get("packs"), "street-fashion", "genre packs")
    if street.get("benchmark_cases") == [CASE_ID]:
        raise SystemExit("Street pack already uses the specific benchmark")


def apply() -> None:
    landscape = LANDSCAPE.read_text(encoding="utf-8")
    if DISCOVERY_NOTE not in landscape:
        anchor = (
            "Research freeze: 15 September 2026. These are candidates and hypotheses, "
            "not installed or promoted routes. Exact files, hashes, graphs, resources "
            "and terms must be captured through #9/#144 before execution."
        )
        if landscape.count(anchor) != 1:
            raise SystemExit("Landscape introduction anchor changed")
        landscape = landscape.replace(anchor, anchor + "\n\n" + DISCOVERY_NOTE)
    replacements = {
        STALE_ANIMA: (
            "**Anima Turbo** is a discovered composition-search candidate. "
            "The current moving provider card describes"
        ),
        STALE_HEADING: "First-wave discovery candidates awaiting immutable source snapshots:",
        (
            "**Qwen Image Edit 2511** is the primary first-wave candidate because it "
            "documents"
        ): (
            "The current moving provider card makes **Qwen Image Edit 2511** a primary "
            "first-wave discovery candidate because it describes"
        ),
        (
            "For Anima, the official card recommends Base for LoRAs, not training its "
            "LLM adapter, using a low learning rate and starting around rank 32 / `2e-5`."
        ): (
            "The current moving Anima card recommends Base for LoRAs, not training its "
            "LLM adapter, using a low learning rate and starting around rank 32 / `2e-5`."
        ),
    }
    for old, new in replacements.items():
        if landscape.count(old) != 1:
            raise SystemExit(f"Landscape replacement count for {old!r} was not one")
        landscape = landscape.replace(old, new)
    LANDSCAPE.write_text(landscape, encoding="utf-8")

    readme = README.read_text(encoding="utf-8")
    if readme.count(STALE_GATE) != 1:
        raise SystemExit("README A0 wording changed")
    readme = readme.replace(
        STALE_GATE,
        "**A0 — contracts:** intent/control ontology, source-evidence candidates, "
        "finite corpus, validator and agent runbook.",
    )
    README.write_text(readme, encoding="utf-8")

    evaluation = EVALUATION.read_text(encoding="utf-8")
    paragraph = (
        "Named genre cases also bind fixed scenario outcomes; generic control IDs alone "
        "cannot qualify a pack. The street-fashion case requires one composed street "
        "outfit, a recognizable street-level urban setting, mixed urban practical "
        "lighting affecting subject and scene, and framing that keeps the outfit readable."
    )
    anchor = "All subjects are declared adult through reviewed metadata. Public briefs remain non-explicit."
    if paragraph not in evaluation:
        if evaluation.count(anchor) != 1:
            raise SystemExit("Evaluation corpus anchor changed")
        evaluation = evaluation.replace(anchor, anchor + "\n\n" + paragraph)
    EVALUATION.write_text(evaluation, encoding="utf-8")

    corpus = load(CORPUS)
    cases = corpus.get("cases")
    if not isinstance(cases, list):
        raise SystemExit("Benchmark cases are not an array")
    if any(isinstance(item, dict) and item.get("id") == CASE_ID for item in cases):
        raise SystemExit("Street-specific benchmark unexpectedly already exists")
    insert_after = next(
        (
            index
            for index, item in enumerate(cases)
            if isinstance(item, dict) and item.get("id") == "adult-scifi-cyber"
        ),
        None,
    )
    if insert_after is None:
        raise SystemExit("Could not find adult-scifi-cyber insertion anchor")
    cases.insert(insert_after + 1, CASE)
    dump(CORPUS, corpus)

    packs = load(PACKS)
    street = find_by_id(packs.get("packs"), "street-fashion", "genre packs")
    street["benchmark_cases"] = [CASE_ID]
    dump(PACKS, packs)


def verify() -> None:
    landscape = LANDSCAPE.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    evaluation = EVALUATION.read_text(encoding="utf-8")
    if STALE_ANIMA in landscape or STALE_HEADING in landscape:
        raise SystemExit("Stale source-reviewed prose remains")
    if DISCOVERY_NOTE not in landscape:
        raise SystemExit("Discovery/source-review boundary is missing")
    if "source-reviewed candidates" in readme:
        raise SystemExit("README still claims source-reviewed candidates")
    if "generic control IDs alone cannot qualify a pack" not in evaluation:
        raise SystemExit("Evaluation does not state the genre-specific gate")

    routes = load(ROUTES)
    for route in routes.get("candidates", []):
        if not isinstance(route, dict):
            raise SystemExit("Route candidate must be an object")
        if route.get("source_revision") == "main" and route.get("evidence_state") != "discovered":
            raise SystemExit(
                f"Moving route {route.get('id')!r} is not conservatively discovered"
            )

    corpus = load(CORPUS)
    cases = corpus.get("cases")
    case = find_by_id(cases, CASE_ID, "benchmark corpus")
    if case != CASE:
        raise SystemExit("Street benchmark does not match the reviewed fixed contract")
    ids = [item.get("id") for item in cases if isinstance(item, dict)]
    if len(ids) != len(set(ids)):
        raise SystemExit("Benchmark IDs are not unique")
    if len(ids) != 21:
        raise SystemExit(f"Expected 21 benchmark cases, found {len(ids)}")

    packs = load(PACKS)
    street = find_by_id(packs.get("packs"), "street-fashion", "genre packs")
    if street.get("benchmark_cases") != [CASE_ID]:
        raise SystemExit("Street pack is not bound exclusively to its specific benchmark")
    if street.get("authorized_candidate_cap") != 0 or street.get("executable") is not False:
        raise SystemExit("Street pack authority boundary changed")
    if CASE_ID not in ids:
        raise SystemExit("Street pack benchmark target is missing")

    fixed = case.get("fixed_scenario")
    required_fixed = {
        "wardrobe": "composed_street_fashion_outfit",
        "environment": "recognizable_street_level_urban_setting",
        "lighting": "mixed_urban_practicals_affect_subject_and_scene",
        "framing": "outfit_readable_editorial_frame",
    }
    if fixed != required_fixed:
        raise SystemExit("Street case fixed scenario is incomplete")
    required_controls = set(case.get("required_controls", []))
    expected_controls = {
        "subject.identity",
        "subject.adult_assertion",
        "wardrobe.construction",
        "wardrobe.coverage",
        "camera.composition",
        "scene.environment",
        "lighting.palette",
        "style.rendering",
    }
    if not expected_controls.issubset(required_controls):
        raise SystemExit("Street case is missing required controls")
    if case.get("authorized_candidate_cap") != 0:
        raise SystemExit("Street case candidate authority is not zero")
    if case.get("public_fixture") != "synthetic_manifest_only":
        raise SystemExit("Street case is not synthetic-only")
    if case.get("real_sources_in_git") is not False:
        raise SystemExit("Street case stores real sources")


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "assert-old":
        assert_old()
    elif command == "apply":
        apply()
    elif command == "verify":
        verify()
    else:
        raise SystemExit("usage: patch.py {assert-old|apply|verify}")


if __name__ == "__main__":
    main()
