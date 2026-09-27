# As-run script (27 Sep 2026), kept as a receipt; hardcodes this machine's local paths and is not a portable reproduction.
"""Fit the small affine offset a FLUX.2 Klein edit introduced (patch-wise edge NCC shifts -> least squares), then warp the
candidate onto the anchor's pixel grid. Out-of-frame samples (a few px at the right and bottom edge) replicate the edge."""
import json, sys
import numpy as np
from PIL import Image
import ns, registration as R

def patch_shifts(A, B, step=96, size=128, search=8):
    pts = []
    for y in range(0, 768 - size + 1, step):
        for x in range(0, 1344 - size + 1, step):
            a = A[y:y + size, x:x + size]
            if a.std() < 3: continue
            best = (-2, 0, 0)
            for dx in range(-search, search + 1):
                for dy in range(-search, search + 1):
                    ys, xs = y + dy, x + dx
                    if ys < 0 or xs < 0 or ys + size > 768 or xs + size > 1344: continue
                    v = R.ncc(a, B[ys:ys + size, xs:xs + size])
                    if v > best[0]: best = (v, dx, dy)
            if best[0] > 0.6: pts.append((x + size / 2, y + size / 2, best[1], best[2], best[0]))
    return pts

def fit(pts):
    P = np.array(pts); X = np.c_[P[:, 0], P[:, 1], np.ones(len(P))]
    ax, *_ = np.linalg.lstsq(X, P[:, 0] + P[:, 2], rcond=None); ay, *_ = np.linalg.lstsq(X, P[:, 1] + P[:, 3], rcond=None)
    return ax, ay   # anchor (x, y) -> candidate (x', y')

def warp(src, ax, ay, dst):
    im = Image.open(src).convert('RGB'); W, H = im.size
    pad = 16; big = Image.fromarray(np.pad(np.asarray(im), ((pad, pad), (pad, pad), (0, 0)), mode='edge'))
    out = big.transform((W, H), Image.AFFINE, (ax[0], ax[1], ax[2] + pad, ay[0], ay[1], ay[2] + pad), resample=Image.BICUBIC)
    out.save(dst); return dst

if __name__ == '__main__':
    runs = {json.loads(l)['key']: json.loads(l) for l in open(ns.HERE + 'runs.jsonl')}
    A = R.edges(ns.ANCHOR); res = {}
    for k in sys.argv[1:]:
        src = runs[k]['outputs'][0]['path']; pts = patch_shifts(A, R.edges(src)); ax, ay = fit(pts)
        dst = ns.HERE + '%s-aligned.png' % k; warp(src, ax, ay, dst)
        after = patch_shifts(A, R.edges(dst))
        res[k] = {'patches_used': len(pts), 'affine_x': [round(v, 6) for v in ax], 'affine_y': [round(v, 6) for v in ay],
                  'mean_abs_shift_before': [round(float(np.mean([abs(p[2]) for p in pts])), 2), round(float(np.mean([abs(p[3]) for p in pts])), 2)],
                  'mean_abs_shift_after': [round(float(np.mean([abs(p[2]) for p in after])), 2), round(float(np.mean([abs(p[3]) for p in after])), 2)],
                  'patches_after': len(after), 'zones_after': {}, 'aligned_file': dst}
        B = R.edges(dst)
        print(k, json.dumps(res[k]))
    json.dump(res, open(ns.HERE + 'align-%s.json' % '-'.join(sys.argv[1:]), 'w'), indent=1)
