"""No GPU required: qualification semantics and real owned-child failure paths."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import os
import venv
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
try:
    import profiler_probe as probe
except ModuleNotFoundError:
    probe = None

RAW = b'{"schemaVersion":1,"traceEvents":[{"ph":"X","cat":"cpu_op","name":"aten::mm","pid":1,"tid":1,"ts":1,"dur":2}]}'


class ProfilerProbeTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(probe, 'Profiler qualification has not been implemented')

    def state(self, device='cpu', raw=RAW):
        result = probe.initial_state(device)
        result.update(outcome='completed', stage='complete', arithmetic_verified=True,
                      advertised_activities=['CPU', 'CUDA'], trace_sha256=hashlib.sha256(raw).hexdigest())
        result['versions']['torch'] = '2.10.0+cpu'
        return result

    def test_cpu_success_is_not_gpu_or_job_qualification(self):
        result = probe.assess(self.state(), RAW, 'cpu')
        self.assertEqual(result['status'], 'cpu_observed')
        self.assertEqual(result['scope'], 'fixed_16x16_arithmetic_probe')
        self.assertFalse(result['inference_performance_qualified'])
        self.assertIsNone(result['driver_identity'])
        self.assertEqual(result['summary']['job_binding'], 'unbound')
        self.assertEqual(result['summary']['device_timing']['status'], 'unavailable')

    def test_advertised_cuda_is_not_observed_device_support(self):
        result = probe.assess(self.state('cuda'), RAW, 'cuda')
        self.assertEqual(result['status'], 'unsupported')
        self.assertEqual(result['code'], 'device_spans_unobserved')

    def test_device_success_requires_recorded_spans_and_arithmetic(self):
        document = json.loads(RAW)
        document['traceEvents'].append(dict(ph='X',cat='kernel',name='secret',pid=0,tid=1,ts=1,dur=2))
        raw = json.dumps(document).encode()
        result = probe.assess(self.state('cuda', raw), raw, 'cuda')
        self.assertEqual(result['status'], 'device_observed')
        self.assertNotIn('secret', json.dumps(result))
        state = self.state('cuda', raw); state['arithmetic_verified'] = False
        self.assertEqual(probe.assess(state, raw, 'cuda')['code'], 'arithmetic_unverified')

    def test_hash_mismatch_never_associates_replaced_trace(self):
        state = self.state(); state['trace_sha256'] = '0' * 64
        self.assertEqual(probe.assess(state, RAW, 'cpu')['code'], 'trace_hash_mismatch')

    def test_requested_device_and_advertised_activity_must_match(self):
        self.assertEqual(probe.assess(self.state(), RAW, 'cuda')['code'], 'worker_state_invalid')
        state = self.state(); state['advertised_activities'] = []
        self.assertEqual(probe.assess(state, RAW, 'cpu')['code'], 'activity_unavailable')

    def test_nonterminal_state_and_unsupported_keep_fixed_reason(self):
        state = probe.initial_state('cpu')
        self.assertEqual(probe.assess(state, None, 'cpu')['code'], 'capture_incomplete')
        state.update(outcome='unsupported', code='torch_unavailable')
        self.assertEqual(probe.assess(state, None, 'cpu')['code'], 'torch_unavailable')

    def test_unknown_fields_or_labels_cannot_escape_protocol(self):
        state = self.state(); state['CANARY'] = 'private'
        result = probe.assess(state, RAW, 'cpu')
        self.assertEqual(result['code'], 'worker_state_invalid')
        self.assertNotIn('CANARY', json.dumps(result))
        state = self.state(); state['versions']['torch'] = 'CANARY/private'
        result = probe.assess(state, RAW, 'cpu')
        self.assertEqual(result['code'], 'worker_state_invalid')
        self.assertNotIn('CANARY', json.dumps(result))

    def test_invalid_trace_is_a_fixed_code(self):
        raw = b'CANARY not JSON'
        result = probe.assess(self.state(raw=raw), raw, 'cpu')
        self.assertEqual(result['code'], 'trace_json_invalid')
        self.assertNotIn('CANARY', json.dumps(result))

    def test_device_requires_opt_in_before_process_creation(self):
        with patch.object(probe.subprocess, 'Popen', side_effect=AssertionError('must not launch')):
            result = probe.run_probe(sys.executable, device='cuda')
        self.assertEqual(result['code'], 'device_opt_in_required')

    def test_bad_timeout_refuses_before_launch(self):
        for timeout in (True, 0, float('inf'), float('nan'), 121):
            with self.subTest(timeout=timeout):
                with patch.object(probe.subprocess, 'Popen', side_effect=AssertionError('must not launch')):
                    self.assertEqual(probe.run_probe(sys.executable, timeout=timeout)['code'], 'probe_options_invalid')

    def test_owned_hanging_child_is_reaped_without_retry(self):
        handles = []; real = subprocess.Popen
        def capture(*args, **kwargs):
            child = real(*args, **kwargs); handles.append(child); return child
        with patch.object(probe.subprocess, 'Popen', side_effect=capture):
            result = probe.supervise([sys.executable, '-c', 'import time; time.sleep(60)'], 0.2)
        self.assertEqual(result['code'], 'worker_timeout')
        self.assertEqual(len(handles), 1)
        self.assertIsNotNone(handles[0].poll())
        self.assertTrue(result['child_reaped'])

    def test_noisy_child_does_not_expand_parent_capture_or_echo(self):
        result = probe.supervise([sys.executable, '-c',
            "import os; os.write(1,b'CANARY'*100000); os.write(2,b'CANARY'*100000)"], 5)
        self.assertEqual(result['returncode'], 0)
        self.assertEqual(result['retained_stdout_stderr_bytes'], 0)
        self.assertNotIn('CANARY', json.dumps(result))

    def test_nonzero_child_exit_is_retained_without_retry(self):
        result = probe.supervise([sys.executable, '-c', 'raise SystemExit(23)'], 5)
        self.assertEqual(result['returncode'], 23)
        self.assertEqual(result['code'], 'worker_failed')
        self.assertTrue(result['child_reaped'])

    def test_launch_failure_is_payload_free(self):
        result = probe.supervise(['/CANARY/no/interpreter'], 1)
        self.assertEqual(result['code'], 'worker_launch_failed')
        self.assertNotIn('CANARY', json.dumps(result))

    def test_selected_virtual_environment_is_not_resolved_to_base_python(self):
        with tempfile.TemporaryDirectory() as folder:
            environment = Path(folder) / 'probe-venv'
            venv.EnvBuilder(with_pip=False, symlinks=os.name != 'nt').create(environment)
            executable = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
            outcome = probe.run_probe(executable, timeout=20)
            self.assertEqual(outcome['code'], 'torch_unavailable', outcome)
            self.assertEqual(outcome['interpreter_path_sha256'],
                             hashlib.sha256(str(executable.absolute()).encode()).hexdigest())

    def test_unknown_torch_version_cannot_qualify_environment(self):
        state = self.state(); state['versions']['torch'] = None
        self.assertEqual(probe.assess(state, RAW, 'cpu')['code'], 'torch_version_unavailable')

    def test_duplicate_keys_in_stage_file_are_refused(self):
        with self.assertRaises(ValueError):
            probe._decode_state(b'{"stage":"import","stage":"complete"}')

    def test_owned_artifact_read_is_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'state.json'; path.write_bytes(b'x' * 101)
            with self.assertRaises(ValueError): probe._read_owned(path, 100)
            self.assertEqual(probe._read_owned(path, 101), b'x' * 101)

    def test_cleanup_failure_is_not_reported_as_clean_success(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder) / 'owned'; work.mkdir()
            state = probe.initial_state('cpu'); state.update(outcome='unsupported', code='torch_unavailable')
            (work / 'state.json').write_text(json.dumps(state))
            execution = dict(code=None, returncode=0, child_reaped=True, elapsed_ms=0, retained_stdout_stderr_bytes=0)
            with patch.object(probe.tempfile, 'mkdtemp', return_value=str(work)), \
                 patch.object(probe, 'supervise', return_value=execution), \
                 patch.object(probe.shutil, 'rmtree', side_effect=OSError('CANARY')):
                outcome = probe.run_probe(sys.executable)
            self.assertEqual(outcome['code'], 'temporary_cleanup_failed')
            self.assertNotIn('CANARY', json.dumps(outcome))

    def test_parent_import_does_not_load_torch_or_server(self):
        code = "import sys; sys.path.insert(0,'app'); import profiler_probe; assert 'torch' not in sys.modules; assert 'server' not in sys.modules"
        result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__': unittest.main()
