# As-run script (27 Sep 2026), kept as a receipt; hardcodes this machine's local paths and is not a portable reproduction.
"""Registration of a quiet candidate against the anchor: edge-map normalised cross-correlation (whole frame and the
right-hand object zone) and the phase-correlation shift. Same-camera edits should give shift ~0 and high edge NCC."""
import json, sys
import numpy as np
from PIL import Image, ImageFilter
import ns

def edges(p, size=(1344, 768)):
    g = Image.open(p).convert('L').resize(size, Image.LANCZOS).filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(1.5))
    return np.asarray(g, dtype=np.float64)

def ncc(a, b):
    a = a - a.mean(); b = b - b.mean(); return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum()))

def shift(a, b):
    F = np.fft.fft2(a) * np.conj(np.fft.fft2(b)); r = np.abs(np.fft.ifft2(F / (np.abs(F) + 1e-9)))
    y, x = np.unravel_index(r.argmax(), r.shape); h, w = r.shape
    return [int(x if x < w // 2 else x - w), int(y if y < h // 2 else y - h)]

def measure(p, anchor=ns.ANCHOR):
    A = edges(anchor); B = edges(p); zone = (slice(250, 768), slice(620, 1344))   # window, lamp, CRT, desk, chair
    return {'edge_ncc_full': round(ncc(A, B), 3), 'edge_ncc_objects': round(ncc(A[zone], B[zone]), 3), 'phase_shift_px': shift(A, B)}

def overlay(p, dst, anchor=ns.ANCHOR):
    """Anchor edges in red over the candidate (grey): misregistration shows as doubled lines."""
    A = edges(anchor); c = np.asarray(Image.open(p).convert('L').resize((1344, 768)), dtype=np.float64) * 0.6
    rgb = np.stack([c, c, c], -1); m = np.clip(A / 40, 0, 1)[..., None]
    rgb = rgb * (1 - m) + np.array([255, 40, 40]) * m
    Image.fromarray(rgb.astype(np.uint8)).save(dst)

if __name__ == '__main__':
    runs = {json.loads(l)['key']: json.loads(l) for l in open(ns.HERE + 'runs.jsonl')}
    out = {'anchor_self': measure(ns.ANCHOR)}
    for k in sys.argv[1:]:
        p = runs[k]['outputs'][0]['path']; out[k] = measure(p); overlay(p, ns.HERE + 'reg-%s.png' % k)
    print(json.dumps(out, indent=1)); json.dump(out, open(ns.HERE + 'registration-%s.json' % '-'.join(sys.argv[1:]), 'w'), indent=1)
