"""Bounded, read-only family and recall projections over existing asset/job records.

Lineage is attribution, not proof of artistic acceptance or current file integrity.
No files are opened and no mutation, staging, model or queue operation is called.
"""
from __future__ import annotations

import json
import math
import re

from .asset_reads import AssetReadError, ENTITY, HEX32, require
from .core import decode

MAX_DEPTH = 12
MAX_NODES = 64
MAX_EDGES = 128
MAX_PARENTS = 16
MAX_CHILDREN = 20
MAX_CHILD_SCAN = 5000
MAX_JSON = 16 * 1024
MAX_RECIPE = 256 * 1024
_COLUMNS = """id,job_id,output_index,substr(title,1,200) AS title,
    substr(preset_name,1,200) AS preset_name,preset_id,media_type,trashed_at,
    CASE WHEN length(CAST(lineage AS BLOB)) <= 16384 THEN lineage END AS lineage,
    CASE WHEN length(CAST(source AS BLOB)) <= 16384 THEN source END AS source"""


def _identity(value, pattern=ENTITY):
    require(type(value) is str and pattern.fullmatch(value) is not None,
            'Valid asset and Workspace identities are required')
    return value


def _json(value, kind):
    try:
        result = decode(value) if type(value) is str and len(value) <= MAX_JSON else None
    except (ValueError, RecursionError):
        return None
    return result if type(result) is kind else None


def _parents(row):
    value = _json(row['lineage'], list)
    if (value is None or len(value) > MAX_PARENTS or
            any(type(x) is not str or not ENTITY.fullmatch(x) for x in value)):
        return None
    return list(dict.fromkeys(value))


def _scalar(value):
    if type(value) is str and len(value) <= 80 and value.isprintable(): return value
    if type(value) is int and value.bit_length() <= 256: return str(value)
    if type(value) is float and math.isfinite(value): return str(value)
    return None


def _row(db, asset_id):
    return db.execute('SELECT '+_COLUMNS+' FROM assets WHERE id=?', (asset_id,)).fetchone()


def _node(studio, asset_id, row):
    if row is None:
        return {'id': asset_id, 'title': 'Missing asset '+asset_id, 'state': 'missing',
                'operation': None, 'seed': None, 'strength': None}
    source = _json(row['source'], dict) or {}
    job = studio.jobs.get(row['job_id'], {})
    controls = job.get('controls') if type(job) is dict else None
    controls = controls if type(controls) is dict else {}
    return {'id': asset_id, 'title': str(row['title'] or asset_id)[:200],
            'state': 'active' if row['trashed_at'] is None else 'trashed',
            'operation': str(row['preset_name'] or 'Operation not recorded')[:200],
            'seed': _scalar(source.get('seed')), 'strength': _scalar(controls.get('denoise'))}


def observe(studio, asset_id, *, workspace_id, children=False):
    asset_id = _identity(asset_id); _identity(workspace_id, HEX32)
    require(type(children) is bool, 'Children must be true or false')
    nodes, edges, gaps, seen, visiting = [], [], [], set(), set()
    truncated = False
    with studio.assets.connection() as db:
        db.execute('BEGIN')
        studio.assets._check_scope(db, workspace_id)

        def visit(identifier, depth):
            nonlocal truncated
            if identifier in visiting:
                if len(gaps) < MAX_NODES: gaps.append({'id': identifier, 'reason': 'cycle'})
                return
            if identifier in seen: return
            if depth >= MAX_DEPTH or len(seen) >= MAX_NODES:
                truncated = True
                if len(gaps) < MAX_NODES: gaps.append({'id': identifier, 'reason': 'depth' if depth >= MAX_DEPTH else 'size'})
                return
            seen.add(identifier); visiting.add(identifier)
            row = _row(db, identifier)
            parents = _parents(row) if row is not None else []
            if parents is None:
                if len(gaps) < MAX_NODES: gaps.append({'id': identifier, 'reason': 'invalid-lineage'})
            else:
                for parent in parents:
                    if len(edges) >= MAX_EDGES:
                        truncated = True
                        break
                    edges.append({'parent': parent, 'child': identifier})
                    visit(parent, depth+1)
            visiting.remove(identifier)
            nodes.append(_node(studio, identifier, row))

        visit(asset_id, 0)
        descendants, child_truncated, scanned = None, False, 0
        if children:
            descendants = []
            # No second relation store or unbounded JSON scan. Child discovery is
            # explicit, newest-first and discloses both result and search bounds.
            cursor = db.execute('SELECT '+_COLUMNS+' FROM assets ORDER BY created_at DESC,id LIMIT ?',
                                (MAX_CHILD_SCAN+1,))
            for row in cursor:
                if scanned == MAX_CHILD_SCAN:
                    child_truncated = True
                    break
                scanned += 1
                parents = _parents(row)
                if parents is None:
                    child_truncated = True
                    continue
                if asset_id not in parents: continue
                if len(descendants) == MAX_CHILDREN:
                    child_truncated = True
                    break
                descendants.append(_node(studio, row['id'], row))
            cursor.close()
    return {'version': 1, 'asset_id': asset_id, 'workspace_id': workspace_id,
            'nodes': nodes, 'edges': edges, 'gaps': gaps, 'truncated': truncated,
            'children': descendants, 'children_truncated': child_truncated, 'children_scanned': scanned,
            'limits': {'depth': MAX_DEPTH, 'nodes': MAX_NODES, 'children': MAX_CHILDREN, 'child_scan': MAX_CHILD_SCAN},
            'observation_only': True, 'generation_submitted': False, 'media_bytes_verified': False}


def _copy_recipe(value):
    remaining = 40000
    def check(item, depth=0):
        nonlocal remaining
        remaining -= 1
        require(remaining >= 0 and depth <= 16, 'Retained recipe exceeds recall bounds')
        if type(item) is dict:
            require(len(item) <= 4096, 'Retained recipe exceeds recall bounds')
            for key, child in item.items():
                require(type(key) is str and len(key) <= 256, 'Invalid retained recipe key')
                check(child, depth+1)
        elif type(item) is list:
            require(len(item) <= 4096, 'Retained recipe exceeds recall bounds')
            for child in item: check(child, depth+1)
        elif type(item) is str: require(len(item) <= 65536, 'Retained recipe text exceeds recall bounds')
        elif type(item) is float: require(math.isfinite(item), 'Invalid retained recipe number')
        else: require(item is None or type(item) in (bool, int), 'Invalid retained recipe value')
    check(value)
    raw = json.dumps(value, allow_nan=False)
    require(len(raw.encode('utf-8')) <= MAX_RECIPE, 'Retained recipe exceeds recall bounds')
    return json.loads(raw)


def recall(studio, asset_id, *, workspace_id):
    asset_id = _identity(asset_id); _identity(workspace_id, HEX32)
    with studio.assets.connection() as db:
        db.execute('BEGIN'); studio.assets._check_scope(db, workspace_id)
        row = _row(db, asset_id)
        require(row is not None and row['trashed_at'] is None, 'Restore an existing asset before recalling its recipe')
        job = studio.jobs.get(row['job_id'])
        require(type(job) is dict and job.get('status') == 'completed' and not job.get('operation')
                and all(job.get(key) is None for key in ('tile', 'parallax', 'native_recipe')),
                'This output needs its specialized or unresolved workflow; open its original recipe instead')
        source = _json(row['source'], dict)
        require(source is not None, 'Output evidence is unavailable')
        seed = source.get('seed')
        require(type(seed) in (int, str) and re.fullmatch(r'[0-9]{1,20}', str(seed)) is not None
                and 0 <= int(seed) <= 2**64-1, 'This output has no valid recorded seed')
        try: recipe = _copy_recipe(studio.export_recipe(job))
        except (KeyError, TypeError) as exc:
            raise AssetReadError('This output has incomplete retained recipe evidence') from exc
        require(type(recipe.get('controls')) is dict and type(recipe.get('workflow')) is dict,
                'This output has no complete recorded recipe')
        controls = dict(recipe['controls'])
        bindings = job.get('prompt_bindings') or {}
        submissions = recipe.get('submissions', [])
        require(type(submissions) is list, 'Invalid retained submission evidence')
        matches = [s for s in submissions if type(s) is dict and source.get('prompt_id') and s.get('prompt_id') == source['prompt_id']]
        for key in ('positive', 'negative'):
            positions = bindings.get(key) if type(bindings) is dict else None
            if not positions:
                require(not controls.get(key), 'No unambiguous submitted wording is retained for this output')
                continue
            require(type(positions) is list and len(positions) <= 32 and len(matches) == 1,
                    'No unambiguous submitted wording is retained for this output')
            texts = []
            for binding in positions:
                try:
                    require(type(binding) in (list, tuple) and len(binding) == 2, 'Invalid retained wording binding')
                    text = matches[0]['graph'][str(binding[0])]['inputs'][binding[1]]
                except (KeyError, TypeError, IndexError):
                    raise AssetReadError('No unambiguous submitted wording is retained for this output') from None
                require(type(text) is str and len(text) <= 65536, 'Invalid retained wording')
                texts.append(text)
            require(len(set(texts)) == 1, 'Companion wording differs; inspect the original workflow instead')
            controls[key] = texts[0]
        controls['seed'] = str(seed)
        # Keep the exported baseline intact for the existing recipe-check route.
        # Effective output wording/seed are explicit edits applied only after that check.
        recipe['submissions'] = []
        recipe['outputs'] = []
        return {'version': 1, 'asset_id': asset_id, 'workspace_id': workspace_id,
                'recipe': recipe, 'controls': controls, 'parent_assets': recipe.get('parent_assets', []),
                'observation_only': True, 'generation_submitted': False, 'media_bytes_verified': False}
