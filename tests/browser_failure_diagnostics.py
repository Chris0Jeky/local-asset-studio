"""Bounded transport evidence for synthetic browser fixtures; no request retries."""
import asyncio
from collections import deque
import re
import threading
from urllib.parse import urlsplit


_STARTUP_STATE = """() => {
  const text = document.querySelector('#narrationStatus')?.textContent || '';
  const kinds = ['completed', 'running', 'uncertain', 'prepared', 'partial', 'blocked',
    'Reading retained narration', 'File changed while opening:', 'File changed while reading:',
    'Source root changed', 'Configured source root changed', 'Invalid retained narration',
    'Retained narration identity differs', 'API unavailable'];
  return {ready_state: document.readyState, catalog_defined: typeof catalog !== 'undefined',
    selector_defined: typeof $ !== 'undefined', escape_defined: typeof esc !== 'undefined',
    narration_status: kinds.find(kind => text.startsWith(kind)) || (text ? 'unclassified' : 'empty')};
}"""


def url_identity(value):
    """Keep route identity without credentials, query values, fragments or media data."""
    try:
        parts = urlsplit(str(value))
        if parts.scheme and parts.scheme not in ('http', 'https'):
            return parts.scheme[:256] + ':<redacted>'
        host = parts.hostname or ''
        if ':' in host: host = '[' + host + ']'
        origin = (parts.scheme + '://' + host + (':' + str(parts.port) if parts.port else '')) if parts.netloc else ''
        keys = [field.partition('=')[0][:32] + '=<redacted>' for field in parts.query.split('&')[:8] if field]
        return (origin + parts.path + ('?' + '&'.join(keys) if keys else ''))[:256]
    except ValueError:
        return '<invalid-url>'


def failure_text(value):
    return re.sub(r'https?://[^\s<>]+', lambda match: url_identity(match.group()), str(value))[:256]


class BrowserFailureDiagnostics:
    """Retain failures separately so successful request churn cannot displace them."""
    _capture_timeout = 2

    def __init__(self):
        self._lock = threading.Lock()
        self._rows = {key: deque(maxlen=limit) for key, limit in (
            ('failed_requests', 40), ('responses', 100), ('server_errors', 40), ('page_states', 20))}
        self._dropped = {key: 0 for key in self._rows}
        self._pages = {}

    def _record(self, kind, value):
        with self._lock:
            rows = self._rows[kind]
            if len(rows) == rows.maxlen: self._dropped[kind] += 1
            rows.append(value)

    def watch(self, page, label):
        self._pages[page] = label
        def failed(request):
            self._record('failed_requests', {'page': label, 'url': url_identity(request.url),
                'method': request.method[:16], 'resource_type': request.resource_type[:32],
                'failure': failure_text(request.failure)})
        def response(value):
            request = value.request
            if (value.status >= 400 or request.resource_type == 'script'
                    or urlsplit(value.url).path.startswith('/api/spoken-briefs/narration')):
                self._record('responses', {'page': label, 'url': url_identity(value.url),
                    'method': request.method[:16], 'resource_type': request.resource_type[:32], 'status': value.status})
        page.on('requestfailed', failed)
        page.on('response', response)

    def server_error(self, handler, error):
        self._record('server_errors', {'url': url_identity(getattr(handler, 'path', '')),
            'method': str(getattr(handler, 'command', ''))[:16], 'type': type(error).__name__,
            'errno': getattr(error, 'errno', None), 'winerror': getattr(error, 'winerror', None)})

    def capture_page(self, page):
        """Only startup flags and a known status category; never source/form/body text."""
        value = {'page': self._pages.get(page, 'unknown')}
        try:
            value['url'] = url_identity(page.url)
            value.update(page.evaluate(_STARTUP_STATE))
        except Exception as error:
            value['capture_error_type'] = type(error).__name__
        self._record('page_states', value)

    async def capture_page_async(self, page):
        """Async Playwright equivalent; a failed renderer cannot replace the test failure."""
        value = {'page': self._pages.get(page, 'unknown')}
        try:
            value['url'] = url_identity(page.url)
            value.update(await asyncio.wait_for(page.evaluate(_STARTUP_STATE), self._capture_timeout))
        except Exception as error:
            value['capture_error_type'] = type(error).__name__
        self._record('page_states', value)

    def snapshot(self):
        with self._lock:
            return {**{key: list(rows) for key, rows in self._rows.items()}, 'dropped': dict(self._dropped)}
