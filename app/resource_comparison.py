"""Finite, descriptive comparisons of pinned job observations; no execution path."""
from __future__ import annotations

import json
import os
from pathlib import Path

from resource_receipts import (EvidenceError, inspect_observation, is_hash, is_id,
                               parse_document, read_evidence_file, require, sha256)

PLAN_SCHEMA = 'studio.resource-comparison-plan/v1'
SCHEMA = 'studio.resource-comparison/v1'
MAX_PAIRS = 8
MAX_PLAN_BYTES = 64 * 1024
MAX_REPORT_BYTES = 1024 * 1024
CONDITIONS = ('unspecified', 'cold_process', 'cold_first_generation', 'warm_same_model', 'model_switch')


def encode_report(report):
    """Serialize exactly the bytes enforced by the report-size contract and CLI."""
    return (json.dumps(report, ensure_ascii=True, allow_nan=False, separators=(',', ':')) + '\n').encode('utf-8')


def _compact_row(row):
    return {'expected_job_id': row['expected_job_id'],
            'expected_result_sha256': row['expected_result_sha256'],
            'state': row['state'], 'reasons': list(row['reasons']), 'observation': None}


def _compact_comparison(value):
    warnings = sorted(set(value['warnings']) | {'report_metrics_omitted'})
    return {'state': value['state'], 'blockers': list(value['blockers']), 'warnings': warnings,
            'observed_differences': list(value['observed_differences']), 'host_metrics': {}, 'devices': [],
            'coordinator_elapsed_delta_seconds': value['coordinator_elapsed_delta_seconds']}


def _compact_report(result):
    compact = {key: value for key, value in result.items() if key != 'pairs'}
    compact['report_compacted'] = True
    compact['pairs'] = [
        {'id': pair['id'], 'declared_condition': pair['declared_condition'],
         'condition_verified': pair['condition_verified'], 'qualified_benchmark': pair['qualified_benchmark'],
         'baseline': _compact_row(pair['baseline']), 'candidate': _compact_row(pair['candidate']),
         'comparison': _compact_comparison(pair['comparison'])}
        for pair in result['pairs']
    ]
    compact['limitations'] = list(compact['limitations']) + [
        'Detailed observation payloads and metric tables were omitted to keep the retained row report within its byte bound.'
    ]
    return compact


def _fit_report(result):
    if len(encode_report(result)) <= MAX_REPORT_BYTES:
        return result
    compact = _compact_report(result)
    require(len(encode_report(compact)) <= MAX_REPORT_BYTES, 'report_too_large')
    return compact


def _manifest(raw, parent):
    plan = parse_document(raw)
    require(isinstance(plan, dict) and set(plan) == {'schema', 'generation_allowance', 'pairs'}
            and plan['schema'] == PLAN_SCHEMA and type(plan['generation_allowance']) is int
            and plan['generation_allowance'] == 0, 'plan_invalid')
    pairs = plan['pairs']
    require(isinstance(pairs, list) and 1 <= len(pairs) <= MAX_PAIRS, 'pair_limit_invalid')
    ids, jobs, pins, paths = set(), set(), set(), set()
    for pair in pairs:
        require(isinstance(pair, dict) and set(pair) == {'id', 'condition', 'baseline', 'candidate'}
                and is_id(pair['id']) and pair['id'] not in ids
                and pair['condition'] in CONDITIONS, 'pair_invalid')
        ids.add(pair['id'])
        for side in ('baseline', 'candidate'):
            trial = pair[side]
            require(isinstance(trial, dict) and set(trial) == {'directory', 'result_sha256', 'job_id'}
                    and is_id(trial['job_id']) and is_hash(trial['result_sha256'])
                    and isinstance(trial['directory'], str) and 1 <= len(trial['directory']) <= 2048
                    and '\0' not in trial['directory'], 'trial_invalid')
            path = Path(trial['directory'])
            if not path.is_absolute(): path = parent / path
            # Do not resolve symlinks: the inspector must still see and refuse them.
            path = path.absolute()
            normalized = os.path.normcase(os.path.abspath(path))
            require(trial['job_id'] not in jobs and trial['result_sha256'] not in pins
                    and normalized not in paths, 'duplicate_trial_evidence')
            jobs.add(trial['job_id']); pins.add(trial['result_sha256']); paths.add(normalized)
            trial['directory'] = path
    return pairs


def _inspect(trial):
    row = {'expected_job_id': trial['job_id'], 'expected_result_sha256': trial['result_sha256'],
           'state': None, 'reasons': [], 'observation': None}
    try:
        row['observation'] = inspect_observation(trial['directory'], expected_job_id=trial['job_id'],
                                                expected_result_sha256=trial['result_sha256'])
        row['state'] = 'verified'
    except EvidenceError as error:
        row.update(state='incomplete' if error.incomplete else 'invalid', reasons=[error.code])
    return row


def _reject_reused_prompts(pairs):
    owners = {}
    for pair in pairs:
        for side in ('baseline', 'candidate'):
            row = pair[side]
            if row['state'] != 'verified': continue
            for item in row['observation']['submissions']:
                pin = item['prompt_id_sha256']
                if pin is not None: owners.setdefault(pin, []).append(row)
    for rows in owners.values():
        if len(rows) > 1:
            for row in rows:
                row['state'] = 'invalid'
                row['observation'] = None
                if 'reused_prompt_evidence' not in row['reasons']: row['reasons'].append('reused_prompt_evidence')


def _metric(a, b):
    result = {'baseline': a, 'candidate': b}
    for statistic in ('sampled_min', 'sampled_max'):
        result[statistic + '_delta'] = None if a[statistic] is None or b[statistic] is None else b[statistic] - a[statistic]
    return result


def _workload(report):
    return [{key: item[key] for key in ('index', 'graph_sha256', 'controls_sha256', 'reference_manifest_sha256')}
            for item in report['submissions']]


def _compare(a, b):
    result = {'state': 'withheld', 'blockers': [], 'warnings': [], 'observed_differences': [],
              'host_metrics': {}, 'devices': [], 'coordinator_elapsed_delta_seconds': None}
    if a['state'] != 'verified' or b['state'] != 'verified':
        result['blockers'].append('evidence_not_verified'); return result
    left, right = a['observation'], b['observation']
    sa, sb = left['profile_summary'], right['profile_summary']
    ra, rb = left['runtime_observation'], right['runtime_observation']
    if _workload(left) != _workload(right): result['blockers'].append('saved_workload_mismatch')
    if not sa['sampling']['observed'] or not sb['sampling']['observed']: result['blockers'].append('no_observed_samples')
    if sa['source']['sampler_sha256'] != sb['source']['sampler_sha256']: result['blockers'].append('sampler_source_mismatch')
    if any('intent_sequence_gap' in r['warnings'] for r in (left, right)): result['blockers'].append('intent_sequence_gap')
    if ra is None or rb is None or ra['lost'] or rb['lost']: result['blockers'].append('runtime_bracket_unavailable')
    if sa['sampling']['interval_seconds_after_completion'] != sb['sampling']['interval_seconds_after_completion']:
        result['warnings'].append('different_sampling_interval')
    if sa['sampling']['observed'] != sb['sampling']['observed']: result['warnings'].append('unequal_sample_counts')
    for name, x, y in (('runtime_profile', ra and ra['profile_sha256'], rb and rb['profile_sha256']),
                        ('runtime_versions', sa['comfy']['versions'], sb['comfy']['versions']),
                        ('source_capture', left['source_observation'], right['source_observation'])):
        if x != y: result['observed_differences'].append(name)
    if result['blockers']: return result
    result['state'] = 'descriptive'
    result['host_metrics'] = {key: _metric(sa['metrics'][key], sb['metrics'][key])
                              for key in sa['metrics'] if key.endswith('_bytes')}
    da = {item['index']: item['metrics'] for item in sa['comfy']['devices']}
    db = {item['index']: item['metrics'] for item in sb['comfy']['devices']}
    if set(da) != set(db): result['warnings'].append('device_layout_mismatch')
    else:
        result['devices'] = [{'index': index, 'metrics': {key: _metric(da[index][key], db[index][key])
                              for key in da[index]}} for index in sorted(da)]
    fa, fb = left['finish_snapshot'], right['finish_snapshot']
    if (fa and fb and fa['status'] == fb['status'] == 'completed'
            and fa['elapsed_seconds'] is not None and fb['elapsed_seconds'] is not None
            and all(item['response'] == 'received' for report in (left, right) for item in report['submissions'])):
        result['coordinator_elapsed_delta_seconds'] = fb['elapsed_seconds'] - fa['elapsed_seconds']
    else: result['warnings'].append('coordinator_elapsed_not_comparable')
    return result


def compare_observations(manifest: str | Path) -> dict:
    """Read one bounded plan, validate it fully, then inspect every pinned record.

    Relative paths belong to the manifest directory. No scanning, sampling,
    mutation, substitution, retries or execution; invalid rows stay in the report.
    """
    path = Path(manifest).absolute()
    raw = read_evidence_file(path, MAX_PLAN_BYTES)
    requested = _manifest(raw, path.parent)
    pairs = [{'id': pair['id'], 'declared_condition': pair['condition'], 'condition_verified': False,
              'qualified_benchmark': False, 'baseline': _inspect(pair['baseline']), 'candidate': _inspect(pair['candidate'])}
             for pair in requested]
    _reject_reused_prompts(pairs)
    counts = {'requested_pairs': len(pairs), 'requested_observations': 2 * len(pairs), 'verified_observations': 0,
              'invalid_observations': 0, 'incomplete_observations': 0, 'descriptive_pairs': 0, 'withheld_pairs': 0}
    for pair in pairs:
        for side in ('baseline', 'candidate'): counts[pair[side]['state'] + '_observations'] += 1
        pair['comparison'] = _compare(pair['baseline'], pair['candidate'])
        counts[pair['comparison']['state'] + '_pairs'] += 1
    result = {'schema': SCHEMA, 'manifest_sha256': sha256(raw), 'counts': counts, 'pairs': pairs,
              'evidence_complete': counts['verified_observations'] == counts['requested_observations'],
              'qualified_benchmark': False, 'execution_authority': False, 'generation_allowance_added': 0,
              'report_compacted': False,
              'limitations': [
                  'All differences are descriptive candidate minus baseline observations, not causal gains or policy.',
                  'Cold/warm labels are caller declarations, never verified starting conditions.',
                  'Saved graph/control/reference hashes do not attest loaded code or actual model/input contents.',
                  'Sample counts and timing differ; sampled extrema can miss peaks and do not reserve resources.',
                  'Device indices do not prove identical hardware; working sets and memory domains are not summed.',
                  'Coordinator snapshots are not authoritative final outcomes; elapsed time is not inference phase time.',
                  'Every requested observation is retained; no success-only averages or pooled performance claims.',
                  'Finite benchmark execution and full trial identity remain separate from this offline report.'
              ]}
    return _fit_report(result)
