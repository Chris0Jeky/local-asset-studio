"""Fixed, opt-in worker for profiler qualification; not a general workload executor."""
from __future__ import annotations
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from profiler_probe import STATE_LIMIT, VERSION, initial_state
from inference_trace import MAX_BYTES


def collect(directory, device, *, loader=importlib.import_module):
    state = initial_state(device)
    def save(stage):
        state['stage'] = stage
        raw = (json.dumps(state, sort_keys=True, allow_nan=False) + '\n').encode()
        if len(raw) > STATE_LIMIT: raise ValueError('worker_state_limit')
        temp = directory / 'state.tmp'
        with temp.open('wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, directory / 'state.json')
    try:
        save('import')
        try: torch = loader('torch')
        except ImportError:
            state.update(outcome='unsupported', code='torch_unavailable'); save('import'); return
        for key, value in (('torch', str(torch.__version__)), ('hip', getattr(torch.version, 'hip', None)),
                           ('cuda_build', getattr(torch.version, 'cuda', None))):
            state['versions'][key] = value if isinstance(value, str) and VERSION.fullmatch(value) else None
        save('capabilities')
        activity = torch.profiler.ProfilerActivity
        supported = torch.profiler.supported_activities()
        state['advertised_activities'] = [name for name in ('CPU', 'CUDA')
            if getattr(activity, name, None) is not None and getattr(activity, name) in supported]
        required = ['CPU'] if device == 'cpu' else ['CPU', 'CUDA']
        if any(name not in state['advertised_activities'] for name in required):
            state.update(outcome='unsupported', code='activity_unavailable'); save('capabilities'); return
        if device == 'cuda':
            if not torch.cuda.is_available():
                state.update(outcome='unsupported', code='device_unavailable'); save('capabilities'); return
            properties = torch.cuda.get_device_properties(0)
            architecture = getattr(properties, 'gcnArchName', '').split(':', 1)[0]
            if re.fullmatch(r'gfx[0-9a-f]{3,5}', architecture): state['device_architecture'] = architecture
            state['device_name_sha256'] = hashlib.sha256(str(properties.name).encode()).hexdigest()
        torch.set_num_threads(1)  # child only; never change Studio's thread settings
        save('allocate')
        with torch.inference_mode():
            a = torch.ones((16, 16), dtype=torch.float32, device=device)
            if device == 'cuda': torch.cuda.synchronize()
            save('capture')
            with torch.profiler.profile(activities=[getattr(activity, name) for name in required],
                    record_shapes=False, with_stack=False, profile_memory=False) as profiler:
                b = a @ a
                c = b.clone()
                if device == 'cuda': torch.cuda.synchronize()
            save('export')
            path = directory / 'trace.json'; profiler.export_chrome_trace(str(path))
            with path.open('rb') as stream: raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                state.update(outcome='failed', code='trace_too_large'); save('export'); return
            state['trace_sha256'] = hashlib.sha256(raw).hexdigest()
            save('verify')
            state['arithmetic_verified'] = bool((c == 16).all().item())
            if not state['arithmetic_verified']:
                state.update(outcome='failed', code='arithmetic_unverified'); save('verify'); return
        state['outcome'] = 'completed'; save('complete')
    except Exception:
        state.update(outcome='failed', code='probe_failed')
        save(state['stage'])  # payload-free stage survives ordinary failures


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--device', choices=('cpu', 'cuda'), required=True)
    args = parser.parse_args(); collect(args.directory, args.device)


if __name__ == '__main__': main()
