"""Phase breakdown of one recorded job from its ComfyUI log lines and GPU timeline.

    python phases.py <results-folder> <label>

Prints the load / sample / decode boundaries (from 'Requested to load' lines and the sampler's step timestamps) and the
GPU memory peak inside each phase, so a spill can be attributed to model loading, sampling or VAE decoding.
"""
import datetime, json, sys
from pathlib import Path

folder, label = Path(sys.argv[1]), sys.argv[2]
rec = next(r for r in json.loads((folder / 'results.json').read_text(encoding='utf-8')) if r['label'] == label)
tl = json.loads((folder / rec['timeline_file']).read_text(encoding='utf-8'))
t0 = datetime.datetime.fromisoformat(tl['t0'])
print(label, rec.get('status'), 'wall', rec.get('wall_seconds'), 'executed', rec.get('comfy_executed_seconds'))
for line in rec.get('log_lines', []): print('  ', line[:150])
for s in rec.get('sampler_runs', []): print('  sampler', s)
prev = None
for t, ded, sh in tl['series']:
    if prev is None or abs(ded - prev[0]) > 300 or abs(sh - prev[1]) > 300:
        print('   %7.1f s  %s  dedicated %6d MB  shared %6d MB' % (t, (t0 + datetime.timedelta(seconds=t)).strftime('%H:%M:%S'), ded, sh))
        prev = (ded, sh)
