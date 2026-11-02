"""Procedural asset factory: params JSON -> Blender Geometry Nodes -> gated GLB + report JSON.

Generators live in procgen_generators.json (bounds, constraints, parts) and are built
as GN node groups by procgen_blender.py inside an explicitly selected Blender. Blender
only measures; every gate is evaluated here from those measurements so the gate logic
is testable without Blender. Passing gates is technical acceptance, never art acceptance.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import shutil
import sys
import time

from engine_validation import EvidenceError, file_sha, read_json, run_command, validate_glb, write_json

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = Path(__file__).with_name('procgen_generators.json')
BLENDER_SCRIPT = Path(__file__).with_name('procgen_blender.py')
GODOT_PROBE = Path(__file__).with_name('procgen_godot_probe.gd')
LOCAL_CONFIG = ROOT / 'config/local.json'
NAME_RE = re.compile(r'^[a-z][a-z0-9_]{0,62}$')
COLLISION_SUFFIX = '-convcolonly'
LOD_LEVELS = 3
MIN_DETAIL = 4
TOL = 0.001          # 1 mm for exact box dimensions and pivots
OVERLAP_SHRINK = 0.002
UV_RES = 512
# Pivot rule per generator: assets stand on z=0; rooms and shrines start at y=0 (open front / first step).
FRONT_ANCHORED = {'room_kit', 'shrine'}


def load_schema(path=SCHEMA_PATH):
    schema = read_json(path)
    if schema.get('schema_version') != 1: raise EvidenceError('Unsupported generator schema version')
    return schema


def lod_details(detail):
    return [max(MIN_DETAIL, detail // (2 ** level)) for level in range(LOD_LEVELS)]


def resolve_params(spec, params):
    """Fill defaults and check types and bounds. Returns (resolved, errors); never clamps."""
    errors, resolved = [], {}
    if not isinstance(params, dict): return {}, ['params must be a JSON object']
    for key in params:
        if key not in spec['params']: errors.append(f'unknown parameter {key!r}')
    for key, rule in spec['params'].items():
        value = params.get(key, rule['default'])
        if rule['type'] == 'int':
            if type(value) is not int: errors.append(f'{key} must be an integer'); continue
        elif type(value) not in (int, float) or not math.isfinite(value):
            errors.append(f'{key} must be a finite number'); continue
        if not rule['min'] <= value <= rule['max']:
            errors.append(f'{key}={value} outside [{rule["min"]}, {rule["max"]}]'); continue
        resolved[key] = float(value) if rule['type'] == 'float' else value
    return resolved, errors


def check_constraints(spec, p):
    failures = []
    for rule in spec.get('constraints', []):
        total = sum(coef * p[name] for name, coef in rule['terms'].items())
        if total > rule['le'] + 1e-9: failures.append(f'{rule["doc"]} (value {total:.3f} > {rule["le"]})')
    return failures


def _snap_up(value, step=0.5):
    return math.ceil(value / step - 1e-9) * step


def expected_bounds(generator, p, detail=None):
    """Expected asset bbox size (x, y, z) and per-axis slack fraction for polygonised round extents."""
    detail = p['detail'] if detail is None else detail
    round_slack = 1 - math.cos(math.pi / detail)
    if generator == 'room_kit':
        return [p['width'] + 2 * p['wall_thickness'], p['depth'] + p['wall_thickness'], p['height']], [0, 0, 0]
    if generator == 'prop':
        w, h = p['width'], p['height']
        if p['kind'] == 1: return [w, w, h], [0, 0, 0]
        if p['kind'] == 0: return [w, w, h], [round_slack, round_slack, 0]
        return [w, w, h], [0.45, 0.45, round_slack]   # plant foliage is seeded scatter inside the width
    if generator == 'shrine':
        gw, pr = p['gate_width'], p['pillar_radius']
        kasagi = 1.3 * gw + 4 * pr
        width = _snap_up(max(kasagi, gw + 2 * pr) + 1.0)
        n = p['step_count']
        return [width, n * p['step_run'] + 3.0, (n + 1) * p['step_rise'] + p['gate_height']], [0, 0, 0]
    raise EvidenceError(f'unknown generator {generator!r}')


def uv_overlap_texels(tris, res=UV_RES):
    """Texel centres covered by more than one UV triangle. tris: (N, 3, 2) array-like in UV space.

    Points exactly on a shared edge belong to neither triangle, so adjacent islands never count."""
    import numpy as np
    tris = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 2)
    counts = np.zeros((res, res), dtype=np.int32)
    for (ax, ay), (bx, by), (cx, cy) in tris:
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-14: continue
        x0, x1 = max(0, int(math.floor(min(ax, bx, cx) * res))), min(res, int(math.ceil(max(ax, bx, cx) * res)))
        y0, y1 = max(0, int(math.floor(min(ay, by, cy) * res))), min(res, int(math.ceil(max(ay, by, cy) * res)))
        if x0 >= x1 or y0 >= y1: continue
        px, py = np.meshgrid((np.arange(x0, x1) + 0.5) / res, (np.arange(y0, y1) + 0.5) / res)
        l1 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / den
        l2 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / den
        inside = (l1 > 1e-9) & (l2 > 1e-9) & (1 - l1 - l2 > 1e-9)
        counts[y0:y1, x0:x1] += inside
    return int((counts > 1).sum())


def island_overlaps(islands, shrink=OVERLAP_SHRINK):
    """islands: [(group, part, min[3], max[3])]. Pairs of different groups whose shrunk AABBs intersect."""
    hits = []
    for i, (ga, pa, amin, amax) in enumerate(islands):
        for gb, pb, bmin, bmax in islands[i + 1:]:
            if ga != gb and all(amin[k] + shrink < bmax[k] and bmin[k] + shrink < amax[k] for k in range(3)):
                hits.append(f'{pa} x {pb}')
    return sorted(set(hits))


def _gate(name, failures, **detail):
    return {'gate': name, 'passed': not failures, 'failures': failures[:20], **detail}


def evaluate_gates(generator, spec, p, m):
    """All mesh/naming/LOD gates from Blender measurements m (see procgen_blender.measure)."""
    gates, parts = [], m['parts']
    want = {k: [r['min'], r['max']] for k, r in spec['params'].items() if r.get('gn', True)}
    gates.append(_gate('gn_interface', [f'{k}: GN bounds {m["gn_bounds"].get(k)} != schema {v}'
                                        for k, v in want.items() if m['gn_bounds'].get(k) != v]))
    present = {part['id'] for part in parts}
    gates.append(_gate('parts_present',
                       [f'missing part {spec["parts"][k]["name"]}' for k in spec['parts']
                        if int(k) not in present and not spec['parts'][k].get('optional')]
                       + [f'unknown part id {i}' for i in m.get('unknown_part_ids', [])]))
    lod0 = m['lods'][0]
    size = [b - a for a, b in zip(lod0['bbox_min'], lod0['bbox_max'])]
    expected, slack = expected_bounds(generator, p)
    dims = [f'axis {"xyz"[k]}: {size[k]:.4f} not in [{expected[k] * (1 - slack[k]) - TOL:.4f}, {expected[k] + TOL:.4f}]'
            for k in range(3) if not expected[k] * (1 - slack[k]) - TOL <= size[k] <= expected[k] + TOL]
    if abs(lod0['bbox_min'][2]) > TOL: dims.append(f'asset does not stand on z=0 (min z {lod0["bbox_min"][2]:.4f})')
    # Centring uses the anchor parts when present (a seeded scatter is not symmetric), else the whole asset.
    anchors = [part for part in parts if spec['parts'][str(part['id'])].get('anchor')]
    cmin = [min(part['bbox_min'][k] for part in anchors) for k in range(3)] if anchors else lod0['bbox_min']
    cmax = [max(part['bbox_max'][k] for part in anchors) for k in range(3)] if anchors else lod0['bbox_max']
    if abs(cmin[0] + cmax[0]) / 2 > TOL: dims.append('asset not centred on x')
    if generator in FRONT_ANCHORED:
        if abs(lod0['bbox_min'][1]) > TOL: dims.append(f'front not at y=0 (min y {lod0["bbox_min"][1]:.4f})')
    elif abs(cmin[1] + cmax[1]) / 2 > TOL: dims.append('asset not centred on y')
    gates.append(_gate('dimensions', dims, measured=[round(v, 4) for v in size], expected=[round(v, 4) for v in expected]))
    manifold = []
    for part in parts:
        rule = spec['parts'][str(part['id'])]
        for key in ('nonmanifold_edges', 'inconsistent_edges', 'degenerate_faces') + (() if rule.get('open') else ('boundary_edges',)):
            if part[key]: manifold.append(f'{part["name"]}: {part[key]} {key}')
    gates.append(_gate('manifold', manifold))
    uv = []
    for part in parts:
        if not part['uv0_present'] or not part['uv0_finite']: uv.append(f'{part["name"]}: UVMap missing or non-finite')
        if not part['uv1_present'] or not part['uv1_in_unit']: uv.append(f'{part["name"]}: UVLightmap missing or outside 0..1')
        elif part['uv1_overlap_texels']: uv.append(f'{part["name"]}: {part["uv1_overlap_texels"]} overlapping lightmap texels')
    gates.append(_gate('uv', uv, note='UVMap may overlap (palette/tiling); UVLightmap must not.'))
    tris = [lod['triangles'] for lod in m['lods']]
    gates.append(_gate('triangle_budget', [f'LOD0 {tris[0]} triangles > budget {spec["tri_budget"]}'] if tris[0] > spec['tri_budget'] else [],
                       triangles=tris[0], budget=spec['tri_budget']))
    chain = [] if len(tris) == LOD_LEVELS else [f'{len(tris)} LODs, want {LOD_LEVELS}']
    chain += [f'LOD{i + 1} {tris[i + 1]} > LOD{i} {tris[i]}' for i in range(len(tris) - 1) if tris[i + 1] > tris[i]]
    for i, lod in enumerate(m['lods'][1:], 1):
        lsize = [b - a for a, b in zip(lod['bbox_min'], lod['bbox_max'])]
        exp, sl = expected_bounds(generator, p, lod['detail'])
        if any(not exp[k] * (1 - sl[k]) - TOL <= lsize[k] <= exp[k] + TOL for k in range(3)): chain.append(f'LOD{i} bbox drifted: {lsize}')
    gates.append(_gate('lod_chain', chain, triangles=tris, details=[lod['detail'] for lod in m['lods']]))
    names = [part['name'] for part in parts]
    naming = [f'bad name {n!r}' for n in names if not NAME_RE.match(n)]
    naming += [f'duplicate name {n!r}' for n in set(names) if names.count(n) > 1]
    want_col = sorted(part['name'] + COLLISION_SUFFIX for part in parts if spec['parts'][str(part['id'])].get('collision', True))
    if sorted(m['collision_objects']) != want_col: naming.append(f'collision objects {sorted(m["collision_objects"])} != {want_col}')
    gates.append(_gate('naming', naming))
    pivots = []
    for part in parts:
        bmin, bmax, origin = part['bbox_min'], part['bbox_max'], part['origin']
        target = [(bmin[0] + bmax[0]) / 2, (bmin[1] + bmax[1]) / 2, bmin[2]]
        if max(abs(a - b) for a, b in zip(origin, target)) > TOL: pivots.append(f'{part["name"]}: origin {origin} != bottom centre {target}')
    gates.append(_gate('pivots', pivots))
    islands = [(spec['parts'][str(part['id'])]['group'], part['name'], isl[:3], isl[3:])
               for part in parts if spec['parts'][str(part['id'])].get('solid', True) for isl in part['islands']]
    gates.append(_gate('interpenetration', island_overlaps(islands), islands=len(islands)))
    return gates


def _probe_godot(godot, glb, directory, timeout):
    project = directory / 'godot'
    project.mkdir()
    (project / 'project.godot').write_text('; procgen factory import check\n[application]\nconfig/name="Procgen Import Check"\n'
                                           '[rendering]\nrenderer/rendering_method="gl_compatibility"\n', encoding='utf-8')
    shutil.copyfile(glb, project / 'asset.glb')
    shutil.copyfile(GODOT_PROBE, project / 'probe.gd')
    run_command([str(godot), '--headless', '--path', str(project), '--import'], directory, 'godot-import', timeout)
    log = run_command([str(godot), '--headless', '--path', str(project), '--script', 'res://probe.gd'], directory, 'godot-probe', timeout)
    lines = [line for line in log['stdout'].splitlines() if line.startswith('PROCGEN_REPORT ')]
    if len(lines) != 1: raise EvidenceError('Godot probe printed no report; see godot-probe-stdout.log')
    return json.loads(lines[0][len('PROCGEN_REPORT '):])


def godot_gate(report, collision_parts, bbox_min, bbox_max):
    failures = []
    if report.get('state') != 'loaded': failures.append(f'Godot could not load the GLB: {report.get("error")}')
    else:
        if report['collision_shapes'] != collision_parts: failures.append(f'{report["collision_shapes"]} collision shapes, want {collision_parts}')
        if report['static_bodies'] != collision_parts: failures.append(f'{report["static_bodies"]} static bodies, want {collision_parts}')
        # glTF is +Y up: Blender (x, y, z) arrives in Godot as (x, z, -y).
        want = [bbox_max[0] - bbox_min[0], bbox_max[2] - bbox_min[2], bbox_max[1] - bbox_min[1]]
        if any(abs(a - b) > 0.01 for a, b in zip(report['mesh_aabb_size'], want)): failures.append(f'Godot AABB {report["mesh_aabb_size"]} != {want}')
    return _gate('godot_import', failures, report=report)


def build(generator, params, output, blender, godot=None, node=None, render=False, timeout=600):
    """Run one factory build into a new output directory. Returns the report (also written as report.json)."""
    started = time.monotonic()
    schema = load_schema()
    if generator not in schema['generators']: raise EvidenceError(f'unknown generator {generator!r}; see describe')
    spec = schema['generators'][generator]
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = {'schema_version': 1, 'generator': generator, 'requested_params': params, 'state': 'rejected', 'gates': [],
              'schema_sha256': file_sha(SCHEMA_PATH), 'blender_script_sha256': file_sha(BLENDER_SCRIPT)}
    p, errors = resolve_params(spec, params)
    report['gates'].append(_gate('params', errors))
    if not errors: report['gates'].append(_gate('constraints', check_constraints(spec, p)))
    report['params'] = p
    if all(g['passed'] for g in report['gates']):
        request = {'generator': generator, 'spec': spec, 'params': p, 'lod_details': lod_details(p['detail']),
                   'output': str(out), 'render': render, 'collision_suffix': COLLISION_SUFFIX, 'uv_res': UV_RES}
        write_json(out / 'request.json', request)
        blender = Path(blender)
        run_command([str(blender), '-b', '--factory-startup', '--python-exit-code', '1', '-P', str(BLENDER_SCRIPT),
                     '--', str(out / 'request.json')], out, 'blender', timeout)
        m = read_json(out / 'measurements.json')
        report['blender'] = m['blender']
        report['gates'] += evaluate_gates(generator, spec, p, m)
        report['outputs'] = {lod['glb']: file_sha(out / lod['glb']) for lod in m['lods']}
        report['outputs']['asset.blend'] = file_sha(out / 'asset.blend')
        if render and (out / 'contact_sheet.png').is_file(): report['outputs']['contact_sheet.png'] = file_sha(out / 'contact_sheet.png')
        khronos = []
        for lod in m['lods']:
            directory = out / ('khronos-' + Path(lod['glb']).stem)
            directory.mkdir()
            try: validate_glb(out / lod['glb'], node, directory, 60)
            except EvidenceError as exc: khronos.append(f'{lod["glb"]}: {exc}')
        report['gates'].append(_gate('khronos', khronos))
        if godot:
            collision_parts = len(m['collision_objects'])
            try: report['gates'].append(godot_gate(_probe_godot(Path(godot), out / m['lods'][0]['glb'], out, 120),
                                                   collision_parts, m['lods'][0]['bbox_min'], m['lods'][0]['bbox_max']))
            except EvidenceError as exc: report['gates'].append(_gate('godot_import', [str(exc)]))
        else: report['gates'].append(_gate('godot_import', [], skipped='no Godot executable given'))
        report['state'] = 'passed' if all(g['passed'] for g in report['gates']) else 'failed'
    report['failed_gates'] = [g['gate'] for g in report['gates'] if not g['passed']]
    report['wall_seconds'] = round(time.monotonic() - started, 2)
    report['not_verified'] = ['art direction and taste', 'shading in a real toon pipeline', 'licence or rights (all geometry is generated)']
    write_json(out / 'report.json', report)
    return report


def _config(key, given):
    if given: return given
    return read_json(LOCAL_CONFIG).get(key) if LOCAL_CONFIG.is_file() else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('describe', help='print the generator schema (parameters, bounds, constraints, parts)')
    run = sub.add_parser('build', help='params JSON -> gated GLBs + report.json in a new directory')
    run.add_argument('params', help='JSON file: {"generator": name, "params": {...}}')
    run.add_argument('output', help='new output directory (must not exist)')
    run.add_argument('--blender'); run.add_argument('--godot'); run.add_argument('--node')
    run.add_argument('--no-godot', action='store_true'); run.add_argument('--render', action='store_true', help='also render contact_sheet.png')
    args = parser.parse_args(argv)
    if args.command == 'describe':
        print(json.dumps(load_schema(), indent=2)); return 0
    request = read_json(args.params)
    blender = _config('blender', args.blender)
    if not blender: raise SystemExit('Set blender in config/local.json or pass --blender')
    godot = None if args.no_godot else _config('godot', args.godot)
    report = build(request.get('generator'), request.get('params', {}), args.output, blender, godot,
                   _config('node', args.node), args.render)
    print(json.dumps({'state': report['state'], 'failed_gates': report['failed_gates'],
                      'failures': {g['gate']: g['failures'] for g in report['gates'] if not g['passed']},
                      'report': str(Path(args.output) / 'report.json')}, indent=2))
    return 0 if report['state'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
