"""Speed of Qwen-Image 2.1 on the isolated backend under one launch configuration (23 September 2026).

`python bench.py <label> [extra ComfyUI flags...]` starts the shipped launcher's server with the extra flags, runs the
shipped text-to-image graph twice at 832x1248 (a cold run that loads the models, then a warm run with another seed),
reads the sampler's s/it from the server log, samples host commit headroom and GPU stats, stops the server it started
and appends one record to bench.json. It refuses to start while less than 30 GB of commit headroom is free.
"""
import json, re, subprocess, sys, threading, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent; REPO = HERE.parents[2]; URL = 'http://127.0.0.1:8196'
ROOT = Path('C:/AI/experiments/qwen-image-21/ComfyUI'); PYTHON = 'C:/AI/ComfyUI_windows_portable/python_embeded/python.exe'
STEPS = 8


def free_virtual_gb():
    out = subprocess.run(['powershell', '-NoProfile', '-Command', '(Get-CimInstance Win32_OperatingSystem).FreeVirtualMemory'],
                         capture_output=True, text=True, encoding='utf-8').stdout.strip()
    return int(out) / 1024 / 1024


def call(route, body=None):
    request = urllib.request.Request(URL + route, json.dumps(body).encode() if body is not None else None, {'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(request, timeout=60))


def run(graph):
    started = time.time(); prompt = call('/prompt', {'prompt': graph, 'client_id': 'qwen21-bench'})['prompt_id']
    while True:
        time.sleep(2); history = call('/history/' + prompt).get(prompt)
        if history: return prompt, round(time.time() - started, 1), history['status'].get('status_str')
        if time.time() - started > 2400: raise SystemExit('no terminal history for ' + prompt)


def main(label, extra):
    headroom = free_virtual_gb()
    if headroom < 32: raise SystemExit(f'Only {headroom:.1f} GiB commit headroom (32 GiB is the documented gate); not launching')
    log = HERE.parent.parent.parent / '.runtime' / f'bench-{label}.log'; log.parent.mkdir(exist_ok=True)
    # The shipped launcher's argv plus the flags under test (argparse takes the last value of a repeated flag).
    code = ("import runpy,sys;sys.argv=['qwen21-launch.py','--comfy-root',%r];"
            "import builtins;_run=runpy.run_path\n"
            "def run_path(path,**k):\n sys.argv=sys.argv+%r\n return _run(path,**k)\n"
            "runpy.run_path=run_path;_run(%r,run_name='__main__')") % (str(ROOT), list(extra), str(REPO / 'scripts/qwen21-launch.py'))
    server = subprocess.Popen([PYTHON, '-s', '-c', code], cwd=str(ROOT), stdout=open(log.with_suffix('.out'), 'w'), stderr=open(log, 'w'))
    low = [headroom]; stop = threading.Event()
    def sample():
        while not stop.is_set(): low.append(free_virtual_gb()); time.sleep(4)
    threading.Thread(target=sample, daemon=True).start()
    try:
        for _ in range(180):
            try: call('/system_stats'); break
            except OSError: time.sleep(2)
        graph = json.loads((REPO / 'workflows/api/qwen21-t2i-api.json').read_text(encoding='utf-8'))
        graph['6']['inputs']['steps'] = STEPS; graph['8']['inputs']['filename_prefix'] = 'research/bench-' + label
        cold = run(graph); graph['6']['inputs']['seed'] += 1; warm = run(graph)
        rates = [float(x) for x in re.findall(r'(\d+\.\d+)s/it', log.read_text(encoding='utf-8', errors='replace'))]
        its = [float(x) for x in re.findall(r'(\d+\.\d+)it/s', log.read_text(encoding='utf-8', errors='replace'))]
        record = {'label': label, 'flags': list(extra), 'steps': STEPS, 'size': [832, 1248], 'cold': cold, 'warm': warm,
                  'last_s_per_it': rates[-1] if rates else (round(1 / its[-1], 3) if its else None),
                  'min_commit_headroom_gb': round(min(low), 1), 'start_commit_headroom_gb': round(headroom, 1)}
    finally:
        stop.set(); server.terminate(); server.wait(30)
    records = json.loads((HERE / 'bench.json').read_text(encoding='utf-8')) if (HERE / 'bench.json').exists() else []
    records.append(record); (HERE / 'bench.json').write_text(json.dumps(records, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=1))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
