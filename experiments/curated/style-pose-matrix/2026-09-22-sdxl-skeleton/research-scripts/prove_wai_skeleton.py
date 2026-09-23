"""Proving run for `wai-skeleton` through the Studio's own path (22 September 2026, #761/#445): the guide is drawn by the
pose editor's endpoint (POST /api/pose/render with the preset's own renderer, exactly as *Use this pose* sends it on this
recipe), then one POST /api/jobs (prepare -> worker -> ComfyUI) with that guide on the Pose skeleton slot. One deliberate
submission; the job, prompt ID, time and recipe (GET /api/jobs/<id>/recipe) are written next to this file.

    python prove_wai_skeleton.py [--guide render|upload] [--seed N]

`--guide render` needs a Studio started after this branch's app/pose_guide.py (the endpoint learns the renderer field);
`--guide upload` posts the committed skeleton-action.openpose.png through POST /api/upload instead, which any Studio serving
this branch's catalog and graph accepts (Studio.catalog() re-reads presets/catalog.json on every request).
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDIO = 'http://127.0.0.1:8191'
PRESET = 'wai-skeleton'
RENDERER = 'studio.coco18-openpose-xinsir/v1'


def call(path, body=None, content_type='application/json', headers=None):
    data = body if isinstance(body, bytes) or body is None else json.dumps(body).encode()
    req = urllib.request.Request(STUDIO + path, data, dict({'Content-Type': content_type, 'Origin': STUDIO}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=120) as reply: return json.load(reply)
    except urllib.error.HTTPError as error: raise SystemExit('rejected %s %s %s' % (path, error.code, error.read().decode('utf-8', 'replace')[:1500]))


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--guide', choices=('render', 'upload'), default='render')
    parser.add_argument('--seed', type=int, default=2026092201); args = parser.parse_args()
    catalog = call('/api/catalog'); preset = next((p for p in catalog['presets'] if p['id'] == PRESET), None)
    if preset is None: raise SystemExit(PRESET + ' is not in the running Studio catalog')
    skeletons = json.loads((HERE / 'skeletons.json').read_text(encoding='utf-8'))
    action = skeletons['skeletons']['action']
    width, height = skeletons['canvas']
    if args.guide == 'render':
        guide = call('/api/pose/render', {'width': width, 'height': height, 'keypoints': action['keypoints'], 'renderer': RENDERER})
        assert guide['renderer'] == RENDERER and guide['generation_submitted'] is False, guide
    else:
        data = (HERE.parent / 'skeleton-action.openpose.png').read_bytes()
        guide = call('/api/upload', data, 'image/png', {'X-Filename': 'skeleton-action.openpose.png'})
    # PNG bytes depend on the Pillow/zlib build of the Python running the Studio, so equality is recorded, not required.
    guide['matches_committed_bytes'] = guide['sha256'] == action['files']['openpose']['sha256']
    print('guide', guide['file'], guide['sha256'][:12], 'same bytes as the research skeleton:', guide['matches_committed_bytes'], flush=True)
    intent = {'preset_id': PRESET, 'controls': {'seed': args.seed, 'width': width, 'height': height}, 'batch_count': 1,
              'references': [{'file': guide['file'], 'role': 'pose'}], 'parent_assets': []}
    job = call('/api/jobs', intent); print('job', job.get('id'), job.get('message'), flush=True); started = time.time()
    while time.time() - started < 1800:
        time.sleep(5)
        with urllib.request.urlopen(STUDIO + '/api/jobs/' + job['id'], timeout=30) as reply: state = json.load(reply)
        if state.get('status') in ('completed', 'failed', 'not_submitted', 'uncertain', 'abandoned'): break
    else: raise SystemExit('still running after 30 minutes: inspect job ' + job['id'] + '; do not resubmit')
    result = {k: state.get(k) for k in ('id', 'status', 'preset_id', 'prompt_ids', 'outputs', 'elapsed_seconds', 'error', 'references', 'created_at')}
    result.update(seed=args.seed, guide=guide, guide_source=args.guide)
    (HERE / 'prove_wai_skeleton.json').write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8', newline='\n')
    if state.get('status') == 'completed':
        with urllib.request.urlopen(STUDIO + '/api/jobs/' + job['id'] + '/recipe', timeout=30) as reply: recipe = json.load(reply)
        (HERE / 'prove_wai_skeleton.recipe.json').write_text(json.dumps(recipe, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(result, indent=1)[:2500])
    if state.get('status') != 'completed': sys.exit(1)


if __name__ == '__main__':
    main()
