"""Check catalog graphs against one explicit Comfy schema; never submit work.

Defaults to every preset. --collection, --backend and --preset are explicit filters.
--object-info uses saved JSON without network access. The source schema describes
one endpoint, not all installations; a successful check is not runtime certification.
"""
from __future__ import annotations
import argparse
import base64
from datetime import datetime, timezone
import io
import os
import tempfile
import hashlib
from http.client import HTTPException
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener
from urllib.error import HTTPError

import game_asset_pipeline as pipeline

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from backend_contracts import loopback_port

MAX_SCHEMA_BYTES = 32 * 1024**2
MAX_CAPTURE_BYTES = 64 * 1024**2


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None


def read_schema(stream, *, include_raw=False):
    raw = stream.read(MAX_SCHEMA_BYTES + 1)
    pipeline.require(len(raw) <= MAX_SCHEMA_BYTES, 'Node schema exceeds 32 MiB')
    def reject(value): raise ValueError('Non-finite schema value: '+value)
    info = json.loads(raw.decode('utf-8'), object_pairs_hook=pipeline.pairs, parse_constant=reject)
    pipeline.require(isinstance(info, dict) and bool(info), 'Expected nonempty object_info mapping')
    pipeline.require(all(isinstance(value, dict) for value in info.values()), 'Expected node-schema objects')
    result = (info, hashlib.sha256(raw).hexdigest())
    return (*result, raw) if include_raw else result


def load_schema(path=None, comfy_url='http://127.0.0.1:8188', *, include_raw=False):
    if path is not None:
        with Path(path).open('rb') as stream: return read_schema(stream, include_raw=include_raw)
    loopback_port(comfy_url)
    # Explicit local discovery only: no proxy, redirect, retry or /prompt validation.
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(comfy_url.rstrip('/')+'/object_info', timeout=30) as stream:
            return read_schema(stream, include_raw=include_raw)
    except HTTPError as exc:
        exc.close()
        raise


def select_presets(presets, *, collection=None, backend=None, preset_ids=()):
    pipeline.require(isinstance(presets, list) and 0 < len(presets) <= 2048, 'Expected bounded nonempty preset catalog')
    ids = set()
    for preset in presets:
        pipeline.require(isinstance(preset, dict), 'Invalid catalog preset')
        pipeline.text(preset.get('id'), 'preset ID')
        pipeline.require(preset['id'] not in ids, 'Duplicate preset ID: '+preset['id'])
        ids.add(preset['id'])
    wanted = set(preset_ids)
    pipeline.require(wanted <= ids, 'Unknown preset IDs: '+', '.join(sorted(wanted-ids)))
    selected = [p for p in presets if (collection is None or p.get('collection') == collection)
                and (backend is None or p.get('backend_id', 'primary') == backend)
                and (not wanted or p['id'] in wanted)]
    pipeline.require(bool(selected), 'No presets match the requested filters; nothing was checked')
    return selected


def validate_catalog(root, presets, info):
    """One result per selected catalog row, including missing or invalid graph files."""
    results = []
    for preset in presets:
        result = {'preset_id': preset['id'], 'backend_id': preset.get('backend_id', 'primary'),
                  'graph': preset.get('graph'), 'status': 'invalid'}
        try:
            graph = pipeline.read_json(pipeline.inside(root, preset.get('graph')))
            result['graph_sha256'] = pipeline.sha(graph)
            result.update(pipeline.graph_check(graph, info), status='passed')
        except (OSError, ValueError, TypeError, KeyError, RecursionError, OverflowError) as exc:
            result['error'] = str(exc)
        results.append(result)
    return {'selected': len(results), 'passed': sum(r['status'] == 'passed' for r in results),
            'failed': sum(r['status'] != 'passed' for r in results), 'results': results,
            'scope': 'static-graphs-against-one-schema', 'inference_verified': False,
            'submissions': 0}



def capture_target(path):
    path = Path(path)
    pipeline.require(path.parent.is_dir(), 'Capture parent must already be a directory')
    pipeline.require(not os.path.lexists(path), 'Capture target already exists; choose a new evidence file')
    return path


def publish_capture(path, capture):
    """Flush an owned staging file, then publish without replacing another writer."""
    path = capture_target(path)
    raw = json.dumps(capture, ensure_ascii=True, allow_nan=False, indent=2).encode('utf-8')
    pipeline.require(len(raw) <= MAX_CAPTURE_BYTES, 'Schema capture exceeds the byte limit')
    fd, temporary = tempfile.mkstemp(prefix='.schema-capture-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        with open(temporary, 'rb') as stream:
            pipeline.require(stream.read(MAX_CAPTURE_BYTES + 1) == raw, 'Capture readback differs')
        os.link(temporary, path)  # Atomic no-clobber on the same filesystem; no replace fallback.
    except (OSError, ValueError) as exc:
        raise ValueError('Schema capture was not published; staging evidence retained at '+temporary+': '+str(exc)) from exc
    try: os.unlink(temporary)
    except OSError: pass  # The complete published file remains authoritative.


def capture_bindings(report):
    return [{key: row.get(key) for key in ('preset_id', 'backend_id', 'graph', 'graph_sha256')}
            for row in report['results']]


def check_capture_metadata(capture):
    """Require complete v1 evidence, without treating historical checks as authority."""
    def digest(value):
        return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)
    pipeline.text(capture.get('captured_at'), 'capture timestamp')
    stamp = datetime.fromisoformat(capture['captured_at'])
    pipeline.require(stamp.utcoffset() == timezone.utc.utcoffset(stamp), 'Capture timestamp must be UTC')
    source = capture.get('schema_source'); pipeline.text(source, 'capture schema source')
    parsed = urlsplit(source)
    pipeline.require(parsed.path == '/object_info' and not parsed.query and not parsed.fragment,
                     'Capture source must identify object_info without query or fragment')
    loopback_port(parsed._replace(path='').geturl())
    pipeline.require(digest(capture.get('catalog_sha256')), 'Invalid captured catalog digest')
    report = capture.get('capture_results')
    pipeline.require(isinstance(report, dict), 'Missing historical capture report')
    for key in ('selected', 'passed', 'failed', 'catalog_total'):
        pipeline.integer(report.get(key), 0, 2048, 'Captured '+key)
    pipeline.require(report['selected'] == len(capture['bindings']) <= report['catalog_total'],
                     'Historical capture coverage differs')
    for key in ('backend_id', 'schema_sha256', 'schema_source'):
        pipeline.require(report.get(key) == capture[key], 'Historical capture identity differs: '+key)
    pipeline.require(report.get('backend_identity_verified') is False and report.get('inference_verified') is False,
                     'Historical capture cannot verify backend identity or inference')
    pipeline.integer(report.get('submissions'), 0, 0, 'Captured submissions')
    pipeline.require(report.get('scope') == 'static-graphs-against-one-schema'
                     and report.get('schema_scope') == 'backend-bound-snapshot', 'Invalid historical capture scope')
    rows = report.get('results')
    pipeline.require(isinstance(rows, list) and len(rows) == report['selected'], 'Invalid historical result rows')
    ids = set()
    for binding, row in zip(capture['bindings'], rows):
        pipeline.require(isinstance(binding, dict) and set(binding) == {'preset_id', 'backend_id', 'graph', 'graph_sha256'},
                         'Invalid captured graph binding')
        pipeline.text(binding.get('preset_id'), 'captured preset ID')
        pipeline.require(binding['preset_id'] not in ids and binding['backend_id'] == capture['backend_id'],
                         'Duplicate or mismatched captured backend binding')
        ids.add(binding['preset_id'])
        pipeline.require(binding['graph_sha256'] is None or digest(binding['graph_sha256']), 'Invalid captured graph digest')
        pipeline.require(isinstance(row, dict) and all(key in row for key in ('preset_id', 'backend_id', 'graph', 'status')),
                         'Invalid historical graph result')
        pipeline.require(row['status'] in ('passed', 'invalid'), 'Unknown historical graph result status')
        if row['status'] == 'passed':
            pipeline.require('error' not in row, 'Passed historical graph cannot contain an error')
            pipeline.integer(row.get('nodes'), 1, 512, 'Captured node count')
            pipeline.require(digest(row.get('graph_sha256')) and row.get('static_topology') == 'passed'
                             and row.get('node_snapshot_checked') is True and row.get('inference_verified') is False,
                             'Incomplete static graph result')
        else:
            pipeline.require(not {'nodes', 'static_topology', 'node_snapshot_checked'}.intersection(row),
                             'Invalid historical graph cannot contain success-only check fields')
            pipeline.require(isinstance(row.get('error'), str), 'Missing historical graph error')
            pipeline.require('inference_verified' not in row or row['inference_verified'] is False,
                             'Historical graph error cannot verify inference')
    pipeline.require(capture_bindings(report) == capture['bindings'], 'Historical graph bindings differ')
    passed = sum(row['status'] == 'passed' for row in rows)
    pipeline.require(report['passed'] == passed and report['failed'] == len(rows)-passed,
                     'Historical result counts are inconsistent')


def read_capture(path):
    with Path(path).open('rb') as stream: raw = stream.read(MAX_CAPTURE_BYTES + 1)
    pipeline.require(len(raw) <= MAX_CAPTURE_BYTES, 'Schema capture exceeds the byte limit')
    def reject(value): raise ValueError('Non-finite capture value: '+value)
    capture = json.loads(raw.decode('utf-8'), object_pairs_hook=pipeline.pairs, parse_constant=reject)
    pipeline.require(isinstance(capture, dict) and type(capture.get('version')) is int and capture['version'] == 1,
                     'Unsupported schema capture version')
    pipeline.require(capture.get('sha256') == pipeline.sha({k:v for k,v in capture.items() if k != 'sha256'}),
                     'Schema capture changed; integrity check failed')
    pipeline.text(capture.get('backend_id'), 'captured backend ID')
    pipeline.require(capture.get('backend_identity_verified') is False, 'Capture does not authenticate backend identity')
    pipeline.require(isinstance(capture.get('schema_base64'), str), 'Missing captured schema bytes')
    schema_raw = base64.b64decode(capture['schema_base64'], validate=True)
    info, digest = read_schema(io.BytesIO(schema_raw))
    pipeline.require(digest == capture.get('schema_sha256'), 'Captured schema bytes changed')
    pipeline.require(isinstance(capture.get('bindings'), list) and 0 < len(capture['bindings']) <= 2048,
                     'Invalid captured graph coverage')
    check_capture_metadata(capture)
    return capture, info, digest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=ROOT)
    parser.add_argument('--collection', help='only this collection; omitted means all collections and uncollected presets')
    parser.add_argument('--backend', help='only presets declaring this backend (undeclared means primary); does not switch it')
    parser.add_argument('--preset', action='append', default=[], help='exact preset ID; repeat to select several')
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--object-info', type=Path, help='saved raw object_info JSON; no network requests')
    source.add_argument('--comfy-url', help='explicit managed loopback backend URL; normal default is port 8188')
    source.add_argument('--schema-snapshot', type=Path, help='replay a backend-bound capture offline against unchanged catalog graphs')
    parser.add_argument('--capture-schema', type=Path, help='save exact schema bytes and graph identities; requires --backend and --comfy-url, no subset filters')
    parser.add_argument('--json', action='store_true', help='emit the complete per-preset report as JSON')
    args = parser.parse_args(argv)
    try:
        capturing = args.capture_schema is not None
        snapshot = None
        if capturing:
            pipeline.require(bool(args.backend) and bool(args.comfy_url), 'Capture requires explicit --backend and --comfy-url')
            pipeline.require(args.object_info is None and args.schema_snapshot is None, 'Capture requires a live schema, not another file')
            capture_target(args.capture_schema)  # Refuse known output problems before contacting a backend.
        if capturing or args.schema_snapshot:
            pipeline.require(not args.preset and args.collection is None, 'Schema captures require complete backend coverage, not subset filters')
        catalog = pipeline.read_json(args.repo_root/'presets/catalog.json')
        pipeline.require(isinstance(catalog, dict), 'Expected catalog object')
        backend = args.backend
        if args.schema_snapshot:
            snapshot, info, digest = read_capture(args.schema_snapshot)
            pipeline.require(backend is None or backend == snapshot['backend_id'], 'Snapshot backend cannot be relabelled')
            backend = snapshot['backend_id']
            pipeline.require(pipeline.sha(catalog) == snapshot.get('catalog_sha256'), 'Catalog changed since schema capture; capture new evidence')
            pipeline.require(snapshot['capture_results']['catalog_total'] == len(catalog['presets']),
                             'Historical catalog coverage differs')
        selected = select_presets(catalog.get('presets'), collection=args.collection,
                                  backend=backend, preset_ids=args.preset)
        url = args.comfy_url or 'http://127.0.0.1:8188'
        if capturing: info, digest, schema_raw = load_schema(comfy_url=url, include_raw=True)
        elif snapshot is None: info, digest = load_schema(args.object_info, url)
        report = validate_catalog(args.repo_root, selected, info)
        report.update(catalog_total=len(catalog['presets']), schema_sha256=digest,
                      schema_source=str(args.schema_snapshot or args.object_info) if args.schema_snapshot or args.object_info else url.rstrip('/')+'/object_info')
        if snapshot is not None:
            pipeline.require(capture_bindings(report) == snapshot['bindings'], 'Graph coverage or content changed since schema capture')
        if capturing or snapshot is not None:
            report.update(schema_scope='backend-bound-snapshot', backend_id=backend, backend_identity_verified=False)
        if capturing:
            capture = {'version':1, 'captured_at':datetime.now(timezone.utc).isoformat(),
                       'backend_id':backend, 'backend_identity_verified':False,
                       'schema_source':url.rstrip('/')+'/object_info', 'schema_sha256':digest,
                       'schema_base64':base64.b64encode(schema_raw).decode('ascii'),
                       'catalog_sha256':pipeline.sha(catalog), 'bindings':capture_bindings(report),
                       'capture_results':report}
            capture['sha256'] = pipeline.sha(capture)
            publish_capture(args.capture_schema, capture)
            report['schema_capture'] = str(args.capture_schema)
        if args.json: print(json.dumps(report, ensure_ascii=True, allow_nan=False))
        else:
            print('Schema:', report['schema_source'], 'SHA-256:', digest)
            for item in report['results']:
                print('PASS' if item['status'] == 'passed' else 'ERROR', item['preset_id'],
                      '['+str(item['backend_id'])+']', item.get('error', 'static schema check passed'))
            print(f"{report['selected']} of {report['catalog_total']} catalog graphs checked: {report['passed']} passed, {report['failed']} failed; no submissions")
            print('One schema only. Model presence, native custom validation, inference and art acceptance are not certified.')
        return 1 if report['failed'] else 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError, OverflowError, HTTPException) as exc:
        print(json.dumps({'error': str(exc), 'submissions': 0}), file=sys.stderr)
        return 2


if __name__ == '__main__': raise SystemExit(main())
