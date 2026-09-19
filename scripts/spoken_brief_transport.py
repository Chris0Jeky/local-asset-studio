"""Durable state, loopback transport, artifact verification and PCM assembly."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import wave

from spoken_brief_compile import *

MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_AUDIO_BYTES = 32 * 1024 * 1024
MAX_ERROR_BYTES = 64 * 1024
HEX_64 = re.compile(r'[0-9a-f]{64}\Z')
PROJECT_ID = re.compile(r'[0-9a-f]{32}\Z')


def normalize_loopback_url(base_url) -> str:
    parsed = urlsplit(str(base_url))
    try:
        port = parsed.port
    except ValueError as exc:
        raise SpokenBriefError('Studio URL must use a valid loopback port') from exc
    host = parsed.hostname.lower() if isinstance(parsed.hostname, str) else None
    if (parsed.scheme != 'http' or host not in ('127.0.0.1', 'localhost')
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise SpokenBriefError('Studio URL must be an HTTP loopback URL')
    if parsed.path not in ('', '/'):
        raise SpokenBriefError('Studio URL must not contain a path')
    expected_netloc = host if port is None else f'{host}:{port}'
    if parsed.netloc.lower() != expected_netloc:
        raise SpokenBriefError('Studio URL must use a valid loopback port')
    return f'http://{expected_netloc}'


def validate_studio_record(record: dict) -> dict:
    if not isinstance(record, dict) or not isinstance(record.get('base_url'), str):
        raise SpokenBriefError('Retained Studio provenance is invalid')
    if normalize_loopback_url(record['base_url']) != record['base_url']:
        raise SpokenBriefError('Retained Studio endpoint is not canonical')
    identity = record.get('identity')
    if (not isinstance(identity, dict) or identity.get('app') != 'local-asset-studio'
            or not isinstance(identity.get('workspace'), str) or not identity['workspace']
            or not isinstance(identity.get('version'), str) or not identity['version']):
        raise SpokenBriefError('Retained Studio workspace identity is invalid')
    return record


def studio_record(base_url: str, identity: dict) -> dict:
    record = {'base_url': normalize_loopback_url(base_url), 'identity': identity}
    validate_studio_record(record)
    return record


def initial_state(manifest: dict) -> dict:
    batches = batch_segments(manifest['segments'])
    return {
        'schema_version': SCHEMA_VERSION,
        'manifest_sha256': manifest['manifest_sha256'],
        'status': 'planned',
        'studio': None,
        'producer_sha256': None,
        'batches': [
            {
                'id': f'batch-{index:03d}',
                'line_ids': [line['id'] for line in batch],
                'project_id': None,
                'project_plan_sha256': None,
                'status': 'pending',
                'artifacts': {},
            }
            for index, batch in enumerate(batches, 1)
        ],
    }


def validate_state(state: dict, manifest: dict, batches: list[list[dict]]) -> None:
    if not isinstance(state, dict) or state.get('schema_version') != SCHEMA_VERSION:
        raise SpokenBriefError('Retained state has an unsupported schema')
    if state.get('manifest_sha256') != manifest['manifest_sha256']:
        raise SpokenBriefError('Retained state belongs to another spoken-brief manifest')
    if not isinstance(state.get('status'), str):
        raise SpokenBriefError('Retained state has an invalid aggregate status')
    studio = state.get('studio')
    if studio is not None:
        validate_studio_record(studio)
    producer_sha256 = state.get('producer_sha256')
    if producer_sha256 is not None and not HEX_64.fullmatch(str(producer_sha256)):
        raise SpokenBriefError('Retained state has an invalid producer hash')
    retained = state.get('batches')
    if not isinstance(retained, list) or len(retained) != len(batches):
        raise SpokenBriefError('Retained state does not match the compiled batch plan')
    has_project = False
    for index, (batch_state, batch) in enumerate(zip(retained, batches), 1):
        expected_ids = [line['id'] for line in batch]
        if (not isinstance(batch_state, dict) or batch_state.get('id') != f'batch-{index:03d}'
                or batch_state.get('line_ids') != expected_ids):
            raise SpokenBriefError('Retained state does not match the compiled batch plan')
        project_id = batch_state.get('project_id')
        status = batch_state.get('status')
        if not isinstance(status, str):
            raise SpokenBriefError('Retained state has an invalid batch status')
        if project_id is not None and (not isinstance(project_id, str) or not PROJECT_ID.fullmatch(project_id)):
            raise SpokenBriefError('Retained state has an invalid voice project identity')
        if project_id is None and status not in ('pending', 'creating', 'create-unconfirmed'):
            raise SpokenBriefError('Retained state lost the voice project identity for a non-pending batch')
        plan_sha256 = batch_state.get('project_plan_sha256')
        if plan_sha256 is not None and not HEX_64.fullmatch(str(plan_sha256)):
            raise SpokenBriefError('Retained state has an invalid project plan hash')
        if project_id is None and plan_sha256 is not None:
            raise SpokenBriefError('Retained state has project plan provenance without a project identity')
        has_project = has_project or project_id is not None
        if not isinstance(batch_state.get('artifacts'), dict):
            raise SpokenBriefError('Retained state has an invalid artifact record')
    if has_project and studio is None:
        raise SpokenBriefError('Retained child projects have no Studio identity provenance')


def production_digest(value) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')
    except (TypeError, ValueError, RecursionError) as exc:
        raise SpokenBriefError('Voice project plan is not canonical JSON') from exc
    return digest_bytes(raw)


def project_provenance(plan: dict) -> dict:
    if not isinstance(plan, dict) or plan.get('kind') != 'voice':
        raise SpokenBriefError('Voice project has an invalid retained plan')
    claimed = plan.get('sha256')
    if not isinstance(claimed, str) or not HEX_64.fullmatch(claimed):
        raise SpokenBriefError('Voice project plan fingerprint is missing or invalid')
    unsigned = {key: value for key, value in plan.items() if key != 'sha256'}
    if production_digest(unsigned) != claimed:
        raise SpokenBriefError('Voice project plan fingerprint is invalid')
    producer = {
        key: value for key, value in unsigned.items()
        if key not in ('name', 'lines', 'created_at')
    }
    return {'project_plan_sha256': claimed, 'producer_sha256': production_digest(producer)}


def verify_project(project: dict, identifier: str, batch: list[dict], speaker_id: str,
                   *, expected_plan_sha256: str | None = None) -> dict:
    if not isinstance(project, dict) or project.get('id') != identifier or project.get('kind') != 'voice':
        raise SpokenBriefError(f'Retained project {identifier} is not the expected Voice baseline project')
    plan = project.get('plan')
    expected_lines = [{'id': line['id'], 'text': line['text']} for line in batch]
    if (not isinstance(plan, dict) or plan.get('speaker_id') != speaker_id
            or plan.get('lines') != expected_lines):
        raise SpokenBriefError(f'Retained voice project {identifier} does not match this spoken-brief batch')
    provenance = project_provenance(plan)
    if expected_plan_sha256 is not None and provenance['project_plan_sha256'] != expected_plan_sha256:
        raise SpokenBriefError(f'Retained voice project {identifier} plan changed after it was adopted')
    return provenance


def _sync_parent(path: Path) -> None:
    if os.name == 'nt' or not hasattr(os, 'O_DIRECTORY'):
        return
    try:
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_json(path: Path, value) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        raw = (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
    except (TypeError, ValueError, RecursionError) as exc:
        raise SpokenBriefError(f'Cannot serialize spoken-brief state: {path}') from exc
    descriptor, temporary_name = tempfile.mkstemp(prefix=f'.{path.name}-', suffix='.tmp', dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _sync_parent(path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def read_json(path: Path):
    path = Path(path)
    try:
        if not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
            raise OSError('missing or oversized state')
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
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
        self.base_url = normalize_loopback_url(base_url)
        if not isinstance(timeout, (int, float)) or not 0 < timeout <= 300:
            raise SpokenBriefError('Studio timeout must be greater than zero and at most 300 seconds')
        self.timeout = timeout
        self.opener = build_opener(ProxyHandler({}), _NoRedirect())

    def _request(self, method, path, payload=None):
        if not isinstance(path, str) or not path.startswith('/') or path.startswith('//'):
            raise SpokenBriefError('Studio request path must be relative to the pinned loopback origin')
        data = None
        headers = {'Accept': 'application/json'}
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
            try:
                decoded = json.loads(raw.decode('utf-8'))
                message = decoded.get('error') if isinstance(decoded, dict) else None
            except Exception:
                message = None
            error = StudioRejected if 400 <= exc.code < 500 else SpokenBriefError
            raise error(message or f'Studio returned HTTP {exc.code} for {path}') from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise SpokenBriefError(f'Studio request did not complete for {path}: {exc}') from exc
        try:
            value = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SpokenBriefError(f'Studio returned invalid JSON for {path}') from exc
        if not isinstance(value, dict):
            raise SpokenBriefError(f'Studio returned a non-object JSON response for {path}; expected a JSON object')
        return value

    def get_json(self, path):
        return self._request('GET', path)

    def post_json(self, path, payload):
        return self._request('POST', path, payload)

    def get_bytes(self, path):
        if not isinstance(path, str) or not path.startswith('/') or path.startswith('//'):
            raise SpokenBriefError('Voice artifact path must stay on the pinned loopback origin')
        request = Request(self.base_url + path, headers={'Accept': 'audio/wav'}, method='GET')
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                return _read_limited(response, MAX_AUDIO_BYTES, 'Voice artifact')
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise SpokenBriefError(f'Cannot download retained voice artifact {path}: {exc}') from exc


def _wav_details(path: Path) -> dict:
    try:
        with wave.open(str(path), 'rb') as source:
            details = {
                'channels': source.getnchannels(),
                'sample_width': source.getsampwidth(),
                'sample_rate': source.getframerate(),
                'samples': source.getnframes(),
                'compression': source.getcomptype(),
            }
    except (OSError, EOFError, wave.Error) as exc:
        raise SpokenBriefError(f'Invalid WAV artifact: {path}') from exc
    if (details['channels'] != 1 or details['sample_width'] != 2
            or details['sample_rate'] != 48000 or details['compression'] != 'NONE'):
        raise SpokenBriefError('Spoken brief assembly requires 48 kHz mono PCM16 scene WAVs')
    return details


def assemble_wav(entries: list[dict], output: Path) -> dict:
    if not entries:
        raise SpokenBriefError('No voice segments are available to assemble')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f'.{output.name}-', suffix='.tmp', dir=output.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    samples = 0
    input_receipts = []
    try:
        with wave.open(str(temporary), 'wb') as joined:
            joined.setparams((1, 2, 48000, 0, 'NONE', ''))
            for entry in entries:
                path = Path(entry['path'])
                details = _wav_details(path)
                with wave.open(str(path), 'rb') as source:
                    raw = source.readframes(source.getnframes())
                joined.writeframesraw(raw)
                samples += details['samples']
                pause_ms = entry.get('pause_after_ms', 0)
                if type(pause_ms) is not int or not 0 <= pause_ms <= 5000:
                    raise SpokenBriefError('Segment pause must be an integer from 0 to 5000 ms')
                silence = round(48000 * pause_ms / 1000)
                if silence:
                    joined.writeframesraw(b'\0\0' * silence)
                    samples += silence
                input_receipts.append({
                    'id': entry['id'],
                    'path': str(path),
                    'sha256': digest_bytes(path.read_bytes()),
                    'samples': details['samples'],
                    'pause_after_ms': pause_ms,
                })
        with temporary.open('r+b') as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, output)
        _sync_parent(output)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return {
        'path': str(output),
        'sha256': digest_bytes(output.read_bytes()),
        'samples': samples,
        'duration_seconds': samples / 48000,
        'format': 'wav-pcm-s16le-mono-48000',
        'inputs': input_receipts,
    }


def _project_name(source: Path, manifest_sha256: str, index: int, total: int) -> str:
    stem = re.sub(r'\s+', ' ', source.stem).strip()[:60] or 'brief'
    return f'Spoken brief · {stem} · {manifest_sha256[:8]} · {index}/{total}'[:120]


def artifact_for(project: dict, segment_id: str, project_id: str) -> dict:
    matches = [
        item for item in project.get('state', {}).get('artifacts', [])
        if isinstance(item, dict) and item.get('role') == 'audio'
        and str(item.get('path', '')).endswith('/' + segment_id + '-scene.wav')
    ]
    if len(matches) != 1:
        raise SpokenBriefError(f'Completed voice project does not expose one scene WAV for {segment_id}')
    artifact = matches[0]
    relative = artifact.get('path')
    expected_relative = f'voice/{segment_id}-scene.wav'
    url = artifact.get('url')
    parsed = urlsplit(url) if isinstance(url, str) else None
    expected = f'/api/production/{project_id}/files/{expected_relative}'
    if (relative != expected_relative or parsed is None or parsed.scheme or parsed.netloc
            or parsed.query or parsed.fragment or parsed.path != expected):
        raise SpokenBriefError(f'Voice artifact route escapes project {project_id} or does not match its retained path')
    if not HEX_64.fullmatch(str(artifact.get('sha256', ''))):
        raise SpokenBriefError(f'Voice artifact receipt is incomplete for {segment_id}')
    return artifact


def acquire_run_claim(run_dir: Path, manifest_sha256: str) -> Path:
    lock = Path(run_dir) / '.spoken-brief.lock'
    payload = json.dumps({
        'pid': os.getpid(),
        'manifest_sha256': manifest_sha256,
        'claimed_at': time.time(),
    }).encode('utf-8')
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise SpokenBriefError(
            f'A spoken-brief coordinator is already active, or left a stale claim at {lock}. Inspect it before removal.'
        ) from exc
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        _sync_parent(lock)
    except Exception:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass
        raise
    return lock


def release_run_claim(lock: Path) -> None:
    try:
        Path(lock).unlink()
        _sync_parent(Path(lock))
    except FileNotFoundError:
        pass


def _completed_result(receipt_path: Path, manifest_sha256: str, expected_output: Path):
    if not receipt_path.is_file():
        return None
    receipt = read_json(receipt_path)
    if receipt.get('manifest_sha256') != manifest_sha256:
        raise SpokenBriefError('Completed receipt belongs to another spoken-brief manifest')
    record = receipt.get('output')
    if (not isinstance(record, dict) or not isinstance(record.get('path'), str)
            or not HEX_64.fullmatch(str(record.get('sha256', '')))):
        raise SpokenBriefError('Completed receipt has an invalid output record')
    output = Path(record['path']).resolve()
    expected = Path(expected_output).resolve()
    if output != expected:
        raise SpokenBriefError('Completed receipt output escapes its spoken-brief run directory')
    if not output.is_file():
        return None
    if digest_bytes(output.read_bytes()) != record['sha256']:
        raise SpokenBriefError('Completed receipt output hash no longer matches the retained WAV')
    projects = receipt.get('projects')
    if (not isinstance(projects, list) or not projects
            or any(not isinstance(item, str) or not PROJECT_ID.fullmatch(item) for item in projects)):
        raise SpokenBriefError('Completed receipt has invalid Voice project identities')
    project_plans = receipt.get('project_plans')
    if (not isinstance(project_plans, list) or len(project_plans) != len(projects)
            or any(not isinstance(item, dict) or set(item) != {'id', 'sha256'}
                   or item.get('id') != projects[index]
                   or not HEX_64.fullmatch(str(item.get('sha256', '')))
                   for index, item in enumerate(project_plans))):
        raise SpokenBriefError('Completed receipt has invalid project plan provenance')
    if not HEX_64.fullmatch(str(receipt.get('producer_sha256', ''))):
        raise SpokenBriefError('Completed receipt has invalid producer provenance')
    validate_studio_record(receipt.get('studio'))
    if receipt.get('schema_version') != SCHEMA_VERSION:
        raise SpokenBriefError('Completed receipt has an unsupported schema')
    return {'output': str(output), 'receipt': str(receipt_path), 'projects': projects, 'reused': True}
