#!/usr/bin/env python3
"""Strict Adult Illustration manifest validator with extended issue ownership."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


_IMPL_PATH = Path(__file__).with_name("_validate_adult_illustration_impl.py")
_SPEC = importlib.util.spec_from_file_location(
    "_validate_adult_illustration_impl",
    _IMPL_PATH,
)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"cannot load Adult Illustration validator from {_IMPL_PATH}")
_base = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_base)


def _validate_programme(payload: dict[str, Any], errors: list[str]) -> None:
    filename = "programme.json"
    label = _base._path_label(filename)
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
        "prompt_profiles": 437,
        "source_snapshots": 438,
        "first_qualification": 439,
        "adapter_lab": 440,
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


_base._validate_programme = _validate_programme
validate_paths = _base.validate_paths


def main(argv: list[str] | None = None) -> int:
    return _base.main(argv)


def __getattr__(name: str) -> Any:
    return getattr(_base, name)


if __name__ == "__main__":
    raise SystemExit(main())
