# As-run script (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
"""#1028 lanes (27 Sep 2026): the smallest matrix for F1 (GGUF Q4) and the smaller text encoder, on qwen21 (8196), direct.
Conditions (all 25 steps, euler/simple, CFG 1, 1024^2, same prompts as the ladder):
  B0  INT8 DiT + INT8 TE (reference, re-run in this session)
  GU  unsloth Q4_K_M GGUF DiT + INT8 TE
  GR  realrebelai Q4 GGUF DiT + INT8 TE
  W   INT8 DiT + w4a8 TE (Comfy-Org, 6.3 GB)
  GW  unsloth Q4_K_M GGUF + w4a8 TE (both might stay resident in 16 GB)
2 prompts x 2 seeds each; seed-audition order within a condition (text unchanged). One POST per cell; commit stop at 92 %."""
import copy, json, sys, threading, time
sys.path.insert(0, 'C:/Users/jekyt/AppData/Local/Temp/cancel-proof-0927'); import drive
C = 'http://127.0.0.1:8196'; OUT = 'C:/Users/jekyt/AppData/Local/Temp/qi21-lanes/'
BASE = json.load(open('C:/Users/jekyt/Desktop/Printer Config/Others/Git/local-asset-studio/experiments/curated/qi21-lab2-20260927/pruna/graph-char-p2.json'))
PROMPTS = {'char': 'Anime key visual of an adult silver-haired sorceress in a midnight-blue travelling coat, holding a glowing brass lantern on a rainy stone bridge at blue hour. Clean linework, layered cel shading, teal and warm amber light.',
           'prop': 'Game item illustration of an ornate brass pocket compass with a teal enamel face and a small star-shaped needle, three-quarter view, centred on a plain warm grey background, clean cel shading, crisp silhouette, no text.'}
CONDS = {'B0': (None, 'qwen3vl_8b_int8_convrot.safetensors'), 'GU': ('qwen-image-2.1-Q4_K_M.gguf', 'qwen3vl_8b_int8_convrot.safetensors'),
         'GR': ('Qwen-Image-2.1-Q4-realrebelai.gguf', 'qwen3vl_8b_int8_convrot.safetensors'), 'W': (None, 'qwen3vl_8b_w4a8.safetensors'),
         'GW': ('Qwen-Image-2.1-Q4-realrebelai.gguf', 'qwen3vl_8b_w4a8.safetensors')}   # GW moved to the realrebelai Q4: the unsloth file is an unknown architecture for ComfyUI-GGUF 6ea2651e
SEEDS = [2026092741, 2026092742]
peak = {'pct': 0}; stop = threading.Event()
def sampler():
    while not stop.is_set(): peak['pct'] = max(peak['pct'], drive.commit()['pct']); time.sleep(0.5)
def graph(prompt, cond, seed, key):
    g = copy.deepcopy(BASE); gguf, te = CONDS[cond]
    del g['20']; g['6']['inputs'].update(model=['1', 0], seed=seed, steps=25)
    g['4']['inputs']['prompt'] = PROMPTS[prompt]; g['2']['inputs']['clip_name'] = te
    if gguf: g['1'] = {'class_type': 'UnetLoaderGGUF', 'inputs': {'unet_name': gguf}}
    g['8']['inputs']['filename_prefix'] = 'Research/qi21-lanes-20260927/' + key
    return g
threading.Thread(target=sampler, daemon=True).start()
import os
done_keys = {json.loads(l)['key'] for l in open(OUT + 'runs.jsonl') if json.loads(l).get('status') == 'success'} if os.path.exists(OUT + 'runs.jsonl') else set()
order = [a for a in sys.argv[1:]] or list(CONDS)
for cond in order:
    for prompt in PROMPTS:
        for seed in SEEDS:
            key = '%s-%s-%d' % (prompt, cond, seed % 100)
            if key in done_keys: continue
            q = drive.req(C, '/queue')[1]; assert not q['queue_running'] and not q['queue_pending']
            if peak['pct'] > 92: print('STOP commit', peak['pct']); stop.set(); sys.exit(1)
            peak['pct'] = drive.commit()['pct']; c0 = peak['pct']; t0 = time.time(); g = graph(prompt, cond, seed, key)
            code, reply = drive.req(C, '/prompt', {'prompt': g, 'client_id': 'qi21-lanes-0927'})
            if code != 200: print(key, 'REFUSED', str(reply)[:600]); open(OUT + 'runs.jsonl', 'a').write(json.dumps({'key': key, 'cond': cond, 'refused': str(reply)[:2000]}) + '\n'); break
            pid = reply['prompt_id']
            while True:
                h = (drive.req(C, '/history/' + pid)[1] or {}).get(pid)
                if h and h['status'].get('status_str') in ('success', 'error'): break
                time.sleep(0.5)
            ts = {m[0]: m[1].get('timestamp') for m in h['status']['messages']}
            cached = [m[1].get('nodes') for m in h['status']['messages'] if m[0] == 'execution_cached']
            err = [m[1] for m in h['status']['messages'] if m[0] == 'execution_error']
            outs = [o for n in h['outputs'].values() for o in n.get('images', [])]
            rec = {'key': key, 'prompt': prompt, 'cond': cond, 'seed': seed, 'prompt_id': pid, 'status': h['status']['status_str'],
                   'exec_s': ((ts.get('execution_success') or ts.get('execution_error')) - ts['execution_start']) / 1000, 'wall_s': round(time.time() - t0, 1),
                   'cached_nodes': cached[0] if cached else [], 'error': (err[0].get('exception_message', '')[:400] if err else None),
                   'outputs': outs, 'commit_start_pct': c0, 'commit_peak_pct': peak['pct'], 'graph': g}
            open(OUT + 'runs.jsonl', 'a').write(json.dumps(rec) + '\n')
            print(key, pid[:8], rec['status'], rec['exec_s'], rec['cached_nodes'], rec['commit_peak_pct'], rec['error'] or '', flush=True)
            if rec['status'] != 'success': break
stop.set()
