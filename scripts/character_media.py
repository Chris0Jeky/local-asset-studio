#!/usr/bin/env python3
"""Offline intake, lossless rectangular extraction, and review-card composition.

No model execution, background removal, semantic approval, or animation synthesis.
Paths in manifests are confined to the workspace. New output folders only.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import sys
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from scripts.character_study import read_json, relative

MAX_PIXELS = 24_000_000
MAX_PANELS = 64
ID_RE = re.compile(r"[a-z][a-z0-9-]{1,63}\Z")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def confined(root: Path, value: str) -> Path:
    relative(value)
    p = Path(value)
    root = root.resolve(strict=True)
    candidate = (root / p).resolve(strict=True)
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise ValueError('File must resolve inside the workspace')
    return candidate


def open_png(path: Path) -> Image.Image:
    with Image.open(path) as im:
        if im.format != 'PNG' or im.width * im.height > MAX_PIXELS:
            raise ValueError('Expected a PNG of at most 24 million pixels')
        if getattr(im, 'n_frames', 1) != 1:
            raise ValueError('Animated PNGs require a separate intake route')
        im.load()
        return im.copy()


def facts(path: Path) -> dict[str, Any]:
    im = open_png(path)
    rgba = im.convert('RGBA')
    hist = rgba.getchannel('A').histogram()
    pixels = im.width * im.height
    minimum, maximum = rgba.getchannel('A').getextrema()
    return {
        'sha256': digest(path), 'bytes': path.stat().st_size,
        'width': im.width, 'height': im.height, 'mode': im.mode,
        'alpha_min': minimum, 'alpha_max': maximum,
        'nonopaque_pixels': sum(hist[:255]),
        'transparent_pixels': hist[0],
        'nonopaque_fraction': sum(hist[:255]) / pixels,
        'has_nonopaque_pixels': minimum < 255,
        'embedded_metadata_keys': sorted(im.info),
        'semantic_quality': 'not_assessed',
        'usable_game_alpha': 'not_assessed' if minimum < 255 else 'absent',
    }


def load_manifest(root: Path, manifest: Path) -> tuple[dict, Path, Image.Image]:
    if manifest.stat().st_size > 1_000_000:
        raise ValueError('Manifest is too large')
    data = read_json(manifest)
    if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data.get('schema_version') != 1 or not isinstance(data.get('sheet_id'), str) or not ID_RE.fullmatch(data['sheet_id']):
        raise ValueError('Invalid manifest version or sheet ID')
    source = confined(root, data['source']['path'])
    if digest(source) != data['source']['sha256']:
        raise ValueError('Source SHA-256 mismatch')
    im = open_png(source)
    if [im.width, im.height] != data['source']['size']:
        raise ValueError('Source dimensions do not match the manifest')
    panels = data.get('panels')
    if not isinstance(panels, list) or not 1 <= len(panels) <= MAX_PANELS:
        raise ValueError('Expected 1 to 64 panels')
    seen: set[str] = set()
    for panel in panels:
        if not isinstance(panel, dict): raise ValueError('Panel must be an object')
        pid = panel.get('id', '')
        if not isinstance(pid, str) or not ID_RE.fullmatch(pid) or pid in seen:
            raise ValueError('Invalid or duplicate panel ID')
        seen.add(pid)
        box = panel.get('box')
        if not isinstance(box, list) or len(box) != 4 or any(type(x) is not int for x in box):
            raise ValueError('Box must have four integer coordinates')
        x0, y0, x1, y1 = box
        if not (0 <= x0 < x1 <= im.width and 0 <= y0 < y1 <= im.height):
            raise ValueError('Crop box is outside source bounds')
        if panel.get('role') not in {'view', 'portrait', 'action'}:
            raise ValueError('Invalid panel role')
        if not isinstance(panel.get('label'), str) or not 1 <= len(panel['label']) <= 64:
            raise ValueError('Invalid panel label')
    return data, source, im


def write_json(path: Path, data: Any) -> None:
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n')


def extract(root: Path, manifest: Path, output: Path) -> dict:
    """Extract pixel-exact crops to a new directory, recording scope limitations.

    Assumes a single trusted local writer; this is not a hostile multi-user sandbox.
    """
    data, source, im = load_manifest(root, manifest)
    if output.exists() or output.is_symlink():
        raise FileExistsError('Output exists; choose a new output folder')
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.cardlab-', dir=output.parent))
    try:
        records = []
        for panel in data['panels']:
            filename = panel['id'] + '.png'
            crop = im.crop(tuple(panel['box']))
            crop.save(stage / filename)
            records.append({
                **panel, 'path': filename, 'sha256': digest(stage / filename),
                'width': crop.width, 'height': crop.height,
                'operation': 'rectangular_crop_without_resampling',
                'alpha_min': crop.convert('RGBA').getchannel('A').getextrema()[0],
                'review_state': 'unreviewed', 'engine_ready': False,
            })
        receipt = {
            'schema_version': 1, 'sheet_id': data['sheet_id'],
            'source': data['source'], 'manifest_sha256': digest(manifest),
            'source_intake': facts(source), 'panels': records,
            'limitations': [
                'Source backgrounds and shadows are retained; no segmentation was performed.',
                'Overlapping artwork may remain in rectangular crops.',
                'Labels, approval, clean topology and animation continuity are not inferred.',
                'Hashes establish byte identity, not artistic correctness or reviewer authority.',
            ],
        }
        write_json(stage / 'extraction.json', receipt)
        # Single-writer publish; refuse a known pre-existing destination.
        if output.exists() or output.is_symlink():
            raise FileExistsError('Output appeared during processing')
        stage.rename(output)
        return receipt
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    # Pillow's bundled default: no host-font lookup or redistribution. Record
    # Pillow version in receipts; layout determinism is scoped to that runtime.
    return ImageFont.load_default(size=size)


def compose(extracted: Path, output: Path) -> dict:
    """Compose the 4-view / 2-portrait / 7-pose layout as an opaque REVIEW card.

    Resamples for display only. Does not change extracted source panels or infer pivots.
    """
    receipt_path = extracted / 'extraction.json'
    if receipt_path.stat().st_size > 1_000_000:
        raise ValueError('Receipt too large')
    data = read_json(receipt_path)
    if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != 1 or not isinstance(data.get('panels'), list) or len(data['panels']) != 13:
        raise ValueError('Expected a bounded extraction receipt v1')
    seen = set()
    for panel in data['panels']:
        if not isinstance(panel, dict) or not isinstance(panel.get('id'), str) or not ID_RE.fullmatch(panel['id']) or panel['id'] in seen:
            raise ValueError('Invalid/duplicate composition panel')
        seen.add(panel['id'])
        if not isinstance(panel.get('label'), str) or not 1 <= len(panel['label']) <= 64:
            raise ValueError('Invalid composition label')
    counts = {role: sum(p.get('role') == role for p in data['panels'])
              for role in ['view', 'portrait', 'action']}
    if counts != {'view': 4, 'portrait': 2, 'action': 7}:
        raise ValueError('This demonstration layout requires four views, two portraits, seven actions')
    canvas = Image.new('RGB', (1800, 1330), '#edf0f2')
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 1800, 153), fill='#102b3a')
    draw.text((40, 22), 'CHARACTER / REVIEW ATLAS', font=font(38, True), fill='white')
    draw.text((42, 77), 'Deterministic composition from your supplied artwork', font=font(22), fill='#c4dce3')
    draw.text((42, 110), 'No new model generation  |  Crops are unreviewed  |  Not an animation sheet', font=font(18), fill='#c4dce3')
    placements = []
    role_index = {'view': 0, 'portrait': 0, 'action': 0}
    for panel in data['panels']:
        p = confined(extracted, panel['path'])
        if digest(p) != panel['sha256']:
            raise ValueError('Panel SHA-256 mismatch')
        im = open_png(p).convert('RGBA')
        role = panel['role']
        n = role_index[role]
        role_index[role] += 1
        if role == 'view':
            x, y, w, h = 36 + n * 339, 180, 325, 625
        elif role == 'portrait':
            x, y, w, h = 1392, 180 + n * 320, 372, 305
        else:
            x, y, w, h = 36 + n * 249, 876, 235, 335
        draw.rounded_rectangle((x, y, x+w, y+h), radius=12, fill='white', outline='#d0d9dd', width=2)
        max_w, max_h = w - 12, h - 46
        # Review thumbnails may be enlarged; no additional details are synthesized.
        thumb = ImageOps.contain(im, (max_w, max_h), method=Image.Resampling.LANCZOS)
        tx, ty = x + (w-thumb.width)//2, y + 6 + (max_h-thumb.height)//2
        canvas.paste(thumb, (tx, ty), thumb)
        draw.text((x+12, y+h-31), panel['label'], font=font(18, True), fill='#193b4a')
        placements.append({'panel_id': panel['id'], 'source_sha256': panel['sha256'],
                           'paste_xy': [tx, ty], 'display_size': list(thumb.size)})
    draw.text((38, 825), 'POSE LIBRARY / illustrative key poses, not timed frames', font=font(22, True), fill='#193b4a')
    draw.text((38, 1242), 'Art, margins, type and layout can evolve independently. This card was assembled with Pillow.', font=font(21), fill='#193b4a')
    draw.text((38, 1277), 'Opaque source backgrounds retained. Original pixels remain in the extraction folder.', font=font(18), fill='#506c76')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as f:
        canvas.save(f, format='PNG')
    return {'schema_version': 1, 'operation': 'review_card_composition',
            'source_receipt_sha256': digest(receipt_path), 'output_sha256': digest(output),
            'output_size': list(canvas.size), 'placements': placements,
            'pillow_version': Image.__version__, 'font': 'Pillow bundled default',
            'neural_inference': False, 'semantic_approval': False, 'engine_ready': False}


def protected_composite(source: Path, candidate: Path, mask: Path, output: Path) -> dict:
    """Explicit L-mask convention: 0 preserves source; 255 replaces with candidate.

    Source and candidate must share dimensions and embedded ICC bytes. This is
    decoded RGBA preservation, not perceptually linear blending or byte-identical
    PNG metadata retention. Comfy's inverse-alpha convention is NOT assumed.
    """
    original = open_png(source); edited = open_png(candidate); matte = open_png(mask)
    if original.mode not in {'RGB', 'RGBA'} or edited.mode not in {'RGB', 'RGBA'}:
        raise ValueError('Use RGB/RGBA source and candidate PNGs')
    if matte.mode != 'L' or original.size != edited.size or matte.size != original.size:
        raise ValueError('Use an explicit grayscale L mask of the same dimensions')
    if original.info.get('icc_profile') != edited.info.get('icc_profile'):
        raise ValueError('Source/candidate ICC profiles differ; normalize explicitly first')
    histogram = matte.histogram()
    if histogram[0] == original.width * original.height: raise ValueError('Empty repair mask')
    if histogram[0] == 0: raise ValueError('Protected repair must leave some exactly preserved pixels')
    result = Image.composite(edited.convert('RGBA'), original.convert('RGBA'), matte)
    if output.exists() or output.is_symlink(): raise FileExistsError('Choose a new output image')
    output.parent.mkdir(parents=True, exist_ok=True)
    options = {'icc_profile': original.info['icc_profile']} if 'icc_profile' in original.info else {}
    with output.open('xb') as stream: result.save(stream, format='PNG', **options)
    return {'schema_version': 1, 'operation': 'protected_composite',
            'source_sha256': digest(source), 'candidate_sha256': digest(candidate), 'mask_sha256': digest(mask),
            'output_sha256': digest(output), 'mask_convention': '0=preserve;255=replace',
            'exactly_preserved_pixels': histogram[0], 'partially_blended_pixels': sum(histogram[1:255]),
            'decoded_pixel_sha256': hashlib.sha256(result.tobytes()).hexdigest(),
            'pillow_version': Image.__version__, 'neural_inference': False, 'semantic_approval': False}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    i = sub.add_parser('inspect'); i.add_argument('image', type=Path)
    e = sub.add_parser('extract')
    e.add_argument('--root', required=True, type=Path)
    e.add_argument('--manifest', required=True, type=Path)
    e.add_argument('--out', required=True, type=Path)
    c = sub.add_parser('compose')
    c.add_argument('--extracted', required=True, type=Path)
    c.add_argument('--out', required=True, type=Path)
    r = sub.add_parser('protected-composite')
    for name in ('source', 'candidate', 'mask', 'out'): r.add_argument('--' + name, required=True, type=Path)
    args = p.parse_args()
    try:
        if args.command == 'inspect': result = facts(args.image)
        elif args.command == 'extract': result = extract(args.root, args.manifest, args.out)
        elif args.command == 'compose': result = compose(args.extracted, args.out)
        else: result = protected_composite(args.source, args.candidate, args.mask, args.out)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        p.exit(2, f'character-media: {exc}\n')

if __name__ == '__main__':
    raise SystemExit(main())
