# As-run driver for this proof (27 Sep 2026), kept as a receipt. It hardcodes this machine's local paths
# (Studio runs folder, scratch output folder) and is not a portable reproduction.
"""Live proof driver for #1138 (owner cancel). One case per invocation: python drive.py be|c|a
Only the Studio's own jobs are cancelled, through POST /api/jobs/<id>/cancel. The case-a blocker is this
driver's own ComfyUI prompt; it is never cancelled or deleted."""
import copy, ctypes, json, sys, time, urllib.error, urllib.request
from ctypes import wintypes
S = 'http://127.0.0.1:8191'; C = 'http://127.0.0.1:8188'
RUNS = 'C:/Users/jekyt/source/local-asset-studio/experiments/runs'
OUT = 'C:/Users/jekyt/AppData/Local/Temp/cancel-proof-0927'
ACTIVE = ('queued', 'waiting', 'submitting', 'running')
POS = 'no humans, scenery, stone lighthouse on a sea cliff, calm ocean, sunset sky, soft clouds, wide shot, masterpiece, best quality'
events = []

def ev(kind, **kw):
    e = dict(t=round(time.time(), 3), kind=kind, **kw); events.append(e); print(json.dumps(e)[:400], flush=True)

def req(base, path, body=None, origin=False):
    h = {'Content-Type': 'application/json'}
    if origin: h['Origin'] = S
    r = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(), headers=h, method='GET' if body is None else 'POST')
    try:
        with urllib.request.urlopen(r, timeout=30) as f: b = f.read(); return f.status, (json.loads(b) if b else None)
    except urllib.error.HTTPError as e: return e.code, e.read().decode('utf-8', 'replace')[:500]

studio = lambda p, b=None: req(S, p, b, origin=True)
comfy = lambda p, b=None: req(C, p, b)

def queue():
    q = comfy('/queue')[1]; return [e[1] for e in q['queue_running']], [e[1] for e in q['queue_pending']]

def job(jid): return studio('/api/jobs/' + jid)[1]

class PERF(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD)] + [(n, ctypes.c_size_t) for n in ('CommitTotal', 'CommitLimit', 'CommitPeak', 'PhysicalTotal', 'PhysicalAvailable', 'SystemCache', 'KernelTotal', 'KernelPaged', 'KernelNonpaged', 'PageSize')] + [(n, wintypes.DWORD) for n in ('HandleCount', 'ProcessCount', 'ThreadCount')]

def commit():
    p = PERF(); p.cb = ctypes.sizeof(p); ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(p), p.cb)
    g = lambda v: round(v * p.PageSize / 1024**3, 1)
    return {'commit_gib': g(p.CommitTotal), 'limit_gib': g(p.CommitLimit), 'pct': round(100 * p.CommitTotal / p.CommitLimit, 1), 'phys_avail_gib': g(p.PhysicalAvailable)}

def log_counts():
    d = comfy('/internal/logs/raw')[1]; ms = [x['m'] for x in d['entries']]
    return {'got_prompt': sum('got prompt' in m for m in ms), 'interrupted': sum('Processing interrupted' in m for m in ms),
            'executed': sum('Prompt executed' in m for m in ms), 'entries': len(ms)}

def create(label, batch, steps, seed):
    code, body = studio('/api/jobs', {'preset_id': 'wai', 'label': label, 'batch_count': batch,
                                      'controls': {'positive': POS, 'seed': seed, 'steps': steps, 'width': 832, 'height': 1216}})
    ev('create', label=label, code=code, id=body.get('id') if isinstance(body, dict) else body, status=body.get('status') if isinstance(body, dict) else None)
    assert code == 201, body
    return body['id']

def cancel(jid):
    t0 = time.time(); code, body = studio('/api/jobs/%s/cancel' % jid, {})
    ev('cancel', id=jid, code=code, took=round(time.time() - t0, 3), status=body.get('status') if isinstance(body, dict) else body,
       cancellation=(body.get('cancellation') if isinstance(body, dict) else None))
    return code, body

def settle(jid, limit=600):
    end = time.time() + limit
    while time.time() < end:
        j = job(jid)
        if j['status'] not in ACTIVE and (j.get('cancellation') or {}).get('state') != 'requested': return j
        time.sleep(0.5)
    raise SystemExit('job did not settle: ' + jid)

def wait_idle(limit=600):
    end = time.time() + limit
    while time.time() < end:
        r, p = queue()
        if not r and not p: return
        time.sleep(1)
    raise SystemExit('queue did not drain')

def dump(name, jid, extra=None):
    j = job(jid)
    state = json.load(open('%s/%s/state.json' % (RUNS, jid), encoding='utf-8'))
    for s in state.get('submissions', []): s.pop('graph', None)
    hist = {}
    for pid in j.get('prompt_ids', []):
        h = comfy('/history/' + pid)[1].get(pid)
        hist[pid] = None if h is None else {'status': h['status'], 'client_id': h['prompt'][3].get('client_id'), 'output_nodes': sorted(h.get('outputs', {}))}
    rec = {'job_public': j, 'state_json': state, 'history': hist, 'extra': extra or {}}
    json.dump(rec, open('%s/%s-%s.json' % (OUT, name, jid[:8]), 'w', encoding='utf-8'), indent=1)
    ev('settled', name=name, id=jid, status=j['status'], message=j.get('message'), cancel_state=(j.get('cancellation') or {}).get('state'),
       prompt_ids=j.get('prompt_ids'), subs=[(s.get('index'), s.get('status')) for s in state.get('submissions', [])], outputs=len(j.get('outputs', [])),
       history={k: (v and v['status']['status_str']) for k, v in hist.items()})
    return j

def pre(name):
    r, p = queue(); ev('pre', name=name, running=r, pending=p, commit=commit(), log=log_counts(), lease=studio('/api/gpu-lease')[1].get('held'))
    assert not r and not p, 'ComfyUI queue not empty'

def post(name):
    wait_idle(); r, p = queue(); ev('post', name=name, running=r, pending=p, commit=commit(), log=log_counts())

def case_be():
    pre('be')
    b = create('cancel-proof-b-running', 1, 40, 927001)
    e = create('cancel-proof-e-studio-queued', 1, 20, 927002)
    while job(b)['status'] == 'queued': time.sleep(0.2)
    je = job(e); ev('e_before_cancel', status=je['status'], can_cancel=je.get('can_cancel'), never_submitted=je.get('never_submitted'))
    cancel(e); dump('e', settle(e, 30)['id'])
    while True:
        j = job(b); r, p = queue()
        if j.get('prompt_ids') and r == j['prompt_ids'][:1] and not p: break
        if j['status'] not in ACTIVE: raise SystemExit('b finished before it was seen running')
        time.sleep(0.2)
    ev('b_running_seen', prompt_id=r[0], running=r, pending=p, job_status=j['status'])
    time.sleep(3)   # a few sampler steps in, still running
    r, p = queue(); ev('b_before_cancel', running=r, pending=p)
    cancel(b); dump('b', settle(b)['id']); post('be')

def case_c():
    pre('c')
    c = create('cancel-proof-c-partial', 3, 40, 927101)
    while True:
        j = job(c); r, p = queue(); subs = j.get('submissions') or []
        if len(j.get('prompt_ids', [])) >= 2 and subs[0].get('status') == 'completed' and r == [j['prompt_ids'][1]] and not p: break
        if j['status'] not in ACTIVE: raise SystemExit('c finished early: ' + j['status'])
        time.sleep(0.2)
    ev('c_member2_running', running=r, pending=p, subs=[(s.get('index'), s.get('status')) for s in subs], outputs=len(j.get('outputs', [])))
    time.sleep(3); r, p = queue(); ev('c_before_cancel', running=r, pending=p)
    cancel(c); dump('c', settle(c)['id']); post('c')

def case_a():
    pre('a')
    a = create('cancel-proof-a-pending', 2, 30, 927201)
    while True:
        j = job(a); r, p = queue()
        if j.get('prompt_ids') and r == j['prompt_ids'][:1]: break
        if j['status'] not in ACTIVE: raise SystemExit('a finished early')
        time.sleep(0.2)
    graph = json.load(open('%s/%s/state.json' % (RUNS, a), encoding='utf-8'))['submissions'][0]['graph']
    blocker = copy.deepcopy(graph)
    for n in blocker.values():
        if n['class_type'] == 'KSampler': n['inputs'].update(steps=60, seed=927299)
        if n['class_type'] == 'SaveImage': n['inputs']['filename_prefix'] = 'cancel-proof/blocker'
    code, reply = comfy('/prompt', {'prompt': blocker, 'client_id': 'cancel-proof-blocker'})
    bpid = reply['prompt_id']; ev('blocker_posted', code=code, prompt_id=bpid, a_running=r)
    while True:
        j = job(a); r, p = queue()
        if len(j.get('prompt_ids', [])) == 2: break
        if j['status'] not in ACTIVE: raise SystemExit('a finished early: ' + j['status'])
        time.sleep(0.1)
    pid2 = j['prompt_ids'][1]
    ev('a_member2_posted', pid2=pid2, running=r, pending=p, member2_pending=pid2 in p, blocker_running=r == [bpid])
    if not (pid2 in p and r == [bpid]): raise SystemExit('pending state not arranged; not cancelling')
    cancel(a); ja = settle(a, 120); r, p = queue(); ev('a_after', running=r, pending=p)
    dump('a', a, {'blocker_prompt_id': bpid}); post('a')
    h = comfy('/history/' + bpid)[1].get(bpid); ev('blocker_history', status=h and h['status']['status_str'], client_id=h and h['prompt'][3].get('client_id'))

if __name__ == '__main__':
    name = sys.argv[1]
    try: {'be': case_be, 'c': case_c, 'a': case_a}[name]()
    finally: json.dump(events, open('%s/events-%s.json' % (OUT, name), 'w', encoding='utf-8'), indent=1)
