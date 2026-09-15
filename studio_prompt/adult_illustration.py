"""Public facade for adult-only controlled illustration intent and projection.

Importing this module performs no I/O, model discovery, graph binding or inference.
"""
from .adult_illustration_schema import (
    ADULT_ASSERTIONS,
    CONSENT_CONTEXTS,
    CONTENT_CLASSES,
    CONTROL_MECHANISMS,
    CONTROL_TARGETS,
    COVERAGE,
    FACETS,
    INTENT_FORMAT,
    LOCKS,
    REFERENCE_ROLES,
    RESERVED_CONSTRAINTS,
    new_intent,
    validate_intent,
)
from .adult_illustration_projection import (
    PROJECTION_FORMAT,
    ROLE_MAP,
    project,
    validate_projection,
)

__all__ = (
    "ADULT_ASSERTIONS",
    "CONSENT_CONTEXTS",
    "CONTENT_CLASSES",
    "CONTROL_MECHANISMS",
    "CONTROL_TARGETS",
    "COVERAGE",
    "FACETS",
    "INTENT_FORMAT",
    "LOCKS",
    "PROJECTION_FORMAT",
    "REFERENCE_ROLES",
    "RESERVED_CONSTRAINTS",
    "ROLE_MAP",
    "new_intent",
    "project",
    "validate_intent",
    "validate_projection",
)
