"""Bounded offline summaries of resource_probe receipts; no live resource access.

A receipt is one finite observation window, not a job, runtime identity proof, or
admission decision. Only allow-listed counters leave this reducer.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from typing import BinaryIO

MAX_LINE_BYTES = 1024 * 1024
MAX_SAMPLES = 120
MAX_PROCESSES = 16
MAX_DEVICES = 8
MAX_COUNTER = 2**63 - 1
SOURCE_SCHEMA = 'studio.resource-profile/v1'
SUMMARY_SCHEMA = 'studio.resource-summary/v1'


def _number(value):
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
            or not 0 <= value <= MAX_COUNTER or not math.isfinite(value)):
        return None
    return value


def _integer(value, minimum, maximum):
    return isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= maximum


def _object(value):
    if not isinstance(value, dict):
        raise ValueError('Expected an observation object')
    return value


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ValueError('Invalid JSON constant')


def _decode(line):
    try:
        return _object(json.loads(line.decode('utf-8'), object_pairs_hook=_unique_object,
                                  parse_constant=_invalid_constant))
    except (UnicodeError, ValueError, RecursionError):
        raise ValueError('Invalid resource receipt JSON') from None


def _timestamp(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        raise ValueError('Invalid observation timestamp')
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError('Missing timezone')
        return result.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise ValueError('Invalid observation timestamp') from None


def _pair(data, total_key, free_key, *, positive_total=True):
    total, free = _number(data.get(total_key)), _number(data.get(free_key))
    if (data.get('unknown_reason') is not None or total is None or free is None
            or free > total or (positive_total and total == 0)):
        return None, None
    return total, free


class _Metric:
    def __init__(self):
        self.low = self.high = None
        self.known = 0

    def add(self, value):
        value = _number(value)
        if value is not None:
            self.low = value if self.low is None else min(self.low, value)
            self.high = value if self.high is None else max(self.high, value)
            self.known += 1

    def result(self, observed):
        return {'sampled_min': self.low, 'sampled_max': self.high,
                'known_samples': self.known, 'unknown_samples': observed - self.known}


def _metrics(names):
    return {name: _Metric() for name in names}


def _results(metrics, observed):
    return {name: metric.result(observed) for name, metric in metrics.items()}


class _Summary:
    def __init__(self, metadata):
        if (metadata.get('type') != 'metadata' or metadata.get('schema') != SOURCE_SCHEMA
                or not _integer(metadata.get('samples_requested'), 1, MAX_SAMPLES)):
            raise ValueError('Invalid resource profile metadata')
        interval = _number(metadata.get('interval_seconds_after_completion'))
        sha = metadata.get('sampler_sha256')
        if (interval is None or not 1 <= interval <= 60 or not isinstance(sha, str)
                or len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha)):
            raise ValueError('Invalid resource profile metadata')
        self.requested, self.interval, self.sampler_sha = metadata['samples_requested'], interval, sha
        self.observed = self.comfy_observed = 0
        self.first = self.last = None
        self.metrics = _metrics(('commit_limit_bytes', 'commit_used_bytes', 'commit_headroom_bytes',
                                 'physical_total_bytes', 'physical_available_bytes', 'sample_seconds'))
        self.runtime_metrics = _metrics(('response_bytes', 'elapsed_seconds'))
        self.processes, self.devices, self.versions = {}, {}, {}
        self.device_layout = None

    def add(self, record):
        if record.get('type') != 'sample' or self.observed >= self.requested:
            raise ValueError('Unexpected record or excess samples')
        timestamp = _timestamp(record.get('observed_at'))
        if self.last is not None and timestamp < self.last:
            raise ValueError('Observation timestamps moved backwards')
        if self.first is None:
            self.first = timestamp
        self.last = timestamp
        self.observed += 1
        self.metrics['sample_seconds'].add(record.get('sample_seconds'))
        commit = _object(record.get('host_commit', {}))
        limit, headroom = _pair(commit, 'limit_bytes', 'available_bytes')
        used = _number(commit.get('committed_bytes'))
        if limit is not None and used is not None and used + headroom == limit:
            for key, value in (('commit_limit_bytes', limit), ('commit_used_bytes', used),
                               ('commit_headroom_bytes', headroom)):
                self.metrics[key].add(value)
        ram = _object(record.get('physical_ram', {}))
        total, available = _pair(ram, 'total_bytes', 'available_bytes')
        self.metrics['physical_total_bytes'].add(total)
        self.metrics['physical_available_bytes'].add(available)
        self._processes(record.get('processes', []))
        self._comfy(_object(record.get('comfy', {})))

    def _processes(self, records):
        if not isinstance(records, list) or len(records) > MAX_PROCESSES:
            raise ValueError('Invalid process observation list')
        seen = set()
        for item in records:
            item = _object(item)
            pid, created = item.get('pid'), item.get('created_at')
            if (not _integer(pid, 1, 2**31 - 1) or pid in seen
                    or (created is not None and _number(created) is None)):
                raise ValueError('Invalid process identity')
            seen.add(pid)
            if pid not in self.processes:
                if len(self.processes) >= MAX_PROCESSES:
                    raise ValueError('Too many process identities in one receipt')
                self.processes[pid] = (created, _metrics(('working_set_bytes', 'private_bytes', 'cpu_one_core_percent')))
            previous, metrics = self.processes[pid]
            if created != previous:
                raise ValueError('Process identity changed within one receipt')
            if created is not None and item.get('unknown_reason') is None:
                for name, metric in metrics.items():
                    metric.add(item.get(name))

    def _comfy(self, runtime):
        # Failure receipts can still contain old-looking counters: do not trust them.
        if runtime.get('observed') is not True or runtime.get('unknown_reason') is not None:
            return
        versions = _object(runtime.get('versions', {}))
        for key in ('comfyui_version', 'pytorch_version'):
            value = versions.get(key)
            if value is None:
                continue
            if not isinstance(value, str) or not 1 <= len(value) <= 128:
                raise ValueError('Invalid runtime version identity')
            if key in self.versions and self.versions[key] != value:
                raise ValueError('Runtime version changed within one receipt')
            self.versions[key] = value
        records = runtime.get('devices', [])
        if not isinstance(records, list) or len(records) > MAX_DEVICES:
            raise ValueError('Invalid device observation list')
        indices = []
        for item in records:
            item = _object(item)
            index = item.get('index')
            if not _integer(index, 0, MAX_DEVICES - 1) or index in indices:
                raise ValueError('Invalid device index')
            indices.append(index)
        layout = tuple(sorted(indices))
        if self.device_layout is not None and self.device_layout != layout:
            raise ValueError('Device layout changed within one receipt')
        self.device_layout = layout
        self.comfy_observed += 1
        for name, metric in self.runtime_metrics.items():
            metric.add(runtime.get(name))
        for item in records:
            index = item['index']
            if index not in self.devices:
                self.devices[index] = _metrics(tuple(prefix + suffix + '_bytes'
                    for prefix in ('vram_', 'torch_vram_') for suffix in ('total', 'free', 'used')))
            metrics = self.devices[index]
            for prefix in ('vram_', 'torch_vram_'):
                total, free = _pair(item, prefix + 'total_bytes', prefix + 'free_bytes', positive_total=False)
                metrics[prefix + 'total_bytes'].add(total)
                metrics[prefix + 'free_bytes'].add(free)
                metrics[prefix + 'used_bytes'].add(total - free if total is not None else None)

    def result(self, receipt_sha):
        return {
            'schema': SUMMARY_SCHEMA,
            'source': {'schema': SOURCE_SCHEMA, 'receipt_sha256': receipt_sha, 'sampler_sha256': self.sampler_sha},
            'sampling': {'requested': self.requested, 'observed': self.observed,
                         'complete': self.observed == self.requested,
                         'interval_seconds_after_completion': self.interval,
                         'first_observed_at': self.first.isoformat() if self.first is not None else None,
                         'last_observed_at': self.last.isoformat() if self.last is not None else None,
                         'observed_span_seconds': (self.last - self.first).total_seconds() if self.first is not None else None},
            'metrics': _results(self.metrics, self.observed),
            'comfy': {'observed_samples': self.comfy_observed,
                      'unobserved_samples': self.observed - self.comfy_observed,
                      'versions': self.versions, 'metrics': _results(self.runtime_metrics, self.observed),
                      'devices': [{'index': index, 'metrics': _results(metrics, self.observed)}
                                  for index, metrics in sorted(self.devices.items())]},
            'processes': [{'pid': pid, 'created_at': created, 'metrics': _results(metrics, self.observed)}
                          for pid, (created, metrics) in sorted(self.processes.items())],
            'limitations': [
                'Extrema are sampled observations and can miss transient peaks and lower free memory.',
                'Complete describes the requested sample count, not a successful generation or complete counter coverage.',
                'Observation span and probe duration are not job wall time or inference phase timings.',
                'No job, graph, model or backend epoch is bound by this receipt schema; same-version restarts can go undetected.',
                'Process lifetime maxima are excluded; working sets overlap and must not be summed as host RAM.',
                'Device and Torch memory describe different domains, not browser attribution or reserved capacity.',
                'Hashes identify supplied evidence bytes; they do not authenticate sensors or prove safe admission.'
            ]}


def summarize_resource_profile(stream: BinaryIO) -> dict:
    """Reduce one finite v1 JSONL receipt without retaining its sample history.

    Every read is bounded; malformed, mixed or oversized receipts raise a
    payload-free ValueError. An interrupted receipt containing only complete
    JSON records is accepted with incomplete sampling, never repaired silently.
    """
    digest, summary, lines = hashlib.sha256(), None, 0
    while True:
        line = stream.readline(MAX_LINE_BYTES + 1)
        if not isinstance(line, bytes):
            raise ValueError('Resource receipt requires a binary stream')
        if not line:
            break
        lines += 1
        if lines > MAX_SAMPLES + 1 or len(line) > MAX_LINE_BYTES:
            raise ValueError('Resource receipt exceeds size limits')
        digest.update(line)
        record = _decode(line)
        if summary is None:
            summary = _Summary(record)
        else:
            summary.add(record)
    if summary is None:
        raise ValueError('Resource receipt is empty')
    return summary.result(digest.hexdigest())
