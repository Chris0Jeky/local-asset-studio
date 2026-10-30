"""Explicit single-user visibility scopes; never authentication or encryption.

Stored classification belongs to a job/asset. HTTP scope is a caller choice and
must never change a shared Studio root or a worker's already admitted intent.
"""
from urllib.parse import parse_qs, urlsplit


class PrivacyError(ValueError):
    def __init__(self, message, *, status=400, code='privacy_invalid'):
        super().__init__(message); self.status, self.code = status, code

    def response(self):
        return {'error':str(self),'code':self.code}


def normalize(value, allow_all=False):
    if type(value) is not str or value not in (('regular','private','all') if allow_all else ('regular','private')):
        raise PrivacyError('Choose regular or private'+(' or all for browsing' if allow_all else ' for this creation'))
    return value


def matches(classification, scope):
    return type(classification) is str and classification in ('regular','private') and scope in (classification,'all')


def _header(handler, name):
    headers=getattr(handler,'headers',{})
    values=headers.get_all(name) if hasattr(headers,'get_all') else ([headers[name]] if name in headers else None)
    if values is None:return None
    if len(values)!=1:raise PrivacyError('Supply exactly one '+name+' header')
    return values[0]


def scope_for_handler(handler):
    query=parse_qs(urlsplit(handler.path).query,keep_blank_values=True).get('privacy')
    header=_header(handler,'X-Studio-Privacy')
    if query is not None and len(query)!=1:raise PrivacyError('Supply exactly one privacy scope')
    selected=query[0] if query is not None else header if header is not None else 'regular'
    if query is not None and header is not None and query[0]!=header:
        raise PrivacyError('Privacy query and header disagree')
    return normalize(selected,allow_all=True)


def creation_for_handler(handler, payload=None):
    header=_header(handler,'X-Studio-Creation-Privacy')
    present=isinstance(payload,dict) and 'privacy' in payload
    selected=payload['privacy'] if present else header if header is not None else 'regular'
    if present and header is not None and payload['privacy']!=header:
        raise PrivacyError('Creation privacy and header disagree')
    return normalize(selected)


def scoped_url(url, privacy):
    return url+('&' if '?' in url else '?')+'privacy=private' if privacy=='private' else url


def unavailable(kind='Item'):
    raise PrivacyError(kind+' not found',status=404,code='not_found')


# The supported creation paths all capture classification explicitly. Other
# project owners retain regular-only storage and must not accept a private header
# while their strict JSON schemas omit that field.
PRIVATE_POSTS=frozenset(('/api/jobs','/api/upload','/api/assets/import','/api/assets/reference',
    '/api/assets/export','/api/assets/update','/api/collections','/api/looks/prepare',
    '/api/preview','/api/wildcards/preview','/api/recipe-check','/api/estimate','/api/references/check',
    '/api/backends/switch','/api/backends/resolve-switch','/api/runtime-recovery/retry',
    '/api/gpu-lease','/api/gpu-lease/release','/api/models/install','/api/folders/open','/api/workflow-inspect',
    '/api/repair/prepare'))
PRIVATE_POST_PREFIXES=('/api/assets/','/api/collections/','/api/jobs/')


def origin_target(raw):
    """One interpretation of the request target before any composed route can dispatch."""
    try:
        parsed=urlsplit(raw)
        if raw.startswith('/') and not raw.startswith('//') and not (parsed.scheme or parsed.netloc or parsed.fragment) and '#' not in raw:
            return parsed.path
    except ValueError:pass
    raise PrivacyError('Use a relative origin-form request target without a fragment',code='privacy_invalid_target')


def extend_handler(base):
    class PrivacyHandler(base):
        def _privacy_error(self, exc, *, drain=False):
            if drain:self._drain_refused_body()
            return self._json(exc.status,exc.response())

        def do_GET(self):
            try:path=origin_target(self.path)
            except PrivacyError as exc:return self._privacy_error(exc)
            if path.startswith('/api/'):
                if not self._safe_host():return self._json(403,{'error':'Loopback Host required'})
                try:scope_for_handler(self)
                except PrivacyError as exc:return self._privacy_error(exc)
            return super().do_GET()

        def do_POST(self):
            try:path=origin_target(self.path)
            except PrivacyError as exc:return self._privacy_error(exc,drain=True)
            if path.startswith('/api/'):
                if not self._safe_host():return self._json(403,{'error':'Loopback Host required'})
                try:
                    scope_for_handler(self)
                    classification=creation_for_handler(self)
                    if classification=='private' and path not in PRIVATE_POSTS and not path.startswith(PRIVATE_POST_PREFIXES):
                        raise PrivacyError('This workflow does not yet support private creation. Your draft is retained; choose an image workflow or deliberately switch this creation to regular.',code='private_workflow_unsupported')
                except PrivacyError as exc:return self._privacy_error(exc,drain=True)
            return super().do_POST()
    return PrivacyHandler
