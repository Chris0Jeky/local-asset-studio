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
COLLISION_SUFFIX = '-colonly'   # Godot: static trimesh body; one box per island keeps openings open
SNAP_EPS = 1e-4                 # shared with procgen_blender.shrine so both sides snap identically
LOD_LEVELS = 3
MIN_DETAIL = 4
TOL = 0.001          # 1 mm for exact box dimensions and pivots
OVERLAP_SHRINK = 0.002
UV_RES = 512
# Pivot rule per generator: assets stand on z=0; rooms and shrines start at y=0 (open front / first step).
FRONT_ANCHORED = {'room_kit', 'shrine', 'pier', 'coastal_path', 'tide_pools', 'market_street'}


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
        if not _expected_part(rule, p): continue                      # a constraint on a disabled feature does not apply
        total = sum(coef * p[name] for name, coef in rule['terms'].items())
        if total > rule['le'] + 1e-9: failures.append(f'{rule["doc"]} (value {total:.3f} > {rule["le"]})')
    return failures


def _snap_up(value, step=0.5):
    return math.ceil(value / step - SNAP_EPS) * step


def expected_bounds(generator, p, detail=None):
    """Expected asset bbox size (x, y, z) and per-axis slack fraction for polygonised round extents."""
    detail = p['detail'] if detail is None else detail
    # A UV sphere loses extent both around (segments) and along (rings, no equator vertex when odd).
    round_slack = 1 - math.cos(math.pi / detail) * math.cos(math.pi / (2 * max(detail // 2, 3)))
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
    if generator == 'lighthouse_room':
        # Floor and wall share one outer regular n-gon (apothem rt): extent is between 2*rt and 2*rt/cos(pi/n).
        c = math.cos(math.pi / p['panels'])
        corner = (p['radius'] + p['wall_thickness']) / c
        return [2 * corner, 2 * corner, p['height']], [1 - c, 1 - c, 0]
    if generator == 'pier':
        top = p['water_level'] + p['deck_height']
        z = top + (2.6 + 0.12 if p['lamps'] else 1.0 if p['railing'] else 0.40 if p['bollards'] else 0.0)
        return [p['width'] + 6, p['length'] + 3, z], [0, 0, 0]
    if generator == 'coastal_path':
        # Top: noise ceiling + tufts (<= 0.33 m) or fence tops (posts ray cast to the ground, 0.95 m tall), whichever is
        # higher. Floor: the flattened path at land - 0.05, which always has vertices (a narrow strip may have no other land).
        land = p['land_height']
        grass = p['grass_density'] >= 0.5
        # A ray cast post base is interpolated ground: anywhere up to the highest vertex (land + roughness).
        upper = land + p['roughness'] + max(0.33 if grass else 0.0, 0.95 if p['fence'] else 0.0)
        return [p['width'] + 6, p['length'], upper], [0, 0, 1 - (land - 0.05) / upper]
    if generator == 'tide_pools':
        # The stair (if any) ends where the shelf starts; the sea runs 3 m past the shelf. Top: the stair top, or the shelf
        # (noise ceiling) plus a boulder (radius <= 0.6, centre 0.2 m up in its own scale, z-scale 0.75); floor: a shelf
        # vertex can sit 0.25 m down in a basin.
        n = math.ceil((p['stair_top'] - p['shelf_height']) / 0.18 - SNAP_EPS)
        y0 = p['stair'] * (0.6 + n * 0.3)
        props = 0.6 * (0.2 + 0.75) if p['boulders'] else 0.02 if p['starfish'] or p['shells'] else 0.0   # starfish, shells <= 2 cm
        rock = p['shelf_height'] + p['roughness'] + props
        upper = max(p['stair_top'] if p['stair'] else 0.0, rock)
        lower = max(p['stair_top'] if p['stair'] else 0.0, p['shelf_height'] - 0.25)
        return [p['width'] + 6, y0 + p['length'] + 3, upper], [0, 0, 1 - lower / upper]
    if generator == 'market_street':
        # The paved slab (0.1 m) spans the street, both house rows and 0.5 m; the tallest thing is a house whose seeded
        # 0.9..1.15x height scales its roof too, and which house draws the top depends on the seed.
        top = p['house_height'] + p['roof_height']
        return [p['width'] + 2 * p['house_depth'] + 1.0, p['length'], 0.1 + 1.15 * top], [0, 0, 1 - (0.1 + 0.9 * top) / (0.1 + 1.15 * top)]
    raise EvidenceError(f'unknown generator {generator!r}')


def uv_degenerate(tris, eps=1e-12):
    """UV triangles with (near) zero area: they bake nothing and hide overlaps from the raster test."""
    return sum(1 for (ax, ay), (bx, by), (cx, cy) in tris if abs((bx - ax) * (cy - ay) - (cx - ax) * (by - ay)) < eps)


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


def _expected_part(rule, p):
    return all(lo <= p[key] <= hi for key, (lo, hi) in rule.get('when', {}).items())


def evaluate_gates(generator, spec, p, m):
    """All mesh/naming/LOD gates from Blender measurements m (see procgen_blender.measure)."""
    gates, parts = [], m['parts']
    want = {k: [r['min'], r['max']] for k, r in spec['params'].items() if r.get('gn', True)}
    gates.append(_gate('gn_interface', [f'{k}: GN bounds {m["gn_bounds"].get(k)} != schema {v}'
                                        for k, v in want.items() if m['gn_bounds'].get(k) != v]))
    levels = [('LOD0', parts)] + [(f'LOD{i}', lod['parts']) for i, lod in enumerate(m['lods'][1:], 1)]
    presence = [f'unknown part id {i}' for i in m.get('unknown_part_ids', [])]
    for level, level_parts in levels:
        present = {part['id'] for part in level_parts}
        for key, rule in spec['parts'].items():
            wanted = _expected_part(rule, p)
            if wanted and int(key) not in present: presence.append(f'{level}: missing part {rule["name"]}')
            if not wanted and int(key) in present: presence.append(f'{level}: unexpected part {rule["name"]} for these params')
    gates.append(_gate('parts_present', presence))
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
    # A round extent (or round anchor) with an odd segment count has a vertex at +r but only r*cos(pi/d) at -r,
    # so it sits off-centre on x by r*(1 - cos(pi/d))/2. Even counts and the y axis stay symmetric.
    odd_round = p['detail'] % 2 and (slack[0] or anchors)
    ctol = [TOL + (expected[0] / 4 * (1 - math.cos(math.pi / p['detail'])) if odd_round else 0), TOL]
    if generator == 'lighthouse_room' and p['panels'] % 2:
        ctol[1] += expected[1] / 4 * slack[1]           # odd n-gon: a face at the front, a vertex at the back
    if abs(cmin[0] + cmax[0]) / 2 > ctol[0]: dims.append('asset not centred on x')
    if generator in FRONT_ANCHORED:
        if abs(lod0['bbox_min'][1]) > TOL: dims.append(f'front not at y=0 (min y {lod0["bbox_min"][1]:.4f})')
    elif abs(cmin[1] + cmax[1]) / 2 > ctol[1]: dims.append('asset not centred on y')
    gates.append(_gate('dimensions', dims, measured=[round(v, 4) for v in size], expected=[round(v, 4) for v in expected]))
    manifold, uv = [], []
    for level, level_parts in levels:
        for part in level_parts:
            rule, name = spec['parts'][str(part['id'])], f'{level} {part["name"]}'
            for key in ('nonmanifold_edges', 'inconsistent_edges', 'degenerate_faces', 'loose_verts') + (() if rule.get('open') else ('boundary_edges',)):
                if part.get(key, 0): manifold.append(f'{name}: {part[key]} {key}')
            if not part['uv0_present'] or not part['uv0_finite']: uv.append(f'{name}: UVMap missing or non-finite')
            if not part['uv1_present'] or not part['uv1_in_unit']: uv.append(f'{name}: UVLightmap missing or outside 0..1')
            else:
                if part['uv1_overlap_texels']: uv.append(f'{name}: {part["uv1_overlap_texels"]} overlapping lightmap texels')
                if part['uv1_degenerate']: uv.append(f'{name}: {part["uv1_degenerate"]} zero-area lightmap triangles')
    gates.append(_gate('manifold', manifold))
    gates.append(_gate('uv', uv, note=f'UVMap may overlap (palette/tiling); UVLightmap must not ({UV_RES}^2 texel centres).'))
    tris = [lod['triangles'] for lod in m['lods']]
    gates.append(_gate('triangle_budget', [f'LOD0 {tris[0]} triangles > budget {spec["tri_budget"]}'] if tris[0] > spec['tri_budget'] else [],
                       triangles=tris[0], budget=spec['tri_budget']))
    chain = [] if len(tris) == LOD_LEVELS else [f'{len(tris)} LODs, want {LOD_LEVELS}']
    chain += [f'LOD{i + 1} {tris[i + 1]} > LOD{i} {tris[i]}' for i in range(len(tris) - 1) if tris[i + 1] > tris[i]]
    for i, lod in enumerate(m['lods'][1:], 1):
        lsize = [b - a for a, b in zip(lod['bbox_min'], lod['bbox_max'])]
        exp, sl = expected_bounds(generator, p, lod['detail'])
        if any(not exp[k] * (1 - sl[k]) - TOL <= lsize[k] <= exp[k] + TOL for k in range(3)): chain.append(f'LOD{i} bbox drifted: {lsize}')
        moved = sorted({'xyz'[k] for k in range(3) for key in ('bbox_min', 'bbox_max') if abs(lod[key][k] - lod0[key][k]) > TOL + sl[k] * exp[k]})
        if moved: chain.append(f'LOD{i} bbox moved against LOD0 on axes {moved}')
    gates.append(_gate('lod_chain', chain, triangles=tris, details=[lod['detail'] for lod in m['lods']]))
    names = [part['name'] for part in parts]
    naming = [f'bad name {n!r}' for n in names if not NAME_RE.match(n)]
    naming += [f'duplicate name {n!r}' for n in set(names) if names.count(n) > 1]
    want_col = sorted(part['name'] + COLLISION_SUFFIX for part in parts if spec['parts'][str(part['id'])].get('collision', True))
    want_islands = sum(len(part['islands']) for part in parts if spec['parts'][str(part['id'])].get('collision', True))
    if m['collision_boxes'] != want_islands: naming.append(f'{m["collision_boxes"]} collision boxes, want one per solid island ({want_islands})')
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


def godot_gate(report, collision_parts, bbox_min, bbox_max, collision_boxes):
    failures = []
    if report.get('state') != 'loaded': failures.append(f'Godot could not load the GLB: {report.get("error")}')
    else:
        if report['collision_shapes'] != collision_parts: failures.append(f'{report["collision_shapes"]} collision shapes, want {collision_parts}')
        # Trimesh shapes keep every island box (12 triangles each), so openings between islands stay open.
        if report.get('collision_triangles') != 12 * collision_boxes:
            failures.append(f'{report.get("collision_triangles")} collision triangles, want {12 * collision_boxes} (12 per island box)')
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
        try:
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
                try: report['gates'].append(godot_gate(_probe_godot(Path(godot), out / m['lods'][0]['glb'], out, 120), collision_parts,
                                                       m['lods'][0]['bbox_min'], m['lods'][0]['bbox_max'], m['collision_boxes']))
                except EvidenceError as exc: report['gates'].append(_gate('godot_import', [str(exc)]))
            else: report['gates'].append({**_gate('godot_import', []), 'passed': None, 'skipped': 'no Godot executable given'})
        except (EvidenceError, OSError, ValueError, KeyError, TypeError) as exc:
            # A Blender crash, timeout or partial output is a failed build with retained logs, never a missing report.
            report['gates'] = [g for g in report['gates'] if g['gate'] in ('params', 'constraints')]
            report['gates'].append(_gate('blender', [f'{type(exc).__name__}: {exc}'], logs=['blender-stdout.log', 'blender-stderr.log']))
        results = [g['passed'] for g in report['gates']]
        report['state'] = 'failed' if False in results else 'incomplete' if None in results else 'passed'
    report['failed_gates'] = [g['gate'] for g in report['gates'] if g['passed'] is False]
    report['skipped_gates'] = [g['gate'] for g in report['gates'] if g['passed'] is None]
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
    print(json.dumps({'state': report['state'], 'failed_gates': report['failed_gates'], 'skipped_gates': report['skipped_gates'],
                      'failures': {g['gate']: g['failures'] for g in report['gates'] if g['passed'] is False},
                      'report': str(Path(args.output) / 'report.json')}, indent=2))
    return {'passed': 0, 'incomplete': 3}.get(report['state'], 1)


if __name__ == '__main__':
    sys.exit(main())
