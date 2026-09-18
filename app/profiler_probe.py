"""One supervised, fixed arithmetic profiler probe; never a Studio job runner."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time

from inference_trace import MAX_BYTES, TraceError, summarize_trace

ROOT = Path(__file__).resolve().parents[1]
STATE_LIMIT = 16 * 1024
STAGES = ('starting', 'import', 'capabilities', 'allocate', 'capture', 'export', 'verify', 'complete')
CODES = (None, 'torch_unavailable', 'activity_unavailable', 'device_unavailable',
         'probe_failed', 'trace_too_large', 'arithmetic_unverified')
VERSION = re.compile(r'[0-9][0-9A-Za-z.+_-]{0,95}\Z')
HEX = re.compile(r'[0-9a-f]{64}\Z')


def initial_state(device):
    return {'schema': 'studio.profiler-probe-worker/v1', 'requested_device': device,
        'outcome': 'in_progress', 'stage': 'starting', 'code': None,
        'versions': {'python': platform.python_version(), 'torch': None, 'hip': None, 'cuda_build': None},
        'advertised_activities': [], 'arithmetic_verified': False, 'trace_sha256': None,
        'device_architecture': None, 'device_name_sha256': None}


def result(code, *, status='failed', stage=None):
    return {'schema': 'studio.profiler-probe/v1', 'scope': 'fixed_16x16_arithmetic_probe',
        'status': status, 'code': code, 'last_stage': stage,
        'driver_identity': None, 'job_binding': 'unbound',
        'inference_performance_qualified': False, 'profiler_overhead_qualified': False,
        'generation_jobs_submitted': 0}


def _valid_state(state, device):
    if not isinstance(state, dict) or set(state) != set(initial_state(device)): return False
    if state['schema'] != 'studio.profiler-probe-worker/v1' or state['requested_device'] != device: return False
    if state['outcome'] not in ('in_progress', 'completed', 'unsupported', 'failed'): return False
    if state['stage'] not in STAGES or state['code'] not in CODES: return False
    versions = state['versions']
    if not isinstance(versions, dict) or set(versions) != {'python', 'torch', 'hip', 'cuda_build'}: return False
    if any(v is not None and (not isinstance(v, str) or VERSION.fullmatch(v) is None) for v in versions.values()): return False
    if versions['python'] is None: return False
    activities = state['advertised_activities']
    if not isinstance(activities, list) or len(activities) > 2: return False
    if any(a not in ('CPU', 'CUDA') for a in activities) or len(set(activities)) != len(activities): return False
    if type(state['arithmetic_verified']) is not bool: return False
    for name in ('trace_sha256', 'device_name_sha256'):
        value = state[name]
        if value is not None and (not isinstance(value, str) or HEX.fullmatch(value) is None): return False
    arch = state['device_architecture']
    if arch is not None and (not isinstance(arch, str) or re.fullmatch(r'gfx[0-9a-f]{3,5}', arch) is None): return False
    return True


def assess(state, raw, device):
    """Combine this worker's declaration and exact exported bytes, not filename/time guesses."""
    if device not in ('cpu', 'cuda') or not _valid_state(state, device): return result('worker_state_invalid')
    base = result(state['code'], stage=state['stage'])
    base.update(requested_device=device, versions=state['versions'],
                advertised_activities=state['advertised_activities'],
                device_architecture=state['device_architecture'], device_name_sha256=state['device_name_sha256'])
    if state['outcome'] == 'in_progress': return dict(base, code='capture_incomplete')
    if state['outcome'] != 'completed':
        return dict(base, status=state['outcome'], code=state['code'] or 'probe_failed')
    if state['stage'] != 'complete' or state['code'] is not None: return result('worker_state_invalid')
    if not state['arithmetic_verified']: return dict(base, code='arithmetic_unverified')
    if state['versions']['torch'] is None: return dict(base, code='torch_version_unavailable')
    required = ('CPU',) if device == 'cpu' else ('CPU', 'CUDA')
    if any(name not in state['advertised_activities'] for name in required):
        return dict(base, status='unsupported', code='activity_unavailable')
    if not isinstance(raw, bytes) or state['trace_sha256'] is None: return dict(base, code='capture_incomplete')
    try: summary = summarize_trace(raw, expected_sha256=state['trace_sha256'])
    except TraceError as exc: return dict(base, code=exc.code)
    base.update(summary=summary, arithmetic_verified=True)
    if not any(lane['kind'] == 'host_operator' for lane in summary['lanes']):
        return dict(base, status='unsupported', code='host_spans_unobserved')
    if device == 'cuda' and not any(lane['kind'] == 'device_kernel' for lane in summary['lanes']):
        return dict(base, status='unsupported', code='device_spans_unobserved')
    return dict(base, code=None, status='cpu_observed' if device == 'cpu' else 'device_observed')


def supervise(command, timeout):
    """Only for the fixed worker (or inert contract children); never attach by PID.

    Raw stdout/stderr go to the null device, not unbounded pipes or spool files.
    A bounded stage file supplies diagnostics. No retries or process-name kills.
    """
    start = time.monotonic(); child = None; code = None; reaped = True
    try:
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, shell=False)
        try:
            child.wait(timeout=timeout)
            if child.returncode: code = 'worker_failed'
        except subprocess.TimeoutExpired:
            code = 'worker_timeout'; child.kill()
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired: code = 'worker_cleanup_incomplete'; reaped = False
    except OSError:
        code = 'worker_launch_failed'
        if child is not None and child.poll() is None:
            try: child.kill(); child.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired): reaped = False; code = 'worker_cleanup_incomplete'
    except KeyboardInterrupt:
        code = 'worker_interrupted'
        if child is not None and child.poll() is None:
            try: child.kill(); child.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired): reaped = False; code = 'worker_cleanup_incomplete'
    except BaseException:
        if child is not None and child.poll() is None:
            child.kill(); child.wait(timeout=5)
        raise
    return {'code': code, 'returncode': None if child is None else child.returncode,
            'child_reaped': reaped, 'elapsed_ms': round((time.monotonic()-start)*1000, 3),
            'retained_stdout_stderr_bytes': 0}


def _read_owned(path, limit):
    """After worker exit, read one of our private temporary artifacts with a byte cap."""
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit: raise ValueError('probe_artifact_invalid')
        raw = stream.read(limit + 1)
    if len(raw) > limit: raise ValueError('probe_artifact_invalid')
    return raw


def _decode_state(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value: raise ValueError('worker_state_invalid')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs)


def run_probe(interpreter, *, device='cpu', timeout=30, allow_device=False):
    if (device not in ('cpu', 'cuda') or type(timeout) not in (int, float)
            or not math.isfinite(timeout) or not 5 <= timeout <= 120 or type(allow_device) is not bool):
        return result('probe_options_invalid')
    if device == 'cuda' and not allow_device: return result('device_opt_in_required', status='refused')
    try:
        # Preserve a venv's executable path: resolving its symlink can select
        # the base interpreter instead of the requested environment.
        python = Path(interpreter).absolute()
        if not python.is_file(): return result('interpreter_invalid')
    except (OSError, ValueError, TypeError): return result('interpreter_invalid')
    worker = ROOT / 'scripts/profiler_probe_worker.py'
    try: folder = Path(tempfile.mkdtemp(prefix='studio-profiler-probe-'))
    except OSError: return result('probe_storage_unavailable')
    execution = None; final = None
    try:
        command = [str(python), '-I', '-B', str(worker), '--directory', str(folder), '--device', device]
        execution = supervise(command, timeout)
        state = None
        try: state = _decode_state(_read_owned(folder / 'state.json', STATE_LIMIT))
        except (OSError, ValueError, UnicodeError, RecursionError): pass
        if execution['code'] is not None:
            final = result(execution['code'], stage=state['stage'] if _valid_state(state, device) else None)
        else:
            raw = None
            if _valid_state(state, device) and state['outcome'] == 'completed':
                try: raw = _read_owned(folder / 'trace.json', MAX_BYTES)
                except (OSError, ValueError): pass
            final = assess(state, raw, device)
        final.update(supervision=execution, interpreter_path_sha256=hashlib.sha256(os.fsencode(python)).hexdigest(),
            worker_source_sha256=hashlib.sha256(worker.read_bytes()).hexdigest(),
            limits={'timeout_seconds': timeout, 'post_export_trace_bytes': MAX_BYTES, 'state_bytes': STATE_LIMIT,
                    'hard_worker_memory_limit': None, 'hard_producer_output_limit': None})
    except OSError:
        final = result('probe_storage_unavailable')
    finally:
        if execution is not None and not execution['child_reaped']:
            if final is not None: final['temporary_cleanup'] = 'retained_worker_not_reaped'
        else:
            try:
                shutil.rmtree(folder)
                if final is not None: final['temporary_cleanup'] = 'removed'
            except OSError:
                if final is not None:
                    final.update(temporary_cleanup='failed', status='failed', code='temporary_cleanup_failed')
    return final
