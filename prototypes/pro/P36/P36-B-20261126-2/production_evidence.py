"""Deterministic proof of prepared Production reads; all fixtures are synthetic.

Uses the actual Production.create / Studio.prepare / production_preflight path
through make_production_case. Host observations are simulated; no server,
generation, native application, dispatch authority or budget permission is used.
Only disposable sources beneath the caller's fresh .runtime output are mutated.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3

import pipeline as p
import production_intent as prepared
from production_intent_fixtures import make_production_case

FLAGS = ('generation_submitted', 'submission_authority', 'budget_authority', 'runtime_ready')


def _check(condition, message):
    p.require(condition, message, 'preparation_proof_failed')


def _capture(case):
    return prepared.capture_production_intent(**{key: case[key] for key in (
        'experiments', 'project_id', 'stage_index', 'family_id', 'stage', 'studio_root')})


def _only_preparation(report):
    _check(report['preparation_only'] is True and all(report[key] is False for key in FLAGS),
           'A preparation report claimed execution or authority')


def _filesystem(case):
    # Compare bytes, paths and write metadata. Reading may change atime; SQLite
    # read-only connections can also touch their SHM mtime without changing bytes.
    # That specific bookkeeping timestamp is excluded, not the sidecar contents.
    root = case['studio_root']; result = {}
    shm = {Path(str(case['experiments'] / relative) + '-shm') for relative in
           ('projects/projects.sqlite3', 'workspace/assets.sqlite3')}
    for path in sorted(root.rglob('*')):
        _check(not p.linked(path), 'Unexpected link in synthetic evidence source')
        info = path.stat(); name = path.relative_to(root).as_posix()
        if path.is_dir(): result[name] = ('directory', info.st_mode, info.st_mtime_ns)
        elif path.is_file():
            result[name] = ('file', info.st_mode, info.st_size, None if path in shm else info.st_mtime_ns,
                            hashlib.sha256(path.read_bytes()).hexdigest())
        else: _check(False, 'Unexpected special file in synthetic evidence source')
    return result


def _databases(case):
    result = {}
    for relative in ('projects/projects.sqlite3', 'workspace/assets.sqlite3'):
        path = case['experiments'] / relative
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
            db.execute('PRAGMA query_only=ON')
            result[relative] = tuple(db.iterdump())
    return result


def _sql(case, relative, statement, parameters=()):
    # Authored corruption is restricted to disposable fixture databases. The
    # missing-budget case deliberately omits FK enforcement to model a bad source.
    with closing(sqlite3.connect(case['experiments'] / relative)) as db:
        with db: db.execute(statement, parameters)


def _change_json(path, mutate):
    data = p.decode_json(path.read_bytes()); mutate(data)
    path.write_bytes(p.canonical_bytes(data))


def _mutate(name, case, intent):
    root = case['studio_root']; project = intent['source_snapshot']['project_record']
    trusted_root = root
    if name in ('model-same-size-and-mtime', 'input-same-size-and-mtime'):
        path = case['model_path' if name.startswith('model-') else 'input_path']; info = path.stat()
        path.write_bytes(b'X' * info.st_size)
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
    elif name == 'plan-bytes-rewritten':
        path = case['experiments'] / 'projects' / case['project_id'] / 'plan.json'
        path.write_bytes(path.read_bytes() + b' ')
    elif name == 'plan-db-materialization-drift':
        plan = p.decode_json(p.canonical_bytes(project['plan'])); plan['name'] = 'Authored DB-only drift'
        plan['sha256'] = prepared.production_fingerprint({k: v for k, v in plan.items() if k != 'sha256'})
        _sql(case, 'projects/projects.sqlite3', 'UPDATE projects SET plan=? WHERE id=?',
             (json.dumps(plan), case['project_id']))
    elif name == 'catalog-changed':
        _change_json(root / 'presets/catalog.json', lambda data: data['presets'][0].update(name='Authored catalog drift'))
    elif name == 'template-bytes-changed':
        path = root / 'workflows/api/p36-fixture.json'; path.write_bytes(path.read_bytes() + b' ')
    elif name == 'budget-row-missing':
        _sql(case, 'projects/projects.sqlite3', 'DELETE FROM budgets WHERE id=?', (project['root_id'],))
    elif name == 'workspace-identity-missing':
        _sql(case, 'workspace/assets.sqlite3', 'DELETE FROM workspace_identity')
    elif name == 'serialized-numeric-graph-alias':
        # intent came through JSON, so this changes only the dispatched graph.
        intent['graph']['2']['inputs']['seed'] = 7.0
        _check(p.canonical_bytes(intent['graph']) != p.canonical_bytes(project['plan']['stages'][0]['graph']),
               'Numeric alias challenge did not change the exact graph bytes')
    elif name == 'alternate-trusted-root':
        trusted_root = root / 'alternate-studio'; trusted_root.mkdir()
    elif name == 'future-job-already-exists':
        (case['experiments'] / 'runs' / intent['job_id']).mkdir(parents=True)
    elif name == 'library-pin-changed':
        _change_json(root / 'models/library.json', lambda data: data['assets'][0].update(sha256='f' * 64))
    else: _check(False, 'Unknown preparation challenge')
    return trusted_root


def _observe(case, intent, trusted_root):
    # Initialize this observer's readonly SQLite readers first: a writer closing
    # after an authored mutation may have removed WAL/SHM bookkeeping sidecars.
    # The observer can recreate those even though retained database rows are unchanged.
    db_before = _databases(case); files_before = _filesystem(case)
    try: prepared.validate_intent(intent); structural = True
    except ValueError: structural = False
    report = prepared.revalidate_intent(case['experiments'], intent, studio_root=trusted_root)
    _only_preparation(report)
    db_after = _databases(case); files_after = _filesystem(case)
    _check(files_before == files_after and db_before == db_after, 'Read-only capture changed its retained source')
    _check(case['studio'].requests == [] and case['studio'].queue.empty(), 'Fixture submitted or queued work')
    return {'intent_validation_pass': structural, 'current_preparation_pass': report['passed'],
            'blocker_codes': sorted({item['code'] for item in report['blockers']}),
            'filesystem_unchanged': files_before == files_after, 'database_unchanged': db_before == db_after}


def prove_preparation(out: Path) -> dict:
    """Create 12 independent refusals and a valid control beneath fresh runtime out.

    The returned projection contains no paths, times, project/workspace/job IDs,
    model hashes or other per-run values. A disagreement raises PipelineError;
    failed evidence is never silently published as a successful proof.
    """
    out = Path(out).absolute(); base = out / 'production-preparation'
    _check(out.resolve().is_relative_to((p.REPO_ROOT / '.runtime').resolve()), 'Evidence must remain under .runtime')
    _check(not any(p.linked(path) for path in (base, *base.parents)), 'Linked evidence output refused')
    _check(not base.exists(), 'Preparation evidence output must be fresh')
    base.mkdir(parents=True)
    control = make_production_case(base / 'valid-control')
    current = _capture(control); _only_preparation(current)
    _check(current['passed'], 'Valid preparation control refused')
    valid = _observe(control, current['intent'], control['studio_root'])
    _check(valid['intent_validation_pass'] and valid['current_preparation_pass'] and not valid['blocker_codes'],
           'Valid preparation revalidation refused')
    cases = [
        ('model-same-size-and-mtime', 'preflight_file_changed'),
        ('input-same-size-and-mtime', 'preflight_file_changed'),
        ('plan-bytes-rewritten', 'prepared_intent_changed'),
        ('plan-db-materialization-drift', 'production_source_unavailable'),
        ('catalog-changed', 'prepared_intent_changed'),
        ('template-bytes-changed', 'template_changed'),
        ('budget-row-missing', 'production_budget_missing'),
        ('workspace-identity-missing', 'workspace_identity_missing'),
        ('serialized-numeric-graph-alias', 'intent_preparation_mismatch'),
        ('alternate-trusted-root', 'trusted_source_root_mismatch'),
        ('future-job-already-exists', 'future_job_already_exists'),
        ('library-pin-changed', 'library_pin_mismatch'),
    ]
    rows = []
    for name, expected in cases:
        case = make_production_case(base / name)
        initial = _capture(case); _only_preparation(initial)
        _check(initial['passed'], 'Initial preparation control refused: ' + name)
        _check(initial['intent']['source_snapshot']['budget_record']['reserved'] == 0,
               'Fixture preparation reserved a generation budget')
        intent = p.decode_json(p.canonical_bytes(initial['intent']))
        trusted_root = _mutate(name, case, intent)
        row = {'name': name, 'initial_control_pass': initial['passed'], **_observe(case, intent, trusted_root)}
        _check(not row['current_preparation_pass'] and row['blocker_codes'] == [expected],
               'Preparation challenge did not refuse as expected: ' + name)
        _check(row['intent_validation_pass'] == (name != 'serialized-numeric-graph-alias'),
               'Structural validation challenge disagreed: ' + name)
        rows.append(row)
    return {'kind': 'actual-Studio-Production-API-with-synthetic-runtime-observations',
            'passed': True, 'preparation_only': True, 'valid_control': valid, 'cases': rows,
            'readonly_scope': 'after-reader-init-file-bytes-paths-permissions-and-rows-shm-mtime-excluded',
            'invalid_cases': len(rows), 'valid_controls_admitted': 1 + sum(row['initial_control_pass'] for row in rows),
            'current_preparation_refusals': sum(not row['current_preparation_pass'] for row in rows),
            'current_preparation_false_accepts': sum(row['current_preparation_pass'] for row in rows),
            'read_only_cases': len(rows) + 1,
            'filesystem_unchanged': valid['filesystem_unchanged'] and all(row['filesystem_unchanged'] for row in rows),
            'database_unchanged': valid['database_unchanged'] and all(row['database_unchanged'] for row in rows),
            'generation_submitted': False, 'submission_authority': False, 'budget_authority': False,
            'runtime_ready': False, 'native_execution': False, 'owner_authority': False}
