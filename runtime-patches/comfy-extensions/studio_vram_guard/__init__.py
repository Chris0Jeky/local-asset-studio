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
leaves the guard off and says so in the log and at GET /studio/vram-guard.
"""
import ast
import hashlib
import importlib.util
import logging
import os
from pathlib import Path
import threading
import time

REPO = Path(__file__).resolve().parents[3]
# SHA-256 of each wrapped function's source segment in ComfyUI 40c4fcdf (9 September 2026).
EXPECTED = {'free_memory': '80ea11a1b6a61a9b83155b7f925bc99ef453e2a89e2e9574f6cde400d1a65de7',
            'get_free_memory': '7621aa973a4551eb04c7fdca2444e4e80bf53034abde6affb3f5386cdc5b86e5'}
CACHE_SECONDS = 0.5
STATUS = {'installed': False, 'reason': 'not loaded', 'others_bytes': None, 'eviction_calls': 0, 'counted_calls': 0}
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


class OthersReading:
    """Dedicated VRAM held by every process except this one on its adapter, cached briefly; 0 when unreadable."""
    def __init__(self, gpu_memory, pid=None, clock=time.monotonic, status=STATUS):
        self.gpu_memory, self.pid, self.clock, self.status = gpu_memory, os.getpid() if pid is None else pid, clock, status
        self.value, self.at, self.lock = 0, None, threading.Lock()

    def __call__(self):
        with self.lock:
            now = self.clock()
            if self.at is None or now - self.at > CACHE_SECONDS:
                try: self.value = self.gpu_memory.others_bytes(self.gpu_memory.read(), self.pid) or 0
                except Exception: self.value = 0
                self.at = now; self.status['others_bytes'] = self.value
            return self.value


def install(mm, others, path=None, expected=EXPECTED, status=STATUS):
    """Wrap `mm.free_memory` and `mm.get_free_memory` once; returns `status`. Never raises."""
    if status['installed']: return status
    try:
        path = path or mm.__file__
        changed = [name for name, digest in expected.items() if function_hash(path, name) != digest]
        if changed:
            status['reason'] = 'ComfyUI changed ' + ', '.join(changed) + '; guard left off (re-measure before updating the hashes)'
            return status
        original_free, original_get, local = mm.free_memory, mm.get_free_memory, threading.local()

        def get_free_memory(dev=None, torch_free_too=False):
            result = original_get(dev, torch_free_too)
            if not getattr(local, 'depth', 0) or getattr(dev, 'type', None) in ('cpu', 'mps'): return result
            held = others()
            if held <= 0: return result
            status['counted_calls'] += 1
            if torch_free_too: return (max(0, result[0] - held), result[1])
            return max(0, result - held)

        def free_memory(memory_required, device, *args, **kwargs):
            local.depth = getattr(local, 'depth', 0) + 1; status['eviction_calls'] += 1
            try: return original_free(memory_required, device, *args, **kwargs)
            finally: local.depth -= 1

        mm.get_free_memory, mm.free_memory = get_free_memory, free_memory
        status.update(installed=True, reason=None)
    except Exception as exc:
        status['reason'] = 'guard not installed: ' + (str(exc) or type(exc).__name__)[:200]
    return status


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
    _register_route()
