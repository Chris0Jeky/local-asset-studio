"""Bounded native qualification of procgen round shading in actual exported GLB normals.

Six production Blender exports (three prop kinds x flat/smooth), three LODs each.
No renderer, Godot, npm or Khronos download required. This is a shading gate only.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import struct
import subprocess

import procgen_factory as factory
from engine_validation import EvidenceError, file_sha, inspect_glb, read_json, require, run_command, write_json


def read_triangles(path):
    """Read uncompressed triangle POSITION/NORMAL data, retaining corner normals and mesh names."""
    inspect_glb(path)
    data = Path(path).read_bytes(); json_size = struct.unpack_from('<I', data, 12)[0]
    doc = json.loads(data[20:20 + json_size]); start = 20 + json_size
    require(start + 8 <= len(data), 'Shading probe requires a BIN chunk')
    size, kind = struct.unpack_from('<II', data, start)
    require(kind == 0x004e4942, 'Shading probe requires a BIN chunk')
    binary = data[start + 8:start + 8 + size]

    def accessor(index, expected):
        a = doc['accessors'][index]
        require(a.get('type') == expected and 'sparse' not in a and not a.get('normalized'), 'Unsupported shading accessor')
        components = 3 if expected == 'VEC3' else 1
        require(a.get('componentType') in ((5126,) if components == 3 else (5121, 5123, 5125)), 'Unexpected accessor component type')
        fmt = {5126: 'f', 5121: 'B', 5123: 'H', 5125: 'I'}[a['componentType']]
        view = doc['bufferViews'][a['bufferView']]
        require(view.get('buffer') == 0, 'Shading accessor must use embedded buffer')
        width = struct.calcsize('<' + fmt * components); stride = view.get('byteStride', width)
        offset, count = a.get('byteOffset', 0), a['count']; base = view.get('byteOffset', 0)
        end = offset + (count - 1) * stride + width
        require(count > 0 and stride >= width and offset >= 0 and base >= 0 and end <= view['byteLength']
                and base + view['byteLength'] <= len(binary), 'Shading accessor outside buffer view')
        return [struct.unpack_from('<' + fmt * components, binary, base + offset + i * stride) for i in range(count)]

    meshes = {}
    for mesh in doc['meshes']:
        name = mesh['name']; require(name not in meshes, 'Duplicate exported mesh name')
        triangles = []
        for primitive in mesh['primitives']:
            require(primitive.get('mode', 4) == 4, 'Shading probe requires triangles')
            attrs = primitive['attributes']; require('NORMAL' in attrs, f'{name}: missing exported NORMAL')
            positions, normals = accessor(attrs['POSITION'], 'VEC3'), accessor(attrs['NORMAL'], 'VEC3')
            indices = [i[0] for i in accessor(primitive['indices'], 'SCALAR')] if 'indices' in primitive else list(range(len(positions)))
            require(len(positions) == len(normals) and len(indices) % 3 == 0 and all(0 <= i < len(positions) for i in indices),
                    'Invalid shading vertex/index count')
            triangles += [[(positions[i], normals[i]) for i in indices[j:j + 3]] for j in range(0, len(indices), 3)]
        require(bool(triangles), f'{name}: no triangles')
        normal_summary(triangles)  # finite, unit normals, including collision meshes
        meshes[name] = triangles
    return meshes


def normal_summary(triangles):
    varying = caps = 0
    for triangle in triangles:
        for position, normal in triangle:
            require(all(math.isfinite(v) for v in (*position, *normal)), 'Nonfinite exported position/normal')
            require(abs(sum(v * v for v in normal) - 1) < 1e-3, 'Exported normal must be unit length')
        ns = [corner[1] for corner in triangle]
        different = any(sum((a - b) ** 2 for a, b in zip(ns[0], n)) > 1e-8 for n in ns[1:])
        varying += int(different)
        # Blender z-up becomes GLB y-up; all qualified props keep round axes vertical.
        ps = [corner[0] for corner in triangle]
        if max(p[1] for p in ps) - min(p[1] for p in ps) < 1e-7:
            require(not different and all(abs(abs(n[1]) - 1) < 1e-5 for n in ns), 'Round cap lost its hard axial normals')
            caps += 1
    return {'triangles': len(triangles), 'varying_triangles': varying, 'hard_cap_triangles': caps}


def require_capped_round_shading(summary, name):
    caps = summary['hard_cap_triangles']; sides = summary['triangles'] - caps
    require(caps > 0 and sides > 0 and summary['varying_triangles'] == sides,
            f'{name}: require hard caps and interpolated normals on every side triangle')


def geometry_key(triangles):
    """Compare exported triangle positions independent of glTF vertex splits/order."""
    return sorted(tuple(sorted(tuple(round(v, 6) for v in p) for p, _ in triangle)) for triangle in triangles)


def qualify(blender, output, timeout=180):
    out = Path(output).resolve(); out.mkdir(parents=True, exist_ok=False)
    receipt = {'schema_version': 1, 'scope': 'procgen-exported-shading', 'started_utc': datetime.now(timezone.utc).isoformat(),
               'state': 'failed', 'cases': [], 'failures': [], 'blender_executable': str(Path(blender).resolve()),
               'source_sha256': {str(p.relative_to(factory.ROOT)): file_sha(p) for p in
                                 (Path(__file__), factory.BLENDER_SCRIPT, factory.SCHEMA_PATH, Path(factory.__file__), Path(inspect_glb.__code__.co_filename))},
               'not_established': ['rendered-appearance', 'Godot-import', 'Khronos-validation', 'art-acceptance']}
    for key, args in (('source_revision', ['rev-parse', 'HEAD']), ('source_tree', ['rev-parse', 'HEAD^{tree}']),
                      ('source_dirty', ['status', '--porcelain'])):
        reply = subprocess.run(['git', '-C', str(factory.ROOT), *args], capture_output=True, text=True, timeout=10)
        receipt[key] = reply.stdout.strip() if reply.returncode == 0 else None
    write_json(out / 'plan.json', receipt)
    try:
        spec = factory.load_schema()['generators']['prop']
        for kind in (0, 1, 2):
            pair = []
            for smooth in (0, 1):
                directory = out / f'prop-{kind}-smooth-{smooth}'; directory.mkdir()
                params, errors = factory.resolve_params(spec, {'kind': kind, 'detail': 12, 'smooth': smooth})
                require(not errors, str(errors))
                request = {'generator': 'prop', 'spec': spec, 'params': params, 'lod_details': factory.lod_details(params['detail']),
                           'output': str(directory), 'render': False, 'collision_suffix': factory.COLLISION_SUFFIX, 'uv_res': factory.UV_RES}
                write_json(directory / 'request.json', request)
                command = [str(Path(blender).resolve()), '-b', '--factory-startup', '--python-exit-code', '1', '-P',
                           str(factory.BLENDER_SCRIPT), '--', str(directory / 'request.json')]
                write_json(directory / 'plan.json', {'command': command, 'timeout_seconds': timeout})
                run_command(command, directory, 'blender', timeout)
                measured = read_json(directory / 'measurements.json')
                gates = factory.evaluate_gates('prop', spec, params, measured)
                require(all(g['passed'] for g in gates), f'Mesh gates failed: {gates}')
                row = {'kind': kind, 'smooth': smooth, 'blender': measured['blender'], 'gates': gates, 'lods': []}
                exports = []
                for level in range(factory.LOD_LEVELS):
                    path = directory / f'asset_LOD{level}.glb'; meshes = read_triangles(path); exports.append(meshes)
                    summaries = {name: normal_summary(tris) for name, tris in meshes.items()}
                    row['lods'].append({'level': level, 'sha256': file_sha(path), 'meshes': summaries})
                    if kind == 1 or smooth == 0:
                        require(all(s['varying_triangles'] == 0 for s in summaries.values()), 'Flat surface acquired interpolated normals')
                    elif kind in (0, 2):
                        suffix = '' if level == 0 else f'_lod{level}'
                        round_name = ('lantern_body' if kind == 0 else 'foliage') + suffix
                        summary = summaries[round_name]
                        require(summary['varying_triangles'] == summary['triangles'], f'{round_name}: exported round normals remained flat')
                        cap_name = ('lantern_caps' if kind == 0 else 'pot') + suffix
                        require_capped_round_shading(summaries[cap_name], cap_name)
                receipt['cases'].append(row); pair.append(exports)
                write_json(directory / 'shading.json', row)
            for level, (flat, smooth) in enumerate(zip(*pair)):
                require(flat.keys() == smooth.keys(), 'Shading changed exported part names')
                for name in flat:
                    require(geometry_key(flat[name]) == geometry_key(smooth[name]), f'{name} LOD{level}: shading changed geometry')
                if kind == 1:
                    require(flat == smooth, 'Shading changed crate hard edges')
        receipt['state'] = 'passed'
    except Exception as exc:
        receipt['failures'].append(f'{type(exc).__name__}: {exc}')
    finally:
        receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
        write_json(out / 'receipt.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender', required=True, type=Path, help='Explicit Blender 5.4 executable')
    parser.add_argument('--output', required=True, type=Path, help='New evidence directory (never reused)')
    parser.add_argument('--timeout', type=int, default=180, help='Seconds per Blender invocation (six invocations)')
    args = parser.parse_args(); receipt = qualify(args.blender, args.output, args.timeout)
    print(json.dumps({'state': receipt['state'], 'failures': receipt['failures'], 'receipt': str(args.output / 'receipt.json')}))
    return 0 if receipt['state'] == 'passed' else 1


if __name__ == '__main__': raise SystemExit(main())
