"""Normalize output ports without inventing ports from malformed metadata.

This is presentation/authoring data, not ComfyUI's runtime validator. Retain
original documents and report errors on the affected node definition only.
"""
from __future__ import annotations


def outputs(raw: dict) -> tuple[list[dict], list[str]]:
    result, errors = [], []

    def port(index, kind, name, is_list):
        if type(index) is not int or not 0 <= index <= 9999:
            errors.append('Output index must be an integer from 0 to 9999')
        elif any(p['index'] == index for p in result):
            errors.append('Duplicate output index: ' + str(index))
        elif not isinstance(kind, str) or not kind.strip():
            errors.append('Output ' + str(index) + ' needs a nonempty type string')
        elif not isinstance(name, str):
            errors.append('Output ' + str(index) + ' name must be text')
        elif type(is_list) is not bool:
            errors.append('Output ' + str(index) + ' list annotation must be boolean')
        else:
            result.append({'index': index, 'type': kind, 'name': name, 'is_list': is_list})

    if 'outputs' in raw:
        # An explicitly malformed v2 field must not fall back to legacy ports.
        if not isinstance(raw['outputs'], list):
            return [], ['Output definitions must be an array']
        for index, item in enumerate(raw['outputs']):
            if not isinstance(item, dict):
                errors.append('Output ' + str(index) + ' definition must be an object')
                continue
            port(item.get('index', index), item.get('type'), item.get('name', str(index)), item.get('is_list', False))
    else:
        kinds = raw.get('output', [])
        if not isinstance(kinds, list):
            return [], ['Legacy output types must be an array']
        metadata = {}
        for field in ('output_name', 'output_is_list'):
            values = raw.get(field, [])
            if not isinstance(values, list):
                errors.append(field + ' must be an array')
                values = []
            if len(values) > len(kinds):
                errors.append(field + ' has entries without a corresponding output')
            metadata[field] = values
        names, lists = metadata['output_name'], metadata['output_is_list']
        for index, kind in enumerate(kinds):
            port(index, kind, names[index] if index < len(names) else str(kind),
                 lists[index] if index < len(lists) else False)
    return result, errors
