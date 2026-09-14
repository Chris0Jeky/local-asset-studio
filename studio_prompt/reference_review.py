"""Read-only browser review over the reference assistant's existing contract.

Original bytes go only to this local validation boundary. No filesystem writes,
Studio access, helper calls, graph binding or generation happen in this module.
"""
from __future__ import annotations
import base64
import copy
import hashlib
import io
import warnings
from PIL import Image, UnidentifiedImageError
from .reference_analysis import draft, review_template, validate_report
from .schema import canonical, digest, fields, need, validate

HTTP_LIMIT = 48 * 1024 * 1024
IMAGE_LIMIT = 8 * 1024 * 1024
ENCODED_LIMIT = 4 * ((IMAGE_LIMIT + 2) // 3)
PIXEL_LIMIT = 16 * 1024 * 1024


def _report(value):
    need(type(value) is dict, 'Expected a reference analysis object')
    # A helper envelope's timing/model declarations grant no additional authority.
    report = value.get('analysis', value)
    return validate_report(report)


def inspect(value):
    fields(value, ('analysis',))
    report = _report(value['analysis'])
    return {'format': 'studio.reference-review/v1', 'analysis': report, 'review': review_template(report),
            'inference_submitted': False, 'generation_submitted': False, 'execution_authorized': False}


def _images(report, rows):
    need(type(rows) is list and len(rows) == len(report['request']['references']), 'Supply every original image in reference order')
    images = {}
    for ref, row in zip(report['request']['references'], rows):
        fields(row, ('reference_id', 'media_base64'))
        need(row['reference_id'] == ref['id'], 'Original image identity/order changed')
        encoded = row['media_base64']
        need(type(encoded) is str and 0 < len(encoded) <= ENCODED_LIMIT, 'Original image exceeds the 8 MiB limit')
        raw = base64.b64decode(encoded, validate=True)
        need(0 < len(raw) <= IMAGE_LIMIT, 'Original image exceeds the 8 MiB limit')
        need(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'Reference bytes changed; choose the exact analyzed original')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as image:
                    need(image.format in ('PNG', 'JPEG', 'WEBP'), 'Choose a PNG, JPEG or WebP image')
                    need(0 < image.width * image.height <= PIXEL_LIMIT and getattr(image, 'n_frames', 1) == 1,
                         'Original image exceeds the pixel/frame limit')
                    image.verify()
                with Image.open(io.BytesIO(raw)) as image: image.load()
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ValueError('Original image could not be decoded within its limits') from exc
        images[ref['id']] = raw
    return images


def _current(value, adopt_brief):
    need(type(adopt_brief) is bool, 'adopt_brief must be an explicit boolean')
    need(type(value) is dict, 'Expected the current CreativeIntent')
    check = copy.deepcopy(value)
    # An empty editor can explicitly adopt the reviewed interpretation. All other
    # current fields still pass the same CreativeIntent validator.
    if adopt_brief and type(check.get('brief')) is str and not check['brief'].strip():
        check['brief'] = 'Pending reviewed instruction'
    validate(check)
    need(check['task'] in ('image', 'edit'), 'Reference review currently supports image/edit briefs only')
    return copy.deepcopy(value)


def preview(value):
    fields(value, ('analysis', 'review', 'images', 'intent', 'adopt_brief'))
    current = _current(value['intent'], value['adopt_brief'])
    report = _report(value['analysis'])
    source = draft(report, value['review'], source_bytes=_images(report, value['images']))
    incoming = source['intent']; result = copy.deepcopy(current)
    if value['adopt_brief']: result['brief'] = incoming['brief']
    result['references'] = copy.deepcopy(incoming['references'])
    result['facets'].update(incoming['facets'])
    result['tags'] = list(dict.fromkeys(current['tags'] + incoming['tags']))
    changes = []
    for field in ('brief', 'references', 'tags', *('facets.' + key for key in incoming['facets'])):
        before = current['facets'].get(field[7:]) if field.startswith('facets.') else current[field]
        after = result['facets'][field[7:]] if field.startswith('facets.') else result[field]
        if canonical(before) == canonical(after): continue
        need(not any(field == lock or field.startswith(lock + '.') for lock in current['locked']), 'Locked field: ' + field)
        changes.append({'field': field, 'before': copy.deepcopy(before), 'after': copy.deepcopy(after)})
    validate(result)
    envelope = {'format': 'studio.reference-transfer-preview/v1', 'base_sha256': digest(current),
                'intent': result, 'intent_sha256': digest(result), 'reference_draft': source,
                'changes': changes, 'source_bytes_verified': True, 'inference_submitted': False,
                'generation_submitted': False, 'execution_authorized': False,
                'limits': ['A preview over the caller-supplied draft, not a persisted shared revision.',
                           'Originals were validated locally, not uploaded or bound to a generator.',
                           'Questions and visual uncertainty remain in the reference receipt; review before generating.']}
    need(len(canonical(envelope)) <= 1024 * 1024, 'Reference transfer preview exceeds 1 MiB')
    envelope['preview_sha256'] = digest(envelope)
    return envelope
