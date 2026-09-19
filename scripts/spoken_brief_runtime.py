"""Coordinate bounded Voice baseline projects into one spoken handoff."""
from __future__ import annotations

from pathlib import Path
import re
import time

from spoken_brief_compile import *
from spoken_brief_transport import *
from spoken_brief_transport import _completed_result, _project_name, _wav_details


def _confirm_environment(client: StudioClient, state: dict, state_path: Path, manifest: dict) -> dict:
    identity = client.get_json('/api/identity')
    current = studio_record(client.base_url, identity)
    retained = state.get('studio')
    if retained is None:
        if any(batch.get('project_id') for batch in state.get('batches', [])):
            raise SpokenBriefError('Retained child projects have no Studio identity provenance')
        state['studio'] = current
        write_json(state_path, state)
    elif retained != current:
        raise SpokenBriefError('Studio endpoint or identity changed since this spoken brief was bound')
    verify_source(manifest)
    return current


def _adopt_project(project: dict, identifier: str, batch: list[dict], speaker_id: str,
                   batch_state: dict, state: dict, state_path: Path) -> dict:
    provenance = verify_project(
        project,
        identifier,
        batch,
        speaker_id,
        expected_plan_sha256=batch_state.get('project_plan_sha256'),
    )
    changed = False
    if batch_state.get('project_plan_sha256') is None:
        batch_state['project_plan_sha256'] = provenance['project_plan_sha256']
        changed = True
    retained_producer = state.get('producer_sha256')
    if retained_producer is None:
        state['producer_sha256'] = provenance['producer_sha256']
        changed = True
    elif retained_producer != provenance['producer_sha256']:
        state['status'] = 'blocked'
        batch_state['last_error'] = 'Voice producer configuration changed between spoken-brief batches'
        write_json(state_path, state)
        raise SpokenBriefError(batch_state['last_error'])
    if changed:
        write_json(state_path, state)
    return provenance


def run(pack, *, base_url='http://127.0.0.1:8191', speaker_id='brief-narrator',
        poll_seconds=1.0, deadline_seconds=3600) -> dict:
    if not isinstance(poll_seconds, (int, float)) or not 0 < poll_seconds <= 30:
        raise SpokenBriefError('Poll interval must be greater than zero and at most 30 seconds')
    if not isinstance(deadline_seconds, (int, float)) or not 1 <= deadline_seconds <= 24 * 3600:
        raise SpokenBriefError('Deadline must be from 1 second to 24 hours')
    source = resolve_source(pack)
    manifest = compile_source(source, speaker_id=speaker_id)
    run_dir = run_directory(source, manifest['manifest_sha256'])
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / 'manifest.json'
    state_path = run_dir / 'state.json'
    receipt_path = run_dir / 'receipt.json'
    output = run_dir / (source.stem + '.spoken.wav')
    completed = _completed_result(receipt_path, manifest['manifest_sha256'], output)
    if completed:
        return completed
    claim = acquire_run_claim(run_dir, manifest['manifest_sha256'])
    try:
        if manifest_path.is_file() and read_json(manifest_path) != manifest:
            raise SpokenBriefError('Retained manifest differs for this source hash')
        write_json(manifest_path, manifest)
        state = read_json(state_path) if state_path.is_file() else initial_state(manifest)
        batches = batch_segments(manifest['segments'])
        validate_state(state, manifest, batches)
        if any(batch.get('status') in ('creating', 'create-unconfirmed') and not batch.get('project_id')
               for batch in state['batches']):
            raise SpokenBriefError(
                'A voice project creation is unconfirmed. Inspect Voice baseline and reconcile it before another submission.'
            )
        client = StudioClient(base_url)
        identity_record = _confirm_environment(client, state, state_path, manifest)
        deadline = time.monotonic() + deadline_seconds
        segment_files = {}
        segment_hashes = {}
        for batch_index, (batch_state, batch) in enumerate(zip(state['batches'], batches), 1):
            _confirm_environment(client, state, state_path, manifest)
            identifier = batch_state.get('project_id')
            project = client.get_json('/api/production/' + identifier) if identifier else None
            if project is None:
                payload = {
                    'name': _project_name(source, manifest['manifest_sha256'], batch_index, len(batches)),
                    'speaker_id': speaker_id,
                    'lines': [{'id': line['id'], 'text': line['text']} for line in batch],
                }
                batch_state['status'] = 'creating'
                state['status'] = 'running'
                write_json(state_path, state)
                _confirm_environment(client, state, state_path, manifest)
                try:
                    created = client.post_json('/api/voice-baseline', payload)
                except StudioRejected as exc:
                    batch_state.update(status='pending', last_error=str(exc))
                    state['status'] = 'blocked'
                    write_json(state_path, state)
                    raise
                except SpokenBriefError:
                    batch_state['status'] = 'create-unconfirmed'
                    state['status'] = 'blocked'
                    write_json(state_path, state)
                    raise SpokenBriefError(
                        'Voice project creation outcome is unconfirmed. Inspect Voice baseline before running this handoff again.'
                    )
                identifier = created.get('id')
                if not isinstance(identifier, str) or not re.fullmatch(r'[0-9a-f]{32}', identifier):
                    batch_state['status'] = 'create-unconfirmed'
                    state['status'] = 'blocked'
                    write_json(state_path, state)
                    raise SpokenBriefError('Voice baseline returned an invalid project identity; creation is unconfirmed')
                batch_state.update(project_id=identifier, status='created')
                write_json(state_path, state)
                _confirm_environment(client, state, state_path, manifest)
                project = client.get_json(f'/api/production/{identifier}')
            if not isinstance(project, dict) or project.get('id') != identifier or project.get('kind') != 'voice':
                raise SpokenBriefError(f'Retained project {identifier} is not the expected Voice baseline project')
            if 'plan' not in project:
                _confirm_environment(client, state, state_path, manifest)
                project = client.get_json(f'/api/production/{identifier}')
            _adopt_project(project, identifier, batch, speaker_id, batch_state, state, state_path)
            status = project.get('state', {}).get('status')
            if status == 'planned':
                _confirm_environment(client, state, state_path, manifest)
                try:
                    client.post_json(f'/api/production/{identifier}/start', {})
                except StudioRejected as exc:
                    batch_state.update(status='start-rejected', last_error=str(exc))
                    state['status'] = 'blocked'
                    write_json(state_path, state)
                    raise
                except SpokenBriefError:
                    batch_state['status'] = 'start-unconfirmed'
                    state['status'] = 'blocked'
                    write_json(state_path, state)
                    raise SpokenBriefError(
                        f'Voice start outcome is unconfirmed for {identifier}. Inspect that project; no replacement was created.'
                    )
                batch_state['status'] = 'start-accepted'
                write_json(state_path, state)
                _confirm_environment(client, state, state_path, manifest)
                project = client.get_json(f'/api/production/{identifier}')
                _adopt_project(project, identifier, batch, speaker_id, batch_state, state, state_path)
                status = project.get('state', {}).get('status')
                batch_state['status'] = status
                write_json(state_path, state)
            while status in ACTIVE_STATUSES:
                if time.monotonic() >= deadline:
                    batch_state['status'] = status
                    state['status'] = 'timed-out'
                    write_json(state_path, state)
                    raise SpokenBriefError(
                        f'Spoken brief deadline reached while {identifier} remained {status}; the project was not repeated'
                    )
                time.sleep(poll_seconds)
                _confirm_environment(client, state, state_path, manifest)
                project = client.get_json(f'/api/production/{identifier}')
                _adopt_project(project, identifier, batch, speaker_id, batch_state, state, state_path)
                status = project.get('state', {}).get('status')
                batch_state['status'] = status
                write_json(state_path, state)
            if status != 'completed':
                message = project.get('state', {}).get('message') or f'Voice project ended as {status}'
                batch_state['status'] = status
                state['status'] = 'blocked'
                write_json(state_path, state)
                raise SpokenBriefError(message + '; no replacement voice project was created')
            _confirm_environment(client, state, state_path, manifest)
            _adopt_project(project, identifier, batch, speaker_id, batch_state, state, state_path)
            segment_dir = run_dir / 'segments'
            segment_dir.mkdir(exist_ok=True)
            for line in batch:
                artifact = artifact_for(project, line['id'], identifier)
                target = segment_dir / (line['id'] + '.wav')
                if not target.is_file() or digest_file(target) != artifact['sha256']:
                    _confirm_environment(client, state, state_path, manifest)
                    raw = client.get_bytes(artifact['url'])
                    if digest_bytes(raw) != artifact['sha256']:
                        raise SpokenBriefError(f'Downloaded voice artifact changed for {line["id"]}')
                    temporary = target.with_name(target.name + '.tmp')
                    temporary.write_bytes(raw)
                    temporary.replace(target)
                _wav_details(target)
                batch_state['artifacts'][line['id']] = {
                    'path': str(target),
                    'sha256': artifact['sha256'],
                    'source_url': artifact['url'],
                }
                segment_files[line['id']] = target
                segment_hashes[line['id']] = artifact['sha256']
            batch_state['status'] = 'completed'
            write_json(state_path, state)
        missing = [
            segment['id'] for segment in manifest['segments']
            if segment['id'] not in segment_files or segment['id'] not in segment_hashes
        ]
        if missing:
            raise SpokenBriefError('Completed Voice projects did not yield every compiled segment')
        _confirm_environment(client, state, state_path, manifest)
        entries = [
            {
                'id': segment['id'],
                'path': segment_files[segment['id']],
                'expected_sha256': segment_hashes[segment['id']],
                'pause_after_ms': segment['pause_after_ms'],
            }
            for segment in manifest['segments']
        ]
        output_receipt = assemble_wav(entries, output)
        try:
            verify_source(manifest)
        except SpokenBriefError as exc:
            output.unlink(missing_ok=True)
            state['status'] = 'source-changed'
            state['last_error'] = str(exc)
            write_json(state_path, state)
            raise
        projects = [batch['project_id'] for batch in state['batches']]
        project_plans = [
            {'id': batch['project_id'], 'sha256': batch['project_plan_sha256']}
            for batch in state['batches']
        ]
        receipt = {
            'schema_version': SCHEMA_VERSION,
            'manifest_sha256': manifest['manifest_sha256'],
            'source': manifest['source'],
            'speaker_id': speaker_id,
            'studio': state['studio'] or identity_record,
            'producer_sha256': state['producer_sha256'],
            'projects': projects,
            'project_plans': project_plans,
            'segments': [
                {
                    'id': item['id'],
                    'text_sha256': item['text_sha256'],
                    'pause_after_ms': item['pause_after_ms'],
                }
                for item in manifest['segments']
            ],
            'output': output_receipt,
        }
        write_json(receipt_path, receipt)
        state.update(status='completed', output=output_receipt)
        write_json(state_path, state)
        return {'output': str(output), 'receipt': str(receipt_path), 'projects': projects, 'reused': False}
    finally:
        release_run_claim(claim)


def plan(pack, *, speaker_id='brief-narrator') -> dict:
    source = resolve_source(pack)
    manifest = compile_source(source, speaker_id=speaker_id)
    directory = run_directory(source, manifest['manifest_sha256'])
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'manifest.json'
    write_json(path, manifest)
    return {
        'manifest': str(path),
        'segments': len(manifest['segments']),
        'batches': len(batch_segments(manifest['segments'])),
        'source': str(source),
        'generation_submitted': False,
    }
