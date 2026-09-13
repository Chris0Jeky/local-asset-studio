"""Same-origin preparation receipts and read-only lineage; no execution endpoint."""
import sqlite3
from urllib.parse import parse_qs, urlsplit

from .core import MAX_BYTES, canonical, decode, need
from .documents import DocumentError
from .document_runs import DocumentRuns
from .document_http import store as document_store

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
        need(parsed.path == PREFIX and not query, 'Only saved-run preparation accepts POST')
        return store(studio).prepare(studio, value)
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
    if len(parts) == 2 and parts[1] == 'observe': return store(studio).observe(studio, parts[0])
    raise DocumentError('not_found', 'Unknown saved-run operation', 404)


def extend_handler(base):
    class RunRecordHandler(base):
        def _run_record_route(self):
            path = urlsplit(self.path).path
            return path == PREFIX or path.startswith(PREFIX + '/')

        def _run_record_reply(self, value=None):
            try:
                result = route(self.studio, self.path, value)
                need(len(canonical(result)) <= 2 * MAX_BYTES, 'Saved-run reply exceeds 2 MiB')
                return self._json(200, result)
            except DocumentError as exc:
                result = exc.result(); result.pop('generation_submitted', None)
                return self._json(exc.status, {**result, 'dispatch_attempted': False})
            except sqlite3.Error:
                return self._json(503, {'error': 'Saved-run storage is unavailable', 'code': 'storage_unavailable',
                    'recovery': 'Retain the same preparation request ID and inspect its record.', 'dispatch_attempted': False})
            except OSError:
                return self._json(503, {'error': 'Saved-run preparation or storage is unavailable', 'code': 'operation_unavailable',
                    'recovery': 'Retain the same preparation request ID and inspect its record.', 'dispatch_attempted': False})
            except (ValueError, KeyError, TypeError, IndexError, RecursionError) as exc:
                return self._json(400, {'error': str(exc), 'code': 'invalid_run_record_request', 'dispatch_attempted': False})

        def do_GET(self):
            if not self._run_record_route(): return super().do_GET()
            if not self._safe_host(): return self._json(403, {'error': 'Loopback Host required'})
            return self._run_record_reply()

        def do_POST(self):
            if not self._run_record_route(): return super().do_POST()
            if not self._safe_mutation(): return self._json(403, {'error': 'Local same-origin request required'})
            try:
                need(self.headers.get('Content-Type', '').split(';')[0] == 'application/json', 'application/json required')
                value = decode(self.rfile.read(self._content_length(MAX_BYTES)))
                need(isinstance(value, dict), 'JSON object required')
            except (ValueError, OSError, RecursionError) as exc:
                return self._json(400, {'error': str(exc), 'code': 'invalid_request', 'dispatch_attempted': False})
            return self._run_record_reply(value)
    return RunRecordHandler
