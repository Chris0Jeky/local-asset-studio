"""One deliberate Studio job per call, never a retry: `python run_job.py <log.json> <label> <preset> '<controls json>' [reference.png ...]`.
Reference pictures are uploaded first (the page's path); with several they fill `reference`, `reference2`, ... in order.
Appends job id, prompt IDs, timing, host-commit samples and outputs to <log.json>; saves the job's recipe beside it."""
import json, os, subprocess, sys, time, urllib.error, urllib.request

STUDIO = 'http://127.0.0.1:8191'


def get(route): return json.load(urllib.request.urlopen(STUDIO + route, timeout=60))


def commit_pct():
    out = subprocess.run(['powershell', '-NoProfile', '-Command', '$o=Get-CimInstance Win32_OperatingSystem; "{0} {1}" -f $o.FreeVirtualMemory,$o.TotalVirtualMemorySize'],
                         capture_output=True, text=True, timeout=60).stdout.split()
    free, total = int(out[0]), int(out[1]); return round(100 * (1 - free / total), 1)


log, label, preset_id, controls = sys.argv[1], sys.argv[2], sys.argv[3], json.loads(sys.argv[4])
refs = sys.argv[5:]
keys = ['reference'] + ['reference%d' % i for i in range(2, 11)]
for key, path in zip(keys, refs):
    if key in controls: continue
    upload = urllib.request.Request(STUDIO + '/api/upload', open(path, 'rb').read(), {'Content-Type': 'image/png', 'X-Filename': os.path.basename(path), 'Origin': STUDIO})
    controls[key] = json.load(urllib.request.urlopen(upload, timeout=60))['file']
intent = {'preset_id': preset_id, 'controls': controls, 'batch_count': 1, 'parent_assets': []}
commit_before = commit_pct()
request = urllib.request.Request(STUDIO + '/api/jobs', json.dumps(intent).encode(), {'Content-Type': 'application/json', 'Origin': STUDIO})
try: job = json.load(urllib.request.urlopen(request, timeout=60))
except urllib.error.HTTPError as error: print('rejected', error.code, error.read().decode('utf-8', 'replace')[:1500]); sys.exit(1)
print('job', job.get('id'), job.get('status'), flush=True); started = time.time(); peak = commit_before
while time.time() - started < 3600:
    time.sleep(5); state = get('/api/jobs/' + job['id'])
    try: peak = max(peak, commit_pct())
    except Exception: pass
    if state.get('status') in ('completed', 'failed', 'not_submitted', 'uncertain', 'abandoned', 'stopped'):
        result = {k: state.get(k) for k in ('id', 'status', 'preset_id', 'prompt_ids', 'outputs', 'elapsed_seconds', 'error', 'created_at', 'finished_at')}
        result.update(label=label, controls=controls, references=[os.path.basename(r) for r in refs], commit_before_pct=commit_before, commit_peak_pct=peak,
                      poll_wall_s=round(time.time() - started, 1))
        results = json.load(open(log, encoding='utf-8')) if os.path.exists(log) else []
        results.append(result); json.dump(results, open(log, 'w', encoding='utf-8'), indent=1)
        if state.get('status') == 'completed':
            recipe = get('/api/jobs/' + job['id'] + '/recipe')
            json.dump(recipe, open(os.path.join(os.path.dirname(os.path.abspath(log)), 'recipe-' + label + '.json'), 'w', encoding='utf-8'), indent=1)
        print(json.dumps(result, indent=1)[:2500], flush=True); break
else: print('no terminal state after 3600 s; job left alone', job['id'])
