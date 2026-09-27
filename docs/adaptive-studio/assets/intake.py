"""Bring owner-made candidates and downloaded free assets into the asset kit, with receipts.

  receipts  hash every image in inbox/ and write receipts/<file-stem>.json from receipt-template.json
  verify    check that every acquired/MANIFEST.json entry is present with its recorded sha256
  fetch     download missing acquired/ entries from their pinned URL and keep only bytes whose sha256 matches

Standard library only. `receipts` reads inbox/ and writes only receipts/; `fetch` writes only acquired/.
Nothing here generates, judges or publishes art, and no downloaded file is executed or opened beyond
reading one named member out of a zip archive. A receipt records bytes, not art acceptance.
Run: python docs/adaptive-studio/assets/intake.py receipts
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import sys
from urllib.parse import urlparse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp'}
NAME = re.compile(r'(?P<id>[a-z0-9]+(?:-[a-z0-9]+)*)--(?:(?P<w>\d+)x(?P<h>\d+)--)?candidate-(?P<n>\d+)')
PART = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*')
LICENCES = {'CC0-1.0', 'MIT', 'OFL-1.1', 'Apache-2.0'}
FETCH_HOSTS = {'raw.githubusercontent.com', 'dl.polyhaven.org', 'ambientcg.com'}
MAX_DOWNLOAD = 32 * 1024 * 1024


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def image_info(data):
    """(format, width, height, alpha) read from the file header; alpha is None when the format cannot say."""
    if data[:8] == b'\x89PNG\r\n\x1a\n' and data[12:16] == b'IHDR':
        width, height = struct.unpack('>II', data[16:24])
        return 'png', width, height, data[25] in (4, 6)
    if data[:2] == b'\xff\xd8':
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            length = struct.unpack('>H', data[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height, width = struct.unpack('>HH', data[i + 5:i + 9])
                return 'jpeg', width, height, False
            i += 2 + length
        raise ValueError('JPEG without a frame header')
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        chunk = data[12:16]
        if chunk == b'VP8X':
            return 'webp', 1 + int.from_bytes(data[24:27], 'little'), 1 + int.from_bytes(data[27:30], 'little'), bool(data[20] & 0x10)
        if chunk == b'VP8L':
            bits = int.from_bytes(data[21:25], 'little')
            return 'webp', 1 + (bits & 0x3FFF), 1 + ((bits >> 14) & 0x3FFF), bool((bits >> 28) & 1)
        if chunk == b'VP8 ':
            width, height = struct.unpack('<HH', data[26:30])
            return 'webp', width & 0x3FFF, height & 0x3FFF, False
    raise ValueError('not a PNG, JPEG or WebP file')


def catalogue(root):
    with (root / 'catalog.csv').open(encoding='utf-8', newline='') as handle:
        return {row['id']: row for row in csv.DictReader(handle)}


def prompt_block(root, asset_id):
    """The exact prompt-pack section for an ID, so a receipt names the prompt text it answered."""
    path = root / 'CHATGPT-PROMPT-PACK.md'
    if not path.is_file():
        return None
    match = re.search(r'^### `?' + re.escape(asset_id) + r'`?[ \t]*\n(.*?)(?=^##)', path.read_text(encoding='utf-8') + '\n##', re.M | re.S)
    return match.group(0) if match else None


def receipt_for(root, path, rows, template, now):
    data = path.read_bytes()
    match = NAME.fullmatch(path.stem)
    if not match:
        raise ValueError(f'{path.name}: expected <asset-id>--<w>x<h>--candidate-<n>{path.suffix}')
    row = rows.get(match['id'])
    if row is None:
        raise ValueError(f'{path.name}: {match["id"]} is not a catalogue ID')
    fmt, width, height, alpha = image_info(data)
    unknowns = ['The tool does not expose its model build; "Image 2.5" is the owner\'s route label, not a verified model ID.',
                'produced_at is unknown: the file time is when it was saved, not when it was generated.']
    if match['w'] and (int(match['w']), int(match['h'])) != (width, height):
        unknowns.append(f'The file name says {match["w"]}x{match["h"]}; the header says {width}x{height}. The header is recorded.')
    block = prompt_block(root, match['id'])
    receipt = json.loads(json.dumps(template))
    receipt.pop('file_entry_instructions', None)
    receipt['status'] = 'candidate-produced'
    receipt['requested_asset_id'] = match['id']
    receipt['brief_revision'] = ('CHATGPT-PROMPT-PACK.md section sha256:' + sha256(block.encode('utf-8'))) if block else None
    if not block:
        unknowns.append('No CHATGPT-PROMPT-PACK.md section exists for this ID; the prompt used is unrecorded.')
    receipt['production'].update({
        'method': row['method'], 'provider': 'ChatGPT (owner-run native image tool)', 'tool_action': 'edit with uploaded anchor' if row['anchor'] else 'generate',
        'reported_model': None, 'output_id': None, 'produced_at': None, 'prompt_record': f'CHATGPT-PROMPT-PACK.md#{match["id"]}' if block else None,
        'input_anchors': [{'asset_id': row['anchor'], 'sha256': None, 'note': 'Add the uploaded anchor file hash when known.'}] if row['anchor'] else []})
    receipt['intake'] = {'received_at': now, 'candidate': int(match['n'])}
    receipt['files'] = [{'relative_path': path.relative_to(root).as_posix(), 'sha256': sha256(data), 'bytes': len(data),
                         'width': width, 'height': height, 'format': fmt, 'alpha': alpha, 'duration_seconds': None, 'codec': None}]
    receipt['unknowns'] = unknowns
    return receipt


def receipts(root, now=None):
    now = now or datetime.now(timezone.utc).isoformat(timespec='seconds')
    inbox, out = root / 'inbox', root / 'receipts'
    if not inbox.is_dir():
        print(f'No inbox yet: create {inbox} and drop candidates into it.')
        return 0
    rows = catalogue(root)
    template = json.loads((root / 'receipt-template.json').read_text(encoding='utf-8'))
    failed = 0
    for path in sorted(p for p in inbox.iterdir() if p.is_file()):
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            print(f'skip     {path.name} (not an image)')
            continue
        try:
            receipt = receipt_for(root, path, rows, template, now)
        except (OSError, ValueError, struct.error) as exc:
            print(f'error    {exc}', file=sys.stderr)
            failed += 1
            continue
        target = out / (path.stem + '.json')
        digest = receipt['files'][0]['sha256']
        if target.is_file():
            old = json.loads(target.read_text(encoding='utf-8'))
            if old.get('files') and old['files'][0].get('sha256') == digest:
                print(f'same     {path.name}')
            else:
                print(f'error    {path.name}: a different file already has receipt {target.name}; save it as a new candidate number', file=sys.stderr)
                failed += 1
            continue
        out.mkdir(exist_ok=True)
        target.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        f = receipt['files'][0]
        print(f'receipt  {path.name} -> receipts/{target.name} ({f["width"]}x{f["height"]} {f["format"]}, {f["bytes"]} bytes)')
    return 2 if failed else 0


def manifest(root):
    data = json.loads((root / 'acquired' / 'MANIFEST.json').read_text(encoding='utf-8'))
    if data.get('version') != 1 or not isinstance(data.get('entries'), list):
        raise ValueError('acquired/MANIFEST.json must be version 1 with entries')
    for entry in data['entries']:
        parts = str(entry.get('file', '')).split('/')
        if not all(PART.fullmatch(p) and p not in ('.', '..') for p in parts):
            raise ValueError(f'Manifest file is not a plain relative path: {entry.get("file")!r}')
        if entry.get('licence') not in LICENCES or not re.fullmatch('[a-f0-9]{64}', str(entry.get('sha256', ''))):
            raise ValueError(f'Manifest entry needs an allowed licence and a sha256: {entry.get("file")}')
        if not isinstance(entry.get('bytes'), int) or entry['bytes'] <= 0 or not str(entry.get('url', '')).startswith('https://'):
            raise ValueError(f'Manifest entry needs a byte count and an https URL: {entry["file"]}')
    return data


def verify(root):
    counts = {'ok': 0, 'missing': 0, 'corrupt': 0}
    for entry in manifest(root)['entries']:
        path = root / 'acquired' / entry['file']
        state = 'missing' if not path.is_file() else 'ok' if sha256(path.read_bytes()) == entry['sha256'] else 'corrupt'
        counts[state] += 1
        if state != 'ok':
            print(f'{state:8} {entry["file"]}')
    print(f'acquired: {counts["ok"]} ok, {counts["missing"]} missing, {counts["corrupt"]} corrupt')
    return 0 if counts['ok'] == sum(counts.values()) else 1


def download(url):
    if urlparse(url).hostname not in FETCH_HOSTS:
        raise ValueError(f'host not allow-listed: {url}')
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'local-asset-studio-intake'}), timeout=60) as response:
        data = response.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise ValueError(f'download exceeds {MAX_DOWNLOAD} bytes: {url}')
    return data


def fetch(root):
    failed = 0
    for entry in manifest(root)['entries']:
        path = root / 'acquired' / entry['file']
        if path.is_file() and sha256(path.read_bytes()) == entry['sha256']:
            continue
        try:
            data = download(entry['url'])
            member = (entry.get('archive') or {}).get('member')
            if member:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    data = archive.read(member)
            if sha256(data) != entry['sha256']:
                raise ValueError('sha256 differs from the manifest; the upstream file changed, nothing was written')
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            print(f'error    {entry["file"]}: {exc}', file=sys.stderr)
            failed += 1
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f'fetched  {entry["file"]} ({len(data)} bytes)')
    return 2 if failed else verify(root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=('receipts', 'verify', 'fetch'))
    args = parser.parse_args(argv)
    try:
        return {'receipts': receipts, 'verify': verify, 'fetch': fetch}[args.command](ROOT)
    except (OSError, ValueError, KeyError) as exc:
        print(f'Asset intake error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
