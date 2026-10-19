"""Studio VRAM guard: ComfyUI's model evictions count the VRAM that other processes hold.

Loaded into the Studio-launched primary ComfyUI through `--extra-model-paths-config`
(runtime-patches/comfy-extensions/extra-paths.yaml); no file inside the ComfyUI installation is edited.

ComfyUI decides how much to unload from `get_free_memory`, which reads torch.cuda.mem_get_info. On this
Windows/ROCm box that figure ignores other processes (16,136 of 16,304 MB "free" while the desktop held
several GB), so before a VAE decode ComfyUI unloaded only part of the SDXL UNet and the decode overflowed
3.8 GB into WDDM shared memory with dwm holding 6 GB (23 September 2026, docs/RUNTIME-PRECONDITIONS.md
section 10). While `free_memory` runs, this guard subtracts what other processes hold, so evictions make
room that really exists. Load decisions stay as they were: a model still loads completely whenever ComfyUI
would have loaded it completely, because a truthful load decision turned Krea 2's full load into a partial
one at 2.7x the time per step (section 8).

The wrapped functions are compared with the source hashes they were written for. Any other ComfyUI version
leaves the guard off and says so in the log, at GET /studio/vram-guard and in the Studio's /api/health (`vram_guard`).
"""
import ast
import hashlib
import importlib.util
import logging
import math
import os
from pathlib import Path
import threading
import time

REPO = Path(__file__).resolve().parents[3]
# SHA-256 of each wrapped function's source segment in ComfyUI 40c4fcdf (9 September 2026).
EXPECTED = {'free_memory': '80ea11a1b6a61a9b83155b7f925bc99ef453e2a89e2e9574f6cde400d1a65de7',
            'get_free_memory': '7621aa973a4551eb04c7fdca2444e4e80bf53034abde6affb3f5386cdc5b86e5'}
CACHE_SECONDS = 0.5
# A partial PDH sample can miss one adapter. Keep a larger recent bound for four sampling windows, never indefinitely.
LAST_KNOWN_SECONDS = 2.0
FALLBACK_BYTES = 4 * 1024 ** 3   # the same declared fallback as gpu_memory.FALLBACK_GIB, not a measurement
STATUS = {'installed': False, 'reason': 'not loaded', 'others_bytes': None, 'eviction_calls': 0, 'counted_calls': 0,
          'reading_basis': 'unknown', 'unknown_reason': 'not sampled', 'effective_others_bytes': None,
          'adjustment_basis': None, 'last_known_age_seconds': None, 'capacity_bytes': None, 'device': None, 'counter_anomalies': []}
NODE_CLASS_MAPPINGS = {}


def function_hash(path, name):
    """SHA-256 of a top-level function's source in `path`, or None when the file has no such function."""
    source = Path(path).read_text(encoding='utf-8')
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return hashlib.sha256(ast.get_source_segment(source, node).encode('utf-8')).hexdigest()
    return None


def load_gpu_memory(repo=REPO):
    """The Studio's app/gpu_memory.py under a private name (ComfyUI has its own `app` package)."""
    spec = importlib.util.spec_from_file_location('studio_gpu_memory', Path(repo) / 'app' / 'gpu_memory.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def _bytes(value, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)): return None
    try:
        if not math.isfinite(value) or value < 0: return None
    except OverflowError: return None
    value = int(value)
    return value if value > 0 or not positive else None


class OthersReading:
    """Eviction adjustment with separately reported evidence; unknown is never a measured zero.

    A missing/invalid reading uses the declared fallback (capped to a known capacity), or a larger last-known bound
    for at most LAST_KNOWN_SECONDS. Failed reads do not refresh that bound's age. Device/capacity changes invalidate it.
    """
    def __init__(self, gpu_memory, pid=None, clock=time.monotonic, status=STATUS):
        self.gpu_memory, self.pid, self.clock, self.status = gpu_memory, os.getpid() if pid is None else pid, clock, status
        self.value, self.at, self.key, self.lock = None, None, None, threading.Lock()
        self.last_known, self.last_known_at, self.notice = None, None, None
        self.reason, self.basis, self.anomalies = 'not sampled', 'unknown', []

    def __call__(self, capacity_bytes=None, device=None, unknown_reason=None):
        with self.lock:
            now, capacity = self.clock(), _bytes(capacity_bytes, positive=True)
            key = (device, capacity)
            if key != self.key or self.at is not None and now < self.at:
                self.at = self.last_known = self.last_known_at = None
                self.key = key
            if self.at is None or now - self.at > CACHE_SECONDS:
                self.value, self.basis, self.anomalies = None, 'unknown', []
                self.reason = unknown_reason or ('GPU capacity is unavailable' if capacity is None else
                                                'GPU device identity is unavailable' if device is None else None)
                if self.reason is None:
                    try:
                        sample = self.gpu_memory.read()
                        self.anomalies = self.gpu_memory.anomalies(sample, capacity_bytes=capacity)
                        self.value = _bytes(self.gpu_memory.others_bytes(sample, self.pid, capacity_bytes=capacity))
                        _, self.reason = self.gpu_memory.others_for_admission(sample, self.pid, capacity_bytes=capacity)
                        if self.value is not None:
                            self.basis = 'reconciled' if self.reason else 'measured'
                            self.last_known, self.last_known_at = self.value, now
                        elif self.reason is None: self.reason = 'External GPU memory reading is unavailable'
                    except Exception as exc:
                        self.value = None
                        self.reason = 'GPU memory reading failed: ' + type(exc).__name__ + ': ' + str(exc)[:160]
                self.at = now
            age = None if self.last_known_at is None else now - self.last_known_at
            held, adjustment = self.value, self.basis
            if held is None:
                held, adjustment = min(FALLBACK_BYTES, capacity) if capacity is not None else FALLBACK_BYTES, 'fallback'
                if age is not None and 0 <= age <= LAST_KNOWN_SECONDS and self.last_known > held:
                    held, adjustment = self.last_known, 'last_known'
            self.status.update(others_bytes=self.value, reading_basis=self.basis, unknown_reason=self.reason,
                               effective_others_bytes=held, adjustment_basis=adjustment, last_known_age_seconds=age,
                               capacity_bytes=capacity, device=device, counter_anomalies=self.anomalies)
            notice = (self.basis, self.reason, adjustment)
            if notice != self.notice and self.reason:
                logging.warning('Studio VRAM guard: external use %s (%s); adjustment %s bytes (%s); anomalies=%s',
                                self.basis, self.reason, held, adjustment, self.anomalies)
            self.notice = notice
            return held


def install(mm, others, path=None, expected=EXPECTED, status=STATUS):
    """Wrap `mm.free_memory` and `mm.get_free_memory` once; returns `status`. Never raises."""
    if status['installed']: return status
    if getattr(mm, '_studio_vram_guard', False):   # wrapped already, e.g. by a second import under another module name
        status.update(installed=True, reason='already installed by an earlier import'); return status
    try:
        path = path or mm.__file__
        changed = [name for name, digest in expected.items() if function_hash(path, name) != digest]
        if changed:
            status['reason'] = 'ComfyUI changed ' + ', '.join(changed) + '; guard left off (re-measure before updating the hashes)'
            return status
        original_free, original_get, local = mm.free_memory, mm.get_free_memory, threading.local()

        def get_free_memory(dev=None, torch_free_too=False):
            result = original_get(dev, torch_free_too)
            if not getattr(local, 'depth', 0): return result
            capacity, device, unknown_reason = None, None, None
            try:
                # A bare cuda device follows the current GPU; resolve its identity before consulting the cache.
                implicit = dev is None or str(dev) == 'cuda' or (getattr(dev, 'type', None) == 'cuda' and getattr(dev, 'index', None) is None)
                resolved = mm.get_torch_device() if implicit else dev
                if getattr(resolved, 'type', None) in ('cpu', 'mps') or str(resolved) in ('cpu', 'mps'): return result
                device = str(resolved)
                try: capacity = mm.get_total_memory(resolved)
                except Exception as exc: unknown_reason = 'GPU capacity query failed: ' + type(exc).__name__
            except Exception as exc:
                unknown_reason = 'GPU device identity query failed: ' + type(exc).__name__
            held = others(capacity_bytes=capacity, device=device, unknown_reason=unknown_reason)
            if held <= 0: return result
            status['counted_calls'] += 1
            if torch_free_too: return (max(0, result[0] - held), result[1])
            return max(0, result - held)

        def free_memory(memory_required, device, *args, **kwargs):
            local.depth = getattr(local, 'depth', 0) + 1; status['eviction_calls'] += 1
            try: return original_free(memory_required, device, *args, **kwargs)
            finally: local.depth -= 1

        mm.get_free_memory, mm.free_memory, mm._studio_vram_guard = get_free_memory, free_memory, True
        status.update(installed=True, reason=None)
    except Exception as exc:
        status['reason'] = 'guard not installed: ' + (str(exc) or type(exc).__name__)[:200]
    return status


def write_report(status=STATUS, repo=REPO, pid=None):
    """Leave the install outcome where the Studio's /api/health reads it (.runtime/vram-guard.json); never raises."""
    try:
        import json
        path = Path(repo) / '.runtime' / 'vram-guard.json'; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'installed': status['installed'], 'reason': status['reason'], 'pid': os.getpid() if pid is None else pid,
                                    'written_at': time.time()}), encoding='utf-8')
    except Exception as exc:
        logging.warning('Studio VRAM guard: could not write its report: %s', exc)


def _register_route():
    try:
        from aiohttp import web
        import server
        @server.PromptServer.instance.routes.get('/studio/vram-guard')
        async def vram_guard_status(request): return web.json_response(STATUS)
    except Exception as exc:
        logging.warning('Studio VRAM guard: status route unavailable: %s', exc)


if os.environ.get('STUDIO_VRAM_GUARD_IMPORT_ONLY') != '1':
    try:
        import comfy.model_management as _mm
        _gpu_memory = load_gpu_memory()
        install(_mm, OthersReading(_gpu_memory))
    except Exception as _exc:
        STATUS['reason'] = 'guard not installed: ' + (str(_exc) or type(_exc).__name__)[:200]
    if STATUS['installed']:
        logging.info('Studio VRAM guard on: model evictions count VRAM other processes hold')
    else:
        logging.warning('Studio VRAM guard off: %s', STATUS['reason'])
    write_report()
    _register_route()
