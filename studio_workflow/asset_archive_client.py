"""Reviewed, reversible Archive over the existing Workspace HTTP owner.

No automatic retries, revision refresh, metadata ownership, file moves or model
operations. Persist the preview before apply; unknown replies require recovery by
that same plan, not another request identity. See docs/workflow-studio/AGENT-ARCHIVE.md.
"""
from __future__ import annotations

import argparse
from http.client import HTTPException
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlencode

from . import asset_reads as contract
from .asset_read_client import AssetReadClient, _envelope, _number, _scope, _summary
from .client import Client, ClientError
from .core import MAX_BYTES, canonical, decode, digest, need

FORMAT = 'studio.asset-archive-plan/v1'
REQUEST_ID = {'type': 'string', 'pattern': r'^[A-Za-z0-9_-]{16,128}$', 'minLength': 16, 'maxLength': 128}
ACTION = {'type': 'string', 'maxLength': 9, 'enum': ['archive', 'unarchive']}
PLAN_TEXT = {'type': 'string', 'maxLength': MAX_BYTES,
             'description': 'The complete retained Archive preview JSON, including its plan_sha256. Never rebuild it after an unknown reply.'}


def _intent(action, request_id, privacy):
    need(type(action) is str and action in ('archive', 'unarchive'), 'Only archive or unarchive is supported')
    need(type(request_id) is str and re.fullmatch(REQUEST_ID['pattern'], request_id), 'Supply the original 16–128 character request identity')
    contract.privacy_scope(privacy)


def validate_plan(plan_json):
    """Validate retained review evidence without I/O; derive only its exact command."""
    need(type(plan_json) is str, 'Retained plan JSON text is required')
    plan = decode(plan_json)
    need(type(plan) is dict and set(plan) == {'format', 'request_id', 'action', 'privacy', 'selection', 'plan_sha256'},
         'Invalid Archive review document')
    need(plan['format'] == FORMAT, 'Unsupported Archive review format')
    _intent(plan['action'], plan['request_id'], plan['privacy'])
    need(contract._matches(contract.HEX64, plan['plan_sha256']), 'Invalid review hash')
    need(digest({k: v for k, v in plan.items() if k != 'plan_sha256'}) == plan['plan_sha256'], 'The retained Archive review changed')
    selection = plan['selection']
    _envelope(selection, 'selection', None, {'items'})
    items = selection['items']
    need(type(items) is list and 1 <= len(items) <= contract.MAX_SELECTION, 'Select 1–200 explicit assets')
    ids, revisions = [], {}
    for item in items:
        need(type(item) is dict and set(item) == {'id', 'state', 'asset'}, 'Invalid retained selection entry')
        need(item['asset'] is not None, 'A selected asset is missing or hidden; no partial plan is available')
        asset = _summary(item['asset'], plan['privacy'])
        need(item['id'] == asset['id'] and item['state'] == ('active' if asset['trashed_at'] is None else 'trashed'),
             'Retained selection identity or lifecycle disagrees')
        ids.append(item['id']); revisions[item['id']] = asset['metadata_revision']
    contract.selection_ids(ids)  # Validate uniqueness as well as bounded IDs.
    command = {'workspace_id': selection['workspace_id'], 'request_id': plan['request_id'],
               'ids': ids, 'action': plan['action'], 'expected_revisions': revisions}
    return plan, command


def _timestamp(value):
    return value is None or _number(value) and value >= 0


def _receipt(result, plan, command, *, allow_unknown=False):
    """Separate the immutable receipt from the owner's bounded current observation.

    Do not forward arbitrary response metadata as instructions or as an exhaustive
    current snapshot. The owner returns at most ten current rows; explicit IDs and
    revisions in the immutable receipt still cover every reviewed target.
    """
    need(type(result) is dict, 'Invalid Archive receipt')
    common = {'status', 'request_id', 'workspace_id', 'current'}
    need(result.get('workspace_id') == command['workspace_id'] and result.get('request_id') == command['request_id'],
         'Archive receipt belongs to another request or Workspace')
    if allow_unknown and result.get('status') == 'unknown':
        need(set(result) == common and result['current'] == [], 'Invalid unknown Archive observation')
        return {'format': 'studio.asset-archive-result/v1', 'privacy': plan['privacy'],
                'receipt': {k: result[k] for k in common - {'current'}}, 'current': [],
                'current_complete': False, 'generation_submitted': False, 'media_bytes_modified': False}
    required = common | {'updated', 'action', 'revisions', 'applied'}
    need(required <= set(result) <= required | {'unchanged'} and result['status'] == 'applied', 'Invalid applied Archive receipt')
    ids = command['ids']
    need(result['updated'] == ids and result['action'] == command['action'], 'Archive receipt does not describe the reviewed command')
    unchanged = result.get('unchanged', [])
    need(type(unchanged) is list and all(type(i) is str and i in ids for i in unchanged)
         and unchanged == [i for i in ids if i in unchanged], 'Invalid unchanged target list')
    expected_unchanged = [item['id'] for item in plan['selection']['items']
                          if ('archived_at' in item['asset']) == (command['action'] == 'archive')]
    need(unchanged == expected_unchanged, 'Archive no-op claims disagree with the reviewed lifecycle')
    revisions = result['revisions']
    need(type(revisions) is dict and set(revisions) == set(ids), 'Archive receipt lost target revisions')
    for i in ids:
        need(contract._integer(revisions[i]) and revisions[i] == command['expected_revisions'][i] + (i not in unchanged),
             'Archive receipt has an unexpected revision')
    changes = result['applied']
    need(type(changes) is dict, 'Invalid Archive changes')
    if len(unchanged) == len(ids):
        need(changes == {}, 'No-op Archive receipt claims changed fields')
    else:
        need(set(changes) == {'archived_at'} and _timestamp(changes['archived_at'])
             and (changes['archived_at'] is None) == (command['action'] == 'unarchive'), 'Archive receipt claims another mutation')
    current = result['current']
    need(type(current) is list and len(current) <= min(10, len(ids)), 'Invalid bounded current observation')
    projected, seen = [], set()
    for row in current:
        need(type(row) is dict and row.get('id') in ids[:10] and row['id'] not in seen,
             'Unexpected current Archive identity')
        identifier = row['id']; seen.add(identifier)
        need(row.get('workspace_id') == command['workspace_id'], 'Current metadata belongs to another Workspace')
        # The owner's metadata projection has no classification field. The
        # request/receipt scope and retained IDs bind access; never invent one.
        need('privacy' not in row or contract.privacy_matches(row['privacy'], plan['privacy']),
             'Current metadata belongs to another privacy scope')
        need(contract._integer(row.get('metadata_revision')) and row['metadata_revision'] >= revisions[identifier],
             'Current metadata predates the retained receipt')
        need('archived_at' in row and 'trashed_at' in row and _timestamp(row['archived_at']) and _timestamp(row['trashed_at']),
             'Current lifecycle metadata is unavailable')
        if row['metadata_revision'] == revisions[identifier]:
            reviewed = next(item['asset'] for item in plan['selection']['items'] if item['id'] == identifier)
            archived = reviewed.get('archived_at') if identifier in unchanged else changes['archived_at']
            need(row['archived_at'] == archived and row['trashed_at'] == reviewed['trashed_at'],
                 'Same-revision current lifecycle contradicts the reviewed receipt')
        projected.append({key: row[key] for key in ('id', 'metadata_revision', 'archived_at', 'trashed_at')})
    need([row['id'] for row in projected] == [i for i in ids[:10] if i in seen], 'Current observations are out of order')
    return {'format': 'studio.asset-archive-result/v1', 'privacy': plan['privacy'],
            'receipt': {k: v for k, v in result.items() if k != 'current'}, 'current': projected,
            'current_complete': len(projected) == len(ids), 'generation_submitted': False, 'media_bytes_modified': False}


class ArchiveOutcomeUnknown(ValueError):
    """A dispatched write lacks a valid acknowledgement; retain the original plan."""
    def __init__(self, plan):
        super().__init__('Archive may have completed. Recover the original plan; never automatically retry or create another request identity.')
        self.request_id = plan['request_id']
        self.workspace_id = plan['selection']['workspace_id']
        self.plan_sha256 = plan['plan_sha256']


class AssetArchiveClient(AssetReadClient):
    def preview(self, ids, *, workspace_id, request_id, action='archive', privacy='regular'):
        _intent(action, request_id, privacy)
        _scope(workspace_id); contract.selection_ids(ids)
        selection = self.selection(ids, workspace_id=workspace_id, privacy=privacy)
        plan = {'format': FORMAT, 'request_id': request_id, 'action': action, 'privacy': privacy, 'selection': selection}
        plan['plan_sha256'] = digest(plan)
        validate_plan(canonical(plan).decode('utf-8'))
        return plan

    def apply(self, plan_json, *, approved_plan_sha256):
        plan, command = validate_plan(plan_json)
        need(contract._matches(contract.HEX64, approved_plan_sha256) and approved_plan_sha256 == plan['plan_sha256'],
             'Approval must name the exact retained Archive plan SHA-256')
        try:
            result = self._observe('/api/assets/update', command, privacy=plan['privacy'])
            return _receipt(result, plan, command)
        except ClientError as exc:
            if 400 <= exc.status < 500: raise
            raise ArchiveOutcomeUnknown(plan) from exc
        except (ValueError, OSError, HTTPException, UnicodeError, KeyError, TypeError, RecursionError) as exc:
            raise ArchiveOutcomeUnknown(plan) from exc

    def recover(self, plan_json):
        plan, command = validate_plan(plan_json)
        result = self._observe('/api/assets/commands/' + command['request_id'] + '?' + urlencode({
            'workspace_id': command['workspace_id'], 'privacy': plan['privacy']}))
        return _receipt(result, plan, command, allow_unknown=True)


class ArchiveToolClient(AssetArchiveClient):
    """Share the bridge's raw transport; mark dispatch only after local validation."""
    def __init__(self, client, request_started):
        need(isinstance(client, Client), 'Archive requires the raw Studio Client transport')
        super().__init__(client.base, client.timeout)
        self.opener = client.opener
        self._request_started = request_started

    def _observe(self, path, body=None, *, privacy=None):
        if privacy is not None: contract.privacy_scope(privacy)
        self._request_started()
        return super()._observe(path, body, privacy=privacy)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8191')
    parser.add_argument('--timeout', type=float, default=30)
    commands = parser.add_subparsers(dest='operation', required=True)
    preview = commands.add_parser('preview', help='One read-only selection; retain stdout as the review document')
    preview.add_argument('--workspace-id', required=True)
    preview.add_argument('--request-id', required=True)
    preview.add_argument('--ids', nargs='+', required=True)
    preview.add_argument('--action', choices=('archive', 'unarchive'), default='archive')
    preview.add_argument('--privacy', choices=('regular', 'private', 'all'), default='regular')
    for name in ('apply', 'recover'):
        command = commands.add_parser(name)
        command.add_argument('--plan', required=True, help='Retained preview JSON file; no rewrite or automatic refresh')
        if name == 'apply': command.add_argument('--approved-plan-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        client = AssetArchiveClient(args.url, args.timeout)
        if args.operation == 'preview':
            result = client.preview(args.ids, workspace_id=args.workspace_id, request_id=args.request_id,
                                    action=args.action, privacy=args.privacy)
        else:
            with Path(args.plan).open('rb') as stream: raw = stream.read(MAX_BYTES + 1)
            need(len(raw) <= MAX_BYTES, 'Retained plan exceeds 1 MiB')
            text = raw.decode('utf-8')
            result = client.apply(text, approved_plan_sha256=args.approved_plan_sha256) if args.operation == 'apply' else client.recover(text)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)); return 0
    except ArchiveOutcomeUnknown as exc:
        print(json.dumps({'error': str(exc), 'code': 'outcome_unknown', 'request_id': exc.request_id,
                          'workspace_id': exc.workspace_id, 'plan_sha256': exc.plan_sha256}), file=sys.stderr); return 2
    except (ValueError, OSError, HTTPException, UnicodeError, RecursionError) as exc:
        print(json.dumps({'error': str(exc), 'code': getattr(exc, 'code', 'archive_failed')}), file=sys.stderr); return 2


if __name__ == '__main__': sys.exit(main())
