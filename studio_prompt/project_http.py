"""Scoped prompt-document commands on the existing same-origin Studio handler."""
import sqlite3
from urllib.parse import parse_qs,urlsplit
from studio_workflow.http_body import reject_json
from .schema import decode,need
from .projects import FLAGS,REQUEST_LIMIT,ProjectError

PREFIX='/api/prompt/projects/'


def extend_handler(base):
    class ProjectHandler(base):
        def _prompt_project_service(self):
            service=getattr(self.studio,'prompt_projects',None)
            if service is None:raise ProjectError('projects_unavailable','Prompt projects are unavailable in this Studio host',503)
            return service
        def _prompt_project_error(self,error):
            if isinstance(error,(sqlite3.Error,OSError)):
                return self._json(503,{'error':'Storage could not confirm this save. Check the same request before an explicit exact retry.',
                    'code':'project_storage_unconfirmed',**FLAGS})
            result=error.response() if hasattr(error,'response') else {'error':str(error),'code':'invalid_project_command'}
            return self._json(getattr(error,'status',400),{**result,**FLAGS})
        def do_GET(self):
            parsed=urlsplit(self.path)
            if not parsed.path.startswith(PREFIX):return super().do_GET()
            if not self._safe_host():return self._json(403,{'error':'Loopback Host required',**FLAGS})
            try:
                service=self._prompt_project_service();route=parsed.path[len(PREFIX):]
                if route=='capabilities':
                    need(not parsed.query,'Capabilities do not take a query');return self._json(200,service.capabilities())
                required={'list':{'workspace_id'},'read':{'workspace_id','id'},'history':{'workspace_id','id'},
                          'status':{'workspace_id','request_id'}}
                need(route in required,'Unknown prompt project read route')
                params=parse_qs(parsed.query,keep_blank_values=True,max_num_fields=4)
                optional={'read':{'revision'},'history':{'before'}}.get(route,set())
                need(required[route]<=params.keys()<=required[route]|optional and all(len(v)==1 for v in params.values()),'Supply exact scoped query fields')
                params={k:v[0] for k,v in params.items()}
                for key in optional&params.keys():
                    need(params[key].isascii() and params[key].isdigit(),'Invalid revision query');params[key]=int(params[key])
                scope=params['workspace_id']
                if route=='list':result=service.list(scope)
                elif route=='read':result=service.get(scope,params['id'],params.get('revision'))
                elif route=='history':result=service.history(scope,params['id'],params.get('before'))
                else:result=service.status(scope,params['request_id'])
                return self._json(200,result)
            except (ValueError,TypeError,KeyError,IndexError,RecursionError,OSError,sqlite3.Error) as error:return self._prompt_project_error(error)
        def do_POST(self):
            parsed=urlsplit(self.path)
            if not parsed.path.startswith(PREFIX):return super().do_POST()
            if not self._safe_mutation():return reject_json(self,403,{'error':'Local same-origin request required',**FLAGS})
            route=parsed.path[len(PREFIX):]
            if parsed.query or route not in ('create','save','restore'):
                return reject_json(self,400,{'error':'Unknown prompt project command route','code':'invalid_project_command',**FLAGS})
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                return reject_json(self,400,{'error':'application/json required','code':'invalid_project_command',**FLAGS})
            try:
                value=decode(self.rfile.read(self._content_length(REQUEST_LIMIT)))
                return self._json(200,self._prompt_project_service().command(route,value))
            except (ValueError,TypeError,KeyError,IndexError,RecursionError,OSError,sqlite3.Error) as error:return self._prompt_project_error(error)
    return ProjectHandler
