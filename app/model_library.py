"""Local model inventory and checksum-pinned, explicit asset installation."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import threading
import time
import uuid
from urllib.request import Request
from download_contracts import InstallLease, asset_id as checked_id, download_source_provider, file_identity, open_download as urlopen, publish_verified, relative_model_path, validate_pins, validate_response

from studio_workflow.model_contracts import FOLDERS, SUFFIXES
INSTALL_SUFFIX = ".safetensors"
RESERVE_BYTES = 20 * 1024**3


def load(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024**2), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ModelLibrary:
    def __init__(self, root, comfy_root):
        self.root = Path(root).resolve()
        self.comfy = Path(comfy_root).resolve()
        self.models = (self.comfy / "models").resolve()
        self.state = self.root / ".runtime/downloads"
        self.state.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def manifest(self):
        return load(self.root / "models/library.json", {"assets": [], "collections": []})

    def asset(self, asset_id):
        checked_id(asset_id)
        for asset in self.manifest().get("assets", []):
            if asset.get("id") == asset_id:
                validate_pins(asset)
                return dict(asset)
        raise ValueError("Unknown curated model")

    def locate(self, asset):
        """Where a pinned file lives, whether or not the installer may write it."""
        relative = relative_model_path(asset["file"])
        self._check_path(self.models / relative)
        target = (self.models / relative).resolve()
        if relative.is_absolute() or not target.is_relative_to(self.models) or relative.parts[0] not in FOLDERS:
            raise ValueError("Model destination is outside a supported model folder")
        return target

    def destination(self, asset):
        """The install target. Pin-only kinds (.pt/.pth/.gguf/.onnx) are refused here."""
        target = self.locate(asset)
        if target.suffix != INSTALL_SUFFIX:
            raise ValueError("Automatic installation supports safetensors weights only")
        return target

    def install_block(self, asset, present=None):
        """Why automatic installation is unavailable for this pin, or None when it is.

        A missing file with no curated URL can only fail deep inside _download, after a
        queued receipt exists; refuse it here instead. An already-installed copy still
        verifies, which is the whole point of pinning a file of unrecorded provenance.
        """
        try:target=self.destination(asset)
        except ValueError as exc:return str(exc)
        if present is None:present=target.is_file()
        if not present:
            try:download_source_provider(asset.get('url') or '')
            except ValueError:return 'No curated source is pinned; copy this file in by hand'
        return None

    def _check_path(self, path):
        if not path.is_relative_to(self.models):raise ValueError('Model path escapes the library')
        for candidate in (path,*path.parents):
            if candidate==self.models:break
            if candidate.is_symlink() or (hasattr(candidate,'is_junction') and candidate.is_junction()):
                raise ValueError('Model or partial path is a link; original preserved')

    def folder(self, key):
        if key in FOLDERS:
            path = (self.models / key).resolve()
            if not path.is_relative_to(self.models):
                raise ValueError("Model folder points outside the model library")
            return path
        fixed = {"input": self.comfy / "input", "output": self.comfy / "output",
                 "workflows": self.root / "workflows/comfyui", "downloads": Path.home() / "Downloads"}
        if key not in fixed:
            raise ValueError("Unknown studio folder")
        return fixed[key]

    def open_folder(self, key):
        path = self.folder(key)
        path.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            raise ValueError("Open folder is available on Windows; copy the path instead")
        os.startfile(str(path))
        return {"path": str(path)}

    def _record(self, asset_id, **state):
        checked_id(asset_id)
        path = self.state / (asset_id + ".json")
        state.update(id=asset_id, updated_at=time.time())
        temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            with temp.open('x',encoding='utf-8') as stream:
                json.dump(state,stream,indent=2);stream.flush();os.fsync(stream.fileno())
            temp.replace(path)
        finally:temp.unlink(missing_ok=True)
        return state

    def snapshot(self):
        manifest = self.manifest()
        assets = []
        for asset in manifest.get("assets", []):
            item = dict(asset)
            path = self.locate(asset)
            present = path.is_file()
            blocked = self.install_block(asset, present)
            checked_id(asset['id'])
            receipt = load(self.state / (asset["id"] + ".json"), {})
            if not isinstance(receipt,dict):receipt={}
            identity = file_identity(path) if present else None
            matches = present and identity['size'] == asset["bytes"]
            verified = bool(matches and receipt.get('version')==2 and receipt.get("status")=="installed"
                            and receipt.get("sha256")==asset["sha256"] and receipt.get('path')==str(path)
                            and receipt.get('file_identity')==identity)
            reason = ('stat-fresh-sha256-receipt' if verified else 'missing' if not present
                      else 'pin-only-manual-verification' if blocked else 'explicit-reverification-required')
            item.update(path=str(path), present=present, size_matches=matches, verified=verified,
                        verification=reason, installable=blocked is None, install_note=blocked, download=receipt)
            assets.append(item)
        folders = [{"id": key, "label": label, "path": str(self.folder(key))} for key, label in FOLDERS.items()]
        folders += [{"id": key, "label": label, "path": str(self.folder(key))} for key, label in [("input", "Reference inputs"), ("output", "Generated outputs"), ("workflows", "Editable workflows"), ("downloads", "Browser downloads")]]
        inventory = []
        if self.models.is_dir():
            for path in self.models.rglob("*"):
                if path.is_file() and path.suffix.lower() in SUFFIXES and path.resolve().is_relative_to(self.models):
                    inventory.append({"file": path.relative_to(self.models).as_posix(), "bytes": path.stat().st_size, "folder": path.relative_to(self.models).parts[0]})
        disk = shutil.disk_usage(self.models if self.models.exists() else self.root)
        return {"assets": assets, "collections": manifest.get("collections", []), "folders": folders,
                "inventory": inventory, "storage": {"free_bytes": disk.free, "total_bytes": disk.total, "reserve_bytes": RESERVE_BYTES},
                "model_root": str(self.models)}

    def _validated_asset(self, asset_id):
        asset=self.asset(asset_id);self.destination(asset)
        blocked=self.install_block(asset)
        if blocked:raise ValueError(blocked)
        validate_pins(asset)
        return asset

    def start_install(self, asset_id):
        asset=self._validated_asset(asset_id)
        if not self.lock.acquire(blocking=False):raise ValueError('Another model is installing; inspect its progress first')
        lease=None
        try:
            # Reserve across CLI/server processes before publishing queued state.
            lease=InstallLease(self.state/'install.lock',asset_id)
            state=self._record(asset_id,status='queued',bytes_done=0,bytes_total=asset['bytes'],message='Waiting for download worker')
            def work():
                try:self._install(asset)
                except Exception as exc:self._failed(asset,exc)
                finally:
                    try:lease.release()
                    finally:self.lock.release()
            threading.Thread(target=work,daemon=True,name='studio-model-download').start()
            return state
        except Exception as exc:
            try:
                if lease:
                    try:self._failed(asset,exc)
                    finally:lease.release()
            finally:self.lock.release()
            raise

    def install(self, asset_id):
        asset=self._validated_asset(asset_id)
        lease=InstallLease(self.state/'install.lock',asset_id)
        try:return self._install(asset)
        except Exception as exc:
            self._failed(asset,exc)
            raise
        finally:lease.release()

    def _failed(self, asset, exc):
        # Reporting a disk/path failure must not mask it or strand the worker gate.
        done=None;partial=None
        try:
            part=self.partial_path(self.destination(asset));partial=str(part)
            done=part.stat().st_size if part.is_file() else 0
        except (OSError,ValueError):pass
        try:self._record(asset['id'],status='failed',bytes_done=done,bytes_total=asset['bytes'],
                         sha256=asset['sha256'],partial_path=partial,message=str(exc)[:300])
        except OSError as reporting_error:
            exc.add_note('Failure receipt could not be written: '+str(reporting_error))

    @staticmethod
    def _verify(path, asset):
        before=file_identity(path)
        if before['size']!=asset['bytes'] or sha256(path)!=asset['sha256']:
            raise ValueError('File size or checksum differs from the pinned asset. Original and partial files preserved.')
        if before!=file_identity(path):raise ValueError('File changed while hashing; original preserved, not verified')
        return before

    def _install(self, asset):
        asset_id=asset['id'];target=self.destination(asset)
        expected_size,expected_hash=asset['bytes'],asset['sha256']
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            self._record(asset_id,status='verifying',message='Checking existing model SHA-256')
            identity=self._verify(target,asset)
        else:
            # Reuse a trusted hash without duplicating tens of GB. Shared inode
            # changes invalidate the receipt; this is not an immutable source copy.
            name=asset.get('download_filename',target.name)
            if not isinstance(name,str) or relative_model_path(name).name!=name:raise ValueError('Invalid download basename')
            local=Path.home()/'Downloads'/name
            if local.is_file() and local.stat().st_size==expected_size:
                self._record(asset_id,status='verifying',message='Checking your existing browser download')
                verified=self._verify(local,asset)
                self._check_path(target)
                try:os.link(local,target)
                except OSError:
                    if target.exists() or target.is_symlink():raise ValueError('Destination appeared during installation; original preserved')
                    if shutil.disk_usage(target.parent).free<expected_size+RESERVE_BYTES:raise ValueError('More disk space is needed to preserve 20 GiB of working headroom')
                    part=self.partial_path(target)
                    with part.open('xb') as output,local.open('rb') as source:
                        while chunk:=source.read(4*1024**2):
                            if output.tell()+len(chunk)>expected_size:raise ValueError('Browser file grew during copy; partial preserved')
                            if shutil.disk_usage(target.parent).free<len(chunk)+RESERVE_BYTES:raise ValueError('Insufficient disk space during copy; partial preserved')
                            output.write(chunk)
                        output.flush();os.fsync(output.fileno())
                    identity=publish_verified(part,target,self._verify(part,asset))
                else:
                    identity=file_identity(target)
                    if any(identity[k]!=verified[k] for k in ('device','inode','size','mtime_ns')):
                        raise ValueError('Browser file changed during linking; files preserved, not verified')
            else:identity=self._download(asset,target)
        # Metadata freshness prevents a receipt migrating between roots or replacement files.
        if file_identity(target)!=identity:raise ValueError('Installed file changed before receipt; reverify explicitly')
        return self._record(asset_id,version=2,status='installed',path=str(target),file_identity=identity,
                            bytes_done=expected_size,bytes_total=expected_size,sha256=expected_hash,
                            mtime_ns=identity['mtime_ns'],message="Installed and SHA-256 verified. Reload ComfyUI's model lists.")

    def partial_path(self, target):
        part = target.with_suffix(target.suffix + ".part")
        self._check_path(part)
        if part.exists() and (not part.is_file() or part.stat().st_nlink!=1):raise ValueError('Partial download must be an unshared regular file; original preserved')
        if part.is_symlink() or not part.resolve().is_relative_to(self.models):
            raise ValueError("Partial download points outside the model library")
        return part

    def _download(self, asset, target):
        url = asset["url"]
        download_source_provider(url)
        part = self.partial_path(target)
        size = asset["bytes"]
        offset = part.stat().st_size if part.exists() else 0
        if offset > size:
            raise ValueError("Partial download exceeds expected size; preserved for inspection")
        if shutil.disk_usage(target.parent).free < size - offset + RESERVE_BYTES:
            raise ValueError("More disk space is needed to preserve 20 GiB of working headroom")
        if offset < size:
            req = Request(url, headers={"User-Agent": "LocalAssetStudio/1", "Accept-Encoding": "identity", **({"Range": f"bytes={offset}-"} if offset else {})})
            with urlopen(req, timeout=60) as response:
                validate_response(response,offset,size)
                start = time.time(); last = 0; original = offset
                self.partial_path(target)
                with part.open("ab" if part.exists() else "xb") as stream:
                    if stream.tell()!=offset:raise ValueError('Partial file changed before append; original preserved')
                    while chunk := response.read(4 * 1024**2):
                        if offset + len(chunk) > size:
                            raise ValueError("Download exceeds pinned size; destination not installed")
                        if shutil.disk_usage(target.parent).free<len(chunk)+RESERVE_BYTES:
                            raise ValueError('Insufficient disk space during transfer; partial download preserved')
                        stream.write(chunk); offset += len(chunk)
                        now = time.time()
                        if now - last > 2:
                            self._record(asset["id"], status="downloading", bytes_done=offset, bytes_total=size,
                                         bytes_per_second=(offset-original)/max(now-start, .01), message="Downloading verified-source weights")
                            last = now
                    stream.flush();os.fsync(stream.fileno())
        self._record(asset["id"], status="verifying", bytes_done=offset, bytes_total=size, message="Checking SHA-256 before installation")
        identity=self._verify(part,asset)
        self._check_path(target)
        return publish_verified(part,target,identity)
