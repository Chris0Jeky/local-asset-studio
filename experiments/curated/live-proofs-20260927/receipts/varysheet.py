# As-run script (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
import json, sys
from PIL import Image, ImageDraw
O = 'C:/AI/ComfyUI_windows_portable/ComfyUI/output/'
label, parent = sys.argv[1], sys.argv[2]
rows = [('parent', [(parent, 'parent')])]
for s in ('subtle', 'strong'):
    r = json.load(open('%s-%s.json' % (label, s)))
    rows.append(('%s  denoise %s  job %s' % (s, r['graph_denoise'][0], r['job_id'][:8]), [(O + o['subfolder'] + '/' + o['filename'], 'seed %s' % o['seed']) for o in r['outputs']]))
W = 420; im0 = Image.open(rows[0][1][0][0]); H = round(im0.size[1] * W / im0.size[0])
cols = max(len(r[1]) for r in rows)
s = Image.new('RGB', (cols * (W + 8), len(rows) * (H + 36)), 'white'); d = ImageDraw.Draw(s)
for i, (title, items) in enumerate(rows):
    y = i * (H + 36); d.text((2, y + 2), title, fill='black')
    for j, (p, cap) in enumerate(items):
        s.paste(Image.open(p).convert('RGB').resize((W, H), Image.LANCZOS), (j * (W + 8), y + 16)); d.text((j * (W + 8) + 2, y + 18 + H), cap, fill='black')
s.save('vary-%s-sheet.jpg' % label, quality=86); print(s.size)
