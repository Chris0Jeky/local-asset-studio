"""Proving runs for the Qwen-Image 2.1 recipes through the Studio's own path (POST /api/jobs: prepare -> worker -> the active
isolated backend), the shape the page submits. The Studio must already be switched to *Qwen-Image 2.1 · isolated*.
One deliberate run per call, never a retry: `python prove_studio.py qwen21-t2i`. Evidence goes to prove_studio.json
(job, prompt IDs, timing, outputs) and the job's exported recipe to recipe-<preset>.json beside this file."""
import json, os, sys, time, urllib.error, urllib.request

OUT = os.path.dirname(os.path.abspath(__file__)); STUDIO = 'http://127.0.0.1:8191'
REFERENCE = os.path.join(OUT, '..', '..', '..', 'examples', 'references', 'studio-lantern-cutout.png')


def get(route): return json.load(urllib.request.urlopen(STUDIO + route, timeout=60))


preset_id = sys.argv[1]
catalog = get('/api/catalog'); preset = next(p for p in catalog['presets'] if p['id'] == preset_id)
if preset.get('runtime_block'): raise SystemExit('Blocked: ' + preset['runtime_block'])
controls = {'seed': 2026092211}
if preset_id == 'qwen21-edit':
    # The page uploads the picture first; the job then names the generated upload, never a client path.
    upload = urllib.request.Request(STUDIO + '/api/upload', open(REFERENCE, 'rb').read(), {'Content-Type': 'image/png', 'X-Filename': 'studio-lantern-cutout.png', 'Origin': STUDIO})
    controls['reference'] = json.load(urllib.request.urlopen(upload, timeout=60))['file']
intent = {'preset_id': preset_id, 'controls': controls, 'batch_count': 1, 'parent_assets': []}
request = urllib.request.Request(STUDIO + '/api/jobs', json.dumps(intent).encode(), {'Content-Type': 'application/json', 'Origin': STUDIO})
try: job = json.load(urllib.request.urlopen(request, timeout=60))
except urllib.error.HTTPError as error: print('rejected', error.code, error.read().decode('utf-8', 'replace')[:1500]); sys.exit(1)
print('job', job.get('id'), job.get('status'), flush=True); started = time.time()
while time.time() - started < 3600:
    time.sleep(5); state = get('/api/jobs/' + job['id'])
    if state.get('status') in ('completed', 'failed', 'not_submitted', 'uncertain', 'abandoned', 'stopped'):
        result = {k: state.get(k) for k in ('id', 'status', 'preset_id', 'prompt_ids', 'outputs', 'elapsed_seconds', 'error', 'created_at', 'comfy_url')}
        result['controls'] = controls
        log = os.path.join(OUT, 'prove_studio.json'); results = json.load(open(log)) if os.path.exists(log) else []
        results.append(result); json.dump(results, open(log, 'w'), indent=1)
        if state.get('status') == 'completed':
            recipe = get('/api/jobs/' + job['id'] + '/recipe'); json.dump(recipe, open(os.path.join(OUT, 'recipe-' + preset_id + '.json'), 'w'), indent=1)
        print(json.dumps(result, indent=1)[:3000], flush=True); break
else: print('no terminal state after 3600 s; job left alone', job['id'])
