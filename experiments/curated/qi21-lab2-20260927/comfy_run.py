"""Submit one API graph to a ComfyUI once (never a retry) and record the outcome.
`python comfy_run.py <log.json> <label> <graph.json> [--url http://127.0.0.1:8196]`
Refuses when host commit headroom is below 32 GiB (the Studio's Qwen gate). Appends prompt ID, wall time,
execution time from /history, host-commit samples and outputs to <log.json>; copies the submitted graph beside it."""
import json, os, subprocess, sys, time, uuid, urllib.request

args = sys.argv[1:]; url = 'http://127.0.0.1:8196'; floor = 32
if '--min-headroom' in args: i = args.index('--min-headroom'); floor = float(args[i + 1]); del args[i:i + 2]
if '--url' in args: i = args.index('--url'); url = args[i + 1]; del args[i:i + 2]
log, label, graph_path = args
graph = json.load(open(graph_path, encoding='utf-8'))


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
entry = None
while time.time() - started < 3600:
    time.sleep(4)
    try: peak = max(peak, commit()[0])
    except Exception: pass
    h = json.load(urllib.request.urlopen(url + '/history/' + pid, timeout=60))
    if pid in h and h[pid].get('status', {}).get('completed') is not None or (pid in h and h[pid].get('status', {}).get('status_str') in ('success', 'error')):
        entry = h[pid]; break
wall = round(time.time() - started, 1)
result = {'label': label, 'prompt_id': pid, 'url': url, 'submitted_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(started)), 'wall_s': wall,
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
results = json.load(open(log, encoding='utf-8')) if os.path.exists(log) else []
results.append(result); json.dump(results, open(log, 'w', encoding='utf-8'), indent=1)
json.dump(graph, open(os.path.join(os.path.dirname(os.path.abspath(log)), 'graph-' + label + '.json'), 'w', encoding='utf-8'), indent=1)
print(json.dumps(result, indent=1), flush=True)
