"""Bounded CreativeIntent schema, profile registry and content identity helpers."""
from __future__ import annotations
import copy
import hashlib
import json
import math
from pathlib import Path
import re

VERSION = '1.0.0'
ROOT = Path(__file__).resolve().parents[1]
LIMIT = 1024 * 1024
FACETS = ('subject', 'action', 'setting', 'composition', 'camera', 'lighting', 'style', 'palette', 'mood', 'motion', 'voice', 'sound')
TASKS = ('image', 'edit', 'video', 'voice', 'music', 'sound', 'mesh')
ROLES = ('identity', 'pose', 'style', 'costume', 'composition', 'motion', 'voice', 'geometry', 'mask')
EDITABLE = {'brief', 'tags', 'avoid'} | {f'facets.{f}' for f in FACETS}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, required, optional=()):
    need(isinstance(value, dict), 'Expected a JSON object')
    need(set(required) <= value.keys() <= set(required) | set(optional), 'Missing or unknown fields')


def text(value, maximum=4000, empty=False):
    need(isinstance(value, str) and len(value) <= maximum and (empty or bool(value.strip())), 'Invalid text length/type')
    need(not any(ord(c) < 32 and c not in '\n\t\r' for c in value), 'Control character in text')


def strings(value, count=64, maximum=1000):
    need(isinstance(value, list) and len(value) <= count, 'Invalid list size/type')
    for item in value:
        text(item, maximum)


def identifier(value):
    need(isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', value), 'Invalid identifier')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def decode(raw, *, limit=LIMIT):
    need(type(limit) is int and 0 < limit <= 48 * LIMIT, 'Invalid JSON byte limit')
    need(len(raw) <= limit, 'JSON exceeds byte limit' if limit != LIMIT else 'JSON exceeds 1 MiB')
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def reject(value):
        raise ValueError('Nonfinite JSON number')
    def floating(value):
        result = float(value)
        need(math.isfinite(result), 'Nonfinite JSON number')
        return result
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=reject, parse_float=floating)


def read_json(path):
    with Path(path).open('rb') as stream:
        return decode(stream.read(LIMIT + 1))


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def safe_path(root, name):
    text(name, 500)
    need('\\' not in name and ':' not in name and all(p not in ('', '.', '..') for p in name.split('/')), 'Expected portable workspace-relative path')
    base = Path(root).resolve()
    path = (base / name).resolve()
    need(path.is_relative_to(base) and path.is_file(), 'Missing reference or path escapes workspace')
    return path


def file_bytes(root, ref, cap=16 * 1024 * 1024):
    path = safe_path(root, ref['path'])
    with path.open('rb') as stream:
        raw = stream.read(cap + 1)
    need(0 < len(raw) <= cap, 'Reference size limit exceeded')
    need(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'Reference bytes changed')
    return raw


def new_brief(description, task='image'):
    result = {'schema_version': 1, 'id': 'creative-brief', 'task': task, 'brief': description,
              'facets': {}, 'tags': [], 'avoid': [], 'constraints': [], 'references': [],
              'verbatim': {}, 'parameters': {}, 'locked': ['verbatim']}
    return validate(result)


def validate(b):
    fields(b, ('schema_version', 'id', 'task', 'brief', 'facets', 'tags', 'avoid', 'constraints', 'references', 'verbatim', 'parameters', 'locked'))
    need(type(b['schema_version']) is int and b['schema_version'] == 1, 'Expected schema version 1')
    identifier(b['id']); need(b['task'] in TASKS, 'Unsupported task'); text(b['brief'])
    fields(b['facets'], (), FACETS)
    for v in b['facets'].values(): text(v, 1000)
    strings(b['tags'], 80, 120); strings(b['avoid'], 30, 200)
    fields(b['verbatim'], (), ('text', 'lyrics'))
    for v in b['verbatim'].values(): text(v, 4096, True)
    fields(b['parameters'], (), ('language', 'duration_seconds', 'bpm', 'key', 'meter', 'instrumental'))
    for key, v in b['parameters'].items():
        if key in ('duration_seconds', 'bpm'):
            lo, hi = (0.1, 600) if key == 'duration_seconds' else (30, 300)
            need(type(v) in (int, float) and math.isfinite(v) and lo <= v <= hi, 'Numeric parameter out of bounds')
            if key == 'bpm': need(type(v) is int, 'BPM must be integer')
        elif key == 'instrumental': need(type(v) is bool, 'instrumental must be boolean')
        else: text(v, 100)
    need(isinstance(b['references'], list) and len(b['references']) <= 12, 'At most twelve reference records')
    ids = set()
    for r in b['references']:
        fields(r, ('id', 'role', 'kind', 'path', 'sha256', 'take', 'ignore'))
        identifier(r['id']); need(r['id'] not in ids, 'Duplicate reference ID'); ids.add(r['id'])
        need(r['role'] in ROLES and r['kind'] in ('image', 'video', 'audio', 'mesh'), 'Invalid reference role/kind')
        text(r['path'], 500)
        need('\\' not in r['path'] and ':' not in r['path'] and all(p not in ('', '.', '..') for p in r['path'].split('/')), 'Unsafe reference path')
        need(isinstance(r['sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', r['sha256']), 'Reference needs a SHA256')
        strings(r['take'], 12, 300); strings(r['ignore'], 12, 300)
    need(isinstance(b['constraints'], list) and len(b['constraints']) <= 24, 'Constraint cap exceeded')
    ids = set()
    for c in b['constraints']:
        fields(c, ('id', 'text', 'mechanism', 'priority'))
        identifier(c['id']); need(c['id'] not in ids, 'Duplicate constraint ID'); ids.add(c['id'])
        text(c['text'], 500)
        need(c['mechanism'] in ('prompt', 'mask', 'guide', 'verify') and c['priority'] in ('hard', 'soft'), 'Invalid constraint mechanism/priority')
    strings(b['locked'], 30, 100)
    need(all(v in EDITABLE | {'facets', 'verbatim', 'references', 'constraints', 'parameters'} for v in b['locked']), 'Unsupported lock path')
    need(len(canonical(b)) <= 65536, 'Brief byte budget exceeded')
    return b


def profiles():
    data = read_json(ROOT / 'research/prompt-studio/profiles.json')
    need(data['schema_version'] == 1, 'Unknown profile schema')
    rows = data['profiles']; need(len({p['id'] for p in rows}) == len(rows), 'Duplicate profiles')
    for p in rows:
        if 'dialect_check' not in p and 'template_bindings' not in p: continue
        checks = {'anima_aesthetic': 'prose', 'anima_base': 'prose', 'animagine_opt': 'tags'}
        need(isinstance(p.get('dialect_check'), str) and p['dialect_check'] in checks
             and p['dialect'] == checks[p['dialect_check']], 'Unknown or mismatched exact-profile dialect check')
        need(p['negative'] is True and p['min_refs'] == p['max_refs'] == 0
             and p['tasks'] == ['image'], 'Exact profiles currently support text-only images')
        templates = p.get('template_bindings')
        need(isinstance(templates, list) and 1 <= len(templates) <= 8, 'Use 1..8 exact profile templates')
        seen = set()
        for t in templates:
            fields(t, ('preset_id', 'graph_sha256', 'bindings'))
            identifier(t['preset_id']); need(t['preset_id'] not in seen, 'Duplicate exact profile template'); seen.add(t['preset_id'])
            need(isinstance(t['graph_sha256'], str) and re.fullmatch(r'[a-f0-9]{64}', t['graph_sha256']), 'Exact profile template needs a graph SHA256')
            fields(t['bindings'], ('positive', 'negative'))
            for pair in t['bindings'].values():
                need(isinstance(pair, list) and len(pair) == 2 and all(isinstance(x, str) and 0 < len(x) <= 120 for x in pair), 'Invalid exact profile text binding')
            need(t['bindings']['positive'] != t['bindings']['negative'], 'Exact profile text bindings collide')
        need(p['recipes'] == [t['preset_id'] for t in templates], 'Exact profile recipes and templates differ')
    return {p['id']: p for p in rows}


