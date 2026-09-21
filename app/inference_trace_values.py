"""One-pass bounded JSON framing for the saved-trace reader.

Framing is not validation: the strict JSON decoder still owns grammar, duplicate
keys and exact numbers. It sees each complete value once, never growing prefixes.
"""
from __future__ import annotations

import codecs
from decimal import Decimal, DecimalException
import hashlib
from io import StringIO
import json
import re

from inference_trace import TraceError, _bounded, _constant, _pairs, _require

_SPACE = re.compile(r'[ \t\r\n]*')
_STRING_MARK = re.compile(r'["\\]')
_ATOM_END = re.compile(r'[ \t\r\n,\]}:]')
_DELIMITERS = ' \t\r\n,]}'


class _JSONValues:
    def __init__(self, stream, *, byte_limit, value_limit, chunk_bytes):
        self.stream = stream
        self.byte_limit, self.value_limit, self.chunk_bytes = byte_limit, value_limit, chunk_bytes
        self.buffer, self.pos, self.eof, self.count = '', 0, False, 0
        self.digest = hashlib.sha256()
        self.utf8 = codecs.getincrementaldecoder('utf-8')('strict')
        self.decoder = json.JSONDecoder(object_pairs_hook=_pairs, parse_float=Decimal, parse_constant=_constant)

    def fill(self):
        # Only exhausted chunks are replaced. Never concatenate an ever-growing
        # value prefix or retain a list of one-character read fragments.
        amount = min(self.chunk_bytes, self.byte_limit - self.count + 1)
        raw = self.stream.read(amount)
        _require(isinstance(raw, bytes) and len(raw) <= amount, 'trace_stream_invalid')
        self.count += len(raw)
        _require(self.count <= self.byte_limit, 'trace_too_large')
        self.digest.update(raw)
        self.eof = not raw
        try: self.buffer = self.utf8.decode(raw, final=self.eof)
        except UnicodeError: raise TraceError('trace_json_invalid') from None
        self.pos = 0

    def char(self):
        while self.pos == len(self.buffer) and not self.eof:
            self.fill()
        return self.buffer[self.pos:self.pos+1]

    def skip(self):
        while self.char():
            self.pos = _SPACE.match(self.buffer, self.pos).end()
            if self.pos < len(self.buffer): return

    def peek(self):
        self.skip()
        return self.char()

    def take(self, char):
        _require(self.peek() == char, 'trace_json_invalid')
        self.pos += 1

    def value(self, depth, *, key=False):
        self.skip()
        first = self.char()
        _require(bool(first), 'trace_json_invalid')
        atom = first not in ('{', '[', '"')
        stack, quoted, escaped, done, byte_count = [], False, False, False, 0
        with StringIO() as text:
            while not done:
                if not self.char():
                    _require(atom, 'trace_json_invalid')
                    break
                start = self.pos
                if atom:
                    marker = _ATOM_END.search(self.buffer, self.pos)
                    self.pos = marker.start() if marker else len(self.buffer)
                    done = marker is not None
                else:
                    while self.pos < len(self.buffer):
                        if quoted and not escaped:
                            marker = _STRING_MARK.search(self.buffer, self.pos)
                            if marker is None:
                                self.pos = len(self.buffer)
                                break
                            self.pos = marker.start()
                        char = self.buffer[self.pos]; self.pos += 1
                        if quoted:
                            if escaped: escaped = False
                            elif char == '\\': escaped = True
                            elif char == '"':
                                quoted = False
                                if not stack: done = True
                        elif char == '"': quoted = True
                        elif char in '{[':
                            stack.append('}' if char == '{' else ']')
                            _require(depth + len(stack) - 1 <= 32, 'trace_json_invalid')
                        elif char in '}]':
                            _require(bool(stack) and stack.pop() == char, 'trace_json_invalid')
                            if not stack: done = True
                        if done: break
                part = self.buffer[start:self.pos]
                byte_count += len(part.encode('utf-8'))
                _require(byte_count <= self.value_limit, 'trace_value_too_large')
                text.write(part)
            following = self.char()
            _require(not following or following in (_DELIMITERS + (':' if key else '')), 'trace_json_invalid')
            token = text.getvalue()
        try:
            result, end = self.decoder.raw_decode(token)
            _require(end == len(token), 'trace_json_invalid')
            _bounded(result, depth)
        except (ValueError, RecursionError, OverflowError, DecimalException):
            raise TraceError('trace_json_invalid') from None
        return result
