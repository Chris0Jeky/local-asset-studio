# As-run script (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
"""Blind panels: per prompt, the 9 renders shuffled (fixed RNG seed recorded), labelled A-I; the key is written to key.sealed.json
and not read until every judgement is written."""
import json, random
from PIL import Image, ImageDraw
Q = 'C:/AI/experiments/qwen-image-21/ComfyUI/output/'
runs = [json.loads(l) for l in open('runs.jsonl')]
key = {}
for prompt in ('char', 'prop'):
    rs = [r for r in runs if r['prompt'] == prompt]; rng = random.Random(20260927 + len(prompt)); rng.shuffle(rs)
    s = Image.new('RGB', (3 * 512 + 20, 3 * 530), 'white'); d = ImageDraw.Draw(s)
    for i, r in enumerate(rs):
        o = r['outputs'][0]; im = Image.open(Q + o['subfolder'] + '/' + o['filename']).convert('RGB').resize((512, 512), Image.LANCZOS)
        L = 'ABCDEFGHI'[i]; x, y = (i % 3) * 522, (i // 3) * 530; s.paste(im, (x, y + 16)); d.text((x + 2, y + 2), L, fill='black')
        key['%s-%s' % (prompt, L)] = {'key': r['key'], 'file': o['subfolder'] + '/' + o['filename']}
    s.save('blind-%s.jpg' % prompt, quality=88)
json.dump(key, open('key.sealed.json', 'w'), indent=1)
json.dump({k: v['file'] for k, v in key.items()}, open('files-by-label.json', 'w'), indent=1)   # file names carry the condition: used only for crops by label below
