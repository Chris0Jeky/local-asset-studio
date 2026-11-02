"""Synthetic labelled dataset from procgen factory scenes: RGB + planar depth + normals + object-ID masks + cameras.

pool:     sample in-bounds, constraint-satisfying params and build them with the factory (no Godot)
render:   compose rooms/shrines with scattered props and render labelled views (Cycles CPU)
validate: re-check every label independently (fresh GLB import, own BVH, pixel-centre rays from camera.json)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import sys

from engine_validation import EvidenceError, read_json, run_command, write_json
import procgen_factory as factory

BLENDER_SCRIPT = Path(__file__).with_name('procgen_dataset_blender.py')
PROP_CAPS = {'width': 0.6, 'height': 1.0}    # keep scattered props furniture-sized
MAX_DETAIL = 24


def sample_params(spec, rng, fixed=None, tries=200):
    """Uniform in-bounds params that satisfy the generator's declared constraints (rejection sampling)."""
    for _ in range(tries):
        p = {k: rng.randint(r['min'], r['max']) if r['type'] == 'int' else round(rng.uniform(r['min'], r['max']), 3)
             for k, r in spec['params'].items()}
        p.update(fixed or {})
        if 'detail' in p: p['detail'] = min(p['detail'], MAX_DETAIL)
        resolved, errors = factory.resolve_params(spec, p)
        if not errors and not factory.check_constraints(spec, resolved): return p
    raise EvidenceError('no constraint-satisfying sample found')


def pool(out, blender, rooms=8, shrines=6, props_per_kind=8, seed=20261102, node=None):
    out = Path(out); out.mkdir(parents=True, exist_ok=False)
    schema, rng, builds = factory.load_schema(), random.Random(seed), {}
    node = node or factory._config('node', None)     # Khronos validation needs Node
    plan = [('room_kit', {}, rooms), ('shrine', {}, shrines)] + [('prop', {'kind': k}, props_per_kind) for k in range(3)]
    for generator, fixed, count in plan:
        for i in range(count):
            p = sample_params(schema['generators'][generator], rng, fixed)
            if generator == 'prop': p.update({k: min(p[k], cap) for k, cap in PROP_CAPS.items()})
            name = f'{generator}{fixed.get("kind", "")}-{i:02d}'
            write_json(out / f'{name}.json', {'generator': generator, 'params': p})
            report = factory.build(generator, p, out / name, blender, node=node)
            builds[name] = {'state': report['state'], 'failed_gates': report['failed_gates']}
    write_json(out / 'pool.json', {'seed': seed, 'builds': builds, 'note': 'built without Godot, so passing builds are "incomplete"'})
    return builds


def _blender(blender, args, directory, label, timeout):
    return run_command([str(blender), '-b', '--factory-startup', '--python-exit-code', '1', '-P', str(BLENDER_SCRIPT), '--', *map(str, args)],
                       Path(directory), label, timeout)


def render(pool_dir, out, blender, scenes=14, views=15, timeout=3600):
    out = Path(out); out.mkdir(parents=True, exist_ok=False)
    _blender(blender, ['render', Path(pool_dir).resolve(), out.resolve(), 0, scenes, views], out, 'render', timeout)
    return sorted(out.glob('scene_*/view_*/rgb.png'))


def validate(dataset, pool_dir, blender, stride=1, timeout=3600):
    dataset = Path(dataset)
    label = next(f'validate{n}' for n in range(1, 10000) if not (dataset / f'validate{n}-exit.json').exists())   # reruns keep earlier logs
    _blender(blender, ['validate', dataset.resolve(), Path(pool_dir).resolve(), stride], dataset, label, timeout)
    return read_json(dataset / 'label-validation.json')['summary']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--blender')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('pool'); p.add_argument('out'); p.add_argument('--rooms', type=int, default=8); p.add_argument('--shrines', type=int, default=6)
    p.add_argument('--props-per-kind', type=int, default=8); p.add_argument('--seed', type=int, default=20261102)
    r = sub.add_parser('render'); r.add_argument('pool'); r.add_argument('out'); r.add_argument('--scenes', type=int, default=14); r.add_argument('--views', type=int, default=15)
    v = sub.add_parser('validate'); v.add_argument('dataset'); v.add_argument('pool'); v.add_argument('--stride', type=int, default=1, help='ray-check 1 of stride^2 pixels; only 1 certifies')
    args = parser.parse_args(argv)
    blender = factory._config('blender', args.blender)
    if not blender: raise SystemExit('Set blender in config/local.json or pass --blender')
    if args.command == 'pool':
        builds = pool(args.out, blender, args.rooms, args.shrines, args.props_per_kind, args.seed)
        print(json.dumps({'built': len(builds), 'usable': sum(not b['failed_gates'] for b in builds.values())}))
    elif args.command == 'render': print(json.dumps({'views': len(render(args.pool, args.out, blender, args.scenes, args.views))}))
    else:
        summary = validate(args.dataset, args.pool, blender, args.stride); print(json.dumps(summary))
        return 0 if summary['certified'] else 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
