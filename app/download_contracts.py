"""Pinned-transfer, receipt-freshness and no-clobber publication contracts."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import time
import uuid


def asset_id(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}',value):
        raise ValueError('Invalid curated model ID')
    return value


def relative_model_path(value):
    if not isinstance(value,str) or not value or '\\' in value:raise ValueError('Model destination must be a portable relative path')
    parts=value.split('/')
    for part in parts:
        if (not part or part in ('.','..') or part[-1:] in ('.',' ') or re.search(r'[<>:"|?*\x00-\x1f]',part)
                or re.fullmatch(r'(con|prn|aux|nul|com[1-9]|lpt[1-9])',part.split('.')[0],re.I)):
            raise ValueError('Model destination must be a portable relative path')
    return Path(*parts)


def file_identity(path):
    value=path.stat()
    return {'device':value.st_dev,'inode':value.st_ino,'size':value.st_size,
            'mtime_ns':value.st_mtime_ns,'ctime_ns':value.st_ctime_ns}


def validate_pins(asset):
    asset_id(asset.get('id'))
    if type(asset.get('bytes')) is not int or asset['bytes']<=0 or not isinstance(asset.get('sha256'),str) or not re.fullmatch(r'[0-9a-f]{64}',asset['sha256']):
        raise ValueError('This asset needs pinned size and SHA-256 metadata before installation')


def validate_response(response, offset, size):
    """Only one complete remaining byte range, identity encoding, is supported."""
    if response.headers.get('Content-Encoding','identity').lower()!='identity':
        raise ValueError('Encoded model transfer refused. Partial download preserved.')
    expected=size-offset
    if response.status==206:
        match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers.get('Content-Range',''))
        if not match or tuple(map(int,match.groups()))!=(offset,size-1,size):
            raise ValueError('Source did not honor resume with the exact pinned range. Partial download preserved.')
    elif response.status!=200 or offset:
        raise ValueError('Source did not honor resume or returned an unexpected status. Partial download preserved.')
    elif response.headers.get('Content-Range') is not None:
        raise ValueError('Unexpected range on a full response. Partial download preserved.')
    length=response.headers.get('Content-Length')
    if length is not None and (not re.fullmatch(r'\d+',length) or int(length)!=expected):
        raise ValueError('Response length differs from the pinned range. Partial download preserved.')


def publish_verified(source,target,identity):
    """Atomically create a destination without overwriting any competing directory entry.

    Source and target must be on the same hard-link-capable filesystem. There is
    deliberately no POSIX rename fallback: rename would overwrite a racing file.
    """
    if file_identity(source)!=identity:raise ValueError('Verified source changed before publication; all files preserved')
    try:os.link(source,target)
    except FileExistsError as exc:raise ValueError('Destination appeared during publication; both files preserved') from exc
    except OSError as exc:raise ValueError('Atomic no-clobber publication is unavailable; verified source preserved for explicit recovery') from exc
    after=file_identity(target)
    # Adding a hard link changes ctime, but not the underlying data identity.
    if any(after[key]!=identity[key] for key in ('device','inode','size','mtime_ns')):
        raise ValueError('Source changed during publication; files preserved for inspection, not verified')
    source.unlink()
    return file_identity(target)


class InstallLease:
    """Cross-process exclusive owner token; never auto-reap interrupted locks."""
    def __init__(self,path,identifier):
        self.path=path;self.token=uuid.uuid4().hex
        try:stream=path.open('x',encoding='utf-8')
        except FileExistsError as exc:raise ValueError('Another installer lock exists. Inspect the active downloader before removing install.lock.') from exc
        try:
            with stream:
                json.dump({'version':1,'token':self.token,'pid':os.getpid(),'asset_id':identifier,'started_at':time.time()},stream)
                stream.flush();os.fsync(stream.fileno())
        except Exception:
            # Leave an incomplete lock as evidence; it cannot authorize another worker.
            raise
    def release(self):
        try:
            value=json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(value,dict) or value.get('token')!=self.token:return False
            self.path.unlink();return True
        except (OSError,ValueError):return False
