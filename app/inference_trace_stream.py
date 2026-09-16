"""Incremental saved-trace inspection with bounded values and exact aggregates.

Only event intervals/aggregate identities survive each decoded JSON value. Limits
apply to the saved-file reader, not a live profiler's memory or export operation.
"""
from __future__ import annotations

import codecs
from decimal import Decimal, DecimalException
import hashlib
import json
import re

from inference_trace import (TraceError, _bounded, _constant, _pairs, _require,
                             _summarize_events)

MAX_STREAM_BYTES = 64 * 1024 * 1024
MAX_STREAM_EVENTS = 100_000
MAX_STREAM_OPERATORS = 4096
MAX_VALUE_BYTES = 256 * 1024
MAX_TOP_KEYS = 64
CHUNK_BYTES = 64 * 1024
_WHITESPACE = ' \t\r\n'
_DELIMITERS = _WHITESPACE + ',]}'


class _Values:
    """Keep at most one bounded JSON value plus one lookahead chunk as text."""
    def __init__(self, stream):
        self.stream = stream
        self.buffer = ''
        self.eof = False
        self.count = 0
        self.digest = hashlib.sha256()
        self.utf8 = codecs.getincrementaldecoder('utf-8')('strict')
        self.decoder = json.JSONDecoder(object_pairs_hook=_pairs, parse_float=Decimal,
                                        parse_constant=_constant)

    def fill(self):
        if self.eof: return
        raw = self.stream.read(min(CHUNK_BYTES, MAX_STREAM_BYTES - self.count + 1))
        _require(isinstance(raw, bytes) and len(raw) <= min(CHUNK_BYTES, MAX_STREAM_BYTES - self.count + 1),
                 'trace_stream_invalid')
        self.count += len(raw)
        _require(self.count <= MAX_STREAM_BYTES, 'trace_too_large')
        self.digest.update(raw)
        self.eof = not raw
        try: self.buffer += self.utf8.decode(raw, final=self.eof)
        except UnicodeError: raise TraceError('trace_json_invalid') from None

    def skip(self):
        while True:
            self.buffer = self.buffer.lstrip(_WHITESPACE)
            if self.buffer or self.eof: return
            self.fill()

    def peek(self):
        self.skip()
        return self.buffer[:1]

    def take(self, char):
        _require(self.peek() == char, 'trace_json_invalid')
        self.buffer = self.buffer[1:]

    def value(self, depth, *, key=False):
        self.skip()
        while True:
            try:
                result, end = self.decoder.raw_decode(self.buffer)
            except json.JSONDecodeError:
                _require(not self.eof, 'trace_json_invalid')
                _require(len(self.buffer.encode('utf-8')) <= MAX_VALUE_BYTES, 'trace_value_too_large')
                self.fill()
                continue
            except (ValueError, RecursionError, OverflowError, DecimalException):
                raise TraceError('trace_json_invalid') from None
            _require(len(self.buffer[:end].encode('utf-8')) <= MAX_VALUE_BYTES, 'trace_value_too_large')
            # raw_decode accepts a numeric prefix (e.g. 1 in an incomplete 1e3).
            # A delimiter or EOF must be observed before that token is accepted.
            if end == len(self.buffer) and not self.eof:
                self.fill()
                continue
            if end < len(self.buffer) and self.buffer[end] not in (_DELIMITERS + (':' if key else '')):
                numeric_continuation = self.buffer[:1] in '-0123456789' and self.buffer[end] in '.eE+-0123456789'
                _require(numeric_continuation and not self.eof, 'trace_json_invalid')
                _require(len(self.buffer.encode('utf-8')) <= MAX_VALUE_BYTES, 'trace_value_too_large')
                self.fill()
                continue
            _require(len(self.buffer[:end].encode('utf-8')) <= MAX_VALUE_BYTES, 'trace_value_too_large')
            try: _bounded(result, depth)
            except (ValueError, RecursionError, OverflowError, DecimalException):
                raise TraceError('trace_json_invalid') from None
            self.buffer = self.buffer[end:]
            return result

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
