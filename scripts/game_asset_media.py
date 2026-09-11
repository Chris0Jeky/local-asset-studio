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
            sheet.paste(im.crop((0, 0, w, 1)).resize((w, e)), (x, y-e))
            sheet.paste(im.crop((0, h-1, w, h)).resize((w, e)), (x, y+h))
            sheet.paste(im.crop((0, 0, 1, h)).resize((e, h)), (x-e, y))
            sheet.paste(im.crop((w-1, 0, w, h)).resize((e, h)), (x+w, y))
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
        out.writestr('mimetype', b'image/openraster', compress_type=zipfile.ZIP_STORED)
        out.writestr('stack.xml', ET.tostring(doc, encoding='utf-8', xml_declaration=True))
        for i, (_, im) in enumerate(prepared): out.writestr(f'data/layer{i:03d}.png', png_bytes(im))
        out.writestr('mergedimage.png', png_bytes(merged))
        out.writestr('Thumbnails/thumbnail.png', png_bytes(thumb))
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
    args=p.parse_args(argv)
    try:
        m=read_json(args.manifest)
        if args.cmd=='atlas': value=atlas(m,args.workspace,args.out,args.columns,args.padding,args.extrude)
        else: value=ora(m,args.workspace,args.out)
        write_json(value);return 0
    except (OSError,ValueError,TypeError,KeyError,ImportError,Warning) as exc:
        print(json.dumps({'error':str(exc)}),file=sys.stderr);return 2


if __name__=='__main__': raise SystemExit(main())
