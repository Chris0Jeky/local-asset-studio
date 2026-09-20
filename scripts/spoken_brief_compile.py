#!/usr/bin/env python3
"""Compile one Markdown handoff into deterministic bounded voice batches."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

SCHEMA_VERSION = 2
COMPILER_VERSION = 2
MAX_SOURCE_BYTES = 512 * 1024
TARGET_LINE_CHARS = 320
MAX_LINE_CHARS = 520
MAX_BATCH_LINES = 6
MAX_BATCH_CHARS = 1500
MAX_BATCH_WORDS = 210
MAX_SEGMENTS = 240
MAX_NARRATED_CHARS = 100000
DEFAULT_PAUSE_MS = 220
SECTION_PAUSE_MS = 650
ACTIVE_STATUSES = {'queued', 'running', 'observing'}
SPEAKER_RE = re.compile(r'[a-z][a-z0-9_-]{0,63}\Z')
URL_RE = re.compile(r'https?://[^\s<>()]+', re.I)
LINK_RE = re.compile(r'!?(\[[^\]]*\])\((?:[^()]+|\([^)]*\))*\)')


class SpokenBriefError(ValueError):
    pass


class StudioRejected(SpokenBriefError):
    pass


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_digest(value) -> str:
    return digest_bytes(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))


def resolve_source(pack) -> Path:
    path = Path(pack).expanduser().resolve()
    if path.is_file():
        if path.suffix.lower() != '.md':
            raise SpokenBriefError('The handoff source must be a Markdown file')
        return path
    if not path.is_dir():
        raise SpokenBriefError('The handoff pack does not exist')
    for name in ('COMPRESSED.md', 'INDEX.md'):
        candidate = path / name
        if candidate.is_file():
            return candidate
    raise SpokenBriefError('The handoff pack needs COMPRESSED.md or INDEX.md')


def read_source_bytes(source: Path) -> bytes:
    source = Path(source).resolve()
    try:
        size = source.stat().st_size
    except OSError as exc:
        raise SpokenBriefError(f'Cannot inspect Markdown source: {source}') from exc
    if not 1 <= size <= MAX_SOURCE_BYTES:
        raise SpokenBriefError(f'Markdown source must contain 1 to {MAX_SOURCE_BYTES} bytes')
    try:
        with source.open('rb') as stream:
            raw = stream.read(MAX_SOURCE_BYTES + 1)
    except OSError as exc:
        raise SpokenBriefError(f'Cannot read Markdown source: {source}') from exc
    if not 1 <= len(raw) <= MAX_SOURCE_BYTES:
        raise SpokenBriefError(f'Markdown source must contain 1 to {MAX_SOURCE_BYTES} bytes')
    return raw


def verify_source(manifest: dict) -> Path:
    record = manifest.get('source') if isinstance(manifest, dict) else None
    if not isinstance(record, dict) or not isinstance(record.get('path'), str):
        raise SpokenBriefError('Spoken-brief manifest has an invalid source record')
    source = Path(record['path']).resolve()
    raw = read_source_bytes(source)
    if record.get('bytes') != len(raw) or record.get('sha256') != digest_bytes(raw):
        raise SpokenBriefError('The handoff source changed since compilation; run again to create a new spoken-brief manifest')
    return source


def _clean_inline(text: str, omissions: dict) -> str:
    def link(match):
        label = match.group(1)[1:-1].strip()
        return label or 'link omitted'
    text = LINK_RE.sub(link, text)

    def raw_url(match):
        omissions['raw_urls'] += 1
        value = match.group(0)
        punctuation = ''
        while value and value[-1] in '.,;:!?':
            punctuation = value[-1] + punctuation
            value = value[:-1]
        return 'link omitted' + punctuation
    text = URL_RE.sub(raw_url, text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'`([^`]*)`', r'\1', text)
    text = re.sub(r'(\*\*|__)(.*?)\1', r'\2', text)
    text = re.sub(r'(?<!\w)[*_~](.*?)[*_~](?!\w)', r'\1', text)
    text = re.sub(r'\[\^[^\]]+\]', '', text)
    text = re.sub(r'\\([`*_{}\[\]()#+.!|>-])', r'\1', text)
    return re.sub(r'\s+', ' ', text).strip()


def _hard_split(text: str, maximum: int) -> list[str]:
    words = text.split()
    result = []
    current = ''
    current_words = 0
    for word in words:
        if len(word) > maximum:
            if current:
                result.append(current)
                current = ''
                current_words = 0
            result.extend(word[index:index + maximum] for index in range(0, len(word), maximum))
            continue
        candidate = word if not current else current + ' ' + word
        if len(candidate) <= maximum and current_words < MAX_BATCH_WORDS:
            current = candidate
            current_words += 1
        else:
            result.append(current)
            current = word
            current_words = 1
    if current:
        result.append(current)
    return result


def _split_block(text: str) -> list[str]:
    sentences = [item.strip() for item in re.split(r'(?<=[.!?])\s+', text) if item.strip()]
    pieces = []
    for sentence in sentences or [text]:
        pieces.extend(_hard_split(sentence, MAX_LINE_CHARS)
                      if len(sentence) > MAX_LINE_CHARS or len(sentence.split()) > MAX_BATCH_WORDS
                      else [sentence])
    result = []
    current = ''
    for piece in pieces:
        candidate = piece if not current else current + ' ' + piece
        if current and (len(candidate) > MAX_LINE_CHARS or len(candidate.split()) > MAX_BATCH_WORDS
                        or (len(current) >= TARGET_LINE_CHARS and len(candidate) > TARGET_LINE_CHARS)):
            result.append(current)
            current = piece
        else:
            current = candidate
    if current:
        result.append(current)
    return result


def compile_markdown(source: str, *, source_name: str = 'brief.md') -> dict:
    if not isinstance(source, str):
        raise SpokenBriefError('Markdown source must be text')
    if '\0' in source:
        raise SpokenBriefError('Markdown source cannot contain NUL characters')
    source = source.lstrip('\ufeff')
    omissions = {'code_blocks': 0, 'raw_urls': 0, 'html_comments': 0, 'front_matter': 0}
    comments = re.findall(r'<!--.*?-->', source, flags=re.S)
    if comments:
        omissions['html_comments'] = len(comments)
        source = re.sub(r'<!--.*?-->', '', source, flags=re.S)
    lines = source.splitlines()
    if lines and lines[0].strip() == '---':
        for index in range(1, len(lines)):
            if lines[index].strip() == '---':
                lines = lines[index + 1:]
                omissions['front_matter'] = 1
                break
    blocks = []
    paragraph = []
    in_code = False

    def flush(kind='paragraph'):
        if not paragraph:
            return
        text = _clean_inline(' '.join(paragraph), omissions)
        paragraph.clear()
        if text:
            blocks.append({'kind': kind, 'text': text})

    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith('```') or stripped.startswith('~~~'):
            if not in_code:
                flush()
                omissions['code_blocks'] += 1
            in_code = not in_code
            continue
        if in_code:
            continue
        if not stripped:
            flush()
            continue
        if re.fullmatch(r'\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?', stripped):
            flush()
            continue
        if stripped.startswith('|') and stripped.endswith('|'):
            flush()
            cells = [_clean_inline(cell.strip(), omissions) for cell in stripped.strip('|').split('|')]
            cells = [cell for cell in cells if cell]
            if cells:
                blocks.append({'kind': 'table', 'text': '. '.join(cells) + '.'})
            continue
        heading = re.match(r'^#{1,6}\s+(.*)$', stripped)
        if heading:
            flush()
            text = _clean_inline(heading.group(1), omissions)
            if text:
                blocks.append({'kind': 'heading', 'text': text})
            continue
        stripped = re.sub(r'^>\s?', '', stripped)
        stripped = re.sub(r'^\s*(?:[-+*]|\d+[.)])\s+', '', stripped)
        stripped = re.sub(r'^\[(?: |x|X)\]\s+', '', stripped)
        paragraph.append(stripped)
    flush()
    segments = []
    for paragraph_index, block in enumerate(blocks):
        pieces = _split_block(block['text'])
        for piece_index, piece in enumerate(pieces):
            segments.append({
                'id': f'segment-{len(segments) + 1:04d}',
                'text': piece,
                'text_sha256': digest_bytes(piece.encode('utf-8')),
                'block': paragraph_index,
                'kind': block['kind'],
                'pause_after_ms': SECTION_PAUSE_MS if piece_index == len(pieces) - 1 else DEFAULT_PAUSE_MS,
            })
    if not segments:
        raise SpokenBriefError('The Markdown source contains no narratable text')
    if len(segments) > MAX_SEGMENTS or sum(len(item['text']) for item in segments) > MAX_NARRATED_CHARS:
        raise SpokenBriefError(f'Spoken briefs are limited to {MAX_SEGMENTS} segments and {MAX_NARRATED_CHARS} narrated characters')
    segments[-1]['pause_after_ms'] = 0
    return {
        'schema_version': SCHEMA_VERSION,
        'compiler_version': COMPILER_VERSION,
        'source_name': source_name,
        'segments': segments,
        'omissions': omissions,
    }


def batch_segments(segments: list[dict]) -> list[list[dict]]:
    batches = []
    current = []
    characters = 0
    words = 0
    for segment in segments:
        text = segment.get('text') if isinstance(segment, dict) else None
        if not isinstance(text, str) or not 1 <= len(text) <= MAX_LINE_CHARS:
            raise SpokenBriefError('Every spoken segment must fit the Voice baseline line contract')
        word_count = len(text.split())
        if word_count > MAX_BATCH_WORDS:
            raise SpokenBriefError('Every spoken segment must fit the Voice baseline word contract')
        if current and (len(current) >= MAX_BATCH_LINES or characters + len(text) > MAX_BATCH_CHARS
                        or words + word_count > MAX_BATCH_WORDS):
            batches.append(current)
            current = []
            characters = 0
            words = 0
        current.append(segment)
        characters += len(text)
        words += word_count
    if current:
        batches.append(current)
    return batches


def compile_source(source: Path, *, speaker_id: str = 'brief-narrator') -> dict:
    source = Path(source).resolve()
    if not SPEAKER_RE.fullmatch(speaker_id):
        raise SpokenBriefError('Speaker ID must start with a letter and use lowercase letters, numbers, dashes or underscores')
    return compile_snapshot(source, read_source_bytes(source), speaker_id=speaker_id)


def compile_snapshot(source: Path, raw: bytes, *, speaker_id: str = 'brief-narrator') -> dict:
    """Compile already captured bytes without reading, resolving or writing a file.

    The caller owns filesystem confinement and snapshot acquisition. Keeping the
    lexical absolute source identity also permits previews of retained snapshots
    after the original source has changed or disappeared.
    """
    source = Path(source).absolute()
    if not isinstance(speaker_id, str) or not SPEAKER_RE.fullmatch(speaker_id):
        raise SpokenBriefError('Speaker ID must start with a letter and use lowercase letters, numbers, dashes or underscores')
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_SOURCE_BYTES:
        raise SpokenBriefError(f'Markdown source must contain 1 to {MAX_SOURCE_BYTES} bytes')
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise SpokenBriefError('Markdown source must be UTF-8') from exc
    compiled = compile_markdown(text, source_name=source.name)
    manifest = {
        'schema_version': SCHEMA_VERSION,
        'kind': 'spoken-brief',
        'source': {'path': str(source), 'name': source.name, 'bytes': len(raw), 'sha256': digest_bytes(raw)},
        'speaker_id': speaker_id,
        'compiler': {
            'version': COMPILER_VERSION,
            'target_line_chars': TARGET_LINE_CHARS,
            'max_line_chars': MAX_LINE_CHARS,
            'max_batch_lines': MAX_BATCH_LINES,
            'max_batch_chars': MAX_BATCH_CHARS,
            'max_batch_words': MAX_BATCH_WORDS,
            'max_segments': MAX_SEGMENTS,
        },
        'omissions': compiled['omissions'],
        'segments': compiled['segments'],
    }
    manifest['manifest_sha256'] = canonical_digest(manifest)
    return manifest


def run_directory(source: Path, manifest_sha256: str) -> Path:
    safe_stem = re.sub(r'[^A-Za-z0-9._-]+', '-', Path(source).stem).strip('.-') or 'brief'
    return Path(source).parent / '_spoken' / f'{safe_stem}-{manifest_sha256[:12]}'
