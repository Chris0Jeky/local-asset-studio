"""Bounded, opt-in synthetic metadata benchmark; never reads user media."""
import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path

from test_workspace import workspace


def populate(store, assets, collections, memberships):
    with store.connection() as db:
        db.executemany('INSERT INTO collections (id,name,created_at) VALUES (?,?,?)',
                       [(f'c{i}', f'Collection {i:04}', i) for i in range(collections)])
        db.executemany('''INSERT INTO assets
            (id,job_id,output_index,title,media_type,path,filename,sha256,bytes,created_at,source,trashed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            [(f'a{i}', f'job{i}', 0, f'Asset {i}', 'image', 'media/synthetic.png', 'synthetic.png',
              '0'*64, 1, i, '{}', 123 if i % 7 == 0 else None) for i in range(assets)])
        db.executemany('INSERT INTO collection_assets (collection_id,asset_id) VALUES (?,?)',
                       [(f'c{(i+j)%collections}', f'a{i}') for i in range(assets) for j in range(memberships)])


def benchmark(assets=10000, collections=200, memberships=4, runs=5):
    if not (1 <= assets <= 10000 and 1 <= collections <= 1000 and
            1 <= memberships <= min(collections, 20) and 1 <= runs <= 10):
        raise ValueError('Use 1..10000 assets, 1..1000 collections, 1..20 memberships and 1..10 runs')
    with tempfile.TemporaryDirectory() as folder:
        store = workspace.AssetWorkspace(folder)
        populate(store, assets, collections, memberships)
        store.snapshot()  # One disclosed warm-up; no model execution.
        seconds = []
        for _ in range(runs):
            start = time.perf_counter()
            result = store.snapshot()
            seconds.append(time.perf_counter() - start)
        return {'assets': assets, 'collections': collections, 'memberships': assets*memberships,
                'runs': runs, 'warmups': 1, 'seconds': seconds, 'median_seconds': statistics.median(seconds),
                'snapshot_bytes': len(json.dumps(result).encode('utf-8')),
                'live_membership_count': sum(c['count'] for c in result['collections'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=int, default=10000)
    parser.add_argument('--collections', type=int, default=200)
    parser.add_argument('--memberships', type=int, default=4)
    parser.add_argument('--runs', type=int, default=5)
    print(json.dumps(benchmark(**vars(parser.parse_args())), indent=2))
