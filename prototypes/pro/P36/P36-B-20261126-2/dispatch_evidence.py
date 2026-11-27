"""Reproduce durable synthetic dispatch outcomes; never send a network request.

Run via prove.py. Actual Studio preparation, Workspace, SQLite, file publication
and independent Python processes are exercised. The callback only appends a row
to a local counting database. This is not a throughput or physical power-loss
benchmark. Raw runtime contexts/logs are deliberately nondeterministic; returned
case decisions and counts contain no paths, random identities or timing data.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from unittest.mock import patch

import admission
import attempt_ledger as ledger
import dispatch_coordinator as coordinator
from dispatch_fixtures import make_dispatch_case, parameters, write_context
from dispatch_simulation import SimulationPort
import pipeline as p


def prove_dispatch(out):
    out = admission._output_path(out); out.mkdir(parents=True, exist_ok=False)
    rows = []

    def setup(name):
        context = make_dispatch_case(out / name)
        coordinator.initialize(context['ledger_path'])
        port = SimulationPort(context['simulation_path'])
        ticket = coordinator.prepare_dispatch(context['ledger_path'], request_id='evidence-request', **parameters(context))
        p.require(ticket['passed'] and ticket['created'], 'Dispatch evidence preparation failed: ' + name)
        return context, port, ticket

    def drive(context, port, ticket, **changes):
        return coordinator.dispatch_once(context['ledger_path'], ticket['attempt_id'], port=port,
                                         **{**parameters(context), **changes})

    def record(name, expected, calls, context, port, ticket, result, **extra):
        p.require(result['passed'] is expected and port.count() == calls,
                  'Dispatch evidence outcome disagrees: ' + name, 'proof_failed')
        p.require(result['generation_submitted'] is False and result['submission_authority'] is False,
                  'Simulation claimed generation authority')
        row = {'case': name, 'expected_passed': expected, 'passed': result['passed'],
               'expected_callbacks': calls, 'observed_callbacks': port.count(),
               'state': result['state'], 'action': result['action'],
               'blocker_codes': sorted({item['code'] for item in result['blockers']}), **extra}
        rows.append(row)
        p.write_new_runtime(out / name / 'observation.json', result)

    def revoke(context):
        with context['workspace'].connection() as db:
            db.execute("UPDATE asset_acceptances SET withdrawn_at=2 WHERE id='test-concept-front'")

    def job_path(context, name='state.json'):
        return context['experiments'] / 'runs' / context['intent']['job_id'] / name

    def terminal(context):
        job = p.load_json(job_path(context)); job['status'] = 'completed'
        job['submissions'][0]['status'] = 'completed'
        job['outputs'] = [{'filename': 'synthetic-descriptor-only.png', 'prompt_id': job['prompt_ids'][0]}]
        job_path(context).write_bytes(p.canonical_bytes(job))
        return job

    name = 'valid-terminal-and-replays'; context, port, ticket = setup(name)
    result = drive(context, port, ticket); p.require(result['passed'], 'Valid callback refused')
    for _ in range(3):
        replay = drive(context, port, ticket)
        p.require(replay['action'] == 'observe-existing' and not replay['callback_invoked'], 'Callback was rearmed')
    terminal(context)
    settled = coordinator.reconcile_dispatch(context['ledger_path'], ticket['attempt_id'],
        experiments=context['experiments'], intent=context['intent'])
    p.require(settled['passed'] and settled['state'] == 'settled', 'Exact simulated terminal observation failed')
    record(name, True, 1, context, port, ticket, settled, replay_count=3, synthetic_terminal_only=True)

    mutators = [
        ('withdrawal-before-claim', revoke),
        ('semantic-side-drift', lambda c: c['annotations']['concept']['views'][0]['anchors']['left-iris'].__setitem__('value', 'blue')),
        ('prepared-plan-bytes-drift', lambda c: (c['experiments'] / 'projects' / c['intent']['project_id'] / 'plan.json').write_bytes(b'{}\n')),
        ('model-bytes-drift', lambda c: c['production']['model_path'].write_bytes(b'changed synthetic model')),
        ('input-bytes-drift', lambda c: c['production']['input_path'].write_bytes(b'changed synthetic input')),
    ]
    for name, mutate in mutators:
        context, port, ticket = setup(name); mutate(context)
        record(name, False, 0, context, port, ticket, drive(context, port, ticket))
    for condition in ('backend_ready', 'budget_allowed', 'lease_held'):
        name = 'simulated-' + condition + '-veto'; context, port, ticket = setup(name)
        port.conditions[condition] = False
        record(name, False, 0, context, port, ticket, drive(context, port, ticket), conditions_scope='simulation-only')

    name = 'foreign-unresolved-ancestor'; context, port, ticket = setup(name)
    ledger.reserve(context['ledger_path'], family_id=context['family']['family_id'], stage='concept',
        request_id='other-request', job_id='other-job', intent_sha256='c' * 64,
        experiments=context['experiments'], workspace_id=context['family']['workspace_id'])
    record(name, False, 0, context, port, ticket, drive(context, port, ticket))

    name = 'withdrawal-after-marker'; context, port, ticket = setup(name)
    def withdraw_at_marker(boundary):
        if boundary == 'after-marker': revoke(context)
    result = drive(context, port, ticket, _checkpoint=withdraw_at_marker)
    replay = drive(context, port, ticket)
    p.require(replay['action'] == 'observe-existing' and not replay['callback_invoked'], 'Late veto rearmed claim')
    record(name, False, 0, context, port, ticket, result, replay_observation_only=True)

    for mode in ('lost-response', 'malformed'):
        name = mode; context, port, ticket = setup(name); port.mode = mode
        result = drive(context, port, ticket); port.mode = 'accept'
        replay = drive(context, port, ticket)
        p.require(replay['action'] == 'observe-existing' and not replay['callback_invoked'], 'Uncertain request repeated')
        record(name, False, 1, context, port, ticket, result, replay_observation_only=True)

    for method, calls in (('_publish_pending', 0), ('_publish_acknowledgement', 1)):
        name = 'publication-failure-' + method.lstrip('_'); context, port, ticket = setup(name)
        with patch.object(coordinator, method, side_effect=OSError('injected publication failure')):
            result = drive(context, port, ticket)
        replay = drive(context, port, ticket)
        p.require(replay['action'] == 'observe-existing' and not replay['callback_invoked'], 'Publication failure rearmed claim')
        record(name, False, calls, context, port, ticket, result, replay_observation_only=True)

    name = 'caller-intent-mutation'; context, port, ticket = setup(name)
    expected_body = p.digest({'prompt': copy.deepcopy(context['intent']['graph']), 'client_id': 'asset-studio'})
    original_admit = coordinator._admit
    def mutate_caller(*args, **kwargs):
        result = original_admit(*args, **kwargs)
        context['intent']['graph']['2']['inputs']['text'] = 'unbound caller edit'
        return result
    with patch.object(coordinator, '_admit', side_effect=mutate_caller): result = drive(context, port, ticket)
    with sqlite3.connect(context['simulation_path']) as db:
        bodies = [row[0] for row in db.execute('SELECT body_sha256 FROM callbacks')]
    p.require(bodies == [expected_body], 'Caller mutation replaced the prepared operation')
    record(name, True, 1, context, port, ticket, result, exact_prepared_body_preserved=True)

    name = 'foreign-terminal-prompt'; context, port, ticket = setup(name)
    p.require(drive(context, port, ticket)['passed'], 'Expected acknowledgement')
    job = terminal(context); job['prompt_ids'] = ['foreign-prompt']
    job['submissions'][0]['prompt_id'] = job['outputs'][0]['prompt_id'] = 'foreign-prompt'
    job_path(context).write_bytes(p.canonical_bytes(job))
    result = coordinator.reconcile_dispatch(context['ledger_path'], ticket['attempt_id'],
        experiments=context['experiments'], intent=context['intent'])
    record(name, False, 1, context, port, ticket, result)

    name = 'workflow-changed-during-reconciliation'; context, port, ticket = setup(name)
    p.require(drive(context, port, ticket)['passed'], 'Expected acknowledgement'); terminal(context)
    original_observation = ledger._observation
    def swap_workflow(*args, **kwargs):
        graph = copy.deepcopy(context['intent']['graph']); graph['2']['inputs']['text'] = 'changed-at-observation'
        job_path(context, 'workflow.json').write_bytes(p.canonical_bytes(graph))
        return original_observation(*args, **kwargs)
    with patch.object(ledger, '_observation', side_effect=swap_workflow):
        result = coordinator.reconcile_dispatch(context['ledger_path'], ticket['attempt_id'],
            experiments=context['experiments'], intent=context['intent'])
    p.require(coordinator.inspect_dispatch(context['ledger_path'], ticket['attempt_id'])['attempt_state'] == 'unresolved',
              'Failed pinned observation cleared the attempt')
    record(name, False, 1, context, port, ticket, result, attempt_remains_unresolved=True)

    def command(context, ticket, crash_at=None):
        config = context['ledger_path'].parent / 'worker-context.json'
        if not config.exists(): write_context(config, context)
        args = [sys.executable, str(Path(__file__).with_name('dispatch_simulation.py')), 'worker',
                '--context', str(config), '--ledger', str(context['ledger_path']),
                '--attempt-id', ticket['attempt_id'], '--port', str(context['simulation_path'])]
        if crash_at: args.extend(['--crash-at', crash_at])
        return args

    for boundary, calls in (('after-claim', 0), ('after-marker', 0), ('after-callback', 1), ('after-receipt', 1)):
        name = 'process-crash-' + boundary; context, port, ticket = setup(name)
        stopped = subprocess.run(command(context, ticket, boundary), capture_output=True, timeout=45)
        p.require(stopped.returncode == 73, 'Crash boundary was not reached: ' + name)
        recovered = subprocess.run(command(context, ticket), capture_output=True, timeout=45)
        p.require(recovered.returncode == 0, 'Recovery process failed: ' + name)
        result = p.decode_json(recovered.stdout)
        p.require(result['action'] == 'observe-existing' and not result['callback_invoked'], 'Crash recovery repeated callback')
        record(name, True, calls, context, port, ticket, result, crash_exit_code=73, recovered_by_separate_process=True)

    name = 'three-process-claim-race'; context, port, ticket = setup(name); args = command(context, ticket)
    workers = [subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(3)]
    try: outputs = [worker.communicate(timeout=45) for worker in workers]
    finally:
        for worker in workers:
            if worker.poll() is None: worker.kill(); worker.communicate()
    results = [p.decode_json(stdout) for stdout, _ in outputs]
    p.require(all(worker.returncode == 0 for worker in workers)
              and sorted(row['action'] for row in results) == ['acknowledged', 'observe-existing', 'observe-existing'],
              'Competing processes did not choose exactly one callback owner')
    winner = next(row for row in results if row['action'] == 'acknowledged')
    record(name, True, 1, context, port, ticket, winner, independent_processes=3, observe_only_callers=2)

    evidence = {'schema': 'las.p36-dispatch-evidence/1', 'evidence_state': 'implemented',
        'scope': 'actual preparation/SQLite/processes with synthetic callback counter; no network worker',
        'case_count': len(rows), 'matched_outcomes': len(rows),
        'expected_callbacks': sum(row['expected_callbacks'] for row in rows),
        'observed_callbacks': sum(row['observed_callbacks'] for row in rows),
        'duplicate_callbacks': sum(max(0, row['observed_callbacks'] - row['expected_callbacks']) for row in rows),
        'crash_boundaries': 4, 'concurrent_processes': 3,
        'generation_submissions': 0, 'native_imports': 0, 'submission_authority': False,
        'physical_power_loss_guarantee': False, 'windows_qualification_claimed': False, 'cases': rows}
    p.write_new_runtime(out / 'dispatch-evidence.json', evidence)
    return evidence
