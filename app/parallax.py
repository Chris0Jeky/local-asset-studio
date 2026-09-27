"""Parallax layers (#1219): the background lab's route C2 as a Studio route. This module never calls ComfyUI or queues work.

1. Prepare (`prepare`): the owner names the foreground to lift out and may mark the far view (window glass, sky) as boxes
   or polygons on the picture. The Studio attaches the unchanged source as the edit picture and returns a plan whose
   identity (`plan_id`) covers the source, its size, the words and the view. Nothing is queued.
2. Generate, twice: the owner presses Generate on the catalog's `parallax_route` recipe (FLUX.2 Klein 4B, the verified
   flux-edit graph) once for the clean plate ("remove <objects>") and once for the isolate ("replace everything except
   <objects> with plain white"). Each job carries the plan as its `parallax` claim with its stage; `validate` re-checks
   the source, the attached picture and the size before binding and before the POST. Two Create runs, not one job: each
   edit keeps its own prompt ID, seed and words, and a bad plate is rerun without repeating a good isolate.
3. Finish (`finish`, run when the second stage completes, or by hand): register both edits to the source by an affine fit
   on edge patches (Klein returns them 0.6-1.3 % larger), derive the near matte from the isolate, colour-match the plate
   in a ring around it and blend it in under a feather, fill the far view's ring from its nearest pixel, and write far /
   mid / near RGBA layers, the recomposite error and a 3-frame parallax strip as a `parallax.finish.v1` job whose assets
   carry lineage to the source and both edits.

Method and numbers: experiments/curated/background-lab-20260927/ (PR #1222), route C2: recomposite error 0.36/255. Pillow
only: numpy is not a Studio dependency, so dilation is two 1-D box passes, parts are found from row runs, and the ring
fill grows one pixel per step. Numbers are evidence for review, never art acceptance.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
import re
import statistics
import threading
import time
import uuid
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat

import continuation

VERSION = 1
OPERATION = "parallax.finish.v1"
STAGES = ("plate", "isolate")
STAGE_NAMES = {"plate": "clean plate", "isolate": "isolate"}
SIZE_LIMITS = (512, 2048)
SIZE_MULTIPLE = 16
MAX_PIXELS = 1_600_000          # the lab ran 1344 x 768 (1.03 MP); Klein edits the picture at about one megapixel
MAX_VIEWS, MAX_POINTS, OBJECTS_LIMIT = 4, 16, 240
# Route C2's values at 1344 x 768, kept in pixels and recorded in every receipt.
PARAMETERS = {"white_below": 225, "open_px": 2, "close_px": 3, "min_part_px": 800, "view_guard_px": 2, "far_ring_px": 32,
              "under_px": 8, "match_ring_px": 32, "feather_px": 6, "near_blur_px": 1.0, "shifts_px": [3, 10, 24]}
REGISTRATION = {"patch_px": 64, "max_shift_px": 36, "max_patches": 48, "min_patches": 6}
PLATE_WORDS = ("Remove {objects}, leaving the space behind them empty. Keep everything else exactly as it is: the same camera and "
               "framing, the same walls, windows, floor and view, the same colours and lighting, and the same painting style.")
ISOLATE_WORDS = ("Replace everything except {objects} with a plain pure white background. Keep {objects} exactly as they are: the "
                 "same position, size, shape, colours and painting style.")
FLAG = ("Name the foreground concretely (e.g. the desk, the chair and the lamp). Mark the far view (window glass, sky) as boxes "
        "inside the glass, or leave it empty for two layers. The view mask is yours, not detected.")
CLAIM_FIELDS = {"version", "plan_id", "stage", "preset_id", "source_asset_id", "source_sha256", "source_file", "width", "height", "objects", "view_polygons"}
_FINISH_LOCK = threading.Lock()


# ---------------------------------------------------------------- masks (L images, 0 or 255)

def binary(mask, threshold=128):
    return mask.convert("L").point(lambda value: 255 if value >= threshold else 0)


def grow(mask, px):
    """Square dilation by `px` (a (2px+1)-wide square), exact: two 1-D box passes, where any lit pixel in reach stays above 0."""
    mask = binary(mask)
    if px <= 0: return mask
    if px > 250: raise ValueError("grow radius too large")
    wide = mask.filter(ImageFilter.BoxBlur((px, 0))).point(lambda value: 255 if value else 0)
    return wide.filter(ImageFilter.BoxBlur((0, px))).point(lambda value: 255 if value else 0)


def shrink(mask, px):
    return ImageChops.invert(grow(ImageChops.invert(binary(mask)), px))


def opening(mask, px): return grow(shrink(mask, px), px)


def closing(mask, px): return shrink(grow(mask, px), px)


# The set operations below take masks that are already 0/255 (every mask here is made by binary, grow or a polygon).
def both(first, second): return ImageChops.darker(first, second)


def minus(first, second): return ImageChops.darker(first, ImageChops.invert(second))


def either(first, second): return ImageChops.lighter(first, second)


def count(mask): return binary(mask).histogram()[255]


def parts(mask, lit=True):
    """Connected parts of the lit (8-connected) or dark (4-connected) pixels, each a list of row runs (y, x0, x1)."""
    width, height = mask.size; data = binary(mask).tobytes(); pattern = re.compile(b"\xff+" if lit else b"\x00+"); slack = 1 if lit else 0
    runs, rows = [], []
    for y in range(height):
        start = len(runs)
        for match in pattern.finditer(data, y * width, (y + 1) * width): runs.append((y, match.start() - y * width, match.end() - y * width))
        rows.append((start, len(runs)))
    parent = list(range(len(runs)))

    def root(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for y in range(1, height):
        above, here = rows[y - 1], rows[y]; i, j = above[0], here[0]
        while i < above[1] and j < here[1]:
            a, b = runs[i], runs[j]
            if a[1] < b[2] + slack and b[1] < a[2] + slack: parent[root(i)] = root(j)
            if a[2] < b[2]: i += 1
            else: j += 1
    groups = {}
    for index, run in enumerate(runs): groups.setdefault(root(index), []).append(run)
    return list(groups.values())


def _paint(mask, runs, value):
    width = mask.size[0]; data = bytearray(binary(mask).tobytes())
    for y, x0, x1 in runs: data[y * width + x0:y * width + x1] = bytes([value]) * (x1 - x0)
    return Image.frombytes("L", mask.size, bytes(data))


def fill_holes(mask):
    """Light every dark part that does not touch the border: a white paper on a desk stays part of the desk."""
    width, height = mask.size
    holes = [run for part in parts(mask, lit=False) if not any(y in (0, height - 1) or x0 == 0 or x1 == width for y, x0, x1 in part) for run in part]
    return _paint(mask, holes, 255)


def drop_small(mask, min_px):
    small = [run for part in parts(mask) if sum(x1 - x0 for _, x0, x1 in part) < min_px for run in part]
    return _paint(mask, small, 0)


def polygon_mask(size, polygons):
    mask = Image.new("L", size, 0); draw = ImageDraw.Draw(mask)
    for points in polygons: draw.polygon([tuple(point) for point in points], fill=255)
    return mask


# ---------------------------------------------------------------- registration

def edge_map(image):
    """Where the edges are, not how strong: |Laplacian| of the softened grey picture above 1.5 times its own local mean (and at
    least 6), softened again so the patch cost is smooth for the sub-pixel step. An isolate edit redraws the outlines crisper,
    on white, than the source draws them in the room, so edge strength differs while edge position holds."""
    grey = image.convert("L").filter(ImageFilter.GaussianBlur(1))
    edges = ImageChops.add(grey.filter(ImageFilter.FIND_EDGES), ImageChops.invert(grey).filter(ImageFilter.FIND_EDGES))
    threshold = edges.filter(ImageFilter.BoxBlur(16)).point(lambda value: min(255, max(6, int(1.5 * value))))
    return ImageChops.subtract(edges, threshold).point(lambda value: 255 if value else 0).filter(ImageFilter.GaussianBlur(1.5))


def _cost(patch, other, x, y, patch_sum):
    """Normalised edge mismatch, 0 (same edges) to 1 (no shared edge): SAD over the two windows' edge mass, so a window moved
    onto an empty area (the isolate's white) scores as the worst match, not the best one."""
    window = other.crop((x, y, x + patch.size[0], y + patch.size[1]))
    return sum(ImageStat.Stat(ImageChops.difference(patch, window)).sum) / (patch_sum + sum(ImageStat.Stat(window).sum) + 1)


def _search(patch, other, x, y, centre, radius):
    width, height = patch.size; costs = {}; patch_sum = sum(ImageStat.Stat(patch).sum)
    for dy in range(centre[1] - radius, centre[1] + radius + 1):
        for dx in range(centre[0] - radius, centre[0] + radius + 1):
            if 0 <= x + dx and 0 <= y + dy and x + dx + width <= other.size[0] and y + dy + height <= other.size[1]: costs[(dx, dy)] = _cost(patch, other, x + dx, y + dy, patch_sum)
    return (min(costs, key=costs.get), costs) if costs else (None, costs)


def _vertex(low, mid, high):
    curve = low - 2 * mid + high
    return max(-0.5, min(0.5, (low - high) / (2 * curve))) if curve > 0 else 0.0


def _distinct(best, costs, apart=2, margin=0.9):
    """True when every candidate at least `apart` steps from the best costs clearly more: a floor's parallel planks or a
    plain wall slide along themselves and give no position (the aperture problem), so those patches are skipped."""
    rivals = [cost for key, cost in costs.items() if max(abs(key[0] - best[0]), abs(key[1] - best[1])) >= apart]
    return not rivals or costs[best] < margin * min(rivals)


def patch_shifts(anchor, edit, patch=None, max_shift=None, max_patches=None):
    """[(centre_x, centre_y, dx, dy)]: where each well-textured patch of the anchor sits in the edit, coarse (1/4 size) then fine, sub-pixel."""
    patch = patch or REGISTRATION["patch_px"]; max_shift = max_shift or REGISTRATION["max_shift_px"]; max_patches = max_patches or REGISTRATION["max_patches"]
    a, b = edge_map(anchor), edge_map(edit); width, height = a.size; margin = max_shift + 4
    candidates = []
    for y in range(margin, height - margin - patch + 1, patch // 2):
        for x in range(margin, width - margin - patch + 1, patch // 2):
            box = (x, y, x + patch, y + patch)
            energy = min(ImageStat.Stat(a.crop(box)).mean[0], ImageStat.Stat(b.crop(box)).mean[0])
            if energy >= 3: candidates.append((energy, x, y))
    candidates = sorted(candidates, reverse=True)[:max_patches]
    a4, b4 = a.reduce(4), b.reduce(4); radius4 = math.ceil(max_shift / 4); found = []
    for _, x, y in candidates:
        coarse, coarse_costs = _search(a4.crop((x // 4, y // 4, x // 4 + patch // 4, y // 4 + patch // 4)), b4, x // 4, y // 4, (0, 0), radius4)
        if coarse is None or not _distinct(coarse, coarse_costs): continue
        best, costs = _search(a.crop((x, y, x + patch, y + patch)), b, x, y, (coarse[0] * 4, coarse[1] * 4), 3)
        if best is None or costs[best] > 0.7: continue       # no real match: a removed object, or unrelated content
        bx, by = best
        sx = _vertex(costs.get((bx - 1, by), costs[best]), costs[best], costs.get((bx + 1, by), costs[best]))
        sy = _vertex(costs.get((bx, by - 1), costs[best]), costs[best], costs.get((bx, by + 1), costs[best]))
        found.append((x + patch / 2, y + patch / 2, bx + sx, by + sy))
    return found


def _solve3(m, v):
    """Gaussian elimination for a 3 x 3 system; None when singular."""
    rows = [list(m[i]) + [v[i]] for i in range(3)]
    for col in range(3):
        pivot = max(range(col, 3), key=lambda r: abs(rows[r][col]))
        if abs(rows[pivot][col]) < 1e-9: return None
        rows[col], rows[pivot] = rows[pivot], rows[col]
        for r in range(3):
            if r != col:
                factor = rows[r][col] / rows[col][col]; rows[r] = [a - factor * b for a, b in zip(rows[r], rows[col])]
    return [rows[i][3] / rows[i][i] for i in range(3)]


def fit_affine(points):
    """Least squares for edit_x = a x + b y + c and edit_y = d x + e y + f from (x, y, dx, dy); None when degenerate."""
    if len(points) < 3: return None
    sums = [[0.0] * 3 for _ in range(3)]; rx, ry = [0.0] * 3, [0.0] * 3
    for x, y, dx, dy in points:
        row = (x, y, 1.0)
        for i in range(3):
            for j in range(3): sums[i][j] += row[i] * row[j]
            rx[i] += row[i] * (x + dx); ry[i] += row[i] * (y + dy)
    first, second = _solve3(sums, rx), _solve3(sums, ry)
    return (first, second) if first and second else None


def _residual(point, fit):
    x, y, dx, dy = point; (a, b, c), (d, e, f) = fit
    return math.hypot(a * x + b * y + c - x - dx, d * x + e * y + f - y - dy)


def _exact(sample):
    """The affine through three point pairs, or None for a degenerate (collinear) triple."""
    rows = [(x, y, 1.0) for x, y, _, _ in sample]
    first, second = _solve3(rows, [x + dx for x, _, dx, _ in sample]), _solve3(rows, [y + dy for _, y, _, dy in sample])
    return (first, second) if first and second else None


def robust_affine(points, tolerance=1.5, rounds=300, seed=1219):
    """RANSAC with a fixed seed (so a replay gives the same fit), then least squares on the inliers, twice. Returns (fit, inliers)."""
    import random
    if len(points) < 3: return None, []
    rng, best = random.Random(seed), (0, 0.0, [])
    for _ in range(rounds):
        fit = _exact(rng.sample(points, 3))
        if not fit: continue
        inliers = [point for point in points if _residual(point, fit) <= tolerance]
        score = (len(inliers), -sum(_residual(point, fit) for point in inliers))
        if score > best[:2]: best = score + (inliers,)
    inliers, fit = best[2], None
    for _ in range(2):
        fit = fit_affine(inliers) if len(inliers) >= 3 else None
        if not fit: return None, inliers
        inliers = [point for point in points if _residual(point, fit) <= tolerance]
    return fit, inliers


def register(anchor, edit, background):
    """Warp `edit` onto `anchor` by a robust affine fit. Returns (registered RGB, record). A failed fit falls back to a
    plain resize and says so in the record; it never raises, because the recomposite check still judges the result."""
    record = {"edit_size": list(edit.size)}
    if edit.size != anchor.size: edit = edit.resize(anchor.size, Image.LANCZOS); record["resized_to"] = list(anchor.size)
    points = patch_shifts(anchor, edit); record["patches_found"] = len(points)
    record["mean_abs_shift_before"] = [round(statistics.fmean(abs(p[2]) for p in points), 2), round(statistics.fmean(abs(p[3]) for p in points), 2)] if points else None
    fit, kept = robust_affine(points)
    reason = None
    if len(kept) < REGISTRATION["min_patches"] or not fit: reason = "only %d agreeing patches (need %d)" % (len(kept), REGISTRATION["min_patches"])
    else:
        (a, b, c), (d, e, f) = fit
        if abs(a - 1) > 0.08 or abs(e - 1) > 0.08 or abs(b) > 0.05 or abs(d) > 0.05 or abs(c) > 3 * REGISTRATION["max_shift_px"] or abs(f) > 3 * REGISTRATION["max_shift_px"]:
            reason = "the fit is implausible (scale %.4f / %.4f)" % (a, e)
    if reason:
        record.update(fallback="No registration: " + reason + "; the edit is only resized to the source size.", affine_x=[1, 0, 0], affine_y=[0, 1, 0], patches_used=len(kept))
        return edit.convert("RGB"), record
    residuals = [_residual(point, fit) for point in kept]
    record.update(affine_x=[round(v, 6) for v in fit[0]], affine_y=[round(v, 6) for v in fit[1]], patches_used=len(kept),
                  mean_residual_px=round(statistics.fmean(residuals), 3), fallback=None)
    warped = edit.convert("RGBA").transform(anchor.size, Image.AFFINE, tuple(fit[0]) + tuple(fit[1]), resample=Image.BICUBIC)
    base = Image.new("RGBA", anchor.size, background + (255,)) if isinstance(background, tuple) else background.convert("RGBA")
    registered = Image.alpha_composite(base, warped).convert("RGB")
    after = patch_shifts(anchor, registered)   # the lab's check: measure the patches again on the warped edit
    record["patches_after"] = len(after)
    if after: record.update(median_abs_shift_after=[round(statistics.median(abs(p[2]) for p in after), 2), round(statistics.median(abs(p[3]) for p in after), 2)],
                            mean_abs_shift_after=[round(statistics.fmean(abs(p[2]) for p in after), 2), round(statistics.fmean(abs(p[3]) for p in after), 2)])
    return registered, record


# ---------------------------------------------------------------- layers

def near_matte(isolate, parameters=PARAMETERS):
    """Foreground = pixels whose darkest channel is below `white_below`, opened, closed, holes filled, specks dropped."""
    red, green, blue = isolate.convert("RGB").split(); darkest = ImageChops.darker(ImageChops.darker(red, green), blue)
    matte = darkest.point(lambda value: 255 if value < parameters["white_below"] else 0)
    matte = opening(matte, parameters["open_px"]); matte = fill_holes(closing(matte, parameters["close_px"]))
    return drop_small(matte, parameters["min_part_px"])


def _stats(image, mask):
    stat = ImageStat.Stat(image, mask); return stat.mean, stat.stddev


def colour_match(plate, source, ring):
    """Per channel, map the plate's mean and spread in `ring` onto the source's (the lab's 24-32 px ring). Returns (image, record)."""
    if count(ring) < 16: return plate, {"skipped": "no ring around the foreground to match against", "gain": [1, 1, 1], "offset": [0, 0, 0]}
    (plate_mean, plate_std), (source_mean, source_std) = _stats(plate, ring), _stats(source, ring); channels, gains, offsets = [], [], []
    for band, pm, ps, sm, ss in zip(plate.split(), plate_mean, plate_std, source_mean, source_std):
        gain = ss / max(ps, 1e-3); offset = sm - pm * gain; gains.append(round(gain, 4)); offsets.append(round(offset, 3))
        channels.append(band.point(lambda value, g=gain, o=offset: max(0, min(255, int(value * g + o + 0.5)))))
    return Image.merge("RGB", channels), {"gain": gains, "offset": offsets, "ring_px": count(ring)}


def _shift(image, dx, dy):
    out = Image.new(image.mode, image.size, 0); out.paste(image, (dx, dy)); return out


def ring_fill(image, known, target):
    """Give every `target` pixel outside `known` the colour of its nearest known pixel (8-neighbour growth, one pixel a step)."""
    known = binary(known); target = either(binary(target), known); box = target.getbbox()
    rgb = Image.composite(image.convert("RGB"), Image.new("RGB", image.size), known)
    if not box or not known.getbbox(): return rgb, count(minus(target, known))
    crop_rgb, crop_known, crop_target = rgb.crop(box), known.crop(box), target.crop(box)
    offsets = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1))
    for _ in range(max(crop_rgb.size)):
        todo = minus(crop_target, crop_known)
        if not todo.getbbox(): break
        start_rgb, start_known, progressed = crop_rgb, crop_known, False
        for dx, dy in offsets:
            take = both(both(_shift(start_known, dx, dy), todo), ImageChops.invert(crop_known))
            if take.getbbox():
                crop_rgb = Image.composite(_shift(start_rgb, dx, dy), crop_rgb, take); crop_known = either(crop_known, take); progressed = True
        if not progressed: break
    rgb.paste(crop_rgb, box[:2])
    return rgb, count(minus(crop_target, crop_known))


def _rgba(rgb, alpha):
    layer = rgb.convert("RGB").convert("RGBA"); layer.putalpha(alpha); return layer


def recomposite(layers, size):
    canvas = Image.new("RGBA", size, (0, 0, 0, 255))
    for layer in layers: canvas = Image.alpha_composite(canvas, layer)
    return canvas.convert("RGB")


def error(first, second):
    """(mean, max) |difference| over the RGB channels, in 0-255 units."""
    diff = ImageChops.difference(first.convert("RGB"), second.convert("RGB"))
    return round(sum(ImageStat.Stat(diff).mean) / 3, 3), max(high for _, high in diff.getextrema())


def strip(layers, shifts, gap=10):
    """Three frames, camera left / centre / right: each layer slides by its shift; the widest shift is cropped from both sides."""
    width, height = layers[0].size; crop = max(shifts); frames = []
    for side in (-1, 0, 1):
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 255))
        for layer, shift in zip(layers, shifts): canvas = Image.alpha_composite(canvas, _shift(layer, side * shift, 0))
        frames.append(canvas.convert("RGB").crop((crop, 0, width - crop, height)))
    sheet = Image.new("RGB", (frames[0].size[0] * 3 + gap * 2, height), "white")
    for index, frame in enumerate(frames): sheet.paste(frame, (index * (frame.size[0] + gap), 0))
    return sheet if sheet.size[0] <= 2400 else sheet.resize((sheet.size[0] // 2, height // 2), Image.LANCZOS)


def layers(source, plate, isolate, polygons, parameters=PARAMETERS):
    """Route C2 on registered edits. Returns {images}, {record}: far (or None), mid, near, strip and every intermediate."""
    source = source.convert("RGB"); size = source.size; p = parameters
    near = near_matte(isolate, p)
    glass = polygon_mask(size, polygons)
    view = minus(glass, grow(near, p["view_guard_px"]))
    under = grow(near, p["under_px"]); ring = minus(minus(grow(near, p["match_ring_px"]), under), glass)
    matched, match = colour_match(plate.convert("RGB"), source, ring)
    blend = under.filter(ImageFilter.GaussianBlur(p["feather_px"]))
    mid = _rgba(Image.composite(matched, source, blend), ImageChops.invert(glass))
    near_layer = _rgba(source, near.filter(ImageFilter.GaussianBlur(p["near_blur_px"])))
    far, unfilled = None, 0
    if count(glass):
        filled, unfilled = ring_fill(source, view, grow(glass, p["far_ring_px"]))
        far = _rgba(filled, grow(glass, p["far_ring_px"]))
    stack = [layer for layer in (far, mid, near_layer) if layer is not None]
    mean, worst = error(recomposite(stack, size), source)
    shifts = p["shifts_px"][-len(stack):]
    total = size[0] * size[1]
    record = {"near_px": count(near), "near_percent": round(100 * count(near) / total, 2), "view_px": count(view), "view_percent": round(100 * count(glass) / total, 2),
              "far_unfilled_px": unfilled, "colour_match": match, "recomposite_mean_abs_error": mean, "recomposite_max_abs_error": worst,
              "layers": ["far", "mid", "near"] if far is not None else ["mid", "near"], "shifts_px": shifts}
    return {"far": far, "mid": mid, "near": near_layer, "strip": strip(stack, shifts), "near_matte": near, "view_mask": view, "plate_matched": matched}, record


def summary(record):
    layer_words = "far / mid / near" if "far" in record["layers"] else "mid / near (no far view marked)"
    return "%s layers recomposite to the source within %.2f/255 (worst pixel %d/255); near %.1f %% of the picture. Review the 3-frame strip; a number is not art acceptance." % (
        layer_words, record["recomposite_mean_abs_error"], record["recomposite_max_abs_error"], record["near_percent"])


def png_bytes(image):
    stream = io.BytesIO(); image.save(stream, "PNG"); return stream.getvalue()


# ---------------------------------------------------------------- route

def eligibility(width, height):
    """None when a picture can be split, else the reason shown on the disabled control."""
    if not (SIZE_LIMITS[0] <= width <= SIZE_LIMITS[1] and SIZE_LIMITS[0] <= height <= SIZE_LIMITS[1]):
        return "Parallax layers needs each side between %d and %d px; this picture is %d × %d." % (SIZE_LIMITS + (width, height))
    if width % SIZE_MULTIPLE or height % SIZE_MULTIPLE: return "Parallax layers needs sides on a %d px grid; this picture is %d × %d." % (SIZE_MULTIPLE, width, height)
    if width * height > MAX_PIXELS: return "Parallax layers needs at most %.1f megapixels (Klein edits at about one); this picture is %d × %d." % (MAX_PIXELS / 1e6, width, height)
    return None


def route(studio):
    routes = [preset for preset in studio.catalog()["presets"] if preset.get("parallax_route")]
    if len(routes) != 1: raise ValueError("No single parallax-layers recipe is registered in the catalog.")
    return routes[0]


route_problems = continuation.parallax_route_problems   # Pillow-free, so scripts/validate-repo.py runs in the payload lane


def words(stage, objects):
    return (PLATE_WORDS if stage == "plate" else ISOLATE_WORDS).format(objects=objects)


def plan_id(plan):
    body = {key: plan[key] for key in sorted(CLAIM_FIELDS - {"plan_id", "stage"})}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _polygons(value, width, height):
    """Boxes [x0, y0, x1, y1] or polygons [[x, y], ...] in source pixels -> polygons of whole numbers inside the picture."""
    if value is None: return []
    if not isinstance(value, list) or len(value) > MAX_VIEWS: raise ValueError("view takes at most %d boxes or polygons." % MAX_VIEWS)
    polygons = []
    for item in value:
        if isinstance(item, list) and len(item) == 4 and all(type(v) is int for v in item):
            x0, y0, x1, y1 = item
            if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height): raise ValueError("A view box must lie inside the %d × %d picture with x0 < x1 and y0 < y1." % (width, height))
            if (x1 - x0) < 8 or (y1 - y0) < 8: raise ValueError("A view box must be at least 8 px on each side.")
            polygons.append([[x0, y0], [x1 - 1, y0], [x1 - 1, y1 - 1], [x0, y1 - 1]]); continue   # a box's far edges are exclusive; a polygon fills its vertices
        if not isinstance(item, list) or not 3 <= len(item) <= MAX_POINTS or any(not isinstance(point, list) or len(point) != 2 or any(type(v) is not int for v in point) for point in item):
            raise ValueError("Each view is a box [x0, y0, x1, y1] or a polygon of 3 to %d [x, y] points." % MAX_POINTS)
        if any(not (0 <= x <= width and 0 <= y <= height) for x, y in item): raise ValueError("A view polygon must lie inside the %d × %d picture." % (width, height))
        polygons.append([list(point) for point in item])
    return polygons


def _objects(value):
    if not isinstance(value, str) or not value.strip(): raise ValueError("Name the foreground to lift out, e.g. the desk, the chair and the lamp.")
    text = " ".join(value.split())
    if len(text) > OBJECTS_LIMIT or re.search(r"[{}\[\]]", text): raise ValueError("The foreground is a short plain list (at most %d characters, no brackets or braces)." % OBJECTS_LIMIT)
    return text


def _source(studio, asset_id):
    context = continuation.source_context(studio, asset_id)
    raw = studio.assets.file(asset_id).read_bytes()
    if hashlib.sha256(raw).hexdigest() != context["sha256"]: raise ValueError("Source bytes changed. Restore the original asset before splitting it.")
    with Image.open(io.BytesIO(raw)) as decoded: return context, decoded.convert("RGB")


def source_status(studio, asset_id):
    context = continuation.source_context(studio, asset_id)
    reason = eligibility(context["width"], context["height"])
    return {"asset_id": context["asset_id"], "width": context["width"], "height": context["height"], "eligible": reason is None, "reason": reason,
            "flag": FLAG, "preset_id": route(studio)["id"], "max_views": MAX_VIEWS}


def stage_payload(plan, stage, context=None):
    claim = dict(copy.deepcopy(plan), stage=stage)
    return {"plan": copy.deepcopy(plan), "claim": claim, "stage": stage, "stage_name": STAGE_NAMES[stage], "other_stage": STAGES[1 - STAGES.index(stage)],
            "words": words(stage, plan["objects"]), "file": plan["source_file"], "width": plan["width"], "height": plan["height"],
            "preset_id": plan["preset_id"], "context": context, "flag": FLAG, "generation_submitted": False}


def prepare(studio, payload):
    """Attach one library picture as the edit source and return the plan with its clean-plate stage. Nothing is queued."""
    if not isinstance(payload, dict) or not set(payload) <= {"asset_id", "objects", "view"} or "asset_id" not in payload:
        raise ValueError("Parallax layers takes asset_id and objects, and optionally view.")
    objects = _objects(payload.get("objects")); preset = route(studio)
    context, source = _source(studio, payload["asset_id"])
    reason = eligibility(*source.size)
    if reason: raise ValueError(reason)
    polygons = _polygons(payload.get("view"), *source.size)
    attached = studio.asset_reference(context["asset_id"])
    if attached["sha256"] != context["sha256"]: raise ValueError("The source changed while it was attached. Press Make parallax layers again.")
    plan = {"version": VERSION, "preset_id": preset["id"], "source_asset_id": context["asset_id"], "source_sha256": context["sha256"],
            "source_file": attached["file"], "width": source.size[0], "height": source.size[1], "objects": objects, "view_polygons": polygons}
    plan["plan_id"] = plan_id(plan)
    return stage_payload(plan, "plate", context)


def _claim(claim):
    if not isinstance(claim, dict) or set(claim) != CLAIM_FIELDS or type(claim.get("version")) is not int or claim["version"] != VERSION or claim.get("stage") not in STAGES:
        raise ValueError("Invalid parallax plan. Press Make parallax layers on the source again.")
    for key in ("preset_id", "source_asset_id", "source_file", "objects"):
        if not isinstance(claim[key], str) or not claim[key] or len(claim[key]) > 255: raise ValueError("Invalid parallax plan field: " + key)
    if any(not isinstance(claim[key], str) or not re.fullmatch("[a-f0-9]{64}", claim[key]) for key in ("source_sha256", "plan_id")) \
            or not re.fullmatch(r"[0-9a-f]{32}_[A-Za-z0-9._-]+\.(?:png|jpg|webp)", claim["source_file"]):
        raise ValueError("Invalid parallax plan identity.")
    if any(type(claim[key]) is not int for key in ("width", "height")) or eligibility(claim["width"], claim["height"]):
        raise ValueError("Invalid parallax plan size. Press Make parallax layers again.")
    if _objects(claim["objects"]) != claim["objects"] or _polygons(claim["view_polygons"], claim["width"], claim["height"]) != claim["view_polygons"] or plan_id(claim) != claim["plan_id"]:
        raise ValueError("The parallax plan was altered. Press Make parallax layers again.")
    return claim


def validate(studio, payload, preset, graph, batch, check_runtime=False):
    """Refuse the parallax recipe without its plan, or a plan whose source, attached picture or size no longer hold."""
    claim = payload.get("parallax")
    if claim is None:
        if preset.get("parallax_route"):
            raise ValueError("%s starts from Make parallax layers on a picture in the Asset library; the authored example cannot be queued." % (preset.get("name") or preset.get("id")))
        return None
    if not preset.get("parallax_route"): raise ValueError("A parallax plan runs only on the parallax-layers recipe.")
    _claim(claim)
    if claim["preset_id"] != preset.get("id"): raise ValueError("This parallax plan was prepared for another recipe. Press Make parallax layers again.")
    if payload.get("continuation") is not None or payload.get("tile") is not None: raise ValueError("A parallax edit is neither a continuation nor a tile; leave those first.")
    if str(batch) != "1": raise ValueError("A parallax edit makes one picture per stage: set the batch count to 1.")
    parents = payload.get("parent_assets")
    if not isinstance(parents, list) or claim["source_asset_id"] not in parents: raise ValueError("The parallax source is missing from lineage.")
    name = claim["source_file"]
    try:
        node, field = preset["reference"]; bound = graph[str(node)]["inputs"][str(field)]
        sizes = [graph[str(preset[key][0])]["inputs"][str(preset[key][1])] for key in ("width", "height")]
    except (KeyError, TypeError, ValueError): raise ValueError("The parallax recipe has no valid picture or size binding.") from None
    if (payload.get("controls") or {}).get("reference") != name or bound != name:
        raise ValueError("Attach the prepared source picture, not another one. Press Make parallax layers again.")
    if sizes != [claim["width"], claim["height"]]:
        raise ValueError("A parallax edit draws at the source size, %d × %d. Press Make parallax layers again." % (claim["width"], claim["height"]))
    text = (payload.get("controls") or {}).get("positive")
    if not isinstance(text, str) or not text.strip(): raise ValueError("Say what the %s edit does before running it." % STAGE_NAMES[claim["stage"]])
    upload = studio.experiments / "uploads" / name
    if upload.is_symlink() or not upload.is_file() or hashlib.sha256(upload.read_bytes()).hexdigest() != claim["source_sha256"]:
        raise ValueError("The attached source picture changed or is missing. Press Make parallax layers again.")
    context = continuation.source_context(studio, claim["source_asset_id"])
    if context["sha256"] != claim["source_sha256"] or (context["width"], context["height"]) != (claim["width"], claim["height"]):
        raise ValueError("The parallax source changed. Press Make parallax layers on it again.")
    if check_runtime:
        runtime = Path(payload.get("comfy_root", studio.comfy_root)) / "input" / name
        if runtime.is_symlink() or not runtime.is_file() or hashlib.sha256(runtime.read_bytes()).hexdigest() != claim["source_sha256"]:
            raise ValueError("The source picture in ComfyUI's input folder changed or is missing. Press Make parallax layers again.")
    return dict(claim)


def next_stage(studio, payload):
    """The other stage of a submitted parallax edit, ready for Create. Nothing is queued."""
    if not isinstance(payload, dict) or not set(payload) <= {"job_id", "stage"}: raise ValueError("Next stage takes job_id and optionally stage.")
    job = studio.jobs.get(payload.get("job_id")) if isinstance(payload.get("job_id"), str) else None
    if not job: raise ValueError("Unknown job")
    claim = job.get("parallax")
    if not claim: raise ValueError("This job is not a parallax edit.")
    _claim(claim)
    stage = payload.get("stage", STAGES[1 - STAGES.index(claim["stage"])])
    if stage not in STAGES: raise ValueError("stage is plate or isolate.")
    context = continuation.source_context(studio, claim["source_asset_id"])
    if context["sha256"] != claim["source_sha256"]: raise ValueError("The parallax source changed. Press Make parallax layers on it again.")
    upload = studio.experiments / "uploads" / claim["source_file"]
    if upload.is_symlink() or not upload.is_file() or hashlib.sha256(upload.read_bytes()).hexdigest() != claim["source_sha256"]:
        raise ValueError("The attached source picture changed or is missing. Press Make parallax layers again.")
    plan = {key: value for key, value in claim.items() if key != "stage"}
    return stage_payload(plan, stage, context)


def finish_id(plate_job_id, isolate_job_id):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "asset-studio:parallax-finish:%s:%s" % (plate_job_id, isolate_job_id)))


def _image_output(job):
    images = [output for output in job.get("outputs", []) if output.get("media_type", "image") == "image"]
    if len(images) != 1 or not images[0].get("asset_id"):
        raise ValueError("The %s edit left %d saved pictures; a layer split needs exactly one." % (STAGE_NAMES[job["parallax"]["stage"]], sum(1 for o in images if o.get("asset_id"))))
    return images[0]


def sibling(studio, job):
    """The newest completed job of the other stage of the same plan, or None."""
    claim = job["parallax"]; other = STAGES[1 - STAGES.index(claim["stage"])]
    with studio.lock: jobs = list(studio.jobs.values())
    matches = [item for item in jobs if (item.get("parallax") or {}).get("plan_id") == claim["plan_id"] and item["parallax"].get("stage") == other and item.get("status") == "completed"]
    return max(matches, key=lambda item: (item.get("finished_at") or item.get("created_at") or 0, item["id"])) if matches else None


def finish(studio, job_id, other_job_id=None):
    """Register, split, measure and preview one completed plate + isolate pair. Idempotent per pair."""
    with _FINISH_LOCK:
        job = studio.jobs.get(job_id) if isinstance(job_id, str) else None
        if not job: raise ValueError("Unknown job")
        if not job.get("parallax"): raise ValueError("This job is not a parallax edit.")
        _claim(job["parallax"])
        if other_job_id is None: other = sibling(studio, job)
        else:
            other = studio.jobs.get(other_job_id) if isinstance(other_job_id, str) else None
            if not other or (other.get("parallax") or {}).get("plan_id") != job["parallax"]["plan_id"] or other["parallax"].get("stage") == job["parallax"]["stage"]:
                raise ValueError("The other job is not the other stage of this parallax plan.")
        if other is None:
            missing = STAGE_NAMES[STAGES[1 - STAGES.index(job["parallax"]["stage"])]]
            raise ValueError("Run the %s edit of this plan first; no layers were made." % missing)
        plate, isolate = (job, other) if job["parallax"]["stage"] == "plate" else (other, job)
        identifier = finish_id(plate["id"], isolate["id"])
        if identifier in studio.jobs:
            finished = studio.jobs[identifier]
            for item in (plate, isolate):
                if (item.get("parallax_finish") or {}).get("job_id") != identifier: _link(studio, item, finished)
            return finished
        for item in (plate, isolate):
            if item.get("status") != "completed": raise ValueError("Split the layers after both edits complete; the %s edit is %s." % (STAGE_NAMES[item["parallax"]["stage"]], item.get("status")))
        claim = plate["parallax"]; _claim(isolate["parallax"])
        context, source = _source(studio, claim["source_asset_id"])
        if context["sha256"] != claim["source_sha256"]: raise ValueError("The parallax source changed; no layers were made.")
        edits, records = {}, {}
        for item in (plate, isolate):
            output = _image_output(item); path, asset = studio.assets.file_entry(output["asset_id"]); raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != asset["sha256"]: raise ValueError("A saved edit changed; no layers were made.")
            with Image.open(io.BytesIO(raw)) as decoded: edits[item["parallax"]["stage"]] = (decoded.convert("RGB"), output, asset)
        white = (255, 255, 255)
        plate_registered, records["plate"] = register(source, edits["plate"][0], source)
        isolate_registered, records["isolate"] = register(source, edits["isolate"][0], white)
        images, record = layers(source, plate_registered, isolate_registered, claim["view_polygons"])
        record["registration"] = records; record["summary"] = summary(record)
        directory = studio.runs / identifier; directory.mkdir(parents=True, exist_ok=True)
        assets = [(name, images[name]) for name in ("far", "mid", "near") if images[name] is not None] + [("strip", images["strip"])]
        evidence = {"plate-registered.png": plate_registered, "isolate-registered.png": isolate_registered, "plate-matched.png": images["plate_matched"],
                    "near-matte.png": images["near_matte"], "view-mask.png": images["view_mask"]}
        files = {("parallax-strip.png" if name == "strip" else name + ".png"): png_bytes(image) for name, image in assets}
        files.update({name: png_bytes(image) for name, image in evidence.items()})
        for filename, data in files.items(): (directory / filename).write_bytes(data)
        hashes = {filename: hashlib.sha256(data).hexdigest() for filename, data in files.items()}
        stage_receipts = {}
        for item in (plate, isolate):
            _, output, asset = edits[item["parallax"]["stage"]]
            submission = next((entry for entry in item.get("submissions", []) if entry.get("prompt_id") == output.get("prompt_id")), {})
            stage_receipts[item["parallax"]["stage"]] = {"job_id": item["id"], "prompt_id": output.get("prompt_id"), "asset_id": output["asset_id"], "sha256": asset["sha256"],
                                                         "seed": output.get("seed"), "preset_id": item.get("preset_id"), "graph_path": item.get("graph_path"),
                                                         "controls": copy.deepcopy(item.get("controls")), "submitted_graph": copy.deepcopy(submission.get("graph"))}
        steps = ["Register each edit to the source: affine least squares on %d px edge patches (coarse 1/4, then +/-3 px, sub-pixel), residual outliers dropped" % REGISTRATION["patch_px"],
                 "Near matte: isolate pixels darker than %d, opened %d px, closed %d px, holes filled, parts under %d px dropped" % tuple(PARAMETERS[k] for k in ("white_below", "open_px", "close_px", "min_part_px")),
                 "Mid: source, with the plate colour-matched in a %d px ring and blended in under the matte grown %d px through a %d px feather; the marked view cut out" % tuple(PARAMETERS[k] for k in ("match_ring_px", "under_px", "feather_px")),
                 "Far: the marked view minus the matte grown %d px, filled %d px beyond its frame from the nearest view pixel" % (PARAMETERS["view_guard_px"], PARAMETERS["far_ring_px"]) if "far" in record["layers"] else "No far view marked: no far layer",
                 "Near: source with the matte blurred %.1f px as alpha" % PARAMETERS["near_blur_px"],
                 "Recomposite far/mid/near over black and compare with the source; 3-frame strip at shifts %s px" % record["shifts_px"]]
        receipt = {"version": VERSION, "plan": copy.deepcopy({k: v for k, v in claim.items() if k != "stage"}), "stages": stage_receipts, "parameters": copy.deepcopy(PARAMETERS),
                   "registration_settings": copy.deepcopy(REGISTRATION), "steps": steps, "metrics": record, "files": hashes,
                   "method": "experiments/curated/background-lab-20260927 route C2 (PR #1222)", "finished_at": time.time()}
        shifts = dict(zip(record["layers"], record["shifts_px"]))
        prompt_id = stage_receipts["plate"]["prompt_id"]
        outputs = [{"filename": name + ".png", "run_file": name + ".png", "type": "output", "media_type": "image", "prompt_id": prompt_id,
                    "parallax": {"layer": name, "shift_px": shifts[name], "plan_id": claim["plan_id"], "summary": record["summary"]}} for name, _ in assets if name != "strip"]
        outputs.append({"filename": "parallax-strip.png", "run_file": "parallax-strip.png", "type": "output", "media_type": "image", "prompt_id": prompt_id,
                        "parallax": {"layer": "strip", "plan_id": claim["plan_id"], "summary": record["summary"]}})
        finished = {"id": identifier, "operation": OPERATION, "status": "completed", "created_at": time.time(), "preset_id": "parallax-layers",
                    "preset_name": "Parallax layers", "controls": {}, "batch_count": 1, "prompt_ids": [], "submissions": [], "references": [],
                    "parent_assets": [claim["source_asset_id"], edits["plate"][1]["asset_id"], edits["isolate"][1]["asset_id"]], "graph_path": "", "graph": {},
                    "parallax_receipt": receipt, "outputs": outputs,
                    "message": "Parallax layers split from plate prompt %s and isolate prompt %s. %s No generation was submitted." % (prompt_id, stage_receipts["isolate"]["prompt_id"], record["summary"])}
        studio.index_outputs(finished); studio._save(finished)
        with studio.lock: studio.jobs[identifier] = finished
        for item in (plate, isolate): _link(studio, item, finished, save=False)   # both links hold in memory before either save
        for item in (plate, isolate): studio._save(item)
        return finished


def _link(studio, job, finished, save=True):
    """Point a stage at its newest layer split; the in-memory link holds even when the save fails."""
    outputs = finished.get("outputs") or []
    with studio.lock:
        job["parallax_finish"] = {"job_id": finished["id"], "asset_ids": {(o.get("parallax") or {}).get("layer"): o.get("asset_id") for o in outputs},
                                  "summary": ((outputs[0].get("parallax") or {}).get("summary") if outputs else None)}
    if save: studio._save(job)


def finish_after_run(studio, job):
    """The worker's hook after a stage completes: split once both stages are in, and record a failure instead of raising."""
    if not job.get("parallax") or job.get("status") != "completed" or (job.get("parallax_finish") or {}).get("job_id"): return
    try:
        _claim(job["parallax"])
        if sibling(studio, job) is None: return      # the other edit has not completed yet; its own completion finishes the pair
        finish(studio, job["id"])
    except Exception as exc:  # a stage's own outcome never changes because its split failed
        if (job.get("parallax_finish") or {}).get("job_id") in studio.jobs: return   # the layers exist; only saving the link failed
        job["parallax_finish"] = {"error": str(exc)[:300], "failed_at": time.time()}
        try: studio._save(job)
        except Exception: pass
