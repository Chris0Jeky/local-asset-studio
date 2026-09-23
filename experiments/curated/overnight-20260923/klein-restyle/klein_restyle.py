"""Klein restyle of the throne witch: two wording hypotheses from the q-27 pre-review (23 September 2026, overnight lab).

    python klein_restyle.py run      # 9 Studio jobs (restyle-klein), one at a time
    python klein_restyle.py seal     # blind copies per seed + key.sealed.json
    python klein_restyle.py split    # the confound split test (6 jobs to split/): written, NOT run (lab paused 23 Sep 2026)
    python klein_restyle.py seal-split

The q-27 pre-review (PR #862) found two repeat faults in every Klein restyle of `Style-Pose/Nova_00004_.png` (the owner ruled
on 23 September 2026 that she is an adult original): the raised leg's foot comes out as a toe-less stocking tip, and the shipped
source description ("long dark hair", the source's prompt) turned her purple hair black and her blue eye violet. This run uses
the shipped job's exact controls (job db25b173: 1040x1520, 6 steps, cfg 1, the same staged reference) and changes only the
source description at the end of the prompt:
- `shipped`: as submitted in job db25b173;
- `colours-barefoot`: "long purple hair, blue eyes" instead of "long dark hair", plus "bare feet" (the review's request);
- `colours-stocking`: the same colours, plus the stocking the source actually shows ("a beige thigh-high stocking on the raised
  leg, the other leg bare"), to separate "name what is there" from "ask for bare feet".
Three seeds each (the shipped seed 2026091401 and two new ones). Images stay out of Git (pin-up framing): ComfyUI
output/Restyle/ plus a local index.html under output/Research/overnight-20260923/klein-restyle/.
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import labkit  # noqa: E402

REFERENCE = '573ec938e3c7402ca1ef0187f19cc41a_Nova_00004_.png.png'
FINISH = ('Redraw this image as a polished light-novel illustration: soft but rich colours, bright high-key lighting with gentle bloom, '
          'a light airy background, delicate clean lineart, smooth soft shading, glossy hair, large detailed sparkling eyes. Keep the '
          'character, the pose, the face and expression, the hair colour, the clothing and its colours, the props and the background '
          'layout exactly as they are; only change the rendering style. The picture shows: ')
SHIPPED = ('1girl, solo, adult woman, original character, witch, wide-brimmed witch hat, long dark hair, red and black robe with gold '
           'trim, full body, sitting on an ornate throne, one knee raised, leaning back, one eye closed, smiling, looking at viewer, '
           'from below, masterpiece, best quality, amazing quality.')
WORDINGS = {
    'shipped': SHIPPED,
    'colours-barefoot': SHIPPED.replace('long dark hair', 'long purple hair, blue eyes').replace('one knee raised,', 'one knee raised, bare feet,'),
    'colours-stocking': SHIPPED.replace('long dark hair', 'long purple hair, blue eyes').replace(
        'one knee raised,', 'one knee raised, a beige thigh-high stocking on the raised leg, the other leg bare,'),
}
SEEDS = [2026091401, 2026092351, 2026092352]


def run():
    results = labkit.Results(HERE)
    for seed in SEEDS:
        for name, text in WORDINGS.items():
            controls = {'positive': FINISH + text, 'seed': seed, 'steps': 6, 'cfg': 1, 'width': 1040, 'height': 1520, 'reference': REFERENCE}
            intent = {'preset_id': 'restyle-klein', 'controls': controls, 'batch_count': 1, 'references': [], 'parent_assets': []}
            labkit.run_studio(intent, '%s-%d' % (name, seed), results, timeout=1200, extra={'config': name, 'seed': seed})


SPLIT = {
    'colours-only': SHIPPED.replace('long dark hair', 'long purple hair, blue eyes'),
    'foot-only': SHIPPED.replace('one knee raised,', 'one knee raised, bare feet,'),
}


def split():
    """Split test for the confound in the first run (#883 review): colours only, and footwear only, on the same three seeds.
    Results go to split/ so the judged first key stays untouched."""
    results = labkit.Results(HERE / 'split')
    for seed in SEEDS:
        for name, text in SPLIT.items():
            controls = {'positive': FINISH + text, 'seed': seed, 'steps': 6, 'cfg': 1, 'width': 1040, 'height': 1520, 'reference': REFERENCE}
            intent = {'preset_id': 'restyle-klein', 'controls': controls, 'batch_count': 1, 'references': [], 'parent_assets': []}
            labkit.run_studio(intent, '%s-%d' % (name, seed), results, timeout=1200, extra={'config': name, 'seed': seed})


def seal_split():
    results = labkit.Results(HERE / 'split')
    items = [{'group': 's%d' % (SEEDS.index(r['seed']) + 1), 'config': r['config'], 'file': r['output_files'][0]['file']}
             for r in results.records if r.get('status') == 'completed' and r.get('output_files')]
    print(labkit.seal(items, HERE / 'split'))


def seal():
    results = labkit.Results(HERE)
    items = [{'group': 's%d' % (SEEDS.index(r['seed']) + 1), 'config': r['config'], 'file': r['output_files'][0]['file']}
             for r in results.records if r.get('status') == 'completed' and r.get('output_files')]
    print(labkit.seal(items, HERE))


if __name__ == '__main__':
    {'run': run, 'seal': seal, 'split': split, 'seal-split': seal_split}[sys.argv[1]]()
