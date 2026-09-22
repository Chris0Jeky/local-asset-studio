"""Explicit compare-and-swap narration updates with one durable transition journal."""
import copy
from pathlib import Path

import voice_profile as vp
import voice_profile_registry_io as io
from strict_json import StrictJsonError, loads_strict

RegistryUnconfirmed = io.RegistryUnconfirmed
MAX_TRANSITIONS = 256
MAX_REGISTRY_BYTES = 4 * 1024 * 1024


def _command(value):
    try:
        vp._fields(value, ('schema_version', 'request_id', 'expected_registry_sha256',
                           'expected_profile_sha256', 'profile'), 'registry command')
        if type(value['schema_version']) is not int or value['schema_version'] != 1:
            raise vp.VoiceProfileError('Registry command schema version is unsupported')
        vp._stable_id(value['request_id'], 'request ID')
        vp._required_hash(value['expected_registry_sha256'], 'expected registry SHA-256')
        vp._required_hash(value['expected_profile_sha256'], 'expected profile SHA-256')
        vp._validate_profile(value['profile'], allow_supersedes=True)
        vp._required_hash(value['profile'].get('supersedes_profile_sha256'), 'supersedes profile SHA-256')
        if len(vp.canonical_bytes(value)) > vp.MAX_PROFILE_JSON_BYTES:
            raise vp.VoiceProfileError('Registry command exceeds its byte capacity')
        return copy.deepcopy(value)
    except (TypeError, UnicodeError, RecursionError) as exc:
        raise vp.VoiceProfileError('Invalid registry command') from exc


def _empty(catalog):
    return {'schema_version': 2, 'catalog_sha256': vp.canonical_digest(catalog), 'transitions': []}


def _receipt(state, profiles, command):
    if command['expected_registry_sha256'] != vp.canonical_digest(state):
        raise vp.VoiceProfileError('Registry changed; expected registry SHA-256 does not match')
    profile = command['profile']
    previous = next((item for item in profiles if item['id'] == profile['id']), None)
    if previous is None: raise vp.VoiceProfileError('Registry update requires an existing catalogue profile')
    previous_hash = vp.profile_digest(previous)
    if (command['expected_profile_sha256'] != previous_hash
            or profile['supersedes_profile_sha256'] != previous_hash):
        raise vp.VoiceProfileError('Registry profile changed; predecessor SHA-256 does not match')
    if profile['revision'] <= previous['revision']:
        raise vp.VoiceProfileError('Registry profile revision must strictly increase')
    return {'schema_version': 1, 'sequence': len(state['transitions']) + 1,
            'request_id': command['request_id'], 'command_sha256': vp.canonical_digest(command),
            'previous_registry_sha256': vp.canonical_digest(state),
            'previous_profile_sha256': previous_hash,
            'resulting_profile_sha256': vp.profile_digest(profile)}


def decode_registry(raw, catalog):
    """Validate every transition against its predecessor; no mutable profile projection."""
    empty = _empty(catalog)
    if raw is None: return empty, copy.deepcopy(catalog['profiles'])
    try:
        value = loads_strict(raw, label='narration registry')
        if isinstance(value, dict) and type(value.get('schema_version')) is int and value['schema_version'] == 1:
            raise vp.VoiceProfileError('Legacy registry version is read-only; explicit migration is required')
        vp._fields(value, ('schema_version', 'catalog_sha256', 'transitions'), 'narration registry')
        if type(value['schema_version']) is not int or value['schema_version'] != 2:
            raise vp.VoiceProfileError('Unsupported narration registry schema version')
        if value['catalog_sha256'] != empty['catalog_sha256']:
            raise vp.VoiceProfileError('Registry catalogue identity changed')
        transitions = value['transitions']
        if not isinstance(transitions, list) or len(transitions) > MAX_TRANSITIONS:
            raise vp.VoiceProfileError('Registry transition capacity exceeded')
        state = empty; profiles = copy.deepcopy(catalog['profiles']); seen = set()
        for transition in transitions:
            vp._fields(transition, ('command', 'receipt'), 'registry transition')
            command = _command(transition['command'])
            if command['request_id'] in seen: raise vp.VoiceProfileError('Duplicate registry request ID')
            receipt = _receipt(state, profiles, command)
            if vp.canonical_bytes(transition['receipt']) != vp.canonical_bytes(receipt):
                raise vp.VoiceProfileError('Registry receipt does not match its transition')
            state['transitions'].append({'command': command, 'receipt': receipt})
            profiles = [copy.deepcopy(command['profile']) if item['id'] == command['profile']['id'] else item
                        for item in profiles]
            seen.add(command['request_id'])
        return state, profiles
    except (StrictJsonError, TypeError, UnicodeError, RecursionError) as exc:
        raise vp.VoiceProfileError('Invalid narration registry JSON or transition') from exc


def inspect_registry(path, *, catalog=None):
    catalog = vp.load_catalog() if catalog is None else catalog
    state, profiles = decode_registry(io.capture(path, MAX_REGISTRY_BYTES)[0], catalog)
    return {'schema_version': 2, 'registry_sha256': vp.canonical_digest(state),
            'profiles': profiles, 'receipts': [copy.deepcopy(t['receipt']) for t in state['transitions']]}


def get_receipt(path, request_id):
    vp._stable_id(request_id, 'request ID')
    return next((r for r in inspect_registry(path)['receipts'] if r['request_id'] == request_id), None)


def update_registry(path, command, *, lock_timeout=5):
    command = _command(command)  # validation precedes even lock-file creation
    path = io.absolute(path)
    catalog = vp.load_catalog(); catalog_hash = vp.canonical_digest(catalog)
    initial_raw, initial_identity = io.capture(path, MAX_REGISTRY_BYTES)
    decode_registry(initial_raw, catalog)
    committed = False

    def recheck_catalog():
        if vp.canonical_digest(vp.load_catalog()) != catalog_hash:
            raise vp.VoiceProfileError('Registry catalogue changed during update')

    try:
        with io.writer_lock(path, timeout=lock_timeout) as owner:
            raw, identity = io.capture(path, MAX_REGISTRY_BYTES)
            if identity != initial_identity:
                raise vp.VoiceProfileError('Registry changed while waiting for the lock; inspect before retrying')
            recheck_catalog()
            state, profiles = decode_registry(raw, catalog)
            for transition in state['transitions']:
                if transition['command']['request_id'] == command['request_id']:
                    if vp.canonical_bytes(transition['command']) != vp.canonical_bytes(command):
                        raise vp.VoiceProfileError('Registry request ID was already used with different content')
                    committed = True  # the historical receipt already crossed publication
                    return copy.deepcopy(transition['receipt'])
            if len(state['transitions']) >= MAX_TRANSITIONS:
                raise vp.VoiceProfileError('Registry journal is full; accepted request IDs are never pruned')
            receipt = _receipt(state, profiles, command)
            state['transitions'].append({'command': command, 'receipt': receipt})
            encoded = vp.canonical_bytes(state) + b'\n'
            if len(encoded) > MAX_REGISTRY_BYTES:
                raise vp.VoiceProfileError('Registry byte capacity exceeded')
            io.publish(path, encoded, identity, MAX_REGISTRY_BYTES, owner, recheck_catalog)
            committed = True
        return copy.deepcopy(receipt)
    except (OSError, vp.VoiceProfileError) as exc:
        if isinstance(exc, RegistryUnconfirmed): raise
        if committed:
            raise RegistryUnconfirmed('Registry committed but lock acknowledgement failed; replay the exact request') from exc
        if isinstance(exc, vp.VoiceProfileError): raise
        raise vp.VoiceProfileError(f'Registry update refused: {exc}') from exc
