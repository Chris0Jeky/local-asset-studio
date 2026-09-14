"""Explicit, agent-operable reference analysis; never submits image generation.

Run `python -m studio_prompt.reference_assistant --help` from the repository root.
All outputs are exclusive creates. Images remain workspace-relative, and only an
explicit analyze command may contact the already-installed loopback helper.
"""
from __future__ import annotations
import argparse
import hashlib
from http.client import HTTPException
import json
from pathlib import Path
import sys
from PIL import Image
from . import local_helper
from .reference_analysis import MAX_REFERENCES, ROLE_FACETS, draft, new_request, review_template, validate_request
from .schema import file_bytes, need, read_json, safe_path, write_new


def _report(path):
    value = read_json(path)
    need(type(value) is dict, 'Expected a reference analysis object')
    return value['analysis'] if 'analysis' in value else value


def _init(args):
    need(1 <= len(args.image) <= MAX_REFERENCES, 'Supply one to four images; no extra image will be silently dropped')
    need(not args.role or len(args.role) == len(args.image), 'Supply one role per image, or omit all roles for auto')
    roles = args.role or ['auto'] * len(args.image); refs = []
    for index, (name, role) in enumerate(zip(args.image, roles)):
        path = safe_path(args.workspace, name)
        with path.open('rb') as stream: raw = stream.read(8 * 1024 * 1024 + 1)
        need(0 < len(raw) <= 8 * 1024 * 1024, 'Reference size limit exceeded')
        refs.append({'id': 'picture-%d' % (index + 1), 'path': name,
                     'sha256': hashlib.sha256(raw).hexdigest(), 'role_hint': role})
    return new_request(args.brief, refs)


def _inspect(args):
    from .recipe_intake import inspect_media
    q = validate_request(read_json(args.request))
    return {'format': 'studio.reference-metadata/v1', 'references': [
        {'reference_id': ref['id'], 'source_sha256': ref['sha256'],
         'inspection': inspect_media(file_bytes(args.workspace, ref, 8 * 1024 * 1024))}
        for ref in q['references']], 'generation_submitted': False,
        'note': 'Recovered metadata claims, not visual observations or authenticated generation history.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Inspect and describe one to four reference images without generating an asset.')
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('init', 'inspect', 'analyze', 'review', 'draft'):
        p = sub.add_parser(command); p.add_argument('--output', required=True, type=Path)
        if command != 'review': p.add_argument('--workspace', required=True, type=Path)
        if command == 'init':
            p.add_argument('--image', action='append', required=True, help='Portable workspace-relative image path; repeat in reference order')
            p.add_argument('--role', action='append', choices=('auto', *ROLE_FACETS))
            p.add_argument('--brief', default='', help='Short instruction; empty is supported')
        elif command in ('inspect', 'analyze'):
            p.add_argument('--request', required=True, type=Path)
            if command == 'analyze':
                p.add_argument('--model', required=True, help='Exact already-installed local vision model name')
                p.add_argument('--port', type=int, default=11434)
                p.add_argument('--idle-confirmed', action='store_true', help='Operator confirmation, NOT a global GPU reservation')
                p.add_argument('--no-cache', action='store_true')
        else:
            p.add_argument('--analysis', required=True, type=Path)
            if command == 'draft': p.add_argument('--review', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        # Avoid a model call when its requested output is already known to be unusable.
        need(not args.output.exists() and args.output.parent.is_dir(), 'Output must be a new file in an existing directory')
        if args.command == 'init': result = _init(args)
        elif args.command == 'inspect': result = _inspect(args)
        elif args.command == 'analyze':
            need(args.idle_confirmed, 'Confirm the GPU queue is idle before explicit local analysis')
            q = validate_request(read_json(args.request))
            result = local_helper.run_local(q, args.model, port=args.port, root=args.workspace,
                include_images=True, idle_confirmed=True, cache=not args.no_cache, operation='references')
        elif args.command == 'review': result = review_template(_report(args.analysis))
        else: result = draft(_report(args.analysis), read_json(args.review), args.workspace)
        write_new(args.output, result)
        print(json.dumps({'output': str(args.output), 'generation_submitted': False}))
        return 0
    except (ValueError, TypeError, KeyError, IndexError, OSError, HTTPException, RecursionError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        print('Reference assistant: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__': raise SystemExit(main())
