"""Durable at-most-once dispatch protocol, restricted to a synthetic local port.

This lab writes only beneath .runtime. A prepared ticket is not a generation
capability. A durable claim precedes the callback and is never rearmed, even if
the process stops before the callback. Existing Studio budget/lease/worker wiring
is not installed by this module. All network/native/generation claims stay false.
"""
from __future__ import annotations

import copy
from pathlib import Path
import secrets
import sqlite3

import admission
import attempt_ledger as ledger
import pipeline as p
import studio_authority
import observation_state
import production_intent


STATES = {'prepared': 0, 'claimed': 1, 'acknowledged': 2, 'uncertain': 2, 'settled': 3}
TICKET_KEYS = {'schema', 'attempt_id', 'attempt_binding', 'intent_sha256', 'input_fingerprints',
               'authority_sha256', 'studio_root_sha256'}


def _diag(value):
    return str(value)[:350].encode('utf-8', errors='backslashreplace').decode('utf-8')[:350]


def _result(*, passed=False, action='refused', state=None, attempt_id=None, created=False,
            callback_invoked=False, blockers=None, **extra):
    result = {'schema': 'las.p36-dispatch-result/1', 'evidence_state': 'implemented',
              'mode': 'simulation-only', 'passed': passed, 'action': action, 'state': state,
              'attempt_id': attempt_id, 'created': created, 'callback_invoked': callback_invoked,
              'generation_submitted': False, 'submission_authority': False,
              'native_import_performed': False, 'blockers': blockers or [],
              'physical_power_loss_guarantee': False, **extra}
    result['report_sha256'] = p.digest(result)
    return result


def _error(error, *, state=None, attempt_id=None, callback_invoked=False):
    return _result(state=state, attempt_id=attempt_id, callback_invoked=callback_invoked,
                   blockers=[{'code': getattr(error, 'code', 'dispatch_refused'), 'detail': _diag(error)}])


def _runtime(path):
    root = Path(path).absolute()
    p.require(root.resolve().is_relative_to((p.REPO_ROOT / '.runtime').resolve())
              and not any(p.linked(x) for x in (root, *root.parents)),
              'Dispatch simulation writes only to unlinked .runtime paths', 'simulation_scope_required')
    return root


def _schema(db):
    rows = list(db.execute('SELECT version FROM p36_dispatch_meta'))
    p.require(len(rows) == 1 and rows[0][0] == 1, 'Unknown dispatch journal schema')


def initialize(path):
    """Explicit additive lab journal initialization; no Workspace migration."""
    ledger.initialize(path)
    with ledger._connection(path, writable=True) as db:
        db.execute('CREATE TABLE IF NOT EXISTS p36_dispatch_meta(version INTEGER NOT NULL)')
        if not db.execute('SELECT 1 FROM p36_dispatch_meta').fetchone():
            db.execute('INSERT INTO p36_dispatch_meta VALUES (1)')
        _schema(db)
        db.execute('''CREATE TABLE IF NOT EXISTS p36_dispatch_tickets (
            attempt_id TEXT PRIMARY KEY, ticket_json TEXT NOT NULL, ticket_sha256 TEXT NOT NULL,
            state TEXT NOT NULL, revision INTEGER NOT NULL, claim_id TEXT, outcome_json TEXT,
            FOREIGN KEY(attempt_id) REFERENCES attempts(attempt_id))''')
    return {'initialized': True, 'generation_submitted': False}


def _read_ticket(db, attempt_id):
    _schema(db)
    row = db.execute('SELECT * FROM p36_dispatch_tickets WHERE attempt_id=?', (attempt_id,)).fetchone()
    p.require(row is not None, 'Dispatch ticket is absent; never adopt an orphan reservation', 'ticket_missing')
    row = dict(row); ticket = p.decode_json(row['ticket_json'])
    p.require(type(ticket) is dict and set(ticket) == TICKET_KEYS
              and ticket['schema'] == 'las.p36-dispatch-ticket/1'
              and ticket['attempt_id'] == attempt_id and p.digest(ticket) == row['ticket_sha256'],
              'Dispatch ticket identity changed', 'ticket_changed')
    fingerprint_keys = {'family_sha256', 'binding_sha256', 'semantic_policy_sha256', 'annotations_sha256',
                        'concept_sha256', 'experiments_root_sha256', 'asset_root_sha256', 'ledger_path_sha256'}
    p.require(type(ticket['input_fingerprints']) is dict and set(ticket['input_fingerprints']) == fingerprint_keys
              and all(type(value) is str and p.HEX64.fullmatch(value)
                      for value in (*ticket['input_fingerprints'].values(), ticket['authority_sha256'],
                                    ticket['intent_sha256'], ticket['studio_root_sha256'])),
              'Malformed prepared fingerprints', 'ticket_changed')
    attempt = db.execute('SELECT * FROM attempts WHERE attempt_id=?', (attempt_id,)).fetchone()
    p.require(attempt is not None, 'Attempt is absent')
    attempt = ledger._validate_row(attempt)
    p.require(ticket['attempt_binding'] == ledger._job_binding(attempt)
              and ticket['intent_sha256'] == attempt['intent_sha256'], 'Ticket/attempt binding differs', 'ticket_changed')
    p.require(row['state'] in STATES and type(row['revision']) is int
              and row['revision'] == STATES[row['state']], 'Invalid monotonic dispatch state', 'journal_changed')
    if row['state'] == 'prepared':
        p.require(row['claim_id'] is None and row['outcome_json'] is None,
                  'Prepared ticket already carries a claim', 'journal_changed')
    else:
        p.require(type(row['claim_id']) is str and len(row['claim_id']) == 32
                  and all(c in '0123456789abcdef' for c in row['claim_id']), 'Missing claim identity')
        outcome = p.decode_json(row['outcome_json']) if row['outcome_json'] is not None else None
        if row['state'] == 'claimed':
            p.require(outcome is None, 'Unsettled claim already carries an outcome', 'journal_changed')
        else:
            p.require(type(outcome) is dict and outcome.get('simulation_only') is True,
                      'Malformed retained dispatch outcome', 'journal_changed')
            if row['state'] == 'uncertain':
                p.require(set(outcome) == {'error', 'callback_attempted', 'simulation_only'}
                          and type(outcome['error']) is str and len(outcome['error']) <= 350
                          and type(outcome['callback_attempted']) is bool, 'Malformed uncertain outcome', 'journal_changed')
            else:
                p.require(type(outcome.get('prompt_id')) is str and outcome['prompt_id'].strip()
                          and len(outcome['prompt_id']) <= 200, 'Missing acknowledged prompt', 'journal_changed')
                digest_key = 'workflow_sha256' if row['state'] == 'acknowledged' else 'observation_sha256'
                keys = {'prompt_id', 'simulation_only', digest_key} | ({'state'} if row['state'] == 'settled' else set())
                p.require(set(outcome) == keys and type(outcome[digest_key]) is str and p.HEX64.fullmatch(outcome[digest_key])
                          and (row['state'] != 'settled' or outcome['state'] in ('completed', 'failed')),
                          'Malformed terminal outcome', 'journal_changed')
    return row, ticket, attempt


def ticket_count(path):
    with ledger._connection(path) as db:
        _schema(db)
        return db.execute('SELECT count(*) FROM p36_dispatch_tickets').fetchone()[0]


def inspect_dispatch(path, attempt_id):
    try:
        with ledger._connection(path) as db:
            row, ticket, attempt = _read_ticket(db, attempt_id)
        return _result(passed=True, action='observe-existing', state=row['state'], attempt_id=attempt_id,
                       callback_may_have_run=row['state'] != 'prepared', attempt_state=attempt['state'],
                       ticket_sha256=p.digest(ticket))
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as error:
        return _error(error, attempt_id=attempt_id)


def _validate_context(experiments, family, intent, studio_root):
    _runtime(experiments)
    production_intent.validate_intent(intent)
    p.require(intent['family_id'] == family['family_id'] and intent['stage'] in p.STAGES,
              'Prepared work names a different character family/stage')
    p.require(intent['batch_count'] == 1 and intent['operation'] == 'comfy.generate.v1',
              'Dispatch lab supports exactly one ordinary prepared member')
    return p.digest({'studio_root': str(Path(studio_root).resolve())})


def _current_intent(experiments, intent, studio_root):
    report = production_intent.revalidate_intent(experiments, intent, studio_root=studio_root)
    p.require(type(report) is dict and report.get('passed') is True,
              'Prepared Production source changed or is unavailable', 'production_intent_changed')
    return report


def _admit(experiments, family, binding, intent, asset_root, semantic_policy, annotations, path):
    return admission.check_transition(experiments, family, binding, intent['stage'],
        asset_root=asset_root, semantic_policy=semantic_policy, annotations=annotations, ledger_path=path)


def _snapshot(*values):
    # Retain our own bounded JSON values; caller mutation cannot replace the
    # operation between its digest check and publication/callback.
    return tuple(p.decode_json(p.canonical_bytes(value)) for value in values)


def _conditions(port, intent):
    conditions = port.check_conditions(copy.deepcopy(intent))
    p.require(type(conditions) is dict and set(conditions) == {'scope', 'backend_ready', 'budget_allowed', 'lease_held'}
              and conditions['scope'] == 'simulation-only'
              and all(conditions[key] is True for key in ('backend_ready', 'budget_allowed', 'lease_held')),
              'Simulated worker conditions refuse this claim', 'worker_conditions_blocked')


def prepare_dispatch(path, *, request_id, experiments, family, binding, asset_root,
                     semantic_policy, annotations, intent, studio_root=p.REPO_ROOT):
    """Reserve once after fresh preparation. Existing requests are observation only."""
    attempt_id = None
    try:
        family, binding, semantic_policy, annotations, intent = _snapshot(family, binding, semantic_policy, annotations, intent)
        root_hash = _validate_context(experiments, family, intent, studio_root)
        intent_hash = p.digest(intent)
        # Existing requests cannot be rebound, nor auto-adopt an orphaned row.
        with ledger._connection(path) as db:
            _schema(db)
            existing = db.execute('SELECT attempt_id FROM attempts WHERE family_id=? AND request_id=?',
                                  (family['family_id'], request_id)).fetchone()
            if existing:
                attempt_id = existing[0]
                row, ticket, attempt = _read_ticket(db, attempt_id)
                p.require(ticket['intent_sha256'] == intent_hash and ticket['studio_root_sha256'] == root_hash,
                          'Existing request binds another intent', 'ticket_changed')
                expected = {'family_sha256': p.digest(family), 'binding_sha256': p.digest(binding),
                            'annotations_sha256': p.digest(annotations),
                            'semantic_policy_sha256': admission.sheet_identity.semantic_policy_digest(semantic_policy)}
                p.require(all(ticket['input_fingerprints'].get(k) == v for k, v in expected.items()),
                          'Existing request binds different admission inputs', 'ticket_changed')
                p.require(attempt['job_id'] == intent['job_id'], 'Existing request names another job')
                return _result(passed=True, action='observe-existing', state=row['state'], attempt_id=attempt_id)
        _current_intent(experiments, intent, studio_root)
        report = _admit(experiments, family, binding, intent, asset_root, semantic_policy, annotations, path)
        if not report['passed']:
            return _result(blockers=report['blockers'], admission_sha256=report['report_sha256'])
        reservation = ledger.reserve(path, family_id=family['family_id'], stage=intent['stage'],
            request_id=request_id, job_id=intent['job_id'], intent_sha256=intent_hash,
            experiments=experiments, workspace_id=family['workspace_id'])
        attempt_id = reservation['attempt_id']
        p.require(reservation['created'], 'Concurrent/orphaned reservation is observation-only', 'reservation_not_owned')
        ticket = {'schema': 'las.p36-dispatch-ticket/1', 'attempt_id': attempt_id,
                  'attempt_binding': reservation['job_binding'], 'intent_sha256': intent_hash,
                  'input_fingerprints': report['input_fingerprints'],
                  'authority_sha256': report['authority']['capture_sha256'], 'studio_root_sha256': root_hash}
        with ledger._connection(path, writable=True) as db:
            _schema(db)
            row = db.execute('SELECT * FROM attempts WHERE attempt_id=?', (attempt_id,)).fetchone()
            current = ledger._validate_row(row)
            p.require(current['state'] == 'unresolved' and ledger._job_binding(current) == ticket['attempt_binding'],
                      'Reservation changed before preparation publication')
            db.execute('INSERT INTO p36_dispatch_tickets VALUES (?,?,?,?,?,?,?)',
                       (attempt_id, p.canonical_bytes(ticket).decode('utf-8'), p.digest(ticket),
                        'prepared', 0, None, None))
        return _result(passed=True, created=True, action='prepared', state='prepared', attempt_id=attempt_id,
                       ticket_sha256=p.digest(ticket))
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as error:
        return _error(error, attempt_id=attempt_id)


def _owned_prepared_gate(report, ticket, attempt):
    """Recognize only our exact reserved attempt; ordinary admission stays false."""
    stage = attempt['stage']; attempt_id = attempt['attempt_id']
    expected = [{'code': 'uncertain_submission', 'stage': stage, 'detail': '', 'source': 'attempt-ledger'}]
    p.require(report['passed'] is False and report['blockers'] == expected,
              'Another admission condition blocks dispatch', 'current_admission_blocked')
    capture = report['ledger']
    p.require(capture['blockers'] == [{'code': 'uncertain_submission', 'stage': stage, 'attempt_id': attempt_id}],
              'Own ticket cannot hide another uncertain attempt', 'foreign_uncertainty')
    selected = [row for row in capture['attempts'] if row['attempt_id'] == attempt_id]
    p.require(len(selected) == 1 and ledger._validate_row(selected[0]) == attempt
              and attempt['state'] == 'unresolved', 'Owned reservation changed', 'ticket_changed')
    p.require(report['input_fingerprints'] == ticket['input_fingerprints']
              and report['authority']['capture_sha256'] == ticket['authority_sha256'],
              'Prepared authority or admission inputs changed', 'admission_changed')
    p.require(report['authority']['passed'] is True and report['next_gate']['passed'] is True
              and report['media_bytes_verified'] is True
              and all(value['passed'] is True for value in report['semantic'].values()),
              'Own reservation is not an exemption from identity/current authority')


def _job_root(experiments, job_id):
    root = _runtime(experiments); p.safe_relative(job_id)
    directory = root / 'runs' / job_id
    p.require(not any(p.linked(x) for x in (directory, directory.parent)), 'Linked job destination refused')
    return directory


def _publish_pending(experiments, intent, ticket):
    directory = _job_root(experiments, intent['job_id'])
    directory.mkdir(parents=True, exist_ok=False)
    graph = copy.deepcopy(intent['graph'])
    job = {'id': intent['job_id'], 'status': 'submitting', 'privacy': 'regular',
           'preset_id': intent['preset_id'], 'backend_id': intent['backend_id'],
           'batch_count': 1, 'prompt_ids': [], 'submissions': [], 'outputs': [],
           'project_id': intent['project_id'], 'p36_attempt': ticket['attempt_binding'],
           'p36_simulation': True,
           'pending_submission': {'index': 0, 'seed': intent['seed'], 'graph': graph, 'marked_at': 0}}
    # These are Studio's existing publication barriers and marker/receipt shapes.
    observation_state.publish(directory / 'workflow.json', graph)
    observation_state.publish(directory / 'state.json', job)
    return job


def _publish_acknowledgement(experiments, intent, job, response):
    prompt = response.get('prompt_id') if type(response) is dict else None
    p.require(type(prompt) is str and prompt.strip() and len(prompt) <= 200,
              'Simulated response lacks an exact prompt ID', 'uncertain_response')
    updated = copy.deepcopy(job)
    updated['prompt_ids'] = [prompt]
    updated['submissions'] = [{'index': 0, 'prompt_id': prompt, 'seed': intent['seed'],
                               'graph': copy.deepcopy(intent['graph']), 'status': 'observing'}]
    updated.pop('pending_submission')
    updated['status'] = 'running'
    observation_state.publish(_job_root(experiments, intent['job_id']) / 'state.json', updated)
    return updated


def _outcome(path, attempt_id, claim_id, state, outcome):
    with ledger._connection(path, writable=True) as db:
        row, _, _ = _read_ticket(db, attempt_id)
        p.require(row['state'] == 'claimed' and row['claim_id'] == claim_id,
                  'Claim no longer belongs to this invocation', 'claim_changed')
        db.execute('UPDATE p36_dispatch_tickets SET state=?,revision=2,outcome_json=? WHERE attempt_id=?',
                   (state, p.canonical_bytes(outcome).decode('utf-8'), attempt_id))


def dispatch_once(path, attempt_id, *, experiments, family, binding, asset_root, semantic_policy,
                  annotations, intent, port, studio_root=p.REPO_ROOT, _checkpoint=None):
    """Invoke the synthetic port at most once. Every retained claim is observe-only.

The explicit simulation port reports injected backend/budget/lease conditions;
these are not observations of the owner's GPU or real Production authority.
No reusable generation capability is returned. The private checkpoint argument
only lets the process-crash tests stop at named durable boundaries.
"""
    state = None; invoked = False; claim_id = None
    checkpoint = _checkpoint or (lambda name: None)
    try:
        from dispatch_simulation import SimulationPort
        p.require(isinstance(port, SimulationPort), 'Only the local simulation port is supported')
        family, binding, semantic_policy, annotations, intent = _snapshot(family, binding, semantic_policy, annotations, intent)
        root_hash = _validate_context(experiments, family, intent, studio_root)
        with ledger._connection(path, writable=True) as db:
            row, ticket, attempt = _read_ticket(db, attempt_id); state = row['state']
            p.require(ticket['intent_sha256'] == p.digest(intent) and ticket['studio_root_sha256'] == root_hash,
                      'Dispatch invocation differs from the prepared intent', 'ticket_changed')
            if state != 'prepared':
                return _result(passed=True, action='observe-existing', state=state, attempt_id=attempt_id,
                               callback_may_have_run=True)
            p.require(attempt['state'] == 'unresolved', 'Prepared reservation is no longer unresolved')
            _conditions(port, intent)
            _current_intent(experiments, intent, studio_root)
            fresh = _admit(experiments, family, binding, intent, asset_root, semantic_policy, annotations, path)
            _owned_prepared_gate(fresh, ticket, attempt)
            p.require(not _job_root(experiments, intent['job_id']).exists(),
                      'A job already exists before the owned claim', 'preexisting_job')
            claim_id = secrets.token_hex(16)
            changed = db.execute("UPDATE p36_dispatch_tickets SET state='claimed',revision=1,claim_id=? WHERE attempt_id=? AND state='prepared' AND revision=0",
                                 (claim_id, attempt_id)).rowcount
            p.require(changed == 1, 'Another invocation owns the claim', 'claim_conflict')
        state = 'claimed'  # Durable commit completed before any callback or job publication.
        checkpoint('after-claim')
        job = _publish_pending(experiments, intent, ticket)
        checkpoint('after-marker')
        # A veto during job publication consumes this claim without a callback.
        # These serial reads still do not lock the owner's Workspace or GPU.
        with ledger._connection(path, writable=True) as db:
            owned, current_ticket, attempt = _read_ticket(db, attempt_id)
            p.require(owned['state'] == 'claimed' and owned['claim_id'] == claim_id,
                      'Claim changed before callback', 'claim_changed')
            _conditions(port, intent)
            fresh = _admit(experiments, family, binding, intent, asset_root, semantic_policy, annotations, path)
            _owned_prepared_gate(fresh, current_ticket, attempt)
        invoked = True
        response = port.submit_once(attempt_id, {'prompt': copy.deepcopy(intent['graph']), 'client_id': 'asset-studio'})
        checkpoint('after-callback')
        recorded = _publish_acknowledgement(experiments, intent, job, response)
        checkpoint('after-receipt')
        _outcome(path, attempt_id, claim_id, 'acknowledged', {'prompt_id': recorded['prompt_ids'][0],
                 'workflow_sha256': p.digest(intent['graph']), 'simulation_only': True})
        return _result(passed=True, action='acknowledged', state='acknowledged', attempt_id=attempt_id,
                       callback_invoked=True, prompt_id=recorded['prompt_ids'][0],
                       conditions_scope='simulation-only', explicit_observation_required=True)
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as error:
        if state == 'claimed' and claim_id is not None:
            try:
                _outcome(path, attempt_id, claim_id, 'uncertain',
                         {'error': _diag(error), 'callback_attempted': invoked, 'simulation_only': True})
                state = 'uncertain'
            except (ValueError, OSError, KeyError, TypeError, sqlite3.Error):
                pass  # Claimed is already a permanent no-replay state.
        return _error(error, state=state, attempt_id=attempt_id, callback_invoked=invoked)


def reconcile_dispatch(path, attempt_id, *, experiments, intent):
    """Observe retained terminal evidence explicitly; never call the port or retry."""
    try:
        intent, = _snapshot(intent)
        _runtime(experiments); production_intent.validate_intent(intent)
        with ledger._connection(path, writable=True) as db:
            row, ticket, _ = _read_ticket(db, attempt_id)
            p.require(row['state'] != 'prepared' and ticket['intent_sha256'] == p.digest(intent),
                      'Only the exact claimed operation can be reconciled')
            job, state_hash = studio_authority.read_record(experiments, 'runs/' + intent['job_id'] + '/state.json')
            graph, workflow_hash = studio_authority.read_record(experiments, 'runs/' + intent['job_id'] + '/workflow.json')
            p.require(type(job) is dict and type(graph) is dict
                      and p.digest(graph) == p.digest(intent['graph']) and job.get('p36_simulation') is True,
                      'Observed workflow differs from exact simulated intent')
            submissions = job.get('submissions')
            p.require(type(submissions) is list and len(submissions) == 1 and type(submissions[0]) is dict
                      and p.digest(submissions[0].get('graph')) == p.digest(intent['graph'])
                      and type(submissions[0].get('seed')) is int and submissions[0]['seed'] == intent['seed']
                      and type(submissions[0].get('index')) is int and submissions[0]['index'] == 0,
                      'Observed member differs from intent')
            prompt = submissions[0].get('prompt_id')
            p.require(type(prompt) is str and prompt.strip() and len(prompt) <= 200
                      and job.get('prompt_ids') == [prompt], 'Observed prompt identity is invalid')
            outcome = p.decode_json(row['outcome_json']) if row['outcome_json'] is not None else {}
            if row['state'] in ('acknowledged', 'settled'):
                p.require(outcome.get('prompt_id') == prompt, 'Known acknowledged prompt changed', 'prompt_identity_changed')
            state = 'completed' if studio_authority.job_is_settled(job) else 'failed'
            observed_hash = p.digest({'job_id': intent['job_id'], 'state': state,
                                      'state_sha256': state_hash, 'workflow_sha256': workflow_hash})
            resolved = ledger._resolve_in_connection(db, attempt_id, experiments=experiments,
                                                      expected_observation_sha256=observed_hash)
            db.execute("UPDATE p36_dispatch_tickets SET state='settled',revision=3,outcome_json=? WHERE attempt_id=?",
                       (p.canonical_bytes({'state': resolved['state'], 'observation_sha256': resolved['observation_sha256'],
                                           'prompt_id': prompt, 'simulation_only': True}).decode('utf-8'), attempt_id))
        return _result(passed=True, action='observed-terminal', state='settled', attempt_id=attempt_id,
                       attempt_state=resolved['state'])
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as error:
        return _error(error, attempt_id=attempt_id)
