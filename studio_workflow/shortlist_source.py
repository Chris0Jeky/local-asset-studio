"""Optional primary-image observations for the existing recipe shortlist.

Uses the existing continuation source boundary; owns no files or attachment state.
A named role here is a proposed prompt role, never a geometric control claim.
"""
from __future__ import annotations

import re
from .core import need

SOURCE_FIELDS = {'source_asset_id', 'source_sha256', 'source_role'}
SOURCE_ROLES = {'source': 'Whole image / first frame', 'identity': 'Identity guidance',
                'pose': 'Pose guidance', 'style': 'Style guidance',
                'costume': 'Costume guidance', 'composition': 'Composition guidance'}


def validate_source_query(value):
    fields = SOURCE_FIELDS.intersection(value)
    if not fields: return
    need(fields == SOURCE_FIELDS, 'Supply source_asset_id, source_sha256 and source_role together')
    key = value['source_asset_id']
    need(type(key) is str and re.fullmatch('[A-Za-z0-9_.-]{1,96}', key)
         and key not in ('.', '..', '__proto__', 'constructor', 'prototype'), 'Invalid source asset identity')
    need(type(value['source_sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['source_sha256']), 'Invalid source SHA-256')
    need(type(value['source_role']) is str and value['source_role'] in SOURCE_ROLES, 'Choose a supported source role')
    need(value.get('reference_count', 0) >= 1, 'A selected source requires at least one declared reference')


def inspect_source(studio, value):
    if 'source_asset_id' not in value: return None
    from continuation import source_context
    from PIL import Image
    try: context = source_context(studio, value['source_asset_id'])
    except Image.DecompressionBombError as exc:
        raise ValueError('Source image exceeds the image safety limit; choose a smaller reference.') from exc
    need(context['asset_id'] == value['source_asset_id'] and context['sha256'] == value['source_sha256'],
         'Source identity changed. Reopen the asset before checking starting recipes.')
    # Do not send retained prompts, private paths or unrelated metadata to the chooser.
    return {'asset_id': context['asset_id'], 'sha256': context['sha256'],
            'role': value['source_role'], 'title': context['title'][:160],
            'width': context['width'], 'height': context['height'],
            'bytes_verified': True, 'staged': False}


def assignment(preset, graph, source):
    """Exact primary slot only; additional references remain the user's declarations."""
    from continuation import reference_bindings, consumes_reference
    bindings = reference_bindings(preset)
    binding = bindings[0] if bindings else None
    result = {'asset_id': source['asset_id'], 'sha256': source['sha256'], 'slot': 1,
              'role': source['role'], 'binding': binding, 'role_mode': 'unsupported'}
    if not consumes_reference(graph, binding):
        return result, ('source_binding_unavailable', 'blocked',
                        'The selected image has no verified primary input path to every supported saved output. No assignment was guessed.')
    if source['role'] == 'source':
        result['role_mode'] = 'whole-image'
        return result, ('source_wiring_observed', 'observed',
                        'The primary image input reaches the saved outputs. This is whole-image wiring, not a promise to preserve identity or pixels.')
    slots = preset.get('reference_slots') or []
    # The existing compiler supports explicit roles only through reference_slots.
    if slots and isinstance(slots[0], dict) and slots[0].get('binding') == binding and preset.get('positive'):
        result['role_mode'] = 'prompt-guidance'
        return result, ('source_role_proposed', 'unknown',
                        f'Assign {source["role"]} to Picture 1 after attaching this image in Create. This is prompt guidance, not geometric pose control or guaranteed visual preservation. No role was applied.')
    return result, ('source_role_unsupported', 'blocked',
                    f'This route uses the whole image but does not expose an explicit {source["role"]} role slot. Choose Whole image / first frame or a role-aware route; the role will not be silently ignored.')


def validate_source_reply(result, query, message):
    source = result.get('source')
    if 'source_asset_id' not in query:
        need(source is None, message)
    else:
        need(type(source) is dict and source.get('asset_id') == query['source_asset_id']
             and source.get('sha256') == query['source_sha256'] and source.get('role') == query['source_role']
             and source.get('bytes_verified') is True and source.get('staged') is False
             and type(source.get('title')) is str and len(source['title']) <= 160
             and all(type(source.get(k)) is int and 0 < source[k] <= 2**53-1 for k in ('width','height')), message)
    for row in result.get('candidates', []):
        if type(row) is not dict or 'source_assignment' not in row: continue
        a = row['source_assignment']
        need(source is not None and type(a) is dict and a.get('asset_id') == query['source_asset_id']
             and a.get('sha256') == query['source_sha256'] and a.get('role') == query['source_role']
             and type(a.get('slot')) is int and a['slot'] == 1
             and a.get('role_mode') in ('whole-image', 'prompt-guidance', 'unsupported'), message)
        binding = a.get('binding')
        need(binding is None or type(binding) is list and len(binding) == 2
             and type(binding[0]) is str and len(binding[0]) <= 96 and binding[1] == 'image', message)
