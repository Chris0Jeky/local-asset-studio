"""Pinned-transfer, receipt-freshness and no-clobber publication contracts."""
from __future__ import annotations
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import time
import uuid
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, build_opener


MAX_DOWNLOAD_REDIRECTS=5
_SOURCE_PROVIDERS={'huggingface.co':'huggingface','civitai.com':'civitai','civitai.red':'civitai'}
# Published at https://huggingface.co/.well-known/meta.json on 2026-09-12.
_HUGGINGFACE_DOWNLOAD_HOSTS={
    'huggingface.co','cdn-lfs.hf.co','cdn-lfs-us-1.hf.co','cdn-lfs-eu-1.hf.co',
    'transfer.xethub.hf.co','transfer.xethub-eu.hf.co','aws.cdn.hf.co','us.aws.cdn.hf.co',
    'us-east-1.aws.cdn.hf.co','us-west-2.aws.cdn.hf.co','eu-west-3.aws.cdn.hf.co',
    'ap-southeast-1.aws.cdn.hf.co','us.gcp.cdn.hf.co','us-east1.us.gcp.cdn.hf.co',
    'us-central1.us.gcp.cdn.hf.co','us-west4.us.gcp.cdn.hf.co',
    'europe-west4.us.gcp.cdn.hf.co','asia-southeast1.us.gcp.cdn.hf.co',
}
_CIVITAI_DOWNLOAD_HOSTS={
    'civitai.com','civitai.red','b2.civitai.com',
    'civitai-modelfiles-b2.f004.backblazeb2.com','s3.us-west-004.backblazeb2.com',
}
_CIVITAI_R2=re.compile(r'civitai-delivery-worker-prod(?:-\d{4}-\d{2}-\d{2})?\.'
                       r'5ac0637cfd0766c97916cefa3764fbdf\.r2\.cloudflarestorage\.com')
_CROSS_HOST_HEADERS={'user-agent','accept-encoding','range'}


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


def _parsed_https_url(url):
    try:
        parsed=urlparse(url);port=parsed.port
    except (TypeError,ValueError) as exc:
        raise ValueError('Model download URL is malformed') from exc
    if (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password
            or port not in (None,443)):
        raise ValueError('Model downloads require HTTPS on port 443 without URL credentials')
    return parsed


def _provider_target_allowed(provider,parsed):
    host=parsed.hostname.lower()
    if provider=='huggingface':return host in _HUGGINGFACE_DOWNLOAD_HOSTS
    if provider!='civitai':return False
    if host not in _CIVITAI_DOWNLOAD_HOSTS and not _CIVITAI_R2.fullmatch(host):return False
    if host=='s3.us-west-004.backblazeb2.com':
        return parsed.path=='/civitai-modelfiles-b2' or parsed.path.startswith('/civitai-modelfiles-b2/')
    return True


def download_source_provider(url):
    """Validate the curated origin without performing DNS for offline reuse paths."""
    parsed=_parsed_https_url(url);provider=_SOURCE_PROVIDERS.get(parsed.hostname.lower())
    if provider is None:raise ValueError('Automatic installation requires a curated HTTPS model source')
    return provider


def validate_download_url(url,provider=None,resolver=socket.getaddrinfo):
    """Validate one source/redirect URL and every address it currently resolves to."""
    parsed=_parsed_https_url(url);host=parsed.hostname.lower()
    if provider is None:
        provider=download_source_provider(url)
    if not _provider_target_allowed(provider,parsed):
        raise ValueError(f'{provider} model download redirected to an untrusted host')
    try:answers=resolver(host,443,type=socket.SOCK_STREAM)
    except OSError as exc:raise ValueError('Model download host could not be resolved safely') from exc
    addresses=set()
    for answer in answers:
        try:addresses.add(ipaddress.ip_address(str(answer[4][0]).split('%',1)[0]))
        except (IndexError,TypeError,ValueError) as exc:raise ValueError('Model download host returned an invalid address') from exc
    if not addresses:raise ValueError('Model download host returned no addresses')
    if any(address.is_multicast for address in addresses):
        raise ValueError('Model download host resolves to a multicast address')
    if any(not address.is_global for address in addresses):
        raise ValueError('Model download host resolves to a loopback, private, local or reserved address')
    return provider


class DownloadRedirectHandler(HTTPRedirectHandler):
    """Validate every Location before urllib opens it and bound each transfer chain."""
    def __init__(self,provider,resolver=socket.getaddrinfo,max_redirects=MAX_DOWNLOAD_REDIRECTS):
        super().__init__();self.provider=provider;self.resolver=resolver;self.max_redirects=max_redirects;self.redirects=0
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        try:
            self.redirects+=1
            if self.redirects>self.max_redirects:raise ValueError('Model download exceeded the redirect limit')
            validate_download_url(newurl,self.provider,self.resolver)
        except Exception:
            fp.close();raise
        redirected=super().redirect_request(req,fp,code,msg,headers,newurl)
        if redirected is not None and urlparse(req.full_url).hostname.lower()!=urlparse(newurl).hostname.lower():
            # Only the transfer contract crosses providers' host boundaries. Tokens,
            # cookies, custom Host values and any future caller headers stay behind.
            for collection in (redirected.headers,redirected.unredirected_hdrs):
                for name in list(collection):
                    if name.lower() not in _CROSS_HOST_HEADERS:redirected.remove_header(name)
        return redirected


def open_download(request,timeout=60,resolver=socket.getaddrinfo,transport_handlers=()):
    """Open one curated transfer with a fresh redirect counter and address policy."""
    provider=validate_download_url(request.full_url,resolver=resolver)
    client=build_opener(DownloadRedirectHandler(provider,resolver),*transport_handlers)
    return client.open(request,timeout=timeout)


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
