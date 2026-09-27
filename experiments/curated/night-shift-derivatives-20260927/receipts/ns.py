# As-run script (27 Sep 2026), kept as a receipt; hardcodes this machine's local paths and is not a portable reproduction.
"""Night Shift derivative driver (27 Sep 2026). Studio jobs via the Studio API; one direct ComfyUI graph for the raw 4x upscale.
Every run appends one JSON line to runs.jsonl with job/prompt IDs, input and output sha256, sizes and receipt timings."""
import hashlib, json, sys, time, urllib.request
sys.path.insert(0, 'C:/Users/jekyt/AppData/Local/Temp/cancel-proof-0927')
import drive
from PIL import Image
OUTROOT = 'C:/AI/ComfyUI_windows_portable/ComfyUI/output/'
ANCHOR = OUTROOT + 'Research/lab-20260927/asset-kit/retro-anime-master/retro-anime-master-z2.png'
ANCHOR_SHA = 'c22b723c65198b896ff9e542b05745742a447b62e91a7e5cfb8c0f593df7dfa9'
HERE = 'C:/Users/jekyt/AppData/Local/Temp/nightshift-0927/'
RUNS = 'C:/Users/jekyt/source/local-asset-studio/experiments/runs/'

def sha(path): return hashlib.sha256(open(path, 'rb').read()).hexdigest()

def log(rec):
    rec['logged_at'] = time.time(); open(HERE + 'runs.jsonl', 'a', encoding='utf-8').write(json.dumps(rec) + '\n'); print(json.dumps(rec)[:600], flush=True)

def upload(path, name):
    body = open(path, 'rb').read()
    r = urllib.request.Request(drive.S + '/api/upload', data=body, method='POST',
                               headers={'Content-Type': 'image/png', 'X-Filename': name, 'Origin': drive.S})
    with urllib.request.urlopen(r, timeout=60) as f: meta = json.loads(f.read())
    assert meta['sha256'] == sha(path), 'upload bytes differ'
    return meta

def studio_job(key, preset, controls, input_sha=None, batch=1, label=None):
    r, p = drive.queue(); assert not r and not p, 'queue busy'
    c0 = drive.commit()
    code, body = drive.studio('/api/jobs', {'preset_id': preset, 'controls': controls, 'batch_count': batch, 'label': label or key})
    assert code == 201, body
    jid = body['id']; t0 = time.time()
    while True:
        j = drive.job(jid)
        if j['status'] not in drive.ACTIVE: break
        time.sleep(1)
    state = json.load(open(RUNS + jid + '/state.json', encoding='utf-8'))
    outs = []
    for o in j.get('outputs', []):
        path = OUTROOT + (o.get('subfolder') + '/' if o.get('subfolder') else '') + o['filename']
        im = Image.open(path); outs.append({'path': path, 'sha256': sha(path), 'size': im.size, 'mode': im.mode, 'prompt_id': o.get('prompt_id'), 'seed': o.get('seed')})
    peaks = [w.get('peak_percent') or w.get('peak_commit_percent') for w in state.get('host_commit_windows', [])]
    rec = {'key': key, 'preset': preset, 'job_id': jid, 'status': j['status'], 'message': j.get('message'), 'prompt_ids': j.get('prompt_ids'),
           'controls': {k: v for k, v in controls.items()}, 'input_sha256': input_sha, 'outputs': outs,
           'created_at': state.get('created_at'), 'started_at': state.get('started_at'), 'finished_at': state.get('finished_at'),
           'elapsed_seconds': state.get('elapsed_seconds'), 'host_commit_windows': state.get('host_commit_windows'), 'commit_before': c0, 'commit_after': drive.commit()}
    log(rec); return rec

def direct(key, graph, input_sha=None):
    r, p = drive.queue(); assert not r and not p, 'queue busy'
    c0 = drive.commit(); t0 = time.time()
    code, reply = drive.comfy('/prompt', {'prompt': graph, 'client_id': 'nightshift-derive-0927'}); assert code == 200, reply
    pid = reply['prompt_id']
    while True:
        h = drive.comfy('/history/' + pid)[1].get(pid)
        if h: break
        time.sleep(1)
    msgs = h['status']['messages']; ts = {m[0]: m[1].get('timestamp') for m in msgs if isinstance(m[1], dict)}
    outs = []
    for node in h.get('outputs', {}).values():
        for o in node.get('images', []):
            path = OUTROOT + (o['subfolder'] + '/' if o['subfolder'] else '') + o['filename']
            im = Image.open(path); outs.append({'path': path, 'sha256': sha(path), 'size': im.size, 'mode': im.mode})
    rec = {'key': key, 'route': 'direct-comfyui', 'prompt_id': pid, 'status': h['status']['status_str'], 'input_sha256': input_sha, 'graph': graph,
           'exec_seconds': (ts.get('execution_success', 0) - ts.get('execution_start', 0)) / 1000 if ts.get('execution_success') else None,
           'wall_seconds': round(time.time() - t0, 1), 'outputs': outs, 'commit_before': c0, 'commit_after': drive.commit()}
    log(rec); return rec
