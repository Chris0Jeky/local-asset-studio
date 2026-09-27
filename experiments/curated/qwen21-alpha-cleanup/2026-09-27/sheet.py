import sys
from PIL import Image, ImageDraw
src, clean, out = sys.argv[1:4]
a = Image.open(src).convert('RGBA'); b = Image.open(clean).convert('RGBA')
def on(bg, im):
    base = Image.new('RGBA', im.size, bg); base.alpha_composite(im); return base.convert('RGB')
def mask(im, lo=1):
    return im.getchannel('A').point(lambda v: 255 if v >= lo else 0).convert('RGB')
def boxed(im, src):
    im = im.copy(); box = src.getchannel('A').getbbox()
    if box: ImageDraw.Draw(im).rectangle(box, outline=(255, 0, 0), width=6)
    return im
tiles = [on((255, 0, 255, 255), a), boxed(mask(a), a), boxed(mask(b), b), on((40, 44, 52, 255), b)]
w, h = a.size; s = 360 / h
tiles = [t.resize((round(w * s), 360)) for t in tiles]
sheet = Image.new('RGB', (sum(t.width for t in tiles) + 30, 360), 'white'); x = 0
for t in tiles: sheet.paste(t, (x, 0)); x += t.width + 10
sheet.save(out, quality=88)
