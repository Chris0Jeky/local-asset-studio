"""Contact sheets for the SDXL drawn-skeleton research (22 September 2026). Reads grid.json and the scratch PNGs run_grid.py
downloaded, writes small JPEGs under examples/style-pose/: one grid sheet per skeleton (the skeleton and the no-ControlNet
baseline first, then one row per strength / end_percent, a column per seed) and one comparison sheet.

    python contact_sheet.py [--renders .runtime/761/renders]
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
TILE = 300  # tile height in pixels; 832x1216 renders become 205x300
PAD, LABEL = 6, 18


def tile(path, label):
    if path and Path(path).exists():
        with Image.open(path) as image: im = image.convert('RGB').resize((round(image.width * TILE / image.height), TILE))
    else:
        im = Image.new('RGB', (round(TILE * 832 / 1216), TILE), (40, 40, 40)); ImageDraw.Draw(im).text((8, 8), 'not rendered', fill='white')
    return label, im


def sheet(rows, dest):
    width = max(sum(im.width for _, im in row) + PAD * (len(row) - 1) for row in rows)
    out = Image.new('RGB', (width, len(rows) * (TILE + LABEL + PAD)), 'white'); draw = ImageDraw.Draw(out); y = 0
    for row in rows:
        x = 0
        for label, im in row:
            out.paste(im, (x, y + LABEL)); draw.text((x + 3, y + 3), label, fill='black'); x += im.width + PAD
        y += TILE + LABEL + PAD
    out.save(dest, quality=78, optimize=True); print(dest, out.size, dest.stat().st_size)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--renders', type=Path, default=ROOT / '.runtime/761/renders')
    args = parser.parse_args()
    cells = json.loads((HERE / 'grid.json').read_text(encoding='utf-8'))['cells']
    def find(**want):
        return sorted((c for c in cells.values() if all(c.get(k) == v for k, v in want.items())), key=lambda c: c['seed'])
    def row(label, found):
        return [tile(args.renders / (c['id'] + '.png'), '%s, seed %s' % (label, str(c['seed'])[-2:])) for c in found]
    dest_dir = ROOT / 'examples/style-pose'
    for skeleton in ('action', 'bent'):
        rows = [[tile(HERE.parent / ('skeleton-%s.openpose.png' % skeleton), 'skeleton (openpose renderer)'),
                 tile(HERE.parent / ('skeleton-%s.lines.png' % skeleton), 'same joints, thin-line renderer')]
                + row('no ControlNet', find(tag='baseline'))]
        for strength, end in ((0.6, 0.6), (0.6, 1.0), (0.8, 0.6), (0.8, 1.0), (0.9, 0.85), (1.0, 0.6), (1.0, 1.0)):
            rows.append(row('s %.1f end %.2g' % (strength, end), find(skeleton=skeleton, tag='wai', strength=strength, end=end)))
        sheet(rows, dest_dir / ('sdxl-skeleton-grid-%s.jpg' % skeleton))
    rows = []
    for skeleton in ('action', 'bent'):
        for tag, label in (('lines', 'thin-line guide'), ('union', 'Union ControlNet'), ('animagine', 'Animagine XL 4')):
            found = find(skeleton=skeleton, tag=tag)
            if found: rows.append(row('%s %s s %.1f end %.2g' % (skeleton, label, found[0]['strength'], found[0]['end']), found))
    if rows: sheet(rows, dest_dir / 'sdxl-skeleton-compare.jpg')


if __name__ == '__main__':
    main()
