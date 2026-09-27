# As-run script (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
"""Tiny direct-ComfyUI helper for the background lab: one POST per graph, wait for history, log prompt id, exec_s, outputs."""
import json, sys, time
sys.path.insert(0, 'C:/Users/jekyt/AppData/Local/Temp/cancel-proof-0927'); import drive
OUT = 'C:/AI/ComfyUI_windows_portable/ComfyUI/output/'; INP = 'C:/AI/ComfyUI_windows_portable/ComfyUI/input/'
LOG = 'C:/Users/jekyt/AppData/Local/Temp/bglab/runs.jsonl'
def run(key, graph, note=''):
    r, p = drive.queue(); assert not r and not p, 'queue busy'
    c0 = drive.commit(); t0 = time.time()
    code, reply = drive.comfy('/prompt', {'prompt': graph, 'client_id': 'bglab-0927'}); assert code == 200, reply; pid = reply['prompt_id']
    while True:
        h = (drive.comfy('/history/' + pid)[1] or {}).get(pid)
        if h and h['status'].get('status_str') in ('success', 'error'): break
        time.sleep(0.5)
    ts = {m[0]: m[1].get('timestamp') for m in h['status']['messages']}
    outs = [OUT + (o['subfolder'] + '/' if o['subfolder'] else '') + o['filename'] for n in h['outputs'].values() for o in n.get('images', []) if o.get('type') == 'output']
    rec = {'key': key, 'prompt_id': pid, 'status': h['status']['status_str'], 'exec_s': ((ts.get('execution_success') or ts.get('execution_error') or ts['execution_start']) - ts['execution_start']) / 1000,
           'started': time.strftime('%H:%M:%S', time.localtime(ts['execution_start'] / 1000)), 'outputs': outs, 'commit_before': c0['pct'], 'commit_after': drive.commit()['pct'], 'note': note, 'graph': graph}
    open(LOG, 'a').write(json.dumps(rec) + '\n'); print(key, pid[:8], rec['status'], rec['exec_s'], rec['started'], flush=True)
    if rec['status'] != 'success': raise SystemExit('error: ' + json.dumps(h['status'])[:800])
    return rec
