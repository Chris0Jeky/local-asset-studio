"""Optional job-bound observations; no submission, admission or recovery authority."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from queue import Empty, Queue
import stat
import subprocess
import threading
import time
from datetime import datetime, timezone

import resource_probe
from performance_history import summarize_resource_profile

MAX_RECEIPTS = 32
MAX_RAW_BYTES = 4 * 1024 * 1024
MAX_DOCUMENT_BYTES = 256 * 1024
MAX_EVENT_BYTES = 8192
MAX_EVENTS = 9  # Four admitted batch outputs: intent + response each, then coordinator exit.
MAX_WINDOW_SECONDS = 4 * 3600 + 60


def now(): return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False) + '\n').encode('utf-8')


def digest(value): return hashlib.sha256(encoded(value)[:-1]).hexdigest()


def event_snapshot(kind, job, *, index=None, graph=None, prompt_id=None):
    """Project values, never share nested live job/graph data with a collaborator."""
    value = {'event': kind, 'job_id': str(job['id']), 'recorded_at': now()}
    if kind == 'intent':
        value.update(index=index, graph_sha256=digest(graph),
                     controls_sha256=digest(job.get('controls', {})),
                     reference_manifest_sha256=digest(job.get('references', [])),
                     comfy_url=str(job.get('comfy_url', '')),
                     fact='pending_submission_save_returned')
    elif kind == 'accepted':
        value.update(index=index, prompt_id=prompt_id if len(prompt_id) <= 256 else None,
                     prompt_id_sha256=digest(prompt_id), fact='validated_prompt_response_received')
    elif kind == 'finish':
        value.update(coordinator_exit_status=str(job.get('status', 'unknown'))[:64],
                     coordinator_elapsed_seconds=resource_probe.counter(job.get('elapsed_seconds')),
                     fact='coordinator_exit_snapshot')
    else: raise ValueError('Unknown observation event')
    return value


def source_identity(root):
    """Capture repository facts off the submission path; never infer loaded-code parity."""
    value = {'captured_at': now(), 'commit_at_capture': None, 'tracked_changes': None,
             'loaded_code_matches_commit': None, 'untracked_files_examined': False,
             'unknown_reason': 'Loaded Python code and untracked files are not attested'}
    env = dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0')
    try:
        result = subprocess.run(['git', '-C', str(root), 'rev-parse', '--verify', 'HEAD'],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=2, env=env)
        commit = result.stdout.decode('ascii').strip()
        if result.returncode or len(commit) not in (40, 64) or any(c not in '0123456789abcdef' for c in commit):
            raise ValueError('Unavailable commit')
        value['commit_at_capture'] = commit
        result = subprocess.run(['git', '-C', str(root), 'diff-index', '--quiet', 'HEAD', '--'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2, env=env)
        if result.returncode in (0, 1): value['tracked_changes'] = result.returncode == 1
    except Exception: value['unknown_reason'] = 'Source capture unavailable or incomplete; loaded code is not attested'
    return value


class EpochUnavailable(ValueError): pass
class ObservationStopped(Exception): pass


class BoundRuntimeSampler:
    """Bracket each statistics GET with the originally captured configured listener."""
    def __init__(self, backends, url, *, sampler_factory=resource_probe.ResourceSampler,
                 fetcher=resource_probe.fetch_stats, studio_pid=None):
        self.backends, self.fetcher = backends, fetcher
        matches = [dict(p) for p in backends.profiles.values() if p['url'] == url]
        self.profile = matches[0] if len(matches) == 1 else None
        self.binding = {'captured_at': now(), 'epoch': None, 'profile_sha256': None,
                        'unknown_reason': None, 'lost': False, 'last_bracket_at': None}
        self.versions_layout = None
        try:
            if self.profile is None: raise EpochUnavailable()
            self.binding['profile_sha256'] = digest(self.profile)
            self.binding['epoch'] = self._epoch()
        except Exception: self.binding.update(unknown_reason='Configured listener epoch unavailable', lost=True)
        pids = [os.getpid() if studio_pid is None else studio_pid]
        if self.binding['epoch'] is not None: pids.append(self.binding['epoch']['pid'])
        self.sampler = sampler_factory(pids=pids, comfy_url=url if self.profile else None, fetcher=self._fetch)
        for process in getattr(self.sampler, 'processes', []):
            if self.binding['epoch'] and process.pid == self.binding['epoch']['pid'] and process.created != self.binding['epoch']['created_at']:
                process.unavailable = 'Initial process epoch did not match the listener'
                self.binding.update(lost=True, unknown_reason='Process epoch changed while attaching counters')

    def _epoch(self):
        process = self.backends.process(self.profile)
        if process is None: raise EpochUnavailable()
        created = resource_probe.counter(process.create_time())
        if created is None: raise EpochUnavailable()
        return {'pid': process.pid, 'created_at': created, 'argv_sha256': digest(process.cmdline())}

    def _fetch(self, url):
        if self.binding['lost']: raise EpochUnavailable()
        try:
            if self._epoch() != self.binding['epoch']: raise EpochUnavailable()
            data, size = self.fetcher(url)
            if self._epoch() != self.binding['epoch']: raise EpochUnavailable()
            layout = (data['versions'], [d['index'] for d in data['devices']])
            if self.versions_layout is not None and layout != self.versions_layout: raise EpochUnavailable()
            self.versions_layout = layout
            self.binding['last_bracket_at'] = now()
            return data, size
        except Exception:
            # An unobserved bracket is a permanent gap; never join a replacement epoch.
            self.binding.update(lost=True, unknown_reason='Listener identity or statistics bracket lost; no rebind')
            raise EpochUnavailable() from None

    def sample(self): return self.sampler.sample()


def _plain_directory(path):
    info = path.lstat()
    return stat.S_ISDIR(info.st_mode) and not (getattr(info, 'st_file_attributes', 0) & 0x400)


def allocate_directory(base):
    """Fixed exclusive slots cap retention even with competing observer instances."""
    base.mkdir(exist_ok=True)
    if not _plain_directory(base): raise ValueError('Observation root is not a plain directory')
    names = {f'observation-{index:02d}' for index in range(MAX_RECEIPTS)}
    with os.scandir(base) as entries:
        for count, entry in enumerate(entries, 1):
            if count > MAX_RECEIPTS or entry.name not in names or not _plain_directory(Path(entry.path)):
                raise ValueError('Observation retention contains an unknown entry')
    for name in sorted(names):
        candidate = base / name
        try: candidate.mkdir()
        except FileExistsError: continue
        return candidate
    raise ValueError('Observation retention is full; preserve or move existing receipts explicitly')


def write_document(path, value):
    data = encoded(value)
    if len(data) > MAX_DOCUMENT_BYTES: raise ValueError('Observation document exceeds byte limit')
    # The directory is exclusively allocated. Keep an interrupted initial document intact.
    with path.open('xb') as stream: stream.write(data); stream.flush()


def artifact_hashes(directory):
    result = {}
    for name in ('context.json', 'events.jsonl', 'profile.jsonl', 'summary.json'):
        path = directory / name
        if not path.exists(): continue
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Observation artifact is not a regular file')
        limit = MAX_RAW_BYTES if name == 'profile.jsonl' else MAX_DOCUMENT_BYTES
        with path.open('rb') as stream: data = stream.read(limit + 1)
        if len(data) > limit: raise ValueError('Observation artifact exceeds byte limit')
        result[name] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    return result


class _Window:
    def __init__(self, first):
        self.job_id = first['job_id']; self.first = first
        self.events = Queue(maxsize=MAX_EVENTS); self.events.put_nowait(first)
        self.stop = threading.Event(); self.done = threading.Event()
        self.started = time.monotonic(); self.event_count = 1; self.error = None
        self.path = None; self.result = None


class _ProfileWriter:
    def __init__(self, stream, drain): self.stream, self.drain, self.bytes = stream, drain, 0
    def write(self, text):
        data = text.encode('utf-8')
        if len(data) > resource_probe.MAX_RESPONSE_BYTES or self.bytes + len(data) > MAX_RAW_BYTES:
            raise ValueError('Observation profile exceeds byte limit')
        self.stream.write(data); self.bytes += len(data)
    def flush(self): self.stream.flush(); self.drain()


class JobResourceObservations:
    def __init__(self, root, experiments, backends, *, samples=120, interval=5,
                 sampler_factory=BoundRuntimeSampler, source_reader=source_identity,
                 thread_factory=threading.Thread):
        if type(samples) is not int or not 1 <= samples <= 120: raise ValueError('Invalid observation sample limit')
        if resource_probe.counter(interval) is None or not 1 <= interval <= 60: raise ValueError('Invalid observation interval')
        self.root, self.base, self.backends = root, experiments / 'resource-observations', backends
        self.samples, self.interval = samples, interval
        self.sampler_factory, self.source_reader, self.thread_factory = sampler_factory, source_reader, thread_factory
        self.lock = threading.Lock(); self.active = None; self.thread = None; self.last = None
        self.unavailable_reason = None

    @staticmethod
    def _copy(value):
        data = encoded(value)
        if len(data) > MAX_EVENT_BYTES: raise ValueError('Observation event exceeds byte limit')
        return json.loads(data)

    def intent(self, value):
        value = self._copy(value)
        if not self.lock.acquire(blocking=False): return
        try:
            if self.active is not None:
                if self.active.job_id == value['job_id']: self._append(self.active, value)
                else: self.unavailable_reason = 'A previous observer is still active'
                return
            if self.thread is not None and self.thread.is_alive():
                self.unavailable_reason = 'A previous observer is still finalizing'; return
            self.unavailable_reason = None
            window = _Window(value); self.active = self.last = window
            self.thread = self.thread_factory(target=self._observe, args=(window,), daemon=True, name='asset-studio-resource-observer')
            try: self.thread.start()
            except Exception:
                self.active = self.thread = None; window.done.set(); raise
        finally: self.lock.release()

    def _append(self, window, value):
        if window.event_count >= MAX_EVENTS:
            window.error = 'Event limit reached'; window.stop.set(); return
        window.events.put_nowait(value); window.event_count += 1

    def accepted(self, value): self._event(value)
    def finish(self, value): self._event(value, finish=True)

    def _event(self, value, finish=False):
        value = self._copy(value)
        # This lock protects only bounded memory operations, never file/process/HTTP calls.
        with self.lock:
            if self.active is not None and self.active.job_id == value['job_id']:
                self._append(self.active, value)
                if finish: self.active.stop.set()

    def _observe(self, window):
        sampler = None; reason = 'coordinator_exit'; event_bytes = 0
        try:
            window.path = allocate_directory(self.base)
            write_document(window.path / 'context.json', {
                'schema': 'studio.job-resource-context/v1', 'job_id': window.job_id,
                'intent': window.first, 'source': self.source_reader(self.root),
                'observer_source_sha256_at_capture': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'model_content_identity': None, 'input_content_identity': None,
                'actual_output_geometry': None, 'precision': None, 'warmth': None,
                'approval_attestation': None, 'generation_allowance_added': 0,
                'unknown_reason': 'Exact expanded graphs are hashed; file contents and runtime phases are not attested',
                'limits': {'samples': self.samples, 'interval_seconds': self.interval,
                           'raw_bytes': MAX_RAW_BYTES, 'events': MAX_EVENTS, 'window_seconds': MAX_WINDOW_SECONDS}})
            with (window.path / 'events.jsonl').open('xb') as events:
                def drain():
                    nonlocal event_bytes
                    while True:
                        try: value = window.events.get_nowait()
                        except Empty: break
                        data = encoded(value)
                        if event_bytes + len(data) > MAX_DOCUMENT_BYTES: raise ValueError('Event receipt exceeds byte limit')
                        events.write(data); event_bytes += len(data)
                    events.flush()

                def check():
                    if window.stop.is_set(): raise ObservationStopped()
                    if time.monotonic() - window.started >= MAX_WINDOW_SECONDS: raise TimeoutError()

                def pause(seconds):
                    until = time.monotonic() + seconds
                    while time.monotonic() < until:
                        drain(); check()
                        window.stop.wait(min(1, until - time.monotonic()))
                    check()

                class Sampler:
                    def sample(_self):
                        nonlocal sampler
                        check()
                        if sampler is None: sampler = self.sampler_factory(self.backends, window.first['comfy_url'])
                        record = sampler.sample(); check()
                        return record

                with (window.path / 'profile.jsonl').open('xb') as stream:
                    writer = _ProfileWriter(stream, drain)
                    try: resource_probe.write_samples(writer, Sampler(), self.samples, self.interval, pause)
                    except ObservationStopped: pass
                # Sampling has a separate finite count. Retain later response/exit facts without more probes.
                try:
                    while not window.stop.is_set(): pause(1)
                except ObservationStopped: pass
                drain()
            with (window.path / 'profile.jsonl').open('rb') as stream: summary = summarize_resource_profile(stream)
            write_document(window.path / 'summary.json', summary)
        except Exception as error:
            reason = type(error).__name__  # Never store exception messages, paths or endpoint payloads.
            self.unavailable_reason = 'Observation unavailable or incomplete: ' + reason
        finally:
            window.result = {'schema': 'studio.job-resource-result/v1', 'job_id': window.job_id,
                             'finished_at': now(), 'stop_reason': window.error or reason,
                             'runtime_binding': getattr(sampler, 'binding', None),
                             'artifact_hashes': None,
                             'summary_available': False}
            try:
                if window.path is not None:
                    window.result['summary_available'] = (window.path / 'summary.json').is_file()
                    window.result['artifact_hashes'] = artifact_hashes(window.path)
                    write_document(window.path / 'result.json', window.result)
            except Exception: pass
            with self.lock:
                if self.active is window: self.active = None
            window.done.set()


def from_config(studio):
    if studio.config.get('observe_job_resources') is not True: return None
    try:
        return JobResourceObservations(studio.root, studio.experiments, studio.backends,
                                       samples=studio.config.get('resource_observation_samples', 120),
                                       interval=studio.config.get('resource_observation_interval_seconds', 5))
    except Exception: return None
