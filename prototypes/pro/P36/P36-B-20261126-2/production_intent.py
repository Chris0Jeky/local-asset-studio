"""Read-only projection of a real prepared Production stage into a P36 intent.

No Studio/Production/ModelLibrary constructor, network, queue, reservation or
source mutation is used. A passing report proves retained preparation and fresh
file agreement, not live runtime readiness, owner authority or budget permission.
The caller supplies the trusted Studio root independently of the candidate.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from urllib.parse import urlsplit

import pipeline as p

for _path in (p.REPO_ROOT, p.REPO_ROOT / 'app'):
    if str(_path) not in sys.path: sys.path.insert(0, str(_path))
import project_storage
import prompting
from production import fingerprint as production_fingerprint
from model_requirements import requirements, path_key
from scripts.game_asset_pipeline import graph_check

SCHEMA = 'las.p36-worker-intent/1'
KEYS = {'schema', 'operation', 'family_id', 'stage', 'project_id', 'stage_index',
        'job_id', 'preset_id', 'backend_id', 'graph', 'seed', 'batch_count', 'source_snapshot'}
SNAPSHOT_KEYS = {'studio_root', 'experiments_root', 'workspace_id', 'project_record',
                 'budget_record', 'plan_file_sha256', 'catalog_sha256', 'preset_record',
                 'preset_sha256', 'template_sha256', 'library_sha256', 'bundle_sha256',
                 'observed_files', 'preparation_only'}
PROJECT_ID = re.compile(r'[0-9a-f]{32}\Z')


def _check(condition, code):
    p.require(condition, code.replace('_', ' '), code)


def _exact(value, keys, code):
    _check(type(value) is dict and set(value) == keys, code)


def _sha(value):
    return type(value) is str and p.HEX64.fullmatch(value) is not None


def _safe_path(path):
    path = Path(path).absolute()
    _check(not any(part.lower() in ('private', '_owner', 'owner-models') for part in path.parts), 'private_source_refused')
    _check(not any(p.linked(item) for item in (path, *path.parents)), 'linked_source_refused')
    return path


def _identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _read_document(path):
    path = _safe_path(path); before = path.stat()
    _check(path.is_file() and before.st_size <= p.MAX_JSON, 'source_document_unavailable')
    with path.open('rb') as stream: raw = stream.read(p.MAX_JSON + 1)
    _check(_identity(before) == _identity(path.stat()), 'source_changed_during_read')
    return p.decode_json(raw), hashlib.sha256(raw).hexdigest()


def _observe_file(record, kind):
    _check(type(record) is dict and type(record.get('path')) is str and Path(record['path']).is_absolute(), 'preflight_file_invalid')
    _check(_sha(record.get('sha256')) and type(record.get('bytes')) is int and 0 < record['bytes'] <= 64 * 1024**3,
           'preflight_file_invalid')
    path = _safe_path(record['path']); before = path.stat()
    _check(path.is_file() and before.st_size == record['bytes'], 'preflight_file_changed')
    if kind == 'model':
        _check(type(record.get('mtime_ns')) is int and before.st_mtime_ns == record['mtime_ns'], 'preflight_file_changed')
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''): h.update(chunk)
    _check(_identity(before) == _identity(path.stat()), 'source_changed_during_read')
    _check(h.hexdigest() == record['sha256'], 'preflight_file_changed')
    return {'kind': kind, 'path': str(path), 'bytes': before.st_size,
            'mtime_ns': before.st_mtime_ns, 'sha256': h.hexdigest()}


def _read_project(experiments, project_id):
    path = p.contained_file(experiments / 'projects', 'projects.sqlite3')
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=2)
    try:
        db.row_factory = sqlite3.Row; db.execute('PRAGMA query_only=ON'); db.execute('BEGIN')
        row = db.execute('SELECT id,root_id,plan,state,created FROM projects WHERE id=?', (project_id,)).fetchone()
        _check(row is not None, 'production_project_missing')
        project = dict(row); project['plan'] = p.decode_json(project['plan']); project['state'] = p.decode_json(project['state'])
        budget = db.execute('SELECT id,allowance,reserved FROM budgets WHERE id=?', (project['root_id'],)).fetchone()
        _check(budget is not None, 'production_budget_missing')
        db.rollback()
    finally: db.close()
    return project, dict(budget)


def _workspace_id(experiments):
    path = p.contained_file(experiments / 'workspace', 'assets.sqlite3')
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=2)
    try:
        db.execute('PRAGMA query_only=ON')
        row = db.execute('SELECT id FROM workspace_identity WHERE singleton=1').fetchone()
    finally: db.close()
    _check(row is not None and type(row[0]) is str and PROJECT_ID.fullmatch(row[0]), 'workspace_identity_missing')
    return row[0]


def _prepared_stage(project, budget, stage_index, preset):
    _exact(project, {'id', 'root_id', 'plan', 'state', 'created'}, 'project_shape_invalid')
    _check(type(project['id']) is str and PROJECT_ID.fullmatch(project['id']), 'project_identity_invalid')
    _check(type(project['root_id']) is str and 0 < len(project['root_id']) <= 200, 'budget_identity_invalid')
    _exact(budget, {'id', 'allowance', 'reserved'}, 'budget_shape_invalid')
    _check(budget['id'] == project['root_id'] and type(budget['allowance']) is int
           and type(budget['reserved']) is int and 0 <= budget['reserved'] <= budget['allowance'] <= 100000, 'budget_invalid')
    plan = project['plan']; state = project['state']
    _check(type(plan) is dict and plan.get('version') == 1 and type(plan.get('version')) is int
           and plan.get('kind') == 'comparison' and type(state) is dict, 'unsupported_production_plan')
    _check(plan.get('sha256') == production_fingerprint({k: v for k, v in plan.items() if k != 'sha256'}), 'plan_digest_invalid')
    stages = plan.get('stages')
    _check(type(stages) is list and 1 <= len(stages) <= 16 and type(stage_index) is int
           and 0 <= stage_index < len(stages), 'production_stage_invalid')
    item = stages[stage_index]
    _check(type(item) is dict and item.get('operation') == 'comfy.generate.v1', 'unsupported_operation')
    request = item.get('request'); graph = item.get('graph')
    _check(type(request) is dict and request.get('privacy', 'regular') == 'regular'
           and (plan.get('recipe') is None or type(plan['recipe']) is dict and plan['recipe'].get('privacy', 'regular') == 'regular'),
           'private_or_invalid_request')
    _check(not any(key in request for key in ('workflow', 'tasks', 'command', 'script')), 'raw_operation_refused')
    _check(type(request.get('batch_count', 1)) is int and request.get('batch_count', 1) == 1, 'batch_unsupported')
    graph_check(graph)
    _check(item.get('graph_sha256') == production_fingerprint(graph), 'prepared_graph_changed')
    _check(type(preset) is dict and request.get('preset_id') == preset.get('id'), 'preset_mismatch')
    _check(type(request.get('controls', {})) is dict, 'request_controls_invalid')
    for node in graph.values():
        for field, value in node['inputs'].items():
            if field in ('text', 'prompt', 'positive', 'negative') and type(value) is str:
                _check(not prompting.has_wildcards(value), 'wildcards_unsupported')
    extras = preset.get('bindings_extra') or {}
    _check(type(extras) is dict and type(extras.get('seed', [])) is list, 'seed_binding_invalid')
    bindings = ([preset['seed']] if preset.get('seed') else []) + extras.get('seed', [])
    _check(type(bindings) is list and bindings, 'seed_binding_required')
    values = []
    for binding in bindings:
        _check(type(binding) is list and len(binding) == 2, 'seed_binding_invalid')
        value = graph[str(binding[0])]['inputs'][str(binding[1])]
        _check(type(value) is int and 0 <= value <= 2**63 - 1, 'seed_invalid'); values.append(value)
    _check(len(set(values)) == 1, 'seed_bindings_disagree')
    if 'seed' in request.get('controls', {}):
        raw = request['controls']['seed']
        _check(type(raw) in (int, float, str), 'seed_control_mismatch')
        try: numeric = Decimal(str(raw))
        except InvalidOperation: numeric = Decimal('NaN')
        _check(numeric.is_finite() and numeric == values[0], 'seed_control_mismatch')
    return item, values[0]


def _bundle_files(bundle, preset, graph, library):
    _check(type(bundle) is dict and type(bundle.get('comfy_root')) is str
           and Path(bundle['comfy_root']).is_absolute() and type(bundle.get('comfy_url')) is str, 'preflight_bundle_invalid')
    parsed = urlsplit(bundle['comfy_url'])
    _check(parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost', '::1')
           and parsed.port is not None and not parsed.username and not parsed.password and not parsed.query
           and not parsed.fragment and parsed.path in ('', '/'), 'backend_endpoint_invalid')
    _check(_sha(bundle.get('schema_sha256')) and type(bundle.get('node_classes')) is list
           and all(type(value) is str for value in bundle['node_classes'])
           and len(bundle['node_classes']) == len(set(bundle['node_classes']))
           and {node['class_type'] for node in graph.values()} <= set(bundle['node_classes']), 'preflight_schema_invalid')
    models, inputs = bundle.get('models'), bundle.get('inputs')
    _check(type(models) is list and 1 <= len(models) <= 128 and type(inputs) is list and len(inputs) <= 128, 'preflight_inventory_invalid')
    observed = [_observe_file(record, 'model') for record in models] + [_observe_file(record, 'input') for record in inputs]
    _check(len({row['path'] for row in observed}) == len(observed), 'preflight_inventory_duplicate')
    roots, model_names = set(), set()
    for record in models:
        name = record.get('file'); p.safe_relative(name)
        parts = Path(name).parts; path = Path(record['path'])
        _check(tuple(path.parts[-len(parts):]) == tuple(parts), 'model_path_mismatch')
        roots.add(path.parents[len(parts) - 1]); model_names.add(path_key(name))
    _check(len(roots) == 1 and len(model_names) == len(models), 'model_roots_or_names_ambiguous')
    model_root = _safe_path(next(iter(roots)))
    _check(type(library) is dict and type(library.get('assets')) is list
           and all(type(asset) is dict for asset in library['assets']), 'library_invalid')
    # A read-only projection object avoids ModelLibrary's constructor writes.
    projection = SimpleNamespace(models=model_root, install_block=lambda *_: 'Read-only projection; installation unavailable')
    rows = requirements(projection, preset, graph, model_root, assets=library['assets'])
    _check(rows and all(row.get('path') is not None and row.get('present') is True
                       and not row.get('pin_conflict') for row in rows), 'model_requirements_unresolved')
    _check({path_key(row['file']) for row in rows} <= model_names, 'preflight_dependency_missing')
    for record in models:
        pins = [asset for asset in library['assets'] if type(asset.get('file')) is str and path_key(asset['file']) == path_key(record['file'])]
        _check(len(pins) <= 1, 'library_pin_conflict')
        if pins:
            pin = pins[0]
            _check(_sha(pin.get('sha256')) and type(pin.get('bytes')) is int
                   and pin['sha256'] == record['sha256'] and pin['bytes'] == record['bytes'], 'library_pin_mismatch')
    input_paths = {str(_safe_path(record['path'])) for record in inputs}
    for node in graph.values():
        if node['class_type'] == 'LoadImage':
            name = node['inputs'].get('image'); p.safe_relative(name)
            path = _safe_path(Path(bundle['comfy_root']) / 'input' / name)
            _check(str(path) in input_paths, 'preflight_reference_missing')
    return sorted(observed, key=lambda row: (row['kind'], row['path']))


def _validate_intent(intent):
    """Strict shape/self-consistency validation; no I/O or authority inference.

    Returns the canonical SHA-256 or raises PipelineError/ValueError. Always call
    revalidate_intent with independently trusted roots before claiming work.
    """
    p.canonical_bytes(intent); _exact(intent, KEYS, 'intent_shape_invalid')
    _check(intent['schema'] == SCHEMA and intent['operation'] == 'comfy.generate.v1', 'intent_operation_invalid')
    _check(type(intent['family_id']) is str and p.ENTITY.fullmatch(intent['family_id'])
           and type(intent['stage']) is str and intent['stage'] in p.STAGES, 'intent_scope_invalid')
    _check(type(intent['project_id']) is str and PROJECT_ID.fullmatch(intent['project_id'])
           and type(intent['stage_index']) is int and 0 <= intent['stage_index'] < 16, 'intent_project_invalid')
    _check(intent['job_id'] == project_storage.stage_job_id(intent['project_id'], intent['stage_index']), 'intent_job_invalid')
    _check(type(intent['batch_count']) is int and intent['batch_count'] == 1, 'batch_unsupported')
    _check(type(intent['seed']) is int and 0 <= intent['seed'] <= 2**63 - 1, 'seed_invalid')
    _check(type(intent['preset_id']) is str and p.ENTITY.fullmatch(intent['preset_id'])
           and type(intent['backend_id']) is str and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', intent['backend_id']), 'intent_route_invalid')
    source = intent['source_snapshot']; _exact(source, SNAPSHOT_KEYS, 'source_snapshot_invalid')
    _check(source['preparation_only'] is True and type(source['workspace_id']) is str
           and PROJECT_ID.fullmatch(source['workspace_id']), 'source_scope_invalid')
    for key in ('studio_root', 'experiments_root'):
        _check(type(source[key]) is str and Path(source[key]).is_absolute(), 'source_root_invalid')
    for key in ('plan_file_sha256', 'catalog_sha256', 'preset_sha256', 'template_sha256', 'library_sha256', 'bundle_sha256'):
        _check(_sha(source[key]), 'source_digest_invalid')
    item, seed = _prepared_stage(source['project_record'], source['budget_record'], intent['stage_index'], source['preset_record'])
    _check(source['project_record']['id'] == intent['project_id'] and p.canonical_bytes(item['graph']) == p.canonical_bytes(intent['graph'])
           and seed == intent['seed'] and item['request']['preset_id'] == intent['preset_id'], 'intent_preparation_mismatch')
    _check(source['preset_record'].get('backend_id', 'primary') == intent['backend_id']
           and p.digest(source['preset_record']) == source['preset_sha256']
           and item['request'].get('expected_template_sha256') == source['template_sha256']
           and p.digest(source['project_record']['plan'].get('bundle')) == source['bundle_sha256'], 'intent_source_mismatch')
    _check(type(source['observed_files']) is list and 1 <= len(source['observed_files']) <= 256, 'source_files_invalid')
    for row in source['observed_files']:
        _exact(row, {'kind', 'path', 'bytes', 'mtime_ns', 'sha256'}, 'source_file_invalid')
        _check(row['kind'] in ('model', 'input') and type(row['path']) is str and Path(row['path']).is_absolute()
               and type(row['bytes']) is int and row['bytes'] > 0 and type(row['mtime_ns']) is int
               and row['mtime_ns'] >= 0 and _sha(row['sha256']), 'source_file_invalid')
    return p.digest(intent)


def validate_intent(intent):
    """Return a strict canonical digest; malformed structures raise ValueError."""
    try: return _validate_intent(intent)
    except (KeyError, TypeError, AttributeError, OverflowError, RecursionError) as error:
        raise p.PipelineError('Malformed intent structure', 'intent_invalid') from error


def _report():
    return {'schema': 'las.p36-production-intent-capture/1', 'passed': False, 'blockers': [], 'intent': None,
            'preparation_only': True, 'generation_submitted': False, 'submission_authority': False,
            'budget_authority': False, 'runtime_ready': False,
            'limitations': ['Retained preparation and file agreement at serial reads only; no live queue, lease or backend observation.',
                            'Serial reads do not freeze engine-open bytes or create a cross-system transaction.',
                            'Source snapshots are not authenticated owner acceptance or permission to dispatch.',
                            'Hook precedes create_job; an existing future job must be observed through the existing protocol.']}


def capture_production_intent(experiments, project_id, stage_index, *, family_id, stage, studio_root=None):
    """Read current prepared sources without constructing or mutating Production."""
    report = _report()
    try:
        p.canonical_bytes({'project_id': project_id, 'stage_index': stage_index, 'family_id': family_id, 'stage': stage})
        _check(type(project_id) is str and PROJECT_ID.fullmatch(project_id), 'production_project_invalid')
        _check(type(stage_index) is int and 0 <= stage_index < 16, 'production_stage_invalid')
        experiments = _safe_path(experiments); root = _safe_path(studio_root if studio_root is not None else p.REPO_ROOT)
        project, budget = _read_project(experiments, project_id)
        _check(type(project['plan']) is dict, 'unsupported_production_plan')
        project_storage.require(experiments / 'projects', project_id, project['plan'])
        plan_file = experiments / 'projects' / project_id / 'plan.json'
        saved_plan, plan_hash = _read_document(plan_file)
        _check(p.canonical_bytes(saved_plan) == p.canonical_bytes(project['plan']), 'materialized_plan_changed')
        stages = project['plan'].get('stages')
        _check(type(stages) is list and stage_index < len(stages), 'production_stage_invalid')
        _check(type(stages[stage_index]) is dict, 'production_stage_invalid')
        request = stages[stage_index].get('request'); _check(type(request) is dict, 'request_invalid')
        catalog_path = root / 'presets/catalog.json'; catalog, catalog_hash = _read_document(catalog_path)
        _check(type(catalog) is dict and type(catalog.get('presets')) is list, 'catalog_invalid')
        matches = [value for value in catalog['presets'] if type(value) is dict and value.get('id') == request.get('preset_id')]
        _check(len(matches) == 1, 'catalog_preset_ambiguous'); preset = matches[0]
        item, seed = _prepared_stage(project, budget, stage_index, preset)
        template_path = p.contained_file(root, preset.get('graph')); _, template_hash = _read_document(template_path)
        _check(request.get('expected_template_sha256') == template_hash, 'template_changed')
        library_path = root / 'models/library.json'; library, library_hash = _read_document(library_path)
        observed = _bundle_files(project['plan'].get('bundle'), preset, item['graph'], library)
        job_id = project_storage.stage_job_id(project_id, stage_index)
        job_path = _safe_path(experiments / 'runs' / job_id)
        _check(not job_path.exists(), 'future_job_already_exists')
        workspace_id = _workspace_id(experiments)
        source = {'studio_root': str(root), 'experiments_root': str(experiments), 'workspace_id': workspace_id,
                  'project_record': project, 'budget_record': budget, 'plan_file_sha256': plan_hash,
                  'catalog_sha256': catalog_hash, 'preset_record': preset, 'preset_sha256': p.digest(preset),
                  'template_sha256': template_hash, 'library_sha256': library_hash,
                  'bundle_sha256': p.digest(project['plan']['bundle']), 'observed_files': observed, 'preparation_only': True}
        intent = {'schema': SCHEMA, 'operation': 'comfy.generate.v1', 'family_id': family_id, 'stage': stage,
                  'project_id': project_id, 'stage_index': stage_index, 'job_id': job_id,
                  'preset_id': preset['id'], 'backend_id': preset.get('backend_id', 'primary'),
                  'graph': item['graph'], 'seed': seed, 'batch_count': 1, 'source_snapshot': source}
        validate_intent(intent)
        for path, expected in ((plan_file, plan_hash), (catalog_path, catalog_hash),
                               (template_path, template_hash), (library_path, library_hash)):
            _check(_read_document(path)[1] == expected, 'source_changed_during_capture')
        _check(p.canonical_bytes(list(_read_project(experiments, project_id))) == p.canonical_bytes([project, budget])
               and _workspace_id(experiments) == workspace_id and not job_path.exists(), 'source_changed_during_capture')
        report.update(passed=True, intent=intent)
    except (ValueError, OSError, KeyError, TypeError, AttributeError, OverflowError, RecursionError, sqlite3.Error) as error:
        report['blockers'].append({'code': getattr(error, 'code', 'production_source_unavailable'),
                                   'detail': str(error)[:300].encode('utf-8', errors='backslashreplace').decode('utf-8')})
    return report


def revalidate_intent(experiments, intent, *, studio_root=None):
    """Reopen all trusted sources and compare the entire immutable intent."""
    report = _report()
    try:
        validate_intent(intent)
        root = _safe_path(studio_root if studio_root is not None else p.REPO_ROOT)
        experiments = _safe_path(experiments)
        _check(str(root) == intent['source_snapshot']['studio_root']
               and str(experiments) == intent['source_snapshot']['experiments_root'], 'trusted_source_root_mismatch')
        report = capture_production_intent(experiments, intent['project_id'], intent['stage_index'],
            family_id=intent['family_id'], stage=intent['stage'], studio_root=root)
        if report['passed']:
            _check(p.canonical_bytes(report['intent']) == p.canonical_bytes(intent), 'prepared_intent_changed')
    except (ValueError, OSError, KeyError, TypeError, OverflowError, RecursionError) as error:
        report.update(passed=False, intent=None)
        report['blockers'].append({'code': getattr(error, 'code', 'intent_invalid'), 'detail': str(error)[:300]})
    return report
