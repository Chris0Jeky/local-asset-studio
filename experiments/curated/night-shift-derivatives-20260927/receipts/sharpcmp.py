# As-run script (27 Sep 2026), kept as a receipt; hardcodes this machine's local paths and is not a portable reproduction.
import sys, json
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import ns, registration as R
PK = ns.OUTROOT + 'Research/nightshift-20260927/retro-anime-master/'
MA = PK + 'master/retro-anime-master--3840x2160--ma.png'
keys = sys.argv[1:]
ims = [('MA (accepted)', Image.open(MA).convert('RGB'))] + [(k, Image.open(PK + 'candidates/retro-anime-master--3840x2160--%s.png' % k).convert('RGB')) for k in keys]
boxes = {'wall 400,600': (400, 600, 900, 1000), 'window/train 2750,380': (2750, 380, 3250, 780), 'monitor+lamp 2500,1050': (2500, 1050, 3000, 1450), 'desk/chair 2000,1500': (1900, 1450, 2400, 1850)}
W = 500; H = 400
s = Image.new('RGB', (len(ims) * (W + 8), len(boxes) * (H + 16) + 16), 'white'); d = ImageDraw.Draw(s)
for i, (n, im) in enumerate(ims): d.text((i * (W + 8) + 3, 2), n, fill='black')
for r, (bn, b) in enumerate(boxes.items()):
    for i, (n, im) in enumerate(ims):
        s.paste(im.crop(b), (i * (W + 8), 16 + r * (H + 16))); d.text((i * (W + 8) + 3, 16 + r * (H + 16) + H + 1), bn + ' (1:1)', fill='black')
out = 'sharp-compare-%s.jpg' % '-'.join(keys); s.save(out, quality=90); print(out, s.size)
# registration vs MA (edges at 1344x756) and a sharpness figure
def e(im): return np.asarray(im.convert('L').resize((1344, 756), Image.LANCZOS).filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(1.5)), np.float64)
A = e(ims[0][1])
for n, im in ims:
    lap = np.asarray(im.convert('L').filter(ImageFilter.FIND_EDGES), np.float64)
    print(n, 'edge NCC vs MA %.3f' % R.ncc(A, e(im)), 'shift', R.shift(A, e(im)), 'full-res edge mean %.2f' % lap.mean(), 'wall edge mean %.2f' % lap[600:1000, 400:900].mean())
