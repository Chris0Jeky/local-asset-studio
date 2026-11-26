"""A semantic veto layered on the pinned P36 feature scorer.

This module compares supplied descriptors; it does not inspect images or infer
identity. The existing ``consistency.score_sheet`` still owns pixel/ratio/trait
agreement. A passing semantic report cannot turn its failure into a pass.

The caller must load ``semantic_policy`` and ``concept`` from its trusted current
family state, independently verify that concept's current owner acceptance, and
retain these exact input/report digests. Matching caller-supplied declarations is
not authentication. No function here creates an acceptance or reads media.

Rubric: name sides anatomically from the subject's perspective; annotate only
the required visible marks with the frozen vocabulary. Unknown/occluded marks
use ``uncertain``/``not_visible`` and block. A hidden far eye is omitted only by
the frozen view policy, never by a candidate. Costume contexts may replace only
costume anchors. Neither context nor a new expression can replace identity.

Thresholds and RGB measurements remain in the prior scorer. Semantic comparison
is exact token equality, not fuzzy language similarity. Review the corresponding
images before using a descriptor: a fabricated but matching annotation will pass
this consistency check. The report explicitly retains that limitation.
"""
from __future__ import annotations

import hashlib
import json
import math
import re

from consistency import policy_digest as proxy_policy_digest, score_sheet

NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
CONCEPT_KEYS = {"asset_id", "media_sha256", "receipt_digest"}
MAX_JSON_BYTES = 4 * 1024 * 1024


class IdentityError(ValueError):
    """A stable fail-closed semantic contract error."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise IdentityError(code)


def _shape(value, fields, code):
    _require(type(value) is dict and set(value) == fields, code)


def _name(value):
    return type(value) is str and NAME.fullmatch(value) is not None


def _sha(value):
    return type(value) is str and SHA256.fullmatch(value) is not None


def _token(value):
    return (type(value) is str and 1 <= len(value) <= 128 and value.isprintable()
            and value.strip() == value)


def _json_value(value, depth=0):
    """Reject non-JSON objects, mixed key types, cycles and non-finite numbers."""
    _require(depth <= 32, "input_depth_exceeded")
    kind = type(value)
    if value is None or kind in (str, bool):
        return
    if kind in (int, float):
        try:
            valid = math.isfinite(value)
        except OverflowError:
            valid = False
        _require(valid, "input_number_invalid")
        return
    if kind is dict:
        _require(len(value) <= 1024 and all(type(k) is str for k in value), "input_object_invalid")
        for item in value.values():
            _json_value(item, depth + 1)
        return
    if kind is list:
        _require(len(value) <= 4096, "input_list_exceeded")
        for item in value:
            _json_value(item, depth + 1)
        return
    raise IdentityError("input_type_invalid")


def _digest(value):
    _json_value(value)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    _require(len(raw) <= MAX_JSON_BYTES, "input_size_exceeded")
    return hashlib.sha256(raw).hexdigest()


def _concept(value):
    _shape(value, CONCEPT_KEYS, "concept_shape_invalid")
    _require(_name(value["asset_id"]) and _sha(value["media_sha256"])
             and _sha(value["receipt_digest"]), "concept_binding_invalid")


def semantic_policy_digest(policy):
    """Validate the complete semantic policy, including unused contexts/stages.

    ``proxy_policy_digest`` binds the existing numeric policy. The scoring call
    additionally verifies that the two policies require exactly the same views.
    A digest is an integrity identifier; the caller owns policy authority.
    """
    _shape(policy, {"version", "side_basis", "concept", "proxy_policy_digest", "anchors", "contexts", "required"},
           "semantic_policy_shape_invalid")
    _require(type(policy["version"]) is int and policy["version"] == 1, "semantic_policy_version_invalid")
    _require(policy["side_basis"] == "subject_anatomical", "side_basis_invalid")
    _concept(policy["concept"])
    _require(_sha(policy["proxy_policy_digest"]), "proxy_policy_digest_invalid")
    anchors, contexts, required = policy["anchors"], policy["contexts"], policy["required"]
    _require(type(anchors) is dict and 1 <= len(anchors) <= 64, "policy_anchors_invalid")
    for name, spec in anchors.items():
        _require(_name(name), "policy_anchor_name_invalid")
        _shape(spec, {"kind", "value", "vocabulary"}, "policy_anchor_shape_invalid")
        _require(type(spec["kind"]) is str and spec["kind"] in {"identity", "costume"}, "policy_anchor_kind_invalid")
        vocabulary = spec["vocabulary"]
        _require(type(vocabulary) is list and 1 <= len(vocabulary) <= 64
                 and all(_token(v) for v in vocabulary), "policy_vocabulary_invalid")
        _require(len(set(vocabulary)) == len(vocabulary), "policy_vocabulary_duplicate")
        _require(_token(spec["value"]) and spec["value"] in vocabulary, "policy_anchor_value_invalid")
    _require(type(contexts) is dict and 1 <= len(contexts) <= 32, "policy_contexts_invalid")
    for name, overrides in contexts.items():
        _require(_name(name) and type(overrides) is dict and len(overrides) <= 64, "policy_context_invalid")
        for anchor, value in overrides.items():
            _require(_name(anchor) and anchor in anchors, "policy_override_unknown")
            _require(anchors[anchor]["kind"] == "costume", "policy_identity_override")
            _require(_token(value) and value in anchors[anchor]["vocabulary"], "policy_override_value_invalid")
    _require(type(required) is dict and 1 <= len(required) <= 16, "policy_requirements_invalid")
    for stage, views in required.items():
        _require(_name(stage) and type(views) is dict and 1 <= len(views) <= 32, "policy_stage_invalid")
        for view, spec in views.items():
            _require(_name(view), "policy_view_name_invalid")
            _shape(spec, {"context", "anchors"}, "policy_view_shape_invalid")
            names = spec["anchors"]
            _require(_name(spec["context"]) and spec["context"] in contexts, "policy_context_unknown")
            _require(type(names) is list and 1 <= len(names) <= 64
                     and all(_name(n) and n in anchors for n in names), "policy_required_anchors_invalid")
            _require(len(set(names)) == len(names), "policy_required_anchor_duplicate")
            _require(any(anchors[n]["kind"] == "identity" for n in names), "policy_identity_coverage_missing")
    return _digest(policy)


def _result():
    return {
        "version": 1, "evidence_state": "implemented", "passed": False, "blockers": [],
        "score": 0.0, "mean_score": 0.0, "worst_view_score": 0.0, "minimum_feature_score": 0.0,
        "score_kind": "diagnostic_mean_of_per_view_minimum_agreement", "per_view": [],
        "input_digest": None, "policy_digest": None, "proxy_report": None,
        "metric_kind": "manual_semantic_veto_plus_existing_proxy", "coverage_complete": False,
        "perceptual_identity_verified": False, "art_acceptance_implied": False,
        "generation_implied": False, "licence_clearance_implied": False,
        "provenance_verified": False, "review_required": True,
        "limitations": [
            "This checks supplied descriptors and the existing proxy metrics; it does not recognize images.",
            "Matching fabricated annotations can pass. Human/fixture labels are declarations, not authentication.",
            "The caller must verify live root acceptance and pin both policies independently of candidate inputs.",
            "Thresholds and vocabularies are unqualified prototype policy, not measured perceptual accuracy.",
            "No generation, art review, owner acceptance, native import or licence clearance is implied.",
        ],
    }


def _finish(result):
    result["blockers"] = sorted(set(result["blockers"]))
    result["report_digest"] = _digest(result)
    return result


def _view_index(views, prefix, blockers):
    _require(type(views) is list and len(views) <= 32, prefix + "_views_invalid")
    indexed = {}
    for view in views:
        if type(view) is not dict or not _name(view.get("id")):
            blockers.append(prefix + "_view_invalid")
            continue
        name = view["id"]
        if name in indexed:
            blockers.append(prefix + "_view_duplicate:" + name)
            continue
        indexed[name] = view
    return indexed


def _annotation_view(view, candidate, requirement, concept):
    _require(view is not None, "annotation_view_missing")
    _shape(view, {"id", "media_sha256", "compared_to", "context", "anchors"}, "annotation_view_shape_invalid")
    _require(candidate is not None and _sha(view["media_sha256"])
             and view["media_sha256"] == candidate.get("media_sha256"), "annotation_media_mismatch")
    _concept(view["compared_to"])
    _require(view["compared_to"] == concept, "annotation_compared_to_mismatch")
    _require(view["context"] == requirement["context"], "annotation_context_mismatch")
    _require(type(view["anchors"]) is dict and len(view["anchors"]) <= 64
             and all(_name(n) for n in view["anchors"]), "annotation_anchors_invalid")


def _observe(record, vocabulary):
    _require(record is not None, "semantic_anchor_missing")
    _shape(record, {"state", "value", "provenance"}, "semantic_observation_shape_invalid")
    _require(type(record["provenance"]) is str
             and record["provenance"] in {"human_annotated", "fixture_truth"}, "semantic_provenance_invalid")
    _require(type(record["state"]) is str
             and record["state"] in {"observed", "uncertain", "not_visible"}, "semantic_state_invalid")
    _require(record["state"] == "observed", "semantic_unavailable")
    _require(_token(record["value"]) and record["value"] in vocabulary, "semantic_value_unknown")
    return record["value"]


def score_sheet_identity(anchor_features, sheet, proxy_policy, stage, *, semantic_policy, annotations, concept):
    """Recompute the prior scorer and apply an additional semantic veto.

    ``concept`` is the current accepted root's asset, media and receipt identity,
    supplied by trusted family state, not obtained from this annotation document.
    Ordinary malformed inputs return a failed, hashed report with blocker codes.
    Neither the mean nor a perfect view can override any failed required anchor.
    """
    result = _result()
    inputs = {"anchor_features": anchor_features, "sheet": sheet, "proxy_policy": proxy_policy,
              "stage": stage, "semantic_policy": semantic_policy, "annotations": annotations, "concept": concept}
    try:
        result["input_digest"] = _digest(inputs)
        result["policy_digest"] = semantic_policy_digest(semantic_policy)
        _concept(concept)
        _require(concept == semantic_policy["concept"], "semantic_root_mismatch")
        _require(proxy_policy_digest(proxy_policy) == semantic_policy["proxy_policy_digest"], "proxy_policy_binding_mismatch")
        required = semantic_policy["required"]
        _require(set(required) == set(proxy_policy["required"])
                 and all(set(required[s]) == set(proxy_policy["required"][s]) for s in required),
                 "semantic_policy_coverage_mismatch")
        _require(_name(stage) and stage in required, "stage_unsupported")
        _shape(annotations, {"version", "method", "side_basis", "concept", "policy_digest", "views"},
               "annotations_shape_invalid")
        _require(type(annotations["version"]) is int and annotations["version"] == 1, "annotations_version_invalid")
        _require(annotations["method"] == "manual_descriptor_v1", "annotations_method_invalid")
        _require(annotations["side_basis"] == "subject_anatomical", "side_basis_invalid")
        _concept(annotations["concept"])
        _require(annotations["concept"] == concept, "annotation_concept_mismatch")
        _require(annotations["policy_digest"] == result["policy_digest"], "annotation_policy_mismatch")
        _require(type(anchor_features) is dict and len(anchor_features) <= 64, "proxy_anchors_invalid")
        for name, feature in anchor_features.items():
            _require(_name(name) and name in proxy_policy["features"], "proxy_anchor_unknown")
            _require(type(feature) is dict and feature.get("media_sha256") == concept["media_sha256"],
                     "proxy_anchor_root_mismatch:" + name)
        proxy = score_sheet(anchor_features, sheet, proxy_policy, stage)
        result["proxy_report"] = proxy
        result["blockers"].extend("proxy:" + code for code in proxy["blockers"])
        _require(type(sheet) is dict, "sheet_shape_invalid")
        candidates = _view_index(sheet.get("views"), "proxy", result["blockers"])
        observed = _view_index(annotations["views"], "annotation", result["blockers"])
        for prefix, indexed in (("proxy", candidates), ("annotation", observed)):
            result["blockers"].extend(prefix + "_view_unknown:" + v for v in sorted(set(indexed) - set(required[stage])))

        total_supported = total_required = 0
        for view_id, requirement in sorted(required[stage].items()):
            candidate, view = candidates.get(view_id), observed.get(view_id)
            errors = []
            try:
                _annotation_view(view, candidate, requirement, concept)
            except IdentityError as error:
                errors.append(error.code + ":" + view_id)
            values = view.get("anchors", {}) if view is not None and not errors else {}
            for name in sorted(set(values) - set(requirement["anchors"])):
                errors.append("semantic_anchor_unknown:" + view_id + ":" + name)
            checks = []
            supported = 0
            overrides = semantic_policy["contexts"][requirement["context"]]
            for name in sorted(requirement["anchors"]):
                spec = semantic_policy["anchors"][name]
                expected = overrides.get(name, spec["value"])
                check = {"anchor": name, "kind": spec["kind"], "expected": expected,
                         "value": None, "agreement": 0.0, "passed": False, "state": "unavailable"}
                try:
                    value = _observe(values.get(name), spec["vocabulary"])
                    supported += 1
                    matched = value == expected
                    check.update(value=value, agreement=1.0 if matched else 0.0, passed=matched,
                                 state="passed" if matched else "failed", provenance=values[name]["provenance"])
                    if not matched:
                        errors.append("semantic_mismatch:" + view_id + ":" + name)
                except IdentityError as error:
                    check["reason"] = error.code
                    errors.append(error.code + ":" + view_id + ":" + name)
                checks.append(check)
            numeric = [feature for feature in proxy["feature_results"] if feature["view"] == view_id]
            numeric_scores = [feature["agreement"] for feature in numeric]
            minimum = min(numeric_scores + [check["agreement"] for check in checks]) if numeric else 0.0
            per_view = {
                "view": view_id, "context": requirement["context"], "anchors": checks,
                "proxy_score": round(math.fsum(numeric_scores) / len(numeric_scores), 12) if numeric else 0.0,
                "semantic_score": min(check["agreement"] for check in checks), "score": minimum,
                "minimum_feature_score": minimum, "supported_annotations": supported,
                "required_annotations": len(checks),
                "passed": bool(numeric) and all(feature["passed"] for feature in numeric)
                          and not errors and all(check["passed"] for check in checks),
            }
            result["per_view"].append(per_view)
            result["blockers"].extend(errors)
            total_supported += supported
            total_required += len(checks)
        scores = [view["score"] for view in result["per_view"]]
        result["mean_score"] = result["score"] = round(math.fsum(scores) / len(scores), 12)
        result["worst_view_score"] = result["minimum_feature_score"] = min(scores)
        result["coverage_complete"] = proxy["coverage_complete"] and total_supported == total_required
        result["passed"] = proxy["passed"] and result["coverage_complete"] and not result["blockers"]
    except (ValueError, TypeError, OverflowError, RecursionError, KeyError) as error:
        result["blockers"].append(getattr(error, "code", "identity_input_invalid"))
    return _finish(result)
