"""Bounded loopback transport shared by CLI and SDK. Never retries writes."""
from __future__ import annotations
import json
import math
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from urllib.error import HTTPError
from .core import canonical, need


class ClientError(ValueError):
    def __init__(self, status, result):
        self.status = status
        self.result = result if isinstance(result, dict) else {'error': 'Studio request failed'}
        self.code = self.result.get('code', 'http_error')
        super().__init__(self.result.get('error', 'Studio request failed'))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirect refused; use the actual loopback Studio address')


class Client:
    def __init__(self, base='http://127.0.0.1:8191', timeout=30):
        parsed = urlsplit(base)
        need(parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', '::1')
             and not parsed.username and not parsed.password and parsed.path in ('', '/')
             and not parsed.query and not parsed.fragment, 'Use a literal loopback HTTP Studio origin')
        need(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 120, 'HTTP timeout must be 0–120 seconds')
        self.base, self.timeout = base.rstrip('/'), timeout
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, path, body=None):
        need(isinstance(path, str) and path.startswith('/api/') and not path.startswith('//'), 'Studio API path required')
        raw = canonical(body) if body is not None else None
        request = Request(self.base + path, data=raw,
                          headers={'Origin': self.base, 'Content-Type': 'application/json', 'Accept': 'application/json'})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                data = response.read(16 * 1024 * 1024 + 1)
                need(len(data) <= 16 * 1024 * 1024, 'Response exceeds 16 MiB')
                result = json.loads(data)
                need(isinstance(result, dict), 'Studio returned a non-object response')
                return result
        except HTTPError as exc:
            # Preserve the public Client exception contract for pre-existing routes.
            prefix = '/api/workflow-studio/documents'
            if path != prefix and not path.startswith(prefix + '/'):
                raise
            with exc:
                raw = exc.read(1048576 + 1)
            try:
                result = json.loads(raw) if len(raw) <= 1048576 else {}
            except (ValueError, UnicodeError): result = {}
            raise ClientError(exc.code, result) from exc
