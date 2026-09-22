"""Fail-closed, zero-authority binding of pose sources to native route contracts."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
import re
import warnings
from typing import Any

from PIL import Image, UnidentifiedImageError

from . import pose_artifact, pose_raster, pose_route_contract

REQUEST_SCHEMA = 'studio.pose-route-binding-request/v1'
BINDING_SCHEMA = 'studio.pose-route-binding/v1'
MAX_SOURCE_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 16_777_216

_HASH = re.compile(r'[0-9a-f]{64}\Z')
_ID = re.compile(r'[a-z0-9](?:[a-z0-9._-]{0,126}[a-z0-9])?\Z')
_COMPONENT_ID = re.compile(r'[a-z0-9](?:[a-z0-9._/-]{0,126}[a-z0-9])?\Z')
_COMMON_PINS = pose_route_contract.COMMON_PINS


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def _keys(value: Any, required: tuple[str, ...] | set[str] | frozenset[str], optional=()) -> None:
    if not isinstance(value, dict):
        raise ValueError('expected an object')
    required = set(required)
    allowed = required | set(optional)
    if required - set(value) or set(value) - allowed:
        raise ValueError('missing or unsupported fields')


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(label + ' must be a bounded lowercase identifier')
    return value


def _component_id(value: Any, label: str) -> str:
    if (not isinstance(value, str) or not _COMPONENT_ID.fullmatch(value) or
            '..' in value or '//' in value or value.startswith('/') or value.endswith('/')):
        raise ValueError(label + ' must be a bounded component identity')
    return value


def _sha256(value: Any, label='SHA-256') -> str:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise ValueError(label + ' must be lowercase SHA-256')
    return value


def _integer(value: Any, low: int, high: int, label: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(label + ' is outside its declared integer range')
    return value


def _number(value: Any, low: float, high: float, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(label + ' is outside its declared finite range')
    return float(value)


def _canvas(value: Any, label='canvas') -> dict[str, int]:
    _keys(value, ('width', 'height'))
    width = _integer(value['width'], 1, 8192, label + ' width')
    height = _integer(value['height'], 1, 8192, label + ' height')
    if width * height > MAX_PIXELS:
        raise ValueError(label + ' exceeds 16 megapixels')
    return {'width': width, 'height': height}


def expected_transform(kind: str, source: dict[str, int], target: dict[str, int]) -> dict[str, Any]:
    source = _canvas(source, 'transform source canvas')
    target = _canvas(target, 'transform target canvas')
    if kind == 'identity':
        if source != target:
            raise ValueError('identity transform requires equal source and target canvases')
        scaled = copy.deepcopy(source)
    elif kind == 'contain-pad':
        sw, sh = source['width'], source['height']
        tw, th = target['width'], target['height']
        if tw * sh <= th * sw:
            scaled = {'width': tw, 'height': max(1, sh * tw // sw)}
        else:
            scaled = {'width': max(1, sw * th // sh), 'height': th}
    else:
        raise ValueError('unsupported transform kind')
    horizontal = target['width'] - scaled['width']
    vertical = target['height'] - scaled['height']
    pad = {
        'left': horizontal // 2,
        'top': vertical // 2,
        'right': horizontal - horizontal // 2,
        'bottom': vertical - vertical // 2,
    }
    return {
        'kind': kind,
        'source_canvas': copy.deepcopy(source),
        'target_canvas': copy.deepcopy(target),
        'scaled_canvas': scaled,
        'pad': pad,
    }


def _transform(value: Any, source: dict[str, int], target: dict[str, int]) -> dict[str, Any]:
    _keys(value, ('kind', 'source_canvas', 'target_canvas', 'scaled_canvas', 'pad'))
    declared_source = _canvas(value['source_canvas'], 'transform source canvas')
    declared_target = _canvas(value['target_canvas'], 'transform target canvas')
    _canvas(value['scaled_canvas'], 'transform scaled canvas')
    _keys(value['pad'], ('left', 'top', 'right', 'bottom'))
    for key in ('left', 'top', 'right', 'bottom'):
        _integer(value['pad'][key], 0, 8192, 'transform padding')
    if declared_source != source or declared_target != target:
        raise ValueError('transform canvases disagree with source or route')
    expected = expected_transform(value['kind'], source, target)
    if value != expected:
        raise ValueError('transform declaration does not match the deterministic policy')
    return expected


def _image(data: bytes, expected: dict[str, Any], formats: tuple[str, ...], skeleton: bool) -> dict[str, Any]:
    if not isinstance(data, bytes) or not 1 <= len(data) <= MAX_SOURCE_BYTES:
        raise ValueError('source image must be bytes from 1 byte through 20 MiB')
    if hashlib.sha256(data).hexdigest() != expected['sha256'] or len(data) != expected['bytes']:
        raise ValueError('source image bytes do not match the declared identity')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if getattr(image, 'n_frames', 1) != 1:
                    raise ValueError('animated or multi-frame pose sources are unsupported')
                image_format = image.format
                width, height = image.size
                mode = image.mode
                if image_format not in formats or image_format != expected['format']:
                    raise ValueError('source image format does not match the declaration and route contract')
                if width * height > MAX_PIXELS:
                    raise ValueError('source image exceeds 16 megapixels')
                if {'width': width, 'height': height} != expected['canvas']:
                    raise ValueError('source image canvas does not match the declaration')
                if mode not in ('RGB', 'RGBA'):
                    raise ValueError('pose source must be RGB or RGBA without implicit conversion')
                if skeleton and (mode != 'RGB' or 'transparency' in image.info):
                    raise ValueError('precomputed skeleton guide must be opaque RGB')
                # Loading before reading EXIF also discovers PNG eXIf chunks placed
                # after IDAT; transform evidence must bind the visibly oriented file.
                image.load()
                if image.getexif().get(274, 1) != 1:
                    raise ValueError('pose source EXIF orientation must be identity')
                non_black = None
                if skeleton:
                    pixels = (image.get_flattened_data() if hasattr(image, 'get_flattened_data') else image.getdata())
                    non_black = sum(1 for pixel in pixels if pixel != (0, 0, 0))
                    if non_black == 0:
                        raise ValueError('precomputed skeleton guide is blank')
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ValueError('invalid or excessive source image') from exc
    return {
        'sha256': expected['sha256'],
        'bytes': expected['bytes'],
        'format': image_format,
        'canvas': {'width': width, 'height': height},
        'mode': mode,
        'non_black_pixels': non_black,
    }


def _route(value: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    _keys(value, ('id', 'mechanism', 'source_kind', 'detector_behavior',
                  'native_slot', 'backend_id', 'target_canvas', 'pins'))
    route_id = _identifier(value['id'], 'route id')
    spec = pose_route_contract.binding_projection(route_id)
    for key in ('mechanism', 'source_kind', 'detector_behavior', 'native_slot'):
        if value[key] != spec[key]:
            raise ValueError('route identity and native binding contract disagree')
    backend_id = pose_route_contract.validate_backend(route_id, value['backend_id'])
    target = _canvas(value['target_canvas'], 'route target canvas')
    pins = _COMMON_PINS | spec['pins']
    _keys(value['pins'], pins)
    normalized_pins = {key: _sha256(value['pins'][key], key + ' pin') for key in sorted(pins)}
    return ({
        'id': route_id,
        'mechanism': spec['mechanism'],
        'source_kind': spec['source_kind'],
        'detector_behavior': spec['detector_behavior'],
        'native_slot': spec['native_slot'],
        'backend_id': backend_id,
        'target_canvas': target,
        'pins': normalized_pins,
    }, spec)


def _filtered_joint_names(artifact: dict[str, Any], threshold: float) -> list[str]:
    names = []
    for name in pose_artifact.JOINTS:
        point = artifact['joints'][name]
        if point is None or (point['origin'] == 'estimated' and point['confidence'] < threshold):
            names.append(name)
    return names


def _drawable_limbs(artifact: dict[str, Any], threshold: float) -> int:
    visible = []
    for name in pose_artifact.JOINTS:
        point = artifact['joints'][name]
        visible.append(point is not None and not (
            point['origin'] == 'estimated' and point['confidence'] < threshold))
    return sum(1 for start, end in pose_raster.LIMBS if visible[start] and visible[end])


def validate_request(request: Any, *, artifact: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize a binding request without reading image bytes or granting execution."""
    _keys(request, ('schema', 'authority', 'execution_authorized', 'generation_submitted',
                    'binding_name', 'route', 'source', 'transform'))
    if (request['schema'] != REQUEST_SCHEMA or request['authority'] != 'none' or
            request['execution_authorized'] is not False or
            request['generation_submitted'] is not False):
        raise ValueError('binding requests have zero execution authority')
    route, spec = _route(request['route'])
    source = request['source']
    common = ('kind', 'sha256', 'bytes', 'format', 'canvas')
    if spec['source_kind'] == 'precomputed-skeleton':
        _keys(source, common + ('artifact_id', 'renderer_id', 'renderer_sha256',
                               'threshold', 'expected_filtered_joints'))
        if artifact is None:
            raise ValueError('precomputed skeleton routes require a pose artifact')
        pose = pose_artifact.validate(artifact)
        if _sha256(source['artifact_id'], 'artifact id') != pose['id']:
            raise ValueError('source artifact identity does not match the supplied artifact')
        renderer_id = _component_id(source['renderer_id'], 'renderer id')
        renderer_sha256 = _sha256(source['renderer_sha256'], 'renderer pin')
        if renderer_sha256 != route['pins']['renderer']:
            raise ValueError('source renderer identity does not match the route renderer pin')
        if (renderer_id in pose_raster.RENDERERS and
                renderer_sha256 != pose_raster.renderer_sha256(renderer_id)):
            raise ValueError('local preview renderer identity does not match the current Pillow/zlib encoder')
        threshold = _number(source['threshold'], 0, 1, 'joint threshold')
        if source['format'] != 'PNG':
            raise ValueError('precomputed skeleton routes require PNG bytes')
        canvas = _canvas(source['canvas'], 'source canvas')
        if canvas != pose['canvas']:
            raise ValueError('pose artifact and guide canvases disagree')
        filtered = _filtered_joint_names(pose, threshold)
        if source['expected_filtered_joints'] != filtered:
            raise ValueError('filtered-joint declaration is stale or reordered')
        if _drawable_limbs(pose, threshold) == 0:
            raise ValueError('pose artifact has no drawable limb at the declared threshold')
        normalized_source = {
            'kind': 'precomputed-skeleton',
            'sha256': _sha256(source['sha256']),
            'bytes': _integer(source['bytes'], 1, MAX_SOURCE_BYTES, 'source byte count'),
            'format': 'PNG',
            'canvas': canvas,
            'artifact_id': pose['id'],
            'renderer_id': renderer_id,
            'renderer_sha256': renderer_sha256,
            'threshold': threshold,
            'expected_filtered_joints': filtered,
        }
        normalized_artifact = pose
    else:
        _keys(source, common)
        if artifact is not None:
            raise ValueError('Copy Pose RGB binds donor pixels, not a COCO-18 artifact')
        if source['format'] not in spec['formats']:
            raise ValueError('RGB donor format is unsupported')
        normalized_source = {
            'kind': 'rgb-pose-donor',
            'sha256': _sha256(source['sha256']),
            'bytes': _integer(source['bytes'], 1, MAX_SOURCE_BYTES, 'source byte count'),
            'format': source['format'],
            'canvas': _canvas(source['canvas'], 'source canvas'),
        }
        normalized_artifact = None
    if source['kind'] != spec['source_kind']:
        raise ValueError('source kind does not match the route contract')
    transform = _transform(request['transform'], normalized_source['canvas'], route['target_canvas'])
    return {
        'schema': REQUEST_SCHEMA,
        'authority': 'none',
        'execution_authorized': False,
        'generation_submitted': False,
        'binding_name': _identifier(request['binding_name'], 'binding name'),
        'route': route,
        'source': normalized_source,
        'transform': transform,
        '_artifact': normalized_artifact,
        '_formats': spec['formats'],
    }


def compile_binding(request: Any, source_bytes: bytes, *, artifact: dict[str, Any] | None = None) -> dict[str, Any]:
    """Bind exact bytes and geometry to one native slot without preparing or executing a graph."""
    normalized = validate_request(request, artifact=artifact)
    pose = normalized.pop('_artifact')
    formats = normalized.pop('_formats')
    skeleton = normalized['source']['kind'] == 'precomputed-skeleton'
    image = _image(source_bytes, normalized['source'], formats, skeleton)
    diagnostics: dict[str, Any] = {
        'detector_invocations': 0,
        'graph_prepared': False,
        'route_qualified': False,
        'source_mode': image['mode'],
    }
    if skeleton:
        threshold = normalized['source']['threshold']
        filtered = normalized['source']['expected_filtered_joints']
        diagnostics.update({
            'filtered_joints': filtered,
            'drawable_limbs': _drawable_limbs(pose, threshold),
            'non_black_pixels': image['non_black_pixels'],
        })
        renderer_id = normalized['source']['renderer_id']
        if renderer_id in pose_raster.RENDERERS:
            expected_bytes = pose_raster.render_png(pose, threshold, renderer_id)
            if source_bytes != expected_bytes:
                raise ValueError('local preview renderer bytes do not match the pose artifact')
            diagnostics['renderer_validation'] = 'recomputed-exact'
            diagnostics['renderer_identity'] = pose_raster.renderer_identity(renderer_id)
        else:
            diagnostics['renderer_validation'] = 'receipt-bound-not-recomputed'
            diagnostics['renderer_identity'] = None
    else:
        diagnostics.update({
            'filtered_joints': [],
            'drawable_limbs': None,
            'non_black_pixels': None,
            'renderer_validation': 'not-applicable',
            'renderer_identity': None,
        })
    request_content = copy.deepcopy(normalized)
    request_sha256 = hashlib.sha256(canonical(request_content)).hexdigest()
    body = {
        'schema': BINDING_SCHEMA,
        'authority': 'none',
        'execution_authorized': False,
        'generation_submitted': False,
        'ready_for_execution': False,
        'binding_name': normalized['binding_name'],
        'route': normalized['route'],
        'source': normalized['source'],
        'transform': normalized['transform'],
        'request_sha256': request_sha256,
        'diagnostics': diagnostics,
    }
    result = copy.deepcopy(body)
    result['binding_id'] = hashlib.sha256(canonical(body)).hexdigest()
    return result


def validate_binding(binding: Any, request: Any, source_bytes: bytes,
                     *, artifact: dict[str, Any] | None = None) -> dict[str, Any]:
    expected = compile_binding(request, source_bytes, artifact=artifact)
    if not isinstance(binding, dict) or binding != expected:
        raise ValueError('binding does not match the exact request, source bytes and artifact')
    return copy.deepcopy(expected)
