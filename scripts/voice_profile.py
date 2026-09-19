#!/usr/bin/env python3
"""Validate and resolve durable narration-profile records for Spoken Briefs."""
from __future__ import annotations

import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

from strict_json import StrictJsonError, load_bounded_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / 'research' / 'voice-profiles' / 'catalog.json'
MAX_PROFILE_JSON_BYTES = 256 * 1024
MAX_PROFILES = 64
MAX_DELIVERIES = 16
MAX_LEXICON_ENTRIES = 256

ID_RE = re.compile(r'[a-z][a-z0-9-]{0,63}\Z')
SPEAKER_RE = re.compile(r'[a-z][a-z0-9_-]{0,63}\Z')
HEX_40_RE = re.compile(r'[0-9a-f]{40}\Z')
HEX_64_RE = re.compile(r'[0-9a-f]{64}\Z')
ASSET_ID_RE = re.compile(r'asset-[a-z0-9][a-z0-9._-]{0,127}\Z')
PERMISSION_RE = re.compile(r'[a-z][a-z0-9._-]{0,127}\Z')

PROFILE_STATUSES = {'control', 'experimental', 'accepted', 'rejected'}
DELIVERY_STATUSES = {'metadata-only', 'qualified', 'rejected'}
ACCEPTANCE_STATES = {'control', 'unreviewed', 'accepted', 'rejected'}
OWNER_REVIEWS = {'not-applicable', 'unreviewed', 'accepted', 'rejected'}


class VoiceProfileError(ValueError):
    """Raised when a narration profile or binding is invalid."""


def canonical_bytes(value) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=False,
            allow_nan=False,
        ).encode('utf-8')
    except (TypeError, ValueError, RecursionError) as exc:
        raise VoiceProfileError('Voice profile data is not canonical JSON') from exc


def canonical_digest(value) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def profile_digest(profile: dict) -> str:
    if not isinstance(profile, dict):
        raise VoiceProfileError('Voice profile must be an object')
    return canonical_digest(profile)


def _fields(value, required, label, optional=()) -> None:
    if not isinstance(value, dict):
        raise VoiceProfileError(f'{label} must be an object')
    actual = set(value)
    expected = set(required)
    allowed = expected | set(optional)
    if actual != expected and not (expected <= actual <= allowed):
        missing = sorted(expected - actual)
        extra = sorted(actual - allowed)
        detail = []
        if missing:
            detail.append('missing ' + ', '.join(missing))
        if extra:
            detail.append('unexpected ' + ', '.join(extra))
        raise VoiceProfileError(f'{label} has invalid fields: ' + '; '.join(detail))


def _text(value, label, maximum=1000, *, minimum=1) -> str:
    if not isinstance(value, str) or '\0' in value or not minimum <= len(value) <= maximum:
        raise VoiceProfileError(f'{label} must be text from {minimum} to {maximum} characters')
    if value != value.strip():
        raise VoiceProfileError(f'{label} must not contain surrounding whitespace')
    return value


def _stable_id(value, label) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise VoiceProfileError(f'{label} must be a lowercase stable ID')
    return value


def _positive_revision(value, label) -> int:
    if type(value) is not int or not 1 <= value <= 1_000_000:
        raise VoiceProfileError(f'{label} must be a positive integer revision')
    return value


def _optional_hash(value, label):
    if value is None:
        return None
    if not isinstance(value, str) or not HEX_64_RE.fullmatch(value):
        raise VoiceProfileError(f'{label} must be a lowercase SHA-256 or null')
    return value


def _required_hash(value, label) -> str:
    if not isinstance(value, str) or not HEX_64_RE.fullmatch(value):
        raise VoiceProfileError(f'{label} must be a lowercase SHA-256')
    return value


def _timestamp(value, label, *, required=False):
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.endswith('Z'):
        raise VoiceProfileError(f'{label} must be an RFC3339 UTC timestamp')
    try:
        parsed = datetime.fromisoformat(value[:-1] + '+00:00')
    except ValueError as exc:
        raise VoiceProfileError(f'{label} must be an RFC3339 UTC timestamp') from exc
    if parsed.utcoffset() is None:
        raise VoiceProfileError(f'{label} must include a timezone')
    return value


def _read_json(path: Path, label: str):
    try:
        return load_bounded_json(
            Path(path),
            label=label,
            maximum_bytes=MAX_PROFILE_JSON_BYTES,
        )
    except StrictJsonError as exc:
        raise VoiceProfileError(str(exc)) from exc


def _validate_reference(value, label):
    if value is None:
        return None
    _fields(
        value,
        ('asset_id', 'sha256', 'transcript_sha256', 'permission_scope'),
        label,
    )
    asset_id = value.get('asset_id')
    if not isinstance(asset_id, str) or not ASSET_ID_RE.fullmatch(asset_id):
        raise VoiceProfileError(f'{label} asset_id must be a local content-addressed asset ID, not a path')
    _required_hash(value.get('sha256'), f'{label}.sha256')
    _required_hash(value.get('transcript_sha256'), f'{label}.transcript_sha256')
    scope = value.get('permission_scope')
    if not isinstance(scope, str) or not PERMISSION_RE.fullmatch(scope):
        raise VoiceProfileError(f'{label}.permission_scope must be a stable recorded scope')
    return copy.deepcopy(value)


def _validate_identity(value, label):
    _fields(
        value,
        ('kind', 'model_id', 'model_revision', 'voice', 'language', 'original', 'reference'),
        label,
    )
    _stable_id(value.get('kind'), f'{label}.kind')
    _text(value.get('model_id'), f'{label}.model_id', 240)
    _text(value.get('model_revision'), f'{label}.model_revision', 160)
    _text(value.get('voice'), f'{label}.voice', 160)
    _text(value.get('language'), f'{label}.language', 32)
    if type(value.get('original')) is not bool:
        raise VoiceProfileError(f'{label}.original must be a boolean')
    _validate_reference(value.get('reference'), f'{label}.reference')
    return copy.deepcopy(value)


def _validate_producer(value, label):
    _fields(value, ('adapter', 'runnable', 'speaker_id'), label)
    _stable_id(value.get('adapter'), f'{label}.adapter')
    if type(value.get('runnable')) is not bool:
        raise VoiceProfileError(f'{label}.runnable must be a boolean')
    if not isinstance(value.get('speaker_id'), str) or not SPEAKER_RE.fullmatch(value['speaker_id']):
        raise VoiceProfileError(f'{label}.speaker_id must be stable speaker metadata')
    if value['runnable'] and value['adapter'] == 'unbound':
        raise VoiceProfileError(f'{label} cannot mark an unbound adapter runnable')
    return copy.deepcopy(value)


def _validate_deliveries(value, label):
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_DELIVERIES:
        raise VoiceProfileError(f'{label} must contain 1 to {MAX_DELIVERIES} delivery presets')
    result = []
    identifiers = set()
    for index, delivery in enumerate(value):
        item_label = f'{label}[{index}]'
        _fields(delivery, ('id', 'name', 'instruction', 'status'), item_label)
        identifier = _stable_id(delivery.get('id'), f'{item_label}.id')
        if identifier in identifiers:
            raise VoiceProfileError(f'{label} has a duplicate delivery ID: {identifier}')
        identifiers.add(identifier)
        _text(delivery.get('name'), f'{item_label}.name', 120)
        _text(delivery.get('instruction'), f'{item_label}.instruction', 2000)
        if delivery.get('status') not in DELIVERY_STATUSES:
            raise VoiceProfileError(f'{item_label}.status is unsupported')
        result.append(copy.deepcopy(delivery))
    return result


def _validate_lexicon(value, label):
    _fields(value, ('revision', 'entries'), label)
    _positive_revision(value.get('revision'), f'{label}.revision')
    entries = value.get('entries')
    if not isinstance(entries, list) or len(entries) > MAX_LEXICON_ENTRIES:
        raise VoiceProfileError(f'{label}.entries must contain at most {MAX_LEXICON_ENTRIES} items')
    seen = set()
    for index, entry in enumerate(entries):
        item_label = f'{label}.entries[{index}]'
        _fields(entry, ('written', 'spoken'), item_label)
        written = _text(entry.get('written'), f'{item_label}.written', 160)
        _text(entry.get('spoken'), f'{item_label}.spoken', 300)
        key = written.casefold()
        if key in seen:
            raise VoiceProfileError(f'{label} contains duplicate written forms')
        seen.add(key)
    return copy.deepcopy(value)


def _validate_mix(value, label):
    _fields(value, ('revision', 'recipe'), label)
    _positive_revision(value.get('revision'), f'{label}.revision')
    _stable_id(value.get('recipe'), f'{label}.recipe')
    return copy.deepcopy(value)


def _validate_acceptance(value, label):
    _fields(
        value,
        (
            'state',
            'owner_review',
            'qualification_report_sha256',
            'long_form_manifest_sha256',
            'long_form_audio_sha256',
            'accepted_at',
        ),
        label,
    )
    if value.get('state') not in ACCEPTANCE_STATES:
        raise VoiceProfileError(f'{label}.state is unsupported')
    if value.get('owner_review') not in OWNER_REVIEWS:
        raise VoiceProfileError(f'{label}.owner_review is unsupported')
    for field in (
        'qualification_report_sha256',
        'long_form_manifest_sha256',
        'long_form_audio_sha256',
    ):
        _optional_hash(value.get(field), f'{label}.{field}')
    _timestamp(value.get('accepted_at'), f'{label}.accepted_at')
    return copy.deepcopy(value)


def _validate_profile(value, label='voice profile', *, allow_supersedes=False):
    required = (
        'id',
        'revision',
        'name',
        'status',
        'identity',
        'producer',
        'deliveries',
        'lexicon',
        'mix',
        'acceptance',
    )
    optional = ('supersedes_profile_sha256',) if allow_supersedes else ()
    _fields(value, required, label, optional)
    identifier = _stable_id(value.get('id'), f'{label}.id')
    _positive_revision(value.get('revision'), f'{label}.revision')
    _text(value.get('name'), f'{label}.name', 120)
    status = value.get('status')
    if status not in PROFILE_STATUSES:
        raise VoiceProfileError(f'{label}.status is unsupported')
    identity = _validate_identity(value.get('identity'), f'{label}.identity')
    producer = _validate_producer(value.get('producer'), f'{label}.producer')
    deliveries = _validate_deliveries(value.get('deliveries'), f'{label}.deliveries')
    _validate_lexicon(value.get('lexicon'), f'{label}.lexicon')
    _validate_mix(value.get('mix'), f'{label}.mix')
    acceptance = _validate_acceptance(value.get('acceptance'), f'{label}.acceptance')
    if 'supersedes_profile_sha256' in value:
        _required_hash(value.get('supersedes_profile_sha256'), f'{label}.supersedes_profile_sha256')

    if status == 'control':
        if acceptance['state'] != 'control' or acceptance['owner_review'] != 'not-applicable':
            raise VoiceProfileError(f'{label} control status needs control acceptance metadata')
        if not producer['runnable']:
            raise VoiceProfileError(f'{label} control profile must be runnable')
    elif status == 'experimental':
        if acceptance['state'] != 'unreviewed' or acceptance['owner_review'] != 'unreviewed':
            raise VoiceProfileError(f'{label} experimental status needs unreviewed acceptance metadata')
    elif status == 'accepted':
        if acceptance['state'] != 'accepted' or acceptance['owner_review'] != 'accepted':
            raise VoiceProfileError(f'{label} accepted status needs explicit owner acceptance')
        for field in (
            'qualification_report_sha256',
            'long_form_manifest_sha256',
            'long_form_audio_sha256',
        ):
            _required_hash(acceptance[field], f'{label}.acceptance.{field}')
        _timestamp(acceptance['accepted_at'], f'{label}.acceptance.accepted_at', required=True)
        if identity['reference'] is None:
            raise VoiceProfileError(f'{label} accepted original profile needs retained reference evidence')
        if not HEX_40_RE.fullmatch(identity['model_revision']):
            raise VoiceProfileError(f'{label}.identity.model_revision must pin a full model revision')
        if not producer['runnable']:
            raise VoiceProfileError(f'{label} accepted profile must be runnable')
        if any(delivery['status'] != 'qualified' for delivery in deliveries):
            raise VoiceProfileError(f'{label} accepted profile needs qualified delivery presets')
    elif status == 'rejected':
        if acceptance['state'] != 'rejected' or acceptance['owner_review'] != 'rejected':
            raise VoiceProfileError(f'{label} rejected status needs rejected acceptance metadata')

    result = copy.deepcopy(value)
    result['id'] = identifier
    return result


def _validate_collection(value, label, *, allow_supersedes=False):
    _fields(value, ('schema_version', 'profiles'), label)
    if value.get('schema_version') != 1:
        raise VoiceProfileError(f'{label} has an unsupported schema version')
    profiles = value.get('profiles')
    if not isinstance(profiles, list) or not 1 <= len(profiles) <= MAX_PROFILES:
        raise VoiceProfileError(f'{label}.profiles must contain 1 to {MAX_PROFILES} records')
    result = []
    seen = set()
    for index, profile in enumerate(profiles):
        validated = _validate_profile(
            profile,
            f'{label}.profiles[{index}]',
            allow_supersedes=allow_supersedes,
        )
        if validated['id'] in seen:
            raise VoiceProfileError(f'{label} has a duplicate profile ID: {validated["id"]}')
        seen.add(validated['id'])
        result.append(validated)
    return {'schema_version': 1, 'profiles': result}


def load_catalog(path: Path | None = None) -> dict:
    source = DEFAULT_CATALOG if path is None else Path(path)
    value = _read_json(source, 'voice profile catalogue')
    return _validate_collection(value, 'voice profile catalogue')


def load_registry(path: Path, base_catalog: dict) -> dict:
    base = _validate_collection(copy.deepcopy(base_catalog), 'base voice profile catalogue')
    local = _validate_collection(
        _read_json(Path(path), 'local voice profile registry'),
        'local voice profile registry',
        allow_supersedes=True,
    )
    ordered = [copy.deepcopy(item) for item in base['profiles']]
    positions = {item['id']: index for index, item in enumerate(ordered)}
    for profile in local['profiles']:
        identifier = profile['id']
        if identifier in positions:
            current = ordered[positions[identifier]]
            supersedes = profile.get('supersedes_profile_sha256')
            if supersedes != profile_digest(current):
                raise VoiceProfileError(
                    f'Local voice profile {identifier} supersedes metadata does not match the current profile SHA-256'
                )
            if profile['revision'] <= current['revision']:
                raise VoiceProfileError(
                    f'Local voice profile {identifier} revision must increase when it supersedes a profile'
                )
            ordered[positions[identifier]] = copy.deepcopy(profile)
        else:
            if 'supersedes_profile_sha256' in profile:
                raise VoiceProfileError(
                    f'New local voice profile {identifier} cannot supersede an unknown profile'
                )
            positions[identifier] = len(ordered)
            ordered.append(copy.deepcopy(profile))
    return {'schema_version': 1, 'profiles': ordered}


def resolve_profile(
    profile_id: str,
    delivery_id: str,
    *,
    registry_path: Path | None = None,
    speaker_id: str | None = None,
) -> dict:
    profile_id = _stable_id(profile_id, 'profile_id')
    delivery_id = _stable_id(delivery_id, 'delivery_id')
    catalogue = load_catalog()
    source_kind = 'catalog'
    if registry_path is not None:
        catalogue = load_registry(Path(registry_path), catalogue)
        source_kind = 'local-registry'
    try:
        profile = next(item for item in catalogue['profiles'] if item['id'] == profile_id)
    except StopIteration as exc:
        raise VoiceProfileError(f'Unknown narration profile: {profile_id}') from exc
    try:
        delivery = next(item for item in profile['deliveries'] if item['id'] == delivery_id)
    except StopIteration as exc:
        raise VoiceProfileError(
            f'Narration profile {profile_id} has no delivery preset {delivery_id}'
        ) from exc

    retained_speaker = profile['producer']['speaker_id']
    speaker_source = 'profile'
    if speaker_id is not None:
        if not isinstance(speaker_id, str) or not SPEAKER_RE.fullmatch(speaker_id):
            raise VoiceProfileError('speaker_id override must be stable lowercase metadata')
        if speaker_id != retained_speaker:
            retained_speaker = speaker_id
            speaker_source = 'cli-metadata-override'

    delivery_binding = copy.deepcopy(delivery)
    delivery_binding['sha256'] = canonical_digest(delivery)
    profile_sha256 = profile_digest(profile)
    binding = {
        'schema_version': 1,
        'id': profile['id'],
        'revision': profile['revision'],
        'name': profile['name'],
        'status': profile['status'],
        'source': source_kind,
        'profile_sha256': profile_sha256,
        'identity': copy.deepcopy(profile['identity']),
        'adapter': profile['producer']['adapter'],
        'runnable': profile['producer']['runnable'],
        'speaker_id': retained_speaker,
        'speaker_id_source': speaker_source,
        'delivery': delivery_binding,
        'lexicon': {
            'revision': profile['lexicon']['revision'],
            'sha256': canonical_digest(profile['lexicon']),
        },
        'mix': {
            'revision': profile['mix']['revision'],
            'recipe': profile['mix']['recipe'],
            'sha256': canonical_digest(profile['mix']),
        },
        'acceptance': copy.deepcopy(profile['acceptance']),
    }
    binding['binding_sha256'] = canonical_digest(binding)
    return binding


def require_executable(binding: dict) -> None:
    if not isinstance(binding, dict):
        raise VoiceProfileError('Narration profile binding is invalid')
    status = binding.get('status')
    identifier = binding.get('id', 'unknown')
    if status == 'experimental':
        raise VoiceProfileError(
            f'Narration profile {identifier} is experimental and has not passed owner acceptance'
        )
    if status == 'rejected':
        raise VoiceProfileError(f'Narration profile {identifier} was rejected during qualification')
    if status not in ('control', 'accepted'):
        raise VoiceProfileError(f'Narration profile {identifier} has no executable acceptance state')
    if binding.get('adapter') != 'voice-baseline':
        raise VoiceProfileError(
            f'Narration profile {identifier} uses unsupported adapter {binding.get("adapter")!r}'
        )
    identity = binding.get('identity')
    if (status != 'control' or not isinstance(identity, dict)
            or identity.get('model_id') != 'hexgrad/Kokoro-82M'
            or identity.get('voice') != 'af_heart'):
        raise VoiceProfileError(
            'The current voice-baseline adapter can execute only the pinned Kokoro af_heart control; '
            f'narration profile {identifier} needs its own qualified producer adapter'
        )
    if binding.get('runnable') is not True:
        raise VoiceProfileError(f'Narration profile {identifier} is not bound to a runnable producer')
