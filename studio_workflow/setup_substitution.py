"""Review-only, dependency-aware setup substitutions.

A substitution profile is retained evidence, not an executable recipe. The planner
recomputes the typed compatibility report, verifies every expected before-value and
shows the complete requested, dependent, removal and invalidation set. It never
installs, stages, switches runtime or submits generation.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
from pathlib import Path

from .core import canonical, decode, digest, need
from .setup_proposal import validate_draft
from . import setup_compatibility as compatibility

REQUEST_FORMAT = 'studio.setup-substitution-request/v1'
PROFILE_FORMAT = 'studio.setup-substitution-profile/v1'
REPORT_FORMAT = 'studio.setup-substitution-report/v1'
# Keep the canonical proposal below the shared command envelope even when
# every byte must be JSON-escaped by the outer setup_draft_command.
MAX_BYTES = 448 * 1024
MAX_CHANGES = 128
CONTROL = re.compile(r'[a-z][a-z0-9_]{0,63}\Z')
REVIEW_REVISION = re.compile(r'sha256:[a-f0-9]{64}\Z')
SOURCE_STATES = {'current', 'stale', 'blocked'}
DOWNLOAD_STATES = {'required', 'already_present', 'unknown'}
APPLICABLE = {'recommended', 'possible'}


def _copy_json(value, label):
    try:
        raw = canonical(value)
        need(len(raw) <= MAX_BYTES, label + ' exceeds the 448 KiB limit')
        return decode(raw)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError('Supply bounded finite JSON for ' + label) from exc


def _text(value, limit, label):
    need(type(value) is str and 0 < len(value) <= limit and value.strip() == value
         and '\x00' not in value, 'Invalid ' + label)
    return value


def _control(value):
    need(type(value) is str and CONTROL.fullmatch(value) is not None,
         'Invalid setup control')
    return value


def _scalar(value, label):
    need(type(value) in (str, int, float), label + ' must be a text or numeric control value')
    if type(value) is str:
        need(len(value) <= 20000 and '\x00' not in value, label + ' text exceeds the limit')
    else:
        need(abs(value) <= 2**53 - 1 and (type(value) is int or math.isfinite(value)),
             label + ' must be a finite browser-safe number')
    return copy.deepcopy(value)


def _change(value, label):
    need(type(value) is dict and set(value) == {'control', 'before', 'after', 'reason'},
         'Invalid ' + label + ' change')
    result = {
        'control': _control(value['control']),
        'before': _scalar(value['before'], label + ' before'),
        'after': _scalar(value['after'], label + ' after'),
        'reason': _text(value['reason'], 1000, label + ' reason'),
    }
    need(canonical(result['before']) != canonical(result['after']),
         label + ' change must alter the control')
    return result


def _component(value):
    fields = {'id', 'resource_identity', 'reason', 'controls'}
    need(type(value) is dict and set(value) == fields,
         'Invalid incompatible component declaration')
    controls = value['controls']
    need(type(controls) is list and 1 <= len(controls) <= 32,
         'Incompatible component needs bounded controls')
    rows = []
    for item in controls:
        need(type(item) is dict and set(item) == {'control', 'before'},
             'Invalid incompatible component control')
        rows.append({'control': _control(item['control']),
                     'before': _scalar(item['before'], 'incompatible component before')})
    need(len({item['control'] for item in rows}) == len(rows),
         'Duplicate incompatible component control')
    return {
        'id': compatibility.identifier(value['id']),
        'resource_identity': compatibility.identity(value['resource_identity']),
        'reason': _text(value['reason'], 1000, 'incompatible component reason'),
        'controls': rows,
    }


def _invalidation(value):
    fields = {'kind', 'id', 'control', 'before', 'reason'}
    need(type(value) is dict and set(value) == fields,
         'Invalid invalidation declaration')
    need(value['kind'] in ('example', 'evidence', 'receipt'),
         'Invalid invalidation kind')
    return {
        'kind': value['kind'],
        'id': _text(value['id'], 160, 'invalidation identity'),
        'control': _control(value['control']),
        'before': _scalar(value['before'], 'invalidation before'),
        'reason': _text(value['reason'], 1000, 'invalidation reason'),
    }


def _implications(value):
    fields = {'download_status', 'download_bytes', 'memory_delta_bytes', 'notes'}
    need(type(value) is dict and set(value) == fields,
         'Invalid substitution implications')
    need(value['download_status'] in DOWNLOAD_STATES,
         'Invalid download status')
    download = value['download_bytes']
    memory = value['memory_delta_bytes']
    need(download is None or type(download) is int and 0 <= download <= 2**50,
         'Invalid download byte estimate')
    need(memory is None or type(memory) is int and -(2**50) <= memory <= 2**50,
         'Invalid memory byte estimate')
    notes = value['notes']
    need(type(notes) is list and len(notes) <= 32,
         'Invalid implication notes')
    notes = [_text(item, 1000, 'implication note') for item in notes]
    need(len(set(notes)) == len(notes), 'Duplicate implication note')
    return {'download_status': value['download_status'], 'download_bytes': download,
            'memory_delta_bytes': memory, 'notes': notes}


def validate_profile(value):
    fields = {'format', 'id', 'review_revision', 'candidate_id',
              'resource_identity', 'component_role', 'requested_changes',
              'dependent_changes', 'incompatible_components', 'invalidations',
              'implications', 'source_status', 'source'}
    need(type(value) is dict and set(value) == fields and value['format'] == PROFILE_FORMAT,
         'Invalid setup substitution profile fields')
    result = copy.deepcopy(value)
    result['id'] = compatibility.identifier(value['id'])
    result['candidate_id'] = compatibility.identifier(value['candidate_id'])
    need(type(value['review_revision']) is str
         and REVIEW_REVISION.fullmatch(value['review_revision']) is not None,
         'Substitution profile review revision must be sha256:<64 lowercase hex>')
    result['review_revision'] = value['review_revision']
    result['resource_identity'] = compatibility.identity(value['resource_identity'])
    result['component_role'] = compatibility.identifier(value['component_role'])
    requested = value['requested_changes']
    dependent = value['dependent_changes']
    components = value['incompatible_components']
    invalidations = value['invalidations']
    need(type(requested) is list and 1 <= len(requested) <= 32,
         'Supply at least one bounded requested change')
    need(type(dependent) is list and len(dependent) <= 64,
         'Invalid dependent changes')
    need(type(components) is list and len(components) <= 32,
         'Invalid incompatible components')
    need(type(invalidations) is list and len(invalidations) <= 32,
         'Invalid invalidations')
    result['requested_changes'] = [_change(item, 'requested') for item in requested]
    result['dependent_changes'] = [_change(item, 'dependent') for item in dependent]
    result['incompatible_components'] = [_component(item) for item in components]
    result['invalidations'] = [_invalidation(item) for item in invalidations]
    result['implications'] = _implications(value['implications'])
    need(value['source_status'] in SOURCE_STATES,
         'Invalid substitution source status')
    result['source_status'] = value['source_status']
    result['source'] = compatibility.validate_source(value['source'])
    if result['source_status'] == 'current':
        need(result['source']['revision'] is not None,
             'Current substitution evidence needs a retained source revision')
    controls = [row['control'] for row in result['requested_changes'] + result['dependent_changes']]
    for component in result['incompatible_components']:
        controls.extend(row['control'] for row in component['controls'])
    controls.extend(row['control'] for row in result['invalidations'])
    need(len(controls) <= MAX_CHANGES, 'Substitution exceeds the change limit')
    need(len(set(controls)) == len(controls),
         'Duplicate control across the atomic substitution profile')
    return result


def query(value):
    q = _copy_json(value, 'setup substitution request')
    fields = {'format', 'draft', 'compatibility_request', 'compatibility_report',
              'candidate_id', 'profile'}
    need(type(q) is dict and set(q) == fields and q['format'] == REQUEST_FORMAT,
         'Invalid setup substitution request fields')
    q['candidate_id'] = compatibility.identifier(q['candidate_id'])
    q['draft'] = validate_draft(q['draft'])
    need(type(q['compatibility_request']) is dict and
         type(q['compatibility_report']) is dict,
         'Supply the exact compatibility request and report')
    q['profile'] = validate_profile(q['profile'])
    need(q['candidate_id'] == q['profile']['candidate_id'],
         'Substitution profile names a different candidate')
    return q


def _expect(controls, control, expected):
    need(control in controls,
         'Control ' + control + ' is absent; the reviewed before-state changed')
    need(canonical(controls[control]) == canonical(expected),
         'Control ' + control + ' changed from the reviewed before-state')


def _derive(before, profile):
    after = copy.deepcopy(before)
    controls = after['recipe']['controls']
    changes = []
    for kind, rows in (('requested', profile['requested_changes']),
                       ('required', profile['dependent_changes'])):
        for row in rows:
            _expect(controls, row['control'], row['before'])
            controls[row['control']] = copy.deepcopy(row['after'])
            changes.append({'kind': kind, **copy.deepcopy(row)})
    for component in profile['incompatible_components']:
        for row in component['controls']:
            _expect(controls, row['control'], row['before'])
            del controls[row['control']]
            changes.append({'kind': 'remove_incompatible',
                            'control': row['control'], 'before': row['before'],
                            'after': None, 'reason': component['reason'],
                            'component_id': component['id'],
                            'resource_identity': component['resource_identity']})
    for row in profile['invalidations']:
        _expect(controls, row['control'], row['before'])
        del controls[row['control']]
        changes.append({'kind': 'invalidate_evidence',
                        'control': row['control'], 'before': row['before'],
                        'after': None, 'reason': row['reason'],
                        'invalidation_kind': row['kind'],
                        'invalidation_id': row['id']})
    return validate_draft(after), changes


def request(value):
    q = query(value)
    fresh = compatibility.evaluate(q['compatibility_request'])
    need(canonical(fresh) == canonical(q['compatibility_report']),
         'Compatibility report is stale or tampered; evaluate the exact context again')
    matches = [row for row in fresh['candidates'] if row['id'] == q['candidate_id']]
    need(len(matches) == 1, 'Compatibility report does not contain the selected candidate')
    candidate = copy.deepcopy(matches[0])
    profile = q['profile']
    need(profile['candidate_id'] == candidate['id'],
         'Substitution profile names a different candidate')
    need(profile['resource_identity'] == candidate['identity'],
         'Substitution profile resource identity differs from the compatibility candidate')
    before = copy.deepcopy(q['draft'])
    after, changes = _derive(before, profile)
    blockers = []
    if candidate['status'] == 'needs_review':
        blockers.append({'code': 'candidate_needs_review',
                         'message': 'Required compatibility facts are unknown; inspect natively before applying.'})
    elif candidate['status'] == 'incompatible':
        blockers.append({'code': 'candidate_incompatible',
                         'message': 'The typed compatibility report contains hard conflicts.'})
    elif candidate['status'] not in APPLICABLE or candidate.get('selectable') is not True:
        blockers.append({'code': 'candidate_not_selectable',
                         'message': 'The compatibility report does not authorize this candidate.'})
    if profile['source_status'] != 'current':
        blockers.append({'code': 'source_' + profile['source_status'],
                         'message': 'The retained substitution source is ' + profile['source_status'] +
                                    '; refresh or unblock it before applying.'})
    core = {
        'format': REPORT_FORMAT,
        'request': q,
        'before': before,
        'after': after,
        'changes': changes,
        'invalidations': copy.deepcopy(profile['invalidations']),
        'candidate': candidate,
        'compatibility': {
            'format': fresh['format'],
            'context_sha256': fresh['context_sha256'],
            'diagnostics': copy.deepcopy(fresh['diagnostics']),
            'notice': fresh['notice'],
        },
        'profile': copy.deepcopy(profile),
        'source_status': profile['source_status'],
        'source': copy.deepcopy(profile['source']),
        'implications': copy.deepcopy(profile['implications']),
        'precondition': {
            'draft_sha256': digest(before),
            'compatibility_context_sha256': fresh['context_sha256'],
            'compatibility_report_sha256': digest(fresh),
            'profile_sha256': digest(profile),
        },
        'blockers': blockers,
        'can_apply': not blockers,
        'execution_authorized': False,
        'selection_changed': False,
        'provider_accessed': False,
        'installation_started': False,
        'runtime_switched': False,
        'generation_submitted': False,
        'side_effects': [
            'Planning changes no draft, file, environment, queue or model runtime.',
            'Applying requires the exact reviewed proposal hash and one matching shared draft revision.',
            'Apply appends one draft revision only; installation, runtime switching and generation remain separate explicit actions.',
        ],
        'limits': [
            'Compatibility is the retained typed report for this exact candidate and context, not filename matching or installed-byte verification.',
            'Download and memory values are retained estimates; preparation must recheck current inventory and runtime.',
            'Unknown, incompatible, stale and blocked substitutions remain inspectable but cannot be applied.',
        ],
    }
    exact = canonical(core).decode('utf-8')
    need(len(exact.encode()) <= MAX_BYTES,
         'Setup substitution proposal exceeds the 448 KiB limit')
    return {**core,
            'proposal_sha256': hashlib.sha256(exact.encode()).hexdigest(),
            'proposal_json': exact}


def validate_reply(value, expected_request=None):
    need(type(value) is dict and type(value.get('proposal_json')) is str and
         type(value.get('proposal_sha256')) is str,
         'Supply the exact reviewed substitution proposal')
    exact = value['proposal_json']
    need(len(exact.encode()) <= MAX_BYTES,
         'Setup substitution proposal exceeds the 448 KiB limit')
    need(hashlib.sha256(exact.encode()).hexdigest() == value['proposal_sha256'],
         'Substitution proposal hash does not match the reviewed bytes')
    core = decode(exact)
    need(type(core) is dict and set(value) == set(core) | {'proposal_json', 'proposal_sha256'},
         'Substitution proposal fields differ from the reviewed bytes')
    observed = {key: value[key] for key in core}
    need(canonical(observed) == canonical(core),
         'Substitution proposal values differ from the reviewed bytes')
    if expected_request is not None:
        need(canonical(core.get('request')) == canonical(query(expected_request)),
             'Substitution proposal request differs from the expected request')
    fresh = request(core['request'])
    need(fresh['proposal_json'] == exact and
         fresh['proposal_sha256'] == value['proposal_sha256'],
         'Substitution proposal context changed; inspect a fresh complete diff')
    return fresh


def read_json(path: Path):
    with path.open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    need(len(raw) <= MAX_BYTES, 'Request exceeds the 448 KiB limit')
    return decode(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Plan a zero-side-effect atomic setup substitution')
    parser.add_argument('request', type=Path)
    args = parser.parse_args(argv)
    try:
        result = request(read_json(args.request))
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        print(json.dumps({'error': {'code': 'invalid_substitution',
                                   'message': str(exc)[:500]},
                          'generation_submitted': False}, sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
