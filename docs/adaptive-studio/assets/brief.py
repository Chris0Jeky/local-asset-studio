"""Read/validate planned asset requests and print provider-neutral text briefs.

Standard library only. This tool cannot acquire, generate or register media.
Run: python docs/adaptive-studio/assets/brief.py show retro-anime-master
"""
import argparse
from collections import Counter
import csv
import io
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
FIELDS = ('id', 'pack', 'category', 'placement', 'profile', 'wave', 'method', 'anchor', 'subject', 'acceptance')
METHODS = {'generate', 'edit', 'derive', 'animate', 'source', 'vector', 'code', 'capture', 'audio'}


def validate(rows, config):
    if config.get('version') != 1 or config.get('production_status') != 'planned' or config.get('asset_bytes_present') is not False:
        raise ValueError('This catalogue must remain planned; actual media belongs in separate receipts')
    worlds, profiles = config.get('worlds', {}), config.get('profiles', {})
    if not isinstance(worlds, dict) or not isinstance(profiles, dict) or not worlds or not profiles:
        raise ValueError('World and delivery profiles are required')
    for name, description in worlds.items():
        if not isinstance(description, str) or not description.strip() or len(description) > 2000:
            raise ValueError(f'Invalid world description: {name}')
    for name, p in profiles.items():
        if not isinstance(p, dict) or any(not isinstance(p.get(k), str) or not p[k].strip() for k in ('master','safe_zone','fallback','budget','motion')):
            raise ValueError(f'Incomplete profile: {name}')
        if not isinstance(p.get('deliverables'), list) or not p['deliverables'] or any(not isinstance(x, str) or not x.strip() for x in p['deliverables']):
            raise ValueError(f'Incomplete deliverables: {name}')
    by_id = {}
    for row in rows:
        if set(row) != set(FIELDS) or any(not isinstance(row[k], str) or len(row[k]) > 2000 for k in FIELDS):
            raise ValueError('Unexpected catalogue fields or oversized text')
        if any(not row[k].strip() for k in FIELDS if k != 'anchor') or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', row['id']):
            raise ValueError('Invalid or incomplete asset request')
        if row['id'] in by_id:
            raise ValueError(f'Duplicate asset: {row["id"]}')
        if row['pack'] not in worlds or row['profile'] not in profiles or row['wave'] not in {'P0','P1','P2','P3'} or row['method'] not in METHODS:
            raise ValueError(f'Unknown world/profile/wave/method: {row["id"]}')
        by_id[row['id']] = row
    for row in rows:
        seen = set()
        current = row
        while current['anchor']:
            if current['id'] in seen:
                raise ValueError(f'Anchor dependency cycle: {row["id"]}')
            seen.add(current['id'])
            if current['anchor'] not in by_id:
                raise ValueError(f'Unknown anchor: {current["anchor"]}')
            current = by_id[current['anchor']]
    return rows, config


def load():
    text = (ROOT/'catalog.csv').read_text(encoding='utf-8')
    raw = (ROOT/'profiles.json').read_text(encoding='utf-8')
    if len(text.encode('utf-8')) > 1048576 or len(raw.encode('utf-8')) > 65536:
        raise ValueError('Planning files exceed the reader limit')
    reader = csv.DictReader(io.StringIO(text))
    if tuple(reader.fieldnames or ()) != FIELDS:
        raise ValueError('Unexpected catalogue header')
    return validate(list(reader), json.loads(raw))


def render(asset_id, rows, config):
    row = next((r for r in rows if r['id'] == asset_id), None)
    if row is None:
        raise ValueError(f'Unknown asset: {asset_id}')
    profile = config['profiles'][row['profile']]
    by_id = {r['id']: r for r in rows}
    anchors = []
    current = row
    while current['anchor']:
        anchors.append(current['anchor'])
        current = by_id[current['anchor']]
    mode = {
        'code': 'Do not use an image generator. Implement the specified semantic component or motion token in a separately authorized implementation session.',
        'vector': 'Use editable vector/design or code tools. Do not use an image generator for functional labels, icons, controls or text.',
        'capture': 'Record the real UI only after the workflow exists. Use a public/synthetic fixture and retain the application commit; no generated fake screen demonstration.',
        'source': 'Use a semantic stock search or reviewed original library. Inspect exact source terms and retain attribution before selecting a candidate.',
        'derive': 'Derive from the approved anchor; crop, encode or composite rather than inventing a new unrelated scene.',
        'edit': 'Edit the approved anchor to preserve its camera, proportions and visual canon. Inspect masks, alpha and registration manually.',
        'animate': 'Animate the approved still in a future video-capable tool. Keep the camera fixed and retain a matching local poster.',
        'audio': 'Use a future audio-capable tool or reviewed original source. No audio generation or playback is performed by this brief.',
        'generate': 'Use the future session\'s actually available native image tool, with an explicit finite candidate count. Record its reported provider/model identity; do not invent an API model name.'
    }[row['method']]
    return '\n'.join([
        f'# {asset_id}', 'PLANNED / NOT PRODUCED', '',
        f'Selection: {row["wave"]} | {row["category"]} | {row["placement"]} | method: {row["method"]}',
        'No generation, acquisition or publication is authorized by running this reader.', '',
        '## Art direction', config['worlds'][row['pack']], '',
        '## Individual brief', row['subject'], '',
        '## Prerequisites', 'Approved anchors, nearest first: '+', '.join(anchors) if anchors else 'No asset anchor. Agree on a small candidate batch before production.', '',
        '## Production route', mode, '',
        '## Delivery target', profile['master'], '',
        '## Deliverables', *('- '+x for x in profile['deliverables']), '',
        '## Composition and accessibility', profile['safe_zone'], profile['motion'], '',
        '## Runtime fallback and budget', profile['fallback'], profile['budget'], '',
        '## Acceptance', row['acceptance'],
        'Inspect actual bytes, crop, alpha, dimensions and seams; record produced, source-reviewed, art-accepted and runtime-qualified separately.',
        'No baked UI copy, fake readiness, brand logos or copied characters. Do not infer route/model capability from example artwork.', '',
        '## Handoff', 'Read SESSION-HANDOFF.md and DELIVERY-SPEC.md. Return a completed receipt derived from actual tool output, not this planned request.', ''
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('validate', 'list', 'show'))
    parser.add_argument('asset_id', nargs='?')
    args = parser.parse_args()
    try:
        rows, config = load()
        if args.command == 'show':
            if not args.asset_id:
                parser.error('show requires an asset ID')
            print(render(args.asset_id, rows, config))
        elif args.command == 'list':
            for row in rows:
                print(f'{row["wave"]}\t{row["id"]}\t{row["method"]}\t{row["subject"]}')
        else:
            print(json.dumps({'planned_requests':len(rows), 'categories':dict(Counter(r['category'] for r in rows)), 'waves':dict(Counter(r['wave'] for r in rows)), 'asset_bytes_present':False}, indent=2))
    except (OSError, ValueError, csv.Error) as exc:
        print(f'Asset brief error: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
