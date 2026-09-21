"""Collection protocol adapter on the existing same-origin Studio handler."""
import sqlite3
from urllib.parse import parse_qsl, urlsplit
from .core import decode
from .http_body import reject_json
from .collection_commands import CollectionError, MAX_COMMAND_BYTES, RECOVERY, require

PREFIX = '/api/collections'
STATUS_PREFIX = PREFIX + '/commands/'


def _path(raw):
    parsed = urlsplit(raw)
    require(not parsed.scheme and not parsed.netloc and not parsed.fragment, 'Relative collection route required')
    return parsed


def status(raw, workspace):
    parsed = _path(raw)
    require(parsed.path.startswith(STATUS_PREFIX), 'Unknown collection status route')
    require(bool(parsed.query), 'Workspace identity is required', status=428, code='collection_precondition_required')
    query = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True, max_num_fields=1)
    require(len(query) == 1 and query[0][0] == 'workspace_id', 'Supply exactly one workspace_id query parameter')
    return workspace.collection_status(parsed.path[len(STATUS_PREFIX):], query[0][1])


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
            if not self._safe_host(): return self._json(403, CollectionError('Loopback Host required').response())
            return self._collection_reply(lambda: status(self.path, self.studio.assets))

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
            return self._collection_reply(lambda: self.studio.assets.collection(value))
    return CollectionHandler
