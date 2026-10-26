"""Read-only family/recall SDK and CLI over Studio's existing loopback client.

Example: python -m studio_workflow.asset_family_client inspect ASSET --workspace ID
The recall command returns an inspection envelope, not a runnable or approved job.
"""
from __future__ import annotations

import argparse
import json
from urllib.error import HTTPError

from .asset_family import _identity
from .asset_reads import HEX32, require, privacy_scope
from .client import Client


class FamilyClient:
    def __init__(self, client=None):
        self.client = client if client is not None else Client()

    def _read(self, action, asset_id, workspace_id, children=False, privacy='regular'):
        _identity(asset_id); _identity(workspace_id, HEX32)
        privacy_scope(privacy)
        require(type(children) is bool, 'Children must be true or false')
        path = '/api/assets/'+action+'/'+asset_id+'?workspace_id='+workspace_id
        if children: path += '&children=true'
        if privacy != 'regular': path += '&privacy='+privacy
        result = self.client.request(path)
        require(type(result) is dict and result.get('version') == 1
                and result.get('workspace_id') == workspace_id and result.get('asset_id') == asset_id
                and result.get('observation_only') is True and result.get('generation_submitted') is False
                and result.get('media_bytes_verified') is False, 'Invalid family response identity or authority')
        return result

    def inspect(self, asset_id, workspace_id, *, children=False, privacy='regular'):
        return self._read('family', asset_id, workspace_id, children, privacy)

    def recall(self, asset_id, workspace_id, *, privacy='regular'):
        return self._read('recall', asset_id, workspace_id, privacy=privacy)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Inspect retained asset families and recipes; never submit work')
    parser.add_argument('action', choices=('inspect', 'recall'))
    parser.add_argument('asset_id')
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--base', default='http://127.0.0.1:8191')
    parser.add_argument('--children', action='store_true')
    parser.add_argument('--privacy', choices=('regular','private','all'), default='regular')
    args = parser.parse_args(argv)
    try:
        require(args.action == 'inspect' or not args.children, 'Children apply only to family inspection')
        client = FamilyClient(Client(args.base, timeout=15))
        result = (client.inspect(args.asset_id, args.workspace, children=args.children, privacy=args.privacy) if args.action == 'inspect'
                  else client.recall(args.asset_id, args.workspace, privacy=args.privacy))
        text = json.dumps(result, allow_nan=False)
    except (ValueError, OSError) as exc:
        result = {'error': str(exc)[:500], 'code': getattr(exc, 'code', 'asset_family_unavailable'),
                  'observation_only': True, 'generation_submitted': False, 'media_bytes_verified': False}
        if isinstance(exc, HTTPError): result['status'] = exc.code; exc.close()
        print(json.dumps(result)); return 2
    print(text); return 0


if __name__ == '__main__':
    raise SystemExit(main())
