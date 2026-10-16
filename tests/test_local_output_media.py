"""#1228: real HTTP delivery of synthetic local outputs after failed snapshots; no ComfyUI."""
import io
import json
import sqlite3
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

from test_server import server


class LocalOutputMediaTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup); self.root = Path(temporary.name)
        (self.root / 'config').mkdir(); (self.root / 'presets').mkdir()
        (self.root / 'presets/catalog.json').write_text('{"presets": []}')
        (self.root / 'config/local.json').write_text(json.dumps({'comfy_root': str(self.root / 'fake-comfy')}))
        with patch.object(threading.Thread, 'start', lambda *_: None):
            self.studio = server.Studio(self.root)
        self.http = server.create_server(self.root, port=0, studio_factory=lambda _: self.studio)
        thread = threading.Thread(target=self.http.serve_forever, kwargs={'poll_interval': .01}, daemon=True); thread.start()
        self.addCleanup(thread.join, 3); self.addCleanup(self.http.server_close); self.addCleanup(self.http.shutdown)

    def get(self, identifier, headers=None):
        connection = HTTPConnection('127.0.0.1', self.http.server_port, timeout=5)
        try:
            connection.request('GET', '/api/image/' + identifier + '/0', headers={'Host': '127.0.0.1:8191', **(headers or {})})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally: connection.close()

    def proxy_file(self, _request, **_kwargs):
        # A different ComfyUI output with the same filename: the old fallback would deliver these bytes.
        result = io.BytesIO(b'unrelated ComfyUI output'); result.status = 200
        result.headers = {'Content-Type': 'application/octet-stream', 'Content-Length': '24'}
        return result

    def local_job(self, operation):
        identifier = 'a' * 32; name = 'shared.png'
        if operation == 'asset.import':
            output = {'uploaded_file': name}; file = self.root / 'experiments/uploads' / name
        elif operation in ('tile.finish.v1', 'parallax.finish.v1'):
            output = {'run_file': name}; file = self.root / 'experiments/runs' / identifier / name
        else:
            output = {'native_path': 'output/' + name}; file = self.root / 'experiments/projects' / identifier / 'output' / name
        output.update(filename=name, subfolder='', type='output')
        job = {'id': identifier, 'project_id': identifier, 'operation': operation, 'outputs': [output]}
        self.studio.jobs[identifier] = job
        file.parent.mkdir(parents=True, exist_ok=True); file.write_bytes(('retained ' + operation).encode())
        with patch.object(self.studio.assets, 'register', side_effect=sqlite3.OperationalError('synthetic snapshot failure')):
            self.studio.index_outputs(job)
        self.assertIn('snapshot_error', output); self.assertNotIn('asset_id', output)
        return identifier, output, file

    def test_failed_snapshots_serve_retained_local_bytes_for_every_local_operation(self):
        operations = ('asset.import', 'tile.finish.v1', 'parallax.finish.v1', 'native.articulated-prop.v1', 'native.av-preview.v1', 'native.voice-baseline.v1')
        for operation in operations:
            with self.subTest(operation=operation):
                identifier, _, file = self.local_job(operation)
                with patch.object(server, 'urlopen', side_effect=self.proxy_file) as remote:
                    status, headers, body = self.get(identifier)
                self.assertEqual(status, 200); self.assertEqual(body, file.read_bytes())
                self.assertEqual(headers['Accept-Ranges'], 'bytes'); remote.assert_not_called()

    def test_missing_retained_output_is_404_even_when_comfy_has_the_same_filename(self):
        identifier, _, file = self.local_job('tile.finish.v1'); file.unlink()
        with patch.object(server, 'urlopen', side_effect=self.proxy_file) as remote:
            status, _, body = self.get(identifier)
        self.assertEqual(status, 404); self.assertIn(b'Unknown image', body); remote.assert_not_called()

    def test_local_fallback_preserves_byte_ranges(self):
        identifier, _, file = self.local_job('native.voice-baseline.v1')
        with patch.object(server, 'urlopen', side_effect=self.proxy_file) as remote:
            status, headers, body = self.get(identifier, {'Range': 'bytes=2-8'})
        self.assertEqual(status, 206); self.assertEqual(body, file.read_bytes()[2:9])
        self.assertEqual(headers['Content-Range'], 'bytes 2-8/' + str(file.stat().st_size)); remote.assert_not_called()

    def test_unknown_or_damaged_local_descriptors_do_not_serve_other_files(self):
        identifier, output, _ = self.local_job('tile.finish.v1')
        # A foreign file exists at both tempting fallback locations; neither is this job's output.
        foreign = self.studio.runs / 'foreign.png'; foreign.write_bytes(b'foreign run')
        comfy = self.root / 'fake-comfy/output/shared.png'; comfy.parent.mkdir(parents=True); comfy.write_bytes(b'foreign comfy file')
        for operation, fields in [('unknown.local.v1', {'filename': 'shared.png', 'type': 'output'}),
                                  ('tile.finish.v1', {'filename': 'shared.png', 'run_file': '../foreign.png'}),
                                  ('tile.finish.v1', {'filename': 'shared.png'})]:
            with self.subTest(operation=operation, fields=fields):
                self.studio.jobs[identifier]['operation'] = operation; output.clear(); output.update(fields)
                with patch.object(server, 'urlopen', side_effect=self.proxy_file) as remote:
                    status, _, body = self.get(identifier)
                self.assertEqual(status, 404); self.assertIn(b'Unknown image', body); remote.assert_not_called()

    def test_comfy_outputs_without_snapshots_still_use_the_recorded_backend(self):
        identifier = 'comfy-job'; self.studio.jobs[identifier] = {'id': identifier, 'comfy_url': 'http://127.0.0.1:9876', 'outputs': [{'filename': 'shared.png', 'type': 'output'}]}
        with patch.object(server, 'urlopen', side_effect=self.proxy_file) as remote:
            status, _, body = self.get(identifier)
        self.assertEqual((status, body), (200, b'unrelated ComfyUI output'))
        self.assertEqual(remote.call_args.args[0].full_url, 'http://127.0.0.1:9876/view?filename=shared.png&type=output')


if __name__ == '__main__': unittest.main()
