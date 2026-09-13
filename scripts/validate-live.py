"""Check catalog graphs against one explicit Comfy schema; never submit work.

Defaults to every preset. --collection, --backend and --preset are explicit filters.
--object-info uses saved JSON without network access. The source schema describes
one endpoint, not all installations; a successful check is not runtime certification.
"""
from __future__ import annotations
import argparse
import hashlib
from http.client import HTTPException
import json
from pathlib import Path
import sys
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

import game_asset_pipeline as pipeline

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from backend_contracts import loopback_port

MAX_SCHEMA_BYTES = 32 * 1024**2


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None


def read_schema(stream):
    raw = stream.read(MAX_SCHEMA_BYTES + 1)
    pipeline.require(len(raw) <= MAX_SCHEMA_BYTES, 'Node schema exceeds 32 MiB')
    def reject(value): raise ValueError('Non-finite schema value: '+value)
    info = json.loads(raw.decode('utf-8'), object_pairs_hook=pipeline.pairs, parse_constant=reject)
    pipeline.require(isinstance(info, dict) and bool(info), 'Expected nonempty object_info mapping')
    pipeline.require(all(isinstance(value, dict) for value in info.values()), 'Expected node-schema objects')
    return info, hashlib.sha256(raw).hexdigest()


def load_schema(path=None, comfy_url='http://127.0.0.1:8188'):
    if path is not None:
        with Path(path).open('rb') as stream: return read_schema(stream)
    loopback_port(comfy_url)
    # Explicit local discovery only: no proxy, redirect, retry or /prompt validation.
    with build_opener(ProxyHandler({}), NoRedirect()).open(comfy_url.rstrip('/')+'/object_info', timeout=30) as stream:
        return read_schema(stream)


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
            result.update(pipeline.graph_check(graph, info), status='passed')
        except (OSError, ValueError, TypeError, KeyError, RecursionError, OverflowError) as exc:
            result['error'] = str(exc)
        results.append(result)
    return {'selected': len(results), 'passed': sum(r['status'] == 'passed' for r in results),
            'failed': sum(r['status'] != 'passed' for r in results), 'results': results,
            'scope': 'static-graphs-against-one-schema', 'inference_verified': False,
            'submissions': 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=ROOT)
    parser.add_argument('--collection', help='only this collection; omitted means all collections and uncollected presets')
    parser.add_argument('--backend', help='only presets declaring this backend (undeclared means primary); does not switch it')
    parser.add_argument('--preset', action='append', default=[], help='exact preset ID; repeat to select several')
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--object-info', type=Path, help='saved raw object_info JSON; no network requests')
    source.add_argument('--comfy-url', default='http://127.0.0.1:8188', help='explicit managed loopback backend URL')
    parser.add_argument('--json', action='store_true', help='emit the complete per-preset report as JSON')
    args = parser.parse_args(argv)
    try:
        catalog = pipeline.read_json(args.repo_root/'presets/catalog.json')
        pipeline.require(isinstance(catalog, dict), 'Expected catalog object')
        selected = select_presets(catalog.get('presets'), collection=args.collection,
                                  backend=args.backend, preset_ids=args.preset)
        info, digest = load_schema(args.object_info, args.comfy_url)
        report = validate_catalog(args.repo_root, selected, info)
        report.update(catalog_total=len(catalog['presets']), schema_sha256=digest,
                      schema_source=str(args.object_info) if args.object_info else args.comfy_url.rstrip('/')+'/object_info')
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
