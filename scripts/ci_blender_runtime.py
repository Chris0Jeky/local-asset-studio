"""Fetch one explicitly selected official runtime in hosted CI; never discover a replacement."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile
import time
from urllib.parse import unquote, urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request

HOSTS = {'builder.blender.org', 'cdn.builder.blender.org'}
MAX_ARCHIVE = 800 * 1024 * 1024
MAX_EXPANDED = 4 * 1024 * 1024 * 1024


def require(condition, message):
    if not condition: raise ValueError(message)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def archive_name(selection):
    require(selection.get('schema_version') == 1, 'Unsupported runtime descriptor')
    require(selection.get('version') == [5, 4, 0] and selection.get('release_cycle') == 'alpha',
            'Qualification requires the explicitly selected Blender 5.4.0 alpha')
    require(selection.get('platform') == 'linux' and selection.get('architecture') == 'x86_64',
            'Qualification requires Linux x86_64')
    build = selection.get('build_hash', '')
    require(isinstance(build, str) and re.fullmatch(r'[0-9a-f]{12}', build), 'Invalid Blender build hash')
    return f'blender-5.4.0-alpha+main.{build}-linux.x86_64-release.tar.xz'


def validate_url(url, filename):
    require(isinstance(url, str) and not any(c.isspace() for c in url), 'Invalid runtime URL')
    parsed = urlsplit(url)
    require(parsed.scheme == 'https' and parsed.hostname in HOSTS and parsed.netloc == parsed.hostname
            and not parsed.query and not parsed.fragment, 'Runtime URL must use an official HTTPS host without credentials or options')
    require(unquote(parsed.path) == '/download/daily/' + filename, 'Unexpected official runtime archive path')
    return url


def validate_selection(selection):
    name = archive_name(selection)
    validate_url(selection.get('archive_url'), name)
    validate_url(selection.get('checksum_url'), name + '.sha256')
    return name


class OfficialRedirects(HTTPRedirectHandler):
    def __init__(self, filename): self.filename = filename

    def redirect_request(self, request, fp, code, message, headers, new_url):
        validate_url(new_url, self.filename)
        return super().redirect_request(request, fp, code, message, headers, new_url)


def download(url, destination, filename, limit, deadline):
    validate_url(url, filename)
    opener = build_opener(OfficialRedirects(filename))
    digest = hashlib.sha256(); total = 0
    request = Request(url, headers={'User-Agent': 'Local-Asset-Studio-native-qualification/1'})
    with opener.open(request, timeout=20) as response, destination.open('xb') as stream:
        validate_url(response.geturl(), filename)
        while True:
            require(time.monotonic() < deadline, 'Runtime download deadline exceeded')
            block = response.read(1024 * 1024)
            if not block: break
            total += len(block); require(total <= limit, 'Runtime download exceeds size limit')
            stream.write(block); digest.update(block)
    require(total > 0, 'Empty runtime download')
    return {'url': url, 'final_url': response.geturl(), 'bytes': total, 'sha256': digest.hexdigest()}


def checksum_digest(data, filename):
    text = data.decode('ascii').strip()
    match = re.fullmatch(r'([0-9a-fA-F]{64})(?:[ \t]+\*?([^\r\n]+))?', text)
    require(match is not None, 'Official checksum must contain exactly one SHA-256 entry')
    require(match[2] is None or match[2] == filename, 'Official checksum names another archive')
    return match[1].lower()


def verify_checksum(archive, checksum, filename):
    expected = checksum_digest(checksum.read_bytes(), filename)
    with archive.open('rb') as stream: actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    require(actual == expected, 'Downloaded Blender archive SHA-256 mismatch')
    return actual


def extract_runtime(archive, destination, filename):
    root = filename.removesuffix('.tar.xz')
    with tarfile.open(archive, 'r:xz') as bundle:
        members = bundle.getmembers()
        require(0 < len(members) <= 100000, 'Unexpected archive member count')
        require(sum(member.size for member in members) <= MAX_EXPANDED, 'Expanded runtime exceeds size limit')
        for member in members:
            path = PurePosixPath(member.name)
            require(not path.is_absolute() and path.parts and path.parts[0] == root
                    and '..' not in path.parts and '\\' not in member.name, 'Archive member escapes expected root')
            require(member.isdir() or member.isfile() or member.issym() or member.islnk(), 'Unsupported archive member type')
            # Python's data filter also rejects links escaping destination and special files.
            tarfile.data_filter(member, str(destination))
        bundle.extractall(destination, members=members, filter='data')
    binary = destination / root / 'blender'
    require(binary.is_file() and not binary.is_symlink() and os.access(binary, os.X_OK), 'Archive lacks executable Blender')
    return binary.resolve()


def bootstrap(descriptor, work, evidence):
    work.mkdir(parents=True, exist_ok=False); evidence.mkdir(parents=True, exist_ok=True)
    receipt = {'state': 'failed', 'started_utc': datetime.now(timezone.utc).isoformat(),
               'descriptor_sha256': hashlib.sha256(descriptor.read_bytes()).hexdigest()}
    write_json(evidence / 'bootstrap.json', receipt)
    try:
        selection = json.loads(descriptor.read_text(encoding='utf-8')); receipt['selection'] = selection
        write_json(evidence / 'runtime-selection.json', selection)
        name = validate_selection(selection)
        checksum = evidence / (name + '.sha256'); archive = work / name
        deadline = time.monotonic() + 180
        receipt['checksum_download'] = download(selection['checksum_url'], checksum, name + '.sha256', 4096, deadline)
        receipt['archive_download'] = download(selection['archive_url'], archive, name, MAX_ARCHIVE, deadline)
        receipt['verified_archive_sha256'] = verify_checksum(archive, checksum, name)
        receipt['checksum_verified'] = True
        write_json(evidence / 'bootstrap.json', receipt)
        binary = extract_runtime(archive, work, name)
        with binary.open('rb') as stream: receipt['binary_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
        receipt.update(state='passed', binary_path=str(binary))
        return binary
    except Exception as exc:
        receipt['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
        write_json(evidence / 'bootstrap.json', receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--descriptor', required=True, type=Path)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--evidence', required=True, type=Path)
    args = parser.parse_args()
    binary = bootstrap(args.descriptor, args.work, args.evidence)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream: stream.write(f'binary={binary}\n')
    print(binary)


if __name__ == '__main__': main()
