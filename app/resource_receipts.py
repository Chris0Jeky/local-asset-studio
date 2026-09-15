"""Offline verification of job_resources v1 sidecars; never execution authority."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat

from backend_contracts import loopback_port
from performance_history import summarize_resource_profile
from studio_workflow.core import decode

DOCUMENT_LIMIT = 256 * 1024
PROFILE_LIMIT = 4 * 1024 * 1024
EVENT_LIMIT = 8192
ARTIFACTS = ('context.json', 'events.jsonl', 'profile.jsonl', 'summary.json')
SCHEMA = 'studio.job-resource-inspection/v1'
_HEX = re.compile(r'[0-9a-f]{64}\Z')
_ID = re.compile(r'[A-Za-z0-9_-]{1,128}\Z')


class EvidenceError(ValueError):
    """Payload-free diagnostic. Incomplete evidence must not be silently repaired."""
    def __init__(self, code: str, *, incomplete: bool = False):
        super().__init__(code)
        self.code, self.incomplete = code, incomplete


def require(condition, code):
    if not condition: raise EvidenceError(code)


def sha256(raw): return hashlib.sha256(raw).hexdigest()
def is_hash(value): return isinstance(value, str) and _HEX.fullmatch(value) is not None
def is_id(value): return isinstance(value, str) and _ID.fullmatch(value) is not None


def _wire(value):
    # job_resources hashes these JSON bytes without the final newline. Do not
    # import that live owner or use Python equality (True == 1) for evidence.
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('utf-8')


def _number(value):
    return type(value) in (int, float) and 0 <= value <= 2**63 - 1 and math.isfinite(value)


def _text(value, limit=256):
    return isinstance(value, str) and 0 < len(value) <= limit and all(ord(c) >= 32 and not 0xd800 <= ord(c) <= 0xdfff for c in value)


def _timestamp(value):
    require(_text(value, 64), 'timestamp_invalid')
    try:
        result = datetime.fromisoformat(value)
        require(result.tzinfo is not None and result.utcoffset() is not None, 'timestamp_invalid')
        return result.astimezone(timezone.utc)
    except (ValueError, OverflowError): raise EvidenceError('timestamp_invalid') from None


def parse_document(raw: bytes):
    """Reuse Studio's strict bounded decoder, without exposing payload errors."""
    try: return decode(raw)
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        raise EvidenceError('invalid_json') from None


def _signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _cross_signature(info):
    # Windows 3.12 path stat can report birth time as ctime while descriptor
    # stat reports change time. Compare ctime only within the same API domain.
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, getattr(info, 'st_birthtime_ns', None)


def _plain(info, kind):
    return kind(info.st_mode) and not (getattr(info, 'st_file_attributes', 0) & 0x400)


def _directories(path):
    for parent in (path, *path.parents):
        require(_plain(parent.lstat(), stat.S_ISDIR), 'directory_not_plain')


class _BoundedRead:
    """Non-seekable consumer view; byte count and real EOF belong to the reader."""
    def __init__(self, stream, limit):
        self.stream, self.limit = stream, limit
        self.count, self.eof = 0, False

    def read(self, count):
        require(type(count) is int and 0 <= count <= 65536, 'stream_read_invalid')
        if count == 0: return b''
        data = self.stream.read(min(count, self.limit - self.count + 1))
        self.count += len(data)
        require(self.count <= self.limit, 'artifact_too_large')
        self.eof = not data
        return data


def _capture_file(path: Path, limit: int, consume=None) -> tuple[object, tuple]:
    """Bound the actual read and bracket one regular file with identity checks.

    This is not a filesystem lease or an OS sandbox against hostile parent races.
    """
    path = Path(path).absolute()
    require('\0' not in str(path), 'input_path_invalid')
    try:
        _directories(path.parent)
        before = path.lstat()
        require(_plain(before, stat.S_ISREG), 'file_not_regular')
        require(before.st_size <= limit, 'artifact_too_large')
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(path, flags)
        try:
            opened = os.fstat(fd)
            require(_plain(opened, stat.S_ISREG) and _cross_signature(opened) == _cross_signature(before), 'file_changed')
            stream = os.fdopen(fd, 'rb'); fd = None
            with stream:
                if consume is None:
                    data = stream.read(limit + 1)
                    count = len(data)
                else:
                    reader = _BoundedRead(stream, limit)
                    data = consume(reader)
                    require(reader.eof, 'artifact_not_consumed')
                    count = reader.count
                after = os.fstat(stream.fileno())
        finally:
            if fd is not None: os.close(fd)
        require(count <= limit, 'artifact_too_large')
        require(_signature(after) == _signature(opened) and _signature(before) == _signature(path.lstat())
                and count == before.st_size, 'file_changed')
        return data, _signature(before)
    except FileNotFoundError: raise EvidenceError('artifact_missing', incomplete=True) from None
    except OSError: raise EvidenceError('artifact_unreadable') from None


def read_evidence_file(path: Path, limit: int) -> bytes:
    """Capture one bounded file; the public byte-reader contract stays unchanged."""
    return _capture_file(path, limit)[0]


def read_evidence_stream(path: Path, limit: int, consume):
    """Run a bounded consumer; return only after EOF and original identity checks."""
    require(callable(consume), 'stream_consumer_invalid')
    return _capture_file(path, limit, consume)[0]


def _context(value, job_id):
    require(isinstance(value, dict) and value.get('schema') == 'studio.job-resource-context/v1'
            and value.get('job_id') == job_id, 'context_invalid')
    for name in ('model_content_identity', 'input_content_identity', 'actual_output_geometry',
                 'precision', 'warmth', 'approval_attestation'):
        require(name in value and value[name] is None, 'context_invalid')
    require(type(value.get('generation_allowance_added')) is int and value['generation_allowance_added'] == 0
            and is_hash(value.get('observer_source_sha256_at_capture')), 'context_invalid')
    limits = value.get('limits')
    require(isinstance(limits, dict) and type(limits.get('samples')) is int and 1 <= limits['samples'] <= 120
            and _number(limits.get('interval_seconds')) and 1 <= limits['interval_seconds'] <= 60
            and type(limits.get('raw_bytes')) is int and limits['raw_bytes'] == PROFILE_LIMIT
            and type(limits.get('events')) is int and limits['events'] == 9
            and type(limits.get('window_seconds')) is int and limits['window_seconds'] == 14460, 'context_invalid')
    source = value.get('source')
    require(isinstance(source, dict) and {'commit_at_capture', 'tracked_changes'} <= set(source), 'context_invalid')
    commit = source.get('commit_at_capture')
    require(commit is None or isinstance(commit, str) and re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', commit), 'context_invalid')
    require(source.get('tracked_changes') is None or type(source['tracked_changes']) is bool, 'context_invalid')
    require('loaded_code_matches_commit' in source and source['loaded_code_matches_commit'] is None
            and source.get('untracked_files_examined') is False, 'context_invalid')
    _timestamp(source.get('captured_at'))
    return {'commit_at_capture': commit, 'tracked_changes': source.get('tracked_changes'),
            'loaded_code_matches_commit': None, 'observer_source_sha256_at_capture': value['observer_source_sha256_at_capture']}


def _events(raw, context, job_id):
    lines = raw.splitlines(keepends=True)
    require(1 <= len(lines) <= 9 and all(len(line) <= EVENT_LIMIT for line in lines), 'event_bounds_invalid')
    records = [parse_document(line) for line in lines]
    require(isinstance(records[0], dict) and records[0].get('event') == 'intent'
            and _wire(records[0]) == _wire(context.get('intent')), 'first_intent_mismatch')
    submissions, finish, previous_time, last_index = [], None, None, -1
    seen_prompts, warnings = set(), []
    first_identity = None
    for event in records:
        require(isinstance(event, dict) and event.get('job_id') == job_id and finish is None, 'event_invalid')
        stamp = _timestamp(event.get('recorded_at'))
        require(previous_time is None or stamp >= previous_time, 'event_order_invalid')
        previous_time = stamp
        kind = event.get('event')
        if kind in ('intent', 'accepted'):
            index = event.get('index')
            require(type(index) is int and 0 <= index < 4, 'event_invalid')
        if kind == 'intent':
            require(index > last_index and event.get('fact') == 'pending_submission_save_returned'
                    and all(is_hash(event.get(k)) for k in ('graph_sha256', 'controls_sha256', 'reference_manifest_sha256')),
                    'event_invalid')
            # No endpoint is contacted or copied into the public report.
            url = event.get('comfy_url')
            try: loopback_port(url)
            except ValueError: raise EvidenceError('event_invalid') from None
            identity = (event['controls_sha256'], event['reference_manifest_sha256'], url)
            require(first_identity is None or identity == first_identity, 'event_identity_mismatch')
            first_identity = identity
            if index != last_index + 1: warnings.append('intent_sequence_gap')
            last_index = index
            submissions.append({'index': index, 'graph_sha256': event['graph_sha256'],
                                'controls_sha256': identity[0], 'reference_manifest_sha256': identity[1],
                                'response': 'not_recorded', 'prompt_id': None, 'prompt_id_sha256': None})
        elif kind == 'accepted':
            require(submissions and index == last_index and submissions[-1]['response'] == 'not_recorded'
                    and event.get('fact') == 'validated_prompt_response_received', 'event_invalid')
            prompt, digest = event.get('prompt_id'), event.get('prompt_id_sha256')
            require('prompt_id' in event and (prompt is None or _text(prompt)) and is_hash(digest)
                    and digest not in seen_prompts, 'event_invalid')
            require(prompt is None or sha256(_wire(prompt)) == digest, 'prompt_digest_mismatch')
            seen_prompts.add(digest)
            submissions[-1].update(response='received', prompt_id=prompt, prompt_id_sha256=digest)
        elif kind == 'finish':
            elapsed, status = event.get('coordinator_elapsed_seconds'), event.get('coordinator_exit_status')
            require(event.get('fact') == 'coordinator_exit_snapshot' and _text(status, 64)
                    and 'coordinator_elapsed_seconds' in event and (elapsed is None or _number(elapsed)), 'event_invalid')
            finish = {'status': status, 'elapsed_seconds': elapsed, 'recorded_at': event['recorded_at'],
                      'authority': 'coordinator_snapshot_not_final_job_state'}
        else: raise EvidenceError('event_invalid')
    return submissions, finish, records, warnings


def _runtime(value, summary):
    if value is None:
        require(summary['comfy']['observed_samples'] == 0, 'runtime_binding_invalid')
        return None
    require(isinstance(value, dict) and type(value.get('lost')) is bool, 'runtime_binding_invalid')
    _timestamp(value.get('captured_at'))
    profile, epoch, last = value.get('profile_sha256'), value.get('epoch'), value.get('last_bracket_at')
    require(profile is None or is_hash(profile), 'runtime_binding_invalid')
    if epoch is not None:
        require(isinstance(epoch, dict) and type(epoch.get('pid')) is int and 1 <= epoch['pid'] < 2**31
                and _number(epoch.get('created_at')) and is_hash(epoch.get('argv_sha256')), 'runtime_binding_invalid')
        epoch = {k: epoch[k] for k in ('pid', 'created_at', 'argv_sha256')}
    require(value['lost'] or epoch is not None and profile is not None, 'runtime_binding_invalid')
    if last is not None: _timestamp(last)
    if summary['comfy']['observed_samples']:
        require(epoch is not None and profile is not None and last is not None, 'runtime_binding_invalid')
    return {'epoch': epoch, 'profile_sha256': profile, 'lost': value['lost'], 'last_bracket_at': last}


def inspect_observation(directory: str | Path, *, expected_result_sha256: str | None = None,
                        expected_job_id: str | None = None) -> dict:
    """Verify one explicitly nominated v1 artifact set. No directory scanning/writes.

    Optional external pins prevent substituting a rehashed result or another job.
    Without a pin this verifies self-consistency, not authenticity or job ownership.
    """
    if expected_result_sha256 is not None: require(is_hash(expected_result_sha256), 'invalid_expected_pin')
    if expected_job_id is not None: require(is_id(expected_job_id), 'invalid_expected_pin')
    directory = Path(directory).absolute()
    result_bytes = read_evidence_file(directory / 'result.json', DOCUMENT_LIMIT)
    result_sha = sha256(result_bytes)
    require(expected_result_sha256 is None or result_sha == expected_result_sha256, 'result_pin_mismatch')
    result = parse_document(result_bytes)
    require(isinstance(result, dict) and result.get('schema') == 'studio.job-resource-result/v1'
            and is_id(result.get('job_id')) and type(result.get('summary_available')) is bool
            and _text(result.get('stop_reason'), 128), 'result_invalid')
    job_id = result['job_id']; finished = _timestamp(result.get('finished_at'))
    require(expected_job_id is None or job_id == expected_job_id, 'job_pin_mismatch')
    manifest = result.get('artifact_hashes')
    require(isinstance(manifest, dict) and not set(manifest) - set(ARTIFACTS), 'artifact_manifest_invalid')
    if set(manifest) != set(ARTIFACTS): raise EvidenceError('artifact_missing', incomplete=True)
    require(result['summary_available'], 'summary_presence_conflict')
    captured, signatures = {}, {}
    for name in ARTIFACTS:
        limit = PROFILE_LIMIT if name == 'profile.jsonl' else DOCUMENT_LIMIT
        entry = manifest[name]
        require(isinstance(entry, dict) and set(entry) == {'sha256', 'bytes'} and is_hash(entry.get('sha256'))
                and type(entry.get('bytes')) is int and 0 <= entry['bytes'] <= limit, 'artifact_manifest_invalid')
        raw, signature = _capture_file(directory / name, limit)
        require(len(raw) == entry['bytes'] and sha256(raw) == entry['sha256'], 'artifact_hash_mismatch')
        captured[name] = raw
        signatures[name] = signature
    context = parse_document(captured['context.json'])
    source = _context(context, job_id)
    submissions, finish, records, warnings = _events(captured['events.jsonl'], context, job_id)
    try: summary = summarize_resource_profile(io.BytesIO(captured['profile.jsonl']))
    except (ValueError, UnicodeError, OverflowError): raise EvidenceError('profile_invalid') from None
    stored_summary = parse_document(captured['summary.json'])
    require(_wire(summary) == _wire(stored_summary), 'summary_mismatch')
    sampling, limits = summary['sampling'], context['limits']
    require(sampling['requested'] == limits['samples'] and sampling['interval_seconds_after_completion'] == limits['interval_seconds'],
            'sampling_contract_mismatch')
    require(_timestamp(records[-1]['recorded_at']) <= finished, 'timestamp_invalid')
    if sampling['observed']:
        end = _timestamp(finish['recorded_at']) if finish else finished
        require(_timestamp(records[0]['recorded_at']) <= _timestamp(sampling['first_observed_at'])
                and _timestamp(sampling['last_observed_at']) <= end, 'samples_outside_window')
    runtime = _runtime(result.get('runtime_binding'), summary)
    if not sampling['complete']: warnings.append('sampling_incomplete')
    if finish is None: warnings.append('coordinator_exit_missing')
    elif finish['status'] not in ('completed', 'failed', 'not_submitted', 'abandoned'):
        warnings.append('coordinator_outcome_unresolved')
    if runtime is None or runtime['lost']: warnings.append('runtime_bracket_lost')
    if result['stop_reason'] != 'coordinator_exit': warnings.append('observer_stopped_early')
    # A second small root capture and metadata brackets reject ordinary changes
    # during parsing, but do not promise an atomic cross-file filesystem snapshot.
    require(read_evidence_file(directory / 'result.json', DOCUMENT_LIMIT) == result_bytes, 'result_changed')
    try:
        require(all(_signature((directory / name).lstat()) == sig for name, sig in signatures.items()), 'file_changed')
    except OSError: raise EvidenceError('file_changed') from None
    return {'schema': SCHEMA, 'integrity': 'verified', 'job_id': job_id, 'result_sha256': result_sha,
            'artifact_hashes': manifest, 'summary_verified': True, 'profile_summary': summary,
            'source_observation': source, 'runtime_observation': runtime, 'submissions': submissions,
            'finish_snapshot': finish, 'warnings': sorted(set(warnings)),
            'qualified_benchmark': False, 'execution_authority': False,
            'qualification_gaps': ['loaded_code', 'model_contents', 'input_contents', 'actual_geometry',
                                   'precision', 'cold_warm_condition', 'final_job_outcome', 'inference_phase_timings']}