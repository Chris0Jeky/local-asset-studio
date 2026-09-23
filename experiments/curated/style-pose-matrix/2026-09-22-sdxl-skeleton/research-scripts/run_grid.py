"""Research renders straight against ComfyUI 127.0.0.1:8188 for the SDXL drawn-skeleton route (22 September 2026, #761/#445).

One prompt at a time: upload the skeleton PNGs (POST /upload/image), queue one graph, wait for /history, copy the outputs
into the scratch folder, record prompt ID and ComfyUI's own execution timestamps in grid.json, then the next. A cell whose
prompt ID is already recorded is never queued again: a rerun only reads its /history. No detector node is in any graph.

This ComfyUI reloads the checkpoint for every prompt (about 42 s of the 85 s the first single-image cells took), so after
the three baseline cells each prompt carries one group: every cell that shares skeleton, guide renderer, checkpoint and
ControlNet, as one KSampler -> VAEDecode -> SaveImage chain per cell behind shared loaders. A KSampler draws its noise from
its own seed alone, so each image is the one a single-cell graph with that seed gives (`graph(cell)` below).

    python run_grid.py <phase> [--out <scratch folder for the PNG outputs>]

Phases: `grid` (no-ControlNet baseline, WAI v17 + Xinsir OpenPose over strength x end_percent, the wai-pose default
0.9/0.85), `compare` (thin-line renderer, Union ControlNet, Animagine XL 4 at the chosen setting).
"""
import argparse
import copy
import json
import mimetypes
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
COMFY = 'http://127.0.0.1:8188'
RESULTS = HERE / 'grid.json'
SEEDS = (2026092201, 2026092202, 2026092203)
W, H = 832, 1216
WAI = 'waiIllustriousSDXL_v170.safetensors'
ANIMAGINE = 'animagine-xl-4.0-opt.safetensors'
OPENPOSE = 'xinsir-openpose-sdxl.safetensors'
UNION = 'xinsir-union-sdxl-1.0.safetensors'
# The subject is named and the pose is left to the skeleton ("dynamic pose" only), so the ControlNet carries the pose.
WAI_POSITIVE = ('1girl, solo, full body, dynamic pose, adventurer, silver hair, long ponytail, green eyes, brown leather '
                'jacket, white shirt, black trousers, brown boots, white background, simple background, '
                'masterpiece, best quality, amazing quality')
WAI_NEGATIVE = 'bad quality, worst quality, worst detail, sketch, censor, multiple views, text, watermark'
ANIMAGINE_POSITIVE = ('1girl, solo, original, safe, full body, dynamic pose, adventurer, silver hair, long ponytail, green '
                      'eyes, brown leather jacket, white shirt, black trousers, brown boots, white background, simple '
                      'background, masterpiece, high score, great score, absurdres')
ANIMAGINE_NEGATIVE = ('lowres, bad anatomy, bad hands, text, error, missing finger, extra digits, fewer digits, cropped, '
                      'worst quality, low quality, low score, bad score, average score, signature, watermark, username, blurry')


def request(path, body=None, headers=None, timeout=60):
    req = urllib.request.Request(COMFY + path, body, headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as reply: return reply.read()


def upload(path):
    boundary = uuid.uuid4().hex
    head = (f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{path.name}"\r\n'
            f'Content-Type: {mimetypes.guess_type(path.name)[0]}\r\n\r\n').encode()
    tail = (f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'
            f'--{boundary}--\r\n').encode()
    reply = json.loads(request('/upload/image', head + path.read_bytes() + tail,
                               {'Content-Type': 'multipart/form-data; boundary=' + boundary}))
    return reply['name']


def graph(cell, guide):
    g = json.loads((ROOT / 'workflows/api/wai-pose-api.json').read_text(encoding='utf-8'))
    animagine = cell['checkpoint'] == ANIMAGINE
    g['1']['inputs']['ckpt_name'] = cell['checkpoint']
    g['2']['inputs']['text'] = ANIMAGINE_POSITIVE if animagine else WAI_POSITIVE
    g['3']['inputs']['text'] = ANIMAGINE_NEGATIVE if animagine else WAI_NEGATIVE
    g['4']['inputs'].update(width=W, height=H)
    g['5']['inputs'].update(seed=cell['seed'], steps=28, cfg=5.0, sampler_name='euler_ancestral', scheduler='normal')
    g['7']['inputs']['filename_prefix'] = 'Research/sdxl-skeleton/' + cell['id']
    g['8']['inputs']['control_net_name'] = cell['controlnet']
    g['9']['inputs']['image'] = guide
    g['10']['inputs'].update(strength=cell['strength'], start_percent=0.0, end_percent=cell['end'])
    if cell['controlnet'] == UNION:
        g['11'] = {'class_type': 'SetUnionControlNetType', 'inputs': {'control_net': ['8', 0], 'type': 'openpose'}}
        g['10']['inputs']['control_net'] = ['11', 0]
    return g


def group_graph(group, guide):
    """Shared loaders from graph(); per cell its own ControlNet apply (or none at strength 0), KSampler, decode and save."""
    base = graph(group[0], guide); g = {k: base[k] for k in ('1', '2', '3', '4', '8', '9', '11') if k in base}
    applies = {}
    for index, cell in enumerate(group):
        if cell['strength'] == 0: conditioning = (['2', 0], ['3', 0])
        else:
            key = (cell['strength'], cell['end'])
            if key not in applies:
                node = 'a%d' % len(applies); applies[key] = node
                g[node] = copy.deepcopy(base['10']); g[node]['inputs'].update(strength=cell['strength'], end_percent=cell['end'])
            conditioning = ([applies[key], 0], [applies[key], 1])
        sampler = copy.deepcopy(base['5']); sampler['inputs'].update(seed=cell['seed'], positive=conditioning[0], negative=conditioning[1])
        g['k%d' % index] = sampler
        g['d%d' % index] = {'class_type': 'VAEDecode', 'inputs': {'samples': ['k%d' % index, 0], 'vae': ['1', 2]}}
        g['s%d' % index] = {'class_type': 'SaveImage', 'inputs': {'images': ['d%d' % index, 0],
                                                                'filename_prefix': 'Research/sdxl-skeleton/' + cell['id']}}
    return g


def cells(phase, chosen):
    out = []
    def add(**kw):
        kw.setdefault('checkpoint', WAI); kw.setdefault('controlnet', OPENPOSE); kw.setdefault('renderer', 'openpose')
        kw['id'] = '{skeleton}-{tag}-s{strength}-e{end}-{seed}'.format(**kw).replace('.', '')
        out.append(kw)
    if phase == 'grid':
        for seed in SEEDS: add(skeleton='action', tag='baseline', strength=0.0, end=1.0, seed=seed)
        for skeleton in ('action', 'bent'):
            for strength in (0.6, 0.8, 1.0):
                for end in (0.6, 1.0):
                    for seed in SEEDS: add(skeleton=skeleton, tag='wai', strength=strength, end=end, seed=seed)
            for seed in SEEDS: add(skeleton=skeleton, tag='wai', strength=0.9, end=0.85, seed=seed)
    elif phase == 'compare':
        strength, end = chosen
        for skeleton in ('action', 'bent'):
            for seed in SEEDS:
                add(skeleton=skeleton, tag='lines', renderer='lines', strength=strength, end=end, seed=seed)
                add(skeleton=skeleton, tag='union', controlnet=UNION, strength=strength, end=end, seed=seed)
                add(skeleton=skeleton, tag='animagine', checkpoint=ANIMAGINE, strength=strength, end=end, seed=seed)
    else: raise SystemExit('unknown phase ' + phase)
    return out


def wait(prompt_id, limit=3600):
    started = time.time()
    while time.time() - started < limit:
        # A polling hiccup (one WinError 10013 on 22 September) is not an outcome: keep reading history, never resubmit.
        try: history = json.loads(request('/history/' + prompt_id)).get(prompt_id)
        except urllib.error.URLError: time.sleep(5); continue
        if history and history.get('status', {}).get('completed') is not None or (history and history.get('outputs')):
            return history
        time.sleep(2)
    raise SystemExit('no history for ' + prompt_id + ' after ' + str(limit) + ' s; not resubmitting')


def timing(history):
    stamps = {m[0]: m[1].get('timestamp') for m in history.get('status', {}).get('messages', [])}
    start, end = stamps.get('execution_start'), stamps.get('execution_success') or stamps.get('execution_error')
    return round((end - start) / 1000, 2) if start and end else None


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('phase'); parser.add_argument('--out', type=Path, default=ROOT / '.runtime/761/renders')
    parser.add_argument('--strength', type=float, default=0.8); parser.add_argument('--end', type=float, default=1.0)
    # A prompt whose history reads execution_error has a certain outcome (nothing was made); only those may be queued again,
    # once each, with the failed record kept under failed_attempts.
    parser.add_argument('--retry-failed', action='store_true')
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    results = json.loads(RESULTS.read_text(encoding='utf-8')) if RESULTS.exists() else {'cells': {}}
    if args.retry_failed:
        for cell_id in [k for k, v in results['cells'].items() if v.get('status') == 'error']:
            failed = results['cells'].pop(cell_id)
            if any(f['id'] == cell_id for f in results.get('failed_attempts', [])): raise SystemExit(cell_id + ' already failed twice; not retrying')
            results.setdefault('failed_attempts', []).append(failed)
    guides = {}
    for skeleton in ('action', 'bent'):
        for renderer in ('openpose', 'lines'):
            guides[skeleton, renderer] = upload(HERE.parent / f'skeleton-{skeleton}.{renderer}.png')
    client = uuid.uuid4().hex
    def save():
        RESULTS.write_text(json.dumps(results, indent=1) + '\n', encoding='utf-8', newline='\n')
    def collect(ids):
        history = wait(results['cells'][ids[0]]['prompt_id'])
        seconds = timing(history)
        for cell_id in ids:
            record = results['cells'][cell_id]
            record['status'] = history.get('status', {}).get('status_str')
            record['prompt_execution_seconds'] = seconds; record['images_in_prompt'] = len(ids)
            images = history.get('outputs', {}).get(record.get('save_node', '7'), {}).get('images', [])
            if images:
                image = images[0]; record['output'] = image['subfolder'] + '/' + image['filename']
                query = urllib.parse.urlencode({'filename': image['filename'], 'subfolder': image['subfolder'], 'type': image['type']})
                (args.out / (cell_id + '.png')).write_bytes(request('/view?' + query, timeout=120))
            print(cell_id, record['prompt_id'], record['status'], seconds, len(ids), flush=True)
        save()
    # Finish anything already queued first: a recorded prompt ID is waited on, never resubmitted.
    pending = {}
    for cell_id, record in results['cells'].items():
        if not record.get('status'): pending.setdefault(record['prompt_id'], []).append(cell_id)
    for ids in pending.values(): collect(ids)
    groups = {}
    for cell in cells(args.phase, (args.strength, args.end)):
        if cell['id'] in results['cells']: continue
        key = (cell['skeleton'], cell['renderer'], cell['checkpoint'], cell['controlnet'])
        groups.setdefault(key, []).append(cell)
    for key, group in groups.items():
        queue = json.loads(request('/queue'))
        if queue['queue_running'] or queue['queue_pending']: raise SystemExit('ComfyUI is busy with other work; stopping')
        body = json.dumps({'prompt': group_graph(group, guides[key[0], key[1]]), 'client_id': client}).encode()
        try: reply = json.loads(request('/prompt', body, {'Content-Type': 'application/json'}))
        except urllib.error.HTTPError as error: raise SystemExit('rejected ' + group[0]['id'] + ': ' + error.read().decode('utf-8', 'replace')[:800])
        for index, cell in enumerate(group):
            results['cells'][cell['id']] = dict(cell, prompt_id=reply['prompt_id'], guide=guides[key[0], key[1]], save_node='s%d' % index)
        save()
        collect([cell['id'] for cell in group])

if __name__ == '__main__':
    main()
