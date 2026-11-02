"""Assemble procgen factory pieces into one Godot level: level JSON -> gated pieces + a runnable Godot project.

level.json: {"pieces": [{"name": "coast", "generator": "coastal_path", "params": {...},
                         "position": [x, y, z], "yaw_deg": 0.0}, ...]}   (Blender metres and degrees, Z up)
Each piece is built by procgen_factory (every gate; Godot optional). The project copies each LOD0 GLB, writes
level.json for procgen_level.gd, and adds trimesh collision for ground parts the factory leaves to the engine (group
"ground" with collision false, e.g. coastal terrain and path). A headless Godot run then reports the assembled level.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

from engine_validation import EvidenceError, file_sha, read_json, run_command, write_json
import procgen_factory as factory

LEVEL_SCRIPT = Path(__file__).with_name('procgen_level.gd')
PROJECT = ('config_version=5\n\n[application]\nconfig/name="Procgen level"\nrun/main_scene="res://level.tscn"\n\n'
           '[rendering]\nrenderer/rendering_method="gl_compatibility"\n')
WINDOWS_RESERVED = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))}
MAX_COORD = 10_000.0      # metres; also keeps placements well inside Godot's single-precision Vector3
SCENE = '[gd_scene load_steps=2 format=3]\n\n[ext_resource type="Script" path="res://procgen_level.gd" id="1"]\n\n[node name="Level" type="Node3D"]\nscript = ExtResource("1")\n'


def trimesh_parts(spec):
    """Ground parts with no factory collision: the engine walks on them, so the level gives them trimesh collision."""
    return sorted(p['name'] for p in spec['parts'].values() if p['group'] == 'ground' and not p.get('collision', True))


def _coord(v):
    # Compare before any float conversion: a huge JSON integer would overflow math.isfinite, and NaN fails the bound.
    return type(v) in (int, float) and -MAX_COORD <= v <= MAX_COORD


def check_level(level, schema):
    errors, names = [], set()
    pieces = level.get('pieces') if isinstance(level, dict) else None
    if not isinstance(pieces, list) or not pieces: return ['level needs a non-empty "pieces" list']
    for i, piece in enumerate(pieces):
        name = piece.get('name') if isinstance(piece, dict) else None
        if not isinstance(name, str) or not factory.NAME_RE.fullmatch(name) or name in WINDOWS_RESERVED:   # names become file names
            errors.append(f'piece {i}: name must fully match {factory.NAME_RE.pattern} and not be a Windows device name'); continue
        if name in names: errors.append(f'piece {name}: duplicate name')
        names.add(name)
        if piece.get('generator') not in schema['generators']: errors.append(f'piece {name}: unknown generator {piece.get("generator")!r}')
        pos, yaw = piece.get('position', [0, 0, 0]), piece.get('yaw_deg', 0.0)
        if not (isinstance(pos, list) and len(pos) == 3 and all(_coord(v) for v in pos)):
            errors.append(f'piece {name}: position must be three numbers within +-{MAX_COORD:g} m')
        if not _coord(yaw): errors.append(f'piece {name}: yaw_deg must be a number within +-{MAX_COORD:g}')
    return errors


def assemble(level_path, output, blender, godot=None, node=None, timeout=180):
    level, schema = read_json(level_path), factory.load_schema()
    errors = check_level(level, schema)
    if errors: raise EvidenceError('; '.join(errors))
    out = Path(output).resolve(); out.mkdir(parents=True, exist_ok=False)
    project = out / 'godot'; project.mkdir()
    manifest = {'schema_version': 1, 'level': str(Path(level_path).resolve()), 'pieces': []}
    for piece in level['pieces']:
        report = factory.build(piece['generator'], piece.get('params', {}), out / 'pieces' / piece['name'], blender, godot, node)
        if report['failed_gates'] or report['state'] not in ('passed', 'incomplete'):
            raise EvidenceError(f'piece {piece["name"]} failed gates {report["failed_gates"]}; see {out / "pieces" / piece["name"] / "report.json"}')
        glb = f'{piece["name"]}.glb'
        shutil.copyfile(out / 'pieces' / piece['name'] / 'asset_LOD0.glb', project / glb)
        manifest['pieces'].append({'name': piece['name'], 'generator': piece['generator'], 'glb': glb, 'sha256': file_sha(project / glb),
                                   'position': piece.get('position', [0, 0, 0]), 'yaw_deg': piece.get('yaw_deg', 0.0),
                                   'trimesh_parts': trimesh_parts(schema['generators'][piece['generator']]), 'piece_state': report['state']})
    write_json(project / 'level.json', manifest)
    (project / 'project.godot').write_text(PROJECT, encoding='utf-8')
    (project / 'level.tscn').write_text(SCENE, encoding='utf-8')
    shutil.copyfile(LEVEL_SCRIPT, project / 'procgen_level.gd')
    if godot:
        run_command([str(godot), '--headless', '--path', str(project), '--import'], out, 'godot-import', timeout)
        log = run_command([str(godot), '--headless', '--path', str(project), '--', '--report'], out, 'godot-level', timeout)
        lines = [l for l in log['stdout'].splitlines() if l.startswith('LEVEL_REPORT ')]
        if len(lines) != 1: raise EvidenceError('Godot printed no level report; see godot-level-stdout.log')
        manifest['godot'] = json.loads(lines[0][len('LEVEL_REPORT '):])
        want = sum(1 for p in manifest['pieces'] for _ in p['trimesh_parts'])
        if manifest['godot']['pieces'] != len(manifest['pieces']) or manifest['godot']['engine_trimesh'] != want:
            raise EvidenceError(f'Godot level mismatch: {manifest["godot"]}, want {len(manifest["pieces"])} pieces and {want} engine trimesh collisions')
    write_json(out / 'level-report.json', manifest)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('command', choices=['assemble']); parser.add_argument('level'); parser.add_argument('output')
    parser.add_argument('--blender'); parser.add_argument('--godot'); parser.add_argument('--node'); parser.add_argument('--no-godot', action='store_true')
    args = parser.parse_args(argv)
    blender = factory._config('blender', args.blender)
    if not blender: raise SystemExit('Set blender in config/local.json or pass --blender')
    godot = None if args.no_godot else factory._config('godot', args.godot)
    manifest = assemble(args.level, args.output, blender, godot, factory._config('node', args.node))
    print(json.dumps({'pieces': [p['name'] for p in manifest['pieces']], 'godot': manifest.get('godot'), 'project': str(Path(args.output) / 'godot')}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
