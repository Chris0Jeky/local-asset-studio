"""Deterministic asset finishing. Optional Pillow; no generation, network or app control.
PNG source frames are never resized/trimmed. OpenRaster supports flat normal RGBA layers.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import warnings
import xml.etree.ElementTree as ET
import zipfile
from game_asset_pipeline import read_json, require, inside, integer, text, slug, sha, file_sha, write_json

MAX_PIXELS = 16 * 1024 * 1024
MAX_FILE = 64 * 1024 * 1024
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def pil():
    from PIL import Image
    return Image


def image(root, entry):
    """Hash and decode the same bounded bytes; metadata and pixels cannot disagree."""
    p = inside(root, entry['path'])
    with p.open('rb') as f: raw = f.read(MAX_FILE + 1)
    require(len(raw) <= MAX_FILE, 'Input image exceeds 64 MiB')
    require(hashlib.sha256(raw).hexdigest() == entry.get('sha256'), 'Image hash mismatch')
    Image = pil()
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(raw)) as source:
            require(source.format == 'PNG', 'Use explicit PNG interchange')
            require(source.width * source.height <= MAX_PIXELS, 'Image exceeds pixel budget')
            require(source.mode == 'RGBA', 'Expected RGBA PNG; convert explicitly before packaging')
            require(getattr(source, 'n_frames', 1) == 1, 'Animated PNG is not a frame or flat layer')
            require(not source.info.get('icc_profile'), 'Convert tagged images to agreed sRGB first')
            source.load(); return source.copy()


def size(value):
    require(isinstance(value, list) and len(value) == 2, 'Expected [width,height]')
    for x in value: integer(x, 1, 8192, 'dimension')
    require(value[0] * value[1] <= MAX_PIXELS, 'Canvas exceeds pixel budget')
    return tuple(value)


def validate_frames(manifest):
    require(manifest.get('schema_version') == 1, 'Expected frame manifest schema 1')
    dims = size(manifest.get('canvas'))
    anchor = manifest.get('anchor')
    require(isinstance(anchor, list) and len(anchor) == 2, 'Expected anchor [x,y]')
    for v, limit in zip(anchor, dims): integer(v, 0, limit, 'anchor')
    require(type(manifest.get('loop')) is bool, 'Explicit boolean loop required')
    slug(manifest.get('clip'))
    frames = manifest.get('frames')
    require(isinstance(frames, list) and 1 <= len(frames) <= 512, 'Expected 1..512 frames')
    seen = set()
    for frame in frames:
        slug(frame.get('id')); require(frame['id'] not in seen, 'Duplicate frame ID'); seen.add(frame['id'])
        integer(frame.get('duration_ms'), 1, 60000, 'duration_ms')
        require(type(frame.get('allow_empty', False)) is bool, 'allow_empty must be boolean')
    return dims


def atlas(manifest, root, output, columns=8, padding=2, extrude=1):
    Image = pil(); w, h = validate_frames(manifest)
    integer(columns, 1, 64, 'columns'); integer(padding, 0, 16, 'padding')
    integer(extrude, 0, padding, 'extrude')
    columns = min(columns, len(manifest['frames']))
    rows = math.ceil(len(manifest['frames']) / columns)
    tw, th = w + padding * 2, h + padding * 2
    require(tw * columns * th * rows <= MAX_PIXELS, 'Atlas exceeds pixel budget')
    sheet = Image.new('RGBA', (tw * columns, th * rows))
    records = []; warnings_out = []; pixels_seen = {}
    for i, frame in enumerate(manifest['frames']):
        im = image(root, frame); require(im.size == (w, h), 'Frame canvas mismatch; do not independently trim')
        box = im.getchannel('A').getbbox()
        require(box is not None or frame.get('allow_empty', False), 'Empty frame requires explicit allow_empty')
        if box and (box[0] == 0 or box[1] == 0 or box[2] == w or box[3] == h):
            warnings_out.append(f"{frame['id']}: visible pixels touch logical frame edge; inspect clipping")
        phash = hashlib.sha256(im.tobytes()).hexdigest()
        if phash in pixels_seen: warnings_out.append(f"{frame['id']}: same pixels as {pixels_seen[phash]}; may be an intentional hold")
        pixels_seen[phash] = frame['id']
        x, y = (i % columns) * tw + padding, (i // columns) * th + padding
        sheet.paste(im, (x, y))  # Copy RGBA bytes, not alpha-composite twice.
        if extrude:
            e = extrude
            # Extrusion duplicates edge bytes, not an interpolated/premultiplied colour.
            sheet.paste(im.crop((0, 0, w, 1)).resize((w, e), Image.Resampling.NEAREST), (x, y-e))
            sheet.paste(im.crop((0, h-1, w, h)).resize((w, e), Image.Resampling.NEAREST), (x, y+h))
            sheet.paste(im.crop((0, 0, 1, h)).resize((e, h), Image.Resampling.NEAREST), (x-e, y))
            sheet.paste(im.crop((w-1, 0, w, h)).resize((e, h), Image.Resampling.NEAREST), (x+w, y))
            for sx, sy, dx, dy in ((0, 0, x-e, y-e), (w-1, 0, x+w, y-e),
                                  (0, h-1, x-e, y+h), (w-1, h-1, x+w, y+h)):
                sheet.paste(Image.new('RGBA', (e,e), im.getpixel((sx,sy))), (dx,dy))
        require(sheet.crop((x,y,x+w,y+h)).tobytes() == im.tobytes(), 'Internal atlas round-trip failed')
        records.append({'id':frame['id'], 'region':[x,y,w,h], 'duration_ms':frame['duration_ms'],
                        'anchor':manifest['anchor'], 'source':frame, 'pixel_sha256':phash})
    folder = Path(output); folder.mkdir(parents=True, exist_ok=False)
    (folder / '.incomplete').write_text('Do not consume until manifest.json exists and this marker is absent.\n')
    sheet.save(folder/'atlas.png')
    payload = {'schema_version':1, 'kind':'sprite_atlas', 'clip':manifest['clip'], 'loop':manifest['loop'],
               'logical_canvas':[w,h], 'anchor':manifest['anchor'], 'atlas':'atlas.png',
               'atlas_sha256':file_sha(folder/'atlas.png'), 'dimensions':list(sheet.size),
               'padding':padding, 'extrude':extrude, 'frames':records, 'input_manifest_sha256':sha(manifest),
               'qa':{'pixel_roundtrip':'passed','warnings':warnings_out,'motion_semantics':'not_checked'}}
    write_json(payload, folder/'manifest.json'); (folder/'.incomplete').unlink()
    return payload


def png_bytes(im):
    buf = io.BytesIO(); im.save(buf, format='PNG'); return buf.getvalue()


ALPHA_DUST_BELOW = 8
ALPHA_SOLID_FROM = 224


def alpha_bands(im):
    """Count alpha pixels per finishing band; the 8..223 edge band is never touched."""
    require(im.mode == 'RGBA', 'Alpha report needs RGBA pixels')
    hist = im.getchannel('A').histogram()
    return {'transparent': sum(hist[0:1]), 'dust': sum(hist[1:ALPHA_DUST_BELOW]),
            'edge': sum(hist[ALPHA_DUST_BELOW:ALPHA_SOLID_FROM]),
            'body': sum(hist[ALPHA_SOLID_FROM:255]), 'opaque': hist[255]}


def matte_components(im):
    """Count 4-connected alpha>0 regions with a deterministic flood fill."""
    require(im.mode == 'RGBA', 'Alpha report needs RGBA pixels')
    w, h = im.size; mask = im.getchannel('A').tobytes(); seen = bytearray(w * h)
    found = 0; largest = 0
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if seen[i] or not mask[i]: continue
            found += 1; size = 0; stack = [i]; seen[i] = 1
            while stack:
                j = stack.pop(); size += 1
                jy, jx = divmod(j, w)
                if jx > 0 and mask[j - 1] and not seen[j - 1]: seen[j - 1] = 1; stack.append(j - 1)
                if jx + 1 < w and mask[j + 1] and not seen[j + 1]: seen[j + 1] = 1; stack.append(j + 1)
                if jy > 0 and mask[j - w] and not seen[j - w]: seen[j - w] = 1; stack.append(j - w)
                if jy + 1 < h and mask[j + w] and not seen[j + w]: seen[j + w] = 1; stack.append(j + w)
            largest = max(largest, size)
    return {'components': found, 'largest_component': largest}


def alpha_report(im):
    box = im.getchannel('A').getbbox()
    report = {'size': list(im.size), 'bbox': list(box) if box else None, 'bands': alpha_bands(im)}
    report.update(matte_components(im))
    return report


def alpha_cleanup(im):
    """Snap alpha below 8 to 0 and at/above 224 to 255; RGB and the edge band pass through byte-identical."""
    require(im.mode == 'RGBA', 'Alpha cleanup needs RGBA pixels')
    table = bytes([0] * ALPHA_DUST_BELOW + list(range(ALPHA_DUST_BELOW, ALPHA_SOLID_FROM)) + [255] * (256 - ALPHA_SOLID_FROM))
    out = im.copy(); out.putalpha(im.getchannel('A').point(table)); return out


def to_rgb(im):
    """Drop a spurious alpha channel; RGB bytes pass through unchanged."""
    require(im.mode == 'RGBA', 'RGB conversion needs RGBA pixels')
    return im.convert('RGB')


def decode_png(raw, what='Input image'):
    Image = pil()
    require(len(raw) <= MAX_FILE, f'{what} exceeds 64 MiB')
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(raw)) as source:
            require(source.format == 'PNG', 'Use explicit PNG interchange')
            require(source.width * source.height <= MAX_PIXELS, f'{what} exceeds pixel budget')
            require(getattr(source, 'n_frames', 1) == 1, 'Animated PNG is not a finishing input')
            require(not source.info.get('icc_profile'), 'Convert tagged images to agreed sRGB first')
            require(source.mode == 'RGBA', 'Expected RGBA PNG; convert explicitly before finishing')
            source.load(); return source.copy()


def cleanup(source, output, mode='rgba-cleanup', evidence=None):
    """Explicit finishing step: clean alpha dust or drop a spurious channel. Never overwrites."""
    require(mode in ('rgba-cleanup', 'to-rgb'), 'Unknown cleanup mode')
    require(evidence is None or not Path(evidence).exists(), 'Evidence file exists; outputs are never overwritten')
    with Path(source).open('rb') as stream: raw = stream.read(MAX_FILE + 1)
    before_image = decode_png(raw)
    before = alpha_report(before_image)
    after_image = alpha_cleanup(before_image) if mode == 'rgba-cleanup' else to_rgb(before_image)
    after = alpha_report(after_image) if mode == 'rgba-cleanup' else {'mode': 'RGB', 'size': list(after_image.size)}
    out = Path(output)
    with out.open('xb') as stream: after_image.save(stream, format='PNG')
    record = {'schema_version': 1, 'kind': 'alpha_cleanup', 'mode': mode,
              'thresholds': {'dust_below': ALPHA_DUST_BELOW, 'solid_from': ALPHA_SOLID_FROM},
              'input': str(source), 'input_sha256': hashlib.sha256(raw).hexdigest(),
              'output': str(out), 'output_sha256': file_sha(out),
              'before': before, 'after': after}
    if evidence:
        try: write_json(record, evidence)
        except OSError: out.unlink(missing_ok=True); raise
    return record


def zip_entry(archive, name, data, compress_type=zipfile.ZIP_DEFLATED):
    """Write fixed ZIP metadata so identical layer inputs reproduce byte-for-byte."""
    info = zipfile.ZipInfo(name, date_time=ZIP_EPOCH)
    info.compress_type = compress_type
    info.create_system = 3
    info.external_attr = 0o600 << 16
    archive.writestr(info, data)


def ora(manifest, root, output):
    Image = pil(); dims = size(manifest.get('canvas'))
    require(manifest.get('schema_version') == 1, 'Expected layer schema 1')
    layers = manifest.get('layers')
    require(isinstance(layers, list) and 1 <= len(layers) <= 64, 'Expected 1..64 layers')
    require(dims[0] * dims[1] * len(layers) <= MAX_PIXELS * 4, 'Layer stack exceeds memory budget')
    prepared = []; seen = set()
    for layer in layers:
        slug(layer.get('id')); require(layer['id'] not in seen, 'Duplicate layer ID'); seen.add(layer['id'])
        text(layer.get('name'), 'layer name')
        require(layer.get('blend', 'normal') == 'normal', 'Only normal src-over layers supported')
        require(type(layer.get('visible', True)) is bool, 'visible must be boolean')
        im = image(root, layer); require(im.size == dims, 'Layer canvas mismatch')
        prepared.append((layer, im))
    merged = Image.new('RGBA', dims)
    for layer, im in reversed(prepared):  # Manifest and ORA are topmost first.
        if layer.get('visible', True): merged = Image.alpha_composite(merged, im)
    doc = ET.Element('image', {'version':'0.0.6','w':str(dims[0]),'h':str(dims[1]),'name':manifest.get('name','Asset layers')})
    stack = ET.SubElement(doc, 'stack')
    for index, (layer, _) in enumerate(prepared):
        ET.SubElement(stack, 'layer', {'name':layer['name'],'src':f'data/layer{index:03d}.png',
                      'x':'0','y':'0','opacity':'1.0','visibility':'visible' if layer.get('visible',True) else 'hidden',
                      'composite-op':'svg:src-over'})
    thumb = merged.copy(); thumb.thumbnail((256,256), Image.Resampling.LANCZOS)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as out:
        zip_entry(out, 'mimetype', b'image/openraster', zipfile.ZIP_STORED)
        zip_entry(out, 'stack.xml', ET.tostring(doc, encoding='utf-8', xml_declaration=True))
        for i, (_, im) in enumerate(prepared): zip_entry(out, f'data/layer{i:03d}.png', png_bytes(im))
        zip_entry(out, 'mergedimage.png', png_bytes(merged))
        zip_entry(out, 'Thumbnails/thumbnail.png', png_bytes(thumb))
    return {'output':str(output),'sha256':file_sha(output),'layers':len(prepared),
            'format':'OpenRaster flat normal RGBA layers','krita_live_import_tested':False,
            'not_preserved':['animation','rig','groups','masks','non-normal blend modes','ICC profiles']}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='cmd',required=True)
    for cmd in ('atlas','ora'):
        child=sub.add_parser(cmd); child.add_argument('manifest'); child.add_argument('--workspace',required=True)
        child.add_argument('--out',required=True)
        if cmd=='atlas':
            child.add_argument('--columns',type=int,default=8); child.add_argument('--padding',type=int,default=2)
            child.add_argument('--extrude',type=int,default=1)
    child=sub.add_parser('cleanup'); child.add_argument('input'); child.add_argument('--out',required=True)
    child.add_argument('--mode',default='rgba-cleanup'); child.add_argument('--evidence')
    args=p.parse_args(argv)
    try:
        if args.cmd=='cleanup': value=cleanup(args.input,args.out,args.mode,args.evidence)
        else:
            m=read_json(args.manifest)
            if args.cmd=='atlas': value=atlas(m,args.workspace,args.out,args.columns,args.padding,args.extrude)
            else: value=ora(m,args.workspace,args.out)
        write_json(value);return 0
    except (OSError,ValueError,TypeError,KeyError,ImportError,Warning) as exc:
        print(json.dumps({'error':str(exc)}),file=sys.stderr);return 2


if __name__=='__main__': raise SystemExit(main())
