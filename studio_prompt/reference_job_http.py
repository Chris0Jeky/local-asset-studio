"""Same-origin operation commands on Studio's existing HTTP server, not inference threads."""
import sqlite3
from urllib.parse import parse_qs, urlparse
from studio_workflow.http_body import reject_json
from .schema import decode, need

PREFIX='/api/prompt/reference-jobs/'


def extend_handler(base):
    class ReferenceJobHandler(base):
        def _reference_service(self):
            service=getattr(self.studio,'reference_jobs',None)
            need(service is not None,'Reference analysis service is unavailable in this host')
            return service

        def _reference_error(self,exc):
            if isinstance(exc,sqlite3.Error) or isinstance(exc,OSError):
                return self._json(503,{'error':'Analysis storage could not confirm this operation. Check the same request ID; do not resubmit.',
                    'code':'reference_storage_unconfirmed','generation_submitted':False})
            status=getattr(exc,'status',404 if str(exc).startswith('Unknown analysis request') else 400)
            return self._json(status,{'error':str(exc),'generation_submitted':False})

        def do_GET(self):
            parsed=urlparse(self.path)
            if not parsed.path.startswith(PREFIX):return super().do_GET()
            if not self._safe_host():return self._json(403,{'error':'Loopback Host required'})
            try:
                service=self._reference_service()
                if self.path==PREFIX+'capabilities':return self._json(200,service.capabilities())
                need(parsed.path==PREFIX+'status','Unknown reference read route')
                query=parse_qs(parsed.query,keep_blank_values=True,max_num_fields=2)
                need(set(query)=={'workspace_id','request_id'} and all(len(v)==1 for v in query.values()),'Supply one workspace and request identity')
                return self._json(200,service.get(query['workspace_id'][0],query['request_id'][0]))
            except (ValueError,TypeError,KeyError,RecursionError,OSError,sqlite3.Error) as exc:return self._reference_error(exc)

        def do_POST(self):
            if not urlparse(self.path).path.startswith(PREFIX):return super().do_POST()
            if not self._safe_mutation():return reject_json(self,403,{'error':'Local same-origin request required'})
            if self.path not in (PREFIX+'create',PREFIX+'cancel',PREFIX+'release',PREFIX+'retire'):
                return reject_json(self,400,{'error':'Unknown reference command route','generation_submitted':False})
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                return reject_json(self,400,{'error':'application/json required','generation_submitted':False})
            try:
                service=self._reference_service()
            except (ValueError,TypeError,KeyError,IndexError,RecursionError,OSError,sqlite3.Error) as exc:
                return self._reference_error(exc)
            held=None;limit=64*1024
            if self.path==PREFIX+'create':
                # Admission precedes the large body read as well as image decoding.
                try:admitted=service.intake.acquire(blocking=False)
                except (ValueError,TypeError,KeyError,IndexError,RecursionError,OSError,sqlite3.Error) as exc:
                    return self._reference_error(exc)
                if not admitted:
                    return reject_json(self,409,{'error':'Reference intake is busy. Nothing was queued.', 'generation_submitted':False})
                held=service.intake;limit=48*1024*1024
            try:
                raw=self.rfile.read(self._content_length(limit));value=decode(raw,limit=limit)
                if self.path==PREFIX+'create':return self._json(202,service._create(value))
                if self.path==PREFIX+'retire':return self._json(200,service.retire(value))
                return self._json(200,service.cancel(value) if self.path.endswith('/cancel') else service.release(value))
            except (ValueError,TypeError,KeyError,IndexError,RecursionError,OSError,sqlite3.Error) as exc:return self._reference_error(exc)
            finally:
                if held is not None:held.release()
    return ReferenceJobHandler
