"""q-32 retest: four LoRA candidates against their no-LoRA controls on three showcase cases (23 September 2026, overnight lab).

    python q32_loras.py render     # 21 renders straight to ComfyUI 8188 (controls shared per base)
    python q32_loras.py seal       # blind copies per (base, case) group + key.sealed.json

Review-judge request (PR #862): the #846 smokes ran one seed; retest on three seeds against a control with the rubric R1-R6.
Candidates (strength and trigger from presets/settings-kb.json / models/README.md; the trigger is appended at the END):
- WAI v17 + Aesthetic Masterpiece v3 (`illustrious_masterpieces_v3`) 0.4, trigger "masterpiece, best quality, very aesthetic";
- WAI v17 + Add Micro Details v7 (`AddMicroDetails_Illustrious_v7`) 0.5, trigger "addmicrodetails";
- NoobAI XL 1.1 + Flat Color v2 (`illustrious_flat_color_v2`) 0.85, trigger "flat color, no lineart" (NoobAI outputs are hobby-only);
- Pony V6 + Gothic Neon (`g0th1cPXL`) 0.85, trigger "g0thicPXL, glowing, neon".
Cases: `portrait` (Makima), `action` (2B), `hands` (original alchemist) from ../suite.py with their fixed seeds; each base's control is
the same graph with the LoRA slot pruned and no trigger. Pony drew youthful faces for "adult woman" in the smoke, so the Pony prompts
carry strong adult cues (mature female, tall, adult proportions) and the full adult-only negative; a youthful-looking result is
discarded, not repaired. Decoding uses VAEDecodeTiled 512/64 (../sdxl-vae-decode: pixel-equivalent, faster, no spill).
Outputs stay in ComfyUI output/Research/overnight-20260923/q32-loras/.
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import labkit, suite  # noqa: E402

CASES = ['portrait', 'action', 'hands']
BASES = {
    'wai': {'graph': 'wai-api.json', 'prefix': '', 'suffix': ', masterpiece, best quality, amazing quality',
            'neg': 'bad quality, worst quality, worst detail, sketch, censor, bad anatomy, bad hands, extra digits, missing fingers'},
    'noob': {'graph': 'noob-api.json', 'prefix': 'masterpiece, best quality, newest, absurdres, highres, safe, ', 'suffix': '',
             'neg': 'worst quality, low quality, worst aesthetic, lowres, bad anatomy, bad hands, text, error, missing fingers, extra digits, '
                    'fewer digits, cropped, jpeg artifacts, signature, watermark, username, blurry, mammal, anthro, furry, ambiguous form, feral'},
    'pony': {'graph': 'pony-api.json', 'prefix': 'score_9, score_8_up, score_7_up, score_6_up, source_anime, rating_safe, ',
             'suffix': ', mature female, tall, adult proportions, adult face', 'neg': 'score_4, score_5, score_6, worst quality, low quality, blurry, text, watermark'},
}
LORAS = {
    'masterpiece04': ('wai', 'illustrious_masterpieces_v3.safetensors', 0.4, 'masterpiece, best quality, very aesthetic'),
    'microdetails05': ('wai', 'AddMicroDetails_Illustrious_v7.safetensors', 0.5, 'addmicrodetails'),
    'flatcolor085': ('noob', 'illustrious_flat_color_v2.safetensors', 0.85, 'flat color, no lineart'),
    'gothicneon085': ('pony', 'g0th1cPXL.safetensors', 0.85, 'g0thicPXL, glowing, neon'),
}


def graph(base, case, lora=None):
    b = BASES[base]; g = json.loads((labkit.REPO / 'workflows/api' / b['graph']).read_text(encoding='utf-8'))
    text = b['prefix'] + case['tags'] + b['suffix']
    if lora:
        _, name, strength, trigger = LORAS[lora]
        g['8']['inputs'].update(lora_name=name, strength_model=strength, strength_clip=strength)
        text += ', ' + trigger
    g = labkit.prune_loras(g)
    g['2']['inputs']['text'] = text
    g['3']['inputs']['text'] = suite.negative_tags(case, b['neg'])
    g['5']['inputs']['seed'] = case['seed']
    g['6'] = {'class_type': 'VAEDecodeTiled', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2], 'tile_size': 512, 'overlap': 64,
                                                         'temporal_size': 64, 'temporal_overlap': 8}}
    g['7']['inputs']['filename_prefix'] = 'Research/overnight-20260923/q32-loras/%s-%s' % (lora or base + '-control', case['id'])
    return g


def render():
    results = labkit.Results(HERE)
    for base in BASES:
        for cid in CASES:
            case = suite.by_id(cid)
            labkit.run_graph(graph(base, case), '%s-control-%s' % (base, cid), results, timeout=900,
                             extra={'config': base + '-control', 'base': base, 'case': cid, 'seed': case['seed']})
            for lora, spec in LORAS.items():
                if spec[0] != base: continue
                labkit.run_graph(graph(base, case, lora), '%s-%s' % (lora, cid), results, timeout=900,
                                 extra={'config': lora, 'base': base, 'case': cid, 'seed': case['seed'], 'lora': spec[1], 'strength': spec[2]})


def seal():
    results = labkit.Results(HERE)
    items = [{'group': '%s-%s' % (r['base'], r['case']), 'config': r['config'], 'file': r['outputs'][0]['file']}
             for r in results.records if r.get('status') == 'success' and r.get('outputs')]
    print(labkit.seal(items, HERE))


if __name__ == '__main__':
    {'render': render, 'seal': seal}[sys.argv[1]]()
