"""Masked hand repaint at 0.6 with a feathered mask edge (23 September 2026, overnight lab; coordinator's follow-up).

    python feather.py run      # 3 direct ComfyUI prompts: the Studio's own masked-0.6 graphs with a soft mask
    python feather.py seam     # step across the old box edge, source vs every repair (seam.json)

The first pass (`hand_inpaint.py`) found that `anime-masked-repair` at denoise 0.6 fixes the six-digit hand on 3/3 seeds, but
every masked route left a vertical seam where the box mask's edge cuts the light streak. This run takes each seed's exact
submitted Studio graph (graphs/masked-0.6-<seed>.recipe.json -> workflow) and changes only the mask, with core nodes:
GrowMask (expand 12, tapered) -> MaskToImage -> ImageBlur (radius 24, sigma 8) -> ImageToMask (red). The soft mask drives both
`SetLatentNoiseMask` and the final `ImageCompositeMasked`.
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import labkit  # noqa: E402

SEEDS = [2026092361, 2026092362, 2026092363]
BOX_X = 180  # the right edge of the box mask (12,535)-(180,792); the light streak crosses it at y 560-760


def graph(seed):
    recipe = json.loads((HERE / 'graphs' / ('masked-0.6-%d.recipe.json' % seed)).read_text(encoding='utf-8'))
    g = json.loads(json.dumps(recipe['workflow']))
    load = next(k for k, v in g.items() if v['class_type'] == 'LoadImage')
    g['40'] = {'class_type': 'GrowMask', 'inputs': {'mask': [load, 1], 'expand': 12, 'tapered_corners': True}}
    g['41'] = {'class_type': 'MaskToImage', 'inputs': {'mask': ['40', 0]}}
    g['42'] = {'class_type': 'ImageBlur', 'inputs': {'image': ['41', 0], 'blur_radius': 24, 'sigma': 8.0}}
    g['43'] = {'class_type': 'ImageToMask', 'inputs': {'image': ['42', 0], 'channel': 'red'}}
    for v in g.values():
        if v['class_type'] in ('SetLatentNoiseMask', 'ImageCompositeMasked'): v['inputs']['mask'] = ['43', 0]
    save = next(k for k, v in g.items() if v['class_type'] == 'SaveImage')
    g[save]['inputs']['filename_prefix'] = 'Research/overnight-20260923/hand-inpaint/feathered-0.6-%d' % seed
    return g


def run():
    results = labkit.Results(HERE)
    for seed in SEEDS:
        labkit.run_graph(graph(seed), 'feathered-0.6-%d' % seed, results, timeout=900, extra={'config': 'feathered-0.6', 'seed': seed})


def seam():
    """Seam measure on the repair's change image d = repair - source (RGB, rows y 560-760, where the light streak crosses the
    box's right edge). The picture's own texture cancels in d. For each column pair in x 150-210, jump(x) = mean |d[:, x+1] -
    d[:, x]|: a hard composite makes one large jump at the box edge (x 179/180); a feathered one spreads the change so no single
    column jumps (jump(180) is the step from the last repainted column 180 to the untouched 181). Reported: the largest jump, where it sits, and the median jump in that window as the texture baseline."""
    import numpy as np
    from PIL import Image
    results = labkit.Results(HERE); out = {}
    src = np.asarray(Image.open(labkit.OUTPUT / 'Studio' / 'noob_00004_.png').convert('RGB')).astype(int)
    for r in results.records:
        files = r.get('output_files') or r.get('outputs') or []
        if r.get('status') not in ('success', 'completed') or not files: continue
        d = np.asarray(Image.open(files[0]['file']).convert('RGB')).astype(int) - src
        band = d[560:760, 150:212]
        jumps = np.abs(np.diff(band, axis=1)).mean(axis=(0, 2))
        i = int(jumps.argmax())
        out[r['label']] = {'max_jump': round(float(jumps.max()), 2), 'at_x': 150 + i, 'median_jump': round(float(np.median(jumps)), 2),
                           'jump_at_box_edge': round(float(jumps[BOX_X - 150]), 2)}
    (HERE / 'seam.json').write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8', newline='\n')
    for k, v in out.items(): print('%-26s max jump %6.2f at x %d (box edge %6.2f)  median %5.2f' % (k, v['max_jump'], v['at_x'], v['jump_at_box_edge'], v['median_jump']))


if __name__ == '__main__':
    {'run': run, 'seam': seam}[sys.argv[1]]()
