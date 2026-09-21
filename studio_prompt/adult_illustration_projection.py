"""Project reviewed adult-illustration semantics into existing CreativeIntent."""
from __future__ import annotations

import copy
from collections import OrderedDict

from .adult_illustration_schema import (
    MAX_BYTES as INTENT_MAX_BYTES,
    validate_intent,
)
from .schema import canonical, digest, fields, need, validate


PROJECTION_FORMAT = "studio.adult-illustration.projection/v1"
CREATIVE_FACET_MAX_CHARS = 1_000
CREATIVE_INTENT_MAX_BYTES = 65_536
PROJECTION_MAX_BYTES = 4 * INTENT_MAX_BYTES
ROLE_MAP = {
    "identity": "identity",
    "body_design": "identity",
    "outfit": "costume",
    "pose": "pose",
    "camera": "composition",
    "composition": "composition",
    "style": "style",
    "palette": "style",
    "material": "style",
    "environment": "composition",
    "prop": "composition",
    "protection": "mask",
    # The base edit source needs a route-specific edit binding.
    "edit_source": None,
}


def _creative_reference_id(source_id, creative_role, group_count):
    if group_count == 1:
        return source_id
    candidate = f"{source_id}-{creative_role}"
    if len(candidate) <= 64:
        return candidate
    prefix = source_id[:47].rstrip("-_")
    return f"{prefix}-{digest([source_id, creative_role])[:12]}"


def _content_constraints(intent):
    content = intent["content"]
    rows = [
        {
            "id": "adult-status",
            "text": "All represented subjects are reviewed adults from owner or canon metadata.",
            "mechanism": "verify",
            "priority": "hard",
        },
        {
            "id": "content-envelope",
            "text": "Keep the result within the reviewed sensual non-explicit content envelope.",
            "mechanism": "verify",
            "priority": "hard",
        },
        {
            "id": "coverage",
            "text": "Preserve the reviewed non-explicit coverage declaration: "
            + content["coverage"].replace("_", " ")
            + ".",
            "mechanism": "verify",
            "priority": "hard",
        },
    ]
    if len(intent["subjects"]) > 1:
        rows.append(
            {
                "id": "consent-context",
                "text": "Keep the reviewed consensual multi-adult context.",
                "mechanism": "verify",
                "priority": "hard",
            }
        )
    return rows


def _project_facets(intent):
    source = intent["facets"]
    subject_parts = [
        f"{item['id']}: {item['description']}" for item in intent["subjects"]
    ]
    for key, label in (
        ("body", "Body"),
        ("wardrobe", "Wardrobe"),
        ("expression", "Expression"),
    ):
        if key in source:
            subject_parts.append(f"{label}: {source[key]}")
    result = {"subject": "; ".join(subject_parts)}
    mapping = {
        "pose": "action",
        "setting": "setting",
        "composition": "composition",
        "camera": "camera",
        "lighting": "lighting",
        "palette": "palette",
        "mood": "mood",
    }
    for source_key, target_key in mapping.items():
        if source_key in source:
            result[target_key] = source[source_key]
    style = []
    if "style" in source:
        style.append(source["style"])
    if "material" in source:
        style.append("Material: " + source["material"])
    if style:
        result["style"] = "; ".join(style)
    return result


def _creative_representation_blocked(facets, candidate, diagnostics):
    blocked = False
    for facet, value in sorted(facets.items()):
        actual = len(value)
        if actual <= CREATIVE_FACET_MAX_CHARS:
            continue
        blocked = True
        diagnostics.append(
            {
                "code": "CREATIVE_FACET_LIMIT",
                "severity": "error",
                "message": (
                    f"Projected CreativeIntent facet {facet} has {actual} characters; "
                    f"the existing contract allows {CREATIVE_FACET_MAX_CHARS}. "
                    "The source intent is retained and nothing is truncated."
                ),
                "facet": facet,
                "actual_length": actual,
                "maximum_length": CREATIVE_FACET_MAX_CHARS,
            }
        )
    if blocked:
        return True

    actual_bytes = len(canonical(candidate))
    if actual_bytes <= CREATIVE_INTENT_MAX_BYTES:
        return False
    diagnostics.append(
        {
            "code": "CREATIVE_INTENT_LIMIT",
            "severity": "error",
            "message": (
                f"Projected CreativeIntent requires {actual_bytes} bytes; the existing "
                f"contract allows {CREATIVE_INTENT_MAX_BYTES}. The source intent is "
                "retained and expanded records are not truncated."
            ),
            "actual_bytes": actual_bytes,
            "maximum_bytes": CREATIVE_INTENT_MAX_BYTES,
        }
    )
    return True


def _project_locks(locks):
    mapping = {
        "brief": "brief",
        "subjects": "facets",
        "facets": "facets",
        "tags": "tags",
        "avoid": "avoid",
        "controls": "constraints",
        "references": "references",
        "constraints": "constraints",
        "content": "constraints",
    }
    return sorted({"verbatim", *(mapping[item] for item in locks)})


def _project_controls(intent, diagnostics):
    result = []
    requires_binding = False
    for control in intent["controls"]:
        if control["mechanism"] in ("semantic_text", "review_decision"):
            status = "represented_in_reviewed_intent"
        else:
            status = "requires_route_binding"
            requires_binding = True
            diagnostics.append(
                {
                    "code": "CONTROL_REQUIRES_BINDING",
                    "severity": "requirement",
                    "message": (
                        f"Control {control['id']} requires an exact compatible route binding; "
                        "it was not converted to prompt prose."
                    ),
                    "control_id": control["id"],
                }
            )
        result.append({**copy.deepcopy(control), "status": status})
    return result, requires_binding


def _project_references(intent, diagnostics):
    creative = []
    mapping = []
    requires_binding = False
    blocking = False
    for source in intent["references"]:
        groups = OrderedDict()
        unsupported = []
        for source_role in source["roles"]:
            creative_role = ROLE_MAP[source_role]
            if creative_role is None:
                unsupported.append(source_role)
                continue
            groups.setdefault(creative_role, []).append(source_role)
        if unsupported:
            blocking = True
            diagnostics.append(
                {
                    "code": "UNSUPPORTED_REFERENCE_ROLE",
                    "severity": "error",
                    "message": (
                        f"Reference {source['id']} has roles {unsupported} that the current "
                        "CreativeIntent cannot represent without a route-specific edit binding."
                    ),
                    "reference_id": source["id"],
                }
            )
            continue
        group_count = len(groups)
        for creative_role, source_roles in groups.items():
            creative_id = _creative_reference_id(source["id"], creative_role, group_count)
            creative.append(
                {
                    "id": creative_id,
                    "role": creative_role,
                    "kind": source["kind"],
                    "path": source["path"],
                    "sha256": source["sha256"],
                    "take": copy.deepcopy(source["take"]),
                    "ignore": copy.deepcopy(source["ignore"]),
                }
            )
            mapping.append(
                {
                    "source_id": source["id"],
                    "source_roles": list(source_roles),
                    "creative_reference_id": creative_id,
                    "creative_role": creative_role,
                    "subject_id": source["subject_id"],
                    "region_id": source["region_id"],
                    "sha256": source["sha256"],
                }
            )
        if source["subject_id"] is not None or source["region_id"] is not None:
            requires_binding = True
            diagnostics.append(
                {
                    "code": "REFERENCE_SCOPE_REQUIRES_BINDING",
                    "severity": "requirement",
                    "message": (
                        f"Reference {source['id']} subject/region ownership remains in the "
                        "reference map and needs a compatible route binding."
                    ),
                    "reference_id": source["id"],
                }
            )
    if len(creative) > 12:
        blocking = True
        diagnostics.append(
            {
                "code": "REFERENCE_LIMIT",
                "severity": "error",
                "message": (
                    f"Role expansion creates {len(creative)} CreativeIntent references; "
                    "the existing contract allows at most twelve. Never truncate."
                ),
            }
        )
    creative_ids = [item["id"] for item in creative]
    if len(set(creative_ids)) != len(creative_ids):
        blocking = True
        diagnostics.append(
            {
                "code": "REFERENCE_ID_COLLISION",
                "severity": "error",
                "message": "Role expansion produced duplicate CreativeIntent reference IDs.",
            }
        )
    return creative, mapping, requires_binding, blocking


def project(value):
    """Project reviewed semantics while retaining unresolved route controls."""
    intent = validate_intent(value)
    diagnostics = []
    control_plan, control_binding = _project_controls(intent, diagnostics)
    creative_references, reference_map, reference_binding, blocking = _project_references(
        intent, diagnostics
    )
    creative_intent = None
    if not blocking:
        projected_facets = _project_facets(intent)
        candidate = {
            "schema_version": 1,
            "id": intent["id"],
            "task": intent["task"],
            "brief": intent["brief"],
            "facets": projected_facets,
            "tags": copy.deepcopy(intent["tags"]),
            "avoid": copy.deepcopy(intent["avoid"]),
            "constraints": _content_constraints(intent) + copy.deepcopy(intent["constraints"]),
            "references": creative_references,
            "verbatim": {},
            "parameters": {},
            "locked": _project_locks(intent["locked"]),
        }
        if _creative_representation_blocked(projected_facets, candidate, diagnostics):
            blocking = True
        else:
            validate(candidate)
            creative_intent = candidate

    state = (
        "blocked"
        if blocking
        else "requires_binding"
        if control_binding or reference_binding
        else "review_required"
    )
    result = {
        "format": PROJECTION_FORMAT,
        "intent": intent,
        "source_sha256": digest(intent),
        "state": state,
        "creative_intent": creative_intent,
        "control_plan": control_plan,
        "reference_map": reference_map,
        "diagnostics": diagnostics,
        "execution_authorized": False,
        "generation_submitted": False,
        "limits": [
            "This projection is not a workflow, model selection, resource reservation or generation approval.",
            "Route-specific controls remain unresolved until exact installed capabilities are bound.",
            "Adult status, consent, artistic acceptance and rights remain reviewed external facts.",
        ],
    }
    result = copy.deepcopy(result)
    result["projection_sha256"] = digest(result)
    need(
        len(canonical(result)) <= PROJECTION_MAX_BYTES,
        f"Adult illustration projection exceeds {PROJECTION_MAX_BYTES} bytes",
    )
    return result


def validate_projection(value):
    """Recompute a projection so changed derived records fail closed."""
    fields(
        value,
        (
            "format",
            "intent",
            "source_sha256",
            "state",
            "creative_intent",
            "control_plan",
            "reference_map",
            "diagnostics",
            "execution_authorized",
            "generation_submitted",
            "limits",
            "projection_sha256",
        ),
    )
    expected = project(value["intent"])
    need(
        canonical(value) == canonical(expected),
        "Changed or invalid adult illustration projection",
    )
    return expected
