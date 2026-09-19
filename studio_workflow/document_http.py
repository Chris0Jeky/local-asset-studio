"""Shared document routes; no ComfyUI call is reachable from this module."""
import sqlite3
from urllib.parse import urlsplit
from .core import decode, need
from .commands import apply_commands, fields, StateConflict
from .documents import WorkflowDocuments, DocumentError
from .http_body import reject_json

PREFIX = '/api/workflow-studio/documents'


def store(studio):
    with studio.lock:
        cached = getattr(studio, '_workflow_documents', None)
        if cached is None or cached.workspace is not studio.assets:
            cached = WorkflowDocuments(studio.assets)
            studio._workflow_documents = cached
        return cached


def route(path, value, studio):
    parsed = urlsplit(path)
    need(not parsed.query and not parsed.fragment, 'Document routes do not accept query parameters')
    path = parsed.path
    if path == PREFIX + '/plan':
        from .command_plan import plan_commands
        fields(value, ('document', 'commands'))
        return plan_commands(value['document'], value['commands'])
    if path in (PREFIX + '/modules/export', PREFIX + '/modules/inspect'):
        from .modules import export_module, validate_module
        from .core import digest
        if path.endswith('/export'):
            fields(value, ('document', 'step_id'))
            module = export_module(value['document'], value['step_id'])
        else:
            fields(value, ('module',))
            module = validate_module(value['module'])
        return {'module': module, 'module_sha256': digest(module), 'generation_submitted': False}
    if path == PREFIX + '/reduce':
        fields(value, ('document', 'commands'))
        return {'document': apply_commands(value['document'], value['commands']),
                'committed': False, 'generation_submitted': False}
    if path == PREFIX:
        return store(studio).list() if value is None else store(studio).create(value)
    need(path.startswith(PREFIX + '/'), 'Unknown document route')
    parts = path[len(PREFIX) + 1:].split('/')
    repository = store(studio)
    if value is None:
        if len(parts) == 5 and parts[1] == 'revisions' and parts[2].isascii() and parts[2].isdigit() and parts[3] == 'modules':
            return repository.export_module(parts[0], parts[4], int(parts[2]))
        if len(parts) == 1: return repository.get(parts[0])
        if len(parts) == 2 and parts[1] == 'history': return repository.history(parts[0])
        if len(parts) == 3 and parts[1] == 'revisions' and parts[2].isdigit():
            return repository.get(parts[0], int(parts[2]))
    elif len(parts) == 2:
        key, action = parts
        if action == 'commands': return repository.command(key, value)
        if action == 'preview': return repository.preview(key, value)
        if action == 'plan': return repository.plan(key, value)
        if action == 'restore': return repository.command(key, value, restore=True)
        if action == 'fork': return repository.fork(key, value)
    raise DocumentError('not_found', 'Unknown document operation', 404)


def extend_handler(base):
    class DocumentHandler(base):
        def _document_route(self):
            path = urlsplit(self.path).path
            return path == PREFIX or path.startswith(PREFIX + '/')

        def _document_reply(self, value):
            try:
                return self._json(200, route(self.path, value, self.studio))
            except StateConflict as exc:
                return self._json(409, {'error': str(exc), 'code': 'document_state_conflict',
                    'expected_sha256': exc.expected_sha256, 'current_sha256': exc.current_sha256,
                    'generation_submitted': False})
            except DocumentError as exc:
                return self._json(exc.status, exc.result())
            except (ValueError, KeyError, TypeError, IndexError, RecursionError) as exc:
                return self._json(400, {'error': str(exc), 'code': 'invalid_document_command', 'generation_submitted': False})
            except (sqlite3.Error, OSError):
                return self._json(503, {'error': 'Workflow storage is unavailable', 'code': 'storage_unavailable',
                    'generation_submitted': False, 'recovery': 'Retain the same request ID and content; inspect before retrying.'})

        def do_GET(self):
            if not self._document_route(): return super().do_GET()
            if not self._safe_host(): return self._json(403, {'error': 'Loopback Host required'})
            return self._document_reply(None)

        def do_POST(self):
            if not self._document_route(): return super().do_POST()
            if not self._safe_mutation(): return reject_json(self, 403, {'error': 'Local same-origin request required'})
            try:
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    return reject_json(self, 400, {'error': 'application/json required', 'code': 'invalid_request',
                                                   'generation_submitted': False})
                value = decode(self.rfile.read(self._content_length(1048576)))
                need(isinstance(value, dict), 'JSON object required')
            except (ValueError, OSError, RecursionError) as exc:
                return self._json(400, {'error': str(exc), 'code': 'invalid_request', 'generation_submitted': False})
            return self._document_reply(value)
    return DocumentHandler
