# As-run script (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
"""Deterministic post step for tiles: remove low-frequency lighting with a circular (wrap-around) Gaussian so the correction
itself tiles: out = tile * mean / blur(tile), sigma 96 px, per channel, via FFT."""
import sys, json
import numpy as np
from PIL import Image
sys.path.insert(0, 'C:/Users/jekyt/AppData/Local/Temp/bglab'); import tiles, comfy
def cblur(ch, sigma):
    n, m = ch.shape; fy = np.fft.fftfreq(n)[:, None]; fx = np.fft.fftfreq(m)[None, :]
    return np.real(np.fft.ifft2(np.fft.fft2(ch) * np.exp(-2 * (np.pi * sigma) ** 2 * (fx ** 2 + fy ** 2))))
def flatten(src, dst, sigma=96):
    a = np.asarray(Image.open(src).convert('RGB'), np.float64)
    out = np.stack([a[..., c] * a[..., c].mean() / np.maximum(cblur(a[..., c], sigma), 1) for c in range(3)], -1).clip(0, 255).astype(np.uint8)
    Image.fromarray(out).save(dst); return out
key = sys.argv[1]
src = comfy.OUT + 'Research/bglab-20260927/tiles/%s-tile.png' % key; dst = comfy.OUT + 'Research/bglab-20260927/tiles/%s-tile-flat.png' % key
o = flatten(src, dst); tiles.grid(o, '%s-flat-3x3.jpg' % key)
print(json.dumps({'key': key + '-flat', 'source': src, 'tile': dst, 'seam_tile': tiles.seam(o), 'inner_gradient_tile': tiles.inner(o), 'step': 'circular-Gaussian illumination flatten, sigma 96 px'}))
