"""Collection protocol adapter on the existing same-origin Studio handler."""
import base64
import hashlib
import re
import sqlite3
from urllib.parse import parse_qsl, urlsplit
from .core import canonical, decode
from .http_body import reject_json
from .collection_commands import CollectionError, MAX_COMMAND_BYTES, RECOVERY, require

PREFIX = '/api/collections'
STATUS_PREFIX = PREFIX + '/commands/'


def page_query(raw):
    require(len(raw) <= 4096, 'Collection query exceeds its bound')
    parsed = _path(raw)
    require(parsed.path == PREFIX, 'Relative collection list route required')
    require(re.search(r'%(?![0-9a-fA-F]{2})', parsed.query) is None, 'Malformed query escape')
    pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True,
                      encoding='utf-8', errors='strict', max_num_fields=4)
    query = dict(pairs)
    require(len(query) == len(pairs) and all(value for _, value in pairs)
            and set(query) <= {'workspace_id','limit','cursor','privacy'}, 'Invalid collection query fields')
    if 'limit' in query:
        require(re.fullmatch(r'[0-9]{1,3}',query['limit']) is not None, 'Invalid page size')
        query['limit'] = int(query['limit'])
    return query


def encode_cursor(position):
    envelope = {'position':position,'sha256':hashlib.sha256(canonical(position)).hexdigest()}
    return base64.urlsafe_b64encode(canonical(envelope)).decode('ascii').rstrip('=')


def collection_cursor(value):
    from .asset_reads import HEX32, ENTITY, _integer
    error = {'code':'collection_cursor_invalid','status':400}
    require(type(value) is str and 0 < len(value) <= 2048
            and re.fullmatch(r'[A-Za-z0-9_-]+',value), 'Invalid collection cursor', **error)
    try:
        raw = base64.b64decode(value+'='*((-len(value))%4), altchars=b'-_', validate=True)
        envelope = decode(raw.decode('utf-8'))
        require(type(envelope) is dict and set(envelope) == {'position','sha256'}, 'Invalid collection cursor', **error)
        body = envelope['position']
        require(type(body) is dict and {'format','workspace_id','catalogue','limit','last'} <= set(body)
                <= {'format','workspace_id','catalogue','limit','last','privacy'},
                'Invalid collection cursor position', **error)
        stamp = body['catalogue']
        require(canonical(envelope) == raw and envelope['sha256'] == hashlib.sha256(canonical(body)).hexdigest()
                and body['format'] == 'studio.collection-cursor/v1'
                and type(body['workspace_id']) is str and HEX32.fullmatch(body['workspace_id'])
                and _integer(body['limit'],1,100) and type(body['last']) is list and len(body['last']) == 2 and type(body['last'][0]) is str and 0 < len(body['last'][0]) <= 100
                and type(body['last'][1]) is str and ENTITY.fullmatch(body['last'][1])
                and type(stamp) is dict and set(stamp) == {'epoch','revision'}
                and type(stamp['epoch']) is str and HEX32.fullmatch(stamp['epoch']) and _integer(stamp['revision'])
                and body.get('privacy','regular') in ('regular','private','all'),
                'Invalid collection cursor values or checksum', **error)
        return body
    except (ValueError,TypeError,OverflowError,RecursionError) as exc:
        if isinstance(exc,CollectionError): raise
        raise CollectionError('Invalid collection cursor encoding', **error) from exc


def _path(raw):
    parsed = urlsplit(raw)
    require(not parsed.scheme and not parsed.netloc and not parsed.fragment, 'Relative collection route required')
    return parsed


def status(raw, workspace, privacy=None):
    parsed = _path(raw)
    require(parsed.path.startswith(STATUS_PREFIX), 'Unknown collection status route')
    require(bool(parsed.query), 'Workspace identity is required', status=428, code='collection_precondition_required')
    pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True, max_num_fields=2)
    query = dict(pairs)
    require(len(query) == len(pairs) and 'workspace_id' in query and set(query) <= {'workspace_id','privacy'}, 'Supply exactly one workspace_id query parameter')
    require(privacy is None or 'privacy' not in query or query['privacy']==privacy, 'Privacy scopes disagree', code='privacy_invalid')
    return workspace.collection_status(parsed.path[len(STATUS_PREFIX):], query['workspace_id'], privacy=privacy or query.get('privacy','regular'))


def extend_handler(base):
    class CollectionHandler(base):
        def _collection_route(self):
            path = self.path.split('?', 1)[0]
            return path == PREFIX or path.startswith(STATUS_PREFIX)

        def _collection_reply(self, action):
            try:
                result, code = action(), 200
            except ValueError as exc:
                if callable(getattr(exc, 'response', None)):
                    result, code = exc.response(), exc.status
                else:
                    result, code = CollectionError(str(exc)).response(), 400
            except (sqlite3.Error, OSError):
                code = 503
                result = CollectionError('Collection storage outcome is unconfirmed', status=503,
                    code='collection_storage_unconfirmed', outcome='unknown', recovery=RECOVERY).response()
            # Response loss cannot roll back or relabel an already committed row.
            try: return self._json(code, result)
            except (BrokenPipeError, ConnectionResetError): return None

        def do_GET(self):
            if not self._collection_route(): return super().do_GET()
            if self.path.split('?',1)[0] == PREFIX:
                # Reads have no uncertain-command outcome or retry advice.
                from .asset_read_http import _error
                try:
                    if not self._safe_host(): return self._json(403,_error(ValueError('Loopback Host required')))
                    from creation_privacy import scope_for_handler
                    query = page_query(self.path); query['privacy'] = scope_for_handler(self)
                    result, code = self.studio.assets.collection_page(**query), 200
                except (ValueError,RecursionError) as exc:
                    result, code = _error(exc), getattr(exc,'status',400)
                except (sqlite3.Error,OSError):
                    result, code = _error(CollectionError('Collection catalogue is unavailable',code='collection_read_unavailable')), 503
                try: return self._json(code,result)
                except (BrokenPipeError,ConnectionResetError): return None
            if not self._safe_host(): return self._json(403, CollectionError('Loopback Host required').response())
            def observation():
                from creation_privacy import scope_for_handler
                return status(self.path, self.studio.assets, privacy=scope_for_handler(self))
            return self._collection_reply(observation)

        def do_POST(self):
            if not self._collection_route(): return super().do_POST()
            if not self._safe_mutation():
                self.close_connection = True
                return reject_json(self, 403, CollectionError('Local same-origin request required').response())
            body_started = False
            try:
                parsed = _path(self.path)
                if parsed.path != PREFIX:
                    self.close_connection = True
                    return reject_json(self, 405, CollectionError('Status lookup is read-only').response())
                require(not parsed.query, 'Collection writes do not accept query parameters')
                require(self.headers.get('Content-Type', '').split(';', 1)[0].strip().lower() == 'application/json', 'application/json required')
                lengths = self.headers.get_all('Content-Length') or []
                require(len(lengths) == 1 and not self.headers.get_all('Transfer-Encoding'), 'Unambiguous fixed-length JSON body required')
                length = lengths[0].strip()
                require(length.isascii() and length.isdigit(), 'Invalid Content-Length')
                size = self._content_length(MAX_COMMAND_BYTES)
                body_started = True
                raw = self.rfile.read(size)
                require(len(raw) == size, 'Incomplete JSON body')
                raw.decode('utf-8')
                require(b'\x00' not in raw, 'JSON transport must use UTF-8 without literal NUL')
                value = decode(raw)
                require(isinstance(value, dict), 'Collection command must be an object')
            except (ValueError, OSError, RecursionError) as exc:
                # Early refusals may drain the unread body. Once reading has
                # started, draining the declared length again would consume the
                # next pipelined request, not this malformed JSON body.
                if body_started:
                    if isinstance(exc, OSError): self.close_connection = True
                    return self._json(400, CollectionError(str(exc)).response())
                self.close_connection = True
                return reject_json(self, 400, CollectionError(str(exc)).response())
            def command():
                from creation_privacy import scope_for_handler, creation_for_handler
                privacy = scope_for_handler(self)
                if value.get('action','create') == 'create':
                    privacy = (creation_for_handler(self,value) if 'privacy' in value or self.headers.get('X-Studio-Creation-Privacy') is not None
                               else 'private' if privacy=='private' else 'regular')
                return self.studio.assets.collection(value, privacy=privacy)
            return self._collection_reply(command)
    return CollectionHandler
