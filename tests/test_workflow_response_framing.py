"""Valid JSON alone does not establish that its HTTP message arrived completely."""
from contextlib import redirect_stdout
from http.client import HTTPException, IncompleteRead
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from studio_workflow.client import Client, ClientError
from studio_workflow.agent_bridge import AgentBridge
from studio_workflow.core import canonical, digest
from studio_workflow.run_client import SavedRuns
from studio_workflow import __main__ as cli
import test_workflow_studio as fixture


class ResponseFramingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def log_message(self, *args): pass
            def do_GET(self): self.reply()
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                self.reply()
            def reply(self):
                cls.requests.append((self.command, self.path))
                self.send_response(cls.status)
                self.send_header('Connection', 'close')
                for key, value in cls.headers: self.send_header(key, value)
                self.end_headers()
                try: self.wfile.write(cls.body)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError): pass
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(5)

    def setUp(self):
        type(self).status = 200
        type(self).body = b'{"job":{"id":"known-job","status":"queued"},"seed":9223372036854775807}'
        type(self).headers = [('Content-Length', str(len(self.body)))]
        type(self).requests = []
        self.client = Client(self.url, timeout=2)

    def truncate(self): type(self).headers = [('Content-Length', str(len(self.body) + 11))]

    def test_valid_json_prefix_of_truncated_get_is_not_a_success(self):
        self.truncate()
        with self.assertRaises(IncompleteRead): self.client.request('/api/jobs/known-job')
        self.assertEqual(self.requests, [('GET', '/api/jobs/known-job')])

    def test_truncated_successful_post_stays_unknown_to_agent_and_is_not_retried(self):
        self.truncate()
        ticket = {'request_id': 'original-request'}
        result = AgentBridge(self.client, 'execute').invoke('recipe_run', {
            'ticket_json': canonical(ticket).decode(), 'approved_ticket_sha256': digest(ticket)})
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['code'], 'outcome_unknown')
        self.assertEqual(result['context']['request_id'], 'original-request')
        self.assertEqual(result['context']['ticket_sha256'], digest(ticket))
        self.assertEqual(self.requests, [('POST', '/api/workflow-studio/run')])

    def test_complete_content_length_and_close_delimited_preserve_result(self):
        for headers in (self.headers, []):
            with self.subTest(headers=headers):
                type(self).headers = headers
                self.assertEqual(self.client.request('/api/jobs/id'), json.loads(self.body))

    def test_chunked_reply_requires_terminal_chunk(self):
        value = self.body
        type(self).headers = [('Transfer-Encoding', 'chunked')]
        type(self).body = f'{len(value):X}\r\n'.encode() + value + b'\r\n0\r\n\r\n'
        self.assertEqual(self.client.request('/api/jobs/id'), json.loads(value))
        type(self).body = self.body[:-5]
        with self.assertRaises(IncompleteRead): self.client.request('/api/jobs/id')

    def test_malformed_duplicate_and_ambiguous_length_headers_are_rejected(self):
        for headers in ([('Content-Length', '-1')], [('Content-Length', 'not-a-number')],
                        [('Content-Length', str(len(self.body))), ('Content-Length', str(len(self.body) + 1))],
                        [('Transfer-Encoding', 'gzip')]):
            with self.subTest(headers=headers):
                type(self).headers = headers
                with self.assertRaises((ValueError, HTTPException)):
                    self.client.request('/api/jobs/id')
        type(self).headers = [('Transfer-Encoding', 'chunked'), ('Content-Length', str(len(self.body)))]
        type(self).body = f'{len(self.body):X}\r\n'.encode() + self.body + b'\r\n0\r\n\r\n'
        with self.assertRaises((ValueError, HTTPException)): self.client.request('/api/jobs/id')

    def test_duplicate_transfer_codings_are_not_hidden_by_first_header(self):
        value = self.body
        type(self).body = f'{len(value):X}\r\n'.encode() + value + b'\r\n0\r\n\r\n'
        for second in ('gzip', 'chunked'):
            with self.subTest(second=second):
                type(self).headers = [('Transfer-Encoding', 'chunked'), ('Transfer-Encoding', second)]
                with self.assertRaisesRegex(ValueError, 'Transfer-Encoding'):
                    self.client.request('/api/jobs/id')

    def test_equal_duplicate_lengths_are_not_a_false_conflict(self):
        length = str(len(self.body))
        for headers in ([('Content-Length', length), ('Content-Length', length)],
                        [('Content-Length', length + ', ' + length)]):
            with self.subTest(headers=headers):
                type(self).headers = headers
                self.assertEqual(self.client.request('/api/jobs/id'), json.loads(self.body))

    def test_actual_body_limit_applies_without_an_advertised_length(self):
        from studio_workflow.client import read_response
        for chunked in (False, True):
            for size in (32, 33):
                with self.subTest(chunked=chunked, size=size):
                    value = b'x' * size
                    type(self).headers = [('Transfer-Encoding', 'chunked')] if chunked else []
                    type(self).body = (f'{size:X}\r\n'.encode() + value + b'\r\n0\r\n\r\n'
                                       if chunked else value)
                    with self.client.opener.open(self.url + '/api/bytes', timeout=2) as response:
                        if size == 32:
                            self.assertEqual(read_response(response, 32), value)
                        else:
                            with self.assertRaisesRegex(ValueError, 'limit'): read_response(response, 32)

    def test_oversized_advertised_length_is_rejected_even_with_small_json_body(self):
        type(self).headers = [('Content-Length', str(16 * 1024 * 1024 + 1))]
        with self.assertRaisesRegex(ValueError, 'limit|16 MiB'):
            self.client.request('/api/jobs/id')

    def test_document_error_does_not_adopt_a_truncated_conflict_payload(self):
        type(self).status = 409
        type(self).body = b'{"error":"stale","code":"revision_conflict"}'
        self.truncate()
        with self.assertRaises(IncompleteRead):
            self.client.request('/api/workflow-studio/documents/doc/commands', {})

    def test_complete_document_conflict_keeps_machine_contract(self):
        type(self).status = 409
        type(self).body = b'{"error":"stale","code":"revision_conflict"}'
        type(self).headers = [('Content-Length', str(len(self.body)))]
        with self.assertRaises(ClientError) as caught:
            self.client.request('/api/workflow-studio/documents/doc/commands', {})
        self.assertEqual((caught.exception.status, caught.exception.code), (409, 'revision_conflict'))

    def test_saved_run_error_drops_unverified_body_but_retains_http_status(self):
        type(self).status = 409
        type(self).body = b'{"error":"stale","code":"revision_conflict"}'
        self.truncate()
        with self.assertRaises(ClientError) as caught: SavedRuns(self.client.request).get('original')
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(caught.exception.code, 'http_error')
        self.assertNotIn('stale', str(caught.exception))

    def test_agent_error_does_not_project_a_truncated_error_body(self):
        type(self).status = 409
        type(self).body = b'{"error":"stale","code":"revision_conflict"}'
        self.truncate()
        ticket = {'request_id': 'original-request'}
        result = AgentBridge(self.client, 'execute').invoke('recipe_run', {
            'ticket_json': canonical(ticket).decode(), 'approved_ticket_sha256': digest(ticket)})
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['http_status'], 409)
        self.assertEqual(result['error']['code'], 'http_error')
        self.assertEqual(json.loads(result['data_json']), {})
        self.assertIn('recovery', result['error'])
        self.assertEqual(len(self.requests), 1)

    def test_shortlist_does_not_present_a_truncated_error_as_complete(self):
        from studio_workflow.sdk import WorkflowClient
        type(self).status = 400
        type(self).body = b'{"error":"unverified diagnostic"}'
        self.truncate()
        with self.assertRaises(IncompleteRead): WorkflowClient(self.url).shortlist('new-image')
        self.assertEqual(len(self.requests), 1)

    def test_legacy_error_is_still_returned_unconsumed_for_its_caller(self):
        type(self).status = 400
        with self.assertRaises(HTTPError) as caught: self.client.request('/api/workflow-studio/open', {})
        with caught.exception as response:
            self.assertEqual(response.read(), self.body)


class AcceptedRunFramingTests(unittest.TestCase):
    setUp = fixture.HTTPTests.setUp
    close = fixture.HTTPTests.close

    def test_accepted_run_with_truncated_reply_preserves_ticket_for_explicit_recovery(self):
        ticket = Client(self.url).request('/api/workflow-studio/prepare', {'recipe': {'preset_id': 'example'}})
        path = Path(self.temp.name) / 'ticket.json'
        path.write_text(json.dumps(ticket), encoding='utf-8')
        original_bytes = path.read_bytes()
        target = Path(self.temp.name) / 'result.json'
        handler = self.server.RequestHandlerClass
        send_header = handler.send_header
        def truncated_header(instance, name, value):
            if instance.path == '/api/workflow-studio/run' and name.lower() == 'content-length':
                value = str(int(value) + 11)
            return send_header(instance, name, value)
        output = io.StringIO()
        with patch.object(handler, 'send_header', truncated_header), redirect_stdout(output):
            code = cli.main(['--url', self.url, 'run', '--ticket', str(path), '--approve', '--out', str(target)])
        result = json.loads(output.getvalue())
        self.assertEqual(self.studio.calls, 1)
        self.assertEqual(code, 3, result)
        self.assertFalse(target.exists(), 'Incomplete response must not be exported as a confirmed job')
        self.assertIn('same ticket', result['recovery'])
        self.assertEqual(path.read_bytes(), original_bytes)
        # Explicit same-ticket recovery uses the server's existing idempotency owner.
        recovered = Client(self.url).request('/api/workflow-studio/run', {'ticket': ticket, 'approved': True})
        self.assertEqual(recovered['job']['id'], next(iter(self.studio.jobs)))
        self.assertEqual(self.studio.calls, 1)


if __name__ == '__main__': unittest.main()
