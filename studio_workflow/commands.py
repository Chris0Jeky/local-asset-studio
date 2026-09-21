"""Pure document commands. Authoring changes are never execution authority."""
from __future__ import annotations
import copy
import re
from .core import canonical, decode, document, ID, RESERVED, link, need, digest

MAX_COMMANDS = 256


def identifier(value):
    need(isinstance(value, str) and bool(ID.fullmatch(value)) and value not in RESERVED, 'Invalid identifier')
    return value


def fields(value, required, optional=()):
    need(isinstance(value, dict) and set(required) <= set(value)
         and set(value) <= set(required) | set(optional), 'Invalid command fields')


def execution_inputs_sha256(doc):
    """Conservative authored inputs identity; NOT a runnable plan or compiled hash.

    Includes disconnected drafts. Excludes layout, labels, step presentation and
    source annotations. Actual selected-output identity comes from the compiler.
    """
    return digest({key: doc[key] for key in ('backend_id', 'schema_sha256', 'outputs', 'disabled', 'bypass')}
                  | {'nodes': {key: {'class_type': node['class_type'], 'inputs': node['inputs']}
                               for key, node in doc['nodes'].items()}})


class StateConflict(ValueError):
    def __init__(self, expected, current):
        super().__init__('Authoring state changed; inspect before applying an inverse')
        self.expected_sha256, self.current_sha256 = expected, current


def state_sha256(doc):
    """All authoring data except the server-assigned append-only revision."""
    return digest({key: value for key, value in document(doc).items() if key != 'revision'})


def apply_commands(source, commands):
    doc = document(source)
    need(isinstance(commands, list) and 1 <= len(commands) <= MAX_COMMANDS, 'Use 1–256 commands')
    commands = decode(canonical(commands))
    for command in commands:
        need(isinstance(command, dict), 'Each command must be an object')
        op = command.get('op')
        if op == 'assert_state':
            fields(command, ('op', 'sha256'))
            expected = command['sha256']
            need(isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected), 'Invalid expected authoring digest')
            current = state_sha256(doc)
            if expected != current: raise StateConflict(expected, current)
        elif op == 'import_module':
            from .modules import insert_module
            doc = insert_module(doc, command)
        elif op in ('put_step', 'remove_step', 'set_step_enabled', 'duplicate_step', 'move_step'):
            from .steps import apply_step_command
            apply_step_command(doc, command)
        elif op == 'replace':
            fields(command, ('op', 'document'))
            replacement = document(command['document'])
            replacement['revision'] = doc['revision']
            doc = replacement
        elif op == 'rename':
            fields(command, ('op', 'name')); doc['name'] = command['name']
        elif op == 'add_node':
            fields(command, ('op', 'id', 'node')); key = identifier(command['id'])
            need(key not in doc['nodes'], 'Node already exists')
            doc['nodes'][key] = copy.deepcopy(command['node'])
        elif op == 'select_outputs':
            fields(command, ('op', 'outputs')); doc['outputs'] = copy.deepcopy(command['outputs'])
        elif op == 'accept_schema':
            fields(command, ('op', 'backend_id', 'schema_sha256'))
            doc['backend_id'], doc['schema_sha256'] = command['backend_id'], command['schema_sha256']
        elif op in ('remove_node', 'set_input', 'unset_input', 'connect', 'disconnect', 'set_enabled', 'set_position', 'set_bypass'):
            key = identifier(command.get('id')); need(key in doc['nodes'], 'Unknown node: ' + key)
            node = doc['nodes'][key]
            if op == 'remove_node':
                fields(command, ('op', 'id'))
                # Keep consumers' dangling links so the compiler can explain them.
                from .steps import remove_member
                remove_member(doc, key)
                del doc['nodes'][key]; doc['positions'].pop(key, None); doc['bypass'].pop(key, None)
                for field in ('outputs', 'disabled'): doc[field] = [x for x in doc[field] if x != key]
            elif op == 'set_enabled':
                fields(command, ('op', 'id', 'enabled')); need(type(command['enabled']) is bool, 'enabled must be boolean')
                doc['disabled'] = [x for x in doc['disabled'] if x != key]
                if not command['enabled']: doc['disabled'].append(key)
            elif op == 'set_position':
                fields(command, ('op', 'id', 'position')); doc['positions'][key] = copy.deepcopy(command['position'])
            elif op == 'set_bypass':
                fields(command, ('op', 'id', 'output', 'input'))
                need(type(command['output']) is int and 0 <= command['output'] <= 9999, 'Invalid output index')
                mapping = doc['bypass'].setdefault(key, {})
                if command['input'] is None: mapping.pop(str(command['output']), None)
                else: mapping[str(command['output'])] = command['input']
            else:
                field = command.get('input')
                need(isinstance(field, str) and 0 < len(field) <= 256 and field not in RESERVED, 'Invalid input name')
                if op in ('unset_input', 'disconnect'):
                    fields(command, ('op', 'id', 'input'))
                    node['inputs'].pop(field, None)
                    doc['bypass'][key] = {port: name for port, name in doc['bypass'].get(key, {}).items() if name != field}
                elif op == 'set_input':
                    fields(command, ('op', 'id', 'input', 'value'))
                    need(not link(command['value']), 'Use connect for typed links')
                    node['inputs'][field] = copy.deepcopy(command['value'])
                else:
                    fields(command, ('op', 'id', 'input', 'source', 'output'))
                    other = identifier(command['source']); need(other in doc['nodes'], 'Unknown source node')
                    need(type(command['output']) is int and 0 <= command['output'] <= 9999, 'Invalid output index')
                    node['inputs'][field] = [other, command['output']]
        else:
            raise ValueError('Unknown document command: ' + str(op))
        # Every prefix must remain structurally meaningful; cycles/unknown schema
        # inputs may remain as draft errors and are handled by compile_document.
        doc = document(doc)
    return doc


def changes(before, after):
    """Bounded, inert review summary. Exact revisions remain separately readable."""
    old, new = before['nodes'], after['nodes']
    return {'added_nodes': sorted(set(new) - set(old)), 'removed_nodes': sorted(set(old) - set(new)),
            'changed_nodes': sorted(k for k in set(old) & set(new) if old[k] != new[k]),
            'changed_fields': [k for k in sorted(set(before) | set(after))
                               if k not in ('nodes', 'revision') and before.get(k) != after.get(k)],
            'execution_inputs_changed': execution_inputs_sha256(before) != execution_inputs_sha256(after)}
