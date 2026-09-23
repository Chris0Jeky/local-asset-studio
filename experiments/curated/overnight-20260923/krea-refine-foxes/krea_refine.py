"""krea-refine on the fox shrine with the shrine's own prompt (23 September 2026, overnight lab; review judge request, PR #866).

    python krea_refine.py stage    # upload Studio/krea-style-lab_00001_.png (the fox shrine the owner said lost detail, morphed fox faces)
    python krea_refine.py run      # 6 Studio jobs: denoise 0.25 and 0.35 x 3 seeds

The recorded krea-refine proof (job 21e4a629) ran the preset's authored witch prompt over the shrine. Here the positive is the
shrine's own prompt from krea-style-lab (the recipe that made it), and everything else is the shipped krea-refine
(TextFusion + Niji Sweet Spot + the 4-step distill LoRA at 0.85, 4 steps euler/simple, cfg 1). Judge: fox count and fox faces
against the source, and whether the airy watercolour look survives. Original content only (foxes, a shrine): Git-safe.
"""
import json, sys, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import labkit  # noqa: E402

SOURCE = labkit.OUTPUT / 'Studio' / 'krea-style-lab_00001_.png'
POSITIVE = 'a fox spirit shrine on a cliff at dawn, paper lanterns and drifting petals, soft mist over the valley, airy anime watercolor style'
DENOISE = [0.25, 0.35]
SEEDS = [2026092381, 2026092382, 2026092383]
STAGE = HERE / 'stage.json'


def stage():
    req = urllib.request.Request(labkit.STUDIO + '/api/upload', SOURCE.read_bytes(),
                                 {'Content-Type': 'image/png', 'X-Filename': 'fox-shrine-source.png', 'Origin': labkit.STUDIO})
    with urllib.request.urlopen(req, timeout=120) as reply: up = json.load(reply)
    STAGE.write_text(json.dumps({'upload': up, 'source': str(SOURCE), 'source_sha256': labkit.file_sha(SOURCE)}, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(up)


def run():
    staged = json.loads(STAGE.read_text(encoding='utf-8')); results = labkit.Results(HERE)
    for denoise in DENOISE:
        for seed in SEEDS:
            controls = {'positive': POSITIVE, 'seed': seed, 'denoise': denoise, 'reference': staged['upload']['file']}
            intent = {'preset_id': 'krea-refine', 'controls': controls, 'batch_count': 1, 'references': [], 'parent_assets': []}
            labkit.run_studio(intent, 'd%s-%d' % (str(denoise).replace('.', ''), seed), results, timeout=1800, extra={'config': 'denoise-%s' % denoise, 'seed': seed})


def seal():
    """Blind groups per seed: the source picture plus its two refines (denoise 0.25 and 0.35), shuffled."""
    results = labkit.Results(HERE)
    items = [{'group': 's%d' % (SEEDS.index(r['seed']) + 1), 'config': r['config'], 'file': r['output_files'][0]['file']}
             for r in results.records if r.get('status') == 'completed' and r.get('output_files')]
    for i in range(len(SEEDS)): items.append({'group': 's%d' % (i + 1), 'config': 'source', 'file': str(SOURCE)})
    print(labkit.seal(items, HERE))


if __name__ == '__main__':
    {'stage': stage, 'run': run, 'seal': seal}[sys.argv[1]]()
