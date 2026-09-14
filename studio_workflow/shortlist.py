"""Explain starting-preset choices through existing read-only Studio observations.

This is not a preparation adapter. It does not stage references, check native
custom validators, mint a ticket, approve a model or call the generation worker.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
from http.client import HTTPException
import json
import re
import sys
import time

from .core import digest, need
from .shortlist_source import SOURCE_FIELDS, SOURCE_ROLES, validate_source_query, inspect_source, assignment, validate_source_reply, inspect_sources, unassigned_sources, validate_ordered_reply

PREFIX = '/api/workflow-studio/shortlist'
FORMAT = 'studio.recipe-shortlist/v1'
GOALS = {
    'new-image': ('Create a new image', 'image', {'new-image'}),
    'edit-image': ('Change an existing image', 'image', {'image-to-image', 'instruction-edit', 'localized-detail'}),
    'reference-image': ('Create with pose or identity references', 'image', {'reference-guided-generation', 'instruction-edit', 'restyle'}),
    'upscale-image': ('Upscale an image', 'image', {'upscale'}),
    'masked-repair': ('Repair a selected region', 'image', {'masked-repair'}),
    'animate-image': ('Animate an image', 'video', {'image-to-video'}),
    'image-to-3d': ('Build 3D from an image', '3d', {'image-to-3d'}),
}
LABELS = {'observed': 'Listed prerequisites observed', 'unknown': 'Some checks are unknown',
          'needs_setup': 'Needs attention before preparation'}
MAX_PRESETS, MAX_REQUIREMENTS = 256, 128


def query(value):
    need(type(value) is dict and set(value) <= {'goal', 'reference_count', 'limit', 'offset', 'expected_snapshot', 'sources'} | SOURCE_FIELDS,
         'Supply goal, reference_count, limit, offset, optional expected_snapshot and exact source fields or ordered sources only')
    need(type(value.get('goal')) is str and value['goal'] in GOALS, 'Choose a supported recipe goal')
    result = {'reference_count': len(value['sources']) if type(value.get('sources')) is list else 0,
              'limit': 6, 'offset': 0, **copy.deepcopy(value)}
    for field, low, high in [('reference_count', 0, 3), ('limit', 1, 12), ('offset', 0, MAX_PRESETS)]:
        need(type(result[field]) is int and low <= result[field] <= high, field + ' requires a bounded integer')
    token = result.get('expected_snapshot')
    need(token is None or type(token) is str and re.fullmatch('[0-9a-f]{64}', token), 'Invalid snapshot SHA-256')
    need(result['offset'] == 0 or token is not None, 'Further pages require expected_snapshot')
    validate_source_query(result)
    return result


def _runtime(studio):
    return {'backend_id': studio.backends.active, 'endpoint': studio.comfy_url,
            'switching': bool(studio.backends.busy),
            'operation': copy.deepcopy(getattr(studio.backends, 'operation', None))}


def _text(value, size=800):
    return value[:size] if isinstance(value, str) else ''


def _check(rows, code, state, message):
    rows.append({'code': code, 'state': state, 'message': _text(message)})


def _status(checks):
    return 'needs_setup' if any(c['state'] == 'blocked' for c in checks) else (
        'unknown' if any(c['state'] == 'unknown' for c in checks) else 'observed')


def _restyle_board(preset, cap):
    """Project only the shipped shape: 1–3 board slots plus a separate pose source."""
    if not (isinstance(cap, dict) and cap.get('operation') == 'restyle'
            and cap.get('source_input') == 'last_reference'):
        return None
    slots = preset.get('reference_slots')
    board = preset.get('reference_board')
    if not (type(slots) is list and 1 <= len(slots) <= 3 and type(board) is dict
            and isinstance(preset.get('last_reference'), (list, tuple))):
        return None
    minimum = board.get('min', 1)
    if type(minimum) is not int or not 1 <= minimum <= len(slots):
        return None
    if cap.get('reference_count') != len(slots) + 1:
        return None
    return {'minimum': minimum, 'slot_count': len(slots),
            'source_input': 'last_reference'}


def _candidate(studio, preset, q, info, runtime, worker_alive, assets, observations, source=None, sources=None):
    cap = preset['continuation_capability']; key = preset['id']; checks = []
    board = _restyle_board(preset, cap)
    row = {'preset_id': key, 'name': _text(preset.get('name'), 160) or key,
           'description': _text(preset.get('description')), 'backend_id': preset.get('backend_id', 'primary'),
           'operation': cap['operation'], 'prompt_role': cap.get('prompt_role', 'unknown'),
           'reference_count': cap['reference_count'], 'template_sha256': cap.get('template_sha256'),
           'basis': 'Registered preset default graph, not a tuned recipe or your current draft.',
           'checks': checks, 'requirements': []}
    if board:
        row['reference_board'] = copy.deepcopy(board)
    if sources is not None: row['source_assignments'] = unassigned_sources(sources)
    if runtime['switching']:
        _check(checks, 'backend_switching', 'blocked', 'An environment change is in progress. Check again when it finishes.')
    matching_backend = row['backend_id'] == runtime['backend_id'] and not runtime['switching']
    if not matching_backend:
        _check(checks, 'backend_switch', 'blocked', 'Select the '+row['backend_id']+' environment explicitly in Models & setup, then check again.')
    if preset.get('runtime_block'):
        _check(checks, 'runtime_block', 'blocked', preset['runtime_block'])
    if worker_alive is not True:
        _check(checks, 'worker_unavailable', 'blocked' if worker_alive is False else 'unknown',
               'The Studio worker is unavailable.' if worker_alive is False else 'Studio worker liveness is unknown.')
    count = cap['reference_count']
    if board:
        declared = q['reference_count']
        if declared < board['minimum']:
            _check(checks, 'references_missing', 'blocked',
                   f'This style board needs at least {board["minimum"]} ordered style picture(s); you declared {declared}.')
        elif declared > board['slot_count']:
            _check(checks, 'unused_references', 'blocked',
                   f'This style board has {board["slot_count"]} picture slot(s), not {declared}. Extra images will not be silently dropped.')
        elif declared and not source and not sources:
            _check(checks, 'references_unchecked', 'unknown',
                   'Your style-board count is a declaration. Files, order, roles, staging and bytes have not been checked.')
        _check(checks, 'restyle_source_separate', 'unknown',
               'This check covers style-board pictures only. The separate pose/continuation source is not selected, staged or invented here.')
    elif q['reference_count'] < count:
        _check(checks, 'references_missing', 'blocked', f'This route needs {count} reference image(s); you declared {q["reference_count"]}. Attach them in Create.')
    elif q['reference_count'] > count:
        _check(checks, 'unused_references', 'blocked', f'This route consumes {count} reference image(s), not {q["reference_count"]}. Extra images will not be silently dropped.')
    elif count and not source and not sources:
        _check(checks, 'references_unchecked', 'unknown', 'Your image count is a declaration. Files, role assignments, staging and bytes have not been checked.')
    if source:
        _check(checks, 'source_not_staged', 'unknown', 'The selected primary asset bytes match the Workspace record. It is not attached by this check; other references, roles and transforms still require review in Create.')
    if sources:
        _check(checks, 'sources_not_staged', 'unknown', 'Every selected image was byte-checked in the stated order. No image was attached and no role or transform was applied; review these in Create.')
    if cap.get('requires_mask'):
        _check(checks, 'mask_required', 'blocked', 'Prepare and attach the required RGBA repair image in Create. A declared image is not a checked repair mask.')
    try:
        graph, path = studio.graph_for(preset)
        need(type(graph) is dict and 0 < len(graph) <= 256, 'Unsupported graph size')
        need(type(cap.get('template_sha256')) is str and hashlib.sha256(path.read_bytes()).hexdigest() == cap['template_sha256'],
             'Recipe graph changed or its identity is unavailable; check again')
        # Match preparation's no-op adapter handling without modifying template data.
        graph = copy.deepcopy(graph)
        studio.prune_disabled_loras(graph)
        if source:
            row['source_assignment'], check = assignment(preset, graph, source)
            _check(checks, *check)
        if sources is not None:
            for index, item in enumerate(sources):
                proposed, check = assignment(preset, graph, item, slot=index+1, ordered=True)
                row['source_assignments'][index] = proposed
                code, state, message = check
                _check(checks, code, state, f'Picture {index+1}: {message}')
        # This deliberately checks class presence only, not a second graph validator.
        classes = sorted({n['class_type'] for n in graph.values()})
        if matching_backend and info:
            missing = [name for name in classes if name not in info]
            _check(checks, 'nodes_missing' if missing else 'nodes_observed', 'blocked' if missing else 'observed',
                   'Missing installed node classes: '+', '.join(missing) if missing else 'Required node classes occur in the active cached schema. Native validation is still separate.')
        else:
            _check(checks, 'schema_unknown', 'unknown', 'Node availability for this environment is unknown. No missing-node or compatibility claim is inferred.')
        try:
            requirements = studio.preset_requirements(preset, graph, assets=assets, observations=observations)
            need(type(requirements) is list and len(requirements) <= MAX_REQUIREMENTS
                 and all(type(r) is dict for r in requirements), 'Unsupported dependency report')
            row['requirements'] = [{k: (r[k] if type(r[k]) is bool or r[k] is None else _text(r[k], 500))
                                     for k in ('file', 'path', 'present', 'note', 'installable', 'install_note') if k in r}
                                    for r in requirements]
            missing = [r for r in requirements if r.get('present') is False]
            unknown = [r for r in requirements if r.get('present') is not True and r.get('present') is not False]
            if missing: _check(checks, 'models_missing', 'blocked', f'{len(missing)} required model file(s) are missing or unusable. See exact locations below.')
            if unknown: _check(checks, 'models_unknown', 'unknown', f'{len(unknown)} model dependency location(s) could not be established.')
            if not missing and not unknown:
                _check(checks, 'models_observed', 'observed', 'Declared model files were observed. This is not hash, compatibility or licence verification.')
        except (ValueError, OSError, KeyError, TypeError) as exc:
            _check(checks, 'models_unknown', 'unknown', 'Dependency inspection unavailable: '+str(exc))
        # Reuse the existing static capacity and host-commit gates without prepare().
        from wan_capacity import enforce
        try: enforce(graph)
        except ValueError as exc: _check(checks, 'capacity_hold', 'blocked', str(exc))
        if matching_backend:
            try: studio.host_commit_preflight(preset, graph)
            except ValueError as exc: _check(checks, 'memory_hold', 'blocked', str(exc))
            except OSError as exc: _check(checks, 'memory_unknown', 'unknown', str(exc))
    except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
        _check(checks, 'inspection_failed', 'unknown', 'Recipe inspection unavailable: '+str(exc))
    row['status'] = _status(checks); row['status_label'] = LABELS[row['status']]
    return row


def request(value, studio, *, preset_id=None):
    """One explicit observation. Uses existing caches; no new store or polling loop."""
    q = query(value)
    source = inspect_source(studio, q)
    sources = inspect_sources(studio, q)
    runtime = _runtime(studio); catalog_before = studio.catalog_path.read_bytes()
    need(len(catalog_before) <= 8*1024*1024, 'Preset catalog exceeds shortlist limit')
    data = studio.catalog(); presets = data.get('presets')
    need(type(presets) is list and len(presets) <= MAX_PRESETS, 'Unsupported preset collection')
    need(all(type(p) is dict and isinstance(p.get('id'), str) and re.fullmatch('[A-Za-z0-9_.-]{1,96}', p['id']) for p in presets), 'Invalid preset identities')
    need(len({p['id'] for p in presets}) == len(presets), 'Duplicate preset identities')
    info = None; schema_error = None
    if not runtime['switching']:
        try:
            info = studio.node_info()
            need(type(info) is dict and bool(info) and all(type(k) is str and type(v) is dict for k,v in info.items()), 'Node schema unavailable or malformed')
        except (ValueError, OSError, HTTPException) as exc:
            info = None; schema_error = _text(str(exc))
    observed_schema = getattr(studio, '_schema', None)
    schema_stamp = getattr(studio, '_schema_at', None)
    worker = getattr(studio, 'worker', None)
    worker_alive = worker.is_alive() if worker is not None else None
    assets = studio.library.manifest().get('assets', [])
    rows = []; diagnostics = []; observations = {}
    _, modality, operations = GOALS[q['goal']]
    for preset in presets:
        if preset_id is not None and preset['id'] != preset_id: continue
        cap = preset.get('continuation_capability')
        board = _restyle_board(preset, cap)
        if not (isinstance(cap, dict) and type(cap.get('version')) is int and cap['version'] == 1
                and type(cap.get('reference_count')) is int
                and (0 <= cap['reference_count'] <= 3 or board is not None)
                and type(cap.get('operation')) is str and type(cap.get('consumes_source')) is bool):
            diagnostics.append({'preset_id': preset['id'], 'message': 'Operation evidence unavailable; no route was guessed.'});continue
        if preset.get('modality', 'image') != modality or cap['operation'] not in operations: continue
        if cap['consumes_source'] != (cap['reference_count'] > 0):
            diagnostics.append({'preset_id': preset['id'], 'message': 'Reference wiring is not established.'});continue
        rows.append(_candidate(studio, preset, q, info, runtime, worker_alive, assets, observations, source, sources))
    need(runtime == _runtime(studio) and studio.catalog_path.read_bytes() == catalog_before
         and observed_schema is getattr(studio, '_schema', None) and schema_stamp == getattr(studio, '_schema_at', None),
         'Studio context changed during inspection; check again without reusing this page')
    need(source == inspect_source(studio, q), 'Source context changed during inspection; reopen the asset and check again')
    need(sources == inspect_sources(studio, q), 'Ordered source context changed during inspection; check again')
    rows.sort(key=lambda r: ({'observed': 0, 'unknown': 1, 'needs_setup': 2}[r['status']],
                           sum(c['state'] == 'blocked' for c in r['checks']), r['name'].casefold(), r['preset_id']))
    identity = {'goal': q['goal'], 'reference_count': q['reference_count'], 'runtime': runtime,
                'schema_sha256': digest(info) if info else None, 'catalog_sha256': hashlib.sha256(catalog_before).hexdigest(),
                'candidates': rows, 'diagnostics': diagnostics}
    if source is not None: identity['source'] = source
    if sources is not None: identity['sources'] = sources
    snapshot = digest(identity)
    need(not q.get('expected_snapshot') or snapshot == q['expected_snapshot'], 'Shortlist changed; return to the first page and review the new observations')
    start, end = q['offset'], q['offset'] + q['limit']
    return {'format': FORMAT, 'goal': q['goal'], 'reference_count': q['reference_count'],
            'checked_at': time.time(), 'snapshot_sha256': snapshot, 'backend_id': runtime['backend_id'],
            'schema_sha256': identity['schema_sha256'], 'schema_error': schema_error,
            'source': source, **({'sources': sources} if sources is not None else {}),
            'source_semantics': ('Every ordered Workspace image was byte-checked against its selected SHA-256. No attachments, roles or transforms were applied.' if sources else
                                 'Primary Workspace image bytes checked against the selected SHA-256; no attachment or role applied. Additional images remain declarations.' if source else 'Declared image count only; no source is selected, uploaded or validated.'),
            'scope': 'Default preset route and listed prerequisites only. Native graph validation, full memory fit, licensing and output quality remain separate. Preparation rechecks current state.',
            'total': len(rows), 'counts': {key: sum(r['status'] == key for r in rows) for key in LABELS},
            'offset': start, 'next_offset': end if end < len(rows) else None,
            'candidates': rows[start:end], 'diagnostics': diagnostics,
            'generation_submitted': False, 'execution_authorized': False}


def observe(transport, value):
    """Client-only wrapper keeps read errors useful without changing legacy transport."""
    from urllib.error import HTTPError
    from .client import ClientError, read_response
    q = query(value)
    try: result = transport(PREFIX, q)
    except HTTPError as exc:
        with exc: raw = read_response(exc, 65536)
        try: detail = json.loads(raw) if len(raw) <= 65536 else {}
        except (ValueError, UnicodeError): detail = {}
        if not isinstance(detail, dict) or not isinstance(detail.get('error'), str):
            detail = {'error': 'Shortlist observation failed; check again explicitly.'}
        detail = {**detail, 'code': 'shortlist_unavailable', 'generation_submitted': False}
        raise ClientError(exc.code, detail) from exc
    message = 'Shortlist response does not match the requested context; check again.'
    need(type(result) is dict and result.get('format') == FORMAT and result.get('goal') == q['goal']
         and type(result.get('reference_count')) is int and result['reference_count'] == q['reference_count']
         and result.get('generation_submitted') is False and result.get('execution_authorized') is False, message)
    need(type(result.get('snapshot_sha256')) is str and re.fullmatch('[0-9a-f]{64}', result['snapshot_sha256'])
         and (not q.get('expected_snapshot') or result['snapshot_sha256'] == q['expected_snapshot']), message)
    need(type(result.get('offset')) is int and result['offset'] == q['offset']
         and type(result.get('total')) is int and 0 <= result['total'] <= MAX_PRESETS, message)
    need(type(result.get('candidates')) is list and len(result['candidates']) == min(q['limit'],max(0,result['total']-q['offset']))
         and all(type(row) is dict for row in result['candidates']), message)
    validate_source_reply(result, q, message)
    validate_ordered_reply(result, q, message)
    end = q['offset'] + q['limit']
    need(result.get('next_offset') == (end if end < result['total'] else None), message)
    return result


def main(argv=None):
    """Independent read-only CLI; leaves the legacy ticket-output path unchanged."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8191')
    parser.add_argument('--http-timeout', type=float, default=30)
    parser.add_argument('--goal', choices=GOALS, required=True)
    parser.add_argument('--references', type=int, default=None)
    parser.add_argument('--limit', type=int, default=6)
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--expected-snapshot')
    parser.add_argument('--source-asset-id')
    parser.add_argument('--source-sha256')
    parser.add_argument('--source-role', choices=SOURCE_ROLES)
    parser.add_argument('--sources-json', help='File containing one to three ordered asset_id/sha256/role objects; no upload')
    args = parser.parse_args(argv)
    try:
        from .sdk import WorkflowClient
        source = {key: getattr(args,key) for key in SOURCE_FIELDS if getattr(args,key) is not None}
        if args.sources_json:
            from pathlib import Path
            from .agent_bridge import decode
            with Path(args.sources_json).open('rb') as stream: raw = stream.read(8193)
            need(len(raw) <= 8192, 'Ordered source JSON exceeds 8 KiB')
            source['sources'] = decode(raw.decode('utf-8'))
            need(type(source['sources']) is list, 'Ordered source JSON must be an array of exact source records')
        value = WorkflowClient(args.url, args.http_timeout).shortlist(args.goal, reference_count=args.references,
                limit=args.limit, offset=args.offset, expected_snapshot=args.expected_snapshot, **source)
        print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False));return 0
    except (ValueError, OSError, HTTPException) as exc:
        print(json.dumps({'code': 'shortlist_unavailable', 'error': str(exc), 'generation_submitted': False}));return 2


if __name__ == '__main__': sys.exit(main())