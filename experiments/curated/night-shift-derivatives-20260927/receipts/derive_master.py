# As-run script (27 Sep 2026), kept as a receipt; hardcodes this machine's local paths and is not a portable reproduction.
import json, os, hashlib
from PIL import Image
O = 'C:/AI/ComfyUI_windows_portable/ComfyUI/output/'
PK = O + 'Research/nightshift-20260927/'
runs = {json.loads(l)['key']: json.loads(l) for l in open('runs.jsonl')}
src = {'MA': runs['master-up-u2-raw4x']['outputs'][0]['path'], 'MB': runs['master-up-u1-studio2x']['outputs'][0]['path']}
os.makedirs(PK + 'retro-anime-master/master', exist_ok=True); os.makedirs(PK + 'retro-anime-master/review', exist_ok=True)
out = {}
for k, p in src.items():
    im = Image.open(p).convert('RGB'); w, h = im.size
    r = im.resize((3840, round(h * 3840 / w)), Image.LANCZOS); H = r.size[1]; top = (H - 2160) // 2
    c = r.crop((0, top, 3840, top + 2160))
    dst = PK + 'retro-anime-master/master/retro-anime-master--3840x2160--%s.png' % k.lower()
    c.save(dst, optimize=True)
    out[k] = {'source': p, 'source_size': [w, h], 'resize_to': [3840, H], 'filter': 'PIL LANCZOS', 'crop_box': [0, top, 3840, top + 2160],
              'crop_box_anchor_px': [0, round(top * 768 / H, 2), 1344, round((top + 2160) * 768 / H, 2)], 'file': dst,
              'sha256': hashlib.sha256(open(dst, 'rb').read()).hexdigest(), 'bytes': os.path.getsize(dst)}
    # 1:1 detail crops for review: CRT+lamp, train window, left wall
    for name, box in {'crt': (2550, 1000, 3150, 1500), 'train': (2750, 250, 3550, 800), 'wall': (400, 600, 1000, 1100)}.items():
        c.crop(box).save(PK + 'retro-anime-master/review/%s-%s-1to1.png' % (k.lower(), name))
json.dump(out, open('master-derive.json', 'w'), indent=1); print(json.dumps(out, indent=1))
