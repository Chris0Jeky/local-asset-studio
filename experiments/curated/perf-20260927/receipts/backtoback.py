"""Back-to-back qwen21 jobs through the running Studio, with commit receipts (lab3, 27 Sep 2026).

Usage: python backtoback.py <label> [--manual-free] [--batch N] [--count N]
Each create is a fresh Studio job. A refused create never existed as a job, so a later create is not a resubmission.
--manual-free reproduces today's workaround: on a headroom refusal, POST /free to the qwen21 backend and wait for headroom.
"""
import json, sys, time, threading, argparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pathlib import Path
ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'app' / 'host_memory.py').is_file())   # the repository, from any copy of this driver
sys.path.insert(0, str(ROOT / 'app'))
import host_memory

STUDIO = 'http://127.0.0.1:8191'; QWEN = 'http://127.0.0.1:8196'; GIB = 1024 ** 3
PROMPT = ("A quiet geometric line illustration of an open empty folio with one inviting blank picture frame resting on its right page "
          "and a small four-point star above it, thin even neutral grey line work with one soft warm amber accent, flat minimal style, "
          "centred, full object visible, no text.")

def call(url, method='GET', data=None, timeout=60):
    body = None if data is None else json.dumps(data).encode()
    headers = {'Content-Type': 'application/json'} if body is not None else {}
    if url.startswith(STUDIO): headers['Origin'] = STUDIO   # ComfyUI refuses a foreign Origin with 403
    req = Request(url, data=body, method=method, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as r: raw = r.read(); return r.status, (json.loads(raw) if raw else None)
    except HTTPError as e:
        raw = e.read()
        try: return e.code, json.loads(raw)
        except ValueError: return e.code, raw.decode('utf-8', 'replace')

def commit():
    r = host_memory.read(); a, l, c = r['available_bytes'], r['limit_bytes'], r['committed_bytes']
    return {'t': round(time.time(), 2), 'available_gib': round(a / GIB, 2), 'committed_gib': round(c / GIB, 2), 'limit_gib': round(l / GIB, 2), 'pct': round(100 * c / l, 1)}

class Sampler:
    def __init__(self): self.samples = []; self.stop = threading.Event(); self.t = threading.Thread(target=self.run, daemon=True); self.t.start()
    def run(self):
        while not self.stop.is_set(): self.samples.append(commit()); self.stop.wait(0.5)
    def close(self): self.stop.set(); self.t.join(2); return self.samples

def log(out, record): record.setdefault('logged_at', time.strftime('%Y-%m-%d %H:%M:%S')); print(json.dumps(record), flush=True); out.write(json.dumps(record) + '\n'); out.flush()

def wait_job(job_id, out, key):
    logged = set()
    while True:
        status, job = call(STUDIO + '/api/jobs/' + job_id)
        if status == 200:
            for pid in job.get('prompt_ids') or []:   # persist every prompt ID as soon as the Studio reports it
                if pid not in logged: logged.add(pid); log(out, {'event': 'prompt_id', 'key': key, 'job_id': job_id, 'prompt_id': pid, 'job_status': job.get('status'), 'message': job.get('message')})
            if job.get('status') not in ('queued', 'waiting', 'submitting', 'running'): return job
        time.sleep(1)

def manual_free(out, key):
    before = commit(); start = time.time(); status, _ = call(QWEN + '/free', 'POST', {'unload_models': True, 'free_memory': True})
    posted = time.time(); samples = []
    while time.time() - start < 90:
        c = commit(); samples.append(c)
        if c['available_gib'] >= 32: break
        time.sleep(0.5)
    log(out, {'event': 'manual_free', 'key': key, 'http': status, 'before': before, 'after': samples[-1], 'post_seconds': round(posted - start, 2),
              'seconds_to_32gib': round(samples[-1]['t'] - start, 2) if samples[-1]['available_gib'] >= 32 else None, 'samples': len(samples)})

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('label'); ap.add_argument('--manual-free', action='store_true'); ap.add_argument('--batch', type=int, default=1)
    ap.add_argument('--count', type=int, default=3); ap.add_argument('--seed', type=int, default=2026092761); args = ap.parse_args()
    out = open(Path(__file__).with_name(args.label + '.jsonl'), 'a', encoding='utf-8')
    status, backends = call(STUDIO + '/api/backends'); log(out, {'event': 'start', 'label': args.label, 'backend': backends.get('active'), 'busy': backends.get('busy'), 'commit': commit()})
    if backends.get('active') != 'qwen21': log(out, {'event': 'abort', 'reason': 'qwen21 backend not active'}); return
    for k in range(args.count):
        key = f'{args.label}-{k + 1}'
        recipe = {'preset_id': 'qwen21-rgba', 'controls': {'positive': PROMPT, 'width': 1024, 'height': 1024, 'seed': args.seed + k}, 'batch_count': args.batch, 'label': 'lab3 perf ' + key}
        for attempt in (1, 2):
            before = commit(); sampler = Sampler(); t0 = time.time()
            status, body = call(STUDIO + '/api/jobs', 'POST', recipe)
            if status != 201:
                samples = sampler.close(); log(out, {'event': 'refused', 'key': key, 'attempt': attempt, 'http': status, 'error': body, 'commit': before})
                if args.manual_free and attempt == 1: manual_free(out, key); continue
                break
            log(out, {'event': 'created', 'key': key, 'attempt': attempt, 'job_id': body['id'], 'status': body.get('status'), 'message': body.get('message'), 'commit': before})
            job = wait_job(body['id'], out, key); wall = time.time() - t0; samples = sampler.close()
            peak = max(samples, key=lambda s: s['pct']) if samples else None
            log(out, {'event': 'job', 'key': key, 'attempt': attempt, 'job_id': job['id'], 'status': job['status'], 'prompt_ids': job.get('prompt_ids'), 'message': job.get('message'), 'commit_releases': job.get('commit_releases'),
                      'wall_seconds': round(wall, 1), 'elapsed_seconds': job.get('elapsed_seconds'), 'commit_before': before, 'commit_peak': peak, 'commit_end': commit(), 'samples': len(samples)})
            time.sleep(3); log(out, {'event': 'settled', 'key': key, 'commit_3s_after': commit()})
            break
    log(out, {'event': 'end', 'commit': commit()})

if __name__ == '__main__': main()
