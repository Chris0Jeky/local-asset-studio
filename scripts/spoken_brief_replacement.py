#!/usr/bin/env python3
"""Explicit one-segment Voice replacement; uncertain mutations are never replayed."""
from __future__ import annotations

import argparse
import io
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import wave

from spoken_brief_archive import checked_directory, inspect_run, wav_parameters
from spoken_brief_compile import (
    ACTIVE_STATUSES, MAX_BATCH_WORDS, MAX_LINE_CHARS, MAX_NARRATED_CHARS, MAX_SEGMENTS, SPEAKER_RE,
    SpokenBriefError, StudioRejected, canonical_digest, digest_bytes,
)
from spoken_brief_exports import _claim, _json_bytes
from spoken_brief_inbox import HEX, _capture, _constant, _lineage, _object
from spoken_brief_qa import archive_binding, load_review
from spoken_brief_transport import (
    MAX_AUDIO_BYTES, MAX_JSON_BYTES, PROJECT_ID, StudioClient, _sync_parent,
    artifact_for, studio_record, verify_project, write_json,
)

MAX_REQUESTS = 32
MAX_PROJECTS = MAX_SEGMENTS
STATUSES = {'prepared', 'creating', 'create-unconfirmed', 'create-rejected', 'created',
            'starting', 'start-unconfirmed', 'start-rejected', 'observing', 'terminal', 'artifact-verified'}
RESERVED = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))}


def _id(identifier):
    if not isinstance(identifier, str) or not SPEAKER_RE.fullmatch(identifier) or identifier in RESERVED:
        raise SpokenBriefError('Replacement request ID must be a portable, stable lowercase identifier')
    return identifier


def _snapshot(path):
    raw, token = _capture(path, MAX_JSON_BYTES)
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_object, parse_constant=_constant)
        if not isinstance(value, dict): raise ValueError('expected an object')
        return value, token
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise SpokenBriefError(f'Invalid replacement record: {path.name}') from exc


def _build(directory, archive, segment_id, review_id, request_id, text):
    _id(request_id)
    if len(archive['project_plans']) >= MAX_PROJECTS:
        raise SpokenBriefError('Parent project history is full; no replacement can be admitted')
    matches = [s for s in archive['segments'] if s['id'] == segment_id]
    if len(matches) != 1: raise SpokenBriefError('Select one stable segment, not the master or a path')
    segment = matches[0]; review = load_review(directory, review_id)
    if (review['target'] != segment_id or review['audio_sha256'] != segment['audio_sha256'] or review['decision'] != 'replace'):
        raise SpokenBriefError('Replacement requires an explicit owner replace review for this exact take')
    text = segment['text'] if text is None else text
    if (not isinstance(text, str) or not 1 <= len(text) <= MAX_LINE_CHARS or text != text.strip()
            or any(c in text for c in '\0\r\n\t') or len(text.split()) > MAX_BATCH_WORDS):
        raise SpokenBriefError('Replacement text must be one bounded, unpadded Voice line')
    if sum(len(s['text']) for s in archive['segments']) - len(segment['text']) + len(text) > MAX_NARRATED_CHARS:
        raise SpokenBriefError('Replacement would exceed the total narration character budget')
    try: text_hash = digest_bytes(text.encode('utf-8'))
    except UnicodeError as exc: raise SpokenBriefError('Replacement text must be UTF-8') from exc
    request = {'schema_version': 1, 'kind': 'spoken-brief-replacement', 'id': request_id,
        'archive': archive_binding(archive), 'segment_id': segment_id, 'old_audio_sha256': segment['audio_sha256'],
        'original_text': segment['text'], 'original_text_sha256': segment['text_sha256'],
        'text': text, 'text_sha256': text_hash, 'pause_after_ms': segment['pause_after_ms'],
        'speaker_id': archive['speaker_id'], 'studio': archive['studio'], 'review_sha256': review_id}
    request['request_sha256'] = canonical_digest(request)
    return request


def _initial(request):
    return {'schema_version': 1, 'request_sha256': request['request_sha256'], 'status': 'prepared',
        'project_id': None, 'project_plan': None, 'artifact': None, 'last_observed_status': None, 'last_error': None}


def _provenance(request, project, identifier, retained=None):
    value = verify_project(project, identifier, [{'id': request['segment_id'], 'text': request['text']}],
                           request['speaker_id'], expected_plan_sha256=retained['sha256'] if retained else None)
    if value['producer_sha256'] != request['archive']['producer_sha256']:
        raise SpokenBriefError('Replacement producer differs from the retained narration recipe; no fallback is authorized')
    return value


def _validate_state(value, request, archive):
    try:
        if (set(value) != set(_initial(request)) or type(value['schema_version']) is not int or value['schema_version'] != 1
                or value['request_sha256'] != request['request_sha256'] or not isinstance(value['status'], str)
                or value['status'] not in STATUSES): raise SpokenBriefError('Replacement state schema or request identity differs')
        identifier, plan, artifact = value['project_id'], value['project_plan'], value['artifact']
        no_child = value['status'] in ('prepared', 'creating', 'create-unconfirmed', 'create-rejected')
        if no_child:
            if identifier is not None or plan is not None or value['last_observed_status'] is not None:
                raise SpokenBriefError('Unexpected child observation for a state with no retained child')
        elif (not isinstance(identifier, str) or not PROJECT_ID.fullmatch(identifier)
                or identifier in [p['id'] for p in archive['project_plans']]):
            raise SpokenBriefError('Replacement child identity is missing, invalid or aliases a parent project')
        if value['status'] in ('created', 'starting', 'start-unconfirmed', 'start-rejected') and value['last_observed_status'] is not None:
            raise SpokenBriefError('A pre-observation marker cannot discard retained child observations')
        if value['status'] == 'terminal' and value['last_observed_status'] is None:
            raise SpokenBriefError('Terminal state requires its retained child observation')
        if plan is not None:
            _provenance(request, {'id': identifier, 'kind': 'voice', 'plan': plan}, identifier)
        elif value['status'] not in ('prepared', 'creating', 'create-unconfirmed', 'create-rejected', 'created'):
            raise SpokenBriefError('Replacement state lost its signed child plan')
        if value['status'] == 'artifact-verified':
            if (not isinstance(artifact, dict) or set(artifact) != {'sha256', 'bytes', 'samples'}
                    or not isinstance(artifact['sha256'], str) or not HEX.fullmatch(artifact['sha256'])
                    or type(artifact['bytes']) is not int or not 1 <= artifact['bytes'] <= MAX_AUDIO_BYTES
                    or type(artifact['samples']) is not int or not 1 <= artifact['samples'] <= MAX_AUDIO_BYTES // 2
                    or value['last_observed_status'] != 'completed'):
                raise SpokenBriefError('Verified take evidence is incomplete')
        elif artifact is not None: raise SpokenBriefError('Unverified state cannot claim a completed artifact')
        for key, bound in [('last_error', 2000), ('last_observed_status', 64)]:
            if value[key] is not None and (not isinstance(value[key], str) or not 1 <= len(value[key]) <= bound):
                raise SpokenBriefError('Invalid replacement observation')
    except (KeyError, TypeError, AttributeError) as exc:
        raise SpokenBriefError('Malformed replacement state') from exc


def _load(directory, archive, request_id):
    path = directory / 'replacements' / _id(request_id)
    request, request_token = _snapshot(path / 'request.json')
    try:
        expected = _build(directory, archive, request['segment_id'], request['review_sha256'], request_id, request['text'])
    except (KeyError, TypeError) as exc: raise SpokenBriefError('Malformed replacement request') from exc
    if canonical_digest(request) != canonical_digest(expected):
        raise SpokenBriefError('Retained replacement request differs from this archive or review')
    state, state_token = _snapshot(path / 'state.json'); _validate_state(state, request, archive)
    return path, request, state, request_token, state_token


def _entries(root):
    entries = []
    with os.scandir(root) as iterator:
        for item in iterator:
            entries.append(item.name)
            if len(entries) > MAX_REQUESTS: raise SpokenBriefError('Replacement history capacity exceeded; no records pruned')
    return sorted(entries)


def _siblings(directory, archive, segment_id, request_id):
    root = directory / 'replacements'; _lineage(root)
    for name in _entries(root):
        if name == request_id or name.startswith('.prepare-'): continue
        _, request, state, _, _ = _load(directory, archive, name)
        if request['segment_id'] == segment_id and state['status'] != 'artifact-verified':
            raise SpokenBriefError(f'Replacement {name} is unresolved; a different request ID cannot authorize a duplicate')


def prepare(run_dir, segment_id, review_id, request_id, *, text=None):
    """Persist an inspectable request and initial state together, without transport."""
    directory = checked_directory(run_dir); archive = inspect_run(directory)
    request = _build(directory, archive, segment_id, review_id, request_id, text)
    root = directory / 'replacements'; target = root / request_id
    if os.path.lexists(target):
        _, old, _, _, _ = _load(directory, archive, request_id)
        if canonical_digest(old) != canonical_digest(request): raise SpokenBriefError('Request ID already names different content')
        return old
    stage = None
    try:
        with _claim(directory, archive['manifest_sha256']) as verify:
            root.mkdir(exist_ok=True); lineage = _lineage(root)
            if os.path.lexists(target): raise SpokenBriefError('Request appeared while acquiring the claim; inspect before retrying')
            _siblings(directory, archive, segment_id, request_id)
            if len(_entries(root)) >= MAX_REQUESTS: raise SpokenBriefError('Replacement history is full; no records pruned')
            stage = Path(tempfile.mkdtemp(prefix='.prepare-', dir=root))
            write_json(stage / 'request.json', request); write_json(stage / 'state.json', _initial(request))
            if (canonical_digest(_snapshot(stage / 'request.json')[0]) != canonical_digest(request)
                    or canonical_digest(_snapshot(stage / 'state.json')[0]) != canonical_digest(_initial(request))
                    or _lineage(root) != lineage or inspect_run(directory) != archive):
                raise SpokenBriefError('Request, parent or archive changed during preparation')
            verify()
            if os.path.lexists(target): raise SpokenBriefError('Request destination already exists')
            os.rename(stage, target); stage = None; _sync_parent(target)
            return request
    except OSError as exc: raise SpokenBriefError(f'Cannot prepare replacement: {exc}') from exc
    finally:
        if stage is not None: shutil.rmtree(stage)


def _save(path, state, token, guard):
    """Own the state transition; refuse external replacement even with equal bytes."""
    guard()
    if _snapshot(path)[1] != token: raise SpokenBriefError('Replacement state changed outside the owned operation')
    raw = _json_bytes(state); fd, name = tempfile.mkstemp(prefix='.state-', suffix='.tmp', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        if _capture(temporary, MAX_JSON_BYTES)[0] != raw: raise SpokenBriefError('Staged state bytes changed')
        guard()
        if _snapshot(path)[1] != token: raise SpokenBriefError('Replacement state changed during flush')
        os.replace(temporary, path); _sync_parent(path)
        return _snapshot(path)[1]
    finally: temporary.unlink(missing_ok=True)


def _audio(raw):
    if not 1 <= len(raw) <= MAX_AUDIO_BYTES: raise SpokenBriefError('Replacement WAV byte bound exceeded')
    try:
        with wave.open(io.BytesIO(raw), 'rb') as reader:
            count = wav_parameters(reader)
            if len(reader.readframes(count)) != count * 2: raise SpokenBriefError('Truncated replacement PCM')
    except (EOFError, wave.Error) as exc: raise SpokenBriefError('Invalid replacement scene WAV') from exc
    return {'sha256': digest_bytes(raw), 'bytes': len(raw), 'samples': count}


def _take(path, state):
    raw, _ = _capture(path / 'take.wav', MAX_AUDIO_BYTES)
    if _audio(raw) != state['artifact']: raise SpokenBriefError('Retained replacement WAV differs; no new inference is authorized')
    return raw


def inspect(run_dir, request_id):
    directory = checked_directory(run_dir); archive = inspect_run(directory)
    path, request, state, _, _ = _load(directory, archive, request_id)
    if state['status'] == 'artifact-verified': _take(path, state)
    return {'directory': str(path), 'request': request, 'state': state}


def _status(project):
    state = project.get('state')
    if (not isinstance(state, dict) or not isinstance(state.get('status'), str)
            or not 1 <= len(state['status']) <= 64 or not isinstance(state.get('artifacts', []), list)
            or len(state.get('artifacts', [])) > 16):
        raise SpokenBriefError('Canonical child observation is malformed')
    return state['status']


def start(run_dir, request_id, *, poll_seconds=1.0, deadline_seconds=3600):
    """Explicitly admit one child through the existing worker, or observe its ID."""
    for value, low, high in [(poll_seconds, 0.01, 30), (deadline_seconds, 1, 86400)]:
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise SpokenBriefError('Poll/deadline must be finite values within the documented bounds')
    directory = checked_directory(run_dir); archive = inspect_run(directory)
    path, request, state, request_token, token = _load(directory, archive, request_id)
    if state['status'] == 'artifact-verified':
        _take(path, state)
        return {'directory': str(path), 'request': request, 'state': state}
    if state['status'] in ('creating', 'create-unconfirmed', 'create-rejected', 'start-rejected', 'terminal'):
        raise SpokenBriefError('Retained mutation is uncertain, rejected or terminal; inspect it instead of resubmitting')
    with _claim(directory, archive['manifest_sha256']) as verify:
        def guard():
            verify()
            if _snapshot(path / 'request.json')[1] != request_token:
                raise SpokenBriefError('Owned replacement request changed')
            if _snapshot(path / 'state.json')[1] != token:
                raise SpokenBriefError('Owned replacement state changed')

        def save(**changes):
            nonlocal token
            state.update(changes); _validate_state(state, request, archive)
            token = _save(path / 'state.json', state, token, guard)

        def environment():
            guard()
            if inspect_run(directory) != archive: raise SpokenBriefError('Parent archive changed during replacement')
            if studio_record(client.base_url, client.get_json('/api/identity')) != request['studio']:
                raise SpokenBriefError('Studio identity differs from the retained parent workspace')
            guard()
            if inspect_run(directory) != archive: raise SpokenBriefError('Parent changed during Studio identity observation')

        def adopt(project):
            _provenance(request, project, state['project_id'], state['project_plan'])
            if state['project_plan'] is None: save(project_plan=project['plan'])
            return _status(project)

        guard()
        if _snapshot(path / 'state.json')[1] != token: raise SpokenBriefError('State changed while acquiring the claim')
        _siblings(directory, archive, request['segment_id'], request_id)
        client = StudioClient(request['studio']['base_url'])
        environment()
        if state['status'] == 'prepared':
            save(status='creating')
            environment()
            try:
                acknowledgement = client.post_json('/api/voice-baseline', {
                    'name': f'Spoken replacement {request_id}', 'speaker_id': request['speaker_id'],
                    'lines': [{'id': request['segment_id'], 'text': request['text']}],
                })
            except StudioRejected as exc:
                save(status='create-rejected', last_error=str(exc)[:2000]); raise
            except (SpokenBriefError, OSError) as exc:
                save(status='create-unconfirmed', last_error=str(exc)[:2000]); raise SpokenBriefError('Replacement Create is unconfirmed') from exc
            identifier = acknowledgement.get('id')
            if (not isinstance(identifier, str) or not PROJECT_ID.fullmatch(identifier)
                    or identifier in [p['id'] for p in archive['project_plans']]):
                save(status='create-unconfirmed', last_error='Invalid or aliased Create acknowledgement')
                raise SpokenBriefError('Replacement Create has no new valid child identity')
            save(status='created', project_id=identifier)
        environment()
        project = client.get_json('/api/production/' + state['project_id']); status = adopt(project)
        if status == 'planned':
            if state['status'] != 'created':
                raise SpokenBriefError('Start was already attempted; planned observation does not authorize replay')
            environment(); save(status='starting')
            environment()
            try: client.post_json(f"/api/production/{state['project_id']}/start", {})
            except StudioRejected as exc:
                save(status='start-rejected', last_error=str(exc)[:2000]); raise
            except (SpokenBriefError, OSError) as exc:
                save(status='start-unconfirmed', last_error=str(exc)[:2000]); raise SpokenBriefError('Replacement Start is unconfirmed; retain this child') from exc
            save(status='observing')
            environment(); project = client.get_json('/api/production/' + state['project_id']); status = adopt(project)
        deadline = time.monotonic() + deadline_seconds
        while status in ACTIVE_STATUSES:
            if state['last_observed_status'] != status: save(status='observing', last_observed_status=status)
            if time.monotonic() >= deadline: raise SpokenBriefError('Replacement observation deadline reached; child retained without replay')
            time.sleep(poll_seconds); guard()
            if studio_record(client.base_url, client.get_json('/api/identity')) != request['studio']:
                raise SpokenBriefError('Studio changed while observing the retained child')
            project = client.get_json('/api/production/' + state['project_id']); status = adopt(project)
        if status != 'completed':
            save(status='terminal', last_observed_status=status, last_error='Child ended as ' + status)
            raise SpokenBriefError('Replacement child ended as ' + status + '; no retry or replacement authorized')
        save(status='observing', last_observed_status='completed')
        environment(); artifact = artifact_for(project, request['segment_id'], state['project_id'])
        cache = path / 'take.wav'
        raw = _capture(cache, MAX_AUDIO_BYTES)[0] if os.path.lexists(cache) else client.get_bytes(artifact['url'])
        details = _audio(raw)
        if details['sha256'] != artifact['sha256']: raise SpokenBriefError('Replacement artifact hash differs from the retained child')
        environment()
        # Completed acknowledgement/earlier snapshots are not authority for a
        # project that changed while its artifact was being downloaded.
        current = client.get_json('/api/production/' + state['project_id'])
        if adopt(current) != 'completed': raise SpokenBriefError('Child changed before artifact publication')
        if artifact_for(current, request['segment_id'], state['project_id'])['sha256'] != details['sha256']:
            raise SpokenBriefError('Child artifact identity changed during download')
        if not os.path.lexists(cache):
            fd, name = tempfile.mkstemp(prefix='.take-', suffix='.tmp', dir=path); temporary = Path(name)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(raw); stream.flush(); os.fsync(stream.fileno())
                if _capture(temporary, MAX_AUDIO_BYTES)[0] != raw: raise SpokenBriefError('Staged replacement audio changed')
                guard(); os.link(temporary, cache); _sync_parent(cache)
            finally: temporary.unlink(missing_ok=True)
        if _audio(_capture(cache, MAX_AUDIO_BYTES)[0]) != details: raise SpokenBriefError('Replacement cache changed before receipt')
        save(status='artifact-verified', artifact=details, last_error=None)
        return {'directory': str(path), 'request': request, 'state': state}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); commands = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', 'inspect', 'start', 'assemble'):
        command = commands.add_parser(name); command.add_argument('run_dir'); command.add_argument('request_id')
        if name == 'prepare':
            command.add_argument('--segment', required=True); command.add_argument('--review-sha256', required=True); command.add_argument('--text')
        elif name == 'start':
            command.add_argument('--poll-seconds', type=float, default=1); command.add_argument('--deadline-seconds', type=float, default=3600)
    args = parser.parse_args(argv)
    try:
        if args.command == 'prepare': result = prepare(args.run_dir, args.segment, args.review_sha256, args.request_id, text=args.text)
        elif args.command == 'inspect': result = inspect(args.run_dir, args.request_id)
        elif args.command == 'start': result = start(args.run_dir, args.request_id, poll_seconds=args.poll_seconds, deadline_seconds=args.deadline_seconds)
        else:
            from spoken_brief_reassembly import assemble
            result = assemble(args.run_dir, args.request_id)
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)); return 0
    except KeyboardInterrupt:
        print('Replacement interrupted; inspect retained intent/child before any further action.', file=sys.stderr); return 130
    except (SpokenBriefError, OSError) as exc:
        print('spoken brief replacement: ' + str(exc), file=sys.stderr); return 1


if __name__ == '__main__': raise SystemExit(main())
