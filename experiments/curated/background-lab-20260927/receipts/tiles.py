# As-run script (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
"""Seamless tile lab: roll the texture by half in both axes so the wrap seam becomes a centre cross, then repaint the cross
(Z-Image img2img with SetLatentNoiseMask, the texture's own prompt) and composite only the masked band. Also a naive 3x3 of the
raw texture for comparison. Seam score = mean |difference| across the wrap edges (right vs left column, bottom vs top row)."""
import json, sys
import numpy as np
from PIL import Image, ImageFilter
sys.path.insert(0, 'C:/Users/jekyt/AppData/Local/Temp/bglab'); import comfy
H = 'C:/Users/jekyt/AppData/Local/Temp/bglab/'
ZG = json.load(open('C:/Users/jekyt/Desktop/Printer Config/Others/Git/local-asset-studio/workflows/api/zimage-fast-api.json', encoding='utf-8'))
def seam(a):
    a = a.astype(np.float32); return round(float((np.abs(a[:, -1] - a[:, 0]).mean() + np.abs(a[-1] - a[0]).mean()) / 2), 2)
def inner(a):
    a = a.astype(np.float32); return round(float((np.abs(a[:, 1:] - a[:, :-1]).mean() + np.abs(a[1:] - a[:-1]).mean()) / 2), 2)
def grid(a, name):
    t = Image.fromarray(a).resize((341, 341), Image.LANCZOS); g = Image.new('RGB', (1023, 1023))
    for i in range(3):
        for j in range(3): g.paste(t, (i * 341, j * 341))
    g.save(H + name, quality=88) if name.endswith('.jpg') else g.save(H + name)
def run(key, src, prompt, band=112, denoise=0.8, seed=2026092779):
    a = np.asarray(Image.open(src).convert('RGB')); n = a.shape[0]
    r = np.roll(np.roll(a, n // 2, 0), n // 2, 1)
    m = np.zeros(a.shape[:2], bool); c = n // 2; m[:, c - band // 2:c + band // 2] = True; m[c - band // 2:c + band // 2, :] = True
    soft = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(12)), np.float32) / 255
    name = 'bglab-%s-rolled.png' % key; Image.fromarray(np.dstack([r, np.where(m, 0, 255).astype(np.uint8)]), 'RGBA').save(comfy.INP + name)
    g = json.loads(json.dumps(ZG)); g['4']['inputs']['text'] = prompt; del g['7']
    g['11'] = {'class_type': 'LoadImage', 'inputs': {'image': name}}
    g['12'] = {'class_type': 'VAEEncode', 'inputs': {'pixels': ['11', 0], 'vae': ['3', 0]}}
    g['13'] = {'class_type': 'SetLatentNoiseMask', 'inputs': {'samples': ['12', 0], 'mask': ['11', 1]}}
    g['8']['inputs'].update(latent_image=['13', 0], denoise=denoise, seed=seed); g['10']['inputs']['filename_prefix'] = 'Research/bglab-20260927/tiles/' + key
    rec = comfy.run(key, g, 'seam repaint, band %d px, denoise %s' % (band, denoise))
    out = np.asarray(Image.open(rec['outputs'][0]).convert('RGB'), np.float32)
    res = (r * (1 - soft[..., None]) + out * soft[..., None]).clip(0, 255).astype(np.uint8)
    dst = comfy.OUT + 'Research/bglab-20260927/tiles/%s-tile.png' % key; Image.fromarray(res).save(dst)
    grid(a, '%s-raw-3x3.jpg' % key); grid(res, '%s-tile-3x3.jpg' % key)
    return {'key': key, 'source': src, 'band_px': band, 'denoise': denoise, 'prompt_id': rec['prompt_id'], 'exec_s': rec['exec_s'], 'tile': dst,
            'seam_raw': seam(a), 'seam_tile': seam(res), 'inner_gradient_raw': inner(a), 'inner_gradient_tile': inner(res)}
if __name__ == '__main__':
    res = [run('floor', comfy.OUT + 'Studio/Z-Image-Fast_00020_.png', 'Seamless texture, top-down view of dark worn wooden floorboards, hand-painted cel anime film background art, muted graphite and brown palette with faint cyan reflections, even soft lighting, no objects, no text, fills the whole frame.'),
           run('wall', comfy.OUT + 'Studio/Z-Image-Fast_00021_.png', 'Seamless texture, flat front view of a dark graphite plaster wall with subtle hand-painted brush texture and faint water stains, hand-painted cel anime film background art, even soft lighting, no objects, no text, fills the whole frame.')]
    json.dump(res, open(H + 'tiles.json', 'w'), indent=1); print(json.dumps(res, indent=1))
