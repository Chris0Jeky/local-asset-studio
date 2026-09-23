"""Judging helper: full-resolution crops and a size readout, written to the gitignored scratch folder.

    python crop.py <image> info
    python crop.py <image> <x0> <y0> <x1> <y1> [name] [scale]

Crops are saved as PNG under `<repo>/.runtime/lab-scratch/crops/` (scaled up with LANCZOS when `scale` > 1) so hands and
faces are read at native pixels or larger, never from a downsampled whole frame.
"""
import sys
from pathlib import Path
from PIL import Image

OUT = Path(__file__).resolve().parents[3] / '.runtime' / 'lab-scratch' / 'crops'


def main(argv):
    img = Image.open(argv[0]); print(argv[0], img.size, img.mode)
    if argv[1:2] == ['info']: return
    x0, y0, x1, y1 = (int(v) for v in argv[1:5])
    name = argv[5] if len(argv) > 5 else Path(argv[0]).stem + '-%d-%d' % (x0, y0)
    scale = float(argv[6]) if len(argv) > 6 else 1.0
    crop = img.crop((x0, y0, x1, y1))
    if scale != 1.0: crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.LANCZOS)
    OUT.mkdir(parents=True, exist_ok=True); path = OUT / (name + '.png'); crop.save(path); print(path)


if __name__ == '__main__':
    main(sys.argv[1:])
