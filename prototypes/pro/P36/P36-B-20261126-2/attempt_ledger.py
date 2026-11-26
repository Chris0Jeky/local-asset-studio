"""Durable attempt reservations. No submission, observation RPC or automatic retry.

Record a reservation before a future worker could send a request. Even a crash
with no prompt ID or artifact leaves it unresolved. Repeated request IDs return
the retained identity, not another permission to submit. SQLite serializes
competing writers. A future worker must use this ledger for *every* P36 attempt;
it cannot reconstruct omitted historical attempts from missing artifacts.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import secrets
import sqlite3

import pipeline as p
from studio_authority import job_is_settled, read_record


def _path(path, *, exists=False):
    path = Path(path).absolute()
    p.require(path.resolve().is_relative_to((p.REPO_ROOT / '.runtime').resolve()),
              'Attempt ledger must be under repository .runtime/')
    p.require(not any(p.linked(x) for x in (path, *path.parents)), 'Linked ledger path refused')
    if exists: p.require(path.is_file(), 'Attempt ledger is missing; no authority can be inferred')
    return path


@contextmanager
def _connection(path, *, writable=False):
    path = _path(path, exists=True)
    db = sqlite3.connect(path.as_uri() + ('?mode=rw' if writable else '?mode=ro'), uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        if writable: db.execute('PRAGMA synchronous=FULL'); db.execute('BEGIN IMMEDIATE')
        else: db.execute('PRAGMA query_only=ON'); db.execute('BEGIN')
        p.require(db.execute('PRAGMA user_version').fetchone()[0] == 1, 'Unknown attempt-ledger schema')
        yield db
        if writable: db.commit()
        else: db.rollback()
    except sqlite3.Error as exc:
        db.rollback(); raise p.PipelineError('Attempt ledger is unavailable or conflicts: ' + type(exc).__name__) from exc
    finally: db.close()


def initialize(path):
    """Explicitly initialize an empty ledger; never replace an existing file."""
    path = _path(path)
    if path.exists():
        with _connection(path): pass
        return {'initialized': False, 'generation_submitted': False}
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive file claim prevents two initializers from replacing each other.
    try:
        with path.open('xb'): pass
    except FileExistsError as exc:
        raise p.PipelineError('Ledger initialization already in progress; inspect the retained file') from exc
    db = sqlite3.connect(path, timeout=5)
    try:
        db.execute('PRAGMA synchronous=FULL')
        db.executescript('''BEGIN IMMEDIATE;
            CREATE TABLE attempts (
                attempt_id TEXT PRIMARY KEY, family_id TEXT NOT NULL, stage TEXT NOT NULL,
                request_id TEXT NOT NULL, job_id TEXT NOT NULL UNIQUE, intent_sha256 TEXT NOT NULL,
                workspace_id TEXT NOT NULL, source_root_sha256 TEXT NOT NULL, nonce TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('unresolved','completed','failed')),
                observation_sha256 TEXT, revision INTEGER NOT NULL DEFAULT 0,
                UNIQUE(family_id,request_id));
            CREATE UNIQUE INDEX one_unresolved_attempt ON attempts(family_id,stage) WHERE state='unresolved';
            PRAGMA user_version=1;
            COMMIT;''')
    finally: db.close()
    return {'initialized': True, 'generation_submitted': False}


def _scope(family_id, stage):
    p.require(type(family_id) is str and p.ENTITY.fullmatch(family_id), 'Invalid attempt family')
    p.require(stage in p.STAGES, 'Invalid attempt stage')


IDENTITY_FIELDS = ('family_id', 'stage', 'request_id', 'job_id', 'intent_sha256',
                   'workspace_id', 'source_root_sha256', 'nonce')


def _source_scope(experiments):
    root = Path(experiments).absolute()
    p.require(not any(p.linked(x) for x in (root, *root.parents)), 'Linked source root refused')
    database = p.contained_file(root / 'workspace', 'assets.sqlite3')
    db = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=2)
    try:
        row = db.execute('SELECT id FROM workspace_identity WHERE singleton=1').fetchone()
    finally: db.close()
    p.require(row is not None and type(row[0]) is str and len(row[0]) == 32
              and all(c in '0123456789abcdef' for c in row[0]), 'Source Workspace identity unavailable')
    return {'workspace_id': row[0], 'source_root_sha256': p.digest({'experiments_root': root.resolve().as_posix()})}


def _validate_row(row):
    row = dict(row); p.canonical_bytes(row)
    _scope(row['family_id'], row['stage'])
    for key in ('request_id', 'job_id'):
        p.require(type(row[key]) is str and p.ENTITY.fullmatch(row[key]), 'Malformed attempt identifier')
        p.safe_relative(row[key])
    for key in ('intent_sha256', 'source_root_sha256'):
        p.require(type(row[key]) is str and p.HEX64.fullmatch(row[key]), 'Malformed attempt digest')
    for key in ('workspace_id', 'nonce'):
        p.require(type(row[key]) is str and len(row[key]) == 32
                  and all(c in '0123456789abcdef' for c in row[key]), 'Malformed attempt scope or nonce')
    p.require(p.digest({k: row[k] for k in IDENTITY_FIELDS}) == row['attempt_id'], 'Attempt identity changed')
    p.require(row['state'] in ('unresolved', 'completed', 'failed'), 'Unknown attempt state')
    p.require(type(row['revision']) is int and row['revision'] == (0 if row['state'] == 'unresolved' else 1),
              'Invalid attempt revision')
    if row['state'] == 'unresolved': p.require(row['observation_sha256'] is None, 'Unresolved attempt has an observation')
    else: p.require(type(row['observation_sha256']) is str and p.HEX64.fullmatch(row['observation_sha256']),
                    'Resolved attempt lacks exact observation')
    return row


def _job_binding(row):
    return {'schema': 'las.p36-attempt-binding/1', 'attempt_id': row['attempt_id'],
            **{k: row[k] for k in IDENTITY_FIELDS}}


def _view(row, *, created=False):
    row = _validate_row(row)
    return {**dict(row), 'created': created, 'action': 'recorded-before-dispatch' if created else 'observe-existing',
            'job_binding': _job_binding(row),
            'generation_submitted': False, 'submission_authority': False}


def reserve(path, *, family_id, stage, request_id, job_id, intent_sha256, experiments, workspace_id):
    _scope(family_id, stage)
    for value in (request_id, job_id):
        p.require(type(value) is str and p.ENTITY.fullmatch(value), 'Safe request and job IDs required')
        p.safe_relative(value)
    p.require(type(intent_sha256) is str and p.HEX64.fullmatch(intent_sha256), 'Exact admission intent digest required')
    source = _source_scope(experiments)
    p.require(workspace_id == source['workspace_id'], 'Reservation names a different Workspace')
    payload = {'family_id': family_id, 'stage': stage, 'request_id': request_id,
               'job_id': job_id, 'intent_sha256': intent_sha256, **source}
    with _connection(path, writable=True) as db:
        # Validate before any filtering so a changed stage cannot hide a retained attempt.
        for row in db.execute('SELECT * FROM attempts WHERE family_id=?', (family_id,)): _validate_row(row)
        existing = db.execute('SELECT * FROM attempts WHERE family_id=? AND request_id=?', (family_id, request_id)).fetchone()
        if existing is not None:
            p.require(all(existing[k] == v for k, v in payload.items()), 'Request ID already binds a different intent')
            return _view(existing)
        pending = db.execute("SELECT 1 FROM attempts WHERE family_id=? AND stage=? AND state='unresolved'",
                             (family_id, stage)).fetchone()
        p.require(pending is None, 'An unresolved attempt blocks this stage; observe it, never repeat it', 'uncertain_submission')
        # A terminal row is only as current as its retained observation. Refuse
        # another request if those bytes disappeared, changed, or became uncertain.
        # Replaying an existing request above remains observation-only.
        for retained in db.execute('SELECT * FROM attempts WHERE family_id=? AND stage=?', (family_id, stage)):
            try:
                observed_state, observed_hash = _observation(experiments, retained)
                p.require(observed_state == retained['state'] and observed_hash == retained['observation_sha256'],
                          'Retained terminal observation changed')
            except (ValueError, OSError, KeyError, TypeError) as error:
                raise p.PipelineError('Changed terminal evidence blocks a fresh attempt; inspect the retained job',
                                      'resolved_attempt_evidence_changed') from error
        p.require(db.execute('SELECT 1 FROM attempts WHERE job_id=?', (job_id,)).fetchone() is None,
                  'A retained job ID cannot be reused by another attempt')
        directory = Path(experiments).absolute() / 'runs' / job_id
        p.require(not any(p.linked(x) for x in (directory, directory.parent)), 'Linked job directory refused')
        p.require(not directory.exists(), 'A preexisting job cannot be attached to a new attempt')
        payload['nonce'] = secrets.token_hex(16); attempt_id = p.digest(payload)
        db.execute("INSERT INTO attempts(attempt_id,family_id,stage,request_id,job_id,intent_sha256,workspace_id,source_root_sha256,nonce,state) VALUES (?,?,?,?,?,?,?,?,?,'unresolved')",
                   (attempt_id, *(payload[k] for k in IDENTITY_FIELDS)))
        row = db.execute('SELECT * FROM attempts WHERE attempt_id=?', (attempt_id,)).fetchone()
    return _view(row, created=True)


def _observation(experiments, row):
    row = _validate_row(row); job_id = row['job_id']
    source = _source_scope(experiments)
    p.require(all(row[k] == v for k, v in source.items()), 'Observation source Workspace or root differs')
    job, state_hash = read_record(experiments, 'runs/' + job_id + '/state.json')
    workflow, workflow_hash = read_record(experiments, 'runs/' + job_id + '/workflow.json')
    p.require(type(job) is dict and job.get('id') == job_id and type(workflow) is dict,
              'Observation does not name the retained job')
    p.require(job.get('privacy', 'regular') == 'regular', 'Private attempt is outside this adapter')
    p.require(job.get('p36_attempt') == _job_binding(row),
              'Observed job lacks the exact reserved attempt/intent/nonce binding')
    state = 'completed' if job_is_settled(job) else None
    if (state is None and job.get('status') == 'failed'
            and not any(k in job for k in ('pending_submission', 'record_error', 'abandonment'))
            and not job.get('tracking_disposition') and not job.get('operation')):
        ids = job.get('prompt_ids'); submissions = job.get('submissions'); outputs = job.get('outputs')
        if (type(ids) is list and ids and all(type(x) is str and x.strip() for x in ids)
                and len(set(ids)) == len(ids) and type(submissions) is list and len(submissions) == len(ids)
                and type(job.get('batch_count')) is int and job['batch_count'] == len(ids)
                and type(outputs) is list and all(type(o) is dict and o.get('prompt_id') in ids for o in outputs)
                and all(type(s) is dict and s.get('prompt_id') == i and s.get('status') in ('completed', 'failed')
                        for s, i in zip(submissions, ids)) and any(s['status'] == 'failed' for s in submissions)):
            state = 'failed'
    p.require(state in ('completed', 'failed'), 'Unresolved submission cannot be cleared by a queue label', 'uncertain_submission')
    observation = {'job_id': job_id, 'state': state, 'state_sha256': state_hash, 'workflow_sha256': workflow_hash}
    return state, p.digest(observation)


def resolve(path, attempt_id, *, experiments):
    p.require(type(attempt_id) is str and p.HEX64.fullmatch(attempt_id), 'Exact retained attempt ID required')
    with _connection(path, writable=True) as db:
        row = db.execute('SELECT * FROM attempts WHERE attempt_id=?', (attempt_id,)).fetchone()
        p.require(row is not None, 'Attempt is not retained')
        row = _validate_row(row)
        state, observation = _observation(experiments, row)
        if row['state'] != 'unresolved':
            p.require(row['state'] == state and row['observation_sha256'] == observation,
                      'Resolved evidence changed; inspect it before further work')
            return _view(row)
        db.execute('UPDATE attempts SET state=?,observation_sha256=?,revision=revision+1 WHERE attempt_id=?',
                   (state, observation, attempt_id))
        row = db.execute('SELECT * FROM attempts WHERE attempt_id=?', (attempt_id,)).fetchone()
    return _view(row)


def inspect(path, *, family_id, stages, experiments):
    selected = set(stages)
    p.require(selected and selected <= set(p.STAGES), 'Invalid attempt stage selection')
    for stage in selected: _scope(family_id, stage)
    with _connection(path) as db:
        all_rows = [dict(r) for r in db.execute('SELECT * FROM attempts WHERE family_id=? ORDER BY stage,request_id', (family_id,))]
    blockers = []
    source = _source_scope(experiments); rows = []
    for row in all_rows:
        try:
            _validate_row(row)
            p.require(all(row[k] == v for k, v in source.items()), 'Attempt source differs')
        except (ValueError, KeyError, TypeError):
            blockers.append({'code': 'attempt_identity_changed', 'stage': str(row.get('stage', '')), 'attempt_id': str(row.get('attempt_id', ''))})
            continue
        if row['stage'] not in selected: continue
        rows.append(row)
        if row['state'] == 'unresolved':
            blockers.append({'code': 'uncertain_submission', 'stage': row['stage'], 'attempt_id': row['attempt_id']})
        else:
            try:
                state, observation = _observation(experiments, row)
                p.require(state == row['state'] and observation == row['observation_sha256'], 'Observation changed')
            except (ValueError, OSError, TypeError):
                blockers.append({'code': 'resolved_attempt_evidence_changed', 'stage': row['stage'], 'attempt_id': row['attempt_id']})
    result = {'schema': 'las.p36-attempt-capture/1', 'passed': not blockers, 'blockers': blockers,
              'family_id': family_id, 'stages': sorted(selected), 'attempts': rows,
              'generation_submitted': False, 'submission_authority': False,
              'scope': 'Only attempts reserved in this ledger; worker integration must reserve every attempt'}
    result['snapshot_sha256'] = p.digest(result)
    return result
