"""Bounded, provider-neutral setup compatibility advice. Never installs or runs."""
from __future__ import annotations

import argparse
import copy
from datetime import date
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from .core import decode, digest, need

INPUT_FORMAT = 'studio.setup-compatibility-input/v1'
REPORT_FORMAT = 'studio.setup-compatibility-report/v1'
MAX_CANDIDATES = 256
MAX_EVIDENCE = 1024
ID = re.compile(r'[a-z0-9][a-z0-9_.-]{0,95}\Z')
GENERIC_IDENTITY = re.compile(r'[a-z][a-z0-9_-]{0,31}:[A-Za-z0-9][A-Za-z0-9._/@+:-]{0,259}\Z')
KINDS = {'creator_documentation', 'controlled_run', 'local_observation',
         'gallery_co_use', 'provider_metadata', 'authored_hypothesis'}
STRONG = {'creator_documentation', 'controlled_run'}
STATES = {'recommended': 0, 'possible': 1, 'needs_review': 2, 'incompatible': 3}


def text(value, limit=300):
    return isinstance(value, str) and 0 < len(value) <= limit and '\x00' not in value


def token(value, limit=300):
    return text(value, limit) and value.strip() == value and not any(ch in value for ch in ('\r', '\n', '\t'))


def identifier(value):
    need(isinstance(value, str) and ID.fullmatch(value), 'Invalid bounded identifier')
    return value


def identity(value):
    if value is None: return None
    need(token(value, 300) and not any(ch.isspace() for ch in value), 'Invalid resource identity')
    if value.startswith('sha256:'):
        need(re.fullmatch(r'sha256:[a-f0-9]{64}', value) is not None, 'Invalid SHA-256 identity')
    elif value.startswith('civitai-version:'):
        need(re.fullmatch(r'civitai-version:[1-9][0-9]{0,19}', value) is not None,
             'Invalid Civitai version identity')
    else: need(GENERIC_IDENTITY.fullmatch(value) is not None, 'Invalid resource identity')
    return value


def strings(value, label, maximum, *, allow_empty=True):
    need(isinstance(value, list) and len(value) <= maximum and (allow_empty or bool(value)),
         'Invalid ' + label)
    need(all(token(item, 300) for item in value), 'Invalid ' + label)
    need(len(set(value)) == len(value), 'Duplicate ' + label)
    return list(value)


def validate_source(value):
    need(isinstance(value, dict) and set(value) == {'locator', 'revision', 'retrieved_at'},
         'Invalid evidence source')
    need(text(value['locator'], 1000) and value['locator'].strip() == value['locator'],
         'Evidence source locator required')
    if '://' in value['locator']:
        parsed = urlsplit(value['locator'])
        need(parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password,
             'Use a credential-free HTTPS locator')
    need(value['revision'] is None or token(value['revision'], 300) and '://' not in value['revision'],
         'Invalid source revision')
    if value['retrieved_at'] is not None:
        need(isinstance(value['retrieved_at'], str) and
             re.fullmatch(r'\d{4}-\d{2}-\d{2}', value['retrieved_at']) is not None,
             'Retrieval date must use YYYY-MM-DD')
        date.fromisoformat(value['retrieved_at'])
    return copy.deepcopy(value)


def validate_slot(value):
    fields = {'role', 'modality', 'architecture', 'base_lineage', 'strict_lineage',
              'loader', 'runtime', 'formats', 'objective', 'capabilities',
              'known_absent_capabilities'}
    need(isinstance(value, dict) and set(value) == fields, 'Invalid setup slot fields')
    for key in ('role', 'modality', 'architecture', 'loader', 'runtime'):
        need(token(value[key], 160), 'Setup slot ' + key + ' is required')
    objective = identifier(value['objective'])
    need(value['base_lineage'] is None or token(value['base_lineage'], 160), 'Invalid base lineage')
    need(type(value['strict_lineage']) is bool, 'strict_lineage must be boolean')
    need(not value['strict_lineage'] or value['base_lineage'] is not None,
         'strict lineage requires an explicit base_lineage')
    formats = strings(value['formats'], 'formats', 32, allow_empty=False)
    capabilities = strings(value['capabilities'], 'capabilities', 256)
    absent = strings(value['known_absent_capabilities'], 'known absent capabilities', 256)
    need(not set(capabilities) & set(absent), 'A capability cannot be both present and absent')
    return {**copy.deepcopy(value), 'objective': objective, 'formats': formats,
            'capabilities': capabilities, 'known_absent_capabilities': absent}


def validate_candidate(value):
    fields = {'id', 'name', 'role', 'modality', 'architecture', 'base_lineage',
              'loaders', 'format', 'runtime', 'requires', 'identity'}
    need(isinstance(value, dict) and set(value) == fields, 'Invalid candidate fields')
    result = copy.deepcopy(value); result['id'] = identifier(value['id'])
    need(text(value['name'], 200) and value['name'].strip() == value['name'], 'Candidate name is required')
    for key in ('role', 'modality'):
        need(token(value[key], 160), 'Candidate ' + key + ' is required')
    for key in ('architecture', 'base_lineage', 'format', 'runtime'):
        need(value[key] is None or token(value[key], 160), 'Invalid candidate ' + key)
    result['loaders'] = strings(value['loaders'], 'candidate loaders', 32)
    result['requires'] = strings(value['requires'], 'candidate requirements', 64)
    result['identity'] = identity(value['identity'])
    return result


def validate_evidence(value):
    fields = {'id', 'candidate_id', 'resource_identity', 'kind', 'scope', 'direction',
              'objective', 'observations', 'independent_sources', 'source'}
    need(isinstance(value, dict) and set(value) == fields, 'Invalid evidence fields')
    result = copy.deepcopy(value); result['id'] = identifier(value['id'])
    result['candidate_id'] = identifier(value['candidate_id'])
    need(value['kind'] in KINDS, 'Unknown evidence kind')
    need(value['scope'] in ('exact_resource', 'family'), 'Unknown evidence scope')
    need(value['direction'] in ('supports', 'contradicts'), 'Unknown evidence direction')
    result['objective'] = identifier(value['objective'])
    for key in ('observations', 'independent_sources'):
        need(type(value[key]) is int and 0 <= value[key] <= 1000000, 'Invalid ' + key)
    result['resource_identity'] = identity(value['resource_identity'])
    result['source'] = validate_source(value['source'])
    if value['scope'] == 'exact_resource':
        need(result['resource_identity'] is not None, 'Exact evidence needs a resource identity')
        need(result['source']['revision'] is not None, 'Exact evidence needs a retained source revision')
    else: need(result['resource_identity'] is None, 'Family evidence cannot claim an exact resource identity')
    if value['kind'] == 'gallery_co_use':
        need(value['observations'] > 0 and value['independent_sources'] > 0,
             'Gallery evidence needs bounded observations and independent sources')
        need(value['independent_sources'] <= value['observations'],
             'Gallery independent sources cannot exceed observations')
    if value['kind'] == 'controlled_run':
        need(value['observations'] > 0,
             'Controlled run evidence needs at least one observation')
    return result


def finding(code, message, **details):
    return {'code': code, 'message': message, **details}


def compatibility(slot, candidate):
    hard, unknown, limitations = [], [], []
    if candidate['role'] != slot['role']:
        hard.append(finding('role_mismatch', 'Candidate component role does not fit this setup slot.',
                            expected=slot['role'], actual=candidate['role']))
    if candidate['modality'] != slot['modality']:
        hard.append(finding('modality_mismatch', 'Candidate modality does not fit this setup.',
                            expected=slot['modality'], actual=candidate['modality']))
    if candidate['architecture'] is None:
        unknown.append(finding('architecture_unknown', 'Candidate architecture is not established.'))
    elif candidate['architecture'] != slot['architecture']:
        hard.append(finding('architecture_mismatch', 'Candidate architecture conflicts with the setup architecture.',
                            expected=slot['architecture'], actual=candidate['architecture']))
    if slot['base_lineage'] is not None:
        if candidate['base_lineage'] is None:
            unknown.append(finding('base_lineage_unknown', 'Candidate base lineage is not established.'))
        elif candidate['base_lineage'] != slot['base_lineage']:
            item = finding('base_lineage_mismatch' if slot['strict_lineage'] else 'base_lineage_differs',
                           'Candidate base lineage differs from the selected setup lineage.',
                           expected=slot['base_lineage'], actual=candidate['base_lineage'])
            (hard if slot['strict_lineage'] else limitations).append(item)
    if not candidate['loaders']:
        unknown.append(finding('loader_unknown', 'Candidate loader compatibility is not established.'))
    elif slot['loader'] not in candidate['loaders']:
        hard.append(finding('loader_mismatch', 'Candidate does not declare the setup loader input.',
                            expected=slot['loader'], actual=candidate['loaders']))
    if candidate['format'] is None:
        unknown.append(finding('format_unknown', 'Candidate file format is not established.'))
    elif candidate['format'] not in slot['formats']:
        hard.append(finding('format_mismatch', 'Candidate file format is not supported by this slot.',
                            expected=slot['formats'], actual=candidate['format']))
    if candidate['runtime'] is None:
        unknown.append(finding('runtime_unknown', 'Candidate runtime is not established.'))
    elif candidate['runtime'] != slot['runtime']:
        hard.append(finding('runtime_mismatch', 'Candidate runtime conflicts with the active setup runtime.',
                            expected=slot['runtime'], actual=candidate['runtime']))
    if candidate['identity'] is None:
        unknown.append(finding('identity_unknown', 'Exact model/version/file identity is not established.'))
    present, absent = set(slot['capabilities']), set(slot['known_absent_capabilities'])
    for requirement in candidate['requires']:
        if requirement in absent:
            hard.append(finding('required_capability_absent', 'A required companion or loader capability is known absent.',
                                capability=requirement))
        elif requirement not in present:
            unknown.append(finding('required_capability_unknown', 'A required companion or loader capability was not observed.',
                                   capability=requirement))
    return hard, unknown, limitations


def evidence_for(candidate, claims, slot, diagnostics):
    summary = {'strong_support': 0, 'strong_contradiction': 0,
               'compatibility_support': 0, 'compatibility_contradiction': 0,
               'qualified_gallery_claims': 0, 'qualified_gallery_sources': 0,
               'qualified_gallery_observations': 0, 'weak_support': 0,
               'weak_contradiction': 0}
    applied = []
    for claim in claims:
        if claim['candidate_id'] != candidate['id']: continue
        exact = claim['scope'] == 'exact_resource'
        if exact and claim['resource_identity'] != candidate['identity']:
            diagnostics.append(finding('evidence_identity_mismatch',
                'Exact evidence targets another resource identity.', evidence_id=claim['id'],
                candidate_id=candidate['id'], expected=candidate['identity'], actual=claim['resource_identity']))
            continue
        if claim['objective'] not in (slot['objective'], 'compatibility'): continue
        applied.append(claim['id'])
        objective = claim['objective'] == slot['objective']
        compatibility_only = claim['objective'] == 'compatibility' and not objective
        if claim['direction'] == 'supports':
            if compatibility_only and exact: summary['compatibility_support'] += 1
            elif objective and exact and claim['kind'] in STRONG: summary['strong_support'] += 1
            elif objective and exact and claim['kind'] == 'gallery_co_use' and claim['observations'] >= 3 and claim['independent_sources'] >= 2:
                summary['qualified_gallery_claims'] += 1
                summary['qualified_gallery_sources'] += claim['independent_sources']
                summary['qualified_gallery_observations'] += claim['observations']
            elif objective: summary['weak_support'] += 1
        else:
            if compatibility_only and exact: summary['compatibility_contradiction'] += 1
            elif objective and exact and claim['kind'] in STRONG: summary['strong_contradiction'] += 1
            elif objective: summary['weak_contradiction'] += 1
    summary['applied_claims'] = sorted(applied)
    return summary


def evaluate(value):
    need(isinstance(value, dict) and set(value) == {'format', 'slot', 'candidates', 'evidence'},
         'Supply format, slot, candidates and evidence')
    need(value['format'] == INPUT_FORMAT, 'Unsupported setup compatibility request')
    slot = validate_slot(value['slot'])
    need(isinstance(value['candidates'], list) and 1 <= len(value['candidates']) <= MAX_CANDIDATES,
         'Use 1–256 setup candidates')
    candidates = [validate_candidate(item) for item in value['candidates']]
    ids = [item['id'] for item in candidates]; need(len(set(ids)) == len(ids), 'Duplicate candidate ID')
    resource_identities = [item['identity'] for item in candidates if item['identity'] is not None]
    need(len(set(resource_identities)) == len(resource_identities),
         'Duplicate candidate resource identity')
    need(isinstance(value['evidence'], list) and len(value['evidence']) <= MAX_EVIDENCE,
         'Use at most 1,024 evidence records')
    diagnostics, claims = [], []
    raw_ids = [item.get('id') for item in value['evidence'] if isinstance(item, dict)]
    for raw in value['evidence']:
        try:
            item = validate_evidence(raw)
            need(raw_ids.count(item['id']) == 1, 'Duplicate evidence ID: ' + item['id'])
            if item['candidate_id'] not in ids:
                diagnostics.append(finding('unknown_evidence_candidate',
                    'Evidence names a candidate outside this request.', evidence_id=item['id'],
                    candidate_id=item['candidate_id']))
                continue
            claims.append(item)
        except (ValueError, TypeError) as exc:
            diagnostics.append(finding('invalid_evidence', str(exc)[:300],
                evidence_id=raw.get('id') if isinstance(raw, dict) else None))
    rows = []
    for candidate in candidates:
        hard, unknown, limitations = compatibility(slot, candidate)
        summary = evidence_for(candidate, claims, slot, diagnostics)
        if summary['strong_support'] and summary['strong_contradiction']:
            limitations.append(finding('strong_evidence_conflict',
                'Exact strong sources support and contradict this recommendation; no source was silently selected.'))
        elif summary['strong_contradiction']:
            limitations.append(finding('exact_negative_evidence',
                'Exact strong evidence contradicts recommendation for the selected objective.'))
        if summary['compatibility_contradiction']:
            limitations.append(finding('compatibility_evidence_contradiction',
                'Exact evidence contradicts compatibility, but it was not promoted into an unreviewed hard fact.'))
        if summary['weak_contradiction']:
            limitations.append(finding('contradictory_evidence',
                'Weaker or family-scoped evidence contradicts this candidate.'))
        promotable = (summary['strong_support'] > 0 or summary['qualified_gallery_claims'] > 0)
        if hard: status = 'incompatible'
        elif unknown: status = 'needs_review'
        elif promotable and not summary['strong_contradiction'] and not summary['compatibility_contradiction']:
            status = 'recommended'
        else: status = 'possible'
        rows.append({'id': candidate['id'], 'name': candidate['name'], 'identity': candidate['identity'],
                     'status': status, 'selectable': status in ('recommended', 'possible'),
                     'expert_override_required': status == 'needs_review', 'recommendation_rank': None,
                     'hard_conflicts': hard, 'unknowns': unknown, 'limitations': limitations,
                     'evidence_summary': summary})
    rows.sort(key=lambda item: (STATES[item['status']], -item['evidence_summary']['strong_support'],
        -item['evidence_summary']['qualified_gallery_sources'],
        -item['evidence_summary']['qualified_gallery_observations'],
        -item['evidence_summary']['weak_support'], item['name'].casefold(), item['id']))
    rank = 0
    for item in rows:
        if item['status'] == 'recommended': rank += 1; item['recommendation_rank'] = rank
    counts = {state: sum(item['status'] == state for item in rows) for state in STATES}
    return {'format': REPORT_FORMAT, 'authoring_only': True, 'provider_accessed': False,
            'generation_submitted': False, 'selection_changed': False,
            'context_sha256': digest(value), 'slot': copy.deepcopy(slot), 'counts': counts,
            'candidates': rows, 'diagnostics': diagnostics,
            'notice': 'Hard compatibility facts are evaluated before recommendation evidence. '
            'Possible is not proven optimal; Needs review is not compatible; gallery co-use cannot override a hard mismatch. '
            'No provider was contacted and no setup, model, runtime or queue was changed.'}


def read_json(path):
    with path.open('rb') as stream: raw = stream.read(1048577)
    return decode(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request', type=Path, help='Retained provider-neutral request JSON; no provider is contacted')
    args = parser.parse_args(argv)
    try: result = evaluate(read_json(args.request))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({'error': {'code': 'invalid_request', 'message': str(exc)[:500]}},
                         ensure_ascii=False, allow_nan=False))
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)); return 0


if __name__ == '__main__': raise SystemExit(main())