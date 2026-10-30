"""Compact environment/model identity recorded on a job at creation (#1765); export_recipe only copies it. Existing evidence only: never hashes a model file."""
import re
from pathlib import Path

SHA = re.compile(r'[0-9a-f]{64}')


def _model(row, assets, models_root):
    entry = {'file': row.get('file'), 'sha256': None, 'asset_id': None}
    pin = assets.get(row.get('asset_id'))
    path = row.get('path')
    if row.get('pin_conflict'): entry['basis'] = 'unknown: several library pins claim this path'
    elif pin is None: entry['basis'] = 'unknown: no exact-path library pin'
    elif not (path and Path(path).is_relative_to(models_root)): entry['basis'] = 'unknown: file is outside the pinned library, so its pin does not describe it'
    elif row.get('pin_mismatch'): entry.update(asset_id=pin['id'], basis='unknown: cached content differs from library pin ' + str(pin['id']))
    elif not isinstance(pin.get('sha256'), str) or not SHA.fullmatch(pin['sha256']): entry['basis'] = 'unknown: library pin has no sha256'
    else: entry.update(sha256=pin['sha256'], asset_id=pin['id'], basis='library pin (not re-hashed at run time)')
    return entry


def build(commit, backend_id, requirements, assets, models_root, references):
    """requirements: Studio.preset_requirements rows; assets: library manifest assets; references: the job's compiled reference records."""
    pins = {a['id']: a for a in assets if isinstance(a, dict) and isinstance(a.get('id'), str)}
    models = [_model(row, pins, Path(models_root)) for row in requirements]
    inputs = [{'slot': r.get('slot'), 'role': r.get('role'), 'sha256': r['sha256']} for r in references if isinstance(r, dict) and isinstance(r.get('sha256'), str)]
    return {'version': 1, 'studio_commit': commit, 'backend_id': backend_id, 'models': models, 'inputs': inputs,
            'unknown': [m['file'] for m in models if m['sha256'] is None]}
