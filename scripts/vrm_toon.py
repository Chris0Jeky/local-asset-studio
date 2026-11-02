"""Anime toon kit core: VRoid material roles, SDF face-shadow thresholds and VRM spring data, with no Blender needed.

Used by `vrm_toon_bpy.py` (Blender 5.4 toon materials), `vrm_posmap_bpy.py` (per-texel position maps) and the
Godot proof in `tools/godot-toon/`. See docs/ANIME-TOON-KIT.md.

  python scripts/vrm_toon.py springs MODEL.vrm OUT.json      chains, colliders, node constraints and expressions for the Godot proof
  python scripts/vrm_toon.py face-sdf FACE.npz OUT.png       SDF face map from a face position map (needs numpy, Pillow)
"""
from __future__ import annotations

import json
import math
import struct
import sys
from pathlib import Path

GLB_MAGIC, JSON_CHUNK = 0x46546C67, 0x4E4F534A
# Shade colour per role, multiplied into the base colour where no light reaches (skin warm, cloth cool, hair deep).
SHADE = {'skin': (.93, .76, .74), 'face': (.93, .76, .74), 'hair': (.50, .64, .74), 'cloth': (.62, .62, .78)}


def material_role(name: str) -> str:
    """VRoid Studio names materials `<Part>_<nn>_<KIND>`; map one to a toon role.

    unlit: eyes, brows, lashes, mouth (drawn flat); face: face skin (SDF shadow); hair; skin; cloth (everything else)."""
    upper = name.upper()
    if upper.endswith('_EYE') or upper.endswith('_FACE'): return 'unlit'
    if upper.endswith('_SKIN'): return 'face' if upper.startswith('FACE') else 'skin'
    if upper.endswith('_HAIR'): return 'hair'
    return 'cloth'


def sdf_threshold(x: float, z: float, y: float, width: float, *, eye_z: float, nose_z: float, nose_y: float,
                  bow: float = .28, bow_height: float = .08, nose: float = .35) -> float:
    """Light angle (0 = from the front, 1 = from behind, as a fraction of pi) up to which a face texel stays lit when
    the light comes from the side where x is positive. Mirror x for the other side.

    The terminator sweeps from the far cheek to the near cheek as the light moves round, bows into a crescent above
    and below eye height, and a small lobe past the nose shades early (the usual anime face-shadow read)."""
    xe = x / max(width, .02) - bow * ((z - eye_z) / bow_height) ** 2
    if y < nose_y + .02: xe -= nose * math.exp(-((z - nose_z) / .011) ** 2 - ((x + .008) / .009) ** 2)
    return math.acos(max(-1.0, min(1.0, -xe))) / math.pi


def face_landmarks(points) -> dict:
    """Eye height, nose height/depth and a width-by-height table from face-skin points [(x, y, z)] (Z up, face -Y)."""
    zs = sorted(p[2] for p in points); lo, hi = zs[0], zs[-1]
    front = [p for p in points if abs(p[0]) < .01 and lo + .1 * (hi - lo) < p[2] < lo + .5 * (hi - lo)]
    tip = min(front, key=lambda p: p[1]) if front else (0.0, min(p[1] for p in points), lo + .25 * (hi - lo))
    ys = [p[1] for p in points]; mid = (min(ys) + max(ys)) / 2; bins = 24; table = []   # widths over the front half only
    for i in range(bins + 1):
        z = lo + (hi - lo) * i / bins; xs = [abs(p[0]) for p in points if abs(p[2] - z) < (hi - lo) / bins and p[1] < mid]
        if xs: table.append((z, max(xs)))
    return {'eye_z': lo + .45 * (hi - lo), 'nose_z': tip[2], 'nose_y': tip[1], 'widths': table}


def width_at(table, z: float) -> float:
    if not table: return .08
    if z <= table[0][0]: return table[0][1]
    for (z0, w0), (z1, w1) in zip(table, table[1:]):
        if z0 <= z <= z1: return w0 + (w1 - w0) * (z - z0) / max(z1 - z0, 1e-9)
    return table[-1][1]


def face_sdf_image(npz: Path, out: Path) -> dict:
    """R = threshold for light from her left (+X), G = from her right; texels outside the face are 1 (always lit)."""
    import numpy as np
    from PIL import Image
    d = np.load(npz); pos, mask = d['pos'], d['mask']
    pts = pos[mask]; marks = face_landmarks([tuple(p) for p in pts[::max(1, len(pts) // 20000)]])
    tz, tw = zip(*marks['widths']) if marks['widths'] else ((0.0,), (.08,))
    x, y, z = (pos[..., i][mask] for i in range(3)); W = np.interp(z, tz, tw)
    f = np.vectorize(lambda a, b, c, w: sdf_threshold(a, b, c, w, eye_z=marks['eye_z'], nose_z=marks['nose_z'], nose_y=marks['nose_y']))
    t = np.ones(mask.shape + (3,), np.float32); t[..., 0][mask] = f(x, z, y, W); t[..., 1][mask] = f(-x, z, y, W)
    grown = mask.copy()                                                    # bleed edge values outward for seam-safe sampling
    for _ in range(4):
        for c in (0, 1):
            ch = t[..., c]; src = np.where(grown, ch, -1.0)
            nb = np.maximum.reduce([np.roll(src, s, a) for a in (0, 1) for s in (1, -1)]); fill = ~grown & (nb >= 0); ch[fill] = nb[fill]
        grown |= np.roll(grown, 1, 0) | np.roll(grown, -1, 0) | np.roll(grown, 1, 1) | np.roll(grown, -1, 1)
    Image.fromarray((t * 255).round().astype(np.uint8)).save(out)
    return {k: round(float(v), 4) for k, v in marks.items() if k != 'widths'}


def read_glb_json(path: Path) -> dict:
    data = Path(path).read_bytes()
    if len(data) < 20: raise ValueError('not a GLB: too short')
    magic, version, length = struct.unpack_from('<III', data, 0)
    if magic != GLB_MAGIC or version != 2 or not 20 <= length <= len(data): raise ValueError('not a GLB 2.0: bad header')
    size, kind = struct.unpack_from('<II', data, 12)
    if kind != JSON_CHUNK or 20 + size > length: raise ValueError('GLB first chunk is not JSON')
    return json.loads(data[20:20 + size])


def vrm_springs(doc: dict) -> dict:
    """VRMC_springBone chains (root, end, first-joint settings, collider indices from their groups) and colliders.

    Per-joint settings beyond the first joint, gravityDir and center are not carried over."""
    names = [n.get('name', f'node{i}') for i, n in enumerate(doc.get('nodes', []))]
    sb = doc.get('extensions', {}).get('VRMC_springBone')
    if not sb: raise ValueError('no VRMC_springBone extension (VRM 1.0 required)')
    colliders = []                                              # schema defaults: offset/tail [0,0,0], radius 0
    for c in sb.get('colliders', []):
        shape = c['shape']; kind = 'sphere' if 'sphere' in shape else 'capsule'; s = shape[kind]
        colliders.append({'bone': names[c['node']], 'type': kind, 'offset': s.get('offset', [0, 0, 0]),
                          'tail': s.get('tail', [0, 0, 0]) if kind == 'capsule' else None, 'radius': s.get('radius', 0.0)})
    groups = [g.get('colliders', []) for g in sb.get('colliderGroups', [])]
    chains = []
    for s in sb.get('springs', []):
        joints = s.get('joints', [])
        if len(joints) < 2: continue
        first = joints[0]
        chains.append({'name': s.get('name', ''), 'root': names[first['node']], 'end': names[joints[-1]['node']],
                       'joints': len(joints), 'stiffness': first.get('stiffness', 1.0), 'drag': first.get('dragForce', .5),
                       'gravity': first.get('gravityPower', 0.0), 'radius': first.get('hitRadius', 0.0),
                       'colliders': sorted({c for g in s.get('colliderGroups', []) for c in groups[g]})})
    return {'chains': chains, 'colliders': colliders}


AXES = {'PositiveX': (1, 0, 0), 'NegativeX': (-1, 0, 0), 'PositiveY': (0, 1, 0), 'NegativeY': (0, -1, 0),
        'PositiveZ': (0, 0, 1), 'NegativeZ': (0, 0, -1), 'X': (1, 0, 0), 'Y': (0, 1, 0), 'Z': (0, 0, 1)}


def vrm_constraints(doc: dict) -> list:
    """VRMC_node_constraint entries (aim, roll, rotation) by node name, in file order; glTF engines ignore them."""
    names = [n.get('name', f'node{i}') for i, n in enumerate(doc.get('nodes', []))]; out = []
    for i, node in enumerate(doc.get('nodes', [])):
        c = node.get('extensions', {}).get('VRMC_node_constraint', {}).get('constraint', {})
        for kind in ('aim', 'roll', 'rotation'):
            if kind in c:
                v = c[kind]; axis = v.get('aimAxis') or v.get('rollAxis')
                out.append({'bone': names[i], 'type': kind, 'source': names[v['source']], 'weight': v.get('weight', 1.0),
                            'axis': list(AXES[axis]) if axis else None})
    return out


def vrm_expressions(doc: dict) -> dict:
    """VRMC_vrm expressions (presets and custom) as morph-target binds by node name, index and target name."""
    names = [n.get('name', f'node{i}') for i, n in enumerate(doc.get('nodes', []))]
    meshes = doc.get('meshes', []); ex = doc.get('extensions', {}).get('VRMC_vrm', {}).get('expressions', {}); out = {}
    for group in ('preset', 'custom'):
        for key, e in ex.get(group, {}).items():
            binds = []
            for b in e.get('morphTargetBinds', []):
                node = doc['nodes'][b['node']]; targets = meshes[node['mesh']].get('extras', {}).get('targetNames', []) if 'mesh' in node else []
                binds.append({'node': names[b['node']], 'node_index': b['node'], 'index': b['index'], 'weight': b.get('weight', 1.0),
                              'name': targets[b['index']] if b['index'] < len(targets) else None})
            if binds: out[key] = {'binds': binds, 'binary': e.get('isBinary', False),
                                  'override_blink': e.get('overrideBlink', 'none'), 'override_mouth': e.get('overrideMouth', 'none')}
    return out


def main(argv) -> int:
    if len(argv) == 3 and argv[0] == 'springs':
        doc = read_glb_json(Path(argv[1])); out = vrm_springs(doc); out['constraints'] = vrm_constraints(doc)
        out['expressions'] = vrm_expressions(doc)
        Path(argv[2]).write_text(json.dumps(out, indent=1), encoding='utf-8')
        print(len(out['chains']), 'chains,', len(out['colliders']), 'colliders,', len(out['constraints']), 'constraints,', len(out['expressions']), 'expressions'); return 0
    if len(argv) == 3 and argv[0] == 'face-sdf':
        print(json.dumps(face_sdf_image(Path(argv[1]), Path(argv[2])))); return 0
    print(__doc__); return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
