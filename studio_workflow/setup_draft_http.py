"""Loopback/same-origin setup draft routes over the existing Workspace."""
import sqlite3
from urllib.parse import urlsplit
from .core import decode, need
from .http_body import reject_json
from .setup_drafts import SetupDrafts, SetupError, PREFIX, MAX_COMMAND


def route(path,value,studio):
    parsed=urlsplit(path)
    from .setup_history import READ_ACTIONS, read_route
    parts=parsed.path[len(PREFIX)+1:].split('/') if parsed.path.startswith(PREFIX+'/') else []
    if len(parts)==2 and parts[1] in READ_ACTIONS:
        need(value is None, 'Setup history is read-only')
        return read_route(path,studio.assets)
    need(not parsed.query and not parsed.fragment,'Setup draft routes do not accept query parameters')
    repository=SetupDrafts(studio)
    if parsed.path==PREFIX:return repository.list() if value is None else repository.command(value)
    need(value is None and parsed.path.startswith(PREFIX+'/'),'Unknown setup draft operation')
    parts=parsed.path[len(PREFIX)+1:].split('/')
    if len(parts)==1:return repository.get(parts[0])
    if len(parts)==2 and parts[0]=='requests':return repository.recover(parts[1])
    if len(parts)==3 and parts[1] in ('revisions','check') and parts[2].isascii() and parts[2].isdigit():
        return repository.check(parts[0],int(parts[2])) if parts[1]=='check' else repository.get(parts[0],int(parts[2]))
    raise SetupError('setup_not_found','Unknown setup draft read',404)


def extend_handler(base):
    class SetupDraftHandler(base):
        def _setup_route(self):
            path=urlsplit(self.path).path
            return path==PREFIX or path.startswith(PREFIX+'/')
        def _setup_reply(self,value):
            try:return self._json(200,route(self.path,value,self.studio))
            except SetupError as exc:return self._json(exc.status,exc.result())
            except (ValueError,KeyError,TypeError,IndexError,RecursionError) as exc:
                return self._json(getattr(exc,'status',400),{'error':str(exc),'code':getattr(exc,'code','invalid_setup_command'),'generation_submitted':False})
            except (OSError,sqlite3.Error):
                return self._json(503,{'error':'Setup storage is unavailable. Inspect the original request receipt; do not submit a replacement automatically.',
                                      'code':'setup_storage_unavailable','generation_submitted':False})
        def do_GET(self):
            if not self._setup_route():return super().do_GET()
            if not self._safe_host():return self._json(403,{'error':'Loopback Host required'})
            return self._setup_reply(None)
        def do_POST(self):
            if not self._setup_route():return super().do_POST()
            if not self._safe_mutation():return reject_json(self,403,{'error':'Local same-origin request required'})
            try:
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                    return reject_json(self,400,{'error':'application/json required','generation_submitted':False})
                value=decode(self.rfile.read(self._content_length(MAX_COMMAND)))
                need(type(value) is dict,'JSON object required')
            except (ValueError,OSError,RecursionError) as exc:return self._json(400,{'error':str(exc),'generation_submitted':False})
            return self._setup_reply(value)
    return SetupDraftHandler
