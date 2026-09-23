"""SDXL VAE decode: plain VAEDecode against VAEDecodeTiled (23 September 2026, overnight lab).

    python ab_vae.py render [case ...]   # per suite case: one sampling, three decoders (the latent is reused from ComfyUI's cache)
    python ab_vae.py diff                # pixel differences between the decoders of each case (objective seam check)
    python ab_vae.py seal                # blind copies + key.sealed.json

Question: the speed census showed every SDXL preset spending 6-9 s sampling and ~11 s in VAEDecode at 832x1216 while
3-5 GB of the ComfyUI process sat in WDDM shared memory. Does a tiled decode avoid the spill and the time, without seams?
Method: the shipped `wai` graph (WAI v17, 832x1216, 30 steps euler_ancestral/normal, cfg 5) on the seven-prompt showcase suite
(suite.py, fixed seeds). For each case the three graphs differ only in the decoder node, so the second and third prompts reuse
the cached latent and time the decode alone; the decoder order rotates across cases so no decoder always runs first.
Outputs stay in ComfyUI output/Research/overnight-20260923/sdxl-vae-decode/ (famous characters never enter Git).
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import labkit, suite  # noqa: E402

DECODERS = {
    'plain': {'class_type': 'VAEDecode', 'inputs': {}},
    'tiled512': {'class_type': 'VAEDecodeTiled', 'inputs': {'tile_size': 512, 'overlap': 64, 'temporal_size': 64, 'temporal_overlap': 8}},
    'tiled1024': {'class_type': 'VAEDecodeTiled', 'inputs': {'tile_size': 1024, 'overlap': 64, 'temporal_size': 64, 'temporal_overlap': 8}},
}
ORDERS = [['plain', 'tiled512', 'tiled1024'], ['tiled512', 'tiled1024', 'plain'], ['tiled1024', 'plain', 'tiled512']]
QUALITY = ', masterpiece, best quality, amazing quality'
WAI_NEG = 'bad quality, worst quality, worst detail, sketch, censor, bad anatomy, bad hands, extra digits, missing fingers'


def graph(decoder, case):
    g = labkit.prune_loras(json.loads((labkit.REPO / 'workflows/api/wai-api.json').read_text(encoding='utf-8')))
    g['2']['inputs']['text'] = case['tags'] + QUALITY
    g['3']['inputs']['text'] = suite.negative_tags(case, WAI_NEG)
    g['5']['inputs']['seed'] = case['seed']
    node = json.loads(json.dumps(DECODERS[decoder])); node['inputs'].update(samples=['5', 0], vae=['1', 2])
    g['6'] = node
    g['7']['inputs']['filename_prefix'] = 'Research/overnight-20260923/sdxl-vae-decode/%s-%s' % (decoder, case['id'])
    return g


def render(ids):
    results = labkit.Results(HERE)
    for i, case in enumerate(c for c in suite.SUITE if not ids or c['id'] in ids):
        for position, decoder in enumerate(ORDERS[i % 3]):
            labkit.run_graph(graph(decoder, case), '%s-%s' % (decoder, case['id']), results, timeout=900,
                             extra={'config': decoder, 'case': case['id'], 'seed': case['seed'], 'position_in_case': position})


SWITCH = [('animagine-xl-4.0-opt.safetensors', ['plain', 'tiled512']), ('NoobAI-XL-v1.1.safetensors', ['tiled512', 'plain']),
          ('waiIllustriousSDXL_v170.safetensors', ['plain', 'tiled512'])]


def switch():
    """The census condition: each prompt pair starts with a checkpoint switch (the previous SDXL model is still cached), then both
    decoders run on the same cached latent, in alternating order. Case `hands` (original character), same seed."""
    results = labkit.Results(HERE); case = suite.by_id('hands')
    for ckpt, order in SWITCH:
        for position, decoder in enumerate(order):
            g = graph(decoder, case); g['1']['inputs']['ckpt_name'] = ckpt
            g['7']['inputs']['filename_prefix'] = 'Research/overnight-20260923/sdxl-vae-decode/switch-%s-%s' % (ckpt.split('.')[0], decoder)
            labkit.run_graph(g, 'switch-%s-%s' % (ckpt.split('.')[0], decoder), results, timeout=900,
                             extra={'config': decoder, 'case': 'hands', 'seed': case['seed'], 'checkpoint': ckpt, 'position_in_case': position, 'condition': 'after-switch'})


def diff():
    import numpy as np
    from PIL import Image
    results = labkit.Results(HERE); out = {}
    for case in suite.SUITE:
        files = dict((r['config'], r['outputs'][0]['file']) for r in results.records if r.get('case') == case['id'] and r.get('outputs'))
        if 'plain' not in files: continue
        base = np.asarray(Image.open(files['plain']).convert('RGB')).astype(np.int16)
        for name in ('tiled512', 'tiled1024'):
            if name not in files: continue
            other = np.asarray(Image.open(files[name]).convert('RGB')).astype(np.int16)
            d = np.abs(base - other).max(axis=2)
            rows, cols = d.mean(axis=1), d.mean(axis=0)
            out['%s/%s' % (case['id'], name)] = {'mean_abs': round(float(d.mean()), 3), 'p99': float(np.percentile(d, 99)), 'max': int(d.max()),
                                                 'pixels_over_16': int((d > 16).sum()), 'worst_rows': [int(i) for i in np.argsort(rows)[-4:]],
                                                 'worst_cols': [int(i) for i in np.argsort(cols)[-4:]]}
    (HERE / 'pixel-diff.json').write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8', newline='\n'); print(json.dumps(out, indent=1))


def seal():
    results = labkit.Results(HERE)
    items = [{'group': r['case'], 'config': r['config'], 'file': r['outputs'][0]['file']}
             for r in results.records if r.get('status') == 'success' and r.get('outputs')]
    print(labkit.seal(items, HERE))


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'render': render(sys.argv[2:])
    elif cmd == 'diff': diff()
    elif cmd == 'switch': switch()
    else: seal()
