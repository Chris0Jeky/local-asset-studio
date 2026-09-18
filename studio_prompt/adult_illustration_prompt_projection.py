"""Public prompt projection API with fail-closed constraint binding."""
from __future__ import annotations

from typing import Any

from . import _adult_illustration_prompt_projection_impl as _base


_ORIGINAL_CONTROL_DIAGNOSTICS = _base._control_diagnostics


def _validated_constraints(
    creative: dict[str, Any],
) -> list[dict[str, Any]]:
    raw_constraints = creative.get("constraints")
    if not isinstance(raw_constraints, list) or len(raw_constraints) > _base.MAX_ITEMS:
        raise ValueError("CreativeIntent constraints must be a bounded array")
    expected_fields = {"id", "text", "mechanism", "priority"}
    values: list[dict[str, Any]] = []
    for index, constraint in enumerate(raw_constraints):
        if not isinstance(constraint, dict) or set(constraint) != expected_fields:
            raise ValueError(
                f"CreativeIntent constraint {index} has missing or unknown fields"
            )
        constraint_id = _base._text(
            constraint.get("id"),
            f"constraint {index} id",
            128,
        )
        _base._text(
            constraint.get("text"),
            f"constraint {constraint_id} text",
        )
        mechanism = _base._text(
            constraint.get("mechanism"),
            f"constraint {constraint_id} mechanism",
            32,
        )
        if mechanism not in {"prompt", "verify", "guide", "mask"}:
            raise ValueError(f"constraint {constraint_id!r} mechanism is unsupported")
        priority = _base._text(
            constraint.get("priority"),
            f"constraint {constraint_id} priority",
            16,
        )
        if priority not in {"hard", "soft"}:
            raise ValueError(f"constraint {constraint_id!r} priority is unsupported")
        values.append(constraint)
    return values


def _constraint_diagnostics(
    source: dict[str, Any],
    diagnostics: list[dict[str, Any]],
) -> bool:
    """Retain guide/mask constraints as explicit route-binding requirements."""

    creative = source.get("creative_intent")
    if not isinstance(creative, dict):
        raise ValueError("CreativeIntent projection must be an object")
    requires_binding = False
    for constraint in _validated_constraints(creative):
        mechanism = constraint["mechanism"]
        if mechanism not in {"guide", "mask"}:
            continue
        requires_binding = True
        constraint_id = constraint["id"]
        _base._diag(
            diagnostics,
            "CONSTRAINT_REQUIRES_ROUTE_BINDING",
            "requirement",
            f"Constraint {constraint_id!r} uses {mechanism!r} and was not "
            "converted into prompt prose.",
            constraint_id=constraint_id,
            mechanism=mechanism,
            priority=constraint["priority"],
        )
    return requires_binding


def _control_diagnostics(
    source: dict[str, Any],
    diagnostics: list[dict[str, Any]],
) -> bool:
    control_binding = _ORIGINAL_CONTROL_DIAGNOSTICS(source, diagnostics)
    constraint_binding = _constraint_diagnostics(source, diagnostics)
    return control_binding or constraint_binding


def _compile_instruction(
    creative: dict[str, Any],
    bindings: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
) -> dict[str, str | None]:
    """Compile semantic constraints while leaving guides and masks unresolved."""

    lines = [
        "Create a new adult-only sensual non-explicit illustration.",
        f"Goal: {_base._text(creative['brief'], 'creative brief')}",
    ]
    for binding in bindings:
        take = (
            ", ".join(binding["take"])
            if binding["take"]
            else "the reviewed role only"
        )
        ignore = (
            ", ".join(binding["ignore"])
            if binding["ignore"]
            else "all unlisted source traits"
        )
        lines.append(
            f"Image {binding['index']} defines only {binding['role']}. "
            f"Use: {take}. Do not copy: {ignore}."
        )
    for key, value in creative["facets"].items():
        lines.append(f"{key.replace('_', ' ').title()}: {value}")
    for constraint in _validated_constraints(creative):
        if constraint["mechanism"] in {"guide", "mask"}:
            continue
        text = _base._text(constraint["text"], "constraint text")
        lines.append(f"Preserve: {text}")
    if creative["avoid"]:
        lines.append("Exclude: " + ", ".join(creative["avoid"]) + ".")
    if creative["tags"]:
        _base._diag(
            diagnostics,
            "TAGS_NOT_EMITTED_FOR_INSTRUCTION_PROFILE",
            "information",
            "Tag vocabulary remains inspectable but is not dumped into the "
            "natural-language instruction profile.",
        )
    return {"positive": None, "negative": None, "instruction": "\n".join(lines)}


# The implementation resolves these helpers from its own module at call time.
_base._control_diagnostics = _control_diagnostics
_base._compile_instruction = _compile_instruction

compile_prompt = _base.compile_prompt
validate_prompt_projection = _base.validate_prompt_projection


def __getattr__(name: str) -> Any:
    """Preserve access to implementation constants/helpers for stacked callers."""

    return getattr(_base, name)


__all__ = ["compile_prompt", "validate_prompt_projection"]
