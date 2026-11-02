"""Offline DCC observations and probe intents. No native execution or acceptance.

Exact equality covers recorded fields only. Capture contracts are declarations,
not independent proof that a renderer followed them. This is not a GLB semantic
mapper, aesthetic critic, OS sandbox or replacement for resource admission.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path, PurePosixPath
import hashlib
import re

from PIL import ImageChops, ImageStat
from .core import canonical, decode, digest, need
from .image_limits import open_bounded
from .research_intake import read_bytes, sha

SCENE = 'studio.dcc-scene/v1'
EVIDENCE = 'studio.dcc-evidence/v1'
MAX_VIEWS, MAX_PIXELS, MAX_ARTIFACT = 16, 1024 * 1024, 16 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]


def _sha(value):
    return isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value) is not None


def _ids(values):
    need(isinstance(values, list) and 1 <= len(values) <= MAX_VIEWS
         and all(isinstance(v, str) and re.fullmatch('[a-z][a-z0-9_-]{0,63}', v) for v in values)
         and len(values) == len(set(values)), 'Expected unique, bounded view IDs')


def _scene(value):
    need(isinstance(value, dict) and value.get('format') == SCENE, 'Unknown scene observation')
    need(type(value.get('complete')) is bool, 'Scene completeness must be explicit')
    content = value.get('content')
    need(isinstance(content, dict) and set(content) == {'objects', 'actions', 'images'}
         and all(isinstance(v, dict) and len(v) <= 2048 for v in content.values()), 'Invalid scene content')
    need(content['objects'], 'Empty object observation is insufficient for asset comparison')
    need(isinstance(value.get('findings'), list) and isinstance(value.get('limitations'), list),
         'Scene findings and limitations are required')
    # Reuse LAS finite JSON/depth/size rules even for the direct Python API.
    decode(canonical(value))
    return value


def compare_scenes(before: dict, after: dict) -> dict:
    before, after = _scene(before), _scene(after)
    changes = []
    def walk(a, b, path=''):
        if len(changes) >= 256:
            return
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(a.keys() | b.keys()):
                pointer = path + '/' + key.replace('~', '~0').replace('/', '~1')
                if key not in a or key not in b:
                    changes.append({'path': pointer, 'kind': 'added' if key not in a else 'removed'})
                else:
                    walk(a[key], b[key], pointer)
                if len(changes) >= 256:
                    break
        elif canonical(a) != canonical(b):
            changes.append({'path': path, 'kind': 'changed',
                            'before_sha256': digest(a), 'after_sha256': digest(b)})
    walk(before['content'], after['content'])
    equal = canonical(before['content']) == canonical(after['content'])
    return {'equal': equal, 'complete': before['complete'] and after['complete'],
            'changes': changes, 'change_list_may_be_truncated': len(changes) >= 256,
            'before_sha256': digest(before['content']), 'after_sha256': digest(after['content']),
            'findings': {'before': before['findings'], 'after': after['findings']},
            'limitations': sorted(set(map(str, before['limitations'] + after['limitations']))),
            'scope': 'Recorded base-scene fields only; not evaluated geometry or visual parity.'}


def _artifact(root: Path, record: dict, suffix: str) -> bytes:
    need(isinstance(record, dict) and set(record) == {'path', 'sha256'} and _sha(record['sha256']),
         'Invalid artifact record')
    name = record['path']
    need(isinstance(name, str) and name and '\\' not in name and ':' not in name, 'Unsafe artifact path')
    relative = PurePosixPath(name)
    need(not relative.is_absolute() and relative.as_posix() == name
         and all(part not in {'.', '..'} for part in relative.parts)
         and relative.suffix.lower() == suffix, 'Unsafe or unexpected artifact path')
    path = root
    for part in relative.parts:
        path = path / part
        need(not path.is_symlink(), 'Symlink artifact refused')
    need(path.is_file(), 'Missing artifact: ' + name)
    with path.open('rb') as stream:
        raw = stream.read(MAX_ARTIFACT + 1)
    need(len(raw) <= MAX_ARTIFACT, 'Artifact exceeds bounded read limit')
    need(sha(raw) == record['sha256'], 'Artifact hash mismatch: ' + name)
    return raw


def _bundle(root: Path):
    need(not root.is_symlink() and root.is_dir(), 'Expected an evidence directory')
    value = decode(read_bytes(root / 'evidence.json'))
    need(isinstance(value, dict) and value.get('format') == EVIDENCE, 'Unknown evidence format')
    contract = value.get('capture_contract')
    need(isinstance(contract, dict) and set(contract) ==
         {'view_ids', 'resolution', 'camera_rig_sha256', 'render_settings'}, 'Invalid capture contract')
    _ids(contract['view_ids'])
    resolution = contract['resolution']
    need(isinstance(resolution, list) and len(resolution) == 2
         and all(type(n) is int and 1 <= n <= 4096 for n in resolution)
         and resolution[0] * resolution[1] <= MAX_PIXELS, 'Invalid capture resolution')
    need(_sha(contract['camera_rig_sha256']) and isinstance(contract['render_settings'], dict)
         and contract['render_settings'], 'Missing camera/render contract')
    views = value.get('views')
    need(isinstance(views, dict) and len(views) <= MAX_VIEWS
         and set(views) <= set(contract['view_ids']), 'Unexpected capture views')
    observed = _scene(decode(_artifact(root, value.get('scene'), '.json')))
    return value, observed


def _png_sample_depth(raw: bytes):
    """Bounded framing only: Pillow may accept a late/repeated IHDR or expose RGB16 as RGB8."""
    refusal = 'PNG evidence requires one canonical first IHDR and complete chunk framing'
    need(len(raw) <= MAX_ARTIFACT, 'PNG exceeds bounded artifact limit')
    need(raw[:8] == b'\x89PNG\r\n\x1a\n' and raw[8:16] == b'\x00\x00\x00\rIHDR', refusal)
    position = 8
    while position + 12 <= len(raw):
        length = int.from_bytes(raw[position:position + 4], 'big')
        kind = raw[position + 4:position + 8]
        end = position + length + 12
        need(end <= len(raw) and (kind != b'IHDR' or position == 8), refusal)
        if kind == b'IEND':
            need(length == 0, refusal)
            return raw[24]
        position = end
    raise ValueError(refusal)


def _pixels(raw: bytes, resolution):
    need(_png_sample_depth(raw) == 8, 'Expected single-frame 8-bit RGB/RGBA PNG')
    with open_bounded(BytesIO(raw)) as image:
        need(image.format == 'PNG' and image.mode in {'RGB', 'RGBA'}
             and getattr(image, 'n_frames', 1) == 1, 'Expected single-frame 8-bit RGB/RGBA PNG')
        need(list(image.size) == resolution, 'Image resolution differs from capture contract')
        return image.convert('RGBA')


def _image_delta(a: bytes, b: bytes, resolution):
    left, right = _pixels(a, resolution), _pixels(b, resolution)
    try:
        delta = ImageChops.difference(left, right)
        extrema = delta.getextrema()
        maximum = max(hi for lo, hi in extrema)
        mean = sum(ImageStat.Stat(delta).mean) / 4
        channels = delta.split()
        mask = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]),
                                  ImageChops.lighter(channels[2], channels[3]))
        changed = 1 - mask.histogram()[0] / (resolution[0] * resolution[1])
        return {'max_channel_delta': maximum, 'mean_absolute_channel_delta': mean,
                'changed_pixel_fraction': changed}
    finally:
        left.close(); right.close()


def compare_bundles(before: Path, after: Path, required_views: list[str], holdout_views: list[str],
                    max_channel_delta: int = 0) -> dict:
    _ids(required_views); _ids(holdout_views)
    need(set(holdout_views) <= set(required_views), 'Holdout views must be required')
    need(type(max_channel_delta) is int and 0 <= max_channel_delta <= 255, 'Invalid pixel tolerance')
    a, scene_a = _bundle(before); b, scene_b = _bundle(after)
    structure = compare_scenes(scene_a, scene_b)
    result = {'format': 'studio.dcc-comparison/v1', 'status': 'incomplete', 'structure': structure,
              'before_evidence_sha256': digest(a), 'after_evidence_sha256': digest(b), 'views': {},
              'policy': {'required_views': required_views, 'holdout_views': holdout_views,
                         'max_channel_delta': max_channel_delta},
              'baseline_promoted': False,
              'acceptance': {'artistic': 'not_evaluated', 'native_execution': 'not_attested',
                             'distribution': 'not_evaluated', 'visual_parity': 'not_established'},
              'notice': 'Exact RGBA comparison includes hidden RGB under transparency. '
                        'Holdout is a declared role, not an access-control boundary.'}
    missing = sorted(set(required_views) - (a['views'].keys() & b['views'].keys()))
    if missing or not structure['complete']:
        result['reason'] = {'missing_views': missing, 'complete_scene_observations': structure['complete']}
        return result
    if canonical(a['capture_contract']) != canonical(b['capture_contract']):
        result.update(status='incomparable', reason='Capture contracts differ; do not resize or normalize silently.')
        return result
    for name in required_views:
        pixels = _image_delta(_artifact(before, a['views'][name], '.png'),
                              _artifact(after, b['views'][name], '.png'), a['capture_contract']['resolution'])
        pixels.update(role='holdout' if name in holdout_views else 'review',
                      within_tolerance=pixels['max_channel_delta'] <= max_channel_delta)
        result['views'][name] = pixels
    match = (structure['equal'] and not scene_a['findings'] and not scene_b['findings']
             and all(v['within_tolerance'] for v in result['views'].values()))
    result['status'] = 'within_declared_tolerance' if match else 'different'
    return result


def pin_file(path: Path, limit: int = 2 * 1024**3) -> dict:
    """Stream a bounded explicit file; no PATH lookup. Detect changes while hashing."""
    need(not path.is_symlink() and path.is_file(), 'Expected an explicit regular file')
    before = path.stat()
    need(before.st_size <= limit, 'Input exceeds pinning size budget')
    checksum, total = hashlib.sha256(), 0
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            total += len(chunk); need(total <= limit, 'Input exceeds pinning size budget')
            checksum.update(chunk)
    after = path.stat()
    need((before.st_size, before.st_mtime_ns, before.st_ino) ==
         (after.st_size, after.st_mtime_ns, after.st_ino) and total == after.st_size,
         'Input changed while pinning')
    return {'path': str(path.resolve()), 'bytes': total, 'sha256': checksum.hexdigest()}


def probe_intent(config_path: Path, source: Path, destination: Path) -> dict:
    config_bytes = read_bytes(config_path)
    config = decode(config_bytes)
    need(isinstance(config, dict) and isinstance(config.get('blender'), str), 'Configured blender path required')
    executable = Path(config['blender'])
    need(executable.is_absolute(), 'Blender executable must be explicitly absolute; no PATH lookup')
    need(source.suffix.lower() == '.blend', 'Probe source must be a .blend copy')
    need(not destination.exists() and not destination.is_symlink() and destination.parent.is_dir(),
         'Choose a new output directory with an existing parent')
    tool = ROOT / 'scripts' / 'blender_lab_bpy.py'  # the one Blender entry point; scene-v1 runs the exact collector
    pins = {key: pin_file(path) for key, path in
            [('source', source), ('blender', executable), ('probe', tool),
             ('collector', ROOT / 'scripts' / 'blender_scene_probe.py')]}
    output = str(destination.resolve() / 'scene.json')
    result = {'format': 'studio.dcc-probe-intent/v1', 'executable': False, 'process_started': False,
              **pins, 'config_sha256': sha(config_bytes), 'output': output,
              'argv': [pins['blender']['path'], '--background', '--factory-startup', '--disable-autoexec',
                       '--python-exit-code', '1', '--python', pins['probe']['path'], '--',
                       'scene-v1', '--blend', pins['source']['path'], '--out', output],
              'requires': ['Recheck all pins immediately before execution',
                           'Existing LAS resource admission or explicit bounded native admission',
                           'Timeout and native stdout/stderr retention'],
              'limits': {'timeout_seconds': 120, 'probe_scalar_budget': 20000000,
                         'output_json_bytes': 1048576},
              'notice': 'Planning does not execute Blender, reserve resources, or attest installed compatibility.'}
    result['plan_sha256'] = digest(result)
    return result
