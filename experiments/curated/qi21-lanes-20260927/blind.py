# As-run script (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
import json, random
from PIL import Image, ImageDraw
Q = 'C:/AI/experiments/qwen-image-21/ComfyUI/output/'
runs = [json.loads(l) for l in open('runs.jsonl')]
runs = [r for r in runs if r.get('status') == 'success']
key = {}
for prompt in ('char', 'prop'):
    rs = [r for r in runs if r['prompt'] == prompt]; random.Random(20260927 * 7 + len(prompt)).shuffle(rs)
    s = Image.new('RGB', (4 * 400 + 30, 2 * 418), 'white'); d = ImageDraw.Draw(s)
    for i, r in enumerate(rs):
        o = r['outputs'][0]; im = Image.open(Q + o['subfolder'].replace(chr(92), '/') + '/' + o['filename']).convert('RGB').resize((400, 400), Image.LANCZOS)
        L = 'ABCDEFGH'[i]; x, y = (i % 4) * 410, (i // 4) * 418; s.paste(im, (x, y + 16)); d.text((x + 2, y + 2), L, fill='black')
        key['%s-%s' % (prompt, L)] = {'key': r['key'], 'file': o['subfolder'].replace(chr(92), '/') + '/' + o['filename']}
    s.save('blind-%s.jpg' % prompt, quality=88)
json.dump(key, open('key.sealed.json', 'w'), indent=1); print(len(key))
