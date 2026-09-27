# As-run script (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
"""#923 probe (27 Sep 2026): does ComfyUI 0.35.0 report success with no outputs for a graph with a save node, and what
does the Studio record? P1/P2: two identical cheap SFW `wai` Studio jobs (P2 is answered from ComfyUI's cache).
D1/D2: an identical LoadImage -> SaveImage graph posted twice straight to ComfyUI (no model, no GPU)."""
import json, sys, time
sys.path.insert(0, 'C:/Users/jekyt/AppData/Local/Temp/nightshift-0927'); import ns
drive = ns.drive; OUT = 'C:/Users/jekyt/AppData/Local/Temp/zero-output-0927/'
POS = 'no humans, scenery, small stone bridge over a quiet stream, spring meadow, soft daylight, masterpiece, best quality'
def hist(pid):
    h = drive.comfy('/history/' + pid)[1][pid]
    return {'status': h['status'], 'outputs': h['outputs'], 'client_id': h['prompt'][3].get('client_id')}
rec = {'log_before': drive.log_counts()}
for key in ('P1', 'P2'):
    r = ns.studio_job('zero-' + key, 'wai', {'positive': POS, 'seed': 2026092923, 'steps': 12}, label='zero-output-probe-' + key)
    j = drive.job(r['job_id']); rec[key] = {'job_id': r['job_id'], 'status': j['status'], 'message': j['message'], 'prompt_ids': j['prompt_ids'],
        'outputs': j['outputs'], 'submissions': [{k: v for k, v in s.items() if k != 'graph'} for s in json.load(open(ns.RUNS + r['job_id'] + '/state.json', encoding='utf-8'))['submissions']],
        'elapsed_seconds': r['elapsed_seconds'], 'history': hist(j['prompt_ids'][0])}
up = json.load(open('C:/Users/jekyt/AppData/Local/Temp/nightshift-0927/anchor-upload.json'))['file']
g = {'1': {'class_type': 'LoadImage', 'inputs': {'image': up}}, '2': {'class_type': 'SaveImage', 'inputs': {'images': ['1', 0], 'filename_prefix': 'Research/zero-output-20260927/probe'}}}
for key in ('D1', 'D2'):
    code, reply = drive.comfy('/prompt', {'prompt': g, 'client_id': 'zero-output-probe'}); pid = reply['prompt_id']
    while pid not in (drive.comfy('/history/' + pid)[1] or {}): time.sleep(0.5)
    rec[key] = {'prompt_id': pid, 'history': hist(pid)}
rec['log_after'] = drive.log_counts(); rec['queue_after'] = drive.queue(); rec['graph_direct'] = g
json.dump(rec, open(OUT + 'probe.json', 'w'), indent=1)
for k in ('P1', 'P2'):
    v = rec[k]; print(k, v['job_id'], v['status'], v['prompt_ids'], round(v['elapsed_seconds'], 1), [(o['filename'], o.get('asset_id')) for o in v['outputs']],
                      v['history']['status']['status_str'], [m[0] for m in v['history']['status']['messages']], [m[1].get('nodes') for m in v['history']['status']['messages'] if m[0] == 'execution_cached'], json.dumps(v['history']['outputs'])[:200])
for k in ('D1', 'D2'):
    v = rec[k]; print(k, v['prompt_id'], v['history']['status']['status_str'], [m[1].get('nodes') for m in v['history']['status']['messages'] if m[0] == 'execution_cached'], json.dumps(v['history']['outputs']))
print(rec['log_before'], rec['log_after'], rec['queue_after'])
