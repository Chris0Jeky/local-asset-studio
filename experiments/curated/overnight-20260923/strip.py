"""Side-by-side crops of the same region from several blind images, labelled by blind label only.

    python strip.py <out-name> <x0> <y0> <x1> <y1> <scale> <image> [<image> ...]

Writes `<repo>/.runtime/lab-scratch/crops/<out-name>.png` (gitignored) so near-identical variants are compared on one canvas.
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[3] / '.runtime' / 'lab-scratch' / 'crops'
name, x0, y0, x1, y1, scale = sys.argv[1], *map(int, sys.argv[2:6]), float(sys.argv[6])
tiles = []
for path in sys.argv[7:]:
    im = Image.open(path).convert('RGB').crop((x0, y0, x1, y1))
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    t = Image.new('RGB', (im.width, im.height + 18), (0, 0, 0)); t.paste(im, (0, 18))
    ImageDraw.Draw(t).text((4, 3), Path(path).stem, fill=(255, 255, 0)); tiles.append(t)
w = sum(t.width for t in tiles) + 6 * (len(tiles) - 1); h = max(t.height for t in tiles)
canvas = Image.new('RGB', (w, h), (60, 60, 60)); x = 0
for t in tiles: canvas.paste(t, (x, 0)); x += t.width + 6
OUT.mkdir(parents=True, exist_ok=True); canvas.save(OUT / (name + '.png')); print(OUT / (name + '.png'), canvas.size)
