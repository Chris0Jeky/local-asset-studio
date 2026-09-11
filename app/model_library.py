"""Local model inventory and checksum-pinned, explicit asset installation."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import threading
import time
import uuid
from urllib.parse import urlparse
from urllib.request import Request, urlopen

FOLDERS = {
    "checkpoints": "Complete image models", "diffusion_models": "Diffusion / video / 3D models",
    "text_encoders": "Prompt interpreters", "vae": "Image, video and audio decoders",
    "loras": "Style and capability adapters", "controlnet": "Pose and structure controls",
    "clip_vision": "Reference image encoders", "upscale_models": "Image upscalers",
    "embeddings": "Learned prompt tokens", "latent_upscale_models": "Latent video upscalers",
    "background_removal": "Foreground isolation models",
}
SUFFIXES = {".safetensors", ".gguf", ".pth", ".pt", ".onnx"}
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
        for asset in self.manifest().get("assets", []):
            if asset.get("id") == asset_id:
                return asset
        raise ValueError("Unknown curated model")

    def destination(self, asset):
        relative = Path(asset["file"])
        target = (self.models / relative).resolve()
        if relative.is_absolute() or not target.is_relative_to(self.models) or relative.parts[0] not in FOLDERS:
            raise ValueError("Model destination is outside a supported model folder")
        if target.suffix != ".safetensors":
            raise ValueError("Automatic installation supports safetensors weights only")
        return target

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
        path = self.state / (asset_id + ".json")
        state.update(id=asset_id, updated_at=time.time())
        temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        temp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        temp.replace(path)
        return state

    def snapshot(self):
        manifest = self.manifest()
        assets = []
        for asset in manifest.get("assets", []):
            item = dict(asset)
            path = self.destination(asset)
            present = path.is_file()
            receipt = load(self.state / (asset["id"] + ".json"), {})
            matches = present and path.stat().st_size == asset["bytes"]
            verified = matches and receipt.get("status") == "installed" and receipt.get("sha256") == asset["sha256"] and receipt.get("mtime_ns") == path.stat().st_mtime_ns
            item.update(path=str(path), present=present, size_matches=matches, verified=verified, download=receipt)
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

    def start_install(self, asset_id):
        asset = self.asset(asset_id)
        self.destination(asset)
        if (self.state / "install.lock").exists():
            raise ValueError("Another installer is active. Check download progress before starting another.")
        if not self.lock.acquire(blocking=False):
            raise ValueError("Another model is installing. Wait for it to finish before starting the next.")
        state = self._record(asset_id, status="queued", bytes_done=0, bytes_total=asset["bytes"], message="Waiting for download worker")
        def work():
            try:
                self.install(asset_id)
            except Exception as exc:
                self._record(asset_id, status="failed", message=str(exc)[:300])
            finally:
                self.lock.release()
        threading.Thread(target=work, daemon=True, name="studio-model-download").start()
        return state

    def install(self, asset_id):
        asset = self.asset(asset_id)
        target = self.destination(asset)
        expected_size, expected_hash = asset["bytes"], asset["sha256"]
        if not isinstance(expected_size, int) or expected_size <= 0 or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            raise ValueError("This asset needs pinned size and SHA-256 metadata before installation")
        target.parent.mkdir(parents=True, exist_ok=True)
        # The lock also covers separate CLI/server processes; an interrupted lock is
        # intentionally explicit, never interpreted as permission to overwrite work.
        lock_path = self.state / "install.lock"
        try:
            lock_file = lock_path.open("x", encoding="utf-8")
        except FileExistsError:
            raise ValueError("An installer lock exists. Check the active downloader before removing .runtime/downloads/install.lock")
        try:
            lock_file.write(str(os.getpid())); lock_file.close()
            if target.exists():
                self._record(asset_id, status="verifying", message="Checking existing model SHA-256")
                if target.stat().st_size != expected_size or sha256(target) != expected_hash:
                    raise ValueError("Existing destination differs from the pinned asset. It has been preserved.")
            else:
                # Reuse the exact downloaded file without duplicating tens of GB.
                name = asset.get("download_filename", target.name)
                if Path(name).name != name:
                    raise ValueError("Invalid download basename")
                local = Path.home() / "Downloads" / name
                if local.is_file() and local.stat().st_size == expected_size:
                    self._record(asset_id, status="verifying", message="Checking your existing browser download")
                    if sha256(local) != expected_hash:
                        raise ValueError("Browser download checksum differs from the source. Original preserved.")
                    try:
                        os.link(local, target)
                    except OSError:
                        if target.exists():
                            raise ValueError("Destination appeared during installation; original preserved")
                        if shutil.disk_usage(target.parent).free < expected_size + RESERVE_BYTES:
                            raise ValueError("More disk space is needed to preserve 20 GiB of working headroom")
                        part = self.partial_path(target)
                        with part.open("xb") as output, local.open("rb") as source:
                            shutil.copyfileobj(source, output, length=8 * 1024**2)
                        if sha256(part) != expected_hash:
                            raise ValueError("Copied file checksum failed; destination not installed")
                        if target.exists():
                            raise ValueError("Destination appeared during copy; both files preserved")
                        part.rename(target)
                else:
                    self._download(asset, target)
            return self._record(asset_id, status="installed", bytes_done=expected_size, bytes_total=expected_size,
                                sha256=expected_hash, mtime_ns=target.stat().st_mtime_ns,
                                message="Installed and SHA-256 verified. Reload ComfyUI's model lists.")
        finally:
            lock_path.unlink(missing_ok=True)

    def partial_path(self, target):
        part = target.with_suffix(target.suffix + ".part")
        if part.is_symlink() or not part.resolve().is_relative_to(self.models):
            raise ValueError("Partial download points outside the model library")
        return part

    def _download(self, asset, target):
        url = asset["url"]
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in ("huggingface.co", "civitai.com", "civitai.red") or parsed.username or parsed.password:
            raise ValueError("Automatic installation requires a curated HTTPS model source")
        part = self.partial_path(target)
        size = asset["bytes"]
        offset = part.stat().st_size if part.exists() else 0
        if offset > size:
            raise ValueError("Partial download exceeds expected size; preserved for inspection")
        if shutil.disk_usage(target.parent).free < size - offset + RESERVE_BYTES:
            raise ValueError("More disk space is needed to preserve 20 GiB of working headroom")
        if offset < size:
            req = Request(url, headers={"User-Agent": "LocalAssetStudio/1", **({"Range": f"bytes={offset}-"} if offset else {})})
            with urlopen(req, timeout=60) as response:
                if offset and (response.status != 206 or not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-")):
                    raise ValueError("Source did not honor resume. Partial download preserved.")
                start = time.time(); last = 0; original = offset
                with part.open("ab") as stream:
                    while chunk := response.read(4 * 1024**2):
                        if offset + len(chunk) > size:
                            raise ValueError("Download exceeds pinned size; destination not installed")
                        stream.write(chunk); offset += len(chunk)
                        now = time.time()
                        if now - last > 2:
                            self._record(asset["id"], status="downloading", bytes_done=offset, bytes_total=size,
                                         bytes_per_second=(offset-original)/max(now-start, .01), message="Downloading verified-source weights")
                            last = now
        self._record(asset["id"], status="verifying", bytes_done=offset, bytes_total=size, message="Checking SHA-256 before installation")
        if part.stat().st_size != size or sha256(part) != asset["sha256"]:
            raise ValueError("Download is incomplete or checksum failed. Partial file preserved; nothing installed.")
        # Never overwrite a destination created while the transfer was running.
        if target.exists():
            raise ValueError("Destination appeared during download; both files preserved")
        part.rename(target)
