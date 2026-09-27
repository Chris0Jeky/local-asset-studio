# As-run script (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
"""#1028 seed-audition Pareto cell (27 Sep 2026): B0 (25 steps) vs F0 (Pruna 8-step LoRA at 2.0, 8 steps) vs Q1 (2.1 Fix LoRA at
1.0, 25 steps) on the isolated qwen21 backend (8196), 2 prompts x 3 seeds, the prompt text unchanged within a prompt block, so the
text encoder runs once per block and the diffusion model stays resident (the case the Pruna lab left open).
Straight to ComfyUI, one POST per cell, never resubmitted. Host commit sampled every 0.5 s; the run stops above 92 %."""
import copy, json, sys, threading, time
sys.path.insert(0, 'C:/Users/jekyt/AppData/Local/Temp/cancel-proof-0927'); import drive
C = 'http://127.0.0.1:8196'; OUT = 'C:/Users/jekyt/AppData/Local/Temp/qi21-pareto/'
BASE = json.load(open('C:/Users/jekyt/Desktop/Printer Config/Others/Git/local-asset-studio/experiments/curated/qi21-lab2-20260927/pruna/graph-char-p2.json'))
PROMPTS = {'char': 'Anime key visual of an adult silver-haired sorceress in a midnight-blue travelling coat, holding a glowing brass lantern on a rainy stone bridge at blue hour. Clean linework, layered cel shading, teal and warm amber light.',
           'prop': 'Game item illustration of an ornate brass pocket compass with a teal enamel face and a small star-shaped needle, three-quarter view, centred on a plain warm grey background, clean cel shading, crisp silhouette, no text.'}
CONDS = {'B0': (None, 1.0, 25), 'F0': ('p_qwen_image_2.1_8step_v0.1.safetensors', 2.0, 8), 'Q1': ('qwen-image-2.1-fix-1.0-comfy.safetensors', 1.0, 25)}
SEEDS = [2026092731, 2026092732, 2026092733]
peak = {'pct': 0}; stop = threading.Event()
def sampler():
    while not stop.is_set():
        c = drive.commit(); peak['pct'] = max(peak['pct'], c['pct']); time.sleep(0.5)
def graph(prompt, cond, seed, key):
    g = copy.deepcopy(BASE); lora, strength, steps = CONDS[cond]
    g['4']['inputs']['prompt'] = PROMPTS[prompt]; g['6']['inputs'].update(seed=seed, steps=steps)
    if lora: g['20']['inputs'].update(lora_name=lora, strength_model=strength)
    else: del g['20']; g['6']['inputs']['model'] = ['1', 0]
    g['8']['inputs']['filename_prefix'] = 'Research/qi21-pareto-20260927/' + key
    return g
def main():
    threading.Thread(target=sampler, daemon=True).start()
    for prompt in PROMPTS:
        for cond in CONDS:
            for seed in SEEDS:
                key = '%s-%s-%d' % (prompt, cond, seed % 100)
                q = drive.req(C, '/queue')[1]; assert not q['queue_running'] and not q['queue_pending'], 'qwen21 queue busy'
                if peak['pct'] > 92: print('STOP: commit peak', peak['pct']); return
                peak['pct'] = drive.commit()['pct']; c0 = peak['pct']; t0 = time.time(); g = graph(prompt, cond, seed, key)
                code, reply = drive.req(C, '/prompt', {'prompt': g, 'client_id': 'qi21-pareto-0927'}); assert code == 200, reply; pid = reply['prompt_id']
                while True:
                    h = (drive.req(C, '/history/' + pid)[1] or {}).get(pid)
                    if h and (h['status'].get('completed') or h['status'].get('status_str') in ('success', 'error')): break
                    time.sleep(0.5)
                ts = {m[0]: m[1].get('timestamp') for m in h['status']['messages']}
                cached = [m[1].get('nodes') for m in h['status']['messages'] if m[0] == 'execution_cached']
                outs = [o for n in h['outputs'].values() for o in n.get('images', [])]
                rec = {'key': key, 'prompt': prompt, 'cond': cond, 'seed': seed, 'prompt_id': pid, 'status': h['status']['status_str'],
                       'exec_s': (ts.get('execution_success', ts.get('execution_error', 0)) - ts['execution_start']) / 1000, 'wall_s': round(time.time() - t0, 1),
                       'cached_nodes': cached[0] if cached else [], 'text_encoded': '4' not in (cached[0] if cached else []),
                       'outputs': outs, 'commit_start_pct': c0, 'commit_peak_pct': peak['pct'], 'graph': g}
                open(OUT + 'runs.jsonl', 'a').write(json.dumps(rec) + '\n')
                print(key, pid[:8], rec['status'], rec['exec_s'], 'TE' if rec['text_encoded'] else '--', rec['commit_peak_pct'], flush=True)
                if rec['status'] != 'success': print('STOP: error'); return
main(); stop.set()
