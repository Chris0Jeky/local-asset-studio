"""Read-only, bounded multi-target controls over existing workflow inputs.

This emits proposals, never applies them or certifies the graph for execution.
The ordinary document command service remains the sole authoring write boundary.
"""
from __future__ import annotations
import copy
import math
from .core import MAX_BYTES, RESERVED, canonical, catalog, decode, digest, document, link, need
from .commands import fields, identifier

FORMAT = 'studio.control/v1'
MAX_TARGETS = 32
MAX_CHOICES = 256
NOTICE = ('Literal authoring proposal only: no change was applied. Installed metadata does not certify '
          'runtime validation, model compatibility, memory fit, native widgets or execution authority.')


def _number(value):
    return type(value) is int or type(value) is float and math.isfinite(value)


def _scalar(value):
    return type(value) in (bool, int) or type(value) is float and math.isfinite(value) or (
        isinstance(value, str) and len(value) <= 65536)


def _validate(value):
    fields(value, ('document', 'expected_revision', 'control', 'value'))
    value = decode(canonical(value))
    doc = document(value['document'])
    need(type(value['expected_revision']) is int and 0 <= value['expected_revision'] <= 2**53 - 1,
         'expected_revision must be a nonnegative safe integer')
    control = value['control']
    fields(control, ('format', 'name', 'targets'))
    need(control['format'] == FORMAT, 'Expected ' + FORMAT)
    need(isinstance(control['name'], str) and 0 < len(control['name'].strip()) <= 120, 'Control name required (120 characters)')
    targets = control['targets']
    need(isinstance(targets, list) and 1 <= len(targets) <= MAX_TARGETS, 'Use 1–32 control targets')
    for target in targets:
        fields(target, ('node', 'input')); identifier(target['node'])
        field = target['input']
        need(isinstance(field, str) and 0 < len(field) <= 256 and field not in RESERVED, 'Invalid control input name')
    need(_scalar(value['value']), 'Proposed value must be a finite scalar (text limit 65536 characters)')
    return value, doc


def preview(value: dict, info: dict, backend_id: str) -> dict:
    value, doc = _validate(value)
    live = catalog(info, backend_id)
    control, proposed = value['control'], value['value']
    rows, diagnostics, specs, seen = [], [], [], set()

    def problem(code, message, target=None):
        diagnostics.append({'code': code, 'message': message,
                            'node': target['node'] if target else None,
                            'input': target['input'] if target else None})

    if value['expected_revision'] != doc['revision']:
        problem('stale_revision', 'The supplied draft revision differs from the expected revision. Read the current draft again.')
    if doc['backend_id'] != live['backend_id'] or doc['schema_sha256'] != live['schema_sha256']:
        problem('stale_schema', 'The backend or installed schema changed. Reload and review the workflow before previewing.')
    for target in control['targets']:
        key, field = target['node'], target['input']
        node = doc['nodes'].get(key)
        row = {**target, 'present': node is not None and field in node['inputs'],
               'current': copy.deepcopy(node['inputs'].get(field)) if node else None,
               'type': None, 'minimum': None, 'maximum': None, 'step_hint': None}
        rows.append(row)
        if (key, field) in seen: problem('duplicate_target', 'Select each node/input only once.', target)
        seen.add((key, field))
        if node is None:
            problem('missing_node', 'This node is absent from the draft.', target); continue
        kind = live['nodes'].get(node['class_type'])
        if kind is None:
            problem('missing_class', 'This node class is absent from the installed schema.', target); continue
        matches = [item for item in kind['inputs'] if item['name'] == field]
        if len(matches) != 1:
            problem('ambiguous_input' if matches else 'missing_input',
                    'The installed schema must identify this input exactly once.', target); continue
        spec = matches[0]; options = spec['options']; typ = spec['type']; row['type'] = typ
        raw_kind = info[node['class_type']]
        native = (kind.get('schema_errors') or spec['hidden'] or
                  spec['widget'] not in ('int', 'float', 'string', 'boolean', 'combo') or
                  any(raw_kind.get(flag, False) is not False for flag in ('input_is_list', 'INPUT_IS_LIST')) or
                  any(options.get(flag, False) is not False for flag in
                      ('forceInput', 'defaultInput', 'rawLink', 'remote', 'lazy', 'is_list')) or
                  'widgetType' in options)
        if native:
            problem('unsupported_input', spec.get('reason') or 'This input needs a native/dynamic/list or custom-behaviour adapter.', target)
            continue
        if link(row['current']):
            problem('connected_input', 'This input is connected. A shared literal must not silently remove its connection.', target)
        if typ in ('INT', 'FLOAT'):
            for name, output in (('min', 'minimum'), ('max', 'maximum'), ('step', 'step_hint')):
                if name in options: row[output] = options[name]
        elif typ == 'COMBO':
            choices = options.get('options')
            if not isinstance(choices, list) or not 1 <= len(choices) <= MAX_CHOICES or not all(_scalar(x) for x in choices):
                problem('unsupported_input', 'Use 1–256 finite scalar choices; larger or custom options need an adapter.', target)
                continue
        specs.append((target, spec))
        valid = (type(proposed) is int if typ == 'INT' else _number(proposed) if typ == 'FLOAT' else
                 type(proposed) is bool if typ == 'BOOLEAN' else isinstance(proposed, str) if typ == 'STRING' else
                 any(type(proposed) is type(x) and proposed == x for x in options['options']) if typ == 'COMBO' else False)
        if not valid:
            problem('invalid_value', 'Proposed value does not match ' + typ + ' or its declared choices.', target)
        elif typ in ('INT', 'FLOAT') and (('min' in options and proposed < options['min']) or
                                         ('max' in options and proposed > options['max'])):
            problem('out_of_range', 'Proposed value is outside this input’s declared range.', target)

    interface = {'type': None, 'minimum': None, 'maximum': None, 'choices': None}
    types = {spec['type'] for _, spec in specs}
    if len(types) > 1:
        for target, _ in specs: problem('type_mismatch', 'Shared targets must declare the same literal type; no coercion is performed.', target)
    elif specs:
        typ = interface['type'] = specs[0][1]['type']
        if typ in ('INT', 'FLOAT'):
            lows = [spec['options']['min'] for _, spec in specs if 'min' in spec['options']]
            highs = [spec['options']['max'] for _, spec in specs if 'max' in spec['options']]
            low, high = max(lows) if lows else None, min(highs) if highs else None
            interface.update(minimum=low, maximum=high)
            if low is not None and high is not None and (low > high or typ == 'INT' and math.ceil(low) > math.floor(high)):
                problem('empty_range', 'These inputs have no shared numeric range.')
        elif typ == 'COMBO':
            choices, keys = [], set()
            others = [{canonical(x) for x in spec['options']['options']} for _, spec in specs[1:]]
            for item in specs[0][1]['options']['options']:
                key = canonical(item)
                if key not in keys and all(key in other for other in others): choices.append(item); keys.add(key)
            interface['choices'] = choices
            if not choices: problem('empty_choices', 'These inputs have no shared typed choice.')
    result = {'format': 'studio.control-preview/v1', 'state': 'blocked' if diagnostics else 'ready',
              'document_revision': doc['revision'], 'document_sha256': digest(doc),
              'backend_id': live['backend_id'], 'schema_sha256': live['schema_sha256'],
              'control': control, 'control_sha256': digest(control), 'value': proposed,
              'targets': rows, 'mixed': len({canonical([row['present'], row['current']]) for row in rows}) > 1,
              'interface': interface, 'diagnostics': diagnostics, 'commands': [],
              'committed': False, 'generation_submitted': False, 'notice': NOTICE}
    if not diagnostics:
        result['commands'] = [{'op': 'set_input', 'id': target['node'], 'input': target['input'], 'value': proposed}
                              for target in control['targets']]
    need(len(canonical(result)) <= MAX_BYTES, 'Control preview exceeds the 1 MiB report limit; use fewer targets or shorter text')
    return result


def request(value: dict, studio) -> dict:
    # Validate bounded caller data before asking the configured schema cache.
    _validate(value)
    with studio.lock:
        need(not studio.backends.busy, 'Environment switch is in progress')
        return preview(value, studio.node_info(False), studio.backends.active)
