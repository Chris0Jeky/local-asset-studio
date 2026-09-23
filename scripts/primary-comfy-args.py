"""Print the primary ComfyUI arguments the Studio itself launches with, for Start-Studio.ps1 -> Start-ComfyUI.ps1.

One source of truth: `BackendManager.primary_argv` (measured --reserve-vram, --disable-pinned-memory from config).
Output is JSON: {"arguments": [...everything after the Python executable...], "python": ..., "reserve": {...}}.
It reads config/local.json and the GPU counters only; it starts, stops and submits nothing.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from backends import BackendManager, PRIMARY_RESERVE_VRAM
from backend_contracts import loopback_port

config = json.loads((ROOT / 'config/local.json').read_text(encoding='utf-8'))
primary = Path(config['comfy_root']).resolve()
target = {'python': str(Path(config.get('python', 'C:/AI/ComfyUI_windows_portable/python_embeded/python.exe')).resolve()),
          'entry': str(primary / 'main.py'), 'port': loopback_port(config.get('comfy_url', 'http://127.0.0.1:8188')),
          'disable_pinned_memory': config.get('primary_disable_pinned_memory') is True,
          'reserve_vram': BackendManager.configured_reserve(config.get('primary_reserve_vram', PRIMARY_RESERVE_VRAM))}
reserve = BackendManager.launch_reserve(target)
argv = BackendManager.primary_argv(target, reserve)
# The desktop launcher has always loaded ComfyUI-Manager (runtime-patches/README.md); keep that for this path only.
# The ownership checks read --listen/--port, so the extra flag does not change which process the Studio adopts.
argv.append('--enable-manager')
print(json.dumps({'python': argv[0], 'arguments': argv[1:], 'reserve': reserve}))
