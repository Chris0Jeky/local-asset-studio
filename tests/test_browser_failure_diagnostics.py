"""Failures retain transport identity without payloads or longer readiness waits."""
import asyncio
from types import SimpleNamespace
import unittest

from browser_failure_diagnostics import BrowserFailureDiagnostics, url_identity


class Page:
    def __init__(self): self.listeners = {}
    def on(self, event, callback): self.listeners[event] = callback
    def emit(self, event, value): self.listeners[event](value)


class Request:
    method = 'GET'; resource_type = 'script'
    def __init__(self, url, failure='net::ERR_CONNECTION_RESET'):
        self.url = url; self.failure = failure
    @property
    def post_data(self): raise AssertionError('Diagnostics must not read private request payloads')
    @property
    def headers(self): raise AssertionError('Diagnostics must not read credentials')


class BrowserFailureDiagnosticTests(unittest.TestCase):
    def test_failed_script_and_http_status_survive_successful_request_churn(self):
        page = Page(); evidence = BrowserFailureDiagnostics(); evidence.watch(page, 'second-tab')
        request = Request('http://127.0.0.1:8191/static/app.js')
        page.emit('requestfailed', request)
        for index in range(140):
            other = Request('http://127.0.0.1:8191/static/other-' + str(index) + '.js')
            page.emit('response', SimpleNamespace(request=other, url=other.url, status=200))
        value = evidence.snapshot()
        self.assertEqual(value['failed_requests'], [{'page': 'second-tab', 'url': request.url,
            'method': 'GET', 'resource_type': 'script', 'failure': 'net::ERR_CONNECTION_RESET'}])
        self.assertEqual(len(value['responses']), 100)
        self.assertEqual(value['dropped']['responses'], 40)
        self.assertEqual(value['dropped']['failed_requests'], 0)

    def test_response_statuses_distinguish_script_and_narration_failures(self):
        page = Page(); evidence = BrowserFailureDiagnostics(); evidence.watch(page, 'reload')
        for path, kind, status in [('/static/app.js', 'script', 404),
                ('/api/spoken-briefs/narration?key=private-words', 'fetch', 400),
                ('/api/spoken-briefs/narration?key=private-words', 'fetch', 200),
                ('/api/catalog', 'fetch', 200)]:
            request = Request('http://127.0.0.1:8191' + path); request.resource_type = kind
            page.emit('response', SimpleNamespace(request=request, url=request.url, status=status))
        value = evidence.snapshot()
        self.assertEqual([row['status'] for row in value['responses']], [404, 400, 200])
        self.assertNotIn('private-words', str(value))

    def test_request_and_server_failures_redact_credentials_and_query_values(self):
        page = Page(); evidence = BrowserFailureDiagnostics(); evidence.watch(page, 'synthetic')
        url = 'http://user:secret@127.0.0.1:8191/static/app.js?note=private-words#private-fragment'
        page.emit('requestfailed', Request(url, 'net::ERR_FAILED ' + url))
        error = ConnectionAbortedError(103, 'private-words'); error.winerror = 10053
        evidence.server_error(SimpleNamespace(path='/static/app.js?token=private-token', command='GET'), error)
        value = evidence.snapshot()
        self.assertEqual(value['server_errors'], [{'url': '/static/app.js?token=<redacted>',
            'method': 'GET', 'type': 'ConnectionAbortedError', 'errno': 103, 'winerror': 10053}])
        self.assertIn('net::ERR_FAILED http://127.0.0.1:8191/static/app.js?note=<redacted>', str(value))
        for private in ('user:secret', 'private-words', 'private-fragment', 'private-token'):
            self.assertNotIn(private, str(value))
        self.assertEqual(url_identity('data:text/plain,private-words'), 'data:<redacted>')

    def test_closed_renderer_diagnostic_cannot_replace_original_failure(self):
        class ClosedPage(Page):
            url = 'http://127.0.0.1:8191/?key=private-words'
            def evaluate(self, _): raise RuntimeError('renderer unavailable: private-words')
        page = ClosedPage(); evidence = BrowserFailureDiagnostics(); evidence.watch(page, 'reload')
        original = AssertionError('original failed assertion')
        with self.assertRaises(AssertionError) as caught:
            try: raise original
            finally: evidence.capture_page(page)
        self.assertIs(caught.exception, original)
        self.assertEqual(evidence.snapshot()['page_states'], [{'page': 'reload',
            'url': 'http://127.0.0.1:8191/?key=<redacted>', 'capture_error_type': 'RuntimeError'}])


class AsyncBrowserFailureDiagnosticTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_startup_capture_awaits_the_renderer_and_redacts_the_url(self):
        class AsyncPage(Page):
            url = 'http://127.0.0.1:8191/?key=private-words#private-fragment'
            async def evaluate(self, _):
                return {'ready_state': 'complete', 'catalog_defined': False,
                        'selector_defined': False, 'escape_defined': False}
        page = AsyncPage(); evidence = BrowserFailureDiagnostics(); evidence.watch(page, '390px reload')
        await evidence.capture_page_async(page)
        self.assertEqual(evidence.snapshot()['page_states'], [{'page': '390px reload',
            'url': 'http://127.0.0.1:8191/?key=<redacted>', 'ready_state': 'complete',
            'catalog_defined': False, 'selector_defined': False, 'escape_defined': False}])

    async def test_async_renderer_failure_preserves_the_original_failure(self):
        class ClosedPage(Page):
            url = 'http://127.0.0.1:8191/?key=private-words'
            async def evaluate(self, _): raise RuntimeError('renderer unavailable: private-words')
        page = ClosedPage(); evidence = BrowserFailureDiagnostics(); evidence.watch(page, '390px reload')
        original = AssertionError('original readiness failure')
        with self.assertRaises(AssertionError) as caught:
            try: raise original
            finally: await evidence.capture_page_async(page)
        self.assertIs(caught.exception, original)
        self.assertEqual(evidence.snapshot()['page_states'], [{'page': '390px reload',
            'url': 'http://127.0.0.1:8191/?key=<redacted>', 'capture_error_type': 'RuntimeError'}])

    async def test_async_capture_of_a_stalled_renderer_is_bounded_and_cleans_up(self):
        cancelled = []
        class StalledPage(Page):
            url = 'http://127.0.0.1:8191/#create'
            async def evaluate(self, _):
                try: await asyncio.Future()
                finally: cancelled.append(True)
        page = StalledPage(); evidence = BrowserFailureDiagnostics(); evidence.watch(page, '390px reload')
        evidence._capture_timeout = .01
        await evidence.capture_page_async(page)
        self.assertEqual(cancelled, [True])
        self.assertEqual(evidence.snapshot()['page_states'], [{'page': '390px reload',
            'url': 'http://127.0.0.1:8191/', 'capture_error_type': 'TimeoutError'}])


if __name__ == '__main__': unittest.main()
