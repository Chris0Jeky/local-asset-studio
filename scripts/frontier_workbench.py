"""Offline research validation, bounded experiment planning and header-only inspection.
No network requests, subprocesses, model imports, installs or generation submissions.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re
import struct
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
MAX_JSON = 4 * 1024 * 1024
TIERS = {'baseline', 'candidate', 'experimental', 'watchlist', 'unresolved'}
MODALITIES = {'tooling', 'anime', 'image', 'video', '3d', 'training', 'audio', 'research'}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key!r}')
        result[key] = value
    return result


def decode(raw: bytes):
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def read_json(path: Path):
    with path.open('rb') as stream:
        raw = stream.read(MAX_JSON + 1)
    if len(raw) > MAX_JSON:
        raise ValueError(f'JSON exceeds {MAX_JSON} byte limit')
    return decode(raw)


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be non-empty text')


def text_list(value, name):
    if not isinstance(value, list) or not value:
        raise ValueError(f'{name} must be a non-empty list')
    for item in value:
        text(item, name)


def check_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9-]{1,63}', value):
        raise ValueError(f'Invalid ID: {value!r}')


def validate(catalog, recipes):
    for doc in (catalog, recipes):
        if not isinstance(doc, dict) or doc.get('schema_version') != 1:
            raise ValueError('Expected schema_version 1 object')
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(doc.get('as_of', ''))):
            raise ValueError('Missing ISO as_of date')
    if recipes.get('kind') != 'non_executable_blueprints':
        raise ValueError('Blueprints must be explicitly non-executable')
    entries = catalog.get('entries')
    if not isinstance(entries, list) or not entries:
        raise ValueError('Catalog entries must be non-empty')
    ids = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('Catalog entry must be an object')
        key = entry.get('id'); check_id(key)
        if key in ids:
            raise ValueError(f'Duplicate ID: {key}')
        ids.add(key)
        for field in ('title', 'opportunity', 'caveat', 'source'):
            text(entry.get(field), field)
        url = urlsplit(entry['source'])
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            raise ValueError(f'Unsafe source URL for {key}')
        if entry.get('tier') not in TIERS or entry.get('modality') not in MODALITIES:
            raise ValueError(f'Unknown classification for {key}')
        if entry.get('source_status') not in {'reviewed', 'access_blocked'}:
            raise ValueError(f'Unknown source status for {key}')
        if entry.get('local_verified') is not False:
            raise ValueError('This research catalog cannot assert local execution evidence')
        if entry['source_status'] == 'access_blocked' and entry['tier'] != 'unresolved':
            raise ValueError('Blocked source must remain unresolved')
    rows = recipes.get('recipes')
    if not isinstance(rows, list) or not rows:
        raise ValueError('Recipes must be non-empty')
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Recipe must be an object')
        key = row.get('id'); check_id(key)
        if key in seen:
            raise ValueError(f'Duplicate recipe: {key}')
        seen.add(key)
        for field in ('title', 'stop'):
            text(row.get(field), field)
        for field in ('inputs', 'stages', 'variants', 'acceptance', 'sources'):
            text_list(row.get(field), field)
        if row.get('modality') not in MODALITIES:
            raise ValueError(f'Unknown recipe modality: {key}')
        if len(set(row['variants'])) != len(row['variants']):
            raise ValueError('Duplicate variants')
        if set(row['sources']) - ids:
            raise ValueError(f'Unknown sources: {key}')
    return {'entries': len(ids), 'blueprints': len(seen), 'generation_submitted': False}


def load(root: Path = ROOT):
    folder = root / 'research' / 'frontier'
    catalog, recipes = read_json(folder / 'catalog.json'), read_json(folder / 'recipes.json')
    validate(catalog, recipes)
    return catalog, recipes


def plan(catalog, recipes, recipe_id: str, brief: str, seed: int = 4200,
         count: int = 2, max_jobs: int = 12):
    validate(catalog, recipes); text(brief, 'brief')
    if type(count) is not int or not 1 <= count <= 16:
        raise ValueError('count must be 1..16')
    if type(max_jobs) is not int or not 1 <= max_jobs <= 48:
        raise ValueError('max_jobs must be 1..48')
    if type(seed) is not int or not 0 <= seed <= 2**64 - count:
        raise ValueError('seed range would exceed unsigned 64-bit bounds')
    row = next((r for r in recipes['recipes'] if r['id'] == recipe_id), None)
    if row is None:
        raise ValueError(f'Unknown recipe: {recipe_id}')
    total = count * len(row['variants'])
    if total > max_jobs:
        raise ValueError(f'{total} proposed jobs exceeds cap {max_jobs}; lower count')
    selected = [e for e in catalog['entries'] if e['id'] in row['sources']]
    result = {'schema_version': 1, 'kind': 'experiment_intent', 'executable': False,
              'as_of': catalog['as_of'], 'brief': brief, 'recipe': row,
              'source_snapshot': selected,
              'catalog_sha256': digest(catalog), 'max_jobs': max_jobs,
              'note': 'Seeds are experimental labels; some non-diffusion stages may ignore them. '
                      'Same seeds across model families do not imply equivalent noise or fair outputs.',
              'requires': ['Pinned workflow and model bundle', 'Live node-schema validation',
                           'Fresh disk/RAM/VRAM preflight', 'Explicit run approval'],
              'jobs': [{'variant': variant, 'seed': s, 'state': 'proposed'}
                       for variant, s in itertools.product(row['variants'], range(seed, seed + count))]}
    result['plan_sha256'] = digest(result)
    return result


def inspect_header(path: Path):
    """Read bounded JSON header only. Not a full SafeTensors or security validator."""
    if path.suffix.lower() != '.safetensors':
        raise ValueError('Only .safetensors header inspection is supported')
    with path.open('rb') as stream:
        prefix = stream.read(8)
        if len(prefix) != 8:
            raise ValueError('Truncated length prefix')
        length = struct.unpack('<Q', prefix)[0]
        if not 2 <= length <= MAX_JSON:
            raise ValueError('Header outside bounded inspection limit')
        raw = stream.read(length)
        if len(raw) != length:
            raise ValueError('Truncated header')
        stream.seek(0, 2)
        data_size = stream.tell() - 8 - length
    header = decode(raw)
    if not isinstance(header, dict):
        raise ValueError('Header must be a JSON object')
    metadata = header.get('__metadata__', {})
    if not isinstance(metadata, dict) or any(not isinstance(v, str) for v in metadata.values()):
        raise ValueError('Metadata must contain string values')
    keys = []
    for key, item in header.items():
        if key == '__metadata__':
            continue
        if not isinstance(item, dict):
            raise ValueError('Tensor descriptor must be an object')
        shape, offsets = item.get('shape'), item.get('data_offsets')
        if not isinstance(shape, list) or any(type(v) is not int or v < 0 for v in shape):
            raise ValueError('Invalid tensor shape')
        if (not isinstance(offsets, list) or len(offsets) != 2
                or any(type(v) is not int for v in offsets)
                or not 0 <= offsets[0] <= offsets[1] <= data_size):
            raise ValueError('Invalid or out-of-file tensor offsets')
        text(item.get('dtype'), 'dtype')
        keys.append(key)
    if not keys:
        raise ValueError('No tensor descriptors')
    name = path.name.lower()
    destination = None
    if name.startswith('minimax_h3_') and ('fl2va_pruned_' in name or 'ref2va_pruned_' in name):
        destination = 'models/diffusion_models'
    elif name.startswith('qwen3vl_32b_minimax_h3_'):
        destination = 'models/text_encoders'
    elif name in {'minimax_h3_video_vae_fp16.safetensors', 'minimax_h3_audio_vae_fp32.safetensors'}:
        destination = 'models/vae'
    return {'file': str(path), 'header_bytes': length, 'tensor_count': len(keys),
            'sample_tensor_keys': keys[:12], 'metadata': metadata,
            'suggested_relative_folder': destination, 'routing_basis': 'filename hint only',
            'loaded_weights': False, 'moved_file': False,
            'warning': 'Does not validate tensor byte lengths, overlaps, authenticity, licensing or '
                       'loader compatibility. Unknown files must be matched to an upstream model card.'}


def render(catalog, recipes, template: str) -> str:
    validate(catalog, recipes)
    payload = json.dumps({'catalog': catalog, 'recipes': recipes}, ensure_ascii=True)
    for char, escaped in [('&', '\\u0026'), ('<', '\\u003c'), ('>', '\\u003e')]:
        payload = payload.replace(char, escaped)
    if template.count('__FRONTIER_DATA__') != 1:
        raise ValueError('Template must contain exactly one data slot')
    return template.replace('__FRONTIER_DATA__', payload)


def write_json(value, path: Path | None):
    value = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    if path:
        path.write_text(value, encoding='utf-8')
    else:
        print(value, end='')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('validate')
    p = sub.add_parser('plan'); p.add_argument('--recipe', required=True)
    p.add_argument('--brief', required=True); p.add_argument('--seed', type=int, default=4200)
    p.add_argument('--count', type=int, default=2); p.add_argument('--max-jobs', type=int, default=12)
    p.add_argument('--out', type=Path)
    p = sub.add_parser('inspect'); p.add_argument('file', type=Path)
    p = sub.add_parser('render'); p.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'inspect':
            write_json(inspect_header(args.file), None); return 0
        catalog, recipes = load()
        if args.command == 'validate':
            write_json(validate(catalog, recipes), None)
        elif args.command == 'plan':
            write_json(plan(catalog, recipes, args.recipe, args.brief, args.seed,
                            args.count, args.max_jobs), args.out)
        else:
            template = (ROOT / 'research/frontier/workbench.template.html').read_text(encoding='utf-8')
            args.out.write_text(render(catalog, recipes, template), encoding='utf-8')
            print(f'Wrote offline research browser: {args.out}')
        return 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
