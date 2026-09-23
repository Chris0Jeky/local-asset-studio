"""Masked hand inpaint on the six-digit NoobAI hand (23 September 2026, overnight lab; review judge request, PR #866).

    python hand_inpaint.py stage     # upload the RGBA source (hand region transparent) to the Studio
    python hand_inpaint.py run       # 15 Studio jobs: 5 settings x 3 seeds, one at a time
    python hand_inpaint.py seal      # blind copies (original + 5 settings per seed) + key.sealed.json

Question: none of the three recorded detail-fix passes fixed its target (PR #866). Does a masked repaint give five clean
fingers on `Studio/noob_00004_.png` (the NoobAI elf portrait, job 14caa4fb; thumb plus five fingers on the raised hand)
without damaging the style? The mask is a rounded box tight on that hand (12,535)-(180,792) of 832x1216, made by this
script's `stage` step from the original pixels (alpha 0 = repaint). Routes, both through the Studio (they double as proofs):
- `anime-masked-repair` (WAI v17, plain SetLatentNoiseMask) at its authored denoise 0.4 and at 0.6;
- `sdxl-inpaint-fix` (WAI v17 + Fooocus inpaint patch) at 0.5 (Gentle), 0.7 (authored) and 1.0 (Redraw).
Both presets' positive is set to the same hand wording plus a description of this picture (the masked-repair default positive
describes a different character). Seeds 2026092361-63.
"""
import json, sys, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import labkit  # noqa: E402

SOURCE = labkit.OUTPUT / 'Studio' / 'noob_00004_.png'
BOX = (12, 535, 180, 792)
POSITIVE = ('masterpiece, best quality, amazing quality, detailed hand, five fingers, natural hand pose, slender fingers, '
            'clean painterly shading, same colours, seamless with the surrounding art, 1girl, adult woman, elf, white hair, white robe, '
            'raised hand, warm rim light, dark background')
NEGATIVE = ('bad quality, worst quality, worst detail, sketch, censor, bad hands, extra digits, fewer digits, missing fingers, '
            'extra fingers, six fingers, fused fingers, deformed hands, blurry, text, watermark')
SETTINGS = {'masked-0.4': ('anime-masked-repair', 0.4), 'masked-0.6': ('anime-masked-repair', 0.6),
            'fooocus-0.5': ('sdxl-inpaint-fix', 0.5), 'fooocus-0.7': ('sdxl-inpaint-fix', 0.7), 'fooocus-1.0': ('sdxl-inpaint-fix', 1.0)}
SEEDS = [2026092361, 2026092362, 2026092363]
STAGE = HERE / 'stage.json'


def stage():
    src = Image.open(SOURCE).convert('RGB'); alpha = Image.new('L', src.size, 255)
    ImageDraw.Draw(alpha).rounded_rectangle(BOX, radius=45, fill=0)
    rgba = src.copy(); rgba.putalpha(alpha)
    tmp = labkit.REPO / '.runtime' / 'lab-scratch' / 'noob4-hand-mask.png'; rgba.save(tmp)
    req = urllib.request.Request(labkit.STUDIO + '/api/upload', tmp.read_bytes(),
                                 {'Content-Type': 'image/png', 'X-Filename': 'noob4-hand-mask.png', 'Origin': labkit.STUDIO})
    with urllib.request.urlopen(req, timeout=120) as reply: up = json.load(reply)
    STAGE.write_text(json.dumps({'upload': up, 'source': str(SOURCE), 'source_sha256': labkit.file_sha(SOURCE), 'box': BOX}, indent=1) + '\n',
                     encoding='utf-8', newline='\n')
    print(up)


def run():
    staged = json.loads(STAGE.read_text(encoding='utf-8')); results = labkit.Results(HERE)
    for seed in SEEDS:
        for name, (preset, denoise) in SETTINGS.items():
            controls = {'positive': POSITIVE, 'negative': NEGATIVE, 'seed': seed, 'denoise': denoise, 'reference': staged['upload']['file']}
            intent = {'preset_id': preset, 'controls': controls, 'batch_count': 1, 'references': [], 'parent_assets': []}
            labkit.run_studio(intent, '%s-%d' % (name, seed), results, timeout=900, extra={'config': name, 'seed': seed, 'preset_id': preset})


def seal():
    results = labkit.Results(HERE)
    items = [{'group': 's%d' % (SEEDS.index(r['seed']) + 1), 'config': r['config'], 'file': r['output_files'][0]['file']}
             for r in results.records if r.get('status') == 'completed' and r.get('output_files')]
    for i in range(len(SEEDS)): items.append({'group': 's%d' % (i + 1), 'config': 'original', 'file': str(SOURCE)})
    print(labkit.seal(items, HERE))


if __name__ == '__main__':
    {'stage': stage, 'run': run, 'seal': seal}[sys.argv[1]]()
