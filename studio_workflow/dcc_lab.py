"""Offline research/evidence CLI: python -m studio_workflow.dcc_lab --help.

No command starts Blender, generation, a server, an agent or a model download.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

from .core import canonical, decode, digest, need
from .research_intake import import_report, read_bytes, verify_archive
from .dcc_evidence import compare_bundles, probe_intent

ROOT = Path(__file__).resolve().parents[1]
STATUSES = {'implemented_offline', 'native_pending', 'planned', 'research_only', 'parked'}
SOURCE_EVIDENCE = {'reported_not_reverified', 'source_inspected',
                   'documentation_observed_not_runtime_tested', 'owner_document_observed_not_installed',
                   'research_reference_not_rechecked_in_implementation'}


def validate_programme(value):
    value = decode(canonical(value))
    need(isinstance(value, dict) and value.get('format') == 'studio.agentic-creation-programme/v1'
         and value.get('automatic_execution') is False, 'Expected a non-executing research programme')
    sources = value.get('sources')
    need(isinstance(sources, list) and 1 <= len(sources) <= 128, 'Invalid source catalogue')
    source_ids = set()
    for source in sources:
        need(isinstance(source, dict) and isinstance(source.get('id'), str)
             and source['id'] not in source_ids and source.get('evidence') in SOURCE_EVIDENCE, 'Invalid or duplicate source')
        source_ids.add(source['id'])
        if 'url' in source:
            url = urlsplit(source['url'])
            need(url.scheme == 'https' and url.hostname and not url.username and not url.password,
                 'Expected an HTTPS primary source without credentials')
    rows = value.get('experiments')
    need(isinstance(rows, list) and 1 <= len(rows) <= 32, 'Invalid experiment list')
    seen = set()
    for row in rows:
        need(isinstance(row, dict), 'Invalid experiment')
        key = row.get('id')
        need(isinstance(key, str) and re.fullmatch('[a-z][a-z0-9-]{1,63}', key)
             and key not in seen, 'Invalid or duplicate experiment ID')
        seen.add(key)
        need(row.get('status') in STATUSES, 'Unknown implementation status')
        for field in ('title', 'question', 'hypothesis', 'stop', 'next_decision'):
            need(isinstance(row.get(field), str) and row[field].strip(), 'Missing experiment ' + field)
        for field in ('inputs', 'prerequisites', 'steps', 'artifacts', 'success', 'sources'):
            need(isinstance(row.get(field), list) and row[field]
                 and all(isinstance(x, str) and x.strip() for x in row[field]), 'Invalid ' + field)
        need(set(row['sources']) <= source_ids, 'Unknown experiment source')
        budget = row.get('budget')
        need(isinstance(budget, dict) and type(budget.get('max_jobs')) is int
             and 1 <= budget['max_jobs'] <= 64 and type(budget.get('wall_hours')) is int
             and 1 <= budget['wall_hours'] <= 48
             and budget.get('gpu') in {'none', 'exclusive', 'exclusive_if_generating'}
             and budget.get('enforcement'), 'Invalid or unbounded planning budget')
    opportunities = value.get('opportunities')
    need(isinstance(opportunities, list) and 1 <= len(opportunities) <= 64, 'Invalid opportunity map')
    seen = set()
    for row in opportunities:
        need(isinstance(row, dict) and isinstance(row.get('id'), str)
             and row['id'] not in seen, 'Invalid or duplicate opportunity')
        seen.add(row['id'])
        need(row.get('readiness') in {'usable_now', 'bounded_project', 'research', 'not_recommended', 'parked'},
             'Unknown opportunity readiness')
        need(all(type(row.get(k)) is int and 1 <= row[k] <= 5
                 for k in ('value', 'effort', 'resource_cost', 'novelty')), 'Invalid opportunity rank')
    return {'experiments': len(rows), 'opportunities': len(opportunities),
            'programme_sha256': digest(value), 'generation_submitted': False}


def load_programme():
    value = decode(read_bytes(ROOT / 'research' / 'agentic-creation' / 'programme.json'))
    validate_programme(value)
    return value


def experiment_intent(programme, experiment_id):
    programme = decode(canonical(programme))
    validated = validate_programme(programme)
    selected = next((r for r in programme['experiments'] if r['id'] == experiment_id), None)
    need(selected is not None, 'Unknown experiment')
    result = {'format': 'studio.dcc-experiment-intent/v1', 'executable': False,
              'generation_submitted': False, 'status': 'proposed', 'experiment': selected,
              'programme_sha256': validated['programme_sha256'],
              'requires': ['Resolve and pin actual input/tool/model bytes',
                           'Existing resource admission and explicit bounded job execution',
                           'Respect workspace-specific artistic and data-flow decisions']}
    result['plan_sha256'] = digest(result)
    return result


def _write(path, value):
    with path.open('xb') as stream:
        stream.write(canonical(value) + b'\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('validate')
    fixture = sub.add_parser('seeded-study'); fixture.add_argument('--out', required=True, type=Path)
    imp = sub.add_parser('import-report'); imp.add_argument('source', type=Path)
    imp.add_argument('--out', required=True, type=Path)
    ver = sub.add_parser('verify-archive'); ver.add_argument('directory', type=Path)
    exp = sub.add_parser('plan-experiment'); exp.add_argument('experiment')
    exp.add_argument('--out', required=True, type=Path)
    probe = sub.add_parser('plan-probe')
    for key in ('config', 'source', 'out'):
        probe.add_argument('--' + key, required=True, type=Path)
    compare = sub.add_parser('compare'); compare.add_argument('before', type=Path); compare.add_argument('after', type=Path)
    compare.add_argument('--required', nargs='+', required=True)
    compare.add_argument('--holdout', nargs='+', required=True)
    compare.add_argument('--max-channel-delta', type=int, default=0)
    compare.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'validate':
            result = validate_programme(load_programme())
        elif args.command == 'seeded-study':
            from .dcc_fixture import run_study
            result = run_study(args.out)
        elif args.command == 'import-report':
            result = import_report(args.source, args.out)
        elif args.command == 'verify-archive':
            result = verify_archive(args.directory)
        elif args.command == 'plan-experiment':
            result = experiment_intent(load_programme(), args.experiment); _write(args.out, result)
        elif args.command == 'plan-probe':
            result = probe_intent(args.config, args.source, args.out)
            args.out.mkdir(exist_ok=False); _write(args.out / 'intent.json', result)
        else:
            result = compare_bundles(args.before, args.after, args.required, args.holdout, args.max_channel_delta)
            _write(args.out, result)
        print(canonical(result).decode())
        # A diagnostic comparison is not a successful gate when evidence is absent
        # or different. The report is still retained for analysis.
        if args.command == 'seeded-study' and not result['expectations_met']:
            return 1
        return 1 if args.command == 'compare' and result['status'] != 'within_declared_tolerance' else 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(f'dcc-lab: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
