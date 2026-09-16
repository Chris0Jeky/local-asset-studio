"""Worker stages fail honestly without requiring Torch in ordinary CI."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
spec = importlib.util.spec_from_file_location('probe_worker_contract', ROOT / 'scripts/profiler_probe_worker.py')
worker = importlib.util.module_from_spec(spec); spec.loader.exec_module(worker)


class WorkerContracts(unittest.TestCase):
    def collect(self, loader, device='cpu'):
        with tempfile.TemporaryDirectory() as folder:
            worker.collect(Path(folder), device, loader=loader)
            state = json.loads((Path(folder) / 'state.json').read_bytes())
            self.assertLess((Path(folder) / 'state.json').stat().st_size, 16 * 1024)
            self.assertFalse((Path(folder) / 'state.tmp').exists())
            return state

    def test_missing_torch_is_a_durable_payload_free_unsupported_stage(self):
        def absent(name): raise ImportError('CANARY-private-path')
        state = self.collect(absent)
        self.assertEqual(state['outcome'], 'unsupported')
        self.assertEqual(state['stage'], 'import')
        self.assertEqual(state['code'], 'torch_unavailable')
        self.assertNotIn('CANARY', json.dumps(state))

    def test_missing_advertised_activity_never_allocates_a_tensor(self):
        torch = SimpleNamespace(__version__='2.10.0+cpu', version=SimpleNamespace(hip=None, cuda=None),
                    profiler=SimpleNamespace(ProfilerActivity=SimpleNamespace(CPU=1, CUDA=2),
                                             supported_activities=lambda: {1}))
        state = self.collect(lambda name: torch, 'cuda')
        self.assertEqual(state['code'], 'activity_unavailable')
        self.assertEqual(state['advertised_activities'], ['CPU'])
        self.assertFalse(state['arithmetic_verified'])

    def test_device_absent_is_not_a_cpu_fallback(self):
        torch = SimpleNamespace(__version__='2.10.0', version=SimpleNamespace(hip='7.0', cuda=None),
                    profiler=SimpleNamespace(ProfilerActivity=SimpleNamespace(CPU=1, CUDA=2),
                                             supported_activities=lambda: {1, 2}),
                    cuda=SimpleNamespace(is_available=lambda: False))
        state = self.collect(lambda name: torch, 'cuda')
        self.assertEqual(state['code'], 'device_unavailable')
        self.assertEqual(state['requested_device'], 'cuda')
        self.assertIsNone(state['trace_sha256'])

    def test_ordinary_capture_error_retains_stage_not_exception_text(self):
        def fail(): raise RuntimeError('CANARY-sensitive-diagnostic')
        torch = SimpleNamespace(__version__='2.10.0', version=SimpleNamespace(hip=None, cuda=None),
                    profiler=SimpleNamespace(ProfilerActivity=SimpleNamespace(CPU=1), supported_activities=fail))
        state = self.collect(lambda name: torch)
        self.assertEqual(state['stage'], 'capabilities')
        self.assertEqual(state['code'], 'probe_failed')
        self.assertNotIn('CANARY', json.dumps(state))

    def test_public_cli_invalid_interpreter_and_opt_in_are_json_without_paths(self):
        for args, code in ((['--python', '/CANARY/missing'], 'interpreter_invalid'),
                           (['--device', 'cuda'], 'device_opt_in_required')):
            with self.subTest(code=code):
                run = subprocess.run([sys.executable, str(ROOT / 'scripts/probe-inference-profiler.py'), *args],
                                     capture_output=True, text=True, timeout=10)
                self.assertEqual(run.returncode, 2)
                self.assertEqual(json.loads(run.stdout)['code'], code)
                self.assertNotIn('CANARY', run.stdout + run.stderr)

    def test_public_cli_disallows_abbreviated_options(self):
        run = subprocess.run([sys.executable, str(ROOT / 'scripts/probe-inference-profiler.py'), '--dev', 'cpu'],
                             capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 2)
        self.assertIn('unrecognized arguments', run.stderr)
        self.assertEqual(run.stdout, '')


if __name__ == '__main__': unittest.main()
