"""Synthetic contract fixtures for adult-illustration intelligence validation."""
from __future__ import annotations

import json
from pathlib import Path

BASELINE = "d73f67db48257e635def2170b67cefd6a3165098"


def common(schema, kind):
    return {
        "schema": schema,
        "kind": kind,
        "executable": False,
        "authority": "none",
        "research_date": "2026-09-15",
        "source_baseline": BASELINE,
    }


def valid_documents():
    routes = common("studio.adult-illustration-route-candidates/v0", "research-candidates")
    routes["candidates"] = [
        {"id": "route-a"},
        {"id": "route-b"},
    ]

    dialects = common(
        "studio.adult-illustration-prompt-dialects/v0", "prompt-dialect-candidates"
    )
    dialects.update(
        {
            "issue": 432,
            "profiles": [
                {
                    "id": "tag-profile",
                    "route_candidate_ids": ["route-a"],
                    "mode": "tag",
                    "evidence_state": "source_reviewed",
                    "ready_for_compilation": False,
                    "source_urls": ["https://example.com/model-card"],
                    "source_revision": "main",
                    "tag_separator": ", ",
                    "ordered_sections": ["subjects", "actions", "quality"],
                    "negative_semantics": "graph_specific",
                    "weighting_semantics": "unresolved",
                    "natural_language": "limited",
                    "vocabulary_ids": ["contract-vocabulary"],
                    "unsupported_mechanisms": ["geometry_artifact", "mask_authority"],
                    "unknowns": ["exact tokenizer limit"],
                },
                {
                    "id": "instruction-profile",
                    "route_candidate_ids": ["route-b"],
                    "mode": "instruction",
                    "evidence_state": "source_reviewed",
                    "ready_for_compilation": False,
                    "source_urls": ["https://example.com/edit-card"],
                    "source_revision": "main",
                    "tag_separator": None,
                    "ordered_sections": ["reference ownership", "edit", "invariants"],
                    "negative_semantics": "prompt_instruction",
                    "weighting_semantics": "unsupported",
                    "natural_language": "primary",
                    "vocabulary_ids": [],
                    "unsupported_mechanisms": ["mask_authority"],
                    "unknowns": ["exact local quantized behavior"],
                },
            ],
        }
    )

    vocabulary = common(
        "studio.adult-illustration-tag-vocabulary/v0", "tag-vocabulary-contract"
    )
    vocabulary.update(
        {
            "issue": 432,
            "accepted_for_compilation": False,
            "entries": [
                {
                    "id": "contract-vocabulary",
                    "canonical": "three quarter view",
                    "display": "three-quarter view",
                    "aliases": ["three-quarter view"],
                    "implications": [],
                    "deprecated_by": None,
                    "semantic_facets": ["camera"],
                    "source": {
                        "kind": "contract_example",
                        "url": None,
                        "revision": None,
                    },
                    "status": "contract_example",
                    "route_profile_ids": ["tag-profile"],
                    "accepted": False,
                }
            ],
        }
    )

    techniques = common(
        "studio.adult-illustration-technique-candidates/v0", "technique-candidates"
    )
    techniques.update(
        {
            "issue": 403,
            "candidates": [
                {
                    "id": "adapter-watch",
                    "category": "appearance_adapter",
                    "evidence_state": "source_reviewed",
                    "source_urls": ["https://example.com/adapter"],
                    "source_revision": "main",
                    "code_state": "source_available",
                    "weight_state": "source_available",
                    "installed": None,
                    "executable": False,
                    "ready_for_qualification": False,
                    "exact_compatibility_required": True,
                    "proposed_role": "identity appearance conditioning",
                    "promotion_blockers": ["no local graph or resource evidence"],
                    "issue_owner": 408,
                },
                {
                    "id": "paper-watch",
                    "category": "research_watch",
                    "evidence_state": "discovered",
                    "source_urls": ["https://arxiv.org/abs/2605.20237"],
                    "source_revision": None,
                    "code_state": "not_released",
                    "weight_state": "not_released",
                    "installed": None,
                    "executable": False,
                    "ready_for_qualification": False,
                    "exact_compatibility_required": True,
                    "proposed_role": "future pose-aware anime identity conditioning",
                    "promotion_blockers": ["code and weights unavailable"],
                    "issue_owner": 408,
                },
            ],
        }
    )

    source_intake = common(
        "studio.adult-illustration-source-intake/v0", "source-intake-examples"
    )
    source_intake.update(
        {
            "issue": 433,
            "records": [
                {
                    "id": "hf-example",
                    "provider": "huggingface",
                    "synthetic": True,
                    "canonical_url": "https://huggingface.co/example-org/example-model",
                    "provider_model_id": "example-org/example-model",
                    "provider_version_id": None,
                    "immutable_revision": None,
                    "snapshot_state": "proposal",
                    "terms_state": "unknown",
                    "claims": [],
                    "files": [
                        {
                            "id": "weights",
                            "path": "model.safetensors",
                            "bytes": None,
                            "sha256": None,
                            "provider_hashes": {},
                            "selected": False,
                        }
                    ],
                    "download_authorized": False,
                    "install_authorized": False,
                    "execution_authorized": False,
                },
                {
                    "id": "civitai-example",
                    "provider": "civitai",
                    "synthetic": True,
                    "canonical_url": "https://civitai.com/models/123456?modelVersionId=654321",
                    "provider_model_id": 123456,
                    "provider_version_id": 654321,
                    "immutable_revision": "654321",
                    "snapshot_state": "proposal",
                    "terms_state": "unknown",
                    "claims": [],
                    "files": [],
                    "download_authorized": False,
                    "install_authorized": False,
                    "execution_authorized": False,
                },
            ],
        }
    )

    return {
        "route-candidates.json": routes,
        "prompt-dialects.json": dialects,
        "tag-vocabulary-example.json": vocabulary,
        "technique-candidates.json": techniques,
        "source-intake-example.json": source_intake,
    }


def write_documents(root, documents):
    directory = root / "research" / "adult-illustration"
    directory.mkdir(parents=True, exist_ok=True)
    for name, value in documents.items():
        (directory / name).write_text(
            json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8"
        )
