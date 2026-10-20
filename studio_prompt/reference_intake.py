"""Bounded intake of the existing reference-preview JSON; no files or model work.

Only the outer object and image rows need streaming grammar. Ordinary metadata
still goes through the shared strict JSON decoder, after byte/structure bounds.
Originals never become aggregate JSON strings: base64 is decoded in small chunks
into at most four capped byte captures, owned until the preview context exits.
"""
from __future__ import annotations
import base64
from contextlib import contextmanager
import io
import re
import time

from .schema import decode, fields, need

READ_CHUNK = 64 * 1024
READ_TIMEOUT_SECONDS = 30
METADATA_LIMIT = 1024 * 1024
METADATA_STRUCTURE_LIMIT = 16384
METADATA_DEPTH_LIMIT = 64
_SPACE = re.compile(rb'[ \t\r\n]*')
_STRING_SPECIAL = re.compile(rb'["\\]')
_HEX = re.compile(rb'[0-9a-fA-F]{4}')
_WHITESPACE = b' \t\r\n'


class _CapturedImage:
    """Internal only: JSON cannot construct this type or claim verification."""
    def __init__(self, raw): self.raw = raw
    def clear(self): self.raw = None


class _PreviewJSON:
    def __init__(self, reader, size, image_limit, encoded_limit, connection=None):
        self.reader = getattr(reader, 'read1', None) or reader.read
        self.remaining = size
        self.image_limit = image_limit
        self.encoded_limit = encoded_limit
        self.buffer = b''; self.position = 0
        self.metadata_size = 0; self.structures = 0
        self.captures = []
        self.deadline = time.monotonic() + READ_TIMEOUT_SECONDS
        self.connection = connection
        self.old_timeout = connection.gettimeout() if connection is not None else None

    def _fill(self):
        if self.position < len(self.buffer): return True
        if not self.remaining: return False
        budget = self.deadline - time.monotonic()
        need(budget > 0, 'Preview body read timed out')
        if self.connection is not None:
            self.connection.settimeout(budget if self.old_timeout is None else min(self.old_timeout, budget))
        size = min(READ_CHUNK, self.remaining)
        chunk = self.reader(size)
        need(type(chunk) is bytes and 0 < len(chunk) <= size, 'Incomplete request body')
        self.remaining -= len(chunk)
        self.buffer = chunk; self.position = 0
        return True

    def _peek(self):
        return self.buffer[self.position] if self._fill() else None

    def _take(self):
        value = self._peek()
        need(value is not None, 'Incomplete JSON body')
        self.position += 1
        return value

    def _space(self):
        while self._fill():
            self.position = _SPACE.match(self.buffer, self.position).end()
            if self.position < len(self.buffer): break

    def _account(self, size=1, *, structure=False):
        self.metadata_size += size
        need(self.metadata_size <= METADATA_LIMIT, 'Preview metadata exceeds 1 MiB')
        if structure:
            self.structures += 1
            need(self.structures <= METADATA_STRUCTURE_LIMIT, 'Preview metadata has too many JSON tokens')

    def _expect(self, token):
        self._space()
        need(self._take() == token, 'Invalid preview JSON structure')
        self._account(structure=True)

    def _accept(self, token):
        self._space()
        if self._peek() != token: return False
        self.position += 1; self._account(structure=True)
        return True

    def _metadata(self):
        """Capture one small JSON value without normalizing whitespace or keys."""
        self._space(); first = self._peek()
        raw = bytearray(); stack = []; quoted = False; escaped = False
        compound = first in (ord('{'), ord('['))
        string = first == ord('"')
        while True:
            char = self._peek()
            if not compound and not string and (char is None or char in b',}]' + _WHITESPACE): break
            char = self._take()
            self._account(); raw.append(char)
            if quoted:
                if escaped: escaped = False
                elif char == ord('\\'): escaped = True
                elif char == ord('"'):
                    quoted = False
                    if string: break
                continue
            if char == ord('"'):
                quoted = True; self._account(0, structure=True)
            elif char in b'{[':
                stack.append(char); self._account(0, structure=True)
                need(len(stack) <= METADATA_DEPTH_LIMIT, 'Preview metadata is nested too deeply')
            elif char in b'}]':
                need(stack and (stack[-1], char) in ((ord('{'), ord('}')), (ord('['), ord(']'))),
                     'Invalid preview JSON structure')
                stack.pop(); self._account(0, structure=True)
                if not stack: break
            elif char in b',:': self._account(0, structure=True)
        need(raw, 'Expected a JSON value')
        return decode(raw)

    def _image_pieces(self):
        self._expect(ord('"'))
        while self._fill():
            match = _STRING_SPECIAL.search(self.buffer, self.position)
            end = match.start() if match else len(self.buffer)
            if end > self.position:
                piece = self.buffer[self.position:end]; self.position = end
                yield piece
            if not match: continue
            special = self._take()
            if special == ord('"'):
                self._account(structure=True)
                return
            escape = self._take()
            if escape == ord('u'):
                digits = bytes(self._take() for _ in range(4))
                need(_HEX.fullmatch(digits), 'Invalid JSON image escape')
                point = int(digits, 16)
                need(point < 128, 'Original image must be ASCII base64')
                yield bytes((point,))
            else:
                escapes = {ord('"'): b'"', ord('\\'): b'\\', ord('/'): b'/',
                           ord('b'): b'\b', ord('f'): b'\f', ord('n'): b'\n', ord('r'): b'\r', ord('t'): b'\t'}
                need(escape in escapes, 'Invalid JSON image escape')
                yield escapes[escape]
        raise ValueError('Incomplete JSON image string')

    def _image(self):
        carry = b''; encoded_size = 0; decoded_size = 0; padded = False
        with io.BytesIO() as output:
            for piece in self._image_pieces():
                encoded_size += len(piece)
                need(encoded_size <= self.encoded_limit, 'Original image exceeds the 8 MiB limit')
                need(not padded, 'Excess data after original base64 padding')
                block = carry + piece; boundary = len(block) // 4 * 4
                complete, carry = block[:boundary], block[boundary:]
                if not complete: continue
                padding = len(complete) - len(complete.rstrip(b'='))
                if b'=' in complete:
                    need(1 <= padding <= 2 and complete.find(b'=') == len(complete) - padding and not carry,
                         'Invalid original base64 padding')
                    padded = True
                size = len(complete) // 4 * 3 - padding
                # Check the decoded size before b64decode allocates its output,
                # including the two byte/three byte boundary at the same encoded length.
                need(decoded_size + size <= self.image_limit, 'Original image exceeds the 8 MiB limit')
                raw = base64.b64decode(complete, validate=True)
                output.write(raw); decoded_size += len(raw)
            need(encoded_size and not carry and decoded_size, 'Invalid or incomplete original base64')
            captured = _CapturedImage(output.getvalue())
        self.captures.append(captured)
        return captured

    def _object(self, readers):
        self._expect(ord('{')); result = {}
        if self._accept(ord('}')): return result
        while True:
            self._space()
            need(self._peek() == ord('"'), 'Expected a JSON object key')
            key = self._metadata()
            need(key not in result, 'Duplicate JSON key')
            need(key in readers, 'Missing or unknown fields')
            self._expect(ord(':'))
            result[key] = readers[key]()
            if self._accept(ord('}')): return result
            self._expect(ord(','))

    def _images(self):
        self._expect(ord('[')); rows = []
        if self._accept(ord(']')): return rows
        while True:
            need(len(rows) < 4, 'Supply one to four image references; never truncate')
            row = self._object({'reference_id': self._metadata, 'media_base64': self._image})
            fields(row, ('reference_id', 'media_base64')); rows.append(row)
            if self._accept(ord(']')): return rows
            self._expect(ord(','))

    def read(self):
        readers = {key: self._metadata for key in ('analysis', 'review', 'intent', 'adopt_brief')}
        readers['images'] = self._images
        value = self._object(readers)
        self._space()
        need(self._peek() is None, 'Extra data after preview JSON')
        fields(value, tuple(readers))
        return value

    def clear(self):
        for captured in self.captures: captured.clear()
        self.captures.clear(); self.buffer = b''
        if self.connection is not None:
            try: self.connection.settimeout(self.old_timeout)
            except OSError: pass


@contextmanager
def preview_body(handler, *, http_limit, image_limit, encoded_limit):
    """One unambiguous fixed-length body; all captures are cleared on every exit."""
    headers = handler.headers; get_all = getattr(headers, 'get_all', None)
    if callable(get_all):
        lengths = get_all('Content-Length') or []
        transfer = get_all('Transfer-Encoding') or []
    else:
        length = headers.get('Content-Length')
        lengths = [] if length is None else [length]
        transfer = headers.get('Transfer-Encoding') is not None
    need(len(lengths) <= 1 and not transfer, 'One Content-Length and no Transfer-Encoding required')
    size = handler._content_length(http_limit)
    # The base guard supplies its existing missing/over-limit wording. Fixed
    # length framing additionally excludes signs, separators and ambiguous forms.
    need(len(lengths) == 1 and re.fullmatch(r'[0-9]+', lengths[0].strip()), 'Valid Content-Length required')
    parser = _PreviewJSON(handler.rfile, size, image_limit, encoded_limit, getattr(handler, 'connection', None))
    try:
        yield parser.read()
    finally:
        parser.clear()
