"""Style + Pose re-proof for the fantasy pack (23 September 2026, overnight lab; review judge request, PR #866).

    python stylepose_pack.py stage     # upload the two pose pictures (the board picture is already staged by ../combine-adult)
    python stylepose_pack.py run       # 18 Studio jobs: 2 poses x pose strength 0.7/0.9/1.0 x 3 seeds, one at a time

`style-pose-wai` (WAI v17 + IP-Adapter style board + OpenPose ControlNet from a pose picture) with the pack's own adult original:
- style board: the pack's look-B three-quarter portrait (`Studio/Anima-v1-Baseline_00004_.png`), one picture;
- standing pose: the pack's full-body render (`Studio/Anima-v1-Baseline_00005_.png`, lantern at her side);
- action pose: the new adult stance picture from ../combine-adult (`pose-source-v2-2026092346`, one arm up, wide stance);
- pose strength 0.7, 0.9 (authored) and 1.0; style weight at the preset default; seeds 2026092371-73.
The positive prompt describes the pack's character in WAI tags. Images stay out of Git except original-character sheets.
"""
import json, sys, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import labkit  # noqa: E402

BOARD_FILE = '906acc81e98f4de399cf0d0c8b6fdd44_adult-traveller-portrait.png.png'  # staged by ../combine-adult stage
POSES = {'standing': labkit.OUTPUT / 'Studio' / 'Anima-v1-Baseline_00005_.png',
         'action': labkit.OUTPUT / 'Research' / 'overnight-20260923' / 'combine-adult' / 'pose-source-v2-2026092346_00001_.png'}
POSITIVE = ('1girl, solo, adult woman, mature female, original character, long dark hair, centre part, brown eyes, gold earrings, '
            'navy double-breasted coat, brass buttons, teal scarf, dark trousers, brown lace-up boots, full body, simple background, '
            'masterpiece, best quality, amazing quality')
NEGATIVE = ('bad quality, worst quality, worst detail, sketch, censor, bad anatomy, bad hands, extra digits, missing fingers, '
            'nsfw, nude, underwear, loli, child, young, teenage')
STRENGTHS = [0.7, 0.9, 1.0]
SEEDS = [2026092371, 2026092372, 2026092373]
STAGE = HERE / 'stage.json'


def upload(path, name):
    req = urllib.request.Request(labkit.STUDIO + '/api/upload', Path(path).read_bytes(),
                                 {'Content-Type': 'image/png', 'X-Filename': name, 'Origin': labkit.STUDIO})
    with urllib.request.urlopen(req, timeout=120) as reply: return json.load(reply)


def stage():
    staged = {'board': BOARD_FILE}
    for name, path in POSES.items(): staged[name] = upload(path, 'pack-%s-pose.png' % name)['file']
    STAGE.write_text(json.dumps(staged, indent=1) + '\n', encoding='utf-8', newline='\n'); print(staged)


def run():
    staged = json.loads(STAGE.read_text(encoding='utf-8')); results = labkit.Results(HERE)
    for pose in POSES:
        for strength in STRENGTHS:
            for seed in SEEDS:
                controls = {'positive': POSITIVE, 'negative': NEGATIVE, 'seed': seed, 'pose_strength': strength, 'last_reference': staged[pose]}
                intent = {'preset_id': 'style-pose-wai', 'controls': controls, 'batch_count': 1,
                          'references': [{'file': staged['board'], 'role': 'style'}], 'parent_assets': []}
                labkit.run_studio(intent, '%s-p%s-%d' % (pose, str(strength).replace('.', ''), seed), results, timeout=1200,
                                  extra={'config': '%s-p%s' % (pose, strength), 'pose': pose, 'pose_strength': strength, 'seed': seed})


def weights():
    """Follow-up: the action pose at pose strength 0.9 (the authored value) with style weight 0.3, 0.45 and the default 0.7
    already measured above, on the same three seeds, to find a weight that keeps the board's palette without the burn."""
    staged = json.loads(STAGE.read_text(encoding='utf-8')); results = labkit.Results(HERE)
    for weight in (0.3, 0.45):
        for seed in SEEDS:
            controls = {'positive': POSITIVE, 'negative': NEGATIVE, 'seed': seed, 'pose_strength': 0.9, 'style_weight': weight,
                        'last_reference': staged['action']}
            intent = {'preset_id': 'style-pose-wai', 'controls': controls, 'batch_count': 1,
                      'references': [{'file': staged['board'], 'role': 'style'}], 'parent_assets': []}
            labkit.run_studio(intent, 'action-p09-w%s-%d' % (str(weight).replace('.', ''), seed), results, timeout=1200,
                              extra={'config': 'action-p0.9-w%s' % weight, 'pose': 'action', 'pose_strength': 0.9, 'style_weight': weight, 'seed': seed})


if __name__ == '__main__':
    {'stage': stage, 'run': run, 'weights': weights}[sys.argv[1]]()
