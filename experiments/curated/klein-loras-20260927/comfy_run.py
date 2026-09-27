"""Submit one API graph to a ComfyUI once (never a retry) and record the outcome.
`python comfy_run.py <log.json> <label> <graph.json> [--url http://127.0.0.1:8188]` (this study: the primary on 8188)
Refuses when host commit headroom is below 32 GiB (the Studio's Qwen gate). Appends prompt ID, wall time,
execution time from /history, host-commit samples and outputs to <log.json>; copies the submitted graph beside it.
The prompt ID is written to <log.json> as a `pending` receipt as soon as ComfyUI accepts it and finalised after polling;
a log that still holds a pending receipt refuses new submissions until it is reconciled by hand (never resubmit)."""
import json, os, subprocess, sys, time, uuid, urllib.request

args = sys.argv[1:]; url = 'http://127.0.0.1:8188'; floor = 32
if '--min-headroom' in args: i = args.index('--min-headroom'); floor = float(args[i + 1]); del args[i:i + 2]
if '--url' in args: i = args.index('--url'); url = args[i + 1]; del args[i:i + 2]
log, label, graph_path = args
graph = json.load(open(graph_path, encoding='utf-8'))


def load(): return json.load(open(log, encoding='utf-8')) if os.path.exists(log) else []


def save(results):
    tmp = log + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f: json.dump(results, f, indent=1)
    os.replace(tmp, log)


pending = [r['prompt_id'] for r in load() if r.get('status') == 'pending']
if pending: raise SystemExit(f'refused: {log} holds pending prompt(s) {pending}; check /history and reconcile before submitting again')


def commit():
    out = subprocess.run(['powershell', '-NoProfile', '-Command', '$o=Get-CimInstance Win32_OperatingSystem; "{0} {1}" -f $o.FreeVirtualMemory,$o.TotalVirtualMemorySize'],
                         capture_output=True, text=True, timeout=60).stdout.split()
    free, total = int(out[0]), int(out[1]); return round(100 * (1 - free / total), 1), round(free / 1048576, 1)


pct, headroom = commit()
if headroom < floor: raise SystemExit(f'refused: commit headroom {headroom} GiB < {floor} GiB ({pct} %)')
body = json.dumps({'prompt': graph, 'client_id': 'lab2-' + uuid.uuid4().hex[:8]}).encode()
started = time.time()
reply = json.load(urllib.request.urlopen(urllib.request.Request(url + '/prompt', body, {'Content-Type': 'application/json'}), timeout=60))
pid = reply['prompt_id']; print('prompt', pid, flush=True); peak = pct
submitted_at = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(started))
save(load() + [{'label': label, 'prompt_id': pid, 'url': url, 'submitted_at': submitted_at, 'status': 'pending', 'commit_before_pct': pct}])
entry = None
while time.time() - started < 3600:
    time.sleep(4)
    try: peak = max(peak, commit()[0])
    except Exception: pass
    h = json.load(urllib.request.urlopen(url + '/history/' + pid, timeout=60))
    st = h.get(pid, {}).get('status', {})  # done only on completed true or a terminal status_str
    if st.get('completed') is True or st.get('status_str') in ('success', 'error'): entry = h[pid]; break
wall = round(time.time() - started, 1)
result = {'label': label, 'prompt_id': pid, 'url': url, 'submitted_at': submitted_at, 'wall_s': wall,
          'commit_before_pct': pct, 'commit_peak_pct': peak}
if entry is None: result['status'] = 'no history after 3600 s; left alone'
else:
    st = entry.get('status', {}); result['status'] = st.get('status_str')
    msgs = {m[0]: m[1].get('timestamp') for m in st.get('messages', []) if isinstance(m, list) and len(m) == 2 and isinstance(m[1], dict)}
    if 'execution_start' in msgs and ('execution_success' in msgs or 'execution_error' in msgs):
        result['exec_s'] = round(((msgs.get('execution_success') or msgs.get('execution_error')) - msgs['execution_start']) / 1000, 1)
    result['outputs'] = [img for node in entry.get('outputs', {}).values() for img in node.get('images', [])]
    errs = [m for m in st.get('messages', []) if m[0] == 'execution_error']
    if errs: result['error'] = {k: errs[0][1].get(k) for k in ('node_id', 'node_type', 'exception_message')}
save([result if r.get('prompt_id') == pid and r.get('status') == 'pending' else r for r in load()])
json.dump(graph, open(os.path.join(os.path.dirname(os.path.abspath(log)), 'graph-' + label + '.json'), 'w', encoding='utf-8'), indent=1)
print(json.dumps(result, indent=1), flush=True)
