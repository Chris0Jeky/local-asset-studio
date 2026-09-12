"""Bounded numeric-loopback transport and local artifact IO for the edit client.

No proxies, DNS lookups, redirect following, content classification or retries.
"""
from __future__ import annotations
import copy
import hashlib
import http.client
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
from PIL import Image

JSON_LIMIT = 8 * 1024 * 1024
IMAGE_LIMIT = 20 * 1024 * 1024
HEX = re.compile(r'[0-9a-f]{64}\Z')
PROJECT = re.compile(r'[0-9a-f]{32}\Z')
UPLOAD = re.compile(r'[0-9a-f]{32}_[A-Za-z0-9._-]+\.png\Z')


def require(value, message):
    if not value: raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(raw): return hashlib.sha256(raw).hexdigest()
def hashed(value): return digest(canonical(value))


def decode(raw):
    require(len(raw) <= JSON_LIMIT, 'JSON response exceeds the byte limit')
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, 'Duplicate JSON key'); result[k] = v
        return result
    def reject(_): raise ValueError('Non-finite JSON number')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=reject)


def read(path):
    with Path(path).open('rb') as stream: return decode(stream.read(JSON_LIMIT + 1))


def relative(value):
    require(isinstance(value, str) and 0 < len(value) <= 240 and '\\' not in value and ':' not in value,
            'Use a portable workspace-relative path')
    require(not PurePosixPath(value).is_absolute() and all(x not in ('', '.', '..') for x in value.split('/')),
            'Noncanonical or escaping path')
    require(not any(ord(x) < 32 or x in '<>"|?*' for x in value), 'Invalid path character')
    for part in value.split('/'):
        stem = part.split('.')[0].upper()
        require(not part.endswith((' ', '.')) and stem not in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}, 'Nonportable path component')


def local(root, name, exists=True):
    relative(name); base = Path(root).resolve(strict=True); p = base / name
    require(p.resolve().is_relative_to(base), 'Path escapes workspace through a symlink')
    if exists: require(p.is_file() and not p.is_symlink(), 'Missing or symlinked artifact: ' + name)
    return p


def bytes_of(root, artifact, limit=IMAGE_LIMIT):
    require(isinstance(artifact, dict) and set(artifact) == {'path', 'sha256'}, 'Invalid artifact descriptor')
    require(isinstance(artifact['sha256'], str) and HEX.fullmatch(artifact['sha256']), 'Invalid artifact digest')
    with local(root, artifact['path']).open('rb') as stream: raw = stream.read(limit + 1)
    require(0 < len(raw) <= limit and digest(raw) == artifact['sha256'], 'Artifact changed or exceeds limit: ' + artifact['path'])
    return raw


def artifact(root, name):
    return {'path': name, 'sha256': digest(local(root, name).read_bytes())}


def save_new(path, data):
    raw = data if isinstance(data, bytes) else canonical(data)
    with Path(path).open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def image_info(raw):
    require(0 < len(raw) <= IMAGE_LIMIT, 'PNG byte limit exceeded')
    with Image.open(io.BytesIO(raw)) as im:
        require(im.format == 'PNG' and getattr(im, 'n_frames', 1) == 1, 'Single-frame PNG required')
        require(im.width * im.height <= 24_000_000 and im.mode in ('RGB', 'RGBA'), 'Unsupported PNG size/mode')
        require(not im.info.get('exif') and not im.info.get('icc_profile'), 'Normalize EXIF/ICC explicitly before this neural bridge')
        im.load(); return im.convert('RGBA').copy()


class StudioHTTP:
    """Numeric IPv4 loopback only: no DNS, proxies, redirects, cookies or retries."""
    def __init__(self, port=8191, timeout=120):
        require(type(port) is int and 1 <= port <= 65535, 'Invalid Studio port')
        require(type(timeout) in (int, float) and 0 < timeout <= 300, 'Invalid timeout')
        self.port, self.timeout = port, timeout
        self.origin = f'http://127.0.0.1:{port}'

    def request(self, method, path, body=None, *, binary=False, filename=None):
        require(method in ('GET', 'POST') and path.startswith('/api/') and '\\' not in path
                and '#' not in path and not any(ord(c) < 32 for c in path), 'Invalid Studio request')
        raw = body if isinstance(body, bytes) else (canonical(body) if body is not None else None)
        limit = IMAGE_LIMIT if binary else JSON_LIMIT
        require(raw is None or len(raw) <= (IMAGE_LIMIT if filename else JSON_LIMIT), 'Request too large')
        headers = {'Origin': self.origin, 'Accept': 'image/png' if binary else 'application/json'}
        if raw is not None: headers['Content-Type'] = 'image/png' if filename else 'application/json'
        if filename:
            require(re.fullmatch(r'[A-Za-z0-9._-]+\.png', filename), 'Invalid upload filename')
            headers['X-Filename'] = filename
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=self.timeout)
        try:
            conn.request(method, path, body=raw, headers=headers); response = conn.getresponse()
            length = response.getheader('Content-Length')
            if length is not None: require(length.isdigit() and int(length) <= limit, 'Response too large')
            require(200 <= response.status < 300, f'Studio HTTP {response.status}; no automatic retry')
            data = response.read(limit + 1)
            require(len(data) <= limit, 'Response too large')
            return data if binary else decode(data)
        finally: conn.close()


