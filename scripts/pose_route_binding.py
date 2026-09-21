#!/usr/bin/env python3
"""Compile, validate or create a synthetic pose-source/native-route binding example."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from studio_workflow import pose_artifact, pose_raster
from studio_workflow.pose_artifact import MAX_BYTES as MAX_JSON_BYTES, loads
from studio_workflow.pose_route_binding import (
    MAX_SOURCE_BYTES, REQUEST_SCHEMA, compile_binding, expected_transform,
    validate_binding,
)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def read_json(path: Path):
    with path.open('rb') as source:
        data = source.read(MAX_JSON_BYTES + 1)
    return loads(data)


def read_source(path: Path) -> bytes:
    with path.open('rb') as source:
        data = source.read(MAX_SOURCE_BYTES + 1)
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError('source image exceeds 20 MiB')
    return data


def receipt(binding):
    return {
        'binding_id': binding['binding_id'],
        'binding_name': binding['binding_name'],
        'route_id': binding['route']['id'],
        'source_sha256': binding['source']['sha256'],
        'request_sha256': binding['request_sha256'],
        'ready_for_execution': False,
        'execution_authorized': False,
        'generation_submitted': False,
    }


def _pin(name):
    return hashlib.sha256(('synthetic-pose-route-example:' + name).encode('ascii')).hexdigest()


def example_documents():
    """Return a deterministic, synthetic artifact, PNG and binding request."""
    points = []
    for index in range(18):
        points.extend([
            20 + (index % 6) * 35,
            20 + (index // 6) * 90,
            .9,
        ])
    imported = json.dumps({'people': [{'pose_keypoints_2d': points}]}).encode('ascii')
    artifact = pose_artifact.import_openpose(
        imported, width=256, height=256, coordinate_space='pixels')
    threshold = .3
    source = pose_raster.render_png(artifact, threshold)
    filtered = [
        name for name in pose_artifact.JOINTS
        if artifact['joints'][name] is None or (
            artifact['joints'][name]['origin'] == 'estimated' and
            artifact['joints'][name]['confidence'] < threshold)
    ]
    renderer_sha256 = pose_raster.renderer_sha256()
    pins = {
        key: _pin(key) for key in (
            'model', 'encoder', 'vae', 'graph', 'nodes', 'runtime',
            'reference_transform', 'prompt_dialect', 'controlnet')
    }
    pins['renderer'] = renderer_sha256
    canvas = artifact['canvas']
    request = {
        'schema': REQUEST_SCHEMA,
        'authority': 'none',
        'execution_authorized': False,
        'generation_submitted': False,
        'binding_name': 'synthetic-sdxl-corrected-skeleton',
        'route': {
            'id': 'sdxl-corrected-skeleton',
            'mechanism': 'sdxl-precomputed-skeleton',
            'source_kind': 'precomputed-skeleton',
            'detector_behavior': 'bypass-precomputed-guide',
            'native_slot': 'control-image',
            'backend_id': 'primary',
            'target_canvas': canvas,
            'pins': pins,
        },
        'source': {
            'kind': 'precomputed-skeleton',
            'sha256': hashlib.sha256(source).hexdigest(),
            'bytes': len(source),
            'format': 'PNG',
            'canvas': canvas,
            'artifact_id': artifact['id'],
            'renderer_id': pose_raster.RENDERER,
            'renderer_sha256': renderer_sha256,
            'threshold': threshold,
            'expected_filtered_joints': filtered,
        },
        'transform': expected_transform('identity', canvas, canvas),
    }
    # Compile before publication so the checked example cannot be internally stale.
    compile_binding(request, source, artifact=artifact)
    return artifact, source, request


def write_example(out_dir: Path):
    out_dir = out_dir.resolve()
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    if out_dir.exists():
        raise FileExistsError('example output directory already exists')
    temporary = Path(tempfile.mkdtemp(
        prefix='.pose-route-binding-example-', dir=out_dir.parent))
    try:
        artifact, source, request = example_documents()
        (temporary / 'artifact.json').write_text(
            json.dumps(artifact, sort_keys=True, indent=2, allow_nan=False) + '\n',
            encoding='utf-8', newline='\n')
        (temporary / 'source.png').write_bytes(source)
        (temporary / 'request.json').write_text(
            json.dumps(request, sort_keys=True, indent=2, allow_nan=False) + '\n',
            encoding='utf-8', newline='\n')
        temporary.rename(out_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {
        'out_dir': str(out_dir),
        'request': str(out_dir / 'request.json'),
        'source': str(out_dir / 'source.png'),
        'artifact': str(out_dir / 'artifact.json'),
        'renderer_sha256': request['source']['renderer_sha256'],
        'ready_for_execution': False,
        'execution_authorized': False,
        'generation_submitted': False,
    }


def build_parser():
    parser = Parser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    example_cmd = commands.add_parser(
        'write-example', help='write one deterministic synthetic request/source/artifact bundle')
    example_cmd.add_argument('out_dir', type=Path)
    compile_cmd = commands.add_parser('compile', help='compile one immutable binding file')
    compile_cmd.add_argument('request', type=Path)
    compile_cmd.add_argument('--source', type=Path, required=True)
    compile_cmd.add_argument('--artifact', type=Path)
    compile_cmd.add_argument('--out', type=Path, required=True)
    validate_cmd = commands.add_parser('validate-binding', help='recompute and validate a saved binding')
    validate_cmd.add_argument('request', type=Path)
    validate_cmd.add_argument('binding', type=Path)
    validate_cmd.add_argument('--source', type=Path, required=True)
    validate_cmd.add_argument('--artifact', type=Path)
    return parser


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
        if args.command == 'write-example':
            print(json.dumps(write_example(args.out_dir), sort_keys=True, allow_nan=False))
            return 0
        request = read_json(args.request)
        source = read_source(args.source)
        artifact = read_json(args.artifact) if args.artifact else None
        if args.command == 'compile':
            result = compile_binding(request, source, artifact=artifact)
            with args.out.open('x', encoding='utf-8', newline='\n') as output:
                json.dump(result, output, sort_keys=True, indent=2, allow_nan=False)
                output.write('\n')
        else:
            result = validate_binding(read_json(args.binding), request, source, artifact=artifact)
        print(json.dumps(receipt(result), sort_keys=True, allow_nan=False))
        return 0
    except (OSError, TypeError, ValueError) as exc:
        print(json.dumps({
            'error': str(exc),
            'ready_for_execution': False,
            'execution_authorized': False,
            'generation_submitted': False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
