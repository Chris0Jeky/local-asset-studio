"""Load / sample / decode split per census record, from ComfyUI's own log lines (timestamps at 1 s resolution).

    python phase_table.py

For each record: submission time -> 'Requested to load <diffusion model>' (text encoding and model load from disk) ->
'Requested to load <VAE>' (sampling) -> 'Prompt executed' (VAE decode and save), plus the peak shared GPU memory in the
sampling window and in the decode window from the 1.5 s GPU timeline. The census was recorded before labkit filtered log
lines by submission time, so only lines at or after each record's own submission are used here.
"""
import datetime, json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIFFUSION = ('SDXL', 'Anima', 'Lumina2', 'Krea2')
VAES = ('AutoencoderKL', 'WanVAE', 'AutoencodingEngine')


def at(day, hms): return datetime.datetime.combine(day, datetime.time.fromisoformat(hms))


rows = []
for r in json.loads((HERE / 'results.json').read_text(encoding='utf-8')):
    sub = datetime.datetime.fromisoformat(r['submitted_at']); day = sub.date()
    lines = [(at(day, l[:8]), l[9:]) for l in r.get('log_lines', []) if re.match(r'\d\d:\d\d:\d\d ', l)]
    lines = [(t, m) for t, m in lines if t >= sub.replace(microsecond=0)]
    load = next((t for t, m in lines if 'Requested to load' in m and any(m.rstrip().endswith(d) for d in DIFFUSION)), None)
    vae = next((t for t, m in lines if 'Requested to load' in m and any(v in m for v in VAES)), None)
    done = next((t for t, m in lines if 'Prompt executed' in m), None)
    tl = json.loads((HERE / r['timeline_file']).read_text(encoding='utf-8')) if r.get('timeline_file') else None
    def peak(a, b):
        if not tl or not a or not b: return None
        t0 = datetime.datetime.fromisoformat(tl['t0'])
        vals = [s for t, d, s in tl['series'] if a <= t0 + datetime.timedelta(seconds=t) <= b + datetime.timedelta(seconds=1)]
        return max(vals) if vals else None
    rows.append({'label': r['label'], 'total': round(r.get('elapsed_seconds') or 0, 1),
                 'to_sampler': (load - sub).total_seconds() if load else None, 'sampling': (vae - load).total_seconds() if load and vae else None,
                 'decode_save': (done - vae).total_seconds() if vae and done else None,
                 'shared_sampling_mb': peak(load, vae), 'shared_decode_mb': peak(vae, done)})
print('| preset | total s | submit -> sampler s | sampling s | decode + save s | peak shared MB while sampling | peak shared MB while decoding |')
print('| --- | --- | --- | --- | --- | --- | --- |')
for x in rows:
    print('| %s | %s | %s | %s | %s | %s | %s |' % tuple(x.get(k) if x.get(k) is not None else '-' for k in
          ('label', 'total', 'to_sampler', 'sampling', 'decode_save', 'shared_sampling_mb', 'shared_decode_mb')))
(HERE / 'phases.json').write_text(json.dumps(rows, indent=1) + '\n', encoding='utf-8', newline='\n')
