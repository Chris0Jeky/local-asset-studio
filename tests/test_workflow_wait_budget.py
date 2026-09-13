"""Observation expiry must not issue another request or masquerade as output failure."""
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import patch
from urllib.error import URLError

from studio_workflow import __main__ as cli
from studio_workflow.client import Client


class Clock:
    def __init__(self, oversleep=0): self.now = 0; self.oversleep = oversleep
    def monotonic(self): return self.now
    def sleep(self, seconds): self.now += seconds + self.oversleep


class Observer:
    def __init__(self, clock, replies, costs=(), timeout=30):
        self.clock, self.replies = clock, iter(replies)
        self.costs, self.timeout, self.calls = iter(costs), timeout, []
    def request(self, path, body=None):
        assert body is None, 'Observation must not send a body'
        self.calls.append((self.clock.now, self.timeout, path))
        self.clock.now += next(self.costs, 0)
        reply = next(self.replies)
        if isinstance(reply, Exception): raise reply
        return reply


class WaitBudgetTests(unittest.TestCase):
    def invoke(self, observer, clock, *args):
        output = io.StringIO()
        with patch.object(cli, 'Client', return_value=observer), patch.object(cli, 'time', clock), redirect_stdout(output):
            code = cli.main(list(args))
        return code, json.loads(output.getvalue())

    def test_no_poll_starts_at_the_deadline(self):
        clock = Clock(); observer = Observer(clock, [{'status': 'running', 'sequence': i} for i in range(5)])
        code, result = self.invoke(observer, clock, 'wait', 'job', '--seconds', '.2', '--interval', '.1')
        self.assertEqual([at for at, _, _ in observer.calls], [0, .1])
        self.assertEqual(code, 4)
        self.assertEqual(result['job']['sequence'], 1)
        self.assertEqual(result['status'], 'observation_timeout')

    def test_overslept_interval_does_not_start_another_poll(self):
        clock = Clock(oversleep=.5); observer = Observer(clock, [{'status': 'waiting'}] * 4)
        code, result = self.invoke(observer, clock, 'wait', 'job', '--seconds', '.2', '--interval', '.1')
        self.assertEqual(len(observer.calls), 1)
        self.assertEqual(code, 4)
        self.assertIn('not cancelled', result['message'])

    def test_each_socket_timeout_is_capped_to_remaining_budget_and_restored(self):
        clock = Clock(); observer = Observer(clock, [{'status': 'queued'}, {'status': 'completed'}], costs=[.05])
        code, _ = self.invoke(observer, clock, 'wait', 'job', '--seconds', '.3', '--interval', '.1')
        self.assertEqual(code, 0)
        self.assertAlmostEqual(observer.calls[0][1], .3)
        self.assertAlmostEqual(observer.calls[1][1], .15)
        self.assertEqual(observer.timeout, 30)

    def test_shorter_configured_http_timeout_is_not_increased(self):
        clock = Clock(); observer = Observer(clock, [{'status': 'completed'}], timeout=.05)
        code, _ = self.invoke(observer, clock, '--http-timeout', '.05', 'wait', 'job', '--seconds', '2')
        self.assertEqual(code, 0)
        self.assertEqual(observer.calls[0][1], .05)
        self.assertEqual(observer.timeout, .05)

    def test_terminal_response_is_preserved_even_if_observation_finished_late(self):
        for state, expected in (('completed', 0), ('uncertain', 3), ('failed', 5), ('partial', 5), ('cancelled', 5)):
            clock = Clock(); reply = {'status': state, 'seed': 2**63 - 1}
            observer = Observer(clock, [reply], costs=[.5])
            with self.subTest(state=state):
                code, result = self.invoke(observer, clock, 'wait', 'job', '--seconds', '.1')
                self.assertEqual((code, result), (expected, reply))
                self.assertEqual(len(observer.calls), 1)
                self.assertEqual(observer.timeout, 30)

    def test_later_transport_failure_is_not_stdout_failure(self):
        clock = Clock(); observer = Observer(clock, [{'status': 'running'}, URLError(ConnectionRefusedError('offline'))])
        code, result = self.invoke(observer, clock, 'wait', 'job', '--seconds', '1', '--interval', '.1')
        self.assertEqual(code, 2)
        self.assertIn('offline', result['error'])
        self.assertNotEqual(result.get('code'), 'stdout_unavailable')
        self.assertNotIn('response_received', result)
        self.assertEqual(len(observer.calls), 2)
        self.assertEqual(observer.timeout, 30)

    def test_timeout_at_budget_expiry_retains_last_observation_without_retry(self):
        for error in (TimeoutError('read expired'), URLError(TimeoutError('read expired'))):
            clock = Clock(); last = {'status': 'running', 'id': 'original', 'seed': 2**63 - 1}
            observer = Observer(clock, [last, error], costs=[0, .1])
            with self.subTest(error=type(error).__name__):
                code, result = self.invoke(observer, clock, 'wait', 'job', '--seconds', '.2', '--interval', '.1')
                self.assertEqual(code, 4)
                self.assertEqual(result['job'], last)
                self.assertIn('not cancelled', result['message'])
                self.assertEqual(len(observer.calls), 2)
                self.assertEqual(observer.timeout, 30)

    def test_first_request_timeout_at_expiry_does_not_invent_a_job_state(self):
        clock = Clock(); observer = Observer(clock, [TimeoutError('read expired')], costs=[.1])
        code, result = self.invoke(observer, clock, 'wait', 'job', '--seconds', '.1')
        self.assertEqual(code, 4)
        self.assertIsNone(result['job'])
        self.assertEqual(len(observer.calls), 1)
        self.assertEqual(observer.timeout, 30)

    def test_early_socket_timeout_and_invalid_parameters_remain_errors(self):
        clock = Clock(); observer = Observer(clock, [TimeoutError('early timeout')], costs=[.05], timeout=.05)
        code, result = self.invoke(observer, clock, '--http-timeout', '.05', 'wait', 'job', '--seconds', '2')
        self.assertEqual(code, 2); self.assertIn('early timeout', result['error'])
        for args in (('--seconds', 'nan'), ('--seconds', 'inf'), ('--seconds', '0'), ('--interval', '0')):
            with self.subTest(args=args):
                observer = Observer(clock, [])
                code, _ = self.invoke(observer, clock, 'wait', 'job', *args)
                self.assertEqual(code, 2)
                self.assertFalse(observer.calls)

    def test_status_is_one_unmodified_observation(self):
        clock = Clock(); observer = Observer(clock, [{'status': 'running'}])
        code, result = self.invoke(observer, clock, 'status', 'job')
        self.assertEqual(code, 0); self.assertEqual(result, {'status': 'running'})
        self.assertEqual(observer.calls, [(0, 30, '/api/jobs/job')])

    def test_real_loopback_gets_use_the_remaining_timeout_and_original_id(self):
        calls, timeouts = [], []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self):
                calls.append(('GET', self.path))
                body = json.dumps({'status': 'running', 'id': 'job/with?part', 'seed': 2**63 - 1}).encode()
                self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
            def do_POST(self):
                calls.append(('POST', self.path)); self.send_error(405)
        http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
        self.addCleanup(lambda: (http.shutdown(), http.server_close(), thread.join(5)))
        clock = Clock(); client = Client(f'http://127.0.0.1:{http.server_port}')
        original_open = client.opener.open
        def opening(request, *, timeout):
            timeouts.append(timeout); return original_open(request, timeout=timeout)
        client.opener = SimpleNamespace(open=opening)
        code, result = self.invoke(client, clock, 'wait', 'job/with?part', '--seconds', '.1', '--interval', '.1')
        self.assertEqual(code, 4)
        self.assertEqual(calls, [('GET', '/api/jobs/job%2Fwith%3Fpart')])
        self.assertEqual(timeouts, [.1])
        self.assertEqual(result['job']['seed'], 2**63 - 1)
        self.assertEqual(client.timeout, 30)


if __name__ == '__main__': unittest.main()
