"""Bounded, non-executing COCO-18 correction artifacts. Hashes are not approval."""
import copy
import hashlib
import json
import math
import re

MAX_BYTES = 1024 * 1024
SCHEMA = 'studio.pose-artifact/v1'
JOINTS = ('nose', 'neck', 'right_shoulder', 'right_elbow', 'right_wrist',
          'left_shoulder', 'left_elbow', 'left_wrist', 'right_hip', 'right_knee',
          'right_ankle', 'left_hip', 'left_knee', 'left_ankle', 'right_eye',
          'left_eye', 'right_ear', 'left_ear')
_HASH = re.compile(r'[0-9a-f]{64}\Z')


def _keys(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise ValueError('missing or unsupported fields')


def _number(value, low, high):
    if type(value) not in (int, float) or not low <= value <= high:
        raise ValueError('expected a finite number in the declared range')
    return float(value) if value else 0.0


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('expected an integer in the declared range')
    return value


def _canvas(width, height):
    _integer(width, 1, 8192); _integer(height, 1, 8192)
    if width * height > 16777216:
        raise ValueError('canvas exceeds 16 megapixels')
    return {'width': width, 'height': height}


def _hash(value):
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise ValueError('expected lowercase SHA-256')
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')


def loads(data):
    """Read bounded JSON without duplicate keys, nonfinite numbers or deep trees."""
    if not isinstance(data, bytes) or len(data) > MAX_BYTES:
        raise ValueError('JSON must be bytes, at most 1 MiB')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    def integer(text):
        if len(text) > 20: raise ValueError('integer literal too long')
        return int(text)
    def floating(text):
        result = float(text)
        if not math.isfinite(result): raise ValueError('nonfinite JSON number')
        return result
    def constant(text):
        raise ValueError('nonfinite JSON constant')
    try:
        value = json.loads(data.decode('utf-8'), object_pairs_hook=pairs, parse_int=integer,
                           parse_float=floating, parse_constant=constant)
        stack, count = [(value, 0)], 0
        while stack:
            item, depth = stack.pop(); count += 1
            if depth > 32 or count > 8192: raise ValueError('JSON structure too large')
            if isinstance(item, str) and len(item) > 16384: raise ValueError('JSON string too long')
            if isinstance(item, dict):
                stack.extend((x, depth + 1) for pair in item.items() for x in pair)
            elif isinstance(item, list): stack.extend((x, depth + 1) for x in item)
        return value
    except (UnicodeError, RecursionError, OverflowError) as exc:
        raise ValueError('invalid or excessive JSON') from exc


def _seal(content):
    result = copy.deepcopy(content)
    result['id'] = hashlib.sha256(canonical(content)).hexdigest()
    return result


def validate(artifact):
    """Validate content integrity, not source-image bytes, anatomy or human review."""
    _keys(artifact, ('schema', 'authority', 'review', 'source', 'canvas', 'joints', 'parent_id', 'id'))
    if artifact['schema'] != SCHEMA or artifact['authority'] != 'none' or artifact['review'] != 'unreviewed':
        raise ValueError('unsupported schema, authority or review state')
    _keys(artifact['canvas'], ('width', 'height'))
    canvas = _canvas(**artifact['canvas'])
    src = artifact['source']
    _keys(src, ('sha256', 'format', 'person_index', 'coordinate_space'))
    _hash(src['sha256']); _integer(src['person_index'], 0, 31)
    if src['format'] != 'openpose-coco18' or src['coordinate_space'] not in ('pixels', 'normalized'):
        raise ValueError('unsupported source format or coordinate space')
    if artifact['parent_id'] is not None: _hash(artifact['parent_id'])
    _keys(artifact['joints'], JOINTS)
    joints = {}
    for name in JOINTS:
        point = artifact['joints'][name]
        if point is None: joints[name] = None; continue
        _keys(point, ('x', 'y', 'confidence', 'origin'))
        x = _number(point['x'], 0, canvas['width']); y = _number(point['y'], 0, canvas['height'])
        if point['origin'] == 'manual' and point['confidence'] is None: confidence = None
        elif point['origin'] == 'estimated':
            confidence = _number(point['confidence'], 0, 1)
            if confidence == 0: raise ValueError('zero-confidence joints must be null')
        else: raise ValueError('manual joints have no detector confidence')
        joints[name] = dict(x=x, y=y, confidence=confidence, origin=point['origin'])
    content = dict(schema=SCHEMA, authority='none', review='unreviewed', source=copy.deepcopy(src),
                   canvas=canvas, joints=joints, parent_id=artifact['parent_id'])
    result = _seal(content)
    if _hash(artifact['id']) != result['id']: raise ValueError('artifact content hash mismatch')
    return result


def import_openpose(data, *, width, height, coordinate_space, person_index=None):
    """Import one explicit body; no automatic coordinate, layout or person guessing."""
    canvas = _canvas(width, height)
    if coordinate_space not in ('pixels', 'normalized'): raise ValueError('declare pixels or normalized coordinates')
    raw = loads(data)
    _keys(raw, ('people',), ('version', 'canvas_width', 'canvas_height'))
    for key, expected in (('canvas_width', width), ('canvas_height', height)):
        if key in raw and (type(raw[key]) is not int or raw[key] != expected):
            raise ValueError('source canvas mismatch')
    people = raw['people']
    if not isinstance(people, list) or not 1 <= len(people) <= 32: raise ValueError('expected 1..32 people')
    if person_index is None:
        if len(people) != 1: raise ValueError('select a person explicitly')
        person_index = 0
    _integer(person_index, 0, len(people) - 1)
    person = people[person_index]
    extras = ('face_keypoints_2d', 'hand_left_keypoints_2d', 'hand_right_keypoints_2d', 'pose_keypoints_3d',
              'face_keypoints_3d', 'hand_left_keypoints_3d', 'hand_right_keypoints_3d')
    _keys(person, ('pose_keypoints_2d',), (*extras, 'person_id'))
    if any(key in person and person[key] != [] for key in extras):
        raise ValueError('body-only import refuses populated hand, face or 3D channels')
    points = person['pose_keypoints_2d']
    if not isinstance(points, list) or len(points) != 54: raise ValueError('COCO-18 requires exactly 54 values')
    joints = {}
    for i, name in enumerate(JOINTS):
        x, y, score = points[3 * i:3 * i + 3]
        x = _number(x, 0, 1 if coordinate_space == 'normalized' else width)
        y = _number(y, 0, 1 if coordinate_space == 'normalized' else height)
        score = _number(score, 0, 1)
        if coordinate_space == 'normalized': x *= width; y *= height
        joints[name] = dict(x=x, y=y, confidence=score, origin='estimated') if score else None
    return _seal(dict(schema=SCHEMA, authority='none', review='unreviewed', canvas=canvas, joints=joints,
                      source=dict(sha256=hashlib.sha256(data).hexdigest(), format='openpose-coco18',
                                  person_index=person_index, coordinate_space=coordinate_space), parent_id=None))


def revise(artifact, expected_id, edits):
    """Apply a complete edit batch or refuse it; never mutate the parent artifact."""
    result = validate(artifact)
    if expected_id != result['id']: raise ValueError('stale expected artifact ID')
    if not isinstance(edits, dict) or len(edits) > 18 or set(edits) - set(JOINTS):
        raise ValueError('edits must name unique COCO-18 joints')
    before = copy.deepcopy(result['joints'])
    for name, position in edits.items():
        if position is None: result['joints'][name] = None; continue
        if not isinstance(position, list) or len(position) != 2: raise ValueError('joint edit must be [x,y] or null')
        x = _number(position[0], 0, result['canvas']['width'])
        y = _number(position[1], 0, result['canvas']['height'])
        result['joints'][name] = dict(x=x, y=y, confidence=None, origin='manual')
    if before == result['joints']: return result
    result['parent_id'] = result.pop('id')
    return _seal(result)


def export_openpose(artifact, threshold=.3):
    """Lossy interchange: manual joint confidence 1 is presence, not estimation."""
    a = validate(artifact); threshold = _number(threshold, 0, 1)
    points = []
    for point in a['joints'].values():
        if point is None or (point['origin'] == 'estimated' and point['confidence'] < threshold):
            points.extend([0, 0, 0])
        else: points.extend([point['x'], point['y'], 1. if point['origin'] == 'manual' else point['confidence']])
    return dict(version=1.3, canvas_width=a['canvas']['width'], canvas_height=a['canvas']['height'],
                people=[dict(pose_keypoints_2d=points, face_keypoints_2d=[],
                             hand_left_keypoints_2d=[], hand_right_keypoints_2d=[])])
