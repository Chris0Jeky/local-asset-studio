"""Re-prove the four lead Combine routes on an adult original pair (23 September 2026, overnight lab; review judge request, PR #862).

    python combine_adult.py pose-source        # one WAI render of an adult original figure in a dynamic lunge (the pose picture)
    python combine_adult.py stage              # upload the character + pose picture to the Studio, draw the skeleton guide
    python combine_adult.py run [route ...]    # Studio jobs (POST /api/jobs): 4 routes x 3 seeds, one at a time
    python combine_adult.py seal               # blind copies per route-seed group are not useful here; see README (open judging)

Every earlier proof of these routes used the owner's imported fan pictures of Ellen Joe, which are now excluded as inputs. This run
uses only original adult characters: the character is the fantasy pack's three-quarter portrait (Anima v1 look B,
`Studio/Anima-v1-Baseline_00004_.png`: an adult traveller in a navy double-breasted coat, teal scarf, long dark hair, gold earrings);
the pose picture is a fresh WAI render of an adult woman in plain clothes in a side-view fencing lunge on white; the skeleton is
drawn from that render's joints through the pose editor's own endpoint (POST /api/pose/render). Routes, each through the Studio so
the runs double as preset proofs:
- `combine-klein-9b-depth` (pose picture read as a depth map), depth_cut 100 (default);
- `combine-klein-9b-depth` with depth_cut 88 ("cut below the ankles", the review asked for 86-92);
- `combine-klein-9b-copypose` (Copy Pose LoRA; character picture first);
- `combine-klein-9b-skeleton` (drawn stick figure).
"""
import json, re, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import labkit  # noqa: E402

CHARACTER = labkit.OUTPUT / 'Studio' / 'Anima-v1-Baseline_00004_.png'
SEEDS = [2026092341, 2026092342, 2026092343]
WHO = 'an adult woman traveller with long dark hair parted in the centre, brown eyes and gold earrings'
CLOTHES = 'a navy double-breasted coat with brass buttons, a teal scarf, dark trousers and brown lace-up boots'
POSE = ('standing in a wide stance facing the viewer, knees slightly bent, right arm extended forward with an open palm, left arm raised overhead, as if casting a spell')
POSE_PROMPT = ('1girl, solo, adult woman, mature female, original character, plain black long-sleeved shirt, black trousers, black shoes, '
               'fencing lunge, lunging forward, front knee bent, back leg straight, right arm extended forward, open hand, left arm swept back, '
               'from side, full body, simple background, white background, masterpiece, best quality')
ROUTES = {
    'depth': ('combine-klein-9b-depth', {}),
    'depth-cut88': ('combine-klein-9b-depth', {'depth_cut': 88}),
    'copypose': ('combine-klein-9b-copypose', {}),
    'skeleton': ('combine-klein-9b-skeleton', {}),
}
STAGE = HERE / 'stage.json'


def studio(path, body=None, raw=None, headers=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    h = {'Content-Type': 'application/json', 'Origin': labkit.STUDIO}; h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(labkit.STUDIO + path, data, h), timeout=120) as reply: return json.load(reply)


# v1 (seed 2026092340, the side-view lunge wording) came out as a bent-over rear view with the hips as the focus: rejected as a
# pose source (suggestive framing, and not the briefed pose). v2 asks for a front-view spellcasting stance instead.
POSE_PROMPT_V2 = ('1girl, solo, adult woman, mature female, original character, plain black long-sleeved shirt, black trousers, black shoes, '
                  'full body, front view, facing viewer, wide stance, legs apart, knees slightly bent, right arm extended forward, open palm, '
                  'left arm raised overhead, dynamic pose, action pose, simple background, white background, masterpiece, best quality')
POSE_NEG = ('bad quality, worst quality, worst detail, sketch, censor, bad anatomy, bad hands, extra digits, nsfw, nude, underwear, '
            'loli, child, young, teenage, weapon, background clutter, from behind, ass focus, bent over')


def pose_source(version='v1', seeds=(2026092340,)):
    g0 = labkit.prune_loras(json.loads((labkit.REPO / 'workflows/api/wai-api.json').read_text(encoding='utf-8')))
    for seed in seeds:
        g = json.loads(json.dumps(g0)); label = 'pose-source' if version == 'v1' else 'pose-source-v2-%d' % seed
        g['2']['inputs']['text'] = POSE_PROMPT if version == 'v1' else POSE_PROMPT_V2
        g['3']['inputs']['text'] = POSE_NEG
        g['5']['inputs']['seed'] = seed
        g['7']['inputs']['filename_prefix'] = 'Research/overnight-20260923/combine-adult/' + label
        labkit.run_graph(g, label, labkit.Results(HERE), timeout=900, extra={'config': 'pose-source-' + version, 'seed': seed})


def stage(pose_label, keypoints_file):
    results = labkit.Results(HERE); pose = Path(results.find(pose_label)['outputs'][0]['file'])
    char = studio('/api/upload', raw=CHARACTER.read_bytes(), headers={'Content-Type': 'image/png', 'X-Filename': 'adult-traveller-portrait.png'})
    pic = studio('/api/upload', raw=pose.read_bytes(), headers={'Content-Type': 'image/png', 'X-Filename': 'adult-stance-pose.png'})
    kp = json.loads(Path(keypoints_file).read_text(encoding='utf-8'))
    guide = studio('/api/pose/render', {'width': kp['width'], 'height': kp['height'], 'keypoints': kp['keypoints']})
    assert guide.get('generation_submitted') is False, guide
    STAGE.write_text(json.dumps({'character': char, 'pose_picture': pic, 'skeleton': guide, 'keypoints': kp,
                                 'character_source': str(CHARACTER), 'pose_source': str(pose)}, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'character': char.get('file'), 'pose': pic.get('file'), 'skeleton': guide.get('file'), 'renderer': guide.get('renderer')}))


def fill(template):
    def repl(m):
        text = m.group(0).lower()
        if 'clothes' in text: return CLOTHES
        if 'who is' in text: return WHO
        if 'pose' in text: return POSE
        raise SystemExit('unknown placeholder ' + m.group(0))
    return re.sub(r'\[[^\]]+\]', repl, template)


def run(names):
    staged = json.loads(STAGE.read_text(encoding='utf-8')); results = labkit.Results(HERE)
    catalog = dict((p['id'], p) for p in studio('/api/catalog')['presets'])
    for name in names or list(ROUTES):
        preset_id, extra_controls = ROUTES[name]; preset = catalog[preset_id]
        positive = fill(preset['continuation_prompt'])
        pose_file = staged['skeleton']['file'] if name == 'skeleton' else staged['pose_picture']['file']
        for seed in SEEDS:
            controls = {'positive': positive, 'last_reference': staged['character']['file'], 'seed': seed}; controls.update(extra_controls)
            intent = {'preset_id': preset_id, 'controls': controls, 'batch_count': 1, 'references': [{'file': pose_file, 'role': 'pose'}], 'parent_assets': []}
            labkit.run_studio(intent, '%s-%d' % (name, seed), results, timeout=1800, extra={'config': name, 'seed': seed, 'preset_id': preset_id})


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'pose-source': pose_source()
    elif cmd == 'pose-source-v2': pose_source('v2', (2026092344, 2026092345, 2026092346))
    elif cmd == 'stage': stage(sys.argv[2], sys.argv[3])
    elif cmd == 'run': run(sys.argv[2:])
