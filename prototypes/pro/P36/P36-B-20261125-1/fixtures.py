"""Procedural test data only: swatches and a triangle, never character generation.

Every synthetic acceptance is marked fixture and is refused by the release gate.
This file has no production role; actual media/decisions must be supplied by owners.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import struct

from PIL import Image, ImageDraw

from consistency import measure_regions
from pipeline import (STAGES, attest, canonical_bytes, create_family,
                      prepare_receipt, record_receipt)

REGIONS = {'hair': [0.0625, 0.0625, 0.4375, 0.4375],
           'eyes': [0.5625, 0.0625, 0.9375, 0.4375]}
VALUES = {'hair': [80, 20, 90], 'eyes': [120, 70, 150],
          'eye_spacing': 0.42, 'braid_side': 'anatomical-left'}


def policy():
    front = ['hair', 'eyes', 'eye_spacing', 'braid_side']
    profile = ['hair', 'eyes', 'braid_side']; back = ['hair', 'braid_side']
    required = {
        'concept': {'front': front},
        'turnaround': {'front': front, 'left': profile, 'right': profile, 'back': back},
        'expressions': {name: front for name in ('neutral', 'smile', 'angry')},
        'outfits': {'travel-front': front, 'travel-back': back, 'formal-front': front, 'formal-back': back},
        'mesh': {'front': front, 'left': profile, 'right': profile, 'back': back},
        'rig': {name: front for name in ('neutral', 'arms-up', 'twist')},
        'toon': {name: front for name in ('neutral', 'warm', 'cool')},
        'unreal': {name: front for name in ('front', 'combat')},
    }
    return {'version': 1, 'features': {'hair': {'kind': 'rgb', 'tolerance': 0.08},
                                      'eyes': {'kind': 'rgb', 'tolerance': 0.08},
                                      'eye_spacing': {'kind': 'ratio', 'tolerance': 0.04},
                                      'braid_side': {'kind': 'trait'}},
            'required': copy.deepcopy(required),
            'regions': {s: {v: {name: REGIONS[name] for name in names if name in REGIONS}
                            for v, names in views.items()} for s, views in required.items()},
            'quality_required': {'mesh': ['geometry', 'uvs'],
                                 'rig': ['weights', 'deformation', 'expressions'],
                                 'toon': ['palette', 'bands', 'face-shading'],
                                 'unreal': ['handoff-contract']}}


def metadata():
    return {'id': 'p36-fixture', 'display_name': 'P36 synthetic gate fixture',
            'profile': {'full_name': 'Synthetic test subject', 'age': 25, 'pronouns': 'they/them',
                        'role': 'Software fixture; not a cast character', 'personality': ['synthetic'],
                        'bio': 'Swatch images and one unrigged triangle; no generated character.'},
            'style': {'tags': ['synthetic-contract-test']},
            'voice': {'engine': 'none', 'voice_id': 'none'},
            'animations': {'set': 'none', 'spring_bones': 'none'}, 'versus': [],
            'skeleton': 'none', 'ue': {'requested_import': 'planned'}, 'expressions': {},
            'notes': 'Implemented software fixture only. No native import, rig, shader or owner art acceptance.'}


def swatch(path, *, marker, hair=None, eyes=None, outfit=(40, 60, 80), geometry='round'):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new('RGBA', (32, 32), (235, 235, 235, 255)); draw = ImageDraw.Draw(image)
    draw.rectangle((2, 2, 13, 13), fill=tuple(hair or VALUES['hair']) + (255,))
    draw.rectangle((18, 2, 29, 13), fill=tuple(eyes or VALUES['eyes']) + (255,))
    if geometry == 'round': draw.ellipse((6, 18, 25, 30), fill=tuple(outfit) + (255,))
    else: draw.polygon([(3, 18), (28, 18), (22, 30), (9, 30)], fill=tuple(outfit) + (255,))
    image.putpixel((0, 0), (marker % 256, (marker // 256) % 256, 0, 255))
    # Deterministic uncompressed PNG, independent of zlib compressor-version heuristics.
    import binascii
    width, height = image.size
    pixels = image.tobytes(); rows = b''.join(b'\0' + pixels[y*width*4:(y+1)*width*4] for y in range(height))
    adler_a = 1; adler_b = 0
    for value in rows: adler_a = (adler_a + value) % 65521; adler_b = (adler_b + adler_a) % 65521
    packed = b'\x78\x01\x01' + struct.pack('<HH', len(rows), 65535-len(rows)) + rows
    packed += struct.pack('>I', (adler_b << 16) | adler_a)
    def chunk(name, data):
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', binascii.crc32(name + data) & 0xffffffff)
    raw = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
    raw += chunk(b'IDAT', packed) + chunk(b'IEND', b'')
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def triangle_glb(path):
    """Minimal valid glTF2 triangle; explicitly not a skeletal character."""
    vertices = struct.pack('<9f', 0, 0, 0, 1, 0, 0, 0, 1, 0)
    indices = struct.pack('<3H', 0, 1, 2); binary = vertices + indices + b'\0\0'
    document = {'asset': {'version': '2.0', 'generator': 'P36 synthetic contract fixture'},
                'buffers': [{'byteLength': len(binary)}],
                'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': 36, 'target': 34962},
                                {'buffer': 0, 'byteOffset': 36, 'byteLength': 6, 'target': 34963}],
                'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3',
                               'min': [0, 0, 0], 'max': [1, 1, 0]},
                              {'bufferView': 1, 'componentType': 5123, 'count': 3, 'type': 'SCALAR'}],
                'meshes': [{'primitives': [{'attributes': {'POSITION': 0}, 'indices': 1}]}],
                'nodes': [{'mesh': 0}], 'scenes': [{'nodes': [0]}], 'scene': 0}
    text = canonical_bytes(document).rstrip(b'\n'); text += b' ' * (-len(text) % 4)
    raw = b'glTF' + struct.pack('<II', 2, 12+8+len(text)+8+len(binary))
    raw += struct.pack('<II', len(text), 0x4e4f534a) + text
    raw += struct.pack('<II', len(binary), 0x004e4942) + binary
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)


def artifact(root, relative, stage, view, *, role='identity-view', media_type='image/png'):
    path = Path(root) / relative; raw = path.read_bytes()
    result = {'key': view, 'asset_id': 'fixture-' + stage + '-' + view, 'path': relative,
              'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
              'media_type': media_type, 'role': role,
              'source': 'fixture:P36-B-20261125-1/' + stage + '/' + view,
              'licence': {'name': 'Synthetic test data authored in this run; no real character',
                          'source': 'fixture:P36-B-20261125-1', 'commercial': 'unknown'}}
    if media_type.startswith('image/'):
        result.update(dimensions=[32, 32], colour_space='srgb', alpha='opaque')
    return result


def stage_receipt(family, stage, root, *, mutation=None, accept=True):
    root = Path(root); views, artifacts = [], []
    for index, (view, names) in enumerate(family['policy']['required'][stage].items()):
        changes = mutation or {}; local = changes if changes.get('view', view) == view else {}
        relative = stage + '/' + view + '.png'
        marker = 1 + STAGES.index(stage) * 32 + index
        sha = swatch(root / relative, marker=marker, hair=local.get('hair'), eyes=local.get('eyes'),
                     outfit=local.get('outfit', (40 + index * 20, 60, 80)), geometry=local.get('geometry', 'round'))
        regions = family['policy']['regions'][stage][view]
        features = measure_regions(root / relative, sha, regions)
        for name in names:
            if name not in features:
                features[name] = {'value': local.get(name, VALUES[name]), 'provenance': 'fixture_truth',
                                  'media_sha256': sha}
        views.append({'id': view, 'media_sha256': sha, 'features': features})
        artifacts.append(artifact(root, relative, stage, view))
    if stage == 'toon':
        triangle_glb(root / 'toon/model.glb')
        artifacts.append(artifact(root, 'toon/model.glb', stage, 'model', role='engine-model',
                                  media_type='model/gltf-binary'))
        material_path = root / 'toon/materials.json'
        material_path.write_bytes(canonical_bytes({'fixture': {'base': [0.31, 0.08, 0.35, 1],
                                                              'shade': [0.15, 0.04, 0.17]}}))
        artifacts.append(artifact(root, 'toon/materials.json', stage, 'materials', role='toon-materials',
                                  media_type='application/json'))
    identity = {'sheet': {'views': views}}
    if stage == 'concept': identity['anchor_features'] = copy.deepcopy(views[0]['features'])
    checks = [{'name': name, 'outcome': 'pass', 'evidence_ref': 'fixture:' + name}
              for name in family['policy'].get('quality_required', {}).get(stage, [])]
    receipt = prepare_receipt(family, stage, artifacts=artifacts,
                              recipe={'route_id': 'synthetic-fixture-no-generation',
                                      'controls': {'marker_stage': STAGES.index(stage)},
                                      'model_pins': [], 'fixture': True},
                              references=[], identity=identity, quality=checks)
    receipt = attest(receipt, 'generation', 'completed', 'fixture', 'fixture:procedural-bytes')
    receipt = attest(receipt, 'inspection', 'inspected', 'fixture', 'fixture:test-contract')
    if accept: receipt = attest(receipt, 'acceptance', 'accepted', 'owner', 'fixture:not-real-acceptance')
    return receipt


def build_fixture(root, *, through='unreal', mutations=None, unaccepted_stage=None):
    family = create_family('p36-fixture', 'a' * 32, 'p36-fixture', policy(), mode='synthetic')
    for stage in STAGES:
        receipt = stage_receipt(family, stage, root, mutation=(mutations or {}).get(stage),
                                accept=stage != unaccepted_stage)
        family = record_receipt(family, receipt)
        if stage == through: break
    return family
