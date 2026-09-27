# As-run script (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
import json, sys
from PIL import Image, ImageDraw
Q = 'C:/AI/experiments/qwen-image-21/ComfyUI/output/'
k = json.load(open('key.sealed.json'))
prompt = sys.argv[1]; specs = sys.argv[2:]   # L:x0,y0,x1,y1
cells = []
for sp in specs:
    L, b = sp.split(':'); box = tuple(int(v) for v in b.split(','))
    im = Image.open(Q + k['%s-%s' % (prompt, L)]['file']).convert('RGB').crop(box); im = im.resize((300, round(im.size[1] * 300 / im.size[0])))
    cells.append((L + ' ' + b, im))
H = max(c[1].size[1] for c in cells) + 14
s = Image.new('RGB', (len(cells) * 306, H), 'white'); d = ImageDraw.Draw(s)
for i, (n, im) in enumerate(cells): s.paste(im, (i * 306, 14)); d.text((i * 306 + 2, 1), n, fill='black')
s.save('crops-%s-%d.jpg' % (prompt, abs(hash(' '.join(specs))) % 1000), quality=90); print('ok', s.size)
