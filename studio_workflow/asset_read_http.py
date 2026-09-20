"""Read-only catalogue routes on Studio's existing Host/Origin boundary."""
import re
import sqlite3
import time
from urllib.parse import parse_qsl, urlsplit

from .asset_reads import AssetReadError, DEFAULT_FILTERS, require
from .core import decode
from .http_body import reject_json

PAGE = '/api/assets/page'
SELECTION = '/api/assets/selection'
MAX_QUERY = 4096
MAX_BODY = 32768
BODY_TIMEOUT = 5


def _error(exc):
    if callable(getattr(exc, 'response', None)):
        result = exc.response()
    else:
        result = {'error': str(exc), 'code': getattr(exc, 'code', 'asset_read_invalid')}
    return dict(result, observation_only=True, generation_submitted=False, media_bytes_verified=False)


def page_query(raw):
    require(len(raw) <= MAX_QUERY, 'Asset query exceeds its bound')
    parsed = urlsplit(raw)
    require(parsed.path == PAGE and not parsed.scheme and not parsed.netloc and not parsed.fragment,
            'Relative asset page route required')
    require(re.search(r'%(?![0-9a-fA-F]{2})', parsed.query) is None, 'Malformed query escape')
    pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True,
                      encoding='utf-8', errors='strict', max_num_fields=8)
    query = dict(pairs)
    require(len(query) == len(pairs) and all(value for _, value in pairs),
            'Asset query fields must be nonempty and occur once')
    require(set(query) <= set(DEFAULT_FILTERS) | {'workspace_id', 'limit', 'cursor'}, 'Unknown asset query field')
    if 'limit' in query:
        require(re.fullmatch(r'[0-9]{1,3}', query['limit']) is not None, 'Invalid page size')
        query['limit'] = int(query['limit'])
    filters = {key: query.pop(key) for key in DEFAULT_FILTERS if key in query}
    if 'favorite' in filters:
        require(filters['favorite'] in ('true', 'false'), 'Favorite must be true or false')
        filters['favorite'] = filters['favorite'] == 'true'
    return dict(query, filters=filters)


def _body(handler):
    # read1 returns after one underlying read, allowing an absolute deadline
    # rather than extending an idle timeout indefinitely for a slow sender.
    deadline = time.monotonic() + BODY_TIMEOUT
    prior_timeout = handler.connection.gettimeout()
    chunks, remaining = [], handler._content_length(MAX_BODY)
    require(remaining > 0, 'A JSON observation body is required')
    try:
        while remaining:
            seconds = deadline - time.monotonic()
            require(seconds > 0, 'Asset observation body timed out', status=408)
            handler.connection.settimeout(seconds if prior_timeout is None else min(seconds, prior_timeout))
            chunk = handler.rfile.read1(min(remaining, 8192))
            require(bool(chunk), 'Incomplete asset observation body')
            chunks.append(chunk)
            remaining -= len(chunk)
        require(time.monotonic() <= deadline, 'Asset observation body timed out', status=408)
        value = decode(b''.join(chunks).decode('utf-8'))
    finally:
        handler.connection.settimeout(prior_timeout)
    require(type(value) is dict and set(value) == {'workspace_id', 'ids'},
            'Supply exactly workspace_id and ids for selection inspection')
    return value


def extend_handler(base):
    class AssetReadHandler(base):
        def _asset_read_route(self):
            return self.path.split('?', 1)[0] in (PAGE, SELECTION)

        def _asset_read_reply(self, action):
            try:
                result, status = action(), 200
            except (ValueError, RecursionError) as exc:
                result, status = _error(exc), getattr(exc, 'status', 400)
            except (sqlite3.Error, OSError):
                result, status = _error(AssetReadError('Asset catalogue is unavailable',
                    code='asset_read_unavailable')), 503
            try:
                return self._json(status, result)
            except (BrokenPipeError, ConnectionResetError):
                return None

        def do_GET(self):
            if not self._asset_read_route(): return super().do_GET()
            if not self._safe_host(): return self._json(403, _error(ValueError('Loopback Host required')))
            if self.path.split('?', 1)[0] != PAGE:
                return self._json(405, _error(ValueError('Selection inspection requires POST')))
            return self._asset_read_reply(lambda: self.studio.assets.asset_page(**page_query(self.path)))

        def do_POST(self):
            if not self._asset_read_route(): return super().do_POST()
            if not self._safe_mutation():
                self.close_connection = True
                return reject_json(self, 403, _error(ValueError('Local same-origin request required')))
            if self.path.split('?', 1)[0] != PAGE:
                pass
            else:
                self.close_connection = True
                return reject_json(self, 405, _error(ValueError('Asset pages require GET')))
            started = False
            try:
                require(self.path == SELECTION, 'Selection inspection takes no query parameters')
                require(self.headers.get('Content-Type', '').split(';', 1)[0].strip().lower() == 'application/json',
                        'application/json required')
                lengths = self.headers.get_all('Content-Length') or []
                require(len(lengths) == 1 and not self.headers.get_all('Transfer-Encoding'),
                        'Unambiguous fixed-length JSON body required')
                require(re.fullmatch(r'[0-9]{1,5}', lengths[0].strip()) is not None, 'Invalid Content-Length')
                self._content_length(MAX_BODY)
                started = True
                value = _body(self)
            except (ValueError, OSError, RecursionError) as exc:
                self.close_connection = True
                status = 408 if isinstance(exc, TimeoutError) else getattr(exc, 'status', 400)
                result = _error(ValueError('Asset observation body timed out')) if status == 408 else _error(exc)
                return self._json(status, result) if started else reject_json(self, status, result)
            return self._asset_read_reply(lambda: self.studio.assets.asset_selection(**value))
    return AssetReadHandler
