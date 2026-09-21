"""Normalize retained Civitai metadata and gallery composition evidence offline."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime
import json
import math
from pathlib import Path, PurePosixPath
import re
from typing import Any

from .core import canonical, decode, digest, need

INPUT_FORMAT = 'studio.civitai-composition-input/v1'
REPORT_FORMAT = 'studio.source-composition-evidence/v1'
HOSTS = {'civitai.com', 'civitai.red'}
OUTCOMES = {'ok', 'filtered', 'blocked'}
AUTH_CONTEXTS = {'anonymous', 'credentialed'}
MAX_PAGES = 32
MAX_IMAGES = 1000
MAX_FILES = 256
MAX_RESOURCES = 128
MAX_QUERY = 64
MAX_BYTES = (1 << 63) - 1
SHA256 = re.compile(r'[a-fA-F0-9]{64}\Z')
VERSION_ROUTE = re.compile(r'/api/v1/model-versions/([1-9][0-9]{0,19})\Z')
AIR = re.compile(
    r'urn:air:[a-z0-9][a-z0-9._-]{0,63}:[a-z0-9][a-z0-9._-]{0,63}:'
    r'civitai:([1-9][0-9]{0,19})@([1-9][0-9]{0,19})\Z', re.IGNORECASE)
SENSITIVE_QUERY = {'apikey', 'api_key', 'api-key', 'token', 'access_token',
                   'access-token', 'authorization', 'key'}
REACTIONS = {'cryCount', 'laughCount', 'likeCount', 'dislikeCount', 'heartCount'}


def text(value: Any, limit: int = 300) -> bool:
    return isinstance(value, str) and 0 < len(value) <= limit and '\x00' not in value


def token(value: Any, limit: int = 300) -> bool:
    return text(value, limit) and value.strip() == value and not any(ch in value for ch in '\r\n\t')


def positive(value: Any, label: str, *, optional: bool = False) -> int | None:
    if value is None and optional: return None
    need(type(value) is int and value > 0, label + ' must be a positive integer')
    return value


def optional_text(value: Any, label: str, limit: int = 1000) -> str | None:
    if value is None: return None
    need(token(value, limit), 'Invalid ' + label)
    return value


def iso(value: Any, label: str) -> str:
    need(token(value, 64), 'Invalid ' + label)
    try: datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc: raise ValueError('Invalid ' + label) from exc
    return value


def sha256(value: Any, label: str) -> str:
    need(isinstance(value, str) and SHA256.fullmatch(value), label + ' must be SHA-256')
    return value.casefold()


def query_scalar(value: Any) -> Any:
    if isinstance(value, bool) or type(value) is int: return value
    if isinstance(value, str):
        need(len(value) <= 1000 and '\x00' not in value and '\r' not in value and '\n' not in value,
             'Invalid source query value')
        return value
    raise ValueError('Invalid source query value')


def normalize_query(value: Any) -> dict[str, Any]:
    need(isinstance(value, dict) and len(value) <= MAX_QUERY, 'Source query must be a bounded object')
    result: dict[str, Any] = {}
    for key, raw in value.items():
        need(token(key, 128), 'Invalid source query key')
        folded = key.casefold()
        need(folded not in SENSITIVE_QUERY and not folded.startswith('authorization'),
             'Source receipt cannot retain a sensitive query parameter')
        if isinstance(raw, list):
            need(len(raw) <= 64, 'Source query list is oversized')
            item = [query_scalar(entry) for entry in raw]
        else: item = query_scalar(raw)
        result[key] = item
    return {key: result[key] for key in sorted(result)}


def normalize_receipt(value: Any) -> dict[str, Any]:
    fields = {'host', 'route', 'query', 'retrieved_at', 'response_sha256', 'etag',
              'last_modified', 'outcome', 'auth_context'}
    need(isinstance(value, dict) and set(value) == fields, 'Invalid retained source receipt')
    need(value['host'] in HOSTS, 'Unsupported Civitai source host')
    need(token(value['route'], 500) and value['route'].startswith('/') and '?' not in value['route']
         and '..' not in PurePosixPath(value['route']).parts, 'Invalid source route')
    need(value['outcome'] in OUTCOMES, 'Invalid source outcome')
    need(value['auth_context'] in AUTH_CONTEXTS, 'Invalid source authentication context')
    return {'host': value['host'], 'route': value['route'],
            'query': normalize_query(value['query']),
            'retrieved_at': iso(value['retrieved_at'], 'retrieval time'),
            'response_sha256': sha256(value['response_sha256'], 'Response identity'),
            'etag': optional_text(value['etag'], 'ETag', 1000),
            'last_modified': optional_text(value['last_modified'], 'Last-Modified', 1000),
            'outcome': value['outcome'], 'auth_context': value['auth_context']}


def snapshot(value: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    need(isinstance(value, dict) and set(value) == {'receipt', 'payload'}, 'Invalid retained snapshot')
    receipt = normalize_receipt(value['receipt'])
    need(isinstance(value['payload'], dict), 'Retained provider payload must be an object')
    return receipt, copy.deepcopy(value['payload'])


def safe_file_name(value: Any) -> str:
    need(token(value, 1024) and '\\' not in value and ':' not in value, 'Unsafe Civitai file name')
    path = PurePosixPath(value)
    need(not path.is_absolute() and all(part not in ('', '.', '..') for part in path.parts),
         'Unsafe Civitai file name')
    return path.as_posix()


def bounded_strings(value: Any, label: str, maximum: int = 256) -> list[str]:
    if value is None: return []
    need(isinstance(value, list) and len(value) <= maximum, label + ' must be a bounded list')
    result, seen = [], set()
    for item in value:
        need(token(item, 1000), 'Invalid ' + label)
        if item not in seen: seen.add(item); result.append(item)
    return result


def provider_hashes(value: Any, label: str) -> dict[str, str]:
    if value is None: return {}
    need(isinstance(value, dict) and len(value) <= 32, label + ' hashes must be a bounded object')
    result: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        need(token(raw_key, 64) and token(raw_value, 256), 'Invalid ' + label + ' hash')
        key = raw_key.casefold(); need(key not in result, 'Duplicate ' + label + ' hash')
        result[key] = raw_value.casefold() if key == 'sha256' else raw_value
    if 'sha256' in result: result['sha256'] = sha256(result['sha256'], label + ' SHA-256')
    return result


def file_facts(raw: Any, version_id: int, seen_ids: set[int]) -> dict[str, Any]:
    need(isinstance(raw, dict), 'Civitai file record must be an object')
    file_id = positive(raw.get('id'), 'Civitai file ID')
    need(file_id not in seen_ids, 'Civitai response contains duplicate file ID'); seen_ids.add(file_id)
    name = safe_file_name(raw.get('name')); size = raw.get('sizeKB')
    need(type(size) in (int, float) and not isinstance(size, bool) and math.isfinite(float(size))
         and 0 < float(size) <= MAX_BYTES / 1024, 'Civitai file sizeKB must be positive, finite, and bounded')
    byte_count = int(round(float(size) * 1024)); need(0 < byte_count <= MAX_BYTES, 'Invalid Civitai file byte count')
    hashes = provider_hashes(raw.get('hashes'), name); metadata = raw.get('metadata')
    need(metadata is None or isinstance(metadata, dict), 'Civitai file metadata must be an object'); metadata = metadata or {}
    return {'provider_file_id': file_id, 'identity': 'sha256:' + hashes['sha256'] if 'sha256' in hashes
            else f'civitai-file:{version_id}/{file_id}', 'name': name, 'bytes': byte_count,
            'file_type': optional_text(raw.get('type'), 'file type', 200), 'primary': raw.get('primary') is True,
            'format': optional_text(metadata.get('format'), 'file format', 200),
            'precision': optional_text(metadata.get('fp'), 'file precision', 200),
            'size_class': optional_text(metadata.get('size'), 'file size class', 200), 'hashes': hashes,
            'scan': {'pickle': optional_text(raw.get('pickleScanResult'), 'pickle scan result', 200),
                     'virus': optional_text(raw.get('virusScanResult'), 'virus scan result', 200),
                     'scanned_at': optional_text(raw.get('scannedAt'), 'scan date', 100)}}


def source_claim(value: Any, label: str) -> Any:
    if value is None or isinstance(value, (bool, str)): return value
    raise ValueError('Invalid provider ' + label + ' claim')


def normalize_model(value: Any, diagnostics: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt, payload = snapshot(value)
    need(receipt['outcome'] == 'ok', 'Model-version snapshot must have outcome ok')
    match = VERSION_ROUTE.fullmatch(receipt['route'])
    need(match is not None, 'Model-version receipt must use an exact version route')
    requested = int(match.group(1)); version_id = positive(payload.get('id'), 'Civitai version ID')
    need(version_id == requested, 'Civitai route and payload version identity differ')
    model_id = positive(payload.get('modelId'), 'Civitai model ID'); model = payload.get('model')
    need(model is None or isinstance(model, dict), 'Civitai model metadata must be an object'); model = model or {}
    if model.get('id') is not None: need(model.get('id') == model_id, 'Civitai model identity is inconsistent')
    raw_files = payload.get('files', [])
    need(isinstance(raw_files, list) and len(raw_files) <= MAX_FILES, 'Civitai files must be a bounded list')
    seen_ids: set[int] = set(); files = [file_facts(item, version_id, seen_ids) for item in raw_files]
    files.sort(key=lambda item: item['provider_file_id'])
    air = payload.get('air'); identity = f'civitai-version:{version_id}'
    if air is not None:
        air_match = AIR.fullmatch(air) if isinstance(air, str) else None
        if (air_match is not None and int(air_match.group(1)) == model_id
                and int(air_match.group(2)) == version_id):
            identity = air
        else:
            diagnostics.append({'code': 'invalid_air',
                'message': 'Provider AIR was invalid or targeted another model/version; exact version identity was retained instead.'})
    terms = {key: source_claim(model.get(provider), provider) for key, provider in (
        ('allow_no_credit', 'allowNoCredit'), ('allow_commercial_use', 'allowCommercialUse'),
        ('allow_derivatives', 'allowDerivatives'), ('allow_different_license', 'allowDifferentLicense'))}
    resource = {'source_host': receipt['host'], 'model_id': model_id, 'version_id': version_id,
                'identity': identity, 'model_name': optional_text(model.get('name'), 'model name', 500),
                'version_name': optional_text(payload.get('name'), 'version name', 500),
                'model_type': optional_text(model.get('type'), 'model type', 200),
                'base_model': optional_text(payload.get('baseModel'), 'base model', 500),
                'base_model_type': optional_text(payload.get('baseModelType'), 'base model type', 500),
                'trained_words': bounded_strings(payload.get('trainedWords'), 'trained words'),
                'created_at': optional_text(payload.get('createdAt'), 'created date', 100),
                'updated_at': optional_text(payload.get('updatedAt'), 'updated date', 100),
                'published_at': optional_text(payload.get('publishedAt'), 'published date', 100),
                'status': optional_text(payload.get('status'), 'version status', 100),
                'terms': terms, 'files': files, 'receipt_sha256': receipt['response_sha256']}
    return receipt, resource


def source_scope(receipt: dict[str, Any]) -> dict[str, Any]:
    scope = {'host': receipt['host'], 'route': receipt['route'], 'query': copy.deepcopy(receipt['query']),
             'auth_context': receipt['auth_context']}
    scope['scope_sha256'] = digest(scope); return scope


def gallery_ids(value: Any, diagnostics: list[dict[str, Any]], image_id: int) -> list[int]:
    if value is None: return []
    if not isinstance(value, list) or len(value) > MAX_RESOURCES:
        diagnostics.append({'code': 'malformed_model_version_ids', 'message': 'Image modelVersionIds was not a bounded list.', 'image_id': image_id}); return []
    result = []
    for item in value:
        if type(item) is not int or item <= 0:
            diagnostics.append({'code': 'invalid_model_version_id', 'message': 'Image contained an invalid model version ID.', 'image_id': image_id}); continue
        if item not in result: result.append(item)
    return sorted(result)


def gallery_resources(meta: dict[str, Any], diagnostics: list[dict[str, Any]], image_id: int) -> list[dict[str, Any]]:
    raw = meta.get('civitaiResources')
    if raw is None: return []
    if not isinstance(raw, list) or len(raw) > MAX_RESOURCES:
        diagnostics.append({'code': 'malformed_gallery_resources', 'message': 'civitaiResources was not a bounded list.', 'image_id': image_id}); return []
    result = []
    for index, item in enumerate(raw):
        try:
            need(isinstance(item, dict), 'resource must be an object')
            version_id = positive(item.get('modelVersionId'), 'gallery resource version ID')
            kind = optional_text(item.get('type'), 'gallery resource type', 100) or 'unknown'; weight = item.get('weight')
            if weight is not None:
                need(type(weight) in (int, float) and not isinstance(weight, bool)
                     and math.isfinite(float(weight)) and abs(float(weight)) <= 100,
                     'gallery resource weight must be finite and bounded')
                weight = float(weight)
            result.append({'version_id': version_id, 'type': kind.casefold(), 'weight': weight})
        except (ValueError, TypeError) as exc:
            diagnostics.append({'code': 'invalid_gallery_resource', 'message': str(exc)[:300],
                                'image_id': image_id, 'index': index})
    result.sort(key=lambda item: (item['version_id'], item['type'], -1000 if item['weight'] is None else item['weight']))
    return result


def number(value: Any, label: str, diagnostics: list[dict[str, Any]], image_id: int,
           *, integer: bool = False, minimum: float = 0, maximum: float = 10000) -> int | float | None:
    if value is None: return None
    valid = type(value) is int if integer else type(value) in (int, float) and not isinstance(value, bool)
    if not valid or not math.isfinite(float(value)) or not minimum <= float(value) <= maximum:
        diagnostics.append({'code': 'invalid_gallery_setting', 'message': 'Invalid ' + label,
                            'image_id': image_id, 'setting': label}); return None
    return int(value) if integer else value


def first(meta: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in meta: return meta[key]
    return None


def image_settings(raw: dict[str, Any], meta: dict[str, Any], diagnostics: list[dict[str, Any]], image_id: int) -> dict[str, Any]:
    result: dict[str, Any] = {}
    steps = number(first(meta, 'steps', 'Steps'), 'steps', diagnostics, image_id, integer=True, minimum=1)
    cfg = number(first(meta, 'cfgScale', 'CFG scale'), 'cfg', diagnostics, image_id, minimum=-1000, maximum=1000)
    clip = number(first(meta, 'clipSkip', 'Clip skip'), 'clip_skip', diagnostics, image_id, integer=True, maximum=100)
    sampler = first(meta, 'sampler', 'Sampler'); scheduler = first(meta, 'scheduler', 'Schedule type')
    if steps is not None: result['steps'] = steps
    if cfg is not None: result['cfg'] = cfg
    if clip is not None: result['clip_skip'] = clip
    if sampler is not None:
        if token(sampler, 200): result['sampler'] = sampler
        else: diagnostics.append({'code': 'invalid_gallery_setting', 'message': 'Invalid sampler', 'image_id': image_id, 'setting': 'sampler'})
    if scheduler is not None:
        if token(scheduler, 200): result['scheduler'] = scheduler
        else: diagnostics.append({'code': 'invalid_gallery_setting', 'message': 'Invalid scheduler', 'image_id': image_id, 'setting': 'scheduler'})
    width = number(raw.get('width'), 'width', diagnostics, image_id, integer=True, minimum=1, maximum=65536)
    height = number(raw.get('height'), 'height', diagnostics, image_id, integer=True, minimum=1, maximum=65536)
    if width is not None and height is not None: result['dimensions'] = [width, height]
    return result


def engagement(raw: Any, diagnostics: list[dict[str, Any]], image_id: int) -> dict[str, int]:
    if raw is None: return {'reaction_total': 0, 'comment_total': 0}
    if not isinstance(raw, dict):
        diagnostics.append({'code': 'malformed_image_stats', 'message': 'Image stats was not an object.', 'image_id': image_id}); return {'reaction_total': 0, 'comment_total': 0}
    reaction = 0
    for key in REACTIONS:
        value = raw.get(key)
        if value is None: continue
        if type(value) is not int or not 0 <= value <= 1_000_000_000:
            diagnostics.append({'code': 'invalid_image_stat', 'message': 'Image reaction count was invalid.',
                                'image_id': image_id, 'stat': key}); continue
        reaction += value
    comments = raw.get('commentCount', 0)
    if type(comments) is not int or not 0 <= comments <= 1_000_000_000:
        diagnostics.append({'code': 'invalid_image_stat', 'message': 'Image comment count was invalid.',
                            'image_id': image_id, 'stat': 'commentCount'}); comments = 0
    return {'reaction_total': reaction, 'comment_total': comments}


def normalize_image(raw: Any, scope: dict[str, Any], receipt: dict[str, Any], diagnostics: list[dict[str, Any]]) -> dict[str, Any] | None:
    try:
        need(isinstance(raw, dict), 'Image record must be an object')
        image_id = positive(raw.get('id'), 'Image ID'); post_id = positive(raw.get('postId'), 'Post ID', optional=True)
        uploader = raw.get('username')
        if uploader is not None and not token(uploader, 200):
            diagnostics.append({'code': 'invalid_uploader', 'message': 'Image uploader identity was invalid.', 'image_id': image_id}); uploader = None
        created = raw.get('createdAt')
        if created is not None and not token(created, 100): created = None
        version_ids = gallery_ids(raw.get('modelVersionIds'), diagnostics, image_id); meta = raw.get('meta')
        if meta is None: state, metadata = 'absent', {}
        elif not isinstance(meta, dict):
            state, metadata = 'malformed', {}
            diagnostics.append({'code': 'malformed_image_metadata', 'message': 'Image metadata was not an object.', 'image_id': image_id})
        else: state, metadata = 'present', meta
        resources = gallery_resources(metadata, diagnostics, image_id) if state == 'present' else []
        version_ids = sorted(set(version_ids) | {item['version_id'] for item in resources})
        return {'source_scope': copy.deepcopy(scope), 'receipt_sha256s': [receipt['response_sha256']],
                'image_id': image_id, 'post_id': post_id, 'uploader': uploader, 'created_at': created,
                'version_ids': version_ids, 'resources': resources,
                'settings': image_settings(raw, metadata, diagnostics, image_id),
                'engagement': engagement(raw.get('stats'), diagnostics, image_id), 'metadata_state': state}
    except (ValueError, TypeError) as exc:
        diagnostics.append({'code': 'invalid_image', 'message': str(exc)[:300]}); return None


def semantic_observation(value: dict[str, Any]) -> bytes:
    return canonical({key: item for key, item in value.items() if key != 'receipt_sha256s'})


def collect_observations(pages: list[Any], version_id: int, diagnostics: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    need(len(pages) <= MAX_PAGES, 'Use at most 32 retained image pages')
    receipts, seen, total, coverage = [], {}, 0, bool(pages)
    for index, raw_page in enumerate(pages):
        receipt, payload = snapshot(raw_page); receipts.append(receipt)
        need(receipt['route'] == '/api/v1/images', 'Image receipt must use /api/v1/images')
        target = receipt['query'].get('modelVersionId')
        need(str(target) == str(version_id), 'Image receipt must target the normalized model version')
        with_meta = receipt['query'].get('withMeta')
        need(with_meta is True or isinstance(with_meta, str) and with_meta.casefold() == 'true',
             'Image receipt must request metadata explicitly')
        scope = source_scope(receipt)
        if receipt['outcome'] != 'ok':
            coverage = False
            diagnostics.append({'code': 'source_' + receipt['outcome'],
                                'message': 'Source page was ' + receipt['outcome'] + '; absence is not authoritative.',
                                'page': index, 'host': receipt['host']}); continue
        items = payload.get('items')
        need(isinstance(items, list), 'Civitai image payload items must be a list')
        total += len(items); need(total <= MAX_IMAGES, 'Use at most 1,000 retained image records')
        metadata = payload.get('metadata')
        if metadata is not None:
            need(isinstance(metadata, dict), 'Civitai image page metadata must be an object')
            if metadata.get('nextCursor') not in (None, ''):
                coverage = False
                diagnostics.append({'code': 'pagination_incomplete', 'message': 'A retained image page reports another cursor.',
                                    'page': index, 'host': receipt['host']})
        for raw in items:
            item = normalize_image(raw, scope, receipt, diagnostics)
            if item is None: continue
            key = (scope['scope_sha256'], item['image_id'])
            if key not in seen: seen[key] = item; continue
            prior = seen[key]
            if prior is None: continue
            if semantic_observation(prior) == semantic_observation(item):
                prior['receipt_sha256s'] = sorted(set(prior['receipt_sha256s'] + item['receipt_sha256s']))
                diagnostics.append({'code': 'duplicate_image', 'message': 'Repeated identical image metadata was deduplicated.',
                                    'image_id': item['image_id'], 'host': receipt['host']})
            else:
                seen[key] = None
                diagnostics.append({'code': 'conflicting_duplicate_image',
                    'message': 'Conflicting records for one image identity were excluded from evidence.',
                    'image_id': item['image_id'], 'host': receipt['host']})
    observations = [item for item in seen.values() if item is not None]
    observations.sort(key=lambda item: (item['source_scope']['host'],
        json.dumps(item['source_scope']['query'], sort_keys=True), item['image_id']))
    return receipts, observations, coverage


def aggregate(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, tuple[int, ...]], dict[str, Any]] = {}
    for item in observations:
        if len(item['version_ids']) < 2: continue
        scope = item['source_scope']; key = (scope['scope_sha256'], tuple(item['version_ids']))
        group = groups.setdefault(key, {'source_scope': copy.deepcopy(scope), 'version_ids': item['version_ids'],
            '_observations': set(), '_posts': set(), '_uploaders': set(), '_receipts': set(),
            '_usages': {}, '_settings': {}, 'engagement': {'reaction_total': 0, 'comment_total': 0}})
        observation_key = ('post', item['post_id']) if item['post_id'] is not None else ('image', item['image_id'])
        if observation_key in group['_observations']: continue
        group['_observations'].add(observation_key)
        if item['post_id'] is not None: group['_posts'].add(item['post_id'])
        if item['uploader'] is not None: group['_uploaders'].add(item['uploader'])
        group['_receipts'].update(item['receipt_sha256s'])
        resource_map: dict[int, list[dict[str, Any]]] = {}
        for entry in item['resources']: resource_map.setdefault(entry['version_id'], []).append(entry)
        for version_id in item['version_ids']:
            usage = group['_usages'].setdefault(version_id, {'types': set(), 'weights': set()})
            entries = resource_map.get(version_id, [])
            if not entries: usage['types'].add('unknown')
            for entry in entries:
                usage['types'].add(entry['type'])
                if entry['weight'] is not None: usage['weights'].add(entry['weight'])
        settings_key = canonical(item['settings'])
        if settings_key not in group['_settings']: group['_settings'][settings_key] = [copy.deepcopy(item['settings']), 0]
        group['_settings'][settings_key][1] += 1
        group['engagement']['reaction_total'] += item['engagement']['reaction_total']
        group['engagement']['comment_total'] += item['engagement']['comment_total']
    result = []
    for group in groups.values():
        usages = [{'version_id': version_id, 'types': sorted(value['types']), 'weights': sorted(value['weights'])}
                  for version_id, value in sorted(group.pop('_usages').items())]
        settings = [{**value[0], 'count': value[1]}
                    for _, value in sorted(group.pop('_settings').items(), key=lambda pair: pair[0])]
        observation_set = group.pop('_observations'); posts = group.pop('_posts')
        uploaders = group.pop('_uploaders'); receipts = group.pop('_receipts')
        result.append({**group, 'distinct_observations': len(observation_set), 'distinct_posts': len(posts),
                       'distinct_uploaders': len(uploaders), 'post_ids': sorted(posts),
                       'uploaders': sorted(uploaders), 'receipt_sha256s': sorted(receipts),
                       'resource_usages': usages, 'settings': settings,
                       'reported_co_use': True, 'compatibility_proven': False, 'quality_proven': False})
    result.sort(key=lambda item: (item['source_scope']['host'],
        json.dumps(item['source_scope']['query'], sort_keys=True), item['version_ids']))
    return result


def normalize(value: Any) -> dict[str, Any]:
    need(isinstance(value, dict) and set(value) == {'format', 'model_version', 'image_pages'},
         'Supply format, model_version and image_pages')
    need(value['format'] == INPUT_FORMAT, 'Unsupported Civitai composition input')
    need(isinstance(value['image_pages'], list), 'image_pages must be a list')
    diagnostics: list[dict[str, Any]] = []
    model_receipt, resource = normalize_model(value['model_version'], diagnostics)
    image_receipts, observations, coverage = collect_observations(
        value['image_pages'], resource['version_id'], diagnostics)
    return {'format': REPORT_FORMAT, 'provider': 'civitai', 'context_sha256': digest(value),
            'resource': resource, 'source_receipts': [model_receipt] + image_receipts,
            'image_observations': observations, 'combinations': aggregate(observations),
            'coverage_complete': coverage, 'diagnostics': diagnostics,
            'network_performed': False, 'model_downloaded': False, 'image_downloaded': False,
            'installation_authorized': False, 'generation_submitted': False,
            'notice': 'Retained provider metadata is untrusted evidence. Reported gallery co-use is not compatibility, quality, licence, installation or execution proof.'}


def read_json(path: Path) -> dict[str, Any]:
    with path.open('rb') as stream: raw = stream.read(1048577)
    return decode(raw)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path, help='Retained JSON input; no provider request is made')
    args = parser.parse_args(argv)
    try: result = normalize(read_json(args.snapshot))
    except (ValueError, TypeError, KeyError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({'error': {'code': 'invalid_snapshot', 'message': str(exc)[:500]},
                         }, ensure_ascii=False, allow_nan=False)); return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)); return 0


if __name__ == '__main__': raise SystemExit(main())
