"""Shared harness for the overnight lab of 23 September 2026 (lab runner and judge).

One deliberate GPU job at a time, with evidence. Every submission:
- refuses unless `.runtime/gpu-lease.json` (main checkout) names `overnight-lab`, the primary ComfyUI queue is empty and
  the Studio has no in-flight job;
- writes the prompt ID (or the Studio job ID) to the experiment's `results.json` as `submitted` BEFORE polling, and a
  network error on the submission itself is recorded as `unresolved`, never retried;
- samples the ComfyUI process's dedicated/shared GPU memory every 1.5 s (app/gpu_memory.py) and host commit, and reads
  ComfyUI's own log buffer (`/internal/logs/raw`) for model-load lines and the sampler's per-step timestamps;
- never resubmits: a timeout leaves an `uncertain` record naming the prompt for inspection.

Direct research graphs go to ComfyUI on 8188 (`run_graph`); preset proofs go through the Studio on 8191 (`run_studio`).
"""
import datetime, hashlib, json, random, re, threading, time, urllib.error, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MAIN = Path('C:/Users/jekyt/Desktop/Printer Config/Others/Git/local-asset-studio')
LEASE = MAIN / '.runtime/gpu-lease.json'
COMFY = 'http://127.0.0.1:8188'
STUDIO = 'http://127.0.0.1:8191'
OUTPUT = Path('C:/AI/ComfyUI_windows_portable/ComfyUI/output')
IN_FLIGHT = {'queued', 'running', 'waiting', 'submitting', 'observing', 'resumed'}
TERMINAL = {'completed', 'failed', 'stopped', 'abandoned', 'not_submitted', 'uncertain'}
import sys
sys.path.insert(0, str(REPO / 'app'))
import gpu_memory  # noqa: E402


def now(): return str(datetime.datetime.now())


def http(url, body=None, timeout=60, origin=None):
    headers = {'Content-Type': 'application/json'}
    if origin: headers['Origin'] = origin
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(urllib.request.Request(url, data, headers), timeout=timeout) as reply: return json.load(reply)


def lease_holder():
    try: return json.loads(LEASE.read_text(encoding='utf-8')).get('holder')
    except (OSError, ValueError): return None


def guard():
    """Raise SystemExit unless the lab holds the lease and both queues are idle."""
    if (REPO / '.runtime' / 'lab-scratch' / 'PAUSE').exists(): raise SystemExit('lab paused (.runtime/lab-scratch/PAUSE); nothing submitted')
    holder = lease_holder()
    if holder != 'overnight-lab': raise SystemExit('GPU lease holder is %r, not overnight-lab; nothing submitted' % holder)
    queue = http(COMFY + '/queue')
    if queue.get('queue_running') or queue.get('queue_pending'): raise SystemExit('primary ComfyUI queue is busy; nothing submitted')
    # Fail closed: a Studio that cannot be read is not proof of an idle Studio.
    try: jobs = http(STUDIO + '/api/jobs', timeout=30)
    except (OSError, ValueError) as error: raise SystemExit('Studio /api/jobs unreadable (%r); nothing submitted' % error)
    if not isinstance(jobs, list): raise SystemExit('Studio /api/jobs returned %s, not a list; nothing submitted' % type(jobs).__name__)
    busy = [j.get('id') for j in jobs if not isinstance(j, dict) or j.get('status') in IN_FLIGHT]
    if busy: raise SystemExit('Studio has in-flight jobs %s; nothing submitted' % busy)


def comfy_pid():
    import psutil
    for c in psutil.net_connections(kind='tcp'):
        if c.status == 'LISTEN' and c.laddr.port == 8188 and c.laddr.ip == '127.0.0.1': return c.pid


def commit_pct():
    import psutil
    try:
        import ctypes
        class MS(ctypes.Structure):
            _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong), ('ullTotalPhys', ctypes.c_ulonglong),
                        ('ullAvailPhys', ctypes.c_ulonglong), ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                        ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong), ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
        m = MS(); m.dwLength = ctypes.sizeof(MS); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return round(100 * (1 - m.ullAvailPageFile / m.ullTotalPageFile), 1), round(m.ullAvailPhys / 2 ** 30, 1)
    except Exception: return None, round(psutil.virtual_memory().available / 2 ** 30, 1)


def canonical_sha(obj): return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()


def prune_loras(graph):
    """Drop LoRA loaders at strength 0 and rewire their consumers, as the Studio does before submission."""
    graph = json.loads(json.dumps(graph))
    while True:
        dead = next((k for k, v in graph.items() if v['class_type'] in ('LoraLoaderModelOnly', 'LoraLoader')
                     and float(v['inputs'].get('strength_model', 1)) == 0 and float(v['inputs'].get('strength_clip', 0) or 0) == 0), None)
        if dead is None: return graph
        upstream = graph[dead]['inputs']
        for v in graph.values():
            for name, value in v['inputs'].items():
                if isinstance(value, list) and len(value) == 2 and value[0] == dead:
                    v['inputs'][name] = upstream['model'] if value[1] == 0 else upstream.get('clip', value)
        del graph[dead]


CLIENT_ID = 'overnight-lab'
GPU_INTERVAL = 1.5  # seconds between GPU memory samples; experiments timing short phases set it lower (0.25)


def log_time(entry):
    """A ComfyUI log entry's timestamp as a datetime ('T' or space separator both parse); unparseable sorts first."""
    try: return datetime.datetime.fromisoformat(str(entry.get('t', '')).replace(' ', 'T'))
    except ValueError: return datetime.datetime.min


class Events:
    """Minimal stdlib WebSocket reader for ComfyUI's /ws: collects (time, type, data) for text frames.

    ComfyUI sends `executing` (node start), `progress` (sampler step) and `execution_*` messages to the socket whose
    clientId submitted the prompt, so this only sees direct submissions made with CLIENT_ID (never the Studio's jobs).
    """
    def __init__(self):
        import base64, os, socket
        self.events, self.stop = [], threading.Event()
        self.sock = socket.create_connection(('127.0.0.1', 8188), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(('GET /ws?clientId=%s HTTP/1.1\r\nHost: 127.0.0.1:8188\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                           'Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n' % (CLIENT_ID, key)).encode())
        head = b''
        while b'\r\n\r\n' not in head: head += self.sock.recv(1)
        if b' 101 ' not in head.split(b'\r\n')[0]: raise OSError('websocket upgrade refused: %r' % head[:80])
        self.sock.settimeout(1.0)
        threading.Thread(target=self._read, daemon=True).start()
    def _recv(self, n):
        import socket
        buf = b''
        while len(buf) < n:
            try: chunk = self.sock.recv(n - len(buf))
            except socket.timeout:
                if self.stop.is_set(): raise EOFError
                continue
            if not chunk: raise EOFError
            buf += chunk
        return buf
    def _read(self):
        import os, struct
        try:
            while not self.stop.is_set():
                b0, b1 = self._recv(2); op, n = b0 & 15, b1 & 127
                if n == 126: n = struct.unpack('>H', self._recv(2))[0]
                elif n == 127: n = struct.unpack('>Q', self._recv(8))[0]
                payload = self._recv(n)
                if op == 1:
                    try: msg = json.loads(payload.decode('utf-8'))
                    except ValueError: continue
                    if msg.get('type') in ('executing', 'progress', 'execution_start', 'execution_cached', 'execution_success', 'execution_error', 'executed'):
                        self.events.append((time.time(), msg['type'], msg.get('data') or {}))
                elif op == 9:  # ping -> masked pong
                    mask = os.urandom(4); self.sock.sendall(bytes([0x8A, 0x80 | len(payload)]) + mask + bytes(c ^ mask[i % 4] for i, c in enumerate(payload)))
                elif op == 8: break
        except (EOFError, OSError): pass
    def close(self):
        self.stop.set()
        try: self.sock.close()
        except OSError: pass

    def summary(self, prompt_id, graph=None):
        """Per-node wall seconds (from `executing` boundaries) and per-sampler step timing for one prompt."""
        ev = [e for e in self.events if (e[2].get('prompt_id') == prompt_id)]
        nodes, current, t_start = [], None, None
        for t, kind, data in ev:
            if kind == 'execution_start': t_start = t
            if kind == 'executing':
                if current: nodes.append({'node': current[0], 'class_type': (graph or {}).get(current[0], {}).get('class_type'), 'seconds': round(t - current[1], 2)})
                current = (data.get('node'), t) if data.get('node') is not None else None
        steps = {}
        for t, kind, data in ev:
            if kind == 'progress': steps.setdefault(data.get('node'), []).append((t, data.get('value'), data.get('max')))
        samplers = []
        for node, seq in steps.items():
            first = dict()
            for t, v, m in seq: first.setdefault(v, t)
            vs = sorted(first); total = seq[-1][2]
            per = [round(first[b] - first[a], 2) for a, b in zip(vs, vs[1:])]
            steady = round((first[vs[-1]] - first[vs[1]]) / (vs[-1] - vs[1]), 3) if len(vs) >= 3 else None
            samplers.append({'node': node, 'class_type': (graph or {}).get(node, {}).get('class_type'), 'steps': total, 'seen': len(vs),
                             'first_step_s': per[0] if per else None, 's_per_step_steady': steady, 'step_seconds': per})
        cached = [e[2].get('nodes') for e in ev if e[1] == 'execution_cached']
        return {'node_seconds': nodes, 'samplers': samplers, 'cached_nodes': cached[0] if cached else [],
                'ws_execution_seconds': round(ev[-1][0] - t_start, 2) if t_start and ev else None}


class Sampler:
    """GPU memory, host commit and ComfyUI log entries sampled on background threads during one job."""
    def __init__(self, pid):
        self.pid, self.gpu, self.logs, self.commit, self.stop = pid, [], {}, [], threading.Event()
        self.since = datetime.datetime.now()  # log entries older than the submission belong to earlier jobs
    def _gpu(self):
        while not self.stop.is_set():
            r = gpu_memory.spill(self.pid)
            if r.get('dedicated_bytes') is not None: self.gpu.append((time.time(), r['dedicated_bytes'], r['shared_bytes']))
            c = commit_pct(); self.commit.append(c[0]); time.sleep(GPU_INTERVAL)
    def _log(self):
        while not self.stop.is_set():
            self.poll_logs(); time.sleep(2)
    def poll_logs(self):
        try:
            for e in http(COMFY + '/internal/logs/raw', timeout=20).get('entries', []): self.logs[(e['t'], e['m'])] = e
        except Exception: pass
    def start(self):
        for target in (self._gpu, self._log): threading.Thread(target=target, daemon=True).start()
        return self
    def finish(self):
        self.stop.set(); self.poll_logs(); time.sleep(0.2)
        entries = sorted((e for e in self.logs.values() if log_time(e) >= self.since), key=log_time)
        out = summarise(entries, self.gpu, self.commit)
        t0 = self.gpu[0][0] if self.gpu else 0
        out['_timeline'] = [[round(g[0] - t0, 1), round(g[1] / 2 ** 20), round(g[2] / 2 ** 20)] for g in self.gpu]
        out['_timeline_t0'] = datetime.datetime.fromtimestamp(t0).isoformat() if t0 else None
        return out


def summarise(entries, gpu, commit):
    step_re = re.compile(r'(\d+)/(\d+) \[(\d+):(\d+)(?::(\d+))?<')
    steps = []  # (timestamp, step, total, elapsed_s)
    for e in entries:
        for part in e['m'].replace('\r', '\n').split('\n'):
            m = step_re.search(part)
            if m:
                el = int(m.group(3)) * 60 + int(m.group(4)) if m.group(5) is None else int(m.group(3)) * 3600 + int(m.group(4)) * 60 + int(m.group(5))
                steps.append((e['t'], int(m.group(1)), int(m.group(2)), el))
    # split into sampler runs: a run restarts when the step counter drops or the total changes
    runs, cur = [], []
    for s in steps:
        if cur and (s[1] < cur[-1][1] or s[2] != cur[-1][2]): runs.append(cur); cur = []
        cur.append(s)
    if cur: runs.append(cur)
    sampler_runs = []
    for run in runs:
        total = run[-1][2]; last = max(run, key=lambda s: s[1])
        by_step = {}
        for s in run: by_step.setdefault(s[1], datetime.datetime.fromisoformat(s[0]))
        ks = sorted(by_step)
        steady = None
        if len(ks) >= 3:  # from step 1 to the last step: excludes the first step's warm-up
            a, b = ks[1] if ks[0] == 0 else ks[0], ks[-1]
            if b > a: steady = round((by_step[b] - by_step[a]).total_seconds() / (b - a), 2)
        sampler_runs.append({'total_steps': total, 'last_step': last[1], 'elapsed_s_tqdm': last[3],
                             's_per_step_tqdm': round(last[3] / last[1], 2) if last[1] else None, 's_per_step_steady': steady})
    keep = ('loaded completely', 'loaded partially', 'Unloaded partially', 'Requested to load', 'Prompt executed in', 'Error', 'error',
            'Traceback', 'out of memory', 'OOM', 'lowvram', 'IndexError')
    lines = [e['t'][11:19] + ' ' + re.sub(r'\x1b\[[0-9;]*m', '', e['m']).strip() for e in entries if any(k in e['m'] for k in keep)]
    executed = [float(x) for e in entries for x in re.findall(r'Prompt executed in ([\d.]+) seconds', e['m'])]
    return {'sampler_runs': sampler_runs,
            'peak_dedicated_mb': round(max((g[1] for g in gpu), default=0) / 2 ** 20),
            'peak_shared_mb': round(max((g[2] for g in gpu), default=0) / 2 ** 20),
            'spilled': max((g[2] for g in gpu), default=0) >= gpu_memory.SPILL_BYTES,
            'gpu_samples': len(gpu), 'peak_commit_pct': max((c for c in commit if c is not None), default=None),
            'comfy_executed_seconds': executed[-1] if executed else None, 'log_lines': lines[-14:]}


class Results:
    """`results.json` in an experiment folder: a list of records, rewritten atomically after every change."""
    def __init__(self, folder):
        self.folder = Path(folder); self.folder.mkdir(parents=True, exist_ok=True); self.path = self.folder / 'results.json'
        self.records = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else []
    def save(self):
        tmp = self.path.with_suffix('.tmp'); tmp.write_text(json.dumps(self.records, indent=1) + '\n', encoding='utf-8', newline='\n'); tmp.replace(self.path)
    def add(self, record): self.records.append(record); self.save(); return record
    def find(self, label): return next((r for r in self.records if r.get('label') == label), None)


def save_timeline(results, label, summary):
    """GPU memory series `[seconds, dedicated MB, shared MB]` beside results.json, so a spill can be placed in a phase."""
    tdir = results.folder / 'timelines'; tdir.mkdir(exist_ok=True)
    series = summary.pop('_timeline', []); t0 = summary.pop('_timeline_t0', None)
    (tdir / (label + '.json')).write_text(json.dumps({'t0': t0, 'series': series}) + '\n', encoding='utf-8', newline='\n')
    summary['timeline_file'] = 'timelines/' + label + '.json'


def outputs_of(history):
    files = []
    for node_out in (history.get('outputs') or {}).values():
        for img in node_out.get('images', []) or []:
            if img.get('type') != 'output': continue
            p = OUTPUT / img.get('subfolder', '') / img['filename']
            files.append({'file': str(p), 'sha256': file_sha(p) if p.exists() else None})
    return files


def run_graph(graph, label, results, timeout=3600, extra=None, skip_existing=True):
    """Submit one graph straight to ComfyUI, with evidence. Returns the record. Never retries."""
    prior = results.find(label)
    if prior and skip_existing:
        print('skip', label, prior.get('status'), flush=True); return prior
    guard(); pid = comfy_pid(); c0 = commit_pct()
    gdir = results.folder / 'graphs'; gdir.mkdir(exist_ok=True)
    (gdir / (label + '.json')).write_text(json.dumps(graph, indent=1) + '\n', encoding='utf-8', newline='\n')
    record = {'label': label, 'status': 'submitting', 'graph_sha256': canonical_sha(graph), 'graph_file': 'graphs/' + label + '.json',
              'submitted_at': now(), 'comfy_pid': pid, 'commit_pct_before': c0[0], 'free_ram_gb_before': c0[1]}
    record.update(extra or {})
    try: events = Events()
    except OSError as error: events = None; record['ws_error'] = repr(error)
    sampler = Sampler(pid).start(); started = time.time()
    try: prompt_id = http(COMFY + '/prompt', {'prompt': graph, 'client_id': CLIENT_ID}, timeout=120)['prompt_id']
    except urllib.error.HTTPError as error:
        sampler.stop.set(); events and events.close(); record.update(status='rejected', error=error.read().decode('utf-8', 'replace')[:3000]); results.add(record)
        print('REJECTED', label, record['error'][:800], flush=True); return record
    except (OSError, ValueError) as error:
        sampler.stop.set(); events and events.close(); record.update(status='unresolved', error='POST /prompt network error: %r' % error); results.add(record)
        raise SystemExit('unresolved submission for %s; inspect the ComfyUI queue/history, do not resubmit' % label)
    record.update(prompt_id=prompt_id, status='submitted'); results.add(record)
    print(label, 'prompt', prompt_id, flush=True)
    history = None
    while time.time() - started < timeout:
        time.sleep(2)
        try: history = http(COMFY + '/history/' + prompt_id, timeout=30).get(prompt_id)
        except (OSError, ValueError): history = None
        if history and history.get('status', {}).get('completed') is not None and (history['status'].get('status_str') in ('success', 'error') or history.get('outputs')): break
        history = None
    summary = sampler.finish(); record['wall_seconds'] = round(time.time() - started, 1); save_timeline(results, label, summary); record.update(summary)
    if history is None: record['status'] = 'uncertain'; record['note'] = 'no terminal history within %d s; left alone' % timeout
    else:
        st = history.get('status', {}); record['status'] = st.get('status_str')
        msgs = st.get('messages', [])
        ts = dict((m[0], m[1].get('timestamp')) for m in msgs if isinstance(m, list) and len(m) == 2 and isinstance(m[1], dict))
        if ts.get('execution_start') and (ts.get('execution_success') or ts.get('execution_error')):
            record['history_execution_seconds'] = round(((ts.get('execution_success') or ts.get('execution_error')) - ts['execution_start']) / 1000, 2)
        errs = [m[1] for m in msgs if isinstance(m, list) and m[0] == 'execution_error']
        if errs: record['error'] = {k: errs[0].get(k) for k in ('node_type', 'exception_type', 'exception_message')}
        record['outputs'] = outputs_of(history)
    if events:
        time.sleep(0.5); events.close(); record['ws'] = events.summary(prompt_id, graph)
    record['finished_at'] = now()
    for i, r in enumerate(results.records):
        if r.get('label') == label and r.get('prompt_id') == record.get('prompt_id'): results.records[i] = record
    results.save()
    brief = {k: record.get(k) for k in ('label', 'status', 'wall_seconds', 'history_execution_seconds', 'peak_dedicated_mb', 'peak_shared_mb', 'spilled')}
    ws = record.get('ws') or {}
    brief['samplers'] = [dict((k, s[k]) for k in ('class_type', 'steps', 'first_step_s', 's_per_step_steady')) for s in ws.get('samplers', [])]
    brief['nodes'] = ['%s:%s' % (n['class_type'], n['seconds']) for n in ws.get('node_seconds', []) if n['seconds'] >= 0.5]
    print(json.dumps(brief), flush=True)
    return record


def finalize(results, label, note, timeout=3600):
    """Complete a `submitted` record whose poller was stopped: wait for its saved prompt ID in /history, never resubmit."""
    record = results.find(label)
    if not record or not record.get('prompt_id'): raise SystemExit('no submitted prompt recorded for ' + label)
    started = time.time(); history = None
    while time.time() - started < timeout:
        try: history = http(COMFY + '/history/' + record['prompt_id'], timeout=30).get(record['prompt_id'])
        except (OSError, ValueError): history = None
        if history and history.get('status', {}).get('completed') is not None: break
        history = None; time.sleep(5)
    if history is None: record['status'] = 'uncertain'; record['note'] = note + '; still not terminal, left alone'
    else:
        st = history.get('status', {}); record['status'] = st.get('status_str'); record['note'] = note
        ts = dict((m[0], m[1].get('timestamp')) for m in st.get('messages', []) if isinstance(m, list) and len(m) == 2 and isinstance(m[1], dict))
        if ts.get('execution_start') and (ts.get('execution_success') or ts.get('execution_error')):
            record['history_execution_seconds'] = round(((ts.get('execution_success') or ts.get('execution_error')) - ts['execution_start']) / 1000, 2)
        record['outputs'] = outputs_of(history)
    record['finished_at'] = now(); results.save(); print(json.dumps({k: record.get(k) for k in ('label', 'status', 'history_execution_seconds', 'note')}))
    return record


def runtime_identity():
    """Which runtime a Studio job ran on: the Studio's active backend (main checkout .runtime/backend-state.json), the preset's
    declared backend is in the recipe, and the answering ComfyUI's argv and version from /system_stats."""
    out = {}
    try: out['studio_active_backend'] = json.loads((MAIN / '.runtime' / 'backend-state.json').read_text(encoding='utf-8')).get('active')
    except (OSError, ValueError) as error: out['studio_active_backend'] = 'unreadable: %r' % error
    try:
        stats = http(COMFY + '/system_stats', timeout=20).get('system', {})
        out['comfy_version'] = stats.get('comfyui_version'); out['comfy_argv_tail'] = (stats.get('argv') or [])[-8:]
    except (OSError, ValueError) as error: out['comfy_version'] = 'unreadable: %r' % error
    return out


def run_studio(intent, label, results, timeout=3600, extra=None, skip_existing=True):
    """One Studio job (POST /api/jobs), sampled like run_graph. Records the job ID before polling; never retries."""
    prior = results.find(label)
    if prior and skip_existing:
        print('skip', label, prior.get('status'), flush=True); return prior
    guard(); pid = comfy_pid(); c0 = commit_pct()
    record = {'label': label, 'status': 'submitting', 'intent': intent, 'submitted_at': now(), 'comfy_pid': pid,
              'commit_pct_before': c0[0], 'free_ram_gb_before': c0[1], 'route': 'studio'}
    record.update(runtime_identity())
    record.update(extra or {})
    sampler = Sampler(pid).start(); started = time.time()
    try: job = http(STUDIO + '/api/jobs', intent, timeout=120, origin=STUDIO)
    except urllib.error.HTTPError as error:
        sampler.stop.set(); record.update(status='rejected', error=error.read().decode('utf-8', 'replace')[:3000]); results.add(record)
        print('REJECTED', label, record['error'][:800], flush=True); return record
    except (OSError, ValueError) as error:
        sampler.stop.set(); record.update(status='unresolved', error='POST /api/jobs network error: %r' % error); results.add(record)
        raise SystemExit('unresolved Studio submission for %s; inspect /api/jobs, do not resubmit' % label)
    record.update(job_id=job.get('id'), status='submitted'); results.add(record)
    print(label, 'job', job.get('id'), flush=True)
    state = None
    while time.time() - started < timeout:
        time.sleep(3)
        try: state = http(STUDIO + '/api/jobs/' + job['id'], timeout=30)
        except (OSError, ValueError): continue
        if state.get('status') in TERMINAL: break
        if state.get('prompt_ids') and not record.get('prompt_ids'): record['prompt_ids'] = state['prompt_ids']
    summary = sampler.finish(); record['wall_seconds'] = round(time.time() - started, 1); save_timeline(results, label, summary); record.update(summary)
    if not state or state.get('status') not in TERMINAL: record['status'] = 'uncertain'; record['note'] = 'job not terminal within %d s; left alone' % timeout
    else:
        record['status'] = state.get('status')
        for k in ('prompt_ids', 'outputs', 'elapsed_seconds', 'failure', 'message', 'controls', 'submissions'): record[k] = state.get(k)
        try:
            recipe = http(STUDIO + '/api/jobs/' + job['id'] + '/recipe', timeout=30)
            gdir = results.folder / 'graphs'; gdir.mkdir(exist_ok=True)
            (gdir / (label + '.recipe.json')).write_text(json.dumps(recipe, indent=1) + '\n', encoding='utf-8', newline='\n')
            record['recipe_file'] = 'graphs/' + label + '.recipe.json'
        except Exception as error: record['recipe_error'] = repr(error)
        files = []
        for o in state.get('outputs') or []:
            name = o if isinstance(o, str) else (o.get('filename') or o.get('file') or o.get('path'))
            sub = '' if isinstance(o, str) else o.get('subfolder', '')
            if not name: continue
            p = Path(name) if Path(name).is_absolute() else OUTPUT / sub / name
            files.append({'file': str(p), 'sha256': file_sha(p) if p.exists() else None})
        record['output_files'] = files
    record['finished_at'] = now()
    for i, r in enumerate(results.records):
        if r.get('label') == label and r.get('job_id') == record.get('job_id'): results.records[i] = record
    results.save()
    brief = {k: record.get(k) for k in ('label', 'status', 'wall_seconds', 'elapsed_seconds', 'peak_dedicated_mb', 'peak_shared_mb', 'spilled')}
    brief['sampler'] = record.get('sampler_runs'); print(json.dumps(brief), flush=True)
    return record


def seal(items, folder, rng_seed=None):
    """Blind copies for judging. `items` = [{'group': 'seed1', 'config': 'fp8', 'file': path}, ...].

    Within each group the configurations get shuffled letters; copies go to `blind/<group>-<letter>.png` and the mapping
    to `key.sealed.json`. Judge from `blind/` only; read the key after writing every judgement.
    """
    import shutil
    # Blind copies can show famous characters, so they live outside Git: <repo>/.runtime/lab-scratch/blind/<experiment>/.
    folder = Path(folder); blind = REPO / '.runtime' / 'lab-scratch' / 'blind' / folder.name; blind.mkdir(parents=True, exist_ok=True)
    rng = random.Random(rng_seed if rng_seed is not None else time.time_ns())
    key, groups = {}, {}
    for it in items: groups.setdefault(it['group'], []).append(it)
    for group, members in groups.items():
        letters = [chr(65 + i) for i in range(len(members))]; rng.shuffle(letters)
        for letter, it in zip(letters, members):
            name = '%s-%s%s' % (group, letter, Path(it['file']).suffix)
            shutil.copyfile(it['file'], blind / name); key[name] = {'config': it['config'], 'file': it['file']}
    (folder / 'key.sealed.json').write_text(json.dumps(key, indent=1) + '\n', encoding='utf-8', newline='\n')
    return sorted(key)


def judge(folder, image, scores, verdict, worst_defect, fix=None, notes='', prompt_id=None, job_id=None, blind=True):
    """Append one judgement (protocol shape) to `<folder>/judgements.jsonl`."""
    p = Path(image)
    rec = {'image': str(p), 'sha256': file_sha(p), 'prompt_id': prompt_id, 'job_id': job_id, 'judge': 'lab', 'judged_at': now(),
           'blind': blind, 'scores': scores, 'verdict': verdict, 'worst_defect': worst_defect, 'fix': fix, 'notes': notes}
    with open(Path(folder) / 'judgements.jsonl', 'a', encoding='utf-8', newline='\n') as f: f.write(json.dumps(rec) + '\n')
    return rec
