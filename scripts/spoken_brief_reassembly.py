"""Append a self-contained replacement archive without synthesizing any audio."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import tempfile

from spoken_brief_archive import MAX_MASTER_BYTES, checked_directory, checked_json, file_record, inspect_run
from spoken_brief_compile import SpokenBriefError, canonical_digest, digest_bytes
from spoken_brief_exports import _claim, _new_file
from spoken_brief_inbox import _capture, _lineage
from spoken_brief_replacement import _load, _snapshot, _take
from spoken_brief_transport import MAX_AUDIO_BYTES, MAX_JSON_BYTES, _sync_parent, assemble_wav, write_json

MAX_REVISION_BYTES = 2 * MAX_MASTER_BYTES


def _manifest(parent, request, state):
    manifest = copy.deepcopy(parent)
    target = next(s for s in manifest['segments'] if s['id'] == request['segment_id'])
    target.update(text=request['text'], text_sha256=request['text_sha256'])
    manifest['replacement'] = {'request_sha256': request['request_sha256'],
        'parent_manifest_sha256': request['archive']['manifest_sha256'], 'parent_master_sha256': request['archive']['master_sha256'],
        'segment_id': request['segment_id'], 'previous_audio_sha256': request['old_audio_sha256'],
        'audio_sha256': state['artifact']['sha256'], 'project_id': state['project_id'], 'review_sha256': request['review_sha256']}
    manifest['manifest_sha256'] = canonical_digest({k: v for k, v in manifest.items() if k != 'manifest_sha256'})
    return manifest


def _proof(directory, archive, request, state, manifest, master_sha):
    value = {'schema_version': 1, 'kind': 'spoken-brief-reassembly', 'parent_directory': str(directory),
        'request': request, 'child': {'id': state['project_id'], 'plan': state['project_plan'], 'artifact': state['artifact']},
        'reused_segments': [{'id': s['id'], 'audio_sha256': s['audio_sha256']} for s in archive['segments'] if s['id'] != request['segment_id']],
        'manifest_sha256': manifest['manifest_sha256'], 'master_sha256': master_sha}
    value['proof_sha256'] = canonical_digest(value)
    return value


def _output(result, archive, request, state, master_sha):
    inputs = []
    for s in archive['segments']:
        replacement = s['id'] == request['segment_id']
        inputs.append({'id': s['id'], 'path': str(result / 'segments' / (s['id'] + '.wav')),
            'sha256': state['artifact']['sha256'] if replacement else s['audio_sha256'],
            'samples': state['artifact']['samples'] if replacement else s['samples'], 'pause_after_ms': s['pause_after_ms']})
    samples = sum(x['samples'] + x['pause_after_ms'] * 48 for x in inputs)
    if samples * 2 + 44 > MAX_MASTER_BYTES: raise SpokenBriefError('Replacement revision exceeds the master WAV byte budget')
    return {'path': str(result / (Path(archive['source']['name']).stem + '.spoken.wav')), 'sha256': master_sha,
        'samples': samples, 'duration_seconds': samples / 48000, 'format': 'wav-pcm-s16le-mono-48000', 'inputs': inputs}


def _receipt(parent, manifest, state, output, proof):
    receipt = copy.deepcopy(parent)
    receipt.update(manifest_sha256=manifest['manifest_sha256'],
        projects=[*parent['projects'], state['project_id']],
        project_plans=[*parent['project_plans'], {'id': state['project_id'], 'sha256': state['project_plan']['sha256']}],
        segments=[{k: s[k] for k in ('id', 'text_sha256', 'pause_after_ms')} for s in manifest['segments']],
        output=output, replacement_proof_sha256=proof['proof_sha256'])
    return receipt


def _verify(result, directory, archive, request, state, manifest, parent_receipt):
    updated = inspect_run(result)
    retained_manifest, _ = checked_json(result / 'manifest.json')
    proof = _proof(directory, archive, request, state, manifest, updated['master']['sha256'])
    output = _output(result, archive, request, state, updated['master']['sha256'])
    expected_receipt = _receipt(parent_receipt, manifest, state, output, proof)
    if (canonical_digest(retained_manifest) != canonical_digest(manifest)
            or canonical_digest(checked_json(result / 'replacement.json')[0]) != canonical_digest(proof)
            or canonical_digest(checked_json(result / 'receipt.json')[0]) != canonical_digest(expected_receipt)):
        raise SpokenBriefError('Replacement archive, lineage or receipt differs from the retained request/take')
    return updated


def assemble(run_dir, request_id):
    """Pure media assembly: only the already verified replacement take is admitted.

    A new independent archive is atomically published, never selected as accepted.
    Parent media, exports, machine reports and listening judgements are untouched.
    """
    directory = checked_directory(run_dir); archive = inspect_run(directory)
    path, request, state, request_token, state_token = _load(directory, archive, request_id)
    if state['status'] != 'artifact-verified': raise SpokenBriefError('A verified replacement take is required; assembly never starts TTS')
    _take(path, state)
    parent_manifest, _ = checked_json(directory / 'manifest.json'); parent_receipt, _ = checked_json(directory / 'receipt.json')
    manifest = _manifest(parent_manifest, request, state); result = path / 'result'
    _output(result, archive, request, state, '0' * 64)  # Check the actual sample budget before any staging writes.
    if os.path.lexists(result):
        _verify(result, directory, archive, request, state, manifest, parent_receipt)
        return {'directory': str(result), 'manifest_sha256': manifest['manifest_sha256'], 'reused': True}
    stage = None; stage_lineage = None
    try:
        with _claim(directory, archive['manifest_sha256']) as verify_claim:
            def guard():
                verify_claim()
                if (_snapshot(path / 'request.json')[1] != request_token or _snapshot(path / 'state.json')[1] != state_token
                        or inspect_run(directory) != archive):
                    raise SpokenBriefError('Parent, request or retained take state changed during reassembly')
                _take(path, state)
            guard()
            if os.path.lexists(result): raise SpokenBriefError('Result appeared while acquiring the run claim')
            stage = Path(tempfile.mkdtemp(prefix='.assemble-', dir=path)); stage_lineage = _lineage(stage)
            (stage / 'segments').mkdir(); entries = []
            used_bytes = _output(result, archive, request, state, '0' * 64)['samples'] * 2 + 44
            for s in archive['segments']:
                replacing = s['id'] == request['segment_id']
                raw = _take(path, state) if replacing else _capture(directory / 'segments' / (s['id'] + '.wav'), MAX_AUDIO_BYTES)[0]
                expected = state['artifact']['sha256'] if replacing else s['audio_sha256']
                if digest_bytes(raw) != expected: raise SpokenBriefError('Carried segment changed before reassembly')
                used_bytes += len(raw)
                if used_bytes > MAX_REVISION_BYTES: raise SpokenBriefError('Replacement staging byte budget exceeded')
                target = stage / 'segments' / (s['id'] + '.wav'); _new_file(target, raw)
                entries.append({'id': s['id'], 'path': target, 'pause_after_ms': s['pause_after_ms'], 'expected_sha256': expected})
            output = assemble_wav(entries, stage / (Path(archive['source']['name']).stem + '.spoken.wav'))
            proof = _proof(directory, archive, request, state, manifest, output['sha256'])
            write_json(stage / 'manifest.json', manifest); write_json(stage / 'replacement.json', proof)
            write_json(stage / 'receipt.json', _receipt(parent_receipt, manifest, state, output, proof))
            _verify(stage, directory, archive, request, state, manifest, parent_receipt)
            # Validate using the physical staging layout first, then bind the
            # final receipt paths before the single directory publication.
            final_output = _output(result, archive, request, state, output['sha256'])
            final_receipt = _receipt(parent_receipt, manifest, state, final_output, proof)
            write_json(stage / 'receipt.json', final_receipt)
            names = ['manifest.json', 'receipt.json', 'replacement.json', Path(output['path']).name]
            names += ['segments/' + s['id'] + '.wav' for s in archive['segments']]
            expected_hashes = {name: digest_bytes((json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))
                for name, value in [('manifest.json', manifest), ('receipt.json', final_receipt), ('replacement.json', proof)]}
            expected_hashes[Path(output['path']).name] = output['sha256']
            expected_hashes.update({'segments/' + x['id'] + '.wav': x['sha256'] for x in final_output['inputs']})
            snapshots = {name: file_record(stage / name, MAX_MASTER_BYTES) for name in names}
            if any(snapshots[name]['sha256'] != expected for name, expected in expected_hashes.items()):
                raise SpokenBriefError('Final staged files differ from the previously verified assembly')
            if (canonical_digest(checked_json(stage / 'receipt.json')[0]) != canonical_digest(final_receipt)
                    or canonical_digest(checked_json(stage / 'manifest.json')[0]) != canonical_digest(manifest)
                    or canonical_digest(checked_json(stage / 'replacement.json')[0]) != canonical_digest(proof)):
                raise SpokenBriefError('Final staged replacement metadata changed')
            for name in names:
                with (stage / name).open('r+b') as stream: os.fsync(stream.fileno())
            for name, snapshot in snapshots.items():
                if file_record(stage / name, MAX_MASTER_BYTES) != snapshot: raise SpokenBriefError('Staged revision changed during flush')
            guard()
            if _lineage(stage) != stage_lineage or os.path.lexists(result): raise SpokenBriefError('Replacement staging/destination changed')
            os.rename(stage, result); stage = None; _sync_parent(result)
            _verify(result, directory, archive, request, state, manifest, parent_receipt)
            return {'directory': str(result), 'manifest_sha256': manifest['manifest_sha256'], 'reused': False}
    except OSError as exc: raise SpokenBriefError(f'Cannot publish replacement archive: {exc}') from exc
    finally:
        if stage is not None and _lineage(stage) == stage_lineage: shutil.rmtree(stage)
