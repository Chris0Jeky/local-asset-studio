"""Krea 2 fp8 before/after the measured --reserve-vram (23 September 2026): one run of the shipped krea-portrait graph.

`python krea_bench.py <label>` submits the unchanged graph (768x1152, 8 steps, seed 2026091103, retro-anime LoRA) straight
to the primary ComfyUI on 8188 once, samples the ComfyUI process's dedicated/shared GPU memory every 2 s through
app/gpu_memory.py, reads the sampler's step times from the newest C:/AI/logs/*-error.log, and appends one record to
krea_bench.json. One deliberate run per call; it refuses to submit while the queue is busy and never retries.
"""
import datetime, json, re, sys, threading, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent; REPO = HERE.parents[2]; URL = 'http://127.0.0.1:8188'
sys.path.insert(0, str(REPO / 'app'))
import gpu_memory


def call(route, body=None):
    request = urllib.request.Request(URL + route, json.dumps(body).encode() if body is not None else None, {'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(request, timeout=60))


def comfy_pid():
    import psutil
    for connection in psutil.net_connections(kind='tcp'):
        if connection.status == 'LISTEN' and connection.laddr.port == 8188 and connection.laddr.ip == '127.0.0.1': return connection.pid


def main(label):
    queue = call('/queue')
    if queue.get('queue_running') or queue.get('queue_pending'): raise SystemExit('Primary queue is busy; nothing submitted')
    pid = comfy_pid(); import psutil; cmdline = psutil.Process(pid).cmdline()
    # The launcher logs to C:/AI/logs; a Studio switch or recovery launch logs to the repo's .runtime/backends.
    logs = list(Path('C:/AI/logs').glob('*-error.log')) + list((REPO.parents[2] / '.runtime/backends').glob('*-error.log')) + list((REPO / '.runtime/backends').glob('*-error.log'))
    log = max(logs, key=lambda p: p.stat().st_mtime); offset = log.stat().st_size
    graph = json.loads((REPO / 'workflows/api/krea-portrait-api.json').read_text(encoding='utf-8'))
    graph['9']['inputs']['filename_prefix'] = 'research/vram-spill-krea-' + label
    samples = []; stop = threading.Event()
    def sample():
        while not stop.is_set():
            reading = gpu_memory.spill(pid)
            if reading.get('dedicated_bytes') is not None: samples.append((reading['dedicated_bytes'], reading['shared_bytes']))
            time.sleep(2)
    threading.Thread(target=sample, daemon=True).start()
    started = time.time(); prompt = call('/prompt', {'prompt': graph, 'client_id': 'vram-spill-bench'})['prompt_id']
    print(label, 'prompt', prompt, flush=True)
    while True:
        time.sleep(2); history = call('/history/' + prompt).get(prompt)
        if history: break
        if time.time() - started > 3600: stop.set(); raise SystemExit('No terminal history after 3600 s; prompt ' + prompt + ' left alone')
    stop.set(); wall = round(time.time() - started, 1)
    text = log.read_bytes()[offset:].decode('utf-8', 'replace').replace('\r', '\n')
    steps = re.findall(r'(\d+)/8 \[(\d+):(\d+)<', text)
    executed = re.findall(r'Prompt executed in ([\d.]+) seconds', text)
    loads = [line.strip() for line in text.splitlines() if 'loaded completely' in line or 'loaded partially' in line or 'Unloaded partially' in line]
    sampling = int(steps[-1][1]) * 60 + int(steps[-1][2]) if steps else None
    record = {'label': label, 'prompt_id': prompt, 'status': history['status'].get('status_str'), 'recorded_at': str(datetime.datetime.now()),
              'wall_seconds': wall, 'comfy_executed_seconds': float(executed[-1]) if executed else None,
              'sampling_seconds_8_steps': sampling, 's_per_step': round(sampling / 8, 2) if sampling else None,
              'peak_dedicated_mb': round(max((s[0] for s in samples), default=0) / 2 ** 20), 'peak_shared_mb': round(max((s[1] for s in samples), default=0) / 2 ** 20),
              'samples': len(samples), 'comfy_argv_tail': cmdline[cmdline.index('--listen'):] if '--listen' in cmdline else cmdline[-8:],
              'load_lines': loads[-6:], 'log': str(log)}
    out = HERE / 'krea_bench.json'; records = json.loads(out.read_text(encoding='utf-8')) if out.exists() else []
    records.append(record); out.write_text(json.dumps(records, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=1))


if __name__ == '__main__':
    main(sys.argv[1])
