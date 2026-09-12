"""Package Studio atlases/GLBs and verify them with an explicitly selected Godot.

Packaging performs no engine execution. Verification observes actual sprite
signals at a fixed simulation timestep, and validates optional GLBs with Khronos
before importing them. It is not artistic, collision or licence acceptance.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
from typing import Any

from engine_validation import (EvidenceError, atlas_evidence, file_sha, inspect_glb, read_json,
                               require, run_command, validate_glb, write_json)

GodotAdapterError = EvidenceError
MAX_MANIFEST_BYTES = 4 * 1024**2
FILTERS = {'nearest': 1, 'linear': 2}
FIXED_FPS = 240
MAX_CYCLE_MS = 30_000


def _require(condition, message):
    require(condition, message)


def _absolute_directory(value, label, exists=True):
    path = Path(value).expanduser()
    require(path.is_absolute(), label + ' must be an absolute path')
    require(not path.is_symlink(), label + ' must not be a symlink')
    path = path.resolve()
    if exists:
        require(path.is_dir(), label + ' is not a directory')
    return path


def _input_file(root, value, label):
    require(isinstance(value, str) and value and '\\' not in value, label + ' must be a portable relative path')
    path = Path(value)
    require(not path.is_absolute() and '..' not in path.parts and ':' not in value, label + ' escapes input_root')
    resolved = (root / path).resolve()
    require(resolved.is_relative_to(root) and resolved.is_file(), label + ' is missing or escapes input_root')
    return resolved


def _finite_number(value, label):
    require(type(value) in (float, int) and math.isfinite(value), label + ' must be a finite number')
    return float(value)


def _read_atlas_manifest(path):
    manifest = read_json(path)
    require(isinstance(manifest, dict) and type(manifest.get('schema_version')) is int
            and manifest['schema_version'] == 1 and manifest.get('kind') == 'sprite_atlas',
            'Expected Studio sprite_atlas manifest schema 1')
    clip = manifest.get('clip')
    require(isinstance(clip, str) and 1 <= len(clip) <= 120 and all(ord(c) >= 32 for c in clip),
            'Atlas clip must be 1..120 printable characters')
    require(type(manifest.get('loop')) is bool, 'Atlas loop must be boolean')
    canvas, anchor = manifest.get('logical_canvas'), manifest.get('anchor')
    require(isinstance(canvas, list) and len(canvas) == 2 and all(type(v) is int and 1 <= v <= 8192 for v in canvas),
            'logical_canvas must be two positive integers up to 8192')
    require(isinstance(anchor, list) and len(anchor) == 2 and all(type(v) is int for v in anchor)
            and all(0 <= anchor[i] <= canvas[i] for i in range(2)), 'anchor lies outside logical_canvas')
    require(manifest.get('filter', 'nearest') in FILTERS, 'filter must be nearest or linear')
    require(isinstance(manifest.get('atlas'), str) and manifest['atlas'], 'Atlas PNG path is required')
    require(isinstance(manifest.get('atlas_sha256'), str) and re.fullmatch('[0-9a-f]{64}', manifest['atlas_sha256']),
            'Atlas SHA-256 is required')
    frames = manifest.get('frames')
    require(isinstance(frames, list) and 1 <= len(frames) <= 512, 'Expected 1..512 atlas frames')
    seen = set()
    for frame in frames:
        require(isinstance(frame, dict), 'Frame must be an object')
        identifier = frame.get('id')
        require(isinstance(identifier, str) and 1 <= len(identifier) <= 200 and identifier not in seen,
                'Frame has a missing or duplicate ID')
        seen.add(identifier)
        region = frame.get('region')
        require(isinstance(region, list) and len(region) == 4 and all(type(v) is int and v >= 0 for v in region)
                and region[2:] == canvas, 'Frame must retain the common logical canvas')
        require(type(frame.get('duration_ms')) is int and 1 <= frame['duration_ms'] <= 60_000,
                'Frame has invalid duration_ms')
    return manifest


def describe():
    return {'adapter': 'godot-asset-adapter', 'schema_version': 2,
            'operations': ['preflight', 'package', 'execute', 'inspect', 'export'],
            'input_contract': 'Studio sprite_atlas and optional self-contained GLB under explicit input_root',
            'output_contract': 'exclusive Godot project, signal timing, source checksums and independent format/import reports',
            'unsupported': ['live asynchronous cancellation', 'rig retargeting', 'collision acceptance',
                            'root motion acceptance', 'art acceptance', 'licence clearance']}


def preflight(godot_path, timeout=30, evidence_dir=None):
    executable = Path(godot_path).expanduser()
    require(executable.is_absolute() and executable.is_file(), 'Godot executable must be an existing absolute path')
    executable = executable.resolve()
    if evidence_dir is None:
        with tempfile.TemporaryDirectory(prefix='studio-godot-preflight-') as directory:
            return preflight(executable, timeout, Path(directory))
    result = run_command([str(executable), '--headless', '--version'], evidence_dir, 'godot-version', timeout)
    version = result['stdout'].strip()
    require(re.fullmatch(r'4\.\d+[^\r\n]*', version), 'Godot 4 headless preflight failed')
    return {'operation_id': 'godot-preflight', 'state': 'ready', 'runtime': {
        'path': str(executable), 'sha256': file_sha(executable), 'version': version},
        'measurement_method': 'Godot --headless --version'}


def _quote(value):
    return json.dumps(value, ensure_ascii=False)


def _project_tscn(manifest):
    canvas, anchor = manifest['logical_canvas'], manifest['anchor']
    textures, frames = [], []
    for index, frame in enumerate(manifest['frames']):
        name = f'AtlasTexture_{index}'
        textures += [f'[sub_resource type="AtlasTexture" id="{name}"]', 'atlas = ExtResource("1_atlas")',
                     'region = Rect2(%s)' % ', '.join(map(str, frame['region'])), 'filter_clip = true', '']
        frames.append('{\n"duration": %.12g,\n"texture": SubResource("%s")\n}' % (frame['duration_ms'] * 60 / 1000, name))
    return '\n'.join([
        f'[gd_scene load_steps={len(frames) + 4} format=3]', '',
        '[ext_resource type="Texture2D" path="res://assets/atlas.png" id="1_atlas"]',
        '[ext_resource type="Script" path="res://verify.gd" id="2_verify"]', '', *textures,
        '[sub_resource type="SpriteFrames" id="SpriteFrames_adapter"]',
        'animations = [{', '"frames": [' + ',\n'.join(frames) + '],',
        '"loop": ' + str(manifest['loop']).lower() + ',', '"name": &' + _quote(manifest['clip']) + ',',
        '"speed": 60.0', '}]', '', '[node name="Verification" type="Node"]',
        'script = ExtResource("2_verify")', f'metadata/asset_anchor = Vector2({anchor[0]}, {anchor[1]})',
        f'metadata/logical_canvas = Vector2({canvas[0]}, {canvas[1]})',
        'metadata/atlas_filter = &' + _quote(manifest.get('filter', 'nearest')), '',
        '[node name="SpritePlayback" type="AnimatedSprite2D" parent="."]',
        'sprite_frames = SubResource("SpriteFrames_adapter")', 'animation = &' + _quote(manifest['clip']),
        'centered = true', 'offset = Vector2(%.12g, %.12g)' % (canvas[0] / 2 - anchor[0], canvas[1] / 2 - anchor[1]),
        f'texture_filter = {FILTERS[manifest.get("filter", "nearest")]}', ''])


def package_project(input_root, atlas_manifest, output_root, glb_path=None):
    source_root = _absolute_directory(input_root, 'input_root')
    target = _absolute_directory(output_root, 'output_root', exists=False)
    require(not target.exists(), 'output_root already exists; retained attempts are never rerun')
    manifest_path = _input_file(source_root, atlas_manifest, 'atlas_manifest')
    manifest_sha = file_sha(manifest_path)
    manifest = _read_atlas_manifest(manifest_path)
    require(file_sha(manifest_path) == manifest_sha, 'Atlas manifest changed while reading')
    image = _input_file(manifest_path.parent, manifest['atlas'], 'atlas PNG')
    glb = _input_file(source_root, glb_path, 'glb_path') if glb_path else None
    require(glb is None or glb.suffix.lower() == '.glb', 'glb_path must name a .glb file')
    require(image.stat().st_size <= 128 * 1024**2 and (glb is None or glb.stat().st_size <= 128 * 1024**2),
            'Native source exceeds the 128 MiB byte budget')
    require(file_sha(image) == manifest['atlas_sha256'], 'Atlas PNG SHA-256 mismatch')
    glb_sha = file_sha(glb) if glb else None
    target.parent.mkdir(parents=True, exist_ok=True); target.mkdir()
    (target / 'assets').mkdir()
    shutil.copyfile(image, target / 'assets/atlas.png')
    require(file_sha(target / 'assets/atlas.png') == manifest['atlas_sha256'], 'Atlas changed while snapshotting')
    if glb:
        shutil.copyfile(glb, target / 'assets/ember.glb')
        require(file_sha(target / 'assets/ember.glb') == glb_sha, 'GLB changed while snapshotting')
    (target / 'project.godot').write_text(
        '; Studio engine-evidence project; no imported scripts or plugins\n[application]\n'
        'config/name="Studio Godot Asset Verification"\nrun/main_scene="res://main.tscn"\n'
        '[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
        '[debug]\nfile_logging/enable_file_logging=false\n'
        '[importer_defaults]\nscene={\n"animation/fps": 100.0,\n'
        '"animation/remove_immutable_tracks": false,\n"meshes/generate_lods": false,\n'
        '"meshes/create_shadow_meshes": false,\n"nodes/use_name_suffixes": false,\n'
        '"nodes/use_node_type_suffixes": false\n}\n', encoding='utf-8', newline='\n')
    (target / 'main.tscn').write_text(_project_tscn(manifest), encoding='utf-8', newline='\n')
    script = Path(__file__).with_name('godot_probe.gd').read_text(encoding='utf-8')
    (target / 'verify.gd').write_text(script.replace('__GLB_PATH__', 'res://assets/ember.glb' if glb else ''), encoding='utf-8', newline='\n')
    write_json(target / 'atlas-manifest.json', manifest)
    package = {'operation_id': 'godot-package', 'state': 'packaged', 'project_root': str(target),
               'manifest_sha256': manifest_sha, 'atlas_sha256': manifest['atlas_sha256'], 'glb_sha256': glb_sha,
               'frame_count': len(manifest['frames']), 'anchor': manifest['anchor'],
               'filter': manifest.get('filter', 'nearest'), 'clip': manifest['clip']}
    write_json(target / 'package.json', package)
    return package


def _engine_report_from_stdout(stdout):
    lines = [line.removeprefix('GODOT_ADAPTER_REPORT=') for line in stdout.splitlines()
             if line.startswith('GODOT_ADAPTER_REPORT=')]
    require(len(lines) == 1, 'Godot must return exactly one engine report')
    from engine_validation import parse_json
    value = parse_json(lines[0])
    require(isinstance(value, dict), 'Godot report was not an object')
    return value


def _verify_report(report, manifest, wants_glb, atlas=None):
    sprite = report.get('sprite')
    require(isinstance(sprite, dict), 'Engine report has no sprite section')
    for key, expected in (('frame_count', len(manifest['frames'])), ('anchor', manifest['anchor']),
                          ('logical_canvas', manifest['logical_canvas']), ('loop', manifest['loop']),
                          ('animation', manifest['clip']), ('filter', manifest.get('filter', 'nearest')),
                          ('texture_filter', FILTERS[manifest.get('filter', 'nearest')])):
        require(sprite.get(key) == expected, 'Godot ' + key + ' differs from manifest')
    error = sprite.get('anchor_world_error')
    require(isinstance(error, list) and len(error) == 2 and all(abs(_finite_number(v, 'anchor error')) < 1e-5 for v in error),
            'Godot anchor is not placed at node origin')
    frames = sprite.get('frames')
    require(isinstance(frames, list) and len(frames) == len(manifest['frames']), 'Godot did not report every frame')
    for i, (actual, expected) in enumerate(zip(frames, manifest['frames'])):
        require(isinstance(actual, dict) and actual.get('region') == expected['region'], 'Godot atlas region mismatch')
        require(abs(_finite_number(actual.get('relative_duration'), 'relative_duration') - expected['duration_ms'] * .06) < 1e-5,
                'Godot relative duration differs from duration_ms / 1000 * fps')
        require(abs(_finite_number(actual.get('duration_ms'), 'duration_ms') - expected['duration_ms']) < .001,
                'Godot configured duration differs from manifest')
        require(isinstance(actual.get('alpha'), dict), 'Godot alpha inspection is missing')
        if atlas:
            require(actual['alpha'] == atlas['frames'][i], 'Godot alpha pixels/bounds differ from original, including blank frames')
    expected_total = sum(f['duration_ms'] for f in manifest['frames'])
    require(abs(_finite_number(sprite.get('total_duration_ms'), 'total_duration_ms') - expected_total) < .001,
            'Godot configured cycle differs from manifest')
    playback = report.get('playback')
    require(isinstance(playback, dict) and playback.get('completed') is True, 'No observed playback completion')
    require(playback.get('signal') == ('animation_looped' if manifest['loop'] else 'animation_finished'), 'Wrong completion signal')
    require(playback.get('timebase') == 'process-delta' and playback.get('fixed_fps') == FIXED_FPS,
            'Playback must disclose the fixed simulation timebase')
    require(abs(_finite_number(playback.get('speed_scale'), 'speed_scale') - 1) < 1e-9, 'Playback speed must be one')
    tolerance = 2 * 1000 / FIXED_FPS + .01
    require(abs(_finite_number(playback.get('elapsed_ms'), 'elapsed_ms') - expected_total) <= tolerance,
            'Observed cycle duration differs from manifest')
    events = playback.get('frame_events')
    require(isinstance(events, list) and all(isinstance(e, dict) for e in events) and [e.get('frame') for e in events] == list(range(len(frames))),
            'Observed frame sequence differs from manifest')
    boundary = 0
    for event, frame in zip(events, manifest['frames']):
        require(abs(_finite_number(event.get('elapsed_ms'), 'frame boundary') - boundary) <= tolerance,
                'Observed frame boundary differs from manifest')
        boundary += frame['duration_ms']
    if wants_glb:
        glb = report.get('glb')
        require(isinstance(glb, dict) and glb.get('loaded') is True and glb.get('meshes'), 'Godot did not import the requested GLB mesh')
        require(glb.get('import_profile', {}).get('animation_fps') == 100, 'Godot did not apply the declared animation import profile')
        require(isinstance(glb.get('animation_samples'), list), 'GLB animation sampling evidence is missing')
        for clip in glb['animation_samples']:
            require(isinstance(clip, dict) and len(clip.get('samples', [])) == 3, 'Incomplete GLB clip sampling')


def execute(input_root, atlas_manifest, output_root, godot_path, glb_path=None, timeout=120, *, node_path=None):
    require(type(timeout) in (int, float) and math.isfinite(timeout) and 1 <= timeout <= 600, 'Timeout must be 1..600 seconds')
    started = time.monotonic()
    package = package_project(input_root, atlas_manifest, output_root, glb_path)
    target = Path(package['project_root'])
    write_json(target / 'execution-intent.json', {'schema_version': 2, 'state': 'prepared', 'package': package,
                                                'timeout_seconds': timeout, 'fixed_fps': FIXED_FPS})
    def remaining():
        seconds = timeout - (time.monotonic() - started)
        require(seconds > 0, 'Execution time budget exhausted; no later command started')
        return seconds
    try:
        manifest = _read_atlas_manifest(target / 'atlas-manifest.json')
        require(sum(f['duration_ms'] for f in manifest['frames']) <= MAX_CYCLE_MS, 'Verification cycle exceeds the 30-second simulation budget')
        original = atlas_evidence(target / 'assets/atlas.png', manifest)
        write_json(target / 'atlas-source-report.json', original)
        gltf = None
        if glb_path:
            if node_path is None:
                config = Path(__file__).resolve().parents[1] / 'config/local.json'
                if config.is_file():
                    node_path = read_json(config).get('node')
            gltf = validate_glb(target / 'assets/ember.glb', node_path, target, min(60, remaining()))
            write_json(target / 'gltf-validation.json', gltf)
        runtime = preflight(godot_path, min(30, remaining()), target)
        commands = [[runtime['runtime']['path'], '--headless', '--path', str(target), '--import'],
                    [runtime['runtime']['path'], '--headless', '--path', str(target), '--fixed-fps', str(FIXED_FPS)]]
        logs = [run_command(command, target, label, remaining()) for command, label in zip(commands, ('godot-import', 'godot-playback'))]
        report = _engine_report_from_stdout(logs[-1]['stdout'])
        write_json(target / 'engine-report.json', report)
        _verify_report(report, manifest, glb_path is not None, original)
        for relative, expected in (('assets/atlas.png', package['atlas_sha256']), ('assets/ember.glb', package['glb_sha256'])):
            if expected:
                require(file_sha(target / relative) == expected, 'Packaged source changed during engine verification')
        if gltf:
            # Source animation indices need not survive engine name sanitization,
            # but every non-RESET imported clip must have real engine samples.
            samples = report['glb']['animation_samples']
            require(len(samples) == len(gltf['source']['animations']), 'Godot did not sample every source animation')
        write_json(target / 'engine-log.json', logs)
        result = {'operation_id': 'godot-execute', 'state': 'verified', 'runtime': runtime['runtime'],
                  'resolved_inputs': {'atlas_manifest': atlas_manifest, 'glb': glb_path}, 'source_hashes': package,
                  'output_paths': {'project': str(target), 'report': str(target / 'engine-report.json'), 'log': str(target / 'engine-log.json')},
                  'report': report, 'gltf_validation': {'state': 'validated', 'validator_version': gltf['validator_version']} if gltf else {'state': 'not_requested'},
                  'warnings': ['Fixed-fps signal timing measures simulation time, not wall-clock rendering performance.',
                               'GLB poses are engine-evaluated samples, not full animation or gameplay acceptance.',
                               'Art, rig quality, collision, root motion and rights require separate acceptance.'],
                  'measurement_method': 'Godot import, actual AnimatedSprite2D completion/frame signals, and optional AnimationPlayer pose sampling',
                  'evidence_hashes': {p.name: file_sha(p) for p in target.iterdir() if p.is_file()},
                  'wall_seconds': time.monotonic() - started}
        write_json(target / 'execution.json', result)
        return result
    except Exception as exc:
        try:
            write_json(target / 'failure.json', {'state': 'failed', 'error': str(exc)[:2000], 'wall_seconds': time.monotonic() - started,
                                                'recovery': 'Retained attempt is never rerun. Inspect reports/logs, then choose a new output directory.'})
        except OSError as reporting_error:
            exc.add_note('Could not write failure receipt: ' + str(reporting_error))
        raise


def inspect(project_root):
    root = _absolute_directory(project_root, 'project_root')
    require(not (root / 'failure.json').exists(), 'Recorded engine failure; not a verified export')
    result = read_json(root / 'execution.json')
    require(isinstance(result, dict) and result.get('state') == 'verified', 'No verified execution receipt')
    hashes = result.get('evidence_hashes')
    require(isinstance(hashes, dict) and {'engine-report.json', 'verify.gd', 'main.tscn', 'atlas-manifest.json'} <= hashes.keys(),
            'Execution receipt is missing mandatory evidence hashes')
    for name, digest in hashes.items():
        require(file_sha(_input_file(root, name, 'evidence')) == digest, 'Engine evidence changed: ' + name)
    for name, digest in (('assets/atlas.png', result['source_hashes']['atlas_sha256']), ('assets/ember.glb', result['source_hashes']['glb_sha256'])):
        if digest:
            require(file_sha(_input_file(root, name, 'source')) == digest, 'Verified source changed')
    return result['report']


def export(project_root):
    root = _absolute_directory(project_root, 'project_root')
    inspect(root)
    return {'operation_id': 'godot-export', 'state': 'portable_project', 'project_root': str(root),
            'files': [str(root / name) for name in ('project.godot', 'main.tscn', 'engine-report.json', 'execution.json')]}


def cancel_owned(operation_id):
    return {'operation_id': operation_id, 'state': 'unsupported',
            'warning': 'This synchronous adapter exposes no live cancellation handle; its timeout stops only its owned child.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('describe')
    pre = sub.add_parser('preflight'); pre.add_argument('--godot', required=True)
    package = sub.add_parser('package'); run = sub.add_parser('run')
    for child in (package, run):
        child.add_argument('--input-root', required=True); child.add_argument('--atlas-manifest', required=True)
        child.add_argument('--output-root', required=True); child.add_argument('--glb')
    run.add_argument('--godot', required=True); run.add_argument('--node'); run.add_argument('--timeout', type=float, default=120)
    for name in ('inspect', 'export'):
        sub.add_parser(name).add_argument('--project-root', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'describe': result = describe()
        elif args.command == 'preflight': result = preflight(args.godot)
        elif args.command == 'package': result = package_project(args.input_root, args.atlas_manifest, args.output_root, args.glb)
        elif args.command == 'run': result = execute(args.input_root, args.atlas_manifest, args.output_root, args.godot, args.glb, args.timeout, node_path=args.node)
        elif args.command == 'inspect': result = inspect(args.project_root)
        else: result = export(args.project_root)
        print(json.dumps(result, indent=2)); return 0
    except (EvidenceError, OSError, TypeError, KeyError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr); return 2


if __name__ == '__main__':
    raise SystemExit(main())
