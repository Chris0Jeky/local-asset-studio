#!/usr/bin/env python3
"""Create and validate deterministic narration-profile qualification evidence."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

from strict_json import StrictJsonError, load_bounded_json
from voice_profile import (
    MAX_PROFILE_JSON_BYTES,
    VoiceProfileError,
    canonical_digest,
    resolve_profile,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVALUATION_SET = ROOT / 'research' / 'voice-profiles' / 'evaluation-set.json'
DEFAULT_POLICY = ROOT / 'research' / 'voice-profiles' / 'qualification-policy.json'
HEX_64_RE = re.compile(r'[0-9a-f]{64}\Z')
MODEL_REVISION_RE = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})\Z')
ID_RE = re.compile(r'[a-z][a-z0-9-]{0,63}\Z')
FIELD_RE = re.compile(r'[a-z][a-z0-9_]{0,63}\Z')
SPEAKER_RE = re.compile(r'[a-z][a-z0-9_-]{0,63}\Z')
PERMISSION_RE = re.compile(r'[a-z][a-z0-9._-]{0,127}\Z')
REFERENCE_REQUIREMENTS = {'none', 'required'}
PROFILE_STATUSES = {'control', 'experimental', 'accepted', 'rejected'}
PROFILE_SOURCES = {'catalog', 'local-registry'}
PROFILE_BINDING_FIELDS = (
    'schema_version', 'id', 'revision', 'name', 'status', 'source',
    'profile_sha256', 'identity', 'adapter', 'runnable', 'speaker_id',
    'speaker_id_source', 'delivery', 'lexicon', 'mix', 'acceptance',
    'binding_sha256',
)


class QualificationError(ValueError):
    """Raised when a voice qualification plan or report is invalid."""


def _fields(value, required, label) -> None:
    if not isinstance(value, dict):
        raise QualificationError(f'{label} must be an object')
    actual = set(value)
    expected = set(required)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details = []
        if missing:
            details.append('missing ' + ', '.join(missing))
        if extra:
            details.append('unexpected ' + ', '.join(extra))
        raise QualificationError(f'{label} has invalid fields: ' + '; '.join(details))


def _text(value, label, maximum=4000, *, minimum=1) -> str:
    if not isinstance(value, str) or '\0' in value or not minimum <= len(value) <= maximum:
        raise QualificationError(f'{label} must be text from {minimum} to {maximum} characters')
    if value != value.strip():
        raise QualificationError(f'{label} must not contain surrounding whitespace')
    return value


def _stable_id(value, label) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise QualificationError(f'{label} must be a lowercase stable ID')
    return value


def _field_id(value, label) -> str:
    if not isinstance(value, str) or not FIELD_RE.fullmatch(value):
        raise QualificationError(f'{label} must be a lowercase field ID')
    return value


def _hash(value, label) -> str:
    if not isinstance(value, str) or not HEX_64_RE.fullmatch(value):
        raise QualificationError(f'{label} must be a lowercase SHA-256')
    return value


def _model_revision(value, label) -> str:
    if not isinstance(value, str) or not MODEL_REVISION_RE.fullmatch(value):
        raise QualificationError(f'{label} must be a full lowercase 40- or 64-character model_revision')
    return value


def _permission_scope(value, label) -> str:
    if not isinstance(value, str) or not PERMISSION_RE.fullmatch(value):
        raise QualificationError(f'{label} must be a stable non-path permission_scope')
    return value


def _timestamp(value, label) -> str:
    if not isinstance(value, str) or not value.endswith('Z'):
        raise QualificationError(f'{label} must be an RFC3339 UTC timestamp')
    try:
        parsed = datetime.fromisoformat(value[:-1] + '+00:00')
    except ValueError as exc:
        raise QualificationError(f'{label} must be an RFC3339 UTC timestamp') from exc
    if parsed.utcoffset() is None:
        raise QualificationError(f'{label} must include a timezone')
    return value


def _finite_nonnegative(value, label) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise QualificationError(f'{label} must be a finite non-negative number')
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise QualificationError(f'{label} must be a finite non-negative number')
    return result


def _rating(value, label) -> int:
    if type(value) is not int or not 1 <= value <= 5:
        raise QualificationError(f'{label} must be an integer rating from 1 to 5')
    return value


def _count(value, label) -> int:
    if type(value) is not int or not 0 <= value <= 1_000_000:
        raise QualificationError(f'{label} must be a non-negative integer')
    return value


def _positive_revision(value, label) -> int:
    if type(value) is not int or not 1 <= value <= 1_000_000:
        raise QualificationError(f'{label} must be a positive integer revision')
    return value


def _validate_profile_binding(value) -> dict:
    label = 'qualification plan profile binding'
    _fields(value, PROFILE_BINDING_FIELDS, label)
    claimed = _hash(value.get('binding_sha256'), f'{label} SHA-256')
    unsigned = {key: item for key, item in value.items() if key != 'binding_sha256'}
    try:
        actual = canonical_digest(unsigned)
    except VoiceProfileError as exc:
        raise QualificationError(str(exc)) from exc
    if actual != claimed:
        raise QualificationError('Qualification plan profile binding SHA-256 is invalid')
    if value.get('schema_version') != 1:
        raise QualificationError('Qualification plan profile binding has an unsupported schema version')
    _stable_id(value.get('id'), f'{label}.id')
    _positive_revision(value.get('revision'), f'{label}.revision')
    _text(value.get('name'), f'{label}.name', 160)
    if value.get('status') not in PROFILE_STATUSES:
        raise QualificationError(f'{label}.status is unsupported')
    if value.get('source') not in PROFILE_SOURCES:
        raise QualificationError(f'{label}.source is unsupported')
    _hash(value.get('profile_sha256'), f'{label}.profile_sha256')
    for field in ('identity', 'delivery', 'lexicon', 'mix', 'acceptance'):
        if not isinstance(value.get(field), dict):
            raise QualificationError(f'{label}.{field} must be an object')
    _stable_id(value.get('adapter'), f'{label}.adapter')
    if type(value.get('runnable')) is not bool:
        raise QualificationError(f'{label}.runnable must be a boolean')
    speaker_id = value.get('speaker_id')
    if not isinstance(speaker_id, str) or not SPEAKER_RE.fullmatch(speaker_id):
        raise QualificationError(f'{label}.speaker_id must be stable speaker metadata')
    _stable_id(value.get('speaker_id_source'), f'{label}.speaker_id_source')
    return copy.deepcopy(value)


def _read_json(path: Path, label: str):
    try:
        return load_bounded_json(
            Path(path),
            label=label,
            maximum_bytes=MAX_PROFILE_JSON_BYTES,
        )
    except StrictJsonError as exc:
        raise QualificationError(str(exc)) from exc


def _load_evaluation_set(path: Path | None = None) -> dict:
    source = DEFAULT_EVALUATION_SET if path is None else Path(path)
    value = _read_json(source, 'voice qualification evaluation set')
    _fields(value, ('schema_version', 'id', 'revision', 'name', 'lines'), 'evaluation set')
    if value.get('schema_version') != 1:
        raise QualificationError('Evaluation set has an unsupported schema version')
    _stable_id(value.get('id'), 'evaluation set id')
    _positive_revision(value.get('revision'), 'evaluation set revision')
    _text(value.get('name'), 'evaluation set name', 160)
    lines = value.get('lines')
    if not isinstance(lines, list) or not 8 <= len(lines) <= 64:
        raise QualificationError('Evaluation set must contain 8 to 64 lines')
    seen = set()
    validated_lines = []
    for index, line in enumerate(lines):
        label = f'evaluation set line {index}'
        _fields(line, ('id', 'category', 'delivery_id', 'text'), label)
        identifier = _stable_id(line.get('id'), f'{label} id')
        if identifier in seen:
            raise QualificationError(f'Evaluation set has duplicate line ID {identifier}')
        seen.add(identifier)
        _stable_id(line.get('category'), f'{label} category')
        _stable_id(line.get('delivery_id'), f'{label} delivery_id')
        _text(line.get('text'), f'{label} text', 1000)
        validated_lines.append(copy.deepcopy(line))
    return {
        'schema_version': 1,
        'id': value['id'],
        'revision': value['revision'],
        'name': value['name'],
        'lines': validated_lines,
    }


def _validate_policy_candidate(value, index):
    label = f'qualification policy candidate {index}'
    _fields(
        value,
        (
            'id', 'name', 'role', 'producer_family', 'adapter',
            'control', 'selectable', 'required', 'reference_requirement',
        ),
        label,
    )
    identifier = _stable_id(value.get('id'), f'{label}.id')
    _text(value.get('name'), f'{label}.name', 160)
    _stable_id(value.get('role'), f'{label}.role')
    _stable_id(value.get('producer_family'), f'{label}.producer_family')
    _stable_id(value.get('adapter'), f'{label}.adapter')
    for field in ('control', 'selectable', 'required'):
        if type(value.get(field)) is not bool:
            raise QualificationError(f'{label}.{field} must be a boolean')
    if value.get('reference_requirement') not in REFERENCE_REQUIREMENTS:
        raise QualificationError(f'{label}.reference_requirement is unsupported')
    if value['control'] and value['selectable']:
        raise QualificationError(f'{label} control cannot be selectable')
    return copy.deepcopy(value)


def load_policy(path: Path | None = None) -> dict:
    source = DEFAULT_POLICY if path is None else Path(path)
    value = _read_json(source, 'voice qualification policy')
    _fields(
        value,
        (
            'schema_version', 'id', 'revision', 'candidates',
            'measurement_fields', 'long_form', 'delivery_contrast',
        ),
        'qualification policy',
    )
    if value.get('schema_version') != 1:
        raise QualificationError('Qualification policy has an unsupported schema version')
    _stable_id(value.get('id'), 'qualification policy id')
    _positive_revision(value.get('revision'), 'qualification policy revision')

    candidates = value.get('candidates')
    if not isinstance(candidates, list) or not 3 <= len(candidates) <= 32:
        raise QualificationError('Qualification policy must contain 3 to 32 candidates')
    validated_candidates = []
    seen = set()
    controls = []
    selectable = []
    for index, candidate in enumerate(candidates):
        validated = _validate_policy_candidate(candidate, index)
        if validated['id'] in seen:
            raise QualificationError(
                f'Qualification policy has duplicate candidate ID {validated["id"]}'
            )
        seen.add(validated['id'])
        if validated['control']:
            controls.append(validated['id'])
        if validated['selectable'] and not validated['control']:
            selectable.append(validated['id'])
        validated_candidates.append(validated)
    if len(controls) != 1:
        raise QualificationError('Qualification policy must identify exactly one control')
    if not selectable:
        raise QualificationError('Qualification policy needs a selectable non-control candidate')

    measurements = value.get('measurement_fields')
    if not isinstance(measurements, list) or not measurements:
        raise QualificationError('Qualification policy measurement_fields must be non-empty')
    validated_measurements = []
    measurement_seen = set()
    for index, field in enumerate(measurements):
        field = _field_id(field, f'qualification policy measurement_fields[{index}]')
        if field in measurement_seen:
            raise QualificationError(f'Qualification policy has duplicate measurement field {field}')
        measurement_seen.add(field)
        validated_measurements.append(field)

    long_form = value.get('long_form')
    _fields(
        long_form,
        (
            'minimum_seconds', 'maximum_seconds',
            'requires_owner_end_to_end_review',
            'requires_identity_consistency_review',
            'requires_pronunciation_review',
        ),
        'qualification policy long_form',
    )
    minimum = _finite_nonnegative(long_form.get('minimum_seconds'), 'long_form.minimum_seconds')
    maximum = _finite_nonnegative(long_form.get('maximum_seconds'), 'long_form.maximum_seconds')
    if minimum <= 0 or maximum < minimum:
        raise QualificationError('Qualification policy long-form bounds are invalid')
    for field in (
        'requires_owner_end_to_end_review',
        'requires_identity_consistency_review',
        'requires_pronunciation_review',
    ):
        if type(long_form.get(field)) is not bool:
            raise QualificationError(f'qualification policy long_form.{field} must be a boolean')

    contrast = value.get('delivery_contrast')
    _fields(
        contrast,
        ('calm_line_id', 'spark_line_id', 'calm_delivery_id', 'spark_delivery_id'),
        'qualification policy delivery_contrast',
    )
    for field in contrast:
        _stable_id(contrast.get(field), f'qualification policy delivery_contrast.{field}')
    if contrast['calm_line_id'] == contrast['spark_line_id']:
        raise QualificationError('Qualification policy delivery contrast line IDs must differ')
    if contrast['calm_delivery_id'] == contrast['spark_delivery_id']:
        raise QualificationError('Qualification policy delivery contrast deliveries must differ')

    return {
        'schema_version': 1,
        'id': value['id'],
        'revision': value['revision'],
        'candidates': validated_candidates,
        'measurement_fields': validated_measurements,
        'long_form': copy.deepcopy(long_form),
        'delivery_contrast': copy.deepcopy(contrast),
    }


def policy_digest(policy: dict) -> str:
    try:
        return canonical_digest(policy)
    except VoiceProfileError as exc:
        raise QualificationError(str(exc)) from exc


def _validate_contrast_against_evaluation(policy: dict, evaluation: dict) -> None:
    contrast = policy['delivery_contrast']
    lines = {item['id']: item for item in evaluation['lines']}
    try:
        calm = lines[contrast['calm_line_id']]
        spark = lines[contrast['spark_line_id']]
    except KeyError as exc:
        raise QualificationError('Canonical evaluation is missing a delivery contrast line') from exc
    if calm['text'] != spark['text']:
        raise QualificationError('Canonical evaluation delivery contrast text must be identical')
    if calm['delivery_id'] != contrast['calm_delivery_id']:
        raise QualificationError('Canonical evaluation calm delivery contrast ID is invalid')
    if spark['delivery_id'] != contrast['spark_delivery_id']:
        raise QualificationError('Canonical evaluation spark delivery contrast ID is invalid')
    if calm['delivery_id'] == spark['delivery_id']:
        raise QualificationError('Canonical evaluation delivery contrast deliveries must differ')


def _canonical_plan_policy(policy: dict) -> dict:
    return {
        'id': policy['id'],
        'revision': policy['revision'],
        'sha256': policy_digest(policy),
    }


def _canonical_plan_evaluation(evaluation: dict) -> dict:
    return {
        'id': evaluation['id'],
        'revision': evaluation['revision'],
        'sha256': canonical_digest(evaluation),
        'lines': copy.deepcopy(evaluation['lines']),
    }


def build_plan(profile_id: str, *, registry_path: Path | None = None) -> dict:
    try:
        profile = resolve_profile(
            profile_id,
            'calm-brief',
            registry_path=registry_path,
        )
    except VoiceProfileError as exc:
        raise QualificationError(str(exc)) from exc
    policy = load_policy()
    evaluation = _load_evaluation_set()
    _validate_contrast_against_evaluation(policy, evaluation)
    plan = {
        'schema_version': 1,
        'kind': 'voice-profile-qualification',
        'profile': profile,
        'policy': _canonical_plan_policy(policy),
        'evaluation': _canonical_plan_evaluation(evaluation),
        'candidates': copy.deepcopy(policy['candidates']),
        'measurement_fields': copy.deepcopy(policy['measurement_fields']),
        'long_form': copy.deepcopy(policy['long_form']),
        'delivery_contrast': copy.deepcopy(policy['delivery_contrast']),
        'generation_submitted': False,
    }
    plan['plan_sha256'] = canonical_digest(plan)
    return plan


def _validate_plan(plan: dict) -> dict:
    _fields(
        plan,
        (
            'schema_version', 'kind', 'profile', 'policy', 'evaluation',
            'candidates', 'measurement_fields', 'long_form',
            'delivery_contrast', 'generation_submitted', 'plan_sha256',
        ),
        'qualification plan',
    )
    if plan.get('schema_version') != 1 or plan.get('kind') != 'voice-profile-qualification':
        raise QualificationError('Qualification plan has an unsupported schema or kind')
    claimed = _hash(plan.get('plan_sha256'), 'qualification plan SHA-256')
    unsigned = {key: value for key, value in plan.items() if key != 'plan_sha256'}
    if canonical_digest(unsigned) != claimed:
        raise QualificationError('Qualification plan SHA-256 is invalid')
    if plan.get('generation_submitted') is not False:
        raise QualificationError('Qualification planning must record zero submitted generation')
    profile = _validate_profile_binding(plan.get('profile'))

    policy = load_policy()
    evaluation = _load_evaluation_set()
    _validate_contrast_against_evaluation(policy, evaluation)
    if plan.get('policy') != _canonical_plan_policy(policy):
        raise QualificationError('Qualification plan does not match the canonical policy identity')
    for field in ('candidates', 'measurement_fields', 'long_form', 'delivery_contrast'):
        if plan.get(field) != policy[field]:
            raise QualificationError(
                f'Qualification plan {field} does not match the canonical policy'
            )
    canonical_evaluation = _canonical_plan_evaluation(evaluation)
    if plan.get('evaluation') != canonical_evaluation:
        raise QualificationError('Qualification plan does not match the canonical evaluation')

    candidate_map = {item['id']: item for item in policy['candidates']}
    control_id = next(item['id'] for item in policy['candidates'] if item['control'])
    return {
        'profile_id': profile['id'],
        'evaluation_sha256': canonical_evaluation['sha256'],
        'line_ids': [item['id'] for item in canonical_evaluation['lines']],
        'candidate_map': candidate_map,
        'candidate_ids': list(candidate_map),
        'control_id': control_id,
        'required_ids': {item['id'] for item in policy['candidates'] if item['required']},
        'measurement_fields': list(policy['measurement_fields']),
        'minimum_seconds': policy['long_form']['minimum_seconds'],
        'maximum_seconds': policy['long_form']['maximum_seconds'],
        'delivery_contrast': copy.deepcopy(policy['delivery_contrast']),
    }


def _validate_machine(value, label):
    _fields(
        value,
        ('status', 'transcript_sha256', 'substitutions', 'insertions', 'deletions', 'empty'),
        label,
    )
    if value.get('status') not in ('exact', 'differences', 'unavailable'):
        raise QualificationError(f'{label}.status is unsupported')
    _hash(value.get('transcript_sha256'), f'{label}.transcript_sha256')
    for field in ('substitutions', 'insertions', 'deletions'):
        _count(value.get(field), f'{label}.{field}')
    if type(value.get('empty')) is not bool:
        raise QualificationError(f'{label}.empty must be a boolean')


def _validate_line_owner(value, label):
    _fields(
        value,
        ('clarity', 'warmth', 'fatigue', 'identity', 'delivery', 'accepted', 'notes'),
        label,
    )
    for field in ('clarity', 'warmth', 'fatigue', 'identity', 'delivery'):
        _rating(value.get(field), f'{label}.{field}')
    if type(value.get('accepted')) is not bool:
        raise QualificationError(f'{label}.accepted must be a boolean')
    _text(value.get('notes'), f'{label}.notes', 4000)


def _validate_producer(value, policy, label):
    _fields(value, ('family', 'adapter', 'model_id', 'model_revision', 'runtime_sha256'), label)
    family = _stable_id(value.get('family'), f'{label}.family')
    if family != policy['producer_family']:
        raise QualificationError(f'{label} producer family does not match canonical policy')
    adapter = _stable_id(value.get('adapter'), f'{label}.adapter')
    if adapter != policy['adapter']:
        raise QualificationError(f'{label} adapter does not match canonical policy')
    _text(value.get('model_id'), f'{label}.model_id', 240)
    _model_revision(value.get('model_revision'), f'{label}.model_revision')
    _hash(value.get('runtime_sha256'), f'{label}.runtime_sha256')
    return copy.deepcopy(value)


def _validate_reference(value, policy, label):
    requirement = policy['reference_requirement']
    if requirement == 'none':
        if value is not None:
            raise QualificationError(f'{label} reference must be null for this candidate')
        return None
    if not isinstance(value, dict):
        raise QualificationError(f'{label} reference evidence is required')
    _fields(value, ('audio_sha256', 'transcript_sha256', 'permission_scope'), f'{label} reference')
    _hash(value.get('audio_sha256'), f'{label}.reference.audio_sha256')
    _hash(value.get('transcript_sha256'), f'{label}.reference.transcript_sha256')
    _permission_scope(value.get('permission_scope'), f'{label}.reference.permission_scope')
    return copy.deepcopy(value)


def _validate_delivery_contrast(value, contrast, label):
    _fields(
        value,
        (
            'calm_line_id', 'spark_line_id', 'identity_consistency',
            'delivery_control', 'accepted', 'notes',
        ),
        f'{label}.delivery_contrast',
    )
    if (
        value.get('calm_line_id') != contrast['calm_line_id']
        or value.get('spark_line_id') != contrast['spark_line_id']
    ):
        raise QualificationError(f'{label} delivery contrast does not use the canonical line pair')
    _rating(value.get('identity_consistency'), f'{label}.delivery_contrast.identity_consistency')
    _rating(value.get('delivery_control'), f'{label}.delivery_contrast.delivery_control')
    if type(value.get('accepted')) is not bool:
        raise QualificationError(f'{label}.delivery_contrast.accepted must be a boolean')
    _text(value.get('notes'), f'{label}.delivery_contrast.notes', 4000)
    return copy.deepcopy(value)


def _validate_candidate(value, plan_info, index):
    label = f'qualification report candidate {index}'
    _fields(
        value,
        (
            'id', 'status', 'producer', 'configuration_sha256', 'reference',
            'metrics', 'lines', 'delivery_contrast', 'notes',
        ),
        label,
    )
    identifier = _stable_id(value.get('id'), f'{label}.id')
    try:
        policy = plan_info['candidate_map'][identifier]
    except KeyError as exc:
        raise QualificationError(f'{label} is not declared by the qualification plan') from exc
    if value.get('status') != 'measured':
        raise QualificationError(f'{label}.status must be measured for submitted candidate evidence')
    producer = _validate_producer(value.get('producer'), policy, label)
    _hash(value.get('configuration_sha256'), f'{label}.configuration_sha256')
    reference = _validate_reference(value.get('reference'), policy, label)
    metrics = value.get('metrics')
    _fields(metrics, plan_info['measurement_fields'], f'{label}.metrics')
    for field in plan_info['measurement_fields']:
        _finite_nonnegative(metrics.get(field), field)
    lines = value.get('lines')
    if not isinstance(lines, list):
        raise QualificationError(f'{label}.lines must be a list')
    actual_ids = []
    for line_index, line in enumerate(lines):
        line_label = f'{label}.lines[{line_index}]'
        _fields(line, ('id', 'audio_sha256', 'machine', 'owner'), line_label)
        actual_ids.append(_stable_id(line.get('id'), f'{line_label}.id'))
        _hash(line.get('audio_sha256'), f'{line_label}.audio_sha256')
        _validate_machine(line.get('machine'), f'{line_label}.machine')
        _validate_line_owner(line.get('owner'), f'{line_label}.owner')
    if actual_ids != plan_info['line_ids']:
        raise QualificationError(f'{label} must cover the exact ordered evaluation lines')
    contrast = _validate_delivery_contrast(
        value.get('delivery_contrast'),
        plan_info['delivery_contrast'],
        label,
    )
    _text(value.get('notes'), f'{label}.notes', 4000)
    return {
        'id': identifier,
        'policy': policy,
        'producer': producer,
        'reference': reference,
        'contrast': contrast,
    }


def _validate_long_form(value, bounds, measured_non_control):
    _fields(value, ('candidate_id', 'manifest_sha256', 'audio_sha256', 'duration_seconds', 'owner'), 'long_form')
    candidate_id = _stable_id(value.get('candidate_id'), 'long_form.candidate_id')
    if candidate_id not in measured_non_control:
        raise QualificationError('Long-form evidence must use a measured non-control candidate')
    _hash(value.get('manifest_sha256'), 'long_form.manifest_sha256')
    _hash(value.get('audio_sha256'), 'long_form.audio_sha256')
    duration = _finite_nonnegative(value.get('duration_seconds'), 'long_form.duration_seconds')
    minimum, maximum = bounds
    if duration < minimum or duration > maximum:
        raise QualificationError(
            f'Long-form duration must be from {minimum} to {maximum} seconds'
        )
    owner = value.get('owner')
    _fields(
        owner,
        (
            'listened_end_to_end', 'identity_consistent', 'pronunciation_reviewed',
            'accepted', 'fatigue', 'notes',
        ),
        'long_form.owner',
    )
    for field in (
        'listened_end_to_end', 'identity_consistent',
        'pronunciation_reviewed', 'accepted',
    ):
        if type(owner.get(field)) is not bool:
            raise QualificationError(f'long_form.owner.{field} must be a boolean')
    if not owner['listened_end_to_end']:
        raise QualificationError('Long-form owner review must listen end to end')
    _rating(owner.get('fatigue'), 'long_form.owner.fatigue')
    _text(owner.get('notes'), 'long_form.owner.notes', 4000)
    return candidate_id


def validate_report(plan: dict, report: dict) -> dict:
    plan_info = _validate_plan(copy.deepcopy(plan))
    _fields(
        report,
        (
            'schema_version', 'plan_sha256', 'profile_id',
            'evaluation_set_sha256', 'candidates', 'long_form', 'decision',
        ),
        'qualification report',
    )
    if report.get('schema_version') != 1:
        raise QualificationError('Qualification report has an unsupported schema version')
    if report.get('plan_sha256') != plan.get('plan_sha256'):
        raise QualificationError('Qualification report belongs to another plan')
    if report.get('profile_id') != plan_info['profile_id']:
        raise QualificationError('Qualification report belongs to another profile')
    if report.get('evaluation_set_sha256') != plan_info['evaluation_sha256']:
        raise QualificationError('Qualification report uses another evaluation set')

    candidates = report.get('candidates')
    if not isinstance(candidates, list) or not candidates:
        raise QualificationError('Qualification report candidates must be a non-empty list')
    measured = {}
    for index, candidate in enumerate(candidates):
        validated = _validate_candidate(candidate, plan_info, index)
        identifier = validated['id']
        if identifier in measured:
            raise QualificationError(f'Qualification report has duplicate candidate ID {identifier}')
        measured[identifier] = validated

    if plan_info['control_id'] not in measured:
        raise QualificationError('Qualification report must include the measured control')
    measured_non_control = {
        identifier for identifier in measured if identifier != plan_info['control_id']
    }
    if len(measured_non_control) < 2:
        raise QualificationError('Qualification report needs at least two measured non-control candidates')
    missing_required = sorted(plan_info['required_ids'] - set(measured))
    if missing_required:
        raise QualificationError(
            'Qualification report is missing required candidate ' + ', '.join(missing_required)
        )

    long_form_candidate = _validate_long_form(
        report.get('long_form'),
        (plan_info['minimum_seconds'], plan_info['maximum_seconds']),
        measured_non_control,
    )
    decision = report.get('decision')
    _fields(
        decision,
        ('state', 'candidate_id', 'profile_id', 'rationale', 'owner_reviewed_at'),
        'qualification decision',
    )
    if decision.get('state') not in ('accepted', 'none-ready'):
        raise QualificationError('Qualification decision state must be accepted or none-ready')
    if decision.get('profile_id') != plan_info['profile_id']:
        raise QualificationError('Qualification decision belongs to another profile')
    _text(decision.get('rationale'), 'qualification decision rationale', 4000)
    _timestamp(decision.get('owner_reviewed_at'), 'qualification decision owner_reviewed_at')

    selected = decision.get('candidate_id')
    selected_record = None
    independent_families = []
    if decision['state'] == 'accepted':
        if selected not in measured:
            raise QualificationError('Accepted qualification decision must select a measured candidate')
        selected_record = measured[selected]
        policy = selected_record['policy']
        if policy['control']:
            raise QualificationError('Accepted qualification decision must select a non-control candidate')
        if not policy['selectable']:
            raise QualificationError('Accepted qualification decision must select a selectable candidate')
        if selected != long_form_candidate:
            raise QualificationError('Accepted candidate must match the long-form reviewed candidate')
        owner = report['long_form']['owner']
        if not owner['accepted'] or not owner['identity_consistent'] or not owner['pronunciation_reviewed']:
            raise QualificationError('Accepted profile needs positive long-form owner evidence')
        if not selected_record['contrast']['accepted']:
            raise QualificationError('Accepted candidate needs accepted delivery contrast evidence')
        selected_family = selected_record['producer']['family']
        independent_families = sorted({
            item['producer']['family']
            for identifier, item in measured.items()
            if identifier != selected
            and not item['policy']['control']
            and item['producer']['family'] != selected_family
        })
        if not independent_families:
            raise QualificationError(
                'Accepted qualification decision needs an independent producer family comparison'
            )
    elif selected is not None:
        raise QualificationError('A none-ready decision must not select a candidate')

    try:
        report_sha256 = canonical_digest(report)
    except VoiceProfileError as exc:
        raise QualificationError(str(exc)) from exc
    return {
        'schema_version': 1,
        'state': decision['state'],
        'profile_id': plan_info['profile_id'],
        'candidate_id': selected,
        'selected_producer_family': (
            selected_record['producer']['family'] if selected_record else None
        ),
        'independent_producer_families': independent_families,
        'reference': copy.deepcopy(selected_record['reference']) if selected_record else None,
        'qualification_report_sha256': report_sha256,
        'long_form_manifest_sha256': report['long_form']['manifest_sha256'],
        'long_form_audio_sha256': report['long_form']['audio_sha256'],
        'owner_reviewed_at': decision['owner_reviewed_at'],
    }


def _write_json(path: Path, value) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
    descriptor, temporary_name = tempfile.mkstemp(prefix=f'.{path.name}-', suffix='.tmp', dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description='Plan and validate offline narration-profile qualification evidence.'
    )
    commands = result.add_subparsers(dest='command', required=True)
    plan_command = commands.add_parser('plan', help='Build a deterministic zero-generation qualification plan.')
    plan_command.add_argument('profile_id')
    plan_command.add_argument('--profile-registry')
    plan_command.add_argument('--output')
    validate_command = commands.add_parser('validate', help='Validate a completed local qualification report.')
    validate_command.add_argument('plan')
    validate_command.add_argument('report')
    return result


def main(argv=None) -> int:
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == 'plan':
            value = build_plan(
                arguments.profile_id,
                registry_path=Path(arguments.profile_registry) if arguments.profile_registry else None,
            )
            if arguments.output:
                _write_json(Path(arguments.output), value)
        else:
            plan = _read_json(Path(arguments.plan), 'qualification plan')
            report = _read_json(Path(arguments.report), 'qualification report')
            value = validate_report(plan, report)
        print(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False))
        return 0
    except (QualificationError, VoiceProfileError, OSError) as exc:
        print('voice qualification: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
