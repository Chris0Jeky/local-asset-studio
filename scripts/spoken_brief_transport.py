"""Durable state, loopback transport, artifact verification and PCM assembly."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import wave

from spoken_brief_compile import *

MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_AUDIO_BYTES = 32 * 1024 * 1024
MAX_ERROR_BYTES = 64 * 1024

def initial_state(manifest: dict) -> dict:
    batches = batch_segments(manifest['segments'])
    return {'schema_version': SCHEMA_VERSION, 'manifest_sha256': manifest['manifest_sha256'],
            'status': 'planned', 'batches': [
                {'id': f'batch-{index:03d}', 'line_ids': [line['id'] for line in batch],
                 'project_id': None, 'status': 'pending', 'artifacts': {}}
                for index, batch in enumerate(batches, 1)]}


def validate_state(state: dict, manifest: dict, batches: list[list[dict]]) -> None:
    if not isinstance(state, dict) or state.get('schema_version') != SCHEMA_VERSION:
        raise SpokenBriefError('Retained state has an unsupported schema')
    if state.get('manifest_sha256') != manifest['manifest_sha256']:
        raise SpokenBriefError('Retained state belongs to another spoken-brief manifest')
    retained = state.get('batches')
    if not isinstance(retained, list) or len(retained) != len(batches):
        raise SpokenBriefError('Retained state does not match the compiled batch plan')
    for index, (batch_state, batch) in enumerate(zip(retained, batches), 1):
        expected_ids = [line['id'] for line in batch]
        if not isinstance(batch_state, dict) or batch_state.get('id') != f'batch-{index:03d}' or batch_state.get('line_ids') != expected_ids:
            raise SpokenBriefError('Retained state does not match the compiled batch plan')
        project_id = batch_state.get('project_id'); status = batch_state.get('status')
        if not isinstance(status, str):
            raise SpokenBriefError('Retained state has an invalid batch status')
        if project_id is not None and (not isinstance(project_id, str) or not re.fullmatch(r'[0-9a-f]{32}', project_id)):
            raise SpokenBriefError('Retained state has an invalid voice project identity')
        if project_id is None and status not in ('pending', 'creating', 'create-unconfirmed'):
            raise SpokenBriefError('Retained state lost the voice project identity for a non-pending batch')
        if not isinstance(batch_state.get('artifacts'), dict):
            raise SpokenBriefError('Retained state has an invalid artifact record')


def verify_project(project: dict, identifier: str, batch: list[dict], speaker_id: str) -> None:
    if not isinstance(project, dict) or project.get('id') != identifier or project.get('kind') != 'voice':
        raise SpokenBriefError(f'Retained project {identifier} is not the expected Voice baseline project')
    plan = project.get('plan')
    expected_lines = [{'id': line['id'], 'text': line['text']} for line in batch]
    if not isinstance(plan, dict) or plan.get('speaker_id') != speaker_id or plan.get('lines') != expected_lines:
        raise SpokenBriefError(f'Retained voice project {identifier} does not match this spoken-brief batch')


def write_json(path: Path, value) -> None:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def read_json(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpokenBriefError(f'Cannot read retained spoken-brief state: {path}') from exc


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def _read_limited(response, maximum: int, label: str) -> bytes:
    raw = response.read(maximum + 1)
    if len(raw) > maximum:
        raise SpokenBriefError(f'{label} exceeded the {maximum}-byte local response limit')
    return raw


class StudioClient:
    def __init__(self, base_url='http://127.0.0.1:8191', timeout=30):
        parsed = urlsplit(str(base_url))
        if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise SpokenBriefError('Studio URL must be an HTTP loopback URL')
        if parsed.path not in ('', '/'):
            raise SpokenBriefError('Studio URL must not contain a path')
        self.base_url = f'http://{parsed.netloc}'.rstrip('/')
        self.timeout = timeout
        self.opener = build_opener(ProxyHandler({}), _NoRedirect())

    def _request(self, method, path, payload=None):
        data = None; headers = {'Accept': 'application/json'}
        if payload is not None:
            data = json.dumps(payload).encode('utf-8')
            headers.update({'Content-Type': 'application/json', 'Origin': self.base_url})
        request = Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = _read_limited(response, MAX_JSON_BYTES, 'Studio JSON')
        except HTTPError as exc:
            raw = exc.read(MAX_ERROR_BYTES + 1)
            if len(raw) > MAX_ERROR_BYTES:
                raw = b''
            try: message = json.loads(raw.decode('utf-8')).get('error')
            except Exception: message = None
            error = StudioRejected if 400 <= exc.code < 500 else SpokenBriefError
            raise error(message or f'Studio returned HTTP {exc.code} for {path}') from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise SpokenBriefError(f'Studio request did not complete for {path}: {exc}') from exc
        try:
            return json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SpokenBriefError(f'Studio returned invalid JSON for {path}') from exc

    def get_json(self, path): return self._request('GET', path)
    def post_json(self, path, payload): return self._request('POST', path, payload)

    def get_bytes(self, path):
        request = Request(self.base_url + path, headers={'Accept': 'audio/wav'}, method='GET')
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                return _read_limited(response, MAX_AUDIO_BYTES, 'Voice artifact')
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise SpokenBriefError(f'Cannot download retained voice artifact {path}: {exc}') from exc


def _wav_details(path: Path) -> dict:
    try:
        with wave.open(str(path), 'rb') as source:
            details = {'channels': source.getnchannels(), 'sample_width': source.getsampwidth(),
                       'sample_rate': source.getframerate(), 'samples': source.getnframes(),
                       'compression': source.getcomptype()}
    except (OSError, EOFError, wave.Error) as exc:
        raise SpokenBriefError(f'Invalid WAV artifact: {path}') from exc
    if details['channels'] != 1 or details['sample_width'] != 2 or details['sample_rate'] != 48000 or details['compression'] != 'NONE':
        raise SpokenBriefError('Spoken brief assembly requires 48 kHz mono PCM16 scene WAVs')
    return details


def assemble_wav(entries: list[dict], output: Path) -> dict:
    if not entries:
        raise SpokenBriefError('No voice segments are available to assemble')
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + '.tmp')
    samples = 0; input_receipts = []
    with wave.open(str(temporary), 'wb') as joined:
        joined.setparams((1, 2, 48000, 0, 'NONE', ''))
        for entry in entries:
            path = Path(entry['path']); details = _wav_details(path)
            with wave.open(str(path), 'rb') as source:
                raw = source.readframes(source.getnframes())
            joined.writeframesraw(raw); samples += details['samples']
            pause_ms = entry.get('pause_after_ms', 0)
            if type(pause_ms) is not int or not 0 <= pause_ms <= 5000:
                raise SpokenBriefError('Segment pause must be an integer from 0 to 5000 ms')
            silence = round(48000 * pause_ms / 1000)
            if silence:
                joined.writeframesraw(b'\0\0' * silence); samples += silence
            input_receipts.append({'id': entry['id'], 'path': str(path), 'sha256': digest_bytes(path.read_bytes()),
                                   'samples': details['samples'], 'pause_after_ms': pause_ms})
    temporary.replace(output)
    return {'path': str(output), 'sha256': digest_bytes(output.read_bytes()), 'samples': samples,
            'duration_seconds': samples / 48000, 'format': 'wav-pcm-s16le-mono-48000', 'inputs': input_receipts}


def _project_name(source: Path, manifest_sha256: str, index: int, total: int) -> str:
    stem = re.sub(r'\s+', ' ', source.stem).strip()[:60] or 'brief'
    return f'Spoken brief · {stem} · {manifest_sha256[:8]} · {index}/{total}'[:120]


def artifact_for(project: dict, segment_id: str, project_id: str) -> dict:
    matches = [item for item in project.get('state', {}).get('artifacts', [])
               if isinstance(item, dict) and item.get('role') == 'audio'
               and str(item.get('path', '')).endswith('/' + segment_id + '-scene.wav')]
    if len(matches) != 1:
        raise SpokenBriefError(f'Completed voice project does not expose one scene WAV for {segment_id}')
    artifact = matches[0]
    relative = artifact.get('path')
    expected_relative = f'voice/{segment_id}-scene.wav'
    url = artifact.get('url'); parsed = urlsplit(url) if isinstance(url, str) else None
    expected = f'/api/production/{project_id}/files/{expected_relative}'
    if relative != expected_relative or parsed is None or parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or parsed.path != expected:
        raise SpokenBriefError(f'Voice artifact route escapes project {project_id} or does not match its retained path')
    if not re.fullmatch(r'[0-9a-f]{64}', str(artifact.get('sha256', ''))):
        raise SpokenBriefError(f'Voice artifact receipt is incomplete for {segment_id}')
    return artifact


def acquire_run_claim(run_dir: Path, manifest_sha256: str) -> Path:
    lock = Path(run_dir) / '.spoken-brief.lock'
    payload = json.dumps({'pid': os.getpid(), 'manifest_sha256': manifest_sha256, 'claimed_at': time.time()}).encode('utf-8')
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise SpokenBriefError(f'A spoken-brief coordinator is already active, or left a stale claim at {lock}. Inspect it before removal.') from exc
    try:
        os.write(descriptor, payload)
    finally:
        os.close(descriptor)
    return lock


def release_run_claim(lock: Path) -> None:
    try:
        Path(lock).unlink()
    except FileNotFoundError:
        pass


def _completed_result(receipt_path: Path, manifest_sha256: str, expected_output: Path):
    if not receipt_path.is_file():
        return None
    receipt = read_json(receipt_path)
    if receipt.get('manifest_sha256') != manifest_sha256:
        raise SpokenBriefError('Completed receipt belongs to another spoken-brief manifest')
    record = receipt.get('output')
    if not isinstance(record, dict) or not isinstance(record.get('path'), str) or not re.fullmatch(r'[0-9a-f]{64}', str(record.get('sha256', ''))):
        raise SpokenBriefError('Completed receipt has an invalid output record')
    output = Path(record['path']).resolve(); expected = Path(expected_output).resolve()
    if output != expected:
        raise SpokenBriefError('Completed receipt output escapes its spoken-brief run directory')
    if not output.is_file():
        return None
    if digest_bytes(output.read_bytes()) != record['sha256']:
        raise SpokenBriefError('Completed receipt output hash no longer matches the retained WAV')
    projects = receipt.get('projects')
    if not isinstance(projects, list) or any(not isinstance(item, str) or not re.fullmatch(r'[0-9a-f]{32}', item) for item in projects):
        raise SpokenBriefError('Completed receipt has invalid Voice project identities')
    return {'output': str(output), 'receipt': str(receipt_path), 'projects': projects, 'reused': True}
