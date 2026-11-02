"""Lossless, offline intake of completed Deep Research exports; never verifies claims.

Raw sources may contain private conversation metadata. Keep archives outside Git or
under .runtime, not in the public research catalogue. No URL is fetched or opened.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from urllib.parse import urlsplit

from .core import MAX_BYTES, canonical, decode, need

FORMAT = 'studio.research-archive/v1'
MEMBERS = {'source.json', 'report.original.md', 'report.md', 'sources.json'}
REFERENCE = re.compile('\ue200(?:cite|filecite)\ue202[^\ue201]*\ue201')


def read_bytes(path: Path) -> bytes:
    need(not path.is_symlink() and path.is_file(), 'Expected a regular, non-symlink file')
    with path.open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    need(len(raw) <= MAX_BYTES, 'Archive member exceeds the 1 MiB limit')
    return raw


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _url(value):
    if not isinstance(value, str) or any(c.isspace() or c in '<>"\\' for c in value):
        return False
    try:
        url = urlsplit(value)
        return bool(url.scheme in {'https', 'http'} and url.hostname
                    and not url.username and not url.password)
    except ValueError:
        return False


def extract(document: dict) -> dict:
    """Derive a readable view, while retaining the exact original Markdown separately."""
    need(isinstance(document, dict), 'Expected a research export object')
    state = document.get('widget_state', {})
    need(isinstance(state, dict) and state.get('status') == 'completed', 'Report is not completed')
    message = state.get('report_message', {})
    need(isinstance(message, dict), 'Missing report message')
    content = message.get('content', {})
    need(isinstance(content, dict) and content.get('content_type') == 'text', 'Expected text report')
    parts = content.get('parts')
    need(isinstance(parts, list) and len(parts) == 1 and isinstance(parts[0], str)
         and parts[0].strip(), 'Expected one complete report text part')
    original = parts[0]
    metadata = message.get('metadata', {})
    need(isinstance(metadata, dict), 'Invalid report metadata')
    references = metadata.get('content_references', [])
    need(isinstance(references, list) and len(references) <= 4096, 'Invalid reference list')
    links, replacements = {}, {}
    for reference in references:
        need(isinstance(reference, dict), 'Invalid reference')
        token = reference.get('matched_text')
        if not isinstance(token, str) or not REFERENCE.fullmatch(token):
            continue
        # File-reference tokens remain unresolved rather than inventing a public URL.
        if reference.get('type') != 'grouped_webpages':
            continue
        items = reference.get('items', [])
        need(isinstance(items, list), 'Invalid web reference items')
        urls = []
        for item in items:
            need(isinstance(item, dict), 'Invalid web reference item')
            supporting = item.get('supporting_websites', [])
            need(isinstance(supporting, list), 'Invalid supporting sources')
            for page in [item, *supporting]:
                need(isinstance(page, dict), 'Invalid supporting source')
                url = page.get('url')
                if _url(url):
                    if url not in links:
                        links[url] = {'id': len(links) + 1, 'url': url,
                                      'title': str(page.get('title') or url),
                                      'status': 'reported_source_not_reverified'}
                    if url not in urls:
                        urls.append(url)
        if urls:
            replacement = ' '.join(f'[source {links[u]["id"]}](<{u}>)' for u in urls)
            need(token not in replacements or replacements[token] == replacement,
                 'Conflicting mappings for one citation token')
            replacements[token] = replacement
    linked = REFERENCE.sub(lambda match: replacements.get(match[0], match[0]), original)
    unresolved = sorted(set(REFERENCE.findall(linked)))
    return {'title': str(document.get('title') or 'Untitled research'),
            'original_markdown': original, 'linked_markdown': linked,
            'sources': list(links.values()), 'unresolved_references': unresolved}


def import_report(source: Path, destination: Path) -> dict:
    raw = read_bytes(source)
    result = extract(decode(raw))
    files = {'source.json': raw,
             'report.original.md': result['original_markdown'].encode('utf-8'),
             'report.md': result['linked_markdown'].encode('utf-8'),
             'sources.json': canonical(result['sources']) + b'\n'}
    need(all(len(data) <= MAX_BYTES for data in files.values()), 'Derived archive exceeds member limit')
    manifest = {'format': FORMAT, 'title': result['title'], 'visibility': 'private_local',
                'claims_independently_verified': False,
                'unresolved_references': result['unresolved_references'],
                'files': {name: {'sha256': sha(data), 'bytes': len(data)} for name, data in files.items()},
                'notice': 'Hashes identify bytes, not truth or permission. No source URL was fetched.'}
    destination.mkdir(exist_ok=False)  # Caller must explicitly select an existing parent.
    # manifest.json is the completion marker. A failed write leaves an incomplete,
    # never-reused directory; it cannot pass verify_archive.
    for name, data in files.items():
        with (destination / name).open('xb') as stream:
            stream.write(data)
    with (destination / 'manifest.json').open('xb') as stream:
        stream.write(canonical(manifest) + b'\n')
    return manifest


def verify_archive(directory: Path) -> dict:
    need(not directory.is_symlink() and directory.is_dir(), 'Expected an archive directory')
    manifest = decode(read_bytes(directory / 'manifest.json'))
    need(isinstance(manifest, dict) and manifest.get('format') == FORMAT, 'Unknown archive format')
    need(manifest.get('claims_independently_verified') is False
         and manifest.get('visibility') == 'private_local', 'Archive cannot promote source evidence')
    files = manifest.get('files')
    need(isinstance(files, dict) and set(files) == MEMBERS, 'Unexpected archive member paths')
    for name, record in files.items():
        need(isinstance(record, dict), 'Invalid archive member record')
        raw = read_bytes(directory / name)
        need(record.get('sha256') == sha(raw) and type(record.get('bytes')) is int
             and record['bytes'] == len(raw), f'Archive hash/size mismatch: {name}')
    # Also check derivation. A self-consistent edited manifest cannot silently
    # relabel a different readable text as an extraction of the retained source.
    derived = extract(decode(read_bytes(directory / 'source.json')))
    need(manifest.get('title') == derived['title']
         and manifest.get('unresolved_references') == derived['unresolved_references'],
         'Archive metadata differs from retained source')
    need(read_bytes(directory / 'report.original.md') == derived['original_markdown'].encode()
         and read_bytes(directory / 'report.md') == derived['linked_markdown'].encode()
         and decode(read_bytes(directory / 'sources.json')) == derived['sources'],
         'Archive derivation mismatch')
    return {'format': FORMAT, 'status': 'intact', 'source_sha256': files['source.json']['sha256'],
            'claims_independently_verified': False, 'members': len(files)}
