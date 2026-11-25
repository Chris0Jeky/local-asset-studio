"""Deterministic feature agreement for an offline character-sheet prototype.

This module does not recognize character identity. ``score_sheet`` compares
provided feature records; their provenance labels are assertions, not signatures.
Call ``measure_regions`` in trusted code to obtain actual pixel measurements and
bind the policy and measurements to immutable evidence in the caller's store.
Manually annotated ratios/traits remain annotations even when they agree.

The caller owns the trusted, pinned policy. Every required feature is a hard
gate. The mean score is diagnostic and never overrides a blocker, performs art
acceptance, establishes generation, or makes a licensing decision.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re

from PIL import Image, UnidentifiedImageError

MAX_FEATURES = 64
MAX_VIEWS = 32
MAX_STAGES = 16
MAX_MEDIA_BYTES = 64 * 1024 * 1024
MAX_DIMENSION = 4096
MAX_PIXELS = 16 * 1024 * 1024
MIN_ALPHA_COVERAGE = 0.95
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
PROVENANCE = frozenset(("pixel_measured", "human_annotated", "fixture_truth"))


class ConsistencyError(ValueError):
    """A stable machine-readable failure raised by the pixel extractor."""

    def __init__(self, code, message=None):
        self.code = code
        super().__init__(message or code)


def _number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _name(value):
    return type(value) is str and NAME.fullmatch(value) is not None


def _sha(value):
    return type(value) is str and SHA256.fullmatch(value) is not None


def _policy(policy):
    """Validate every policy branch, so unused malformed branches cannot hide."""
    if type(policy) is not dict or set(policy) != {"version", "features", "required"}:
        raise ConsistencyError("policy_shape_invalid")
    if type(policy["version"]) is not int or policy["version"] != 1:
        raise ConsistencyError("policy_version_invalid")
    features, required = policy["features"], policy["required"]
    if type(features) is not dict or not 1 <= len(features) <= MAX_FEATURES:
        raise ConsistencyError("policy_features_invalid")
    for name, spec in features.items():
        if not _name(name) or type(spec) is not dict:
            raise ConsistencyError("policy_feature_invalid")
        kind = spec.get("kind")
        if kind not in ("rgb", "ratio", "trait"):
            raise ConsistencyError("policy_feature_kind_invalid")
        expected_keys = {"kind"} if kind == "trait" else {"kind", "tolerance"}
        if set(spec) != expected_keys:
            raise ConsistencyError("policy_feature_shape_invalid")
        if kind != "trait":
            tolerance = spec["tolerance"]
            if not _number(tolerance) or tolerance < 0 or (kind == "rgb" and tolerance > 1):
                raise ConsistencyError("policy_tolerance_invalid")
    if type(required) is not dict or not 1 <= len(required) <= MAX_STAGES:
        raise ConsistencyError("policy_requirements_invalid")
    for stage, views in required.items():
        if not _name(stage) or type(views) is not dict or not 1 <= len(views) <= MAX_VIEWS:
            raise ConsistencyError("policy_stage_invalid")
        for view, names in views.items():
            if not _name(view) or type(names) is not list or not 1 <= len(names) <= MAX_FEATURES:
                raise ConsistencyError("policy_view_invalid")
            if any(not _name(name) or name not in features for name in names):
                raise ConsistencyError("policy_requirement_unknown")
            if len(set(names)) != len(names):
                raise ConsistencyError("policy_requirement_duplicate")
    raw = json.dumps(policy, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


def policy_digest(policy):
    """Return a canonical digest after validating the complete policy."""
    return _policy(policy)


def _value(value, kind):
    if kind == "rgb":
        return type(value) is list and len(value) == 3 and all(
            _number(channel) and 0 <= channel <= 255 for channel in value)
    if kind == "ratio":
        return _number(value) and value >= 0
    return type(value) is str and 1 <= len(value) <= 128 and value.isprintable()


def _observation(record, kind, expected_media=None):
    if type(record) is not dict:
        return "observation_shape_invalid"
    provenance = record.get("provenance")
    if type(provenance) is not str or provenance not in PROVENANCE:
        return "provenance_invalid"
    if record.get("state", "observed") != "observed":
        return "observation_unavailable"
    if not _sha(record.get("media_sha256")):
        return "observation_hash_invalid"
    if expected_media is not None and record["media_sha256"] != expected_media:
        return "observation_hash_mismatch"
    if not _value(record.get("value"), kind):
        return "feature_value_invalid"
    return None


def _distance(expected, observed, kind):
    if kind == "rgb":
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(expected, observed)) / (3 * 255 ** 2))
    if kind == "ratio":
        return abs(expected - observed)
    return 0.0 if expected == observed else 1.0


def _result():
    return {
        "version": 1,
        "passed": False,
        "blockers": [],
        "score": 0.0,
        "score_kind": "diagnostic_required_feature_agreement",
        "feature_results": [],
        "policy_digest": None,
        "required_observations": 0,
        "supported_observations": 0,
        "coverage_complete": False,
        "provenance_counts": {name: 0 for name in sorted(PROVENANCE)},
        "annotation_checks": 0,
        "ignored_features": [],
        "ignored_views": [],
        "metric_kind": "proxy_and_annotations",
        "perceptual_identity_verified": False,
        "art_acceptance_implied": False,
        "generation_implied": False,
        "licence_clearance_implied": False,
        "review_required": True,
        "provenance_verified": False,
        "measurements_recomputed": False,
        "limitations": [
            "Agreement is limited to the required supplied feature records.",
            "Provenance labels and manual annotations are not authenticated or independently verified here.",
            "Pixel ROI agreement does not establish facial identity, view pose, art quality, or owner acceptance.",
        ],
    }


def score_sheet(anchor_features: dict, sheet: dict, policy: dict, stage: str) -> dict:
    """Compare required observations against an accepted concept's fixed values.

    All ordinary invalid inputs produce a failed result with stable blocker codes.
    Extra observations/views are disclosed and ignored; they cannot increase the
    required-observation mean or waive a hard gate. Each required view represents
    a separate media artifact; an atlas must be extracted before calling this API.
    """
    result = _result()
    try:
        result["policy_digest"] = _policy(policy)
    except (ConsistencyError, TypeError, ValueError, OverflowError) as exc:
        result["blockers"].append(getattr(exc, "code", "policy_invalid"))
        return result
    if not _name(stage) or stage not in policy["required"]:
        result["blockers"].append("stage_unsupported")
        return result
    required = policy["required"][stage]
    result["required_observations"] = sum(len(names) for names in required.values())
    if type(anchor_features) is not dict or len(anchor_features) > MAX_FEATURES:
        result["blockers"].append("anchor_features_invalid")
        return result
    if type(sheet) is not dict or type(sheet.get("views")) is not list or len(sheet["views"]) > MAX_VIEWS:
        result["blockers"].append("sheet_shape_invalid")
        return result

    views = {}
    for item in sheet["views"]:
        if type(item) is not dict or not _name(item.get("id")):
            result["blockers"].append("view_shape_invalid")
            continue
        view_id = item["id"]
        if view_id in views:
            result["blockers"].append("view_duplicate:" + view_id)
            continue
        views[view_id] = item
    result["ignored_views"] = sorted(set(views) - set(required))
    used_media = {}
    agreements = []
    for view_id in sorted(required):
        item = views.get(view_id)
        features = item.get("features") if item else None
        media_sha = item.get("media_sha256") if item else None
        view_error = None
        if item is None:
            view_error = "view_missing"
        elif not _sha(media_sha):
            view_error = "view_hash_invalid"
        elif type(features) is not dict or len(features) > MAX_FEATURES:
            view_error = "view_features_invalid"
        elif any(not _name(name) for name in features):
            view_error = "view_feature_name_invalid"
        elif media_sha in used_media:
            view_error = "duplicate_required_media"
        else:
            used_media[media_sha] = view_id
        if view_error:
            result["blockers"].append(view_error + ":" + view_id)
        if type(features) is dict:
            result["ignored_features"].extend(
                view_id + ":" + name for name in sorted(name for name in features if _name(name))
                if name not in required[view_id])

        for name in sorted(required[view_id]):
            spec = policy["features"][name]
            kind = spec["kind"]
            feature = {"view": view_id, "feature": name, "kind": kind, "critical": True,
                       "passed": False, "state": "invalid", "distance": None,
                       "tolerance": spec.get("tolerance", 0), "agreement": 0.0}
            result["feature_results"].append(feature)
            agreements.append(0.0)
            anchor = anchor_features.get(name)
            anchor_error = _observation(anchor, kind)
            if anchor_error:
                feature["reason"] = "anchor_" + anchor_error
                result["blockers"].append(feature["reason"] + ":" + name)
                continue
            feature["expected"] = anchor["value"]
            feature["anchor_provenance"] = anchor["provenance"]
            if view_error:
                feature["reason"] = view_error
                feature["state"] = "missing" if item is None else "invalid"
                continue
            if name not in features:
                feature["state"] = "missing"
                feature["reason"] = "feature_missing"
                result["blockers"].append("feature_missing:" + view_id + ":" + name)
                continue
            observation = features[name]
            error = _observation(observation, kind, media_sha)
            if error:
                feature["reason"] = error
                result["blockers"].append(error + ":" + view_id + ":" + name)
                continue
            observed = observation["value"]
            distance = _distance(anchor["value"], observed, kind)
            passed = distance <= spec.get("tolerance", 0)
            agreement = max(0.0, 1.0 - min(distance, 1.0))
            feature.update(value=observed, provenance=observation["provenance"],
                           distance=round(distance, 12), agreement=round(agreement, 12),
                           passed=passed, state="passed" if passed else "failed")
            agreements[-1] = agreement
            result["supported_observations"] += 1
            result["provenance_counts"][observation["provenance"]] += 1
            if "human_annotated" in (observation["provenance"], anchor["provenance"]):
                result["annotation_checks"] += 1
            if not passed:
                feature["reason"] = "critical_mismatch"
                result["blockers"].append("critical_mismatch:" + view_id + ":" + name)

    result["ignored_features"].sort()
    result["blockers"] = sorted(set(result["blockers"]))
    result["coverage_complete"] = result["supported_observations"] == result["required_observations"]
    result["score"] = round(math.fsum(agreements) / result["required_observations"], 12)
    result["passed"] = not result["blockers"] and result["coverage_complete"]
    return result


def measure_regions(path, expected_sha256: str, regions: dict, min_alpha=MIN_ALPHA_COVERAGE) -> dict:
    """Read one bounded, hash-pinned PNG and measure fixed normalized ROIs.

    Returns encoded RGB alpha-weighted means rounded to six decimals. This is
    not color management or perceptual color matching. Transparent pixels do not
    contribute RGB; mean alpha coverage must meet a non-waivable 0.95 floor.
    The caller must take ``regions`` from its trusted pinned policy, not media
    metadata or an untrusted candidate. No files are written and no network is
    accessed. The file is read once and both hashed and decoded from those bytes.
    """
    if not _sha(expected_sha256):
        raise ConsistencyError("expected_hash_invalid")
    if not _number(min_alpha) or not MIN_ALPHA_COVERAGE <= min_alpha <= 1:
        raise ConsistencyError("alpha_threshold_invalid")
    if type(regions) is not dict or not 1 <= len(regions) <= MAX_FEATURES:
        raise ConsistencyError("regions_invalid")
    normalized = {}
    for name, region in regions.items():
        if not _name(name) or type(region) not in (list, tuple) or len(region) != 4:
            raise ConsistencyError("region_invalid")
        if not all(_number(v) and 0 <= v <= 1 for v in region):
            raise ConsistencyError("region_bounds_invalid")
        x0, y0, x1, y1 = region
        if x0 >= x1 or y0 >= y1:
            raise ConsistencyError("region_empty")
        normalized[name] = tuple(region)
    try:
        with open(os.fspath(path), "rb") as handle:
            raw = handle.read(MAX_MEDIA_BYTES + 1)
    except (OSError, TypeError, ValueError) as exc:
        raise ConsistencyError("media_read_failed") from exc
    if len(raw) > MAX_MEDIA_BYTES:
        raise ConsistencyError("media_too_large")
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != expected_sha256:
        raise ConsistencyError("media_hash_mismatch")
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ConsistencyError("media_format_unsupported")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != "PNG":
                raise ConsistencyError("media_format_unsupported")
            if getattr(image, "is_animated", False) or getattr(image, "n_frames", 1) != 1:
                raise ConsistencyError("media_animated")
            width, height = image.size
            if not 1 <= width <= MAX_DIMENSION or not 1 <= height <= MAX_DIMENSION or width * height > MAX_PIXELS:
                raise ConsistencyError("media_dimensions_exceeded")
            if image.mode not in ("RGB", "RGBA", "L", "LA", "P"):
                raise ConsistencyError("media_mode_unsupported")
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            rgba = image.convert("RGBA")
    except ConsistencyError:
        raise
    except (OSError, ValueError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ConsistencyError("media_decode_failed") from exc
    pixels = rgba.load()
    measured = {}
    for name in sorted(normalized):
        x0, y0, x1, y1 = normalized[name]
        left, top = math.floor(x0 * width), math.floor(y0 * height)
        right, bottom = math.ceil(x1 * width), math.ceil(y1 * height)
        pixel_count = (right - left) * (bottom - top)
        if pixel_count <= 0:
            raise ConsistencyError("region_empty:" + name)
        red = green = blue = alpha_sum = 0
        for y in range(top, bottom):
            for x in range(left, right):
                r, g, b, a = pixels[x, y]
                red += r * a
                green += g * a
                blue += b * a
                alpha_sum += a
        alpha_coverage = alpha_sum / (255 * pixel_count)
        if alpha_coverage < min_alpha:
            raise ConsistencyError("region_alpha_insufficient:" + name)
        measured[name] = {
            "value": [round(total / alpha_sum, 6) for total in (red, green, blue)],
            "provenance": "pixel_measured",
            "media_sha256": actual_sha,
            "measurement_method": "encoded_rgba_mean_v1",
            "alpha_coverage": round(alpha_coverage, 8),
            "region": list(normalized[name]),
        }
    return measured
