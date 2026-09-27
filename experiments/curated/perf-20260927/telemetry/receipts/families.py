"""One Studio job per preset at its authored defaults (fixed seed), with an independent 0.5 s commit sampler to cross-check
the Studio's own host_commit_windows (lab3, 27 Sep 2026). Usage: python families.py <label> <preset> [<preset> ...]"""
import json, sys, time, threading
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'app'))
import host_memory

STUDIO = 'http://127.0.0.1:8191'; GIB = 1024 ** 3; SEED = 2026092701

def call(url, method='GET', data=None):
    req = Request(url, data=None if data is None else json.dumps(data).encode(), method=method, headers={'Content-Type': 'application/json', 'Origin': STUDIO})
    try:
        with urlopen(req, timeout=60) as r: return r.status, json.loads(r.read() or b'null')
    except HTTPError as e: return e.code, e.read().decode('utf-8', 'replace')

def main():
    label, presets = sys.argv[1], sys.argv[2:]; out = open(Path(__file__).with_name(label + '.jsonl'), 'a', encoding='utf-8')
    def log(r): r['logged_at'] = time.strftime('%Y-%m-%d %H:%M:%S'); print(json.dumps(r)[:600], flush=True); out.write(json.dumps(r) + '\n'); out.flush()
    for preset in presets:
        samples = []; stop = threading.Event()
        def sample():
            while not stop.is_set():
                r = host_memory.read(); samples.append((time.time(), r['available_bytes'], r['committed_bytes'], r['limit_bytes'])); stop.wait(0.5)
        t = threading.Thread(target=sample, daemon=True); t.start()
        status, body = call(STUDIO + '/api/jobs', 'POST', {'preset_id': preset, 'controls': {'seed': SEED}, 'batch_count': 1, 'label': 'lab3 telemetry ' + label})
        if status != 201: stop.set(); log({'event': 'refused', 'preset': preset, 'http': status, 'error': body}); continue
        log({'event': 'created', 'preset': preset, 'job_id': body['id']}); seen = set()
        while True:
            s, job = call(STUDIO + '/api/jobs/' + body['id'])
            for pid in (job.get('prompt_ids') or []) if s == 200 else []:
                if pid not in seen: seen.add(pid); log({'event': 'prompt_id', 'preset': preset, 'job_id': body['id'], 'prompt_id': pid})
            if s == 200 and job.get('status') not in ('queued', 'waiting', 'submitting', 'running'): break
            time.sleep(1)
        stop.set(); t.join(2)
        windows = job.get('host_commit_windows') or []
        # The independent sampler restricted to the Studio window's own time span, for a like-for-like minimum.
        span = [x for x in samples if windows and windows[0]['first_at'] - 0.25 <= x[0] <= windows[-1]['last_at'] + 0.25 and x[1] is not None]
        log({'event': 'job', 'preset': preset, 'job_id': job['id'], 'status': job['status'], 'prompt_ids': job.get('prompt_ids'), 'elapsed_seconds': job.get('elapsed_seconds'),
             'message': job.get('message'), 'host_commit_windows': windows,
             'independent': {'samples_in_window': len(span), 'min_available_gib': round(min(x[1] for x in span) / GIB, 2) if span else None,
                             'peak_pct': round(100 * max(x[2] / x[3] for x in span), 1) if span else None,
                             'whole_run_min_available_gib': round(min(x[1] for x in samples if x[1] is not None) / GIB, 2) if samples else None}})
        time.sleep(3)

if __name__ == '__main__': main()
