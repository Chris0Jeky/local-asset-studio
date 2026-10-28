"""One bounded collection observation through the existing Studio HTTP owner.

No automatic continuation, refresh, retry, media reads or metadata writes.
Run ``python -m studio_workflow.collection_read_client --help``.
"""
from __future__ import annotations

import argparse
from http.client import HTTPException
import json
import sys
from urllib.parse import urlencode

from . import asset_reads as contract
from .asset_read_client import AssetReadClient, FLAGS, _need, _scope
from .collection_http import collection_cursor

FIELDS = {'format', 'workspace_id', 'catalogue', 'limit', 'order',
          'collections', 'next_cursor', *FLAGS}
ITEM = {'id', 'name', 'description', 'revision', 'count'}
ASCII_LOWER = str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')


def _order(name, identity):
    # SQLite NOCASE folds only ASCII and stops comparison at NUL; equal
    # prefixes are then ordered by full UTF-8 byte length, followed by ID.
    # Tests compare actual SQLite ordering and every returned page boundary.
    return name.split('\0', 1)[0].translate(ASCII_LOWER).encode('utf-8'), len(name.encode('utf-8')), identity


class CollectionReadClient(AssetReadClient):
    """Reuse the strict bounded transport; retain the collection owner's schema."""

    def page(self, *, workspace_id=None, limit=50, cursor=None, privacy='regular'):
        _need(contract._integer(limit, 1, 100), 'Page size must be an integer between 1 and 100')
        contract.privacy_scope(privacy)
        if workspace_id is not None: _scope(workspace_id)
        position = collection_cursor(cursor) if cursor is not None else None
        if position is not None:
            _need(position['limit'] == limit and position.get('privacy', 'regular') == privacy,
                  'Collection cursor belongs to another privacy scope or page size')
            _need(workspace_id is None or workspace_id == position['workspace_id'],
                  'Collection cursor belongs to another Workspace')
            workspace_id = position['workspace_id']
        params = {'limit': limit}
        if workspace_id is not None: params['workspace_id'] = workspace_id
        if cursor is not None: params['cursor'] = cursor
        if privacy != 'regular': params['privacy'] = privacy
        result = self._observe('/api/collections?' + urlencode(params))
        _need(type(result) is dict and set(result) == FIELDS, 'Invalid collection observation shape')
        _need(result['format'] == 'studio.collection-page/v1' and result['order'] == 'name_nocase_asc_id_asc')
        _scope(result['workspace_id'])
        _need(workspace_id is None or result['workspace_id'] == workspace_id, 'Response belongs to another Workspace')
        _need(type(result['limit']) is int and result['limit'] == limit)
        _need(all(result[key] is value for key, value in FLAGS.items()))
        stamp = result['catalogue']
        _need(type(stamp) is dict and set(stamp) == {'epoch', 'revision'}
              and contract._matches(contract.HEX32, stamp['epoch']) and contract._integer(stamp['revision']))
        if position is not None:
            _need(stamp == position['catalogue'], 'Continuation returned a changed collection catalogue')
        items = result['collections']
        _need(type(items) is list and len(items) <= limit)
        seen = set()
        previous = _order(*position['last']) if position is not None else None
        for item in items:
            _need(type(item) is dict and set(item) in (ITEM, ITEM | {'privacy'}))
            _need(contract.privacy_matches(item.get('privacy', 'regular'), privacy),
                  'Collection response belongs to another privacy scope')
            _need(contract._matches(contract.ENTITY, item['id']) and type(item['name']) is str
                  and 0 < len(item['name']) <= 100 and type(item['description']) is str
                  and len(item['description']) <= 1000 and contract._integer(item['revision'], 1)
                  and contract._integer(item['count']))
            order = _order(item['name'], item['id'])
            _need(item['id'] not in seen and (previous is None or order > previous),
                  'Collections are duplicated or out of order')
            seen.add(item['id']); previous = order
        next_cursor = result['next_cursor']
        if next_cursor is not None:
            following = collection_cursor(next_cursor)
            _need(len(items) == limit and following['workspace_id'] == result['workspace_id']
                  and following['catalogue'] == stamp and following['limit'] == limit
                  and following.get('privacy', 'regular') == privacy
                  and following['last'] == [items[-1]['name'], items[-1]['id']],
                  'Next collection cursor does not identify this page boundary')
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='Observe one collection page; no writes, media reads or automatic paging.')
    parser.add_argument('--url', default='http://127.0.0.1:8191')
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--workspace-id')
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--cursor')
    parser.add_argument('--privacy', choices=('regular', 'private', 'all'), default='regular')
    args = parser.parse_args(argv)
    try:
        result = CollectionReadClient(args.url, timeout=args.timeout).page(
            workspace_id=args.workspace_id, limit=args.limit, cursor=args.cursor, privacy=args.privacy)
        print(json.dumps(result, ensure_ascii=True, allow_nan=False))
        return 0
    except (ValueError, OSError, HTTPException) as exc:
        print(json.dumps({'error': str(exc), 'code': getattr(exc, 'code', 'collection_read_failed')},
                         ensure_ascii=True), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
