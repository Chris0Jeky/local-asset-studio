"""Typed, bounded catalogue observations using Studio's existing loopback transport.

Run ``python -m studio_workflow.asset_read_client --help``. No automatic next
page, refresh, retry, metadata write, media retrieval, or generation is performed.
"""
from __future__ import annotations

import argparse
import hashlib
from http.client import HTTPException
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

from . import asset_reads as contract
from .client import Client, ClientError, read_response
from .core import canonical

FLAGS = {'observation_only': True, 'generation_submitted': False, 'media_bytes_verified': False}
COMMON = {'format', 'workspace_id', 'catalogue', *FLAGS}
SUMMARY = {'id', 'sha256', 'media_type', 'review', 'preset_id', 'title', 'filename', 'preset_name',
           'bytes', 'metadata_revision', 'favorite', 'created_at', 'trashed_at', 'url', 'truncated_fields'}


def _need(value, message='Invalid or mismatched asset observation response'):
    if not value: raise ValueError(message)


def _json(raw):
    # The authoring decoder's 1 MiB cap is not the 2 MiB observation contract.
    # Use strict JSON under the transport cap, followed by the exact response schema.
    def pairs(items):
        result = {}
        for key, value in items:
            _need(key not in result, 'Duplicate JSON response key')
            result[key] = value
        return result
    def constant(_):
        raise ValueError('Non-finite JSON response value')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
        canonical(value)  # Reject non-finite numbers and unpaired Unicode surrogates.
        return value
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('Invalid asset response encoding or depth') from exc


def _scope(value):
    _need(contract._matches(contract.HEX32, value), 'Workspace identity must be 32 lowercase hexadecimal characters')
    return value


def _envelope(result, kind, scope, fields):
    _need(type(result) is dict and set(result) == COMMON | fields)
    _need(result['format'] == 'studio.asset-' + kind + '/v1')
    _scope(result['workspace_id'])
    _need(scope is None or result['workspace_id'] == scope, 'Response belongs to another Workspace')
    _need(all(result[key] is value for key, value in FLAGS.items()))
    stamp = result['catalogue']
    _need(type(stamp) is dict and set(stamp) == {'epoch', 'revision'}
          and contract._matches(contract.HEX32, stamp['epoch']) and contract._integer(stamp['revision']))


def _number(value):
    try:
        return contract._finite(value)
    except OverflowError:
        return False


def _summary(asset):
    _need(type(asset) is dict and set(asset) == SUMMARY)
    _need(contract._matches(contract.ENTITY, asset['id']) and contract._matches(contract.HEX64, asset['sha256']))
    _need(type(asset['media_type']) is str and 1 <= len(asset['media_type']) <= 32
          and type(asset['review']) is str and asset['review'] in contract.REVIEWS
          and type(asset['favorite']) is bool and contract._integer(asset['bytes'])
          and contract._integer(asset['metadata_revision']) and _number(asset['created_at'])
          and (asset['trashed_at'] is None or _number(asset['trashed_at']))
          and (asset['preset_id'] is None or contract._matches(contract.ENTITY, asset['preset_id'])))
    for field, maximum in contract.DISPLAY_LIMITS.items():
        text = asset[field]
        _need(field == 'preset_name' and text is None or type(text) is str and len(text) <= maximum)
    truncated = asset['truncated_fields']
    _need(type(truncated) is list and len(truncated) <= len(contract.DISPLAY_LIMITS)
          and all(type(field) is str and field in contract.DISPLAY_LIMITS for field in truncated)
          and len(set(truncated)) == len(truncated))
    _need(all(type(asset[field]) is str and len(asset[field]) == contract.DISPLAY_LIMITS[field]
              for field in truncated))
    _need(asset['url'] == '/api/assets/' + asset['id'] + '/file')
    return asset


class AssetReadClient(Client):
    """A thin strict client; current metadata commands remain separate APIs."""

    def _observe(self, path, body=None):
        raw = canonical(body) if body is not None else None
        request = Request(self.base + path, data=raw,
                          headers={'Origin': self.base, 'Content-Type': 'application/json', 'Accept': 'application/json'})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                _need(response.status == 200, 'Unexpected asset observation HTTP status')
                return _json(read_response(response, contract.MAX_RESPONSE_BYTES))
        except HTTPError as exc:
            with exc:
                raw = read_response(exc, 65536)
            try:
                result = _json(raw)
                _need(type(result) is dict and type(result.get('error')) is str)
                _need('code' not in result or type(result['code']) is str)
            except ValueError:
                result = {'error': 'Studio refused the asset observation', 'code': 'asset_read_http_error'}
            raise ClientError(exc.code, result) from exc

    def page(self, *, workspace_id=None, limit=50, cursor=None, filters=None):
        _need(contract._integer(limit, 1, contract.MAX_PAGE), 'Page size must be an integer between 1 and 100')
        query = contract.normalize_filters(filters)
        query_hash = hashlib.sha256(canonical(query)).hexdigest()
        position = contract._cursor(cursor) if cursor is not None else None
        if workspace_id is not None: _scope(workspace_id)
        if position is not None:
            _need(position['limit'] == limit and position['query_sha256'] == query_hash,
                  'Cursor belongs to different filters or page size')
            _need(workspace_id is None or workspace_id == position['workspace_id'], 'Cursor belongs to another Workspace')
            workspace_id = position['workspace_id']
        params = dict(query, workspace_id=workspace_id, limit=limit, cursor=cursor)
        params = {k: str(v).lower() if type(v) is bool else v for k, v in params.items() if v is not None}
        result = self._observe('/api/assets/page?' + urlencode(params))
        _envelope(result, 'page', workspace_id, {'assets', 'next_cursor', 'filters', 'limit', 'order'})
        _need(type(result['limit']) is int and result['limit'] == limit and result['order'] == contract.ORDER
              and type(result['filters']) is dict and set(result['filters']) == set(query)
              and canonical(result['filters']) == canonical(query))
        assets = result['assets']
        _need(type(assets) is list and len(assets) <= limit)
        seen, previous = set(), tuple(position['last']) if position is not None else None
        if position is not None: _need(result['catalogue'] == position['catalogue'], 'Continuation returned a changed catalogue')
        for asset in assets:
            _summary(asset)
            order = asset['created_at'], asset['id']
            _need(asset['id'] not in seen and (previous is None or order < previous), 'Assets are duplicated or out of order')
            seen.add(asset['id']); previous = order
            _need(query['visibility'] == 'all' or (asset['trashed_at'] is None) == (query['visibility'] == 'active'))
            for field in ('media_type', 'review', 'favorite'):
                _need(query[field] is None or asset[field] == query[field])
        next_cursor = result['next_cursor']
        if next_cursor is not None:
            next_position = contract._cursor(next_cursor)
            _need(len(assets) == limit and next_position['workspace_id'] == result['workspace_id']
                  and next_position['catalogue'] == result['catalogue'] and next_position['limit'] == limit
                  and next_position['query_sha256'] == query_hash and tuple(next_position['last']) == previous,
                  'Next cursor does not identify this page boundary')
        return result

    def selection(self, ids, *, workspace_id):
        ids = contract.selection_ids(ids); _scope(workspace_id)
        result = self._observe('/api/assets/selection', {'ids': ids, 'workspace_id': workspace_id})
        _envelope(result, 'selection', workspace_id, {'items'})
        items = result['items']
        _need(type(items) is list and len(items) == len(ids), 'Selection response lost retained IDs')
        for key, item in zip(ids, items):
            _need(type(item) is dict and set(item) == {'id', 'state', 'asset'} and item['id'] == key)
            if item['asset'] is None:
                _need(item['state'] == 'missing')
            else:
                asset = _summary(item['asset'])
                _need(asset['id'] == key and item['state'] == ('active' if asset['trashed_at'] is None else 'trashed'))
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='Inspect bounded Studio asset observations; no writes or automatic paging.')
    parser.add_argument('--url', default='http://127.0.0.1:8191')
    parser.add_argument('--timeout', type=float, default=30)
    sub = parser.add_subparsers(dest='command', required=True)
    page = sub.add_parser('page'); page.add_argument('--workspace-id'); page.add_argument('--limit', type=int, default=50)
    page.add_argument('--cursor'); page.add_argument('--visibility', choices=('active', 'trash', 'all'), default='active')
    page.add_argument('--media-type'); page.add_argument('--review', choices=contract.REVIEWS)
    page.add_argument('--favorite', choices=('true', 'false')); page.add_argument('--collection-id')
    selected = sub.add_parser('selection'); selected.add_argument('--workspace-id', required=True)
    selected.add_argument('ids', nargs='+')
    args = parser.parse_args(argv)
    try:
        client = AssetReadClient(args.url, timeout=args.timeout)
        if args.command == 'page':
            filters = {key: getattr(args, key) for key in contract.DEFAULT_FILTERS}
            if args.favorite is not None: filters['favorite'] = args.favorite == 'true'
            result = client.page(workspace_id=args.workspace_id, limit=args.limit, cursor=args.cursor, filters=filters)
        else:
            result = client.selection(args.ids, workspace_id=args.workspace_id)
        print(json.dumps(result, ensure_ascii=True, allow_nan=False))
        return 0
    except (ValueError, OSError, URLError, HTTPException) as exc:
        print(json.dumps({'error': str(exc), 'code': getattr(exc, 'code', 'asset_read_failed')}, ensure_ascii=True), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
