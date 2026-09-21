"""Strict source intent for reviewed adult-only controlled illustration."""
from __future__ import annotations

import copy
import re

from .schema import canonical, fields, identifier, need, strings, text


INTENT_FORMAT = "studio.adult-illustration.intent/v1"
MAX_BYTES = 65536

FACETS = (
    "body",
    "pose",
    "wardrobe",
    "expression",
    "setting",
    "composition",
    "camera",
    "lighting",
    "style",
    "palette",
    "mood",
    "material",
)
CONTROL_TARGETS = {
    "subject.identity",
    "subject.adult_assertion",
    "body.silhouette",
    "pose.action",
    "contact.relationship",
    "camera.composition",
    "wardrobe.construction",
    "wardrobe.coverage",
    "expression.gaze",
    "scene.environment",
    "lighting.palette",
    "material.surface",
    "style.rendering",
    "reference.transfer",
    "edit.write_scope",
    "finish.derivative",
    "review.acceptance",
}
CONTROL_MECHANISMS = {
    "semantic_text",
    "vocabulary_choice",
    "bounded_number",
    "geometry_artifact",
    "appearance_adapter",
    "reference_binding",
    "mask_authority",
    "deterministic_operation",
    "review_decision",
}
REFERENCE_ROLES = {
    "identity",
    "body_design",
    "outfit",
    "pose",
    "camera",
    "composition",
    "style",
    "palette",
    "material",
    "environment",
    "prop",
    "edit_source",
    "protection",
}
LOCKS = {
    "brief",
    "subjects",
    "facets",
    "tags",
    "avoid",
    "controls",
    "references",
    "constraints",
    "content",
}
RESERVED_CONSTRAINTS = {
    "adult-status",
    "content-envelope",
    "coverage",
    "consent-context",
}
CONTENT_CLASSES = {"sensual_non_explicit"}
ADULT_ASSERTIONS = {"reviewed_owner_or_canon"}
CONSENT_CONTEXTS = {"not_applicable", "reviewed_consensual"}
COVERAGE = {
    "opaque_critical_coverage",
    "reviewed_non_explicit_coverage",
    "route_review_required",
}


def bounded(value):
    need(len(canonical(value)) <= MAX_BYTES, "Adult illustration intent exceeds 64 KiB")
    return copy.deepcopy(value)


def _portable_path(value):
    text(value, 500)
    need(
        "\\" not in value
        and ":" not in value
        and all(part not in ("", ".", "..") for part in value.split("/")),
        "Unsafe reference path",
    )


def _sha256(value):
    need(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value),
        "Reference needs a SHA256",
    )


def _unique_strings(values, *, count, maximum, message):
    strings(values, count, maximum)
    need(len(values) == len(set(values)), message)


def _subject_ids(subjects):
    ids = []
    for item in subjects:
        identifier(item["id"])
        need(item["id"] not in ids, "Duplicate subject ID")
        ids.append(item["id"])
    return set(ids)


def validate_intent(value):
    """Validate and return a detached copy of an adult illustration intent."""
    fields(
        value,
        (
            "format",
            "id",
            "task",
            "brief",
            "content",
            "subjects",
            "facets",
            "tags",
            "avoid",
            "controls",
            "references",
            "constraints",
            "locked",
            "execution_authorized",
            "generation_submitted",
        ),
    )
    need(value["format"] == INTENT_FORMAT, "Unsupported adult illustration intent")
    identifier(value["id"])
    need(value["task"] in ("image", "edit"), "Adult illustration task must be image or edit")
    text(value["brief"], 4000)

    content = value["content"]
    fields(content, ("class", "adult_assertion", "consent_context", "coverage"))
    need(content["class"] in CONTENT_CLASSES, "Unsupported public content class")
    need(
        content["adult_assertion"] in ADULT_ASSERTIONS,
        "Adult assertion must come from reviewed owner or canon metadata",
    )
    need(content["consent_context"] in CONSENT_CONTEXTS, "Unsupported consent context")
    need(content["coverage"] in COVERAGE, "Unsupported coverage declaration")

    subjects = value["subjects"]
    need(type(subjects) is list and 1 <= len(subjects) <= 4, "Declare one to four adult subjects")
    for subject in subjects:
        need(
            isinstance(subject, dict) and "adult_assertion" in subject,
            "Every subject needs reviewed adult metadata",
        )
        fields(subject, ("id", "description", "adult_assertion"))
        text(subject["description"], 1000)
        need(
            subject["adult_assertion"] in ADULT_ASSERTIONS,
            "Every subject needs reviewed adult metadata",
        )
    subject_ids = _subject_ids(subjects)
    if len(subjects) > 1:
        need(
            content["consent_context"] == "reviewed_consensual",
            "Multi-subject adult intent requires reviewed consent context",
        )

    facets = value["facets"]
    fields(facets, (), FACETS)
    for item in facets.values():
        text(item, 1000)
    _unique_strings(value["tags"], count=80, maximum=120, message="Duplicate tag")
    _unique_strings(value["avoid"], count=30, maximum=200, message="Duplicate avoidance")

    controls = value["controls"]
    need(type(controls) is list and len(controls) <= 32, "Control cap exceeded")
    control_ids = set()
    for control in controls:
        fields(control, ("id", "target", "mechanism", "priority", "description"))
        identifier(control["id"])
        need(control["id"] not in control_ids, "Duplicate control ID")
        control_ids.add(control["id"])
        need(control["target"] in CONTROL_TARGETS, "Unsupported control target")
        need(control["mechanism"] in CONTROL_MECHANISMS, "Unsupported control mechanism")
        need(control["priority"] in ("hard", "soft"), "Invalid control priority")
        text(control["description"], 500)

    references = value["references"]
    need(type(references) is list and len(references) <= 8, "At most eight source references")
    reference_ids = set()
    for reference in references:
        fields(
            reference,
            (
                "id",
                "roles",
                "kind",
                "path",
                "sha256",
                "take",
                "ignore",
                "subject_id",
                "region_id",
            ),
        )
        identifier(reference["id"])
        need(reference["id"] not in reference_ids, "Duplicate reference ID")
        reference_ids.add(reference["id"])
        roles = reference["roles"]
        need(type(roles) is list and 1 <= len(roles) <= 4, "Reference needs one to four roles")
        _unique_strings(roles, count=4, maximum=32, message="Duplicate reference role")
        need(set(roles) <= REFERENCE_ROLES, "Unsupported reference role")
        need(reference["kind"] in ("image", "video", "mesh"), "Unsupported reference kind")
        _portable_path(reference["path"])
        _sha256(reference["sha256"])
        _unique_strings(reference["take"], count=12, maximum=300, message="Duplicate take item")
        _unique_strings(reference["ignore"], count=12, maximum=300, message="Duplicate ignore item")
        subject_id = reference["subject_id"]
        need(subject_id is None or subject_id in subject_ids, "Reference subject does not exist")
        if reference["region_id"] is not None:
            identifier(reference["region_id"])

    constraints = value["constraints"]
    need(type(constraints) is list and len(constraints) <= 20, "Constraint cap exceeded")
    constraint_ids = set()
    for constraint in constraints:
        fields(constraint, ("id", "text", "mechanism", "priority"))
        identifier(constraint["id"])
        need(
            constraint["id"] not in RESERVED_CONSTRAINTS,
            "Constraint ID is reserved by the content envelope",
        )
        need(constraint["id"] not in constraint_ids, "Duplicate constraint ID")
        constraint_ids.add(constraint["id"])
        text(constraint["text"], 500)
        need(
            constraint["mechanism"] in ("prompt", "mask", "guide", "verify"),
            "Invalid constraint mechanism",
        )
        need(constraint["priority"] in ("hard", "soft"), "Invalid constraint priority")

    _unique_strings(value["locked"], count=16, maximum=32, message="Duplicate lock")
    need(set(value["locked"]) <= LOCKS, "Unsupported adult illustration lock")
    need(value["execution_authorized"] is False, "Intent cannot authorize execution")
    need(value["generation_submitted"] is False, "Intent cannot submit generation")
    return bounded(value)


def new_intent(
    brief,
    subjects,
    *,
    intent_id="adult-illustration",
    task="image",
    consent_context="not_applicable",
    coverage="opaque_critical_coverage",
):
    """Create a minimal reviewed intent; consent is explicit and no runtime is touched."""
    return validate_intent(
        {
            "format": INTENT_FORMAT,
            "id": intent_id,
            "task": task,
            "brief": brief,
            "content": {
                "class": "sensual_non_explicit",
                "adult_assertion": "reviewed_owner_or_canon",
                "consent_context": consent_context,
                "coverage": coverage,
            },
            "subjects": copy.deepcopy(subjects),
            "facets": {},
            "tags": [],
            "avoid": [],
            "controls": [],
            "references": [],
            "constraints": [],
            "locked": [],
            "execution_authorized": False,
            "generation_submitted": False,
        }
    )
