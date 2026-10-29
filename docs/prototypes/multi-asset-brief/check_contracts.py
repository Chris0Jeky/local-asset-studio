"""Check the fictional observations with production readers; no network or runtime."""
import copy
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from studio_workflow.asset_read_client import AssetReadClient
from studio_workflow.collection_read_client import CollectionReadClient


def main():
    script = "import {collectionPage,assetPage,routes} from './fixtures.mjs'; console.log(JSON.stringify({collectionPage,assetPage,routes}));"
    fixture = json.loads(subprocess.check_output(['node', '--input-type=module', '-e', script], cwd=HERE, text=True, encoding='utf-8'))
    calls = []
    for cls, key in [(CollectionReadClient, 'collectionPage'), (AssetReadClient, 'assetPage')]:
        page = fixture[key]
        client = cls()
        # Exercise the real reply validator without opening any transport.
        def observe(path, body=None):
            calls.append((path, body))
            return copy.deepcopy(page)
        client._observe = observe
        options = dict(workspace_id=page['workspace_id'], limit=25)
        if key == 'assetPage':
            options['filters'] = {'collection_id': 'lantern-marsh'}
        assert client.page(**options) == page
        changed = copy.deepcopy(page)
        page['workspace_id'] = 'c' * 32
        try:
            client.page(**options)
        except ValueError:
            pass
        else:
            raise AssertionError('The production reader accepted a foreign Workspace')
        page.update(changed)
    assert all(body is None for _, body in calls)
    looks = json.loads((ROOT / 'presets/looks.json').read_text(encoding='utf-8'))
    look_records = next(v for v in looks.values() if isinstance(v, list))
    look_ids = {item['id'] for item in look_records}
    presets = {p['id']: p for p in json.loads((ROOT / 'presets/catalog.json').read_text(encoding='utf-8'))['presets']}
    for route in fixture['routes'].values():
        if 'lookId' in route:
            assert route['lookId'] in look_ids
        if 'presetId' in route:
            assert route['presetId'] in presets
    assert presets['h3-preview']['modality'] == 'video'
    assert presets['trellis-rgba']['modality'] == '3d'
    assert presets['hunyuan-draft']['modality'] == '3d'
    assert fixture['collectionPage']['collections'][0]['count'] == len(fixture['assetPage']['assets'])
    print('PASS production collection/asset reply validators, foreign-Workspace refusal, catalogue identities and media kinds; zero transport calls.')


if __name__ == '__main__':
    main()
