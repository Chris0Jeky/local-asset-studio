#!/usr/bin/env python3
"""Explicit, bounded PNG normalization into a new offline repair packet.

No inference, Workspace mutation, model installation or creative approval.
Preserves encoded colour samples/chunks; does not certify or convert colour.
"""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
import zlib

from PIL import Image, ImageOps

MAX_SOURCE_BYTES = 20 * 1024 * 1024
MAX_OUTPUT_BYTES = 100 * 1024 * 1024
MAX_METADATA_BYTES = 1024 * 1024
MAX_PIXELS = 24_000_000
MAX_CHUNKS = 8192
SIGNATURE = b'\x89PNG\r\n\x1a\n'
COLOUR = (b'gAMA', b'cHRM', b'sRGB', b'iCCP')
SCHEMA = 'studio.repair-source/v1'
NORMALIZER = 'png-rgba8-orientation-v1'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _inflate(data: bytes, remaining: int) -> bytes:
    if remaining < 0: raise ValueError('PNG metadata exceeds its aggregate limit')
    decoder = zlib.decompressobj()
    try: result = decoder.decompress(data, remaining + 1)
    except zlib.error as exc: raise ValueError('Invalid compressed PNG metadata') from exc
    if len(result) > remaining or decoder.unconsumed_tail:
        raise ValueError('PNG metadata exceeds its aggregate limit')
    if not decoder.eof or decoder.unused_data:
        raise ValueError('Incomplete or trailing compressed PNG metadata')
    return result


def _metadata_size(kind: bytes, data: bytes, remaining: int) -> int:
    # Bound compressed ancillary payloads before Pillow can expand them.
    if kind in (b'zTXt', b'iCCP'):
        parts = data.split(b'\0', 1)
        if len(parts) != 2 or not 1 <= len(parts[0]) <= 79 or not parts[1].startswith(b'\0'):
            raise ValueError('Invalid compressed PNG metadata header')
        return len(parts[0]) + 2 + len(_inflate(parts[1][1:], remaining - len(parts[0]) - 2))
    if kind == b'iTXt':
        parts = data.split(b'\0', 1)
        if len(parts) != 2 or not 1 <= len(parts[0]) <= 79 or len(parts[1]) < 4:
            raise ValueError('Invalid international PNG text')
        rest = parts[1]; flag, method = rest[:2]
        fields = rest[2:].split(b'\0', 2)
        if flag not in (0, 1) or method != 0 or len(fields) != 3:
            raise ValueError('Invalid international PNG text header')
        overhead = len(parts[0]) + len(fields[0]) + len(fields[1]) + 5
        return overhead + (len(_inflate(fields[2], remaining - overhead)) if flag else len(fields[2]))
    return len(data)


def scan_png(encoded: bytes, limit: int = MAX_OUTPUT_BYTES) -> list[tuple[bytes, bytes]]:
    """Validate framing/limits and supported sample representation before decode."""
    if type(encoded) is not bytes or len(encoded) > limit or not encoded.startswith(SIGNATURE):
        raise ValueError('Expected a bounded PNG byte capture')
    chunks = []; pos = 8; seen = set(); metadata = 0; ended_data = False
    while pos < len(encoded):
        if len(chunks) >= MAX_CHUNKS or pos + 12 > len(encoded): raise ValueError('PNG chunk limit or truncated chunk')
        length = struct.unpack_from('>I', encoded, pos)[0]
        kind = encoded[pos+4:pos+8]; end = pos + 12 + length
        if end > len(encoded) or not re.fullmatch(b'[A-Za-z]{4}', kind) or kind[2] & 32:
            raise ValueError('Invalid PNG chunk framing')
        data = encoded[pos+8:end-4]
        if zlib.crc32(kind + data) != struct.unpack_from('>I', encoded, end-4)[0]:
            raise ValueError('PNG chunk checksum mismatch')
        if not chunks and kind != b'IHDR': raise ValueError('PNG must begin with IHDR')
        if kind in (b'acTL', b'fcTL', b'fdAT', b'cICP', b'mDCV', b'cLLI'):
            raise ValueError('Animation/HDR requires a separate explicit intake route')
        if not kind[0] & 32 and kind not in (b'IHDR', b'PLTE', b'IDAT', b'IEND'):
            raise ValueError('Unsupported critical PNG chunk')
        if kind in (b'IHDR', b'PLTE', b'IEND', b'tRNS', b'eXIf', *COLOUR) and kind in seen:
            raise ValueError('Duplicate singleton PNG chunk')
        if kind == b'IHDR':
            if length != 13: raise ValueError('Invalid IHDR')
            width, height, depth, colour, compression, filtering, interlace = struct.unpack('>IIBBBBB', data)
            if not (0 < width <= MAX_PIXELS and 0 < height <= MAX_PIXELS and width * height <= MAX_PIXELS):
                raise ValueError('PNG exceeds the decoded pixel limit')
            if depth != 8 or colour not in (2, 6): raise ValueError('Only 8-bit true-colour RGB/RGBA PNG is supported')
            if compression or filtering or interlace not in (0,1): raise ValueError('Unsupported PNG encoding')
        if kind in (*COLOUR, b'PLTE', b'tRNS') and b'IDAT' in seen:
            raise ValueError('PNG colour/palette/transparency chunk follows image data')
        if kind == b'tRNS' and (colour != 2 or length != 6 or any(v > 255 for v in struct.unpack('>HHH', data))):
            raise ValueError('Invalid true-colour transparency key')
        if kind == b'IDAT' and ended_data: raise ValueError('Noncontiguous PNG image data')
        if kind != b'IDAT' and b'IDAT' in seen: ended_data = True
        if kind not in (b'IHDR', b'IDAT', b'IEND'):
            metadata += _metadata_size(kind, data, MAX_METADATA_BYTES - metadata)
            if metadata > MAX_METADATA_BYTES: raise ValueError('PNG metadata exceeds its aggregate limit')
        chunks.append((kind, data)); seen.add(kind); pos = end
        if kind == b'IEND':
            if length or pos != len(encoded) or b'IDAT' not in seen: raise ValueError('Invalid PNG end or trailing bytes')
            break
    if not chunks or chunks[-1][0] != b'IEND': raise ValueError('PNG has no complete end marker')
    return chunks


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack('>I',len(data)) + kind + data + struct.pack('>I',zlib.crc32(kind+data))


def encode_rgba(image: Image.Image, colours: list[tuple[bytes, bytes]]) -> bytes:
    # New image drops EXIF/text/implicit transparency; preserve supported colour chunks verbatim.
    with Image.frombytes('RGBA', image.size, image.tobytes()) as clean, BytesIO() as out:
        clean.save(out, format='PNG')
        raw = out.getvalue()
    raw = raw[:33] + b''.join(png_chunk(k,v) for k,v in colours) + raw[33:]
    if len(raw) > MAX_OUTPUT_BYTES: raise ValueError('Normalized output exceeds byte limit')
    return raw


def normalize_repair_png(encoded: bytes) -> tuple[bytes, dict]:
    chunks = scan_png(encoded, MAX_SOURCE_BYTES)
    colours = [(k,v) for k,v in chunks if k in COLOUR]
    with BytesIO(encoded) as buffer, Image.open(buffer) as image:
        if image.format != 'PNG' or image.mode not in ('RGB','RGBA') or getattr(image,'n_frames',1) != 1:
            raise ValueError('Unsupported decoded PNG representation')
        image.load()  # PNG EXIF can follow IDAT; inspect only after the bounded complete decode.
        orientation = image.getexif().get(274, 1)
        if type(orientation) is not int or orientation not in range(1,9): raise ValueError('Invalid EXIF orientation')
        icc = image.info.get('icc_profile')
        source = {'sha256': digest(encoded), 'bytes': len(encoded), 'size': list(image.size),
                  'mode': image.mode, 'bit_depth': 8, 'orientation': orientation,
                  'colour_key_transparency': any(k == b'tRNS' for k,_ in chunks),
                  'removed_metadata_chunks': sorted({k.decode('ascii') for k,_ in chunks if k not in (*COLOUR,b'IHDR',b'IDAT',b'IEND')})}
        with ImageOps.exif_transpose(image) as oriented, oriented.convert('RGBA') as rgba:
            normalized = encode_rgba(rgba, colours)
            target = {'sha256': digest(normalized), 'bytes': len(normalized), 'size': list(rgba.size),
                      'mode': 'RGBA', 'pixel_sha256': digest(rgba.tobytes())}
    return normalized, {'normalizer': NORMALIZER, 'pillow_version': Image.__version__,
        'source': source, 'normalized': target,
        'colour': {'converted': False, 'interpretation': 'not_certified',
                   'retained_chunks': [k.decode('ascii') for k,_ in colours],
                   'chunk_sha256': digest(b''.join(png_chunk(k,v) for k,v in colours)),
                   'icc_sha256': digest(icc) if icc is not None else None},
        'neural_inference': False, 'review_state': 'unreviewed'}


def read_bounded(path: Path, limit: int, *, reject_symlink: bool = False) -> bytes:
    if reject_symlink and path.is_symlink(): raise ValueError('Packet member must not be a symlink')
    if not path.is_file(): raise ValueError('Expected a regular input file')
    with path.open('rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode): raise ValueError('Expected a regular input file')
        data = stream.read(limit + 1)
    if len(data) > limit: raise ValueError('Input exceeds byte limit')
    return data


def strict_json(data: bytes) -> dict:
    def pairs(items):
        result = {}
        for k,v in items:
            if k in result: raise ValueError('Duplicate JSON field')
            result[k] = v
        return result
    def constant(_): raise ValueError('Nonfinite JSON value')
    try:
        result = json.loads(data.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
        if type(result) is not dict: raise ValueError('Expected a JSON object')
        return result
    except (UnicodeError, RecursionError) as exc: raise ValueError('Invalid bounded UTF-8 JSON') from exc


def publish_packet(output: Path, artifacts: dict[str, bytes], receipt: dict) -> dict:
    """Exclusive directory; final hard-linked receipt is the completion marker.

    Failed/partial packets remain for inspection, never reused or deleted. This
    is a cooperative local-writer contract, not hostile FS or power-loss safety.
    """
    encoded = (json.dumps(receipt, ensure_ascii=True, allow_nan=False, indent=2) + '\n').encode()
    if len(artifacts) > 68 or sum(map(len, artifacts.values())) > MAX_OUTPUT_BYTES or len(encoded) > MAX_METADATA_BYTES:
        raise ValueError('Packet exceeds artifact/byte bounds')
    for name in artifacts:
        if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{0,79}', name) or name in ('receipt.json','receipt.pending'):
            raise ValueError('Invalid packet artifact name')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()  # Atomic no-clobber claim; never rename over a competing directory.
    for name, data in {**artifacts, 'receipt.pending': encoded}.items():
        with (output/name).open('xb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
    os.link(output/'receipt.pending', output/'receipt.json')
    (output/'receipt.pending').unlink()
    return receipt


def capture(image: Path, output: Path) -> dict:
    original = read_bounded(image, MAX_SOURCE_BYTES)
    normalized, details = normalize_repair_png(original)
    receipt = {'schema': SCHEMA, 'normalization': details, 'neural_inference': False, 'review_state': 'unreviewed'}
    return publish_packet(output, {'source.png':original,'normalized.png':normalized}, receipt)


def load_packet(folder: Path) -> tuple[bytes, dict, bytes]:
    raw_receipt = read_bounded(folder/'receipt.json', MAX_METADATA_BYTES, reject_symlink=True)
    receipt = strict_json(raw_receipt)
    if set(receipt) != {'schema','normalization','neural_inference','review_state'} or receipt['schema'] != SCHEMA:
        raise ValueError('Unsupported repair-source packet')
    original = read_bounded(folder/'source.png',MAX_SOURCE_BYTES,reject_symlink=True)
    if len(original) > MAX_OUTPUT_BYTES: raise ValueError('Packet exceeds aggregate artifact byte limit')
    actual = read_bounded(folder/'normalized.png',MAX_OUTPUT_BYTES-len(original),reject_symlink=True)
    expected, details = normalize_repair_png(original)
    actual_chunks = scan_png(actual)
    if any(k not in (*COLOUR,b'IHDR',b'IDAT',b'IEND') for k,_ in actual_chunks):
        raise ValueError('Normalized derivative contains undeclared metadata')
    if [(k,v) for k,v in actual_chunks if k in COLOUR] != [(k,v) for k,v in scan_png(expected) if k in COLOUR]:
        raise ValueError('Normalized colour metadata does not match the source')
    with Image.open(BytesIO(actual)) as a, Image.open(BytesIO(expected)) as b:
        if a.mode != 'RGBA' or a.size != b.size or a.tobytes() != b.tobytes():
            raise ValueError('Normalized pixels do not reconstruct from the retained source')
    # Encoding may differ across Pillow versions; decoded samples and metadata may not.
    recorded = receipt.get('normalization')
    if type(recorded) is not dict or type(recorded.get('pillow_version')) is not str or not 1 <= len(recorded['pillow_version']) <= 64:
        raise ValueError('Missing normalization producer version')
    details['pillow_version'] = recorded['pillow_version']
    details['normalized']['sha256'] = digest(actual); details['normalized']['bytes'] = len(actual)
    expected_receipt = {'schema':SCHEMA,'normalization':details,'neural_inference':False,'review_state':'unreviewed'}
    if json.dumps(receipt, sort_keys=True, allow_nan=False) != json.dumps(expected_receipt, sort_keys=True, allow_nan=False):
        raise ValueError('Packet evidence does not match its captured bytes')
    return actual, receipt, raw_receipt


def verify(folder: Path) -> dict:
    return load_packet(folder)[1]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    cap=commands.add_parser('capture'); cap.add_argument('--image',required=True,type=Path); cap.add_argument('--out',required=True,type=Path)
    check=commands.add_parser('verify'); check.add_argument('packet',type=Path)
    args=parser.parse_args(argv)
    try:
        result=capture(args.image,args.out) if args.command=='capture' else verify(args.packet)
        print(json.dumps(result,ensure_ascii=True,allow_nan=False,indent=2)); return 0
    except (ValueError,OSError) as exc:
        print(json.dumps({'error':str(exc),'neural_inference':False,'review_state':'unreviewed'},ensure_ascii=True)); return 2

if __name__=='__main__': raise SystemExit(main())
