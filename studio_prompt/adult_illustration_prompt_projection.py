"""Public prompt projection API with fail-closed constraint binding."""
from __future__ import annotations

from typing import Any

from . import _adult_illustration_prompt_projection_impl as _base


_ORIGINAL_CONTROL_DIAGNOSTICS = _base._control_diagnostics


def _constraint_bindings(
    source: dict[str, Any],
    diagnostics: list[dict[str, Any]],
) -> bool:
    """Remove guide/mask constraints from prose and retain binding requirements."""

    creative = source.get("creative_intent")
    if not isinstance(creative, dict):
        raise ValueError("CreativeIntent projection must be an object")
    raw_constraints = creative.get("constraints")
    if not isinstance(raw_constraints, list) or len(raw_constraints) > _base.MAX_ITEMS:
        raise ValueError("CreativeIntent constraints must be a bounded array")

    promptable: list[dict[str, Any]] = []
    requires_binding = False
    expected_fields = {"id", "text", "mechanism", "priority"}
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
        priority = _base._text(
            constraint.get("priority"),
            f"constraint {constraint_id} priority",
            16,
        )
        if mechanism in {"guide", "mask"}:
            requires_binding = True
            _base._diag(
                diagnostics,
                "CONSTRAINT_REQUIRES_ROUTE_BINDING",
                "requirement",
                f"Constraint {constraint_id!r} uses {mechanism!r} and was not "
                "converted into prompt prose.",
                constraint_id=constraint_id,
                mechanism=mechanism,
                priority=priority,
            )
        else:
            promptable.append(constraint)

    # ``creative`` is the detached, validated source copy used later by the base
    # compiler, so replacing this list cannot mutate the caller's projection.
    creative["constraints"] = promptable
    return requires_binding


def _control_diagnostics(
    source: dict[str, Any],
    diagnostics: list[dict[str, Any]],
) -> bool:
    control_binding = _ORIGINAL_CONTROL_DIAGNOSTICS(source, diagnostics)
    constraint_binding = _constraint_bindings(source, diagnostics)
    return control_binding or constraint_binding


# The implementation resolves this helper from its own module at call time.
_base._control_diagnostics = _control_diagnostics

compile_prompt = _base.compile_prompt
validate_prompt_projection = _base.validate_prompt_projection


def __getattr__(name: str) -> Any:
    """Preserve access to implementation constants/helpers for stacked callers."""

    return getattr(_base, name)


__all__ = ["compile_prompt", "validate_prompt_projection"]
