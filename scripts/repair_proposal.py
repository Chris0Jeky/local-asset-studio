#!/usr/bin/env python3
"""Validate a bounded, NON-EXECUTABLE repair design proposal.

No image decoding, file-hash verification, model discovery, graph compilation,
network calls, approval, budget reservation or output files. The production
character-edit/Production services remain the execution and pixel authorities.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

SCHEMA = 'studio.repair-proposal/v0'
MAX_BYTES = 262144
MAX_PIXELS = 24_000_000
ROLES = ('identity', 'costume', 'pose', 'style', 'geometry')
STRATEGIES = ('preserve', 'masked', 'instruction', 'geometry', 'native', 'upscale')
RUNTIME_CHECKS = (
    'source-and-document-freshness', 'actual-mask-support', 'protected-pixels',
    'reference-and-canon-binding', 'native-transform-conformance',
    'model-and-resource-preflight', 'registered-campaign-authority',
    'intended-change-and-owner-review',
)


class ContractError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise ContractError(code, message)


def fields(value: Any, names: str, location: str) -> dict:
    if type(value) is not dict or set(value) != set(names.split()):
        fail('fields', f'{location}: exact declared fields required')
    return value


def integer(value: Any, low: int, high: int, location: str) -> int:
    if type(value) is not int or not low <= value <= high:
        fail('integer', f'{location}: integer in [{low}, {high}] required')
    return value


def sequence(value: Any, low: int, high: int, location: str) -> list:
    if type(value) is not list or not low <= len(value) <= high:
        fail('list', f'{location}: list length in [{low}, {high}] required')
    return value


def text(value: Any, maximum: int, location: str) -> str:
    if type(value) is not str or not value.strip() or len(value) > maximum:
        fail('text', f'{location}: nonempty bounded text required')
    return value


def choice(value: Any, options: tuple, code: str) -> str:
    if type(value) is not str or value not in options:
        fail(code, f'{code}: unsupported value')
    return value


def identifier(value: Any) -> str:
    if type(value) is not str or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', value):
        fail('identifier', 'Expected a lowercase bounded instance identifier')
    return value


def sha256(value: Any) -> str:
    if type(value) is not str or not re.fullmatch(r'[0-9a-f]{64}', value):
        fail('sha256', 'Expected a lowercase SHA-256 declaration, not a path')
    return value


def size(value: Any) -> list[int]:
    sequence(value, 2, 2, 'size')
    result = [integer(v, 1, MAX_PIXELS, 'dimension') for v in value]
    if result[0] * result[1] > MAX_PIXELS:
        fail('pixels', 'Canvas exceeds the proposal pixel bound')
    return result


def box(value: Any, canvas: list[int]) -> list[int]:
    if type(value) is not list or len(value) != 4 or any(type(v) is not int for v in value):
        fail('box', 'Expected four integer half-open source coordinates')
    x0, y0, x1, y1 = value
    if not (0 <= x0 < x1 <= canvas[0] and 0 <= y0 < y1 <= canvas[1]):
        fail('box', 'Box must be nonempty and inside the normalized source')
    return value


def ratio(value: Fraction) -> list[int]:
    return [value.numerator, value.denominator]


def transform(canvas: list[int], context: dict) -> dict:
    """Account for declared crop/resize/pad, without resampling any pixels.

    Positive half-up dimensions are explicit. Integer pixel centres map as
    x_work = (x_source - crop_left + 1/2) * actual_scale - 1/2 + pad_left.
    Native adapters still must prove their own resampling follows this contract.
    """
    size(canvas)
    fields(context, 'box scale padding alignment', 'context')
    crop = box(context['box'], canvas)
    sequence(context['scale'], 2, 2, 'scale')
    n, d = [integer(v, 1, 4096, 'scale') for v in context['scale']]
    padding = sequence(context['padding'], 4, 4, 'padding')
    padding = [integer(v, 0, 65536, 'padding') for v in padding]
    alignment = context['alignment']
    if type(alignment) is not int or alignment not in (1, 8, 16, 32, 64):
        fail('alignment', 'Alignment must be an explicit supported proposal value')
    cropped = [crop[2] - crop[0], crop[3] - crop[1]]
    resized = [(2 * dimension * n + d) // (2 * d) for dimension in cropped]
    if min(resized) < 1:
        fail('rounded_size', 'Scale rounds a working dimension to zero')
    work = size([resized[0] + padding[0] + padding[2],
                 resized[1] + padding[1] + padding[3]])
    if any(v % alignment for v in work):
        fail('alignment', 'Padded working dimensions are not aligned')
    mapping = {}
    for axis, start, length, output, pad in zip(('x', 'y'), crop[:2], cropped, resized, padding[:2]):
        scale = Fraction(output, length)
        offset = (Fraction(1, 2) - start) * scale - Fraction(1, 2) + pad
        mapping[axis] = {'scale': ratio(scale), 'offset': ratio(offset)}
    return {'resized_size': resized, 'work_size': work, 'padding_ltrb': padding,
            'pixel_centres': 'integer-centres-half-pixel-resize', 'mapping': mapping,
            'resampling_performed': False}


def bounded_structure(value: Any, depth: int = 0, count: list[int] | None = None) -> None:
    if count is None:
        count = [0]
    count[0] += 1
    if depth > 32 or count[0] > 10000:
        fail('structure', 'Proposal nesting or item count exceeds its bound')
    if type(value) is float and not math.isfinite(value):
        fail('json', 'Nonfinite values are not allowed')
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str:
                fail('json', 'Object keys must be strings')
            bounded_structure(child, depth + 1, count)
    elif type(value) is list:
        for child in value:
            bounded_structure(child, depth + 1, count)
    elif type(value) not in (str, int, float, bool, type(None)):
        fail('json', 'Proposal must contain JSON values only')


def assess(value: dict) -> dict:
    """Check declarations, not image truth or permission to execute."""
    bounded_structure(value)
    fields(value, 'schema source mode context instances targets references contacts masks intent limits strategies', 'proposal')
    choice(value['schema'], (SCHEMA,), 'schema')
    source = fields(value['source'], 'sha256 revision size', 'source')
    sha256(source['sha256'])
    sha256(source['revision'])
    canvas = size(source['size'])
    geometry = transform(canvas, value['context'])
    mode = choice(value['mode'], ('localized', 'remaster', 'reconstruction'), 'mode')
    instances = {}
    for entry in sequence(value['instances'], 1, 32, 'instances'):
        fields(entry, 'id kind', 'instance')
        name = identifier(entry['id'])
        choice(entry['kind'], ('character', 'prop'), 'kind')
        if name in instances:
            fail('duplicate', 'Instance IDs must be unique, even for the same canon')
        instances[name] = entry['kind']
    targets = sequence(value['targets'], 1, 8, 'targets')
    if any(identifier(name) not in instances for name in targets):
        fail('instance', 'Target references an unknown instance')
    if len(set(targets)) != len(targets):
        fail('duplicate', 'Targets must be unique')
    seen_refs = set()
    for entry in sequence(value['references'], 0, 64, 'references'):
        fields(entry, 'instance_id role sha256', 'reference')
        if identifier(entry['instance_id']) not in instances:
            fail('instance', 'Reference belongs to an unknown instance')
        choice(entry['role'], ROLES, 'role')
        sha256(entry['sha256'])
        key = (entry['instance_id'], entry['role'], entry['sha256'])
        if key in seen_refs:
            fail('duplicate', 'Identical reference declaration is duplicated')
        seen_refs.add(key)
    contacts = sequence(value['contacts'], 0, 32, 'contacts')
    for entry in contacts:
        fields(entry, 'participants box', 'contact')
        participants = sequence(entry['participants'], 2, 8, 'participants')
        if any(identifier(name) not in instances for name in participants) or len(set(participants)) != len(participants):
            fail('contact', 'Contact needs known distinct participants')
        box(entry['box'], canvas)
    masks = fields(value['masks'], 'encoding edit write protect subject', 'masks')
    choice(masks['encoding'], ('source-L-coverage-v1',), 'mask_encoding')
    for name in ('edit', 'write', 'protect', 'subject'):
        if name in ('protect', 'subject') and masks[name] is None:
            continue
        sha256(masks[name])
    intent = fields(value['intent'], 'kind visibility synthesize_unseen description', 'intent')
    choice(intent['kind'], ('detail', 'anatomy', 'contact', 'restore', 'outpaint', 'remove_occluder'), 'kind')
    choice(intent['visibility'], ('visible', 'occluded', 'out_of_frame', 'ambiguous'), 'visibility')
    if type(intent['synthesize_unseen']) is not bool:
        fail('boolean', 'synthesize_unseen must be a boolean')
    text(intent['description'], 2048, 'description')
    if intent['kind'] in ('outpaint', 'remove_occluder') and not intent['synthesize_unseen']:
        fail('preservation_conflict', 'Completion/removal requires an explicit synthesis declaration')
    if intent['synthesize_unseen'] and mode != 'reconstruction':
        fail('preservation_conflict', 'Unseen synthesis requires a reconstruction branch')
    if intent['kind'] == 'contact':
        if not contacts:
            fail('contact_scope', 'Contact editing requires declared participants and region')
        x0, y0, x1, y1 = value['context']['box']
        for entry in contacts:
            a, b, c, d = entry['box']
            if not set(entry['participants']).issubset(targets) or not (x0 <= a < c <= x1 and y0 <= b < d <= y1):
                fail('contact_scope', 'All coupled participants and regions must be in the proposed scope')
    limits = fields(value['limits'], 'max_candidates max_analysis_calls', 'limits')
    integer(limits['max_candidates'], 0, 64, 'max_candidates')
    integer(limits['max_analysis_calls'], 0, 64, 'max_analysis_calls')
    strategies = sequence(value['strategies'], 1, 6, 'strategies')
    for strategy in strategies:
        choice(strategy, STRATEGIES, 'strategy')
    if len(set(strategies)) != len(strategies):
        fail('duplicate', 'Alternative strategies must be distinct')
    if mode == 'localized' and 'upscale' in strategies:
        fail('preservation_conflict', 'Global finishing belongs to a separate remaster proposal')
    if any(s in strategies for s in ('masked', 'instruction', 'geometry', 'upscale')) and limits['max_candidates'] == 0:
        fail('budget', 'Candidate strategies require a positive declared cap, not execution authority')
    review = ['target-and-mask-scope', 'adapter-capability', 'intended-change']
    if intent['visibility'] != 'visible':
        review.append('visibility')
    if mode == 'reconstruction':
        review.append('reconstruction-scope')
    for name in targets:
        if instances[name] == 'character' and not any(r['instance_id'] == name and r['role'] == 'identity' for r in value['references']):
            review.append('identity-reference:' + name)
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('utf-8')
    if len(encoded) > MAX_BYTES:
        fail('bytes', 'Canonical proposal exceeds the byte bound')
    return {'schema': SCHEMA, 'status': 'declarations_valid', 'executable': False,
            'authority': 'none', 'pixel_validation': 'not_performed',
            'proposal_sha256': hashlib.sha256(encoded).hexdigest(),
            'geometry': geometry, 'review_required': review,
            'required_runtime_checks': list(RUNTIME_CHECKS)}


def read_proposal(path: Path) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                fail('json', 'Duplicate object key')
            result[key] = value
        return result

    def constant(_):
        fail('json', 'Nonfinite JSON constant')

    with path.open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        fail('bytes', 'Input exceeds the byte bound')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
        bounded_structure(value)
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ContractError('json', 'Invalid UTF-8 JSON or excessive nesting') from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('describe')
    validate = commands.add_parser('validate')
    validate.add_argument('proposal', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'describe':
            report = {'schema': SCHEMA, 'executable': False, 'authority': 'none',
                      'commands': ['describe', 'validate'], 'roles': list(ROLES),
                      'strategies': list(STRATEGIES), 'max_input_bytes': MAX_BYTES,
                      'required_runtime_checks': list(RUNTIME_CHECKS)}
        else:
            report = assess(read_proposal(args.proposal))
        print(json.dumps(report, ensure_ascii=True, allow_nan=False, indent=2))
        return 0
    except (ContractError, OSError) as error:
        report = {'executable': False, 'authority': 'none',
                  'error': {'code': getattr(error, 'code', 'io'), 'message': str(error)}}
        print(json.dumps(report, ensure_ascii=True, allow_nan=False))
        return 2


if __name__ == '__main__':
    sys.exit(main())
