"""Qwen-Image 2.1 first research runs, straight against the isolated backend on 127.0.0.1:8196 (22 September 2026).

One deliberate run per case, never a retry: each case loads the shipped API graph, changes only the fields named in
CASES, submits once, polls /history, copies the PNG next to this file and records prompt ID, seed, timing and the
alpha statistics into research.json. Run one case at a time: `python research.py t2i`.
"""
import json, os, shutil, sys, time, urllib.request, uuid
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent; REPO = HERE.parents[2]; URL = 'http://127.0.0.1:8196'
OUTPUT = Path('C:/AI/experiments/qwen-image-21/ComfyUI/output')
CASES = {
    't2i': ('qwen21-t2i', {}),
    't2i-40': ('qwen21-t2i', {('6', 'steps'): 40}),
    'rgba-icon': ('qwen21-rgba', {('5', 'width'): 1024, ('5', 'height'): 1024}),
    'rgba-character': ('qwen21-rgba', {('9', 'string_b'): 'A full-body anime game character sprite of an adult red-haired knight in silver armour '
                                       'with a blue cape, standing in a relaxed pose, clean cel shading, whole figure in frame.'}),
    'edit': ('qwen21-edit', {}),
    't2i-2k': ('qwen21-t2i', {('5', 'width'): 2048, ('5', 'height'): 2048}),
    # The model card's "extract subjects from photographs": the one-picture edit with the RGBA wording as the instruction.
    'cutout': ('qwen21-edit', {('4', 'prompt'): 'This is an RGBA image with transparency. Extract the woman in the green cloak with her lantern, '
                               'exactly as drawn, and remove everything else. The image has alpha channel and the background is transparent.',
                               ('10', 'image'): 'wai.png'}),
}
# Two community suggestions from civitai (22 September 2026): CFG 2 (workflow 2951890's author) and the
# "Qwen Image 2.1 Fix v1.0" LoRA (model 2957332, version 3350008, sha256 e4a36915...), model-only at strength 1.
CASES['t2i-cfg2'] = ('qwen21-t2i', {('6', 'cfg'): 2.0})
CASES['t2i-fix'] = ('qwen21-t2i', {})
CASES['rgba-character-fix'] = ('qwen21-rgba', dict(CASES['rgba-character'][1]))
LORA_CASES = {'t2i-fix', 'rgba-character-fix'}
FIX_LORA = 'qwen-image-2.1-fix-1.0-comfy.safetensors'
REFERENCES = {'studio-lantern-cutout.png': 'examples/references/studio-lantern-cutout.png', 'wai.png': 'examples/gallery/wai.png'}


def call(route, body=None):
    request = urllib.request.Request(URL + route, json.dumps(body).encode() if body is not None else None, {'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(request, timeout=60))


def upload(path):
    boundary = uuid.uuid4().hex; data = Path(path).read_bytes()
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{Path(path).name}"\r\nContent-Type: image/png\r\n\r\n').encode() + data \
        + f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n--{boundary}--\r\n'.encode()
    request = urllib.request.Request(URL + '/upload/image', body, {'Content-Type': 'multipart/form-data; boundary=' + boundary})
    return json.load(urllib.request.urlopen(request, timeout=60))


def alpha_stats(path):
    image = Image.open(path)
    if 'A' not in image.getbands(): return {'mode': image.mode, 'alpha': None}
    alpha = image.getchannel('A'); histogram = alpha.histogram(); total = sum(histogram)
    return {'mode': image.mode, 'size': image.size, 'alpha_zero_fraction': round(histogram[0] / total, 4),
            'alpha_full_fraction': round(histogram[255] / total, 4), 'alpha_partial_fraction': round(1 - (histogram[0] + histogram[255]) / total, 4)}


def run(case):
    preset_id, changes = CASES[case]
    graph = json.loads((REPO / f'workflows/api/{preset_id}-api.json').read_text(encoding='utf-8'))
    for (node, field), value in changes.items(): graph[node]['inputs'][field] = value
    graph['8']['inputs']['filename_prefix'] = 'research/qwen21-' + case
    if case in LORA_CASES:
        graph['11'] = {'class_type': 'LoraLoaderModelOnly', 'inputs': {'model': ['1', 0], 'lora_name': FIX_LORA, 'strength_model': 1.0}}
        graph['6']['inputs']['model'] = ['11', 0]
    if preset_id == 'qwen21-edit': upload(REPO / REFERENCES[graph['10']['inputs']['image']])
    queue = call('/queue')
    if queue.get('queue_running') or queue.get('queue_pending'): raise SystemExit('Isolated queue is busy; nothing submitted')
    started = time.time(); prompt_id = call('/prompt', {'prompt': graph, 'client_id': 'qwen21-research'})['prompt_id']
    print(case, 'prompt', prompt_id, flush=True)
    while True:
        time.sleep(3); history = call('/history/' + prompt_id).get(prompt_id)
        if history: break  # ComfyUI writes a history entry only once the prompt has finished
        if time.time() - started > 3600: raise SystemExit('No terminal history after 3600 s; prompt ' + prompt_id + ' left alone')
    elapsed = round(time.time() - started, 1); status = history['status']
    files = [image for output in history.get('outputs', {}).values() for image in output.get('images', [])]
    record = {'case': case, 'preset_id': preset_id, 'prompt_id': prompt_id, 'status': status.get('status_str'), 'wall_seconds': elapsed,
              'seed': graph['6']['inputs']['seed'], 'steps': graph['6']['inputs']['steps'], 'changes': {f'{n}.{f}': v for (n, f), v in changes.items()},
              'cfg': graph['6']['inputs']['cfg'], 'lora': FIX_LORA if case in LORA_CASES else None,
              'messages': [m[0] for m in status.get('messages', [])], 'outputs': []}
    for image in files:
        source = OUTPUT / image.get('subfolder', '') / image['filename']; target = HERE / ('qwen21-' + case + '.png')
        shutil.copyfile(source, target); record['outputs'].append({'file': target.name, 'bytes': target.stat().st_size, **alpha_stats(target)})
    log = HERE / 'research.json'; records = json.loads(log.read_text(encoding='utf-8')) if log.exists() else []
    records.append(record); log.write_text(json.dumps(records, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=1), flush=True)


if __name__ == '__main__':
    run(sys.argv[1])
