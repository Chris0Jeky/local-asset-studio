"""Does the depth Combine lose the face because the character picture is a portrait? (23 September 2026, overnight lab)

    python combine_scale.py stage   # upload the pack's full-body render as the character picture
    python combine_scale.py run     # 3 Studio jobs: combine-klein-9b-depth, full-body character, the same pose picture and seeds

Hypothesis from ../combine-adult (PR #875): `combine-klein-9b-depth` drew a blank or dark featureless face on seeds 41 and 43
when the character picture was the pack's three-quarter PORTRAIT and the target a full body. If the scale gap is the cause, the
same route, pose picture, wording and seeds with the pack's FULL-BODY render (`Studio/Anima-v1-Baseline_00005_.png`: the same
adult traveller, lantern at her side) as the character picture should keep the face on all three seeds.
"""
import json, re, sys, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import labkit  # noqa: E402

CHARACTER = labkit.OUTPUT / 'Studio' / 'Anima-v1-Baseline_00005_.png'
POSE_FILE = 'b72d60be4bd64fbfa6574d550808d0e8_adult-stance-pose.png.png'  # staged by ../combine-adult (pose-source-v2-2026092346)
SEEDS = [2026092341, 2026092342, 2026092343]
WHO = 'an adult woman traveller with long dark hair parted in the centre, brown eyes and gold earrings'
CLOTHES = 'a navy double-breasted coat with brass buttons, a teal scarf, dark trousers and brown lace-up boots'
POSE = ('standing in a wide stance facing the viewer, knees slightly bent, right arm extended forward with an open palm, left arm raised '
        'overhead, as if casting a spell')
STAGE = HERE / 'stage.json'


def stage():
    req = urllib.request.Request(labkit.STUDIO + '/api/upload', CHARACTER.read_bytes(),
                                 {'Content-Type': 'image/png', 'X-Filename': 'adult-traveller-fullbody.png', 'Origin': labkit.STUDIO})
    with urllib.request.urlopen(req, timeout=120) as reply: up = json.load(reply)
    STAGE.write_text(json.dumps({'character': up, 'character_source': str(CHARACTER), 'pose_file': POSE_FILE}, indent=1) + '\n',
                     encoding='utf-8', newline='\n')
    print(up)


def fill(template):
    def repl(m):
        text = m.group(0).lower()
        if 'clothes' in text: return CLOTHES
        if 'who is' in text: return WHO
        if 'pose' in text: return POSE
        raise SystemExit('unknown placeholder ' + m.group(0))
    return re.sub(r'\[[^\]]+\]', repl, template)


def run():
    staged = json.loads(STAGE.read_text(encoding='utf-8')); results = labkit.Results(HERE)
    with urllib.request.urlopen(labkit.STUDIO + '/api/catalog', timeout=60) as reply: catalog = json.load(reply)
    preset = next(p for p in catalog['presets'] if p['id'] == 'combine-klein-9b-depth')
    positive = fill(preset['continuation_prompt'])
    for seed in SEEDS:
        controls = {'positive': positive, 'last_reference': staged['character']['file'], 'seed': seed}
        intent = {'preset_id': 'combine-klein-9b-depth', 'controls': controls, 'batch_count': 1,
                  'references': [{'file': POSE_FILE, 'role': 'pose'}], 'parent_assets': []}
        labkit.run_studio(intent, 'depth-fullbody-%d' % seed, results, timeout=1800, extra={'config': 'depth-fullbody-character', 'seed': seed})


if __name__ == '__main__':
    {'stage': stage, 'run': run}[sys.argv[1]]()
