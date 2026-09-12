"""Small, loopback-only client for the Studio Scene editor HTTP contract."""
from __future__ import annotations

import http.client
import json
from urllib.parse import urlsplit


MAX_BODY=1024*1024
MAX_RESPONSE=4*1024*1024


class StudioClientError(RuntimeError):
    """The Studio did not accept or return a valid Scene editor request."""


class StudioClient:
    """One-request-at-a-time client: no proxy, redirect, retry, or mutation replay."""
    def __init__(self, url: str, timeout: float=10, body_limit: int=MAX_BODY, response_limit: int=MAX_RESPONSE):
        parsed=urlsplit(url)
        if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost') or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:
            raise StudioClientError('Studio URL must be an http://127.0.0.1 or http://localhost origin')
        try:port=parsed.port or 80
        except ValueError as exc:raise StudioClientError('Studio URL has an invalid port') from exc
        if port<1 or port>65535:raise StudioClientError('Studio URL has an invalid port')
        if not isinstance(timeout,(int,float)) or timeout<=0:raise StudioClientError('Timeout must be positive')
        if not isinstance(body_limit,int) or not isinstance(response_limit,int) or body_limit<1 or response_limit<1:raise StudioClientError('Client limits must be positive')
        self.host=parsed.hostname;self.port=port;self.timeout=timeout;self.body_limit=body_limit;self.response_limit=response_limit
        self.origin='http://'+self.host+((':'+str(port)) if port!=80 else '')

    def request(self, method: str, path: str, payload=None):
        if method not in ('GET','POST') or not isinstance(path,str) or not path.startswith('/') or '\\' in path or '\x00' in path:
            raise StudioClientError('Unsupported Studio request')
        body=None;headers={'Accept':'application/json'}
        if payload is not None:
            try:body=json.dumps(payload,separators=(',',':')).encode('utf-8')
            except (TypeError,ValueError) as exc:raise StudioClientError('Studio payload must be JSON') from exc
            if len(body)>self.body_limit:raise StudioClientError('Studio request body is too large')
            headers.update({'Content-Type':'application/json','Origin':self.origin})
        connection=http.client.HTTPConnection(self.host,self.port,timeout=self.timeout)
        try:
            connection.request(method,path,body=body,headers=headers);response=connection.getresponse()
            if 300<=response.status<400:raise StudioClientError('Studio redirects are not allowed')
            length=response.getheader('Content-Length')
            if length is not None and (not length.isdigit() or int(length)>self.response_limit):raise StudioClientError('Studio response is too large')
            raw=response.read(self.response_limit+1)
            if len(raw)>self.response_limit:raise StudioClientError('Studio response is too large')
        except (OSError,http.client.HTTPException) as exc:raise StudioClientError('Studio request failed: '+str(exc)) from exc
        finally:connection.close()
        try:data=json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError,json.JSONDecodeError) as exc:raise StudioClientError('Studio returned invalid JSON') from exc
        if not isinstance(data,dict):raise StudioClientError('Studio returned an invalid JSON object')
        if response.status<200 or response.status>=300:raise StudioClientError(str(data.get('error') or 'Studio request failed'))
        return data

    def list(self):return self.request('GET','/api/av')
    def inspect(self, identifier: str):return self.request('GET','/api/av/'+self._identifier(identifier))
    def workspace(self):return self.request('GET','/api/workspace')
    def create(self, payload: dict, actor='cli'):
        command=self._command(payload,actor);command['action']='create';return self.request('POST','/api/av',command)
    def command(self, identifier: str, payload: dict, actor='cli'):
        return self.request('POST','/api/av/'+self._identifier(identifier),self._command(payload,actor))

    @staticmethod
    def _identifier(identifier):
        if not isinstance(identifier,str) or len(identifier)>128 or not identifier.isascii() or not identifier.isalnum():raise StudioClientError('Invalid scene identifier')
        return identifier

    @staticmethod
    def _command(payload, actor):
        if not isinstance(payload,dict):raise StudioClientError('Studio command must be a JSON object')
        if actor not in ('agent','cli'):raise StudioClientError('Actor must be agent or cli')
        result=dict(payload);result['actor']=actor;return result
