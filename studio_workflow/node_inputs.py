"""Conservative input adapters; opaque schemas are evidence, not executable code.

JSON-text evidence preserves parsed integer/float distinctions through JavaScript
transport. It does not claim to preserve the original whitespace or byte stream.
"""
from __future__ import annotations

import copy
import json
import math
from typing import Any

SCALARS = {'INT': 'int', 'FLOAT': 'float', 'STRING': 'string', 'BOOLEAN': 'boolean'}
RESERVED = {'__proto__', 'prototype', 'constructor'}
BOOLEAN_OPTIONS = ('isOptional', 'forceInput', 'defaultInput', 'hidden', 'lazy', 'rawLink', 'remote', 'socketless')


def evidence(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def socket_tokens(value: Any) -> set[str]:
    if not isinstance(value, str): return set()
    tokens = {part.strip() for part in value.split(',')}
    return tokens if '' not in tokens else set()


def descriptor(name: str, raw: Any, required: bool) -> dict:
    options, kind, reasons = {}, 'UNKNOWN', []
    if isinstance(raw, dict):
        options = copy.deepcopy(raw)
        kind = options.pop('type', None)
        if type(options.get('isOptional', False)) is bool:
            required = not options.get('isOptional', not required)
    elif isinstance(raw, list) and raw:
        kind = raw[0]
        if len(raw) == 2 and isinstance(raw[1], dict):
            options = copy.deepcopy(raw[1])
        elif len(raw) != 1:
            reasons.append('Legacy descriptor needs one type and at most one options object')
    else:
        reasons.append('Unrecognized input descriptor')
    for flag in BOOLEAN_OPTIONS:
        if flag in options and type(options[flag]) is not bool:
            reasons.append(flag + ' must be boolean')
    if isinstance(kind, list):
        if 'options' in options and evidence(options['options']) != evidence(kind):
            reasons.append('Legacy choices conflict with the options field')
        options['options'] = copy.deepcopy(kind)
        kind = 'COMBO'
    kind = kind if isinstance(kind, str) else 'UNKNOWN'
    widget = SCALARS.get(kind, 'socket')
    if not socket_tokens(kind):
        reasons.append('Input type requires nonempty socket tokens')
    if kind == 'COMBO':
        choices = options.get('options')
        scalar = lambda x: type(x) in (str, int, bool) or (type(x) is float and math.isfinite(x))
        widget = 'combo' if isinstance(choices, list) and choices and all(map(scalar, choices)) else 'unsupported'
    if kind not in {*SCALARS, 'COMBO'} and (options.get('socketless') or 'default' in options):
        widget = 'unsupported'
    if kind in {'INT', 'FLOAT'}:
        numeric = lambda n: type(n) is int or (type(n) is float and math.isfinite(n))
        if any(not numeric(options[k]) for k in ('min', 'max', 'step') if k in options):
            reasons.append('Numeric bounds and step must be finite numbers')
        elif 'min' in options and 'max' in options and options['min'] > options['max']:
            reasons.append('Numeric minimum exceeds maximum')
        elif 'step' in options and options['step'] <= 0:
            reasons.append('Numeric step must be positive')
    if kind in {'DYNAMIC_COMBO', 'DYNAMIC_AUTOGROW', 'UNKNOWN'} or (kind.startswith('COMFY_') and kind.endswith('_V3')):
        reasons.append('Dynamic/custom input needs a native adapter')
    for flag in ('rawLink', 'remote'):
        if options.get(flag): reasons.append(flag + ' behaviour needs a native adapter')
    if widget == 'unsupported' and not reasons:
        reasons.append('Custom widget or non-scalar options need a native adapter')
    if reasons: widget = 'unsupported'
    elif options.get('forceInput'): widget = 'socket'
    adapter = ('native-required' if widget == 'unsupported' else
               'typed-connection' if widget == 'socket' else 'scalar-' + widget)
    return {'name': name, 'type': kind, 'required': required, 'widget': widget,
            'options': options, 'reason': '; '.join(reasons),
            # Malformed flags must not hide a required unsupported field.
            'hidden': options.get('hidden') is True and not reasons,
            'source_descriptor_json': evidence(raw), 'adapter': adapter + '/v1',
            'capabilities': {'static_validation': widget != 'unsupported',
                             'document_round_trip': True, 'runtime_qualified': False}}


def inputs(raw: Any) -> tuple[list[dict], list[str]]:
    if not isinstance(raw, dict): return [], ['Node definition must be an object']
    result, errors, seen = [], [], set()
    if 'input_is_list' in raw and type(raw['input_is_list']) is not bool:
        errors.append('input_is_list must be boolean')
    if 'input' in raw and 'inputs' in raw:
        errors.append('Both legacy input and NodeDef-v2 inputs were declared; adapter required')
    if 'input' in raw:
        groups = raw['input']
        if not isinstance(groups, dict): return [], errors + ['Legacy input definitions must be an object']
        if set(groups) - {'required', 'optional', 'hidden'}:
            errors.append('Unknown input group; definition retained for a native adapter')
        entries = [(group, groups[group]) for group in ('required', 'optional', 'hidden') if group in groups]
    elif 'inputs' in raw:
        entries = [('v2', raw['inputs'])]
    else:
        entries = []  # Truly absent input declarations are valid for zero-input nodes.
    for group, fields in entries:
        if not isinstance(fields, dict):
            errors.append(group + ' input definitions must be an object')
            continue
        for name, value in fields.items():
            if not isinstance(name, str) or not name or name in RESERVED:
                errors.append('Invalid or reserved input name')
                continue
            if name in seen:
                errors.append('Duplicate input name across groups: ' + name)
                continue
            seen.add(name)
            # Hidden runtime injection remains in source_definition_json, not an
            # authorable field. Its name still participates in duplicate checks.
            if group != 'hidden': result.append(descriptor(name, value, group != 'optional'))
    return result, errors
