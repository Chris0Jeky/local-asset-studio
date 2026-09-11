"""Fixed, non-interactive OpenRaster -> Krita -> PNG roundtrip adapter.

The only application invocation is Krita's documented batch export form.  It
does not accept user scripts, macros, shell text, or a command override.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile


DEFAULT_KRITA = Path(r"C:\Program Files\Krita (x64)\bin\krita.exe")
MAX_ORA_BYTES = 64 * 1024 * 1024
MAX_ZIP_MEMBERS = 256
MAX_ZIP_MEMBER_BYTES = 64 * 1024 * 1024
MAX_PIXELS = 16 * 1024 * 1024
TIMEOUT_SECONDS = 90


class KritaRoundtripError(ValueError):
    """A bounded Krita roundtrip cannot safely proceed."""


def require(condition, message):
    if not condition:
        raise KritaRoundtripError(message)


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_name(name):
    value = Path(name)
    return bool(name) and not value.is_absolute() and ".." not in value.parts and "\\" not in name


def _png_dimensions(raw, label):
    require(len(raw) >= 24 and raw[:8] == b"\x89PNG\r\n\x1a\n" and raw[12:16] == b"IHDR", f"Invalid PNG: {label}")
    width, height = int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")
    require(1 <= width <= 8192 and 1 <= height <= 8192 and width * height <= MAX_PIXELS,
            f"PNG exceeds the roundtrip pixel budget: {label}")
    return [width, height]


def png_dimensions(path):
    with Path(path).open("rb") as stream:
        return _png_dimensions(stream.read(24), Path(path).name)


def _zip(path, label):
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise KritaRoundtripError(f"Invalid {label} ZIP") from exc
    entries = archive.infolist()
    require(1 <= len(entries) <= MAX_ZIP_MEMBERS, f"{label} has too many ZIP entries")
    require(all(_safe_name(entry.filename) and entry.file_size <= MAX_ZIP_MEMBER_BYTES for entry in entries),
            f"{label} contains an unsafe or oversized ZIP entry")
    require(len({entry.filename for entry in entries}) == len(entries), f"{label} contains duplicate ZIP entries")
    return archive, entries


def _layers(root):
    result = []
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1].lower()
        if tag in {"layer", "paintlayer", "shapelayer", "grouplayer"}:
            result.append({key: node.attrib[key] for key in ("name", "nodetype", "visible", "compositeop", "composite-op", "src")
                           if key in node.attrib})
    return result


def inspect_ora(path):
    path = Path(path).resolve()
    require(path.is_file() and path.suffix.lower() == ".ora", "Supply an existing .ora file")
    require(path.stat().st_size <= MAX_ORA_BYTES, "ORA exceeds the 64 MiB byte budget")
    archive, entries = _zip(path, "ORA")
    try:
        require(entries[0].filename == "mimetype" and archive.read("mimetype") == b"image/openraster",
                "ORA mimetype entry is missing or invalid")
        root = ET.fromstring(archive.read("stack.xml"))
        width, height = int(root.attrib.get("w", 0)), int(root.attrib.get("h", 0))
        require(1 <= width <= 8192 and 1 <= height <= 8192 and width * height <= MAX_PIXELS,
                "ORA canvas exceeds the pixel budget")
        layers = _layers(root)
        require(1 <= len(layers) <= 64, "ORA must contain 1..64 flat layers")
        return {"path": str(path), "sha256": file_sha(path), "bytes": path.stat().st_size,
                "canvas": [width, height], "layers": layers,
                "zip_entries": [entry.filename for entry in entries]}
    except (KeyError, ET.ParseError, ValueError) as exc:
        raise KritaRoundtripError("ORA stack metadata is invalid") from exc
    finally:
        archive.close()


def inspect_kra(path):
    path = Path(path).resolve()
    require(path.is_file() and path.suffix.lower() == ".kra", "Krita did not create a .kra file")
    archive, entries = _zip(path, "KRA")
    try:
        require("maindoc.xml" in archive.namelist(), "KRA lacks maindoc.xml")
        root = ET.fromstring(archive.read("maindoc.xml"))
        preview_name = next((name for name in ("mergedimage.png", "preview.png") if name in archive.namelist()), None)
        require(preview_name is not None, "KRA lacks a merged or preview PNG")
        return {"path": str(path), "sha256": file_sha(path), "bytes": path.stat().st_size,
                "layers": _layers(root), "preview": {"path": preview_name, "dimensions": _png_dimensions(archive.read(preview_name), preview_name)},
                "zip_entries": [entry.filename for entry in entries]}
    except (KeyError, ET.ParseError, ValueError) as exc:
        raise KritaRoundtripError("KRA metadata is invalid") from exc
    finally:
        archive.close()


def preflight(configured_krita=DEFAULT_KRITA):
    path = Path(configured_krita).expanduser().resolve()
    require(path.is_file() and path.suffix.lower() == ".exe", "Configured Krita executable is unavailable")
    return {"path": str(path), "sha256": file_sha(path), "timeout_seconds": TIMEOUT_SECONDS,
            "fixed_argv": ["<input>", "--export", "--export-filename", "<output>"],
            "execution_mode": "windows-batch-hidden"}


def command_for(krita_path, source, output):
    return [str(Path(krita_path).resolve()), str(Path(source).resolve()), "--export", "--export-filename", str(Path(output).resolve())]


def _write_log(path, command, completed=None, error=None):
    stdout = getattr(completed, "stdout", "") if completed is not None else getattr(error, "stdout", "")
    stderr = getattr(completed, "stderr", "") if completed is not None else getattr(error, "stderr", "")
    if isinstance(stdout, bytes): stdout = stdout.decode("utf-8", "replace")
    if isinstance(stderr, bytes): stderr = stderr.decode("utf-8", "replace")
    payload = {"argv": command, "returncode": getattr(completed, "returncode", None), "stdout": stdout or "", "stderr": stderr or ""}
    if error is not None: payload["error"] = str(error)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _export(runtime, source, output, log_path):
    command = command_for(runtime["path"], source, output)
    environment = os.environ.copy(); environment.pop("QT_QPA_PLATFORM", None)
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
    try:
        completed = subprocess.run(command, shell=False, cwd=str(Path(output).parent), env=environment,
                                   capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
                                   startupinfo=startupinfo, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        _write_log(log_path, command, error=exc)
        raise KritaRoundtripError(f"Krita batch export did not complete: {exc}") from exc
    _write_log(log_path, command, completed=completed)
    require(completed.returncode == 0, f"Krita batch export failed; see {Path(log_path).name}")
    require(Path(output).is_file(), f"Krita reported success without {Path(output).name}")


def execute(ora_path, output_root, configured_krita=DEFAULT_KRITA):
    """Use only a trusted configured executable; preserve a copied ORA and all logs on failure."""
    source_info = inspect_ora(ora_path)
    runtime = preflight(configured_krita)
    output = Path(output_root).resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / "source.ora"
    kra, png = output / "roundtrip.kra", output / "export.png"
    try:
        with Path(ora_path).open('rb') as stream:
            snapshot = stream.read(MAX_ORA_BYTES + 1)
        require(len(snapshot) <= MAX_ORA_BYTES, "ORA grew beyond the snapshot byte budget")
        source.write_bytes(snapshot)
        require(file_sha(source) == source_info['sha256'], "ORA changed while its snapshot was prepared; no Krita command was run")
        _export(runtime, source, kra, output / "ora-to-kra.log.json")
        kra_info = inspect_kra(kra)
        _export(runtime, kra, png, output / "kra-to-png.log.json")
        exported_dimensions = png_dimensions(png)
        require(exported_dimensions == source_info["canvas"], "Reopened KRA export changed canvas dimensions")
        result = {"schema_version": 1, "operation": "krita.ora-roundtrip.v1", "runtime": runtime,
                  "source": {**source_info, "snapshot": "source.ora"}, "kra": kra_info,
                  "export": {"path": "export.png", "sha256": file_sha(png), "bytes": png.stat().st_size,
                             "dimensions": exported_dimensions},
                  "native_kra_save_reopen_proved": True,
                  "limitations": ["ZIP and layer metadata plus dimensions were inspected; UI state and pixel/art acceptance were not assessed."]}
        (output / "roundtrip.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        return result
    except Exception as exc:
        (output / "failure.json").write_text(json.dumps({"error": str(exc), "source_sha256": source_info["sha256"]}, indent=2) + "\n", encoding="utf-8", newline="\n")
        if isinstance(exc, KritaRoundtripError): raise
        raise KritaRoundtripError(f"Krita roundtrip failed: {exc}") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preflight")
    run = commands.add_parser("roundtrip"); run.add_argument("ora"); run.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        value = preflight() if args.command == "preflight" else execute(args.ora, args.out)
        print(json.dumps(value, ensure_ascii=False, indent=2)); return 0
    except (KritaRoundtripError, OSError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
