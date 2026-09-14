"""Bounded, read-only observations. This module never constructs Studio or imports Torch."""
from __future__ import annotations

import hashlib
import http.client
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

import host_memory
from backend_contracts import loopback_port

MAX_RESPONSE_BYTES = 1024 * 1024
MAX_PROCESSES = 16
MAX_SAMPLES = 120


def counter(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
        return value
    return None


def physical_memory(provider=psutil):
    empty = {'total_bytes': None, 'available_bytes': None, 'unknown_reason': None}
    if provider is None: return dict(empty, unknown_reason='psutil is unavailable')
    try:
        memory = provider.virtual_memory()
        total, available = counter(memory.total), counter(memory.available)
        if total is None or available is None or total <= 0 or available > total:
            return dict(empty, unknown_reason='Invalid physical memory counters')
        return {'total_bytes': total, 'available_bytes': available, 'unknown_reason': None}
    except Exception as error:
        return dict(empty, unknown_reason='Physical memory unavailable: ' + type(error).__name__)


class ProcessObservation:
    """An explicitly nominated PID is pinned to one create-time identity, never rebound."""
    def __init__(self, pid, provider=psutil, clock=time.perf_counter):
        if isinstance(pid, bool) or not isinstance(pid, int) or not 1 <= pid <= 2**31 - 1:
            raise ValueError('PID must be a positive integer')
        self.pid, self.provider, self.clock = pid, provider, clock
        self.created = None; self.previous = None; self.unavailable = None
        try:
            if provider is None: raise RuntimeError('psutil unavailable')
            self.created = counter(provider.Process(pid).create_time())
            if self.created is None: raise ValueError('Invalid process identity')
        except Exception as error:
            self.unavailable = 'Initial process identity unavailable: ' + type(error).__name__

    def _matches(self, process):
        created = counter(process.create_time())
        if created is None: raise ValueError('Invalid process identity')
        if created != self.created:
            self.previous = None
            self.unavailable = 'PID identity changed; this observer will not rebind'
            return False
        return True

    def read(self):
        record = {'pid': self.pid, 'created_at': self.created, 'working_set_bytes': None, 'peak_working_set_bytes': None,
                  'private_bytes': None, 'cpu_seconds': None, 'cpu_one_core_percent': None,
                  'unknown_reason': self.unavailable}
        if self.unavailable: return record
        try:
            process = self.provider.Process(self.pid)
            if not self._matches(process):
                return dict(record, unknown_reason=self.unavailable)
            memory = process.memory_info(); cpu = process.cpu_times(); now = self.clock()
            # create_time() is cached on a psutil Process. A fresh handle must
            # verify identity after the PID-addressed counter reads as well.
            if not self._matches(self.provider.Process(self.pid)):
                return dict(record, unknown_reason=self.unavailable)
            total = counter(cpu.user + cpu.system)
            record.update(working_set_bytes=counter(memory.rss), peak_working_set_bytes=counter(getattr(memory, 'peak_wset', None)),
                          private_bytes=counter(getattr(memory, 'private', None)), cpu_seconds=total)
            if total is not None and self.previous is not None:
                before, previous_cpu = self.previous
                if now > before and total >= previous_cpu:
                    record['cpu_one_core_percent'] = (total - previous_cpu) * 100 / (now - before)
            self.previous = (now, total) if total is not None else None
            return record
        except Exception as error:
            self.previous = None
            return dict(record, unknown_reason='Process counters unavailable: ' + type(error).__name__)


def project_stats(data):
    """Do not retain command lines, paths, queue contents, names or arbitrary endpoint data."""
    if not isinstance(data, dict) or not isinstance(data.get('system'), dict) or not isinstance(data.get('devices'), list):
        raise ValueError('Invalid system statistics')
    versions = {key: value for key in ('comfyui_version', 'pytorch_version')
                if isinstance(value := data['system'].get(key), str) and len(value) <= 128}
    devices = []
    for index, device in enumerate(data['devices'][:8]):
        if not isinstance(device, dict): raise ValueError('Invalid device statistics')
        record = {'index': index}
        for total_key, free_key in (('vram_total', 'vram_free'), ('torch_vram_total', 'torch_vram_free')):
            total, free = counter(device.get(total_key)), counter(device.get(free_key))
            if total is None or free is None or free > total: total, free = None, None
            record.update({total_key + '_bytes': total, free_key + '_bytes': free})
        devices.append(record)
    return {'versions': versions, 'devices': devices}


def fetch_stats(url, timeout=2.0, clock=time.perf_counter):
    """One direct loopback GET, no proxy/redirect; bounded body and socket waits."""
    port = loopback_port(url)
    if counter(timeout) is None or not 0 < timeout <= 10: raise ValueError('Timeout must be in (0, 10] seconds')
    started = clock(); connection = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout)
    try:
        connection.request('GET', '/system_stats', headers={'Accept': 'application/json', 'Connection': 'close'})
        sock = connection.sock
        response = connection.getresponse()
        if response.status != 200: raise ValueError('HTTP response was not 200')
        length = response.getheader('Content-Length')
        if length is not None and (int(length) < 0 or int(length) > MAX_RESPONSE_BYTES):
            raise ValueError('Response exceeds size limit')
        chunks, size = [], 0
        while True:
            remaining = timeout - (clock() - started)
            if remaining <= 0: raise TimeoutError('Response deadline exceeded')
            if sock is not None and sock.fileno() >= 0: sock.settimeout(remaining)
            part = response.read1(min(65536, MAX_RESPONSE_BYTES + 1 - size))
            if not part: break
            size += len(part)
            if size > MAX_RESPONSE_BYTES: raise ValueError('Response exceeds size limit')
            chunks.append(part)
        return project_stats(json.loads(b''.join(chunks))), size
    finally:
        connection.close()


class ResourceSampler:
    def __init__(self, pids=(), comfy_url=None, *, provider=psutil, commit_reader=host_memory.read,
                 fetcher=fetch_stats, clock=time.perf_counter):
        pids = list(dict.fromkeys(pids))
        if len(pids) > MAX_PROCESSES: raise ValueError('At most 16 explicitly nominated PIDs are supported')
        if comfy_url is not None: loopback_port(comfy_url)
        self.provider, self.commit_reader, self.fetcher, self.clock = provider, commit_reader, fetcher, clock
        self.comfy_url = comfy_url
        self.processes = [ProcessObservation(pid, provider, clock) for pid in pids]

    def sample(self):
        started = self.clock()
        record = {'type': 'sample', 'observed_at': datetime.now(timezone.utc).isoformat(),
                  'host_commit': self.commit_reader(), 'physical_ram': physical_memory(self.provider),
                  'processes': [process.read() for process in self.processes]}
        runtime = {'observed': False, 'versions': {}, 'devices': [], 'response_bytes': None,
                   'elapsed_seconds': None, 'unknown_reason': 'ComfyUI sampling was not requested'}
        if self.comfy_url is not None:
            probe_started = self.clock()
            try:
                data, size = self.fetcher(self.comfy_url)
                runtime.update(data, observed=True, response_bytes=size, unknown_reason=None)
            except Exception as error:
                runtime['unknown_reason'] = 'ComfyUI counters unavailable: ' + type(error).__name__
            runtime['elapsed_seconds'] = self.clock() - probe_started
        record['comfy'] = runtime; record['sample_seconds'] = self.clock() - started
        return record


def write_samples(stream, sampler, samples=6, interval=5.0, sleep=time.sleep):
    if isinstance(samples, bool) or not isinstance(samples, int) or not 1 <= samples <= MAX_SAMPLES:
        raise ValueError('Samples must be an integer between 1 and 120')
    if counter(interval) is None or not 1 <= interval <= 60: raise ValueError('Interval must be between 1 and 60 seconds')
    metadata = {'type': 'metadata', 'schema': 'studio.resource-profile/v1', 'samples_requested': samples,
                'interval_seconds_after_completion': interval,
                'sampler_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'notes': ['Observations are not admission or ownership authority.',
                          'Working sets include shared pages and must not be summed as total host RAM.',
                          'Private bytes are reported only where psutil exposes them; unavailable is null.',
                          'CPU percentage uses one logical core as 100%; it can exceed 100%.',
                          'ComfyUI VRAM counters are runtime/device observations, not browser attribution.',
                          'Sampling can miss peaks. No inference or crash-reduction claim follows.']}
    stream.write(json.dumps(metadata, allow_nan=False) + '\n'); stream.flush()
    for index in range(samples):
        stream.write(json.dumps(sampler.sample(), allow_nan=False) + '\n'); stream.flush()
        if index + 1 < samples: sleep(interval)
