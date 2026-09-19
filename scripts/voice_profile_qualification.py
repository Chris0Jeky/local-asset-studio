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
HEX_64_RE = re.compile(r'[0-9a-f]{64}\Z')
ID_RE = re.compile(r'[a-z][a-z0-9-]{0,63}\Z')
METRIC_FIELDS = (
    'load_seconds',
    'first_audio_seconds',
    'generation_seconds',
    'peak_host_bytes',
    'peak_vram_bytes',
    'generated_seconds',
    'accepted_seconds',
    'correction_seconds',
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


def _hash(value, label) -> str:
    if not isinstance(value, str) or not HEX_64_RE.fullmatch(value):
        raise QualificationError(f'{label} must be a lowercase SHA-256')
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
    if type(value.get('revision')) is not int or not 1 <= value['revision'] <= 1_000_000:
        raise QualificationError('Evaluation set revision must be a positive integer')
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


def _candidate_plan() -> list[dict]:
    return [
        {
            'id': 'qwen3-voice-design-v1',
            'name': 'Qwen3-TTS VoiceDesign exploration',
            'role': 'original-identity-exploration',
            'control': False,
            'required': True,
        },
        {
            'id': 'qwen3-reusable-reference-v1',
            'name': 'Qwen3-TTS reusable accepted-reference route',
            'role': 'reusable-identity-candidate',
            'control': False,
            'required': True,
        },
        {
            'id': 'indextts-2-5-expressive-v1',
            'name': 'IndexTTS 2.5 expressive comparison',
            'role': 'independent-expressive-candidate',
            'control': False,
            'required': False,
        },
        {
            'id': 'kokoro-af-heart-control-v1',
            'name': 'Kokoro af_heart CPU control',
            'role': 'cheap-built-in-control',
            'control': True,
            'required': True,
        },
    ]


def build_plan(profile_id: str, *, registry_path: Path | None = None) -> dict:
    try:
        profile = resolve_profile(
            profile_id,
            'calm-brief',
            registry_path=registry_path,
        )
    except VoiceProfileError as exc:
        raise QualificationError(str(exc)) from exc
    evaluation = _load_evaluation_set()
    plan = {
        'schema_version': 1,
        'kind': 'voice-profile-qualification',
        'profile': profile,
        'evaluation': {
            'id': evaluation['id'],
            'revision': evaluation['revision'],
            'sha256': canonical_digest(evaluation),
            'lines': copy.deepcopy(evaluation['lines']),
        },
        'candidates': _candidate_plan(),
        'measurement_fields': list(METRIC_FIELDS),
        'long_form': {
            'minimum_seconds': 300,
            'maximum_seconds': 600,
            'requires_owner_end_to_end_review': True,
            'requires_identity_consistency_review': True,
            'requires_pronunciation_review': True,
        },
        'generation_submitted': False,
    }
    plan['plan_sha256'] = canonical_digest(plan)
    return plan


def _validate_plan(plan: dict) -> dict:
    _fields(
        plan,
        (
            'schema_version',
            'kind',
            'profile',
            'evaluation',
            'candidates',
            'measurement_fields',
            'long_form',
            'generation_submitted',
            'plan_sha256',
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
    profile = plan.get('profile')
    if not isinstance(profile, dict) or not isinstance(profile.get('id'), str):
        raise QualificationError('Qualification plan profile binding is invalid')
    evaluation = plan.get('evaluation')
    _fields(evaluation, ('id', 'revision', 'sha256', 'lines'), 'qualification plan evaluation')
    _hash(evaluation.get('sha256'), 'qualification plan evaluation SHA-256')
    lines = evaluation.get('lines')
    if not isinstance(lines, list) or not lines:
        raise QualificationError('Qualification plan evaluation lines are invalid')
    line_ids = []
    for line in lines:
        if not isinstance(line, dict) or not isinstance(line.get('id'), str):
            raise QualificationError('Qualification plan evaluation line is invalid')
        line_ids.append(line['id'])
    if len(line_ids) != len(set(line_ids)):
        raise QualificationError('Qualification plan has duplicate evaluation line IDs')
    candidates = plan.get('candidates')
    if not isinstance(candidates, list) or not candidates:
        raise QualificationError('Qualification plan candidates are invalid')
    candidate_ids = []
    control_ids = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or not isinstance(candidate.get('id'), str):
            raise QualificationError('Qualification plan candidate is invalid')
        candidate_ids.append(candidate['id'])
        if candidate.get('control') is True:
            control_ids.append(candidate['id'])
    if len(candidate_ids) != len(set(candidate_ids)):
        raise QualificationError('Qualification plan has duplicate candidate IDs')
    if len(control_ids) != 1:
        raise QualificationError('Qualification plan must identify exactly one control')
    return {
        'profile_id': profile['id'],
        'evaluation_sha256': evaluation['sha256'],
        'line_ids': line_ids,
        'candidate_ids': candidate_ids,
        'control_id': control_ids[0],
        'minimum_seconds': plan['long_form'].get('minimum_seconds'),
        'maximum_seconds': plan['long_form'].get('maximum_seconds'),
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


def _validate_candidate(value, expected_line_ids, candidate_ids, index):
    label = f'qualification report candidate {index}'
    _fields(
        value,
        ('id', 'status', 'configuration_sha256', 'metrics', 'lines', 'notes'),
        label,
    )
    identifier = _stable_id(value.get('id'), f'{label}.id')
    if identifier not in candidate_ids:
        raise QualificationError(f'{label} is not declared by the qualification plan')
    if value.get('status') != 'measured':
        raise QualificationError(f'{label}.status must be measured for submitted candidate evidence')
    _hash(value.get('configuration_sha256'), f'{label}.configuration_sha256')
    metrics = value.get('metrics')
    _fields(metrics, METRIC_FIELDS, f'{label}.metrics')
    for field in METRIC_FIELDS:
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
    if actual_ids != expected_line_ids:
        raise QualificationError(f'{label} must cover the exact ordered evaluation lines')
    _text(value.get('notes'), f'{label}.notes', 4000)
    return identifier


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
            'listened_end_to_end',
            'identity_consistent',
            'pronunciation_reviewed',
            'accepted',
            'fatigue',
            'notes',
        ),
        'long_form.owner',
    )
    for field in (
        'listened_end_to_end',
        'identity_consistent',
        'pronunciation_reviewed',
        'accepted',
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
            'schema_version',
            'plan_sha256',
            'profile_id',
            'evaluation_set_sha256',
            'candidates',
            'long_form',
            'decision',
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
    measured = []
    seen = set()
    for index, candidate in enumerate(candidates):
        identifier = _validate_candidate(
            candidate,
            plan_info['line_ids'],
            set(plan_info['candidate_ids']),
            index,
        )
        if identifier in seen:
            raise QualificationError(f'Qualification report has duplicate candidate ID {identifier}')
        seen.add(identifier)
        measured.append(identifier)

    if plan_info['control_id'] not in measured:
        raise QualificationError('Qualification report must include the measured control')
    measured_non_control = {
        identifier for identifier in measured if identifier != plan_info['control_id']
    }
    if len(measured_non_control) < 2:
        raise QualificationError('Qualification report needs at least two measured non-control candidates')

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
    if decision['state'] == 'accepted':
        if selected not in measured:
            raise QualificationError('Accepted qualification decision must select a measured candidate')
        if selected == plan_info['control_id']:
            raise QualificationError('Accepted qualification decision must select a non-control candidate')
        if selected != long_form_candidate:
            raise QualificationError('Accepted candidate must match the long-form reviewed candidate')
        owner = report['long_form']['owner']
        if not owner['accepted'] or not owner['identity_consistent'] or not owner['pronunciation_reviewed']:
            raise QualificationError('Accepted profile needs positive long-form owner evidence')
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
