"""Incremental saved-trace inspection with bounded values and exact aggregates.

Only event intervals/aggregate identities survive each decoded JSON value. Limits
apply to the saved-file reader, not a live profiler's memory or export operation.
"""
from __future__ import annotations

import re

from inference_trace import TraceError, _require, _summarize_events
from inference_trace_values import _JSONValues

MAX_STREAM_BYTES = 64 * 1024 * 1024
MAX_STREAM_EVENTS = 100_000
MAX_STREAM_OPERATORS = 4096
MAX_VALUE_BYTES = 256 * 1024
MAX_TOP_KEYS = 64
CHUNK_BYTES = 64 * 1024


class _Values(_JSONValues):
    """Frame values once; the trace envelope owns event and EOF interpretation."""
    def __init__(self, stream):
        super().__init__(stream, byte_limit=MAX_STREAM_BYTES,
                         value_limit=MAX_VALUE_BYTES, chunk_bytes=CHUNK_BYTES)

    def events(self, source, expected_sha256):
        self.take('{')
        keys = set(); version = None
        if self.peek() != '}':
            while True:
                key = self.value(2, key=True)
                _require(isinstance(key, str) and len(key) <= 256, 'trace_key_invalid')
                _require(key not in keys, 'trace_json_invalid')
                keys.add(key)
                _require(len(keys) <= MAX_TOP_KEYS, 'trace_keys_exceeded')
                self.take(':')
                if key == 'traceEvents':
                    _require(self.peek() == '[', 'trace_format_unsupported')
                    self.take('[')
                    if self.peek() != ']':
                        while True:
                            yield self.value(3)
                            if self.peek() == ']': break
                            self.take(',')
                    self.take(']')
                else:
                    value = self.value(2)
                    if key == 'schemaVersion': version = value
                    del value
                if self.peek() == '}': break
                self.take(',')
        self.take('}')
        _require(self.peek() == '' and self.eof, 'trace_json_invalid')
        _require('traceEvents' in keys and type(version) is int and version == 1, 'trace_format_unsupported')
        identity = self.digest.hexdigest()
        _require(expected_sha256 is None or identity == expected_sha256, 'trace_hash_mismatch')
        source.update(sha256=identity, bytes=self.count)


def summarize_trace_stream(stream, *, expected_sha256=None):
    """Read to EOF once; return no partial report on later corruption or overflow."""
    if expected_sha256 is not None:
        _require(isinstance(expected_sha256, str) and re.fullmatch('[0-9a-f]{64}', expected_sha256),
                 'expected_hash_invalid')
    source = {}
    values = _Values(stream)
    return _summarize_events(values.events(source, expected_sha256), source,
                             event_limit=MAX_STREAM_EVENTS, operator_limit=MAX_STREAM_OPERATORS)
