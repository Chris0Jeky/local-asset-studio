"""Z-Image Turbo: the installed fp8 (KJ scaled e4m3fn) build, with the text encoder on the GPU or the CPU, against the shipped
bf16 build (23 September 2026, overnight lab).

    python ab_zimage.py render <config> [case ...]   # config: bf16 | fp8 | fp8-cpute | bf16-cpute; straight to ComfyUI 8188
    python ab_zimage.py seal                         # blind copies per case + key.sealed.json

Question: the census measured the shipped `zimage` preset (bf16, 11.7 GB) at 28.7 s/step with 715 MB in shared memory and
308 s per 1024x1024 image; its text encoder `qwen_3_4b` loads 7.7 GB. The Krea experiment (../krea-gguf/) showed that a
co-resident text encoder is what pushes a diffusion model into WDDM shared memory on this card. Does
`z-image-turbo_fp8_scaled_e4m3fn_KJ.safetensors` (6.2 GB; civitai 2169712 version 2445746, SHA-256 matches the listing), with
or without the encoder on the CPU (`CLIPLoader` device cpu), cut the time without a visible quality loss?
Method: the shipped `zimage` graph (8 steps, res_multistep/simple, cfg 1, shift 3, 1024x1024, tiled VAE decode) on the
showcase suite's prose prompts with fixed seeds; only the diffusion file and the encoder device change. Outputs stay in
ComfyUI output/Research/overnight-20260923/zimage-fp8/.
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import labkit, suite  # noqa: E402

FILES = {'fp8': 'z-image-turbo_fp8_scaled_e4m3fn_KJ.safetensors', 'bf16': 'z_image_turbo_bf16.safetensors'}


def graph(config, case):
    g = json.loads((labkit.REPO / 'workflows/api/zimage-api.json').read_text(encoding='utf-8'))
    g['1']['inputs']['unet_name'] = FILES[config.split('-')[0]]
    if config.endswith('-cpute'): g['2']['inputs']['device'] = 'cpu'
    g['4']['inputs']['text'] = case['prose']
    g['8']['inputs']['seed'] = case['seed']
    g['10']['inputs']['filename_prefix'] = 'Research/overnight-20260923/zimage-fp8/%s-%s' % (config, case['id'])
    return g


def render(config, ids):
    results = labkit.Results(HERE)
    for case in suite.SUITE:
        if ids and case['id'] not in ids: continue
        labkit.run_graph(graph(config, case), '%s-%s' % (config, case['id']), results, timeout=1800,
                         extra={'config': config, 'case': case['id'], 'seed': case['seed']})


def seal():
    if (HERE / 'judgements.jsonl').exists() and (HERE / 'key.sealed.json').exists():
        raise SystemExit('key.sealed.json already has judgements against it; refusing to reshuffle')
    results = labkit.Results(HERE); groups = {}
    for r in results.records:
        if r.get('status') == 'success' and r.get('outputs'): groups.setdefault(r['case'], []).append(r)
    items = [{'group': case, 'config': r['config'], 'file': r['outputs'][0]['file']}
             for case, rs in groups.items() if len(rs) > 1 for r in rs]
    print(labkit.seal(items, HERE))


if __name__ == '__main__':
    if sys.argv[1] == 'render': render(sys.argv[2], sys.argv[3:])
    elif sys.argv[1] == 'seal': seal()
    else: raise SystemExit('unknown command %r (render, seal)' % sys.argv[1])
