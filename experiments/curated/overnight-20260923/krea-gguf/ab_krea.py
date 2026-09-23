"""Krea 2 Turbo: Q5_K_M GGUF (8.87 GB) against the shipped fp8 scaled build (13.1 GB) (23 September 2026, overnight lab).

    python ab_krea.py render <config> [case ...]   # config gguf|fp8; straight to ComfyUI 8188
    python ab_krea.py seal                         # blind copies per case + key.sealed.json

Question: is the GGUF faster per step on this 16 GB card (the fp8 build loads 12.5 GB and ran 35.4 s/step at 768x1152 with
474 MB in shared memory), and is its output indistinguishable from fp8's?
Method: the shipped `krea-portrait` graph (768x1152, 8 steps euler/simple, cfg 1) with the retro-anime LoRA pruned (strength 0:
the suite asks for many looks, and the LoRA is a separate question) and the diffusion loader swapped for ComfyUI-GGUF's
`UnetLoaderGGUF`; the showcase suite's prose prompts and fixed seeds, identical across builds. Famous-character and fanservice
outputs stay in ComfyUI output/Research/overnight-20260923/krea-gguf/.
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import labkit, suite  # noqa: E402


def graph(config, case):
    g = json.loads((labkit.REPO / 'workflows/api/krea-portrait-api.json').read_text(encoding='utf-8'))
    g['10']['inputs']['strength_model'] = 0; g = labkit.prune_loras(g)
    if config.startswith('gguf'): g['1'] = {'class_type': 'UnetLoaderGGUF', 'inputs': {'unet_name': 'krea2_turbo-Q5_K_M.gguf'}}
    if config.endswith('-cpute'): g['2']['inputs']['device'] = 'cpu'  # text encoder on the CPU: it never occupies VRAM
    g['4']['inputs']['text'] = case['prose']
    g['7']['inputs']['seed'] = case['seed']
    g['9']['inputs']['filename_prefix'] = 'Research/overnight-20260923/krea-gguf/%s-%s' % (config, case['id'])
    return g


def render(config, ids):
    results = labkit.Results(HERE)
    for case in suite.SUITE:
        if ids and case['id'] not in ids: continue
        labkit.run_graph(graph(config, case), '%s-%s' % (config, case['id']), results, timeout=2400,
                         extra={'config': config, 'case': case['id'], 'seed': case['seed']})


def probe(config):
    """Speed without a co-resident text encoder: unload every model (keeping ComfyUI's output cache), then sample the
    portrait prompt at seed+1, so the cached conditioning is reused and only the diffusion model is loaded."""
    labkit.guard(); case = dict(suite.by_id('portrait')); case['seed'] += 1
    import time, urllib.request
    urllib.request.urlopen(urllib.request.Request(labkit.COMFY + '/free', json.dumps({'unload_models': True, 'free_memory': False}).encode(),
                                                  {'Content-Type': 'application/json'}), timeout=60).read()  # empty 200 body
    time.sleep(3)
    g = graph(config, case); g['9']['inputs']['filename_prefix'] += '-probe'
    labkit.run_graph(g, '%s-probe-noTE' % config, labkit.Results(HERE), timeout=2400,
                     extra={'config': config, 'case': 'portrait', 'seed': case['seed'], 'probe': 'models unloaded first; cached conditioning'})


def cached(config):
    """Warm prompt with the same text: the portrait case again at seed+2, so the conditioning is served from ComfyUI's cache."""
    case = dict(suite.by_id('portrait')); case['seed'] += 2
    g = graph(config, case); g['9']['inputs']['filename_prefix'] += '-cached'
    labkit.run_graph(g, '%s-portrait-cached' % config, labkit.Results(HERE), timeout=2400,
                     extra={'config': config, 'case': 'portrait', 'seed': case['seed'], 'probe': 'same text as the previous portrait prompt'})


def lora(config):
    """The shipped krea-portrait preset exactly as authored (retro-anime LoRA 1.0, its own prompt and seed), with only the
    loader/encoder device changed: compared against the census's fp8 output of the same recipe (speed-census, prompt 8aed29b6)."""
    g = json.loads((labkit.REPO / 'workflows/api/krea-portrait-api.json').read_text(encoding='utf-8'))
    if config.startswith('gguf'): g['1'] = {'class_type': 'UnetLoaderGGUF', 'inputs': {'unet_name': 'krea2_turbo-Q5_K_M.gguf'}}
    if config.endswith('-cpute'): g['2']['inputs']['device'] = 'cpu'
    g['9']['inputs']['filename_prefix'] = 'Research/overnight-20260923/krea-gguf/%s-lora-retro' % config
    labkit.run_graph(g, '%s-lora-retro' % config, labkit.Results(HERE), timeout=2400,
                     extra={'config': config, 'case': 'krea-portrait-defaults', 'seed': g['7']['inputs']['seed'], 'probe': 'shipped recipe with the retro-anime LoRA'})


BLIND_GROUPS = {('portrait', 2026092301): 'portrait-s01', ('portrait', 2026092302): 'portrait-s02',
                ('action', 2026092302): 'action-s02', ('hands', 2026092307): 'hands-s07'}


def seal():
    """Blind groups = every (case, seed) rendered by more than one configuration: the shipped fp8 against GGUF with the CPU
    encoder on three suite cases, plus the portrait seed where GGUF (GPU encoder), fp8 with the CPU encoder and the no-encoder
    probes also exist."""
    results = labkit.Results(HERE); items = []
    for r in results.records:
        group = BLIND_GROUPS.get((r.get('case'), r.get('seed')))
        if group and r.get('status') == 'success' and r.get('outputs'):
            items.append({'group': group, 'config': r['config'] + ('-noTE' if 'noTE' in r['label'] else ''), 'file': r['outputs'][0]['file']})
    print(len(items), labkit.seal(items, HERE))


if __name__ == '__main__':
    if sys.argv[1] == 'render': render(sys.argv[2], sys.argv[3:])
    elif sys.argv[1] == 'probe': probe(sys.argv[2])
    elif sys.argv[1] == 'cached': cached(sys.argv[2])
    elif sys.argv[1] == 'lora': lora(sys.argv[2])
    else: seal()
