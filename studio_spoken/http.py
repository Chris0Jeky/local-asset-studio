"""Strict loopback routes on the existing Studio server; no inference routes."""
from __future__ import annotations

import json
import re
from urllib.parse import parse_qsl, urlsplit

from .core import ArchiveAccess, AccessError, digest, fields
from studio_workflow.http_body import drain_declared_body
from spoken_brief_archive import ArchiveConflict, require_archive
from spoken_brief_compile import SpokenBriefError
from spoken_brief_exports import PlaybackConflict

PREFIX = '/api/spoken-briefs'
MAX_BODY_BYTES = 16384
READ_TIMEOUT = 2


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value: raise AccessError('Duplicate JSON field')
        value[key] = item
    return value


def _constant(_): raise AccessError('Non-finite JSON value refused')


def byte_range(value, size):
    """One finite byte range; multiple ranges are deliberately unsupported."""
    match = re.fullmatch(r'bytes=(\d{0,18})-(\d{0,18})', value)
    if not match or not any(match.groups()): raise AccessError('Invalid or unsupported byte range', 416)
    first, last = match.groups()
    if not first:
        suffix = int(last)
        if not suffix: raise AccessError('Empty suffix byte range', 416)
        return max(0, size - suffix), size - 1
    start = int(first); end = int(last) if last else size - 1
    if start >= size or end < start: raise AccessError('Byte range is outside this audio', 416)
    return start, min(end, size - 1)


def extend_handler(base):
    class SpokenHandler(base):
        def _spoken_error(self, exc):
            self.close_connection = True
            # Windows resets a socket closed with unread request bytes, which can abort the client before it
            # reads this refusal (WinError 10053, #837; the other routes fixed it in #196/#468/#545).
            if not getattr(self, '_spoken_body_consumed', False): drain_declared_body(self)
            status = (409 if isinstance(exc, (ArchiveConflict, PlaybackConflict))
                      else exc.status if isinstance(exc, AccessError) else 400)
            return self._json(status, {'error': str(exc)[:800], 'generation_submitted': False})

        def _spoken_query(self):
            parsed = urlsplit(self.path)
            if len(self.path) > 8192 or parsed.fragment or re.search(r'%(?![0-9a-fA-F]{2})', parsed.query):
                raise AccessError('Invalid route or query')
            pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True,
                              max_num_fields=6, encoding='utf-8', errors='strict')
            query = {}
            for key, value in pairs:
                if key in query: raise AccessError('Duplicate query field')
                query[key] = value
            return parsed.path, query

        def _spoken_host(self):
            return len(self.headers.get_all('Host', [])) == 1 and self._safe_host()

        def _spoken_origin(self):
            return (self._spoken_host() and len(self.headers.get_all('Origin', [])) == 1
                    and self.headers['Origin'] == 'http://' + self.headers['Host']
                    and self._safe_mutation())

        def _spoken_access(self):
            return ArchiveAccess(self.studio.config.get('spoken_briefs'))

        def _spoken_body(self):
            if (self.headers.get_all('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1
                    or len(self.headers.get_all('Content-Type', [])) != 1):
                raise AccessError('One Content-Length and Content-Type required; no Transfer-Encoding')
            length = self.headers['Content-Length']
            if not re.fullmatch(r'\d{1,9}', length): raise AccessError('Invalid Content-Length')
            length = int(length)
            if length > MAX_BODY_BYTES: raise AccessError('Request body exceeds 16 KiB', 413)
            if self.headers['Content-Type'].split(';')[0].strip().lower() != 'application/json':
                raise AccessError('application/json required')
            previous = self.connection.gettimeout()
            try:
                self.connection.settimeout(READ_TIMEOUT)
                self._spoken_body_consumed = True
                raw = self.rfile.read(length)
            finally: self.connection.settimeout(previous)
            if len(raw) != length: raise AccessError('Incomplete JSON request')
            # Re-encoding also rejects JSON escaped lone surrogates.
            value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_constant)
            json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
            return value

        def _spoken_media(self, access, query, *, head=False):
            required = {'key', 'archive_sha256', 'target'}
            if set(query) not in (required, required | {'download'}): raise AccessError('Invalid audio query')
            if 'download' in query and query['download'] != '1': raise AccessError('Invalid download action')
            sent = False
            try:
                with access.audio(query['key'], query['archive_sha256'], query['target']) as (stream, size):
                    etag = '"' + query['archive_sha256'] + ':' + query['target'] + '"'
                    start, end = 0, size - 1; code = 200
                    ranges = self.headers.get_all('Range', [])
                    if not head and ranges and self.headers.get('If-Range', etag) == etag:
                        try:
                            if len(ranges) != 1: raise AccessError('Duplicate Range', 416)
                            start, end = byte_range(ranges[0], size); code = 206
                        except AccessError:
                            self.send_response(416); self.send_header('Content-Range', f'bytes */{size}')
                            self.send_header('Content-Length', '0'); self.send_header('Cache-Control', 'no-store')
                            sent = True; self.end_headers(); return
                    stream.seek(start)
                    self.send_response(code)
                    self.send_header('Content-Type', 'audio/wav'); self.send_header('Content-Length', str(end - start + 1))
                    self.send_header('Accept-Ranges', 'bytes'); self.send_header('Cache-Control', 'no-store')
                    self.send_header('ETag', etag)
                    if code == 206: self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                    if 'download' in query:
                        self.send_header('Content-Disposition', f'attachment; filename="spoken-{query["archive_sha256"][:24]}-{query["target"]}.wav"')
                    sent = True; self.end_headers()
                    if not head:
                        remaining = end - start + 1; previous = self.connection.gettimeout()
                        try:
                            self.connection.settimeout(10)
                            while remaining:
                                chunk = stream.read(min(65536, remaining))
                                if not chunk: raise AccessError('Audio changed while streaming', 409)
                                self.wfile.write(chunk); remaining -= len(chunk)
                        finally: self.connection.settimeout(previous)
            except (SpokenBriefError, OSError):
                if not sent: raise
                # A response has begun: never append a second JSON/HTTP response to a WAV.
                self.close_connection = True

        def _spoken_get(self, *, head=False):
            self._spoken_body_consumed = False
            if not self._spoken_host(): return self._spoken_error(AccessError('Loopback Host required', 403))
            try:
                if (self.headers.get_all('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) > 1
                        or self.headers.get('Content-Length', '0') != '0'):
                    raise AccessError('Read requests do not accept a body')
                path, query = self._spoken_query(); route = path.removeprefix(PREFIX)
                access = self._spoken_access()
                if route == '/audio': return self._spoken_media(access, query, head=head)
                if head: raise AccessError('HEAD is only supported for audio', 405)
                if route in ('/capabilities', '/archives'):
                    fields(query, ())
                    return self._json(200, access.status() if route == '/capabilities' else access.archives())
                if route == '/archive':
                    fields(query, ('key',)); return self._json(200, access.inspect(query['key']))
                if route in ('/report', '/review'):
                    fields(query, ('key', 'archive_sha256', 'id'))
                    reader = access.report if route == '/report' else access.saved_review
                    return self._json(200, reader(query['key'], query['archive_sha256'], query['id']))
                if route == '/chapters':
                    fields(query, ('key', 'archive_sha256')); digest(query['archive_sha256'])
                    value = access.inspect(query['key'])['archive']; require_archive(value, query['archive_sha256'])
                    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
                    name = f'spoken-{value["source"]["sha256"][:12]}-{value["manifest_sha256"][:12]}.chapters.json'
                    self.send_response(200); self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.send_header('Content-Length', str(len(raw))); self.send_header('Cache-Control', 'no-store')
                    self.send_header('Content-Disposition', f'attachment; filename="{name}"')
                    self.end_headers(); self.wfile.write(raw); return
                raise AccessError('Unknown Spoken Brief read operation', 404)
            except (BrokenPipeError, ConnectionResetError): self.close_connection = True
            except (SpokenBriefError, ValueError, TypeError, OSError, RecursionError) as exc:
                return self._spoken_error(exc)

        def do_GET(self):
            if urlsplit(self.path).path.startswith(PREFIX + '/'): return self._spoken_get()
            return super().do_GET()

        def do_HEAD(self):
            if urlsplit(self.path).path.startswith(PREFIX + '/'): return self._spoken_get(head=True)
            handler = getattr(super(), 'do_HEAD', None)
            if handler is not None: return handler()
            return self.send_error(501, 'Unsupported method (HEAD)')

        def do_POST(self):
            if not urlsplit(self.path).path.startswith(PREFIX + '/'): return super().do_POST()
            self._spoken_body_consumed = False
            if not self._spoken_origin(): return self._spoken_error(AccessError('Exact local same-origin request required', 403))
            try:
                path, query = self._spoken_query()
                if path not in (PREFIX + '/bookmark', PREFIX + '/review'):
                    raise AccessError('Unknown Spoken Brief write operation', 404)
                fields(query, ('key',)); value = self._spoken_body(); access = self._spoken_access()
                action = access.bookmark if path.endswith('/bookmark') else access.review
                return self._json(200, action(query['key'], value))
            except (BrokenPipeError, ConnectionResetError): self.close_connection = True
            except (SpokenBriefError, ValueError, TypeError, OSError, RecursionError) as exc:
                return self._spoken_error(exc)
    return SpokenHandler
