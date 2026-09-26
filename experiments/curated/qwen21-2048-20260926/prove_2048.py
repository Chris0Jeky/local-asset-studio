"""Frozen 2048x2048 proving run for qwen21-t2i (issue #739 leftover), 26 September 2026.

Frozen inputs: preset qwen21-t2i, Native 2K square (2048x2048), default brief,
seed 2026092601, 25 steps, batch 1. Budget: this one job; no resubmission on any
outcome (uncertain outcomes are reconciled from the retained prompt ID, never rerun).
Stop: 3600 s without a terminal state leaves the job alone for later Resume.
Review: output exists at 2048x2048, wall time and peak GPU recorded, every output
opened and described in plain words. Evidence: run-2048.json + recipe-qwen21-t2i-2048.json
beside this file. The Studio must already be switched to Qwen-Image 2.1 isolated."""
import json, os, sys, time, urllib.error, urllib.request

OUT = os.path.dirname(os.path.abspath(__file__)); STUDIO = 'http://127.0.0.1:8191'


def get(route): return json.load(urllib.request.urlopen(STUDIO + route, timeout=60))


catalog = get('/api/catalog'); preset = next(p for p in catalog['presets'] if p['id'] == 'qwen21-t2i')
if preset.get('runtime_block'): raise SystemExit('Blocked: ' + preset['runtime_block'])
controls = {'seed': 2026092601, 'width': 2048, 'height': 2048, 'steps': 25}
intent = {'preset_id': 'qwen21-t2i', 'controls': controls, 'batch_count': 1, 'parent_assets': []}
request = urllib.request.Request(STUDIO + '/api/jobs', json.dumps(intent).encode(), {'Content-Type': 'application/json', 'Origin': STUDIO})
try: job = json.load(urllib.request.urlopen(request, timeout=60))
except urllib.error.HTTPError as error: print('rejected', error.code, error.read().decode('utf-8', 'replace')[:1500]); sys.exit(1)
print('job', job.get('id'), job.get('status'), flush=True); started = time.time()
while time.time() - started < 3600:
    time.sleep(10); state = get('/api/jobs/' + job['id'])
    if state.get('status') in ('completed', 'failed', 'not_submitted', 'uncertain', 'abandoned', 'stopped'):
        result = {k: state.get(k) for k in ('id', 'status', 'preset_id', 'prompt_ids', 'outputs', 'elapsed_seconds', 'error', 'created_at', 'comfy_url')}
        result['controls'] = controls
        json.dump(result, open(os.path.join(OUT, 'run-2048.json'), 'w'), indent=1)
        if state.get('status') == 'completed':
            recipe = get('/api/jobs/' + job['id'] + '/recipe'); json.dump(recipe, open(os.path.join(OUT, 'recipe-qwen21-t2i-2048.json'), 'w'), indent=1)
        print(json.dumps(result, indent=1)[:3000], flush=True); break
else: print('no terminal state after 3600 s; job left alone', job['id'])
