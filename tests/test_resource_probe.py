import io
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from resource_probe import (MAX_RESPONSE_BYTES, ProcessObservation, ResourceSampler, counter,
                                fetch_stats, physical_memory, project_stats, write_samples)


STATS = {'system': {'comfyui_version': '0.35.0', 'pytorch_version': '2.9.1', 'argv': ['PRIVATE']},
         'devices': [{'name': 'PRIVATE', 'vram_total': 160, 'vram_free': 40,
                      'torch_vram_total': 120, 'torch_vram_free': 20}]}


class FakeProcess:
    def __init__(self): self.created = 100; self.cpu = 2; self.denied = False
    def create_time(self): return self.created
    def memory_info(self):
        if self.denied: raise PermissionError('PRIVATE')
        return NS(rss=30, private=50, vms=1000)
    def cpu_times(self): return NS(user=self.cpu, system=1)


class ProbeTests(unittest.TestCase):
    def test_physical_memory_is_not_commit_or_working_set(self):
        process = FakeProcess()
        provider = NS(virtual_memory=lambda: NS(total=320, available=100), Process=lambda pid: process)
        sampler = ResourceSampler([12], provider=provider, commit_reader=lambda: {'available_bytes': 600, 'limit_bytes': 900, 'committed_bytes': 300})
        record = sampler.sample()
        self.assertEqual(record['physical_ram']['available_bytes'], 100)
        self.assertEqual(record['host_commit']['available_bytes'], 600)
        self.assertEqual(record['processes'][0]['working_set_bytes'], 30)
        self.assertEqual(record['processes'][0]['private_bytes'], 50)
        self.assertIsNone(record['processes'][0]['cpu_one_core_percent'])
        self.assertFalse(record['comfy']['observed'])
        self.assertNotIn('vms', json.dumps(record))

    def test_cpu_delta_pid_reuse_and_missing_initial_identity(self):
        process = FakeProcess(); now = [10]
        provider = NS(Process=lambda pid: process)
        observer = ProcessObservation(12, provider, lambda: now[0])
        observer.read(); now[0] = 12; process.cpu = 5
        self.assertEqual(observer.read()['cpu_one_core_percent'], 150)
        process.created = 200
        self.assertIn('identity changed', observer.read()['unknown_reason'])
        process.created = 100
        self.assertIsNone(observer.read()['working_set_bytes'], 'An observer never rebinds after reuse')
        missing = ProcessObservation(13, NS(Process=lambda pid: (_ for _ in ()).throw(ProcessLookupError())))
        self.assertIsNone(missing.read()['working_set_bytes'])
        self.assertIn('Initial process identity', missing.read()['unknown_reason'])

    def test_unavailable_counters_are_null_and_errors_do_not_leak_details(self):
        self.assertIsNone(physical_memory(None)['available_bytes'])
        bad = NS(virtual_memory=lambda: NS(total=32, available=33))
        self.assertIn('Invalid', physical_memory(bad)['unknown_reason'])
        process = FakeProcess(); observer = ProcessObservation(12, NS(Process=lambda pid: process))
        process.denied = True
        self.assertIsNone(observer.read()['working_set_bytes'])
        self.assertNotIn('PRIVATE', json.dumps(observer.read()))
        sampler = ResourceSampler(comfy_url='http://127.0.0.1:8188', provider=None,
                                  fetcher=lambda url: (_ for _ in ()).throw(TimeoutError('PRIVATE')))
        record = sampler.sample()['comfy']
        self.assertFalse(record['observed']); self.assertIsNone(record['response_bytes'])
        self.assertNotIn('PRIVATE', json.dumps(record))

    def test_projection_drops_payloads_and_rejects_invalid_counters(self):
        projected = project_stats(STATS)
        self.assertEqual(projected['devices'][0]['vram_free_bytes'], 40)
        self.assertNotIn('PRIVATE', json.dumps(projected))
        for value in (True, -1, float('nan'), float('inf'), '40', None):
            self.assertIsNone(counter(value))
            data = {'system': {}, 'devices': [{'vram_total': 16, 'vram_free': value}]}
            self.assertIsNone(project_stats(data)['devices'][0]['vram_free_bytes'])
        self.assertIsNone(project_stats({'system': {}, 'devices': [{'vram_total': 16, 'vram_free': 17}]})['devices'][0]['vram_free_bytes'])
        with self.assertRaises(ValueError): project_stats({'system': {}, 'devices': [None]})
        with self.assertRaises(ValueError): project_stats([])

    def test_sampling_is_finite_serial_and_preserves_partial_receipts(self):
        events = []
        sampler = NS(sample=lambda: events.append('sample') or {'type': 'sample'})
        stream = io.StringIO()
        write_samples(stream, sampler, samples=3, interval=2, sleep=lambda seconds: events.append(('sleep', seconds)))
        self.assertEqual(events, ['sample', ('sleep', 2), 'sample', ('sleep', 2), 'sample'])
        self.assertEqual(len(stream.getvalue().splitlines()), 4)
        partial = io.StringIO()
        with self.assertRaises(KeyboardInterrupt):
            write_samples(partial, sampler, samples=2, sleep=lambda seconds: (_ for _ in ()).throw(KeyboardInterrupt()))
        self.assertEqual(len(partial.getvalue().splitlines()), 2)
        for kwargs in ({'samples': 0}, {'samples': 121}, {'interval': float('nan')}, {'interval': 0}):
            with self.assertRaises(ValueError): write_samples(io.StringIO(), sampler, **kwargs)
        with self.assertRaises(ValueError): ResourceSampler(range(1, 18))

    def test_remote_credentials_paths_and_invalid_pids_refused_before_network(self):
        for url in ('https://127.0.0.1:8188', 'http://example.com:80', 'http://localhost:8188',
                    'http://user:secret@127.0.0.1:8188', 'http://127.0.0.1:8188/x',
                    'http://127.0.0.1:8188?x=1', 'http://127.0.0.1:8188#x'):
            with self.assertRaises(ValueError): fetch_stats(url)
        for pid in (0, -1, True, '12'):
            with self.assertRaises(ValueError): ProcessObservation(pid)


class ProbeHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = []; cls.status = 200; cls.body = b''; cls.length = None
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                cls.requests.append((self.command, self.path))
                self.send_response(cls.status)
                if cls.status == 302: self.send_header('Location', '/must-not-follow')
                if cls.length is not False: self.send_header('Content-Length', str(cls.length if cls.length is not None else len(cls.body)))
                self.end_headers()
                try: self.wfile.write(cls.body)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError): pass
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.url = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=5)

    def setUp(self):
        type(self).status = 200; type(self).length = None; type(self).body = json.dumps(STATS).encode()
        self.requests.clear()

    def test_real_http_get_projection_and_no_proxy(self):
        with patch.dict('os.environ', {'HTTP_PROXY': 'http://127.0.0.1:1', 'http_proxy': 'http://127.0.0.1:1', 'NO_PROXY': ''}):
            data, size = fetch_stats(self.url)
        self.assertEqual(data, project_stats(STATS)); self.assertEqual(size, len(self.body))
        self.assertEqual(self.requests, [('GET', '/system_stats')])

    def test_redirect_not_followed_or_recorded(self):
        type(self).status = 302
        with self.assertRaises(ValueError): fetch_stats(self.url)
        self.assertEqual(self.requests, [('GET', '/system_stats')])

    def test_malformed_and_oversized_responses(self):
        type(self).body = b'not json'
        with self.assertRaises(ValueError): fetch_stats(self.url)
        type(self).body = b'{}'; type(self).length = MAX_RESPONSE_BYTES + 1
        with self.assertRaises(ValueError): fetch_stats(self.url)
        type(self).length = False; type(self).body = b' ' * (MAX_RESPONSE_BYTES + 1)
        with self.assertRaises(ValueError): fetch_stats(self.url)

    def test_response_deadline_and_socket_timeout_are_bounded(self):
        times = iter((0, 3))
        with self.assertRaises(TimeoutError): fetch_stats(self.url, timeout=2, clock=lambda: next(times))
        with patch('resource_probe.http.client.HTTPConnection') as connection:
            connection.return_value.request.side_effect = TimeoutError()
            with self.assertRaises(TimeoutError): fetch_stats(self.url)
            connection.return_value.close.assert_called_once()


class ProbeCommandTests(unittest.TestCase):
    def test_command_creates_one_receipt_without_model_import_and_refuses_overwrite(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'probe.jsonl'
            command = [sys.executable, str(root / 'scripts/profile-resources.py'), '--samples', '1', '--output', str(output)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=15, cwd=directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            original = output.read_bytes()
            self.assertEqual(len(original.splitlines()), 2)
            result = subprocess.run(command, capture_output=True, text=True, timeout=15, cwd=directory)
            self.assertNotEqual(result.returncode, 0); self.assertEqual(output.read_bytes(), original)
        result = subprocess.run([sys.executable, '-c', "import sys; sys.path.insert(0, 'app'); from resource_probe import ResourceSampler; ResourceSampler().sample(); assert 'torch' not in sys.modules; assert 'server' not in sys.modules"], cwd=root, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__': unittest.main()
