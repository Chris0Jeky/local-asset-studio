"""Pure, inexpensive preflight contracts. Presence is not inference certification."""
from __future__ import annotations

import errno
from pathlib import Path
from urllib.parse import urlsplit

H3_FILES = (
    ('diffusion', 'models/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors'),
    ('text encoder', 'models/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors'),
    ('video decoder', 'models/vae/minimax_h3_video_vae_fp16.safetensors'),
    ('audio decoder', 'models/vae/minimax_h3_audio_vae_fp32.safetensors'),
    ('preview adapter', 'models/loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors'),
)

# docs/QWEN-IMAGE-21.md: the Comfy-Org pack files the recipes load, inside the isolated checkout.
QWEN21_FILES = (
    ('diffusion', 'models/diffusion_models/qwen_image_2.1_int8_convrot.safetensors'),
    ('text encoder', 'models/text_encoders/qwen3vl_8b_int8_convrot.safetensors'),
    ('decoder', 'models/vae/qwen_image_2.1_vae_bf16.safetensors'),
)


def loopback_port(url):
    """Managed launchers support one explicit IPv4 loopback listener, not proxies."""
    try:
        parsed = urlsplit(url)
        port = parsed.port
        valid = (parsed.scheme == 'http' and parsed.hostname == '127.0.0.1'
                 and parsed.username is None and parsed.password is None
                 and parsed.path in ('', '/') and not parsed.query and not parsed.fragment
                 and port is not None and 1 <= port <= 65535)
    except (TypeError, ValueError):
        valid = False
    if not valid:raise ValueError('Managed backend URL must be http://127.0.0.1:<port> without credentials, path or query')
    return port


def queue_is_idle(queue):
    """A malformed or partial response must never authorize stopping a process."""
    # Preserve a useful busy diagnosis even when the other field is absent.
    if isinstance(queue, dict) and any(isinstance(queue.get(k), list) and queue[k] for k in ('queue_running', 'queue_pending')):
        raise ValueError('ComfyUI has active or queued work. Its queue was preserved.')
    if not isinstance(queue, dict) or any(not isinstance(queue.get(k), list) for k in ('queue_running', 'queue_pending')):
        raise ValueError('ComfyUI queue state is unknown: expected running and pending lists. No process was authorized to stop.')
    return True


def connection_refused(error):
    reason = getattr(error, 'reason', error)
    return isinstance(reason, OSError) and (reason.errno == errno.ECONNREFUSED or getattr(reason, 'winerror', None) == 10061)


def endpoint_ready(value):
    return isinstance(value, dict) and isinstance(value.get('system'), dict) and bool(value['system'])


def readiness(profile, repo_root):
    """Check the selected launcher plus its declared baseline files, without loading them.

    H3's five-file contract follows docs/H3-WINDOWS.md and Qwen-Image 2.1's three files
    docs/QWEN-IMAGE-21.md. Other families retain
    per-preset model validation: this is not a second general model manager.
    """
    root = Path(profile['root'])
    required = [('Python interpreter', Path(profile['python']), False),
                ('ComfyUI entry', root / 'main.py', False),
                ('Studio launcher', Path(profile['entry']), False)]
    if profile['id'] == 'hidream':required.append(('Transformers overlay', root / 'python_packages/transformers', True))
    if profile['id'] == 'qwen21':
        required.append(('Comfy Kitchen overlay', root / 'python_packages/comfy_kitchen', True))
        required.extend((role, root / path, False) for role, path in QWEN21_FILES)
    if profile['id'] == 'h3':
        required.append(('isolated loader', Path(repo_root) / 'scripts/h3_mmap_loader.py', False))
        required.extend((role, root / path, False) for role, path in H3_FILES)
    items = []
    for role, path, directory in required:
        try:present = path.is_dir() if directory else path.is_file() and path.stat().st_size > 0
        except OSError:present = False
        items.append({'role': role, 'path': str(path), 'present': present})
    missing = [item for item in items if not item['present']]
    return {'ready': not missing, 'scope': 'launcher-and-baseline-file-presence', 'requirements': items,
            'missing': missing, 'hash_verified': None, 'runtime_compatible': None,
            'message': ('Required files are present; hashes, node schemas and inference are separate checks.'
                        if not missing else 'Missing or empty: ' + ', '.join(item['role'] for item in missing))}
