"""Saved-run receipts, exact review and explicit dispatch via the existing worker."""
import sqlite3
from urllib.parse import parse_qs, urlsplit

from .core import MAX_BYTES, canonical, decode, need
from .documents import DocumentError
from .execution import RunAdmissionRefused
from .document_runs import DocumentRuns
from .document_http import store as document_store
from .http_body import reject_json

PREFIX = '/api/workflow-studio/document-runs'


def store(studio):
    with studio.lock:
        documents = document_store(studio)
        cached = getattr(studio, '_workflow_document_runs', None)
        if cached is None or cached.documents is not documents:
            cached = DocumentRuns(documents)
            studio._workflow_document_runs = cached
        return cached


def route(studio, path, value=None):
    parsed = urlsplit(path)
    need(not parsed.fragment, 'Fragments are not accepted')
    query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
    need(all(len(v) == 1 for v in query.values()), 'Duplicate query parameter')
    if value is not None:
        need(not query, 'POST routes do not accept query parameters')
        if parsed.path == PREFIX: return store(studio).prepare(studio, value)
        parts = parsed.path[len(PREFIX) + 1:].split('/')
        need(parsed.path.startswith(PREFIX + '/') and len(parts) == 2 and parts[1] == 'run',
             'Unknown saved-run POST route')
        from .saved_dispatch import run_saved
        return run_saved(studio, store(studio), parts[0], value)
    if parsed.path == PREFIX:
        need('document_id' in query and set(query) <= {'document_id', 'before', 'limit'},
             'Specify document_id and optional before/limit')
        def number(key, default):
            if key not in query: return default
            raw = query[key][0]
            need(raw.isascii() and raw.isdigit() and len(raw) <= 16, 'Invalid ' + key)
            return int(raw)
        return store(studio).list(query['document_id'][0], before=number('before', None), limit=number('limit', 25))
    need(not query and parsed.path.startswith(PREFIX + '/'), 'Unknown saved-run route')
    parts = parsed.path[len(PREFIX) + 1:].split('/')
    if len(parts) == 1: return store(studio).get(parts[0])
    if len(parts) == 2 and parts[0] == 'by-job': return store(studio).by_job(parts[1])
    if len(parts) == 2 and parts[1] == 'review':
        from .saved_dispatch import review_saved
        return review_saved(store(studio), parts[0])
    if len(parts) == 2 and parts[1] == 'observe': return store(studio).observe(studio, parts[0])
    raise DocumentError('not_found', 'Unknown saved-run operation', 404)


def extend_handler(base):
    class RunRecordHandler(base):
        def _run_record_route(self):
            path = urlsplit(self.path).path
            return path == PREFIX or path.startswith(PREFIX + '/')

        def _run_record_reply(self, value=None):
            dispatch_route = value is not None and urlsplit(self.path).path.endswith('/run')
            def failure(status, result):
                # Encoding/storage/transport errors may occur after the dispatch
                # seam. The HTTP wrapper cannot assert that no work was attempted.
                result.pop('generation_submitted', None)
                result['dispatch_attempted'] = None if dispatch_route else False
                if dispatch_route:
                    result['recovery'] = 'Observe the original saved run; do not prepare a replacement.'
                return self._json(status, result)
            try:
                result = route(self.studio, self.path, value)
                need(len(canonical(result)) <= 2 * MAX_BYTES, 'Saved-run reply exceeds 2 MiB')
                return self._json(200, result)
            except RunAdmissionRefused as exc:
                return self._json(exc.status, exc.response())
            except DocumentError as exc:
                result = exc.result(); result.pop('generation_submitted', None)
                return failure(exc.status, result)
            except sqlite3.Error:
                return failure(503, {'error': 'Saved-run storage is unavailable', 'code': 'storage_unavailable',
                    'recovery': 'Retain the same preparation request ID and inspect its record.', 'dispatch_attempted': False})
            except OSError:
                return failure(503, {'error': 'Saved-run preparation or storage is unavailable', 'code': 'operation_unavailable',
                    'recovery': 'Retain the same preparation request ID and inspect its record.', 'dispatch_attempted': False})
            except (ValueError, KeyError, TypeError, IndexError, RecursionError) as exc:
                return failure(400, {'error': str(exc), 'code': 'invalid_run_record_request'})

        def do_GET(self):
            if not self._run_record_route(): return super().do_GET()
            if not self._safe_host(): return self._json(403, {'error': 'Loopback Host required'})
            return self._run_record_reply()

        def do_POST(self):
            if not self._run_record_route(): return super().do_POST()
            if not self._safe_mutation(): return reject_json(self, 403, {'error': 'Local same-origin request required'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return reject_json(self, 400, {'error': 'application/json required', 'code': 'invalid_request',
                                               'dispatch_attempted': False})
            try:
                value = decode(self.rfile.read(self._content_length(MAX_BYTES)))
                need(isinstance(value, dict), 'JSON object required')
            except (ValueError, OSError, RecursionError) as exc:
                return self._json(400, {'error': str(exc), 'code': 'invalid_request', 'dispatch_attempted': False})
            return self._run_record_reply(value)
    return RunRecordHandler
