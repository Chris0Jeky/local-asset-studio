"""Opt-in routes on the existing Studio handler; no second port, queue or model worker."""
import base64
import hashlib
import sqlite3
from urllib.parse import urlparse

from studio_workflow.addressable_figures import split_figures
from studio_workflow.http_body import reject_json
from .core import fields, need, decode, profiles, compile_brief, apply_proposal, bind_graph, canonical
from .recipe_intake import inspect_media


def _typed_value_error(exc):
    """Return a domain HTTP response without relying on one exception class identity."""
    response = getattr(exc, 'response', None)
    status = getattr(exc, 'status', None)
    if not callable(response) or type(status) is not int or not 400 <= status <= 599:
        return None
    value = response()
    return (status, value) if isinstance(value, dict) else None


def dispatch(path, value, studio=None):
    if path == '/api/prompt/reference-review/inspect':
        from .reference_review import inspect
        return inspect(value)
    if path == '/api/prompt/reference-review/preview':
        from .reference_review import preview
        return preview(value)
    if path == '/api/prompt/compile':
        fields(value, ('intent','profile_id')); return compile_brief(value['intent'],value['profile_id'])
    if path == '/api/prompt/apply':
        fields(value, ('intent','proposal','accepted_fields')); return apply_proposal(value['intent'],value['proposal'],value['accepted_fields'])
    if path == '/api/prompt/metadata':
        fields(value, (), ('png_base64', 'media_base64', 'sidecar_base64', 'output_node'))
        keys = [key for key in ('png_base64', 'media_base64') if key in value]
        need(len(keys) == 1, 'Supply exactly one media payload')
        def unpack(key):
            data = value[key]
            need(isinstance(data, str) and len(data) <= 3000000, 'Media payload too large')
            return base64.b64decode(data, validate=True)
        raw = unpack(keys[0])
        if keys[0] == 'png_base64':
            need(raw.startswith(b'\x89PNG\r\n\x1a\n'), 'Legacy payload requires PNG bytes')
        return inspect_media(raw, unpack('sidecar_base64') if 'sidecar_base64' in value else None,
                             value.get('output_node'))
    if path == '/api/prompt/bind':
        fields(value, ('compiled','binding')); need(studio is not None,'Studio binding context unavailable')
        binding=value['binding']; preset=studio.preset(binding['preset_id'])
        need(not any(preset.get(k) for k in ('reference','last_reference','reference_slots','requires_rgba_mask'))
             and not any((preset.get('bindings_extra') or {}).get(k) for k in ('reference','last_reference')),
             'Reference-bearing presets require an explicit source handoff; text-only binding is unavailable')
        graph,path=studio.graph_for(preset)
        for key,target in binding['bindings'].items():
            need(preset.get(key)==target and not preset.get('bindings_extra',{}).get(key),'Binding differs from registered preset or has unhandled companions')
        raw=path.read_bytes(); need(decode(raw)==graph,'Template changed during binding')
        result=bind_graph(value['compiled'],graph,binding)
        result['expected_template_sha256']=hashlib.sha256(raw).hexdigest()
        result['batch_count']=1
        result['submission_payload']={k:result[k] for k in ('preset_id','controls','expected_template_sha256','batch_count')}
        return result
    raise ValueError('Unknown prompt operation')


def extend_handler(base):
    class PromptHandler(base):
        def do_GET(self):
            if urlparse(self.path).path != '/api/prompt/profiles': return super().do_GET()
            if not self._safe_host(): return self._json(403,{'error':'Loopback Host required'})
            return self._json(200,{'profiles':list(profiles().values()),'generation_submitted':False})

        def do_POST(self):
            path = urlparse(self.path).path
            if path == '/api/assets/split-figures':
                if not self._safe_mutation(): return reject_json(self,403,{'error':'Local same-origin request required'})
                try:
                    if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                        return reject_json(self,400,{'error':'application/json required','generation_submitted':False})
                    body=self.rfile.read(self._content_length(1024*1024))
                    return self._json(201,split_figures(self.studio.assets,decode(body)))
                except sqlite3.Error:
                    return self._json(503,{
                        'error':'Asset storage could not confirm this request. Check its receipt before retrying the exact command.',
                        'code':'asset_storage_unconfirmed',
                        'generation_submitted':False,
                    })
                except OSError as exc:
                    return self._json(500,{'error':'Local figure split failed: '+str(exc)[:200],
                                           'generation_submitted':False})
                except ValueError as exc:
                    domain = _typed_value_error(exc)
                    if domain is not None: return self._json(*domain)
                    return self._json(400,{'error':str(exc),'generation_submitted':False})
                except (KeyError,TypeError,IndexError,RecursionError) as exc:
                    return self._json(400,{'error':str(exc),'generation_submitted':False})
            if not path.startswith('/api/prompt/'): return super().do_POST()
            if not self._safe_mutation(): return reject_json(self,403,{'error':'Local same-origin request required'})
            try:
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                    return reject_json(self,400,{'error':'application/json required','generation_submitted':False})
                # Only reference review accepts four original images; every source
                # has its own byte/pixel cap and no input is persisted or executed.
                limit = 1024*1024
                if self.path == '/api/prompt/reference-review/preview':
                    from .reference_review import HTTP_LIMIT
                    limit = HTTP_LIMIT
                body=self.rfile.read(self._content_length(limit))
                result=dispatch(self.path,decode(body, limit=limit),self.studio)
                return self._json(200,result)
            except (ValueError,KeyError,TypeError,IndexError,RecursionError,OSError) as exc:
                return self._json(400,{'error':str(exc),'generation_submitted':False})
    # Compose at the existing extension seam; no second server or worker.
    from studio_workflow.http_extension import extend_handler as workflow_handler
    from .reference_job_http import extend_handler as reference_job_handler
    from .project_http import extend_handler as project_handler
    from studio_spoken.http import extend_handler as spoken_handler
    return spoken_handler(project_handler(reference_job_handler(workflow_handler(PromptHandler))))
