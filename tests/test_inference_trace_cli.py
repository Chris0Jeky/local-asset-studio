"""Real subprocess/file boundary; uses the existing evidence reader in CI."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'scripts' / 'inspect-inference-trace.py'
RAW = b'{"schemaVersion":1,"traceEvents":[{"ph":"X","cat":"cpu_op","name":"aten::mm","pid":1,"tid":2,"ts":1,"dur":2}]}'


class InferenceTraceCliTests(unittest.TestCase):
    def invoke(self, path, *args):
        return subprocess.run([sys.executable, str(CLI), str(path), *args],
                              cwd=ROOT, capture_output=True, text=True, timeout=15)

    def test_real_file_is_read_without_modification_or_output_files(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'trace.json'; path.write_bytes(RAW)
            result = self.invoke(path, '--sha256', hashlib.sha256(RAW).hexdigest())
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary['recognized_events'], 1)
            self.assertEqual(summary['lanes'][0]['active_union_ns'], 2000)
            self.assertEqual(path.read_bytes(), RAW)
            self.assertEqual(list(Path(folder).iterdir()), [path])

    def test_read_and_parse_failures_are_payload_free_and_nonzero(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'CANARY-private.json'
            for data, code in ((None, 'artifact_missing'), (b'CANARY-private', 'trace_json_invalid'),
                               (b' '*(1024*1024+1), 'artifact_too_large')):
                with self.subTest(code=code):
                    if data is not None: path.write_bytes(data)
                    result = self.invoke(path)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(json.loads(result.stdout)['code'], code)
                    self.assertNotIn('CANARY', result.stdout + result.stderr)

    def test_abbreviated_hash_option_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'trace.json'; path.write_bytes(RAW)
            result = self.invoke(path, '--sha', hashlib.sha256(RAW).hexdigest())
            self.assertEqual(result.returncode, 2)
            self.assertIn('unrecognized arguments', result.stderr)
            self.assertEqual(result.stdout, '')

    def test_hash_mismatch_preserves_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'trace.json'; path.write_bytes(RAW)
            result = self.invoke(path, '--sha256', '0'*64)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stdout)['code'], 'trace_hash_mismatch')
            self.assertEqual(path.read_bytes(), RAW)

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'POSIX FIFO fixture')
    def test_fifo_is_refused_without_blocking(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'trace.json'; os.mkfifo(path)
            result = self.invoke(path)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stdout)['code'], 'file_not_regular')


if __name__ == '__main__': unittest.main()
