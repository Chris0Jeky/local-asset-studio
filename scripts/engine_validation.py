"""Bounded local engine evidence helpers; no installation, model calls or shell."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import time
from typing import Any

MAX_GLB_BYTES = 128 * 1024**2
MAX_JSON_BYTES = 4 * 1024**2
MAX_LOG_BYTES = 4 * 1024**2
MAX_PIXELS = 40_000_000
MAX_FRAME_PIXELS = 80_000_000
VALIDATOR_VERSION = '2.0.0-dev.3.10'


class EvidenceError(ValueError):
    """An unavailable tool, failed contract, changed input or incomplete execution."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def file_sha(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024**2), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'Duplicate JSON key: ' + key)
        value[key] = item
    return value


def _constant(value):
    raise EvidenceError('Non-finite JSON number: ' + value)


def parse_json(data: bytes | str):
    try:
        return json.loads(data, object_pairs_hook=_object, parse_constant=_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise EvidenceError('Invalid evidence JSON: ' + str(exc)[:200]) from exc


def read_json(path: str | Path):
    with Path(path).open('rb') as stream:
        data = stream.read(MAX_JSON_BYTES + 1)
    require(len(data) <= MAX_JSON_BYTES, 'JSON exceeds 4 MiB')
    return parse_json(data)


def write_json(path: Path, value: Any) -> None:
    """Publish a new evidence file; never replace an earlier receipt."""
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def inspect_glb(path: str | Path) -> dict[str, Any]:
    """Container/intake checks, NOT a substitute for the Khronos validator.

    The supported intake is a self-contained GLB v2: JSON + optional BIN, no URI
    references (including data URIs), at most 2048 nodes and 32 animation clips.
    """
    path = Path(path)
    require(path.is_file() and 20 <= path.stat().st_size <= MAX_GLB_BYTES,
            'GLB must be a nonempty file under 128 MiB')
    with path.open('rb') as stream:
        data = stream.read(MAX_GLB_BYTES + 1)
    require(len(data) <= MAX_GLB_BYTES, 'GLB exceeds 128 MiB')
    magic, version, length = struct.unpack_from('<4sII', data)
    require(magic == b'glTF' and version == 2 and length == len(data), 'Invalid GLB v2 header or byte length')
    cursor = 12
    chunks = []
    while cursor < len(data):
        require(cursor + 8 <= len(data), 'Truncated GLB chunk header')
        size, kind = struct.unpack_from('<II', data, cursor)
        cursor += 8
        require(size % 4 == 0 and cursor + size <= len(data), 'Invalid GLB chunk extent or alignment')
        chunks.append((kind, cursor, size))
        cursor += size
    require([c[0] for c in chunks] in ([0x4e4f534a], [0x4e4f534a, 0x004e4942]),
            'Supported GLB requires one JSON chunk followed by at most one BIN chunk')
    _, start, size = chunks[0]
    require(size <= MAX_JSON_BYTES, 'GLB JSON exceeds 4 MiB')
    doc = parse_json(data[start:start + size])
    require(isinstance(doc, dict) and isinstance(doc.get('asset'), dict)
            and doc['asset'].get('version') == '2.0', 'GLB asset.version must be 2.0')
    pending = [doc]
    visited = 0
    while pending:
        item = pending.pop(); visited += 1
        require(visited <= 250_000, 'GLB JSON complexity exceeds intake limit')
        if isinstance(item, dict):
            require('uri' not in item, 'Self-contained GLB required: URI resources are not loaded')
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
        elif isinstance(item, float):
            require(math.isfinite(item), 'GLB contains a non-finite number')
    arrays = {}
    for key, limit in (('nodes', 2048), ('meshes', 2048), ('materials', 512), ('skins', 128), ('animations', 32)):
        values = doc.get(key, [])
        require(isinstance(values, list) and len(values) <= limit and all(isinstance(v, dict) for v in values),
                f'Invalid or over-budget GLB {key}')
        arrays[key] = values
    return {'scope': 'container-and-self-contained-intake', 'sha256': hashlib.sha256(data).hexdigest(),
            'bytes': len(data), 'nodes': [{'index': i, 'name': n.get('name'),
                'translation': n.get('translation'), 'rotation': n.get('rotation'),
                'scale': n.get('scale'), 'matrix': n.get('matrix'), 'skin': n.get('skin')}
                for i, n in enumerate(arrays['nodes'])],
            'meshes': [{'index': i, 'name': n.get('name')} for i, n in enumerate(arrays['meshes'])],
            'materials': [{'index': i, 'name': n.get('name'), 'pbrMetallicRoughness': n.get('pbrMetallicRoughness'),
                'normalTexture': n.get('normalTexture'), 'occlusionTexture': n.get('occlusionTexture'),
                'emissiveTexture': n.get('emissiveTexture')} for i, n in enumerate(arrays['materials'])],
            'skins': [{'index': i, 'name': n.get('name'), 'joints': n.get('joints')} for i, n in enumerate(arrays['skins'])],
            'animations': [{'index': i, 'name': n.get('name'), 'channels': n.get('channels')}
                for i, n in enumerate(arrays['animations'])],
            'extensions_used': doc.get('extensionsUsed', []),
            'not_established': ['specification-validity', 'engine-import', 'art', 'rights', 'gameplay']}


def atlas_evidence(path: Path, manifest: dict) -> dict:
    from PIL import Image, UnidentifiedImageError
    try:
        with Image.open(path) as source:
            require(source.format == 'PNG' and getattr(source, 'n_frames', 1) == 1, 'Atlas must be a single PNG')
            require(source.width * source.height <= MAX_PIXELS, 'Atlas exceeds the 40 megapixel decode budget')
            require(sum(f['region'][2] * f['region'][3] for f in manifest['frames']) <= MAX_FRAME_PIXELS,
                    'Atlas frame inspection exceeds 80 megapixels')
            source.load()
            image = source.convert('RGBA')
        frames = []
        with image:
            for frame in manifest['frames']:
                x, y, width, height = frame['region']
                require(x + width <= image.width and y + height <= image.height, 'Atlas frame lies outside its image')
                with image.crop((x, y, x + width, y + height)) as crop:
                    with crop.getchannel('A') as alpha:
                        histogram = alpha.histogram()
                        frames.append({'alpha_pixels': sum(histogram[1:]), 'bounds': list(alpha.getbbox() or [])})
            return {'width': image.width, 'height': image.height, 'frames': frames, 'sha256': file_sha(path)}
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as exc:
        raise EvidenceError('Invalid atlas PNG: ' + str(exc)[:200]) from exc


def run_command(argv: list[str], directory: Path, label: str, timeout: float) -> dict:
    """Run only our child; retain bounded stdout/stderr on failure and timeout."""
    require(math.isfinite(timeout) and timeout > 0, 'Execution time budget exhausted')
    require(label.replace('-', '').isalnum(), 'Invalid command evidence label')
    stdout_path = directory / (label + '-stdout.log')
    stderr_path = directory / (label + '-stderr.log')
    env = dict(os.environ)
    env.pop('NODE_OPTIONS', None); env.pop('NODE_PATH', None)
    start = time.monotonic()
    state, code = 'failed', None
    failure = None
    with stdout_path.open('xb') as out, stderr_path.open('xb') as err:
        child = subprocess.Popen(argv, cwd=directory, env=env, stdin=subprocess.DEVNULL,
                                 stdout=out, stderr=err, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            while True:
                code = child.poll()
                if max(stdout_path.stat().st_size, stderr_path.stat().st_size) > MAX_LOG_BYTES:
                    raise EvidenceError('Child log exceeds the 4 MiB budget')
                if code is not None:
                    require(code == 0, f'{label} exited with code {code}; logs retained')
                    state = 'completed'; break
                require(time.monotonic() - start < timeout, f'{label} timed out; owned child stopped, logs retained')
                time.sleep(0.02)
        except BaseException as exc:
            failure = exc
        finally:
            if child.poll() is None:
                child.kill()
            code = child.wait(timeout=10)
    receipt = {'argv': argv, 'state': state, 'returncode': code, 'wall_seconds': time.monotonic() - start,
               'stdout_path': stdout_path.name, 'stderr_path': stderr_path.name}
    write_json(directory / (label + '-exit.json'), receipt)
    if failure:
        raise failure
    receipt['stdout'] = stdout_path.read_bytes()[:MAX_LOG_BYTES].decode('utf-8', errors='replace')
    receipt['stderr'] = stderr_path.read_bytes()[:MAX_LOG_BYTES].decode('utf-8', errors='replace')
    return receipt


def validate_glb(path: Path, node_path: str | Path | None, directory: Path, timeout: float = 60) -> dict:
    """Run the official pinned npm validator. Dependencies are installed explicitly."""
    source = inspect_glb(path)
    require(node_path is not None, 'GLB engine verification needs an explicit Node executable: set node in config/local.json or pass --node')
    node = Path(node_path).expanduser()
    require(node.is_absolute() and node.is_file(), 'Node executable must be an existing absolute path')
    node = node.resolve()
    bridge = Path(__file__).resolve().parents[1] / 'tools/gltf-validation/validate.cjs'
    package = bridge.parent / 'node_modules/gltf-validator/package.json'
    require(package.is_file(), 'Install the pinned validator explicitly: npm ci --prefix tools/gltf-validation --ignore-scripts')
    metadata = read_json(package)
    require(metadata.get('name') == 'gltf-validator' and metadata.get('version') == VALIDATOR_VERSION,
            'Installed Khronos validator differs from the pinned version')
    result = run_command([str(node), '--max-old-space-size=512', str(bridge), str(path.resolve())],
                         directory, 'khronos', timeout)
    report = parse_json(result['stdout'])
    write_json(directory / 'khronos-report.json', report)
    require(isinstance(report, dict) and report.get('validatorVersion') == VALIDATOR_VERSION,
            'Validator did not return its pinned identity')
    require(report.get('sourceSha256') == source['sha256'] == file_sha(path), 'GLB bytes changed during validation')
    issues = report.get('issues')
    require(isinstance(issues, dict) and type(issues.get('numErrors')) is int,
            'Khronos report is incomplete')
    require(issues['numErrors'] == 0 and issues.get('truncated') is False,
            'Khronos validation failed or report was truncated; inspect khronos-report.json')
    return {'state': 'validated', 'source': source, 'validator_version': VALIDATOR_VERSION,
            'node_sha256': file_sha(node), 'bridge_sha256': file_sha(bridge),
            'report': report, 'wall_seconds': result['wall_seconds']}
