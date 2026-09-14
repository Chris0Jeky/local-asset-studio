"""CLI file limits apply to capture, not only after an unbounded allocation."""
from contextlib import contextmanager, redirect_stdout
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_workflow_studio as fixture
from studio_workflow import __main__ as cli, core


class FileInputTests(unittest.TestCase):
    setUp = fixture.HTTPTests.setUp
    close = fixture.HTTPTests.close

    def invoke(self, args):
        output = io.StringIO()
        with redirect_stdout(output):
            code = cli.main(['--url', self.url, *args])
        return code, json.loads(output.getvalue())

    def commands(self, source):
        path = str(source)
        return [
            ['import', '--graph', path], ['compile', '--document', path],
            ['prepare', '--recipe', path], ['run', '--ticket', path, '--approve'],
            ['prepare-document', '--document', path, '--preset', 'example'],
            ['documents', 'create', '--document', path, '--request-id', 'create-input'],
            ['documents', 'apply', 'document-a', '--commands', path, '--expected-revision', '1', '--request-id', 'apply-input'],
            ['documents', 'preview', 'document-a', '--commands', path, '--expected-revision', '1'],
        ]

    @contextmanager
    def track(self, source, before_open=None):
        original = Path.open
        observed, handles = [], []
        expected = source.resolve()
        class Reader:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): return self
            def __exit__(self, *args): return self.stream.__exit__(*args)
            def read(self, size=-1):
                observed.append(size)
                return self.stream.read(size)
        def opening(path, *args, **kwargs):
            mode = args[0] if args else kwargs.get('mode', 'r')
            if path.resolve() == expected and mode == 'rb':
                if before_open: before_open()
                stream = original(path, *args, **kwargs)
                handles.append(stream)
                return Reader(stream)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', opening): yield observed, handles

    def test_every_file_command_uses_a_single_bounded_read(self):
        source = Path(self.temp.name) / 'input.json'; source.write_bytes(b'{}')
        for args in self.commands(source):
            with self.subTest(command=args[:2]), self.track(source) as (reads, handles), patch.object(cli.Client, 'request', return_value={}):
                self.invoke(args)
                self.assertEqual(reads, [core.MAX_BYTES + 1])
                self.assertTrue(all(stream.closed for stream in handles))

    def test_oversized_input_does_not_request_or_read_beyond_the_sentinel(self):
        source = Path(self.temp.name) / 'large.json'
        raw = b'{}' + b' ' * (core.MAX_BYTES * 3); source.write_bytes(raw)
        for args in self.commands(source):
            with self.subTest(command=args[:2]), self.track(source) as (reads, handles), patch.object(cli.Client, 'request') as request:
                code, result = self.invoke(args)
                self.assertNotEqual(code, 0)
                self.assertIn('1 MiB', result['error'])
                request.assert_not_called()
                self.assertEqual(reads, [core.MAX_BYTES + 1])
                self.assertTrue(all(stream.closed for stream in handles))
        self.assertEqual(source.read_bytes(), raw)
        self.assertEqual(self.studio.calls, 0)

    def test_growth_at_open_is_bounded_and_rejected(self):
        source = Path(self.temp.name) / 'growing.json'; source.write_bytes(b'{}')
        with self.track(source, lambda: source.write_bytes(b'{}' + b' ' * core.MAX_BYTES)) as (reads, handles), patch.object(cli.Client, 'request') as request:
            code, result = self.invoke(['prepare', '--recipe', str(source)])
            self.assertEqual(code, 2)
            self.assertIn('1 MiB', result['error'])
            self.assertEqual(reads, [core.MAX_BYTES + 1])
            request.assert_not_called()
            self.assertTrue(all(stream.closed for stream in handles))

    def test_exact_limit_real_preparation_preserves_wide_integer(self):
        source = Path(self.temp.name) / 'exact.json'
        info = copy.deepcopy(fixture.INFO)
        info['Number']['input']['required']['value'][1]['max'] = 2**63 - 1
        self.studio.node_info = lambda **_: info
        value = {'preset_id': 'example', 'controls': {'value': 2**63 - 1}}
        raw = json.dumps(value).encode(); source.write_bytes(raw + b' ' * (core.MAX_BYTES - len(raw)))
        code, result = self.invoke(['prepare', '--recipe', str(source)])
        self.assertEqual(code, 0, result)
        self.assertEqual(result['recipe']['controls']['value'], value['controls']['value'])
        self.assertEqual(self.studio.calls, 0)

    def test_strict_json_failures_close_capture_without_a_request(self):
        source = Path(self.temp.name) / 'bad.json'
        for raw in (b'', b'\xff', b'{"a":1,"a":2}', b'{"__proto__":{}}', b'NaN', b'1e400', b'[' * 50 + b'0' + b']' * 50):
            source.write_bytes(raw)
            with self.subTest(raw=raw[:30]), self.track(source) as (_, handles), patch.object(cli.Client, 'request') as request:
                code, _ = self.invoke(['prepare', '--recipe', str(source)])
                self.assertEqual(code, 2)
                request.assert_not_called()
                self.assertEqual(len(handles), 1)
                self.assertTrue(handles[0].closed)
                self.assertEqual(source.read_bytes(), raw)

    def test_missing_or_directory_input_never_requests(self):
        for source in (Path(self.temp.name) / 'missing.json', Path(self.temp.name)):
            with self.subTest(source=source), patch.object(cli.Client, 'request') as request:
                code, _ = self.invoke(['prepare', '--recipe', str(source)])
                self.assertEqual(code, 2)
                request.assert_not_called()

    def test_cli_from_another_directory_uses_the_same_limit(self):
        source = Path(self.temp.name) / 'large.json'; source.write_bytes(b'{}' + b' ' * core.MAX_BYTES)
        root = Path(__file__).resolve().parents[1]
        script = 'import sys;sys.path.insert(0,sys.argv.pop(1));from studio_workflow.__main__ import main;raise SystemExit(main())'
        process = subprocess.run([sys.executable, '-c', script, str(root), 'prepare', '--recipe', str(source)],
                                 cwd=self.temp.name, capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assertIn('1 MiB', json.loads(process.stdout)['error'])


if __name__ == '__main__': unittest.main()
