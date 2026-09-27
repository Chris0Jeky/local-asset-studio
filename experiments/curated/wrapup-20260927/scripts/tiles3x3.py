# As-run script (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
import json, urllib.request, os
from PIL import Image, ImageDraw
W = 'C:/Users/jekyt/source/local-asset-studio/experiments/workspace/'
A = {a['id']: a for a in json.load(urllib.request.urlopen('http://127.0.0.1:8191/api/workspace'))['assets']}
fix = lambda p: os.path.join(W, *p.replace(chr(92), '/').split('/'))
out = {}
for label, (tile, prev) in {'wall': ('67c808bd810c5559830be7f1bbf8df12', '0f4e49192415521d8b161119eecd5c2d'), 'floor': ('84eb33a810a15d2fb2dce3c0a26ecc44', '9f546d909998565ba01d63860ccae645')}.items():
    t = Image.open(fix(A[tile]['path'])); p = Image.open(fix(A[prev]['path']))
    out[label] = {'tile_asset': tile, 'tile_sha256': A[tile]['sha256'], 'tile_size': t.size, 'preview_asset': prev, 'preview_sha256': A[prev]['sha256'], 'preview_size': p.size}
    p.convert('RGB').resize((768, 768), Image.LANCZOS).save('tile-%s-3x3.jpg' % label, quality=86)
json.dump(out, open('tiles-assets.json', 'w'), indent=1); print(json.dumps(out))
s = Image.new('RGB', (768 * 2 + 10, 768 + 18), 'white'); d = ImageDraw.Draw(s)
for i, l in enumerate(('wall', 'floor')): s.paste(Image.open('tile-%s-3x3.jpg' % l), (i * 778, 18)); d.text((i * 778 + 2, 2), '%s: Studio 3x3 preview (Make seamless)' % l, fill='black')
s.save('tiles-3x3-sheet.jpg', quality=86); s.resize((1036, 527)).save('tiles-3x3-view.jpg', quality=86)
