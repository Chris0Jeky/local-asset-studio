"""Optional primary or ordered-image observations for the existing recipe shortlist.

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
    if 'sources' in value:
        need(not SOURCE_FIELDS.intersection(value), 'Use ordered sources or legacy primary-source fields, not both')
        items = value['sources']
        need(type(items) is list and 1 <= len(items) <= 3, 'Choose one to three ordered sources')
        need(value.get('reference_count') == len(items), 'reference_count must equal the ordered source count')
        for index, item in enumerate(items):
            need(type(item) is dict and set(item) == {'asset_id', 'sha256', 'role'},
                 f'Picture {index+1} requires only asset_id, sha256 and role')
            validate_source_query({'source_asset_id': item['asset_id'], 'source_sha256': item['sha256'],
                                   'source_role': item['role'], 'reference_count': 1})
        return
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


def ordered_bindings(preset):
    """Preserve slot positions, including invalid entries; never compact or deduplicate."""
    slots = preset.get('reference_slots')
    raw = ([slot.get('binding') if type(slot) is dict else None for slot in slots]
           if type(slots) is list and slots else [preset.get('reference'), preset.get('last_reference')])
    return [list(b) if isinstance(b, (list, tuple)) and len(b) == 2 and type(b[0]) is str
            and 0 < len(b[0]) <= 96 and b[1] == 'image' else None for b in raw]


def assignment(preset, graph, source, slot=1, ordered=False):
    """Propose an exact slot, never staging or applying a prompt role."""
    from continuation import reference_bindings, consumes_reference
    bindings = ordered_bindings(preset) if ordered else reference_bindings(preset)
    binding = bindings[slot-1] if slot <= len(bindings) else None
    result = {'asset_id': source['asset_id'], 'sha256': source['sha256'], 'slot': slot,
              'role': source['role'], 'binding': binding, 'role_mode': 'unsupported'}
    if ordered and binding is not None and bindings.count(binding) > 1:
        return result, ('source_binding_ambiguous', 'blocked',
                        'Several slots write the same image input. No source assignment was guessed.')
    if not consumes_reference(graph, binding):
        return result, ('source_binding_unavailable', 'blocked',
                        'The selected image has no verified image input path to every supported saved output. No assignment was guessed.')
    if source['role'] == 'source':
        result['role_mode'] = 'whole-image'
        return result, ('source_wiring_observed', 'observed',
                        'The image input reaches the saved outputs. This is whole-image wiring, not a promise to preserve identity or pixels.')
    slots = preset.get('reference_slots') or []
    # The existing compiler supports explicit roles only through reference_slots.
    if len(slots) >= slot and isinstance(slots[slot-1], dict) and slots[slot-1].get('binding') == binding and preset.get('positive'):
        result['role_mode'] = 'prompt-guidance'
        return result, ('source_role_proposed', 'unknown',
                        f'Assign {source["role"]} to Picture {slot} after attaching this image in Create. This is prompt guidance, not geometric pose control or guaranteed visual preservation. No role was applied.')
    return result, ('source_role_unsupported', 'blocked',
                    f'This route uses the whole image but does not expose an explicit {source["role"]} role slot. Choose Whole image / first frame or a role-aware route; the role will not be silently ignored.')


def inspect_sources(studio, value):
    if 'sources' not in value: return None
    result = []
    for index, item in enumerate(value['sources']):
        try:
            observed = inspect_source(studio, {'source_asset_id': item['asset_id'],
                                      'source_sha256': item['sha256'], 'source_role': item['role']})
        except (ValueError, KeyError) as exc:
            raise ValueError(f'Picture {index+1}: {exc}') from exc
        except OSError as exc:
            raise ValueError(f'Picture {index+1}: source unavailable; reopen the image and check again.') from exc
        result.append({**observed, 'slot': index+1})
    return result


def unassigned_sources(sources):
    return [{'asset_id': x['asset_id'], 'sha256': x['sha256'], 'role': x['role'],
             'slot': i+1, 'binding': None, 'role_mode': 'unsupported'} for i, x in enumerate(sources)]


def validate_ordered_reply(result, query, message):
    expected = query.get('sources')
    if expected is None:
        need(result.get('sources') is None, message)
        need(all('source_assignments' not in row for row in result.get('candidates', [])), message)
        return
    observed = result.get('sources')
    need(type(observed) is list and len(observed) == len(expected), message)
    for index, (source, want) in enumerate(zip(observed, expected)):
        singular = {'source_asset_id': want['asset_id'], 'source_sha256': want['sha256'], 'source_role': want['role']}
        # Reuse the same identity/type contract as the legacy primary observation.
        validate_source_reply({'source': source, 'candidates': []}, singular, message)
        need(type(source.get('slot')) is int and source['slot'] == index+1, message)
    for row in result.get('candidates', []):
        need('source_assignment' not in row, message)
        items = row.get('source_assignments')
        need(type(items) is list and len(items) == len(expected), message)
        for index, (item, want) in enumerate(zip(items, expected)):
            need(type(item) is dict and type(item.get('slot')) is int and item['slot'] == index+1, message)
            singular = {'source_asset_id': want['asset_id'], 'source_sha256': want['sha256'], 'source_role': want['role']}
            validate_source_reply({'source': observed[index], 'candidates': [{'source_assignment': {**item, 'slot': 1}}]}, singular, message)


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
