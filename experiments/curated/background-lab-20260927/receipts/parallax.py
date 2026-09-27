# As-run script (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
"""Parallax lab (27 Sep 2026). Route B: clean plate from a flux-edit furniture removal, registered to the anchor, then
near = difference matte (anchor vs plate), mid = anchor outside the matte + plate behind it, with the window glass cut out,
far = the anchor's window view with a MAT-inpainted ring behind the frame. Route A (naive): three depth bands from Depth
Anything V2 with MAT-filled holes. Writes RGBA layers and a 3-frame parallax strip per route."""
import json, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, 'C:/Users/jekyt/AppData/Local/Temp/nightshift-0927'); sys.path.insert(0, 'C:/Users/jekyt/AppData/Local/Temp/bglab')
import comfy, align, registration as R
H = 'C:/Users/jekyt/AppData/Local/Temp/bglab/'; OUTD = comfy.OUT + 'Research/bglab-20260927/parallax/'
import os; os.makedirs(OUTD, exist_ok=True)
ANCHOR = 'C:/AI/ComfyUI_windows_portable/ComfyUI/output/Research/lab-20260927/asset-kit/retro-anime-master/retro-anime-master-z2.png'
PLATE = comfy.OUT + 'Verified/FLUX-Edit_00020_.png'
GLASS = [[(978, 62), (1133, 30), (1133, 450), (975, 440)], [(1162, 22), (1344, 0), (1344, 478), (1162, 455)]]   # manual, from a grid view of the plate
A = np.asarray(Image.open(ANCHOR).convert('RGB'), np.float32)

def mat_fill(rgb, hole, key):
    """MAT inpaint of hole (bool) via ComfyUI; returns filled RGB array."""
    rgba = np.dstack([rgb.clip(0, 255).astype(np.uint8), np.where(hole, 0, 255).astype(np.uint8)])
    name = 'bglab-%s.png' % key; Image.fromarray(rgba, 'RGBA').save(comfy.INP + name)
    g = {'1': {'class_type': 'LoadImage', 'inputs': {'image': name}}, '2': {'class_type': 'INPAINT_LoadInpaintModel', 'inputs': {'model_name': 'MAT_Places512_G_fp16.safetensors'}},
         '3': {'class_type': 'INPAINT_InpaintWithModel', 'inputs': {'inpaint_model': ['2', 0], 'image': ['1', 0], 'mask': ['1', 1], 'seed': 2026092700}},
         '4': {'class_type': 'SaveImage', 'inputs': {'images': ['3', 0], 'filename_prefix': 'Research/bglab-20260927/parallax/' + key}}}
    r = comfy.run(key, g, 'MAT inpaint'); out = np.asarray(Image.open(r['outputs'][0]).convert('RGB'), np.float32)
    return np.where(hole[..., None], out, rgb)

def poly_mask(polys, shape):
    m = Image.new('L', (shape[1], shape[0]), 0); d = ImageDraw.Draw(m)
    for p in polys: d.polygon(p, fill=255)
    return np.asarray(m) > 127

def grow(mask, px):
    return np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * px + 1))) > 127

def shrink(mask, px):
    return np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(2 * px + 1))) > 127

def save_layer(rgb, alpha, name):
    im = Image.fromarray(np.dstack([rgb.clip(0, 255).astype(np.uint8), (alpha * 255).clip(0, 255).astype(np.uint8)]), 'RGBA'); p = OUTD + name + '.png'; im.save(p); return p

def strip(layers, shifts, name, crop=28):
    """3 frames: camera left, centre, right. layers far->near as (rgb, alpha); shift in px per layer."""
    frames = []
    for s in (-1, 0, 1):
        canvas = np.zeros_like(A)
        for (rgb, al), sh in zip(layers, shifts):
            dx = int(round(s * sh)); rr = np.roll(rgb, dx, 1); aa = np.roll(al, dx, 1)[..., None]
            canvas = canvas * (1 - aa) + rr * aa
        frames.append(Image.fromarray(canvas[crop:-crop, crop:-crop].clip(0, 255).astype(np.uint8)))
    w, h = frames[0].size; sheet = Image.new('RGB', (w * 3 + 20, h), 'white')
    for i, f in enumerate(frames): sheet.paste(f, (i * (w + 10), 0))
    p = H + name + '.jpg'; sheet.resize((sheet.size[0] // 2, sheet.size[1] // 2), Image.LANCZOS).save(p, quality=88); return p, frames

def route_b():
    pts = align.patch_shifts(R.edges(ANCHOR), R.edges(PLATE)); ax, ay = align.fit(pts)
    warped = align.warp(PLATE, ax, ay, H + 'plate1-aligned.png'); P = np.asarray(Image.open(warped).convert('RGB'), np.float32)
    after = align.patch_shifts(R.edges(ANCHOR), R.edges(warped))
    diff = np.abs(A - P).mean(-1); yy, xx = np.mgrid[0:768, 0:1344]
    near = (diff > 28) & (xx > 600) & (yy > 330) & ~poly_mask(GLASS, diff.shape)
    near = shrink(grow(near, 4), 4); near = grow(shrink(near, 2), 2)          # close small gaps, then drop specks
    glass = poly_mask(GLASS, diff.shape)
    # far: anchor view in the glass; MAT fills a 32 px ring behind the frame and mullion so the view can slide
    ring = grow(glass, 32) & ~glass
    far_rgb = mat_fill(np.where(glass[..., None], A, 0), ~glass & grow(glass, 32), 'b-far-ring')
    far_a = grow(glass, 32).astype(np.float32)
    # mid: anchor everywhere except under the near matte (plate there, dilated 6 px), glass cut out
    under = grow(near, 6); mid_rgb = np.where(under[..., None], P, A); mid_a = (~glass).astype(np.float32)
    near_a = np.asarray(Image.fromarray((near * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255
    paths = [save_layer(far_rgb, far_a, 'b-far'), save_layer(mid_rgb, mid_a, 'b-mid'), save_layer(A, near_a, 'b-near')]
    comp = (far_rgb * far_a[..., None] * (1 - mid_a[..., None]) + mid_rgb * mid_a[..., None]) * (1 - near_a[..., None]) + A * near_a[..., None]
    err = float(np.abs(comp - A).mean())
    sp, _ = strip([(far_rgb, far_a), (mid_rgb, mid_a), (A, near_a)], [3, 10, 24], 'strip-route-b')
    return {'route': 'B', 'plate_affine_x': [round(v, 5) for v in ax], 'plate_affine_y': [round(v, 5) for v in ay],
            'patches': len(pts), 'mean_abs_shift_before': [round(float(np.mean([abs(p[2]) for p in pts])), 2), round(float(np.mean([abs(p[3]) for p in pts])), 2)],
            'mean_abs_shift_after': [round(float(np.mean([abs(p[2]) for p in after])), 2), round(float(np.mean([abs(p[3]) for p in after])), 2)],
            'near_pixels': int(near.sum()), 'glass_pixels': int(glass.sum()), 'recomposite_mean_abs_error': round(err, 2), 'layers': paths, 'strip': sp, 'shifts_px': [3, 10, 24]}

def route_a():
    dep = np.asarray(Image.open(comfy.OUT + 'Research/bglab-20260927/parallax/depth-z2_00001_.png').convert('L').resize((1344, 768), Image.LANCZOS), np.float32) / 255
    far = dep < 0.25; near = dep > 0.62; mid = ~far & ~near
    far_rgb = mat_fill(A, ~far, 'a-far-fill'); mid_rgb = mat_fill(A, near, 'a-mid-fill')
    paths = [save_layer(far_rgb, np.ones_like(dep), 'a-far'), save_layer(mid_rgb, (mid | near).astype(np.float32) * 0 + mid.astype(np.float32), 'a-mid'), save_layer(A, near.astype(np.float32), 'a-near')]
    sp, _ = strip([(far_rgb, np.ones_like(dep)), (mid_rgb, mid.astype(np.float32)), (A, near.astype(np.float32))], [3, 10, 24], 'strip-route-a')
    return {'route': 'A', 'thresholds': {'far': '<0.25', 'near': '>0.62'}, 'far_pixels': int(far.sum()), 'near_pixels': int(near.sum()), 'layers': paths, 'strip': sp}

if __name__ == '__main__':
    res = {'B': route_b(), 'A': route_a()}
    json.dump(res, open(H + 'parallax.json', 'w'), indent=1); print(json.dumps(res, indent=1)[:2500])

ISOLATE = comfy.OUT + 'Verified/FLUX-Edit_00022_.png'
def route_c():
    """B with the near matte from a second flux-edit that isolates the furniture on white (registered with the same affine fit)."""
    from scipy import ndimage as nd
    pts = align.patch_shifts(R.edges(ANCHOR), R.edges(ISOLATE)); ax, ay = align.fit(pts)
    iw = np.asarray(Image.open(align.warp(ISOLATE, ax, ay, H + 'isolate-aligned.png')).convert('RGB'), np.float32)
    after = align.patch_shifts(R.edges(ANCHOR), R.edges(H + 'isolate-aligned.png'))
    near = (iw.min(-1) < 225)   # the isolate is trusted inside the window area too (the CRT overlaps the glass)
    near = nd.binary_opening(near, iterations=2); near = nd.binary_fill_holes(nd.binary_closing(near, iterations=3))
    lab, n = nd.label(near); sizes = nd.sum(near, lab, range(1, n + 1)); near = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s > 800])
    P = np.asarray(Image.open(H + 'plate1-aligned.png').convert('RGB'), np.float32)
    glass = poly_mask(GLASS, near.shape)
    far_rgb = mat_fill(np.where(glass[..., None], A, 0), ~glass & grow(glass, 32), 'c-far-ring'); far_a = grow(glass, 32).astype(np.float32)
    under = grow(near, 8); mid_rgb = np.where(under[..., None], P, A); mid_a = (~glass).astype(np.float32)
    near_a = np.asarray(Image.fromarray((near * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0)), np.float32) / 255
    paths = [save_layer(far_rgb, far_a, 'c-far'), save_layer(mid_rgb, mid_a, 'c-mid'), save_layer(A, near_a, 'c-near')]
    comp = (far_rgb * far_a[..., None] * (1 - mid_a[..., None]) + mid_rgb * mid_a[..., None]) * (1 - near_a[..., None]) + A * near_a[..., None]
    sp, _ = strip([(far_rgb, far_a), (mid_rgb, mid_a), (A, near_a)], [3, 10, 24], 'strip-route-c')
    Image.fromarray((near * 255).astype(np.uint8)).resize((672, 384)).save(H + 'c-near-mask.png')
    return {'route': 'C', 'isolate_affine_x': [round(v, 5) for v in ax], 'isolate_affine_y': [round(v, 5) for v in ay], 'patches': len(pts),
            'mean_abs_shift_after': [round(float(np.mean([abs(p[2]) for p in after])), 2), round(float(np.mean([abs(p[3]) for p in after])), 2)] if after else None,
            'near_pixels': int(near.sum()), 'recomposite_mean_abs_error': round(float(np.abs(comp - A).mean()), 2), 'layers': paths, 'strip': sp, 'shifts_px': [3, 10, 24]}

def route_c2():
    """C plus two fixes found on review: the far layer's ring behind the frame is filled from the nearest window-view pixel
    (MAT had extended the black context), with the CRT excluded from the view; the clean plate is colour-matched to the anchor
    (per-channel mean/std in a 24 px ring around the matte) and blended in with a 6 px feather."""
    from scipy import ndimage as nd
    iw = np.asarray(Image.open(H + 'isolate-aligned.png').convert('RGB'), np.float32)
    near = iw.min(-1) < 225
    near = nd.binary_opening(near, iterations=2); near = nd.binary_fill_holes(nd.binary_closing(near, iterations=3))
    lab, n = nd.label(near); sizes = nd.sum(near, lab, range(1, n + 1)); near = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s > 800])
    P = np.asarray(Image.open(H + 'plate1-aligned.png').convert('RGB'), np.float32)
    glass = poly_mask(GLASS, near.shape); view = glass & ~grow(near, 2)
    _, (iy, ix) = nd.distance_transform_edt(~view, return_indices=True)
    far_rgb = A[iy, ix]; far_a = grow(glass, 32).astype(np.float32)
    under = grow(near, 8); ring = grow(near, 32) & ~under & ~glass
    Pm = P.copy()
    for c in range(3):
        pa, aa = P[..., c][ring], A[..., c][ring]
        Pm[..., c] = (P[..., c] - pa.mean()) * (aa.std() / max(pa.std(), 1e-3)) + aa.mean()
    blend = np.asarray(Image.fromarray((under * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), np.float32)[..., None] / 255
    mid_rgb = A * (1 - blend) + Pm * blend; mid_a = (~glass).astype(np.float32)
    near_a = np.asarray(Image.fromarray((near * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0)), np.float32) / 255
    paths = [save_layer(far_rgb, far_a, 'c2-far'), save_layer(mid_rgb, mid_a, 'c2-mid'), save_layer(A, near_a, 'c2-near')]
    comp = (far_rgb * far_a[..., None] * (1 - mid_a[..., None]) + mid_rgb * mid_a[..., None]) * (1 - near_a[..., None]) + A * near_a[..., None]
    sp, _ = strip([(far_rgb, far_a), (mid_rgb, mid_a), (A, near_a)], [3, 10, 24], 'strip-route-c2')
    return {'route': 'C2', 'near_pixels': int(near.sum()), 'recomposite_mean_abs_error': round(float(np.abs(comp - A).mean()), 2), 'layers': paths, 'strip': sp, 'shifts_px': [3, 10, 24],
            'fixes': ['far ring filled from the nearest window-view pixel (no MAT), CRT excluded from the view', 'plate colour-matched to the anchor in a 24 px ring, 6 px feathered blend']}
