"""Automatic hand repair: does the detector route (no hand-drawn mask) fix hands at a stronger setting? (23 September 2026)

    python hand_fix.py run     # 4 sources x 3 detailer settings, straight to ComfyUI (the shipped anime-hand graph)
    python hand_fix.py seal    # blind copies per source (original + 3 settings) + key.sealed.json

../hand-inpaint/ found that a manual masked repaint at denoise 0.6 fixes a six-digit hand where 0.4 does not. `anime-hand`
(Impact Pack FaceDetailer on `bbox/hand_yolov8n.pt`, WAI v17) needs no mask but is authored at denoise 0.4. Sources are
four pictures the lab judged `fixable` for hands tonight (all original characters, all Git-safe):
- `noob4`: Studio/noob_00004_.png, the six-digit raised hand (the hand-inpaint subject);
- `noob5`: Studio/noob_00005_.png, the witch's left hand with smeared, partly fused fingers (census);
- `cstati`: Studio/CSTati-v3-Baseline_00003_.png, both hands fingerless mittens (census);
- `yume`: Studio/YumeFlux-ILv1-Baseline_00002_.png, a mitten right hand (census).
Settings (FaceDetailer inputs only; the positive is a generic hand prompt, the graph's own prompt describes another character):
- `authored`: denoise 0.4, guide_size 512, bbox_crop_factor 2.5 (the shipped values);
- `d06`: denoise 0.6, otherwise authored;
- `d06-g768`: denoise 0.6, guide_size 768, bbox_crop_factor 3.0 (the crop is sampled larger).
Judged blind per source with R8: `adherence` = the named hand defect fixed, `control` = everything else kept.
"""
import json, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import labkit  # noqa: E402

INPUT = labkit.OUTPUT.parent / 'input'
SOURCES = {'noob4': 'Studio/noob_00004_.png', 'noob5': 'Studio/noob_00005_.png',
           'cstati': 'Studio/CSTati-v3-Baseline_00003_.png', 'yume': 'Studio/YumeFlux-ILv1-Baseline_00002_.png'}
SETTINGS = {'authored': {'denoise': 0.4, 'guide_size': 512, 'bbox_crop_factor': 2.5},
            'd06': {'denoise': 0.6, 'guide_size': 512, 'bbox_crop_factor': 2.5},
            'd06-g768': {'denoise': 0.6, 'guide_size': 768, 'bbox_crop_factor': 3.0}}
POSITIVE = ('masterpiece, best quality, amazing quality, detailed hand, five fingers, natural hand pose, slender fingers, '
            'clean lineart, same colours, same style as the surrounding picture')
NEGATIVE = ('bad quality, worst quality, worst detail, sketch, censor, bad hands, extra digits, fewer digits, missing fingers, '
            'extra fingers, fused fingers, mitten hands, deformed hands, blurry, text, watermark')
SEED = 2026092395


def staged(name):
    """Copy the source into ComfyUI's input folder under a lab name (LoadImage reads from input/)."""
    dest = INPUT / ('overnight-handfix-%s.png' % name)
    if not dest.exists(): shutil.copyfile(labkit.OUTPUT / SOURCES[name], dest)
    return dest.name


def graph(setting, name):
    g = json.loads((labkit.REPO / 'workflows/api/anime-hand-api.json').read_text(encoding='utf-8'))
    g['4']['inputs']['image'] = staged(name)
    g['2']['inputs']['text'] = POSITIVE; g['3']['inputs']['text'] = NEGATIVE
    g['5']['inputs'].update(SETTINGS[setting]); g['5']['inputs']['seed'] = SEED
    g['7']['inputs']['filename_prefix'] = 'Research/overnight-20260923/hand-fix/%s-%s' % (setting, name)
    g['9']['inputs']['filename_prefix'] = 'Research/overnight-20260923/hand-fix/mask-%s-%s' % (setting, name)
    return g


def run():
    results = labkit.Results(HERE)
    for name in SOURCES:
        for setting in SETTINGS:
            labkit.run_graph(graph(setting, name), '%s-%s' % (setting, name), results, timeout=900,
                             extra={'config': setting, 'source': name, 'source_file': str(labkit.OUTPUT / SOURCES[name]), 'seed': SEED})


def seal():
    results = labkit.Results(HERE); items = []
    for r in results.records:
        if r.get('status') != 'success' or not r.get('outputs'): continue
        image = next(o['file'] for o in r['outputs'] if '/mask-' not in o['file'].replace('\\', '/') and '\\mask-' not in o['file'])
        items.append({'group': r['source'], 'config': r['config'], 'file': image})
    for name, rel in SOURCES.items(): items.append({'group': name, 'config': 'original', 'file': str(labkit.OUTPUT / rel)})
    print(labkit.seal(items, HERE))


if __name__ == '__main__':
    {'run': run, 'seal': seal}[sys.argv[1]]()
