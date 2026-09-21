"""One-shot guarded fix for setup-slot objective grammar."""
from pathlib import Path

path = Path('studio_workflow/setup_compatibility.py')
text = path.read_text(encoding='utf-8')
old = """    for key in ('role', 'modality', 'architecture', 'loader', 'runtime', 'objective'):
        need(token(value[key], 160), 'Setup slot ' + key + ' is required')
    need(value['base_lineage'] is None or token(value['base_lineage'], 160), 'Invalid base lineage')
"""
new = """    for key in ('role', 'modality', 'architecture', 'loader', 'runtime'):
        need(token(value[key], 160), 'Setup slot ' + key + ' is required')
    objective = identifier(value['objective'])
    need(value['base_lineage'] is None or token(value['base_lineage'], 160), 'Invalid base lineage')
"""
count = text.count(old)
print(f'objective grammar replacement: {count} exact match(es)')
if count != 1:
    raise SystemExit(f'expected one exact validate_slot block, found {count}')
text = text.replace(old, new)
old_return = """    return {**copy.deepcopy(value), 'formats': formats, 'capabilities': capabilities,
            'known_absent_capabilities': absent}
"""
new_return = """    return {**copy.deepcopy(value), 'objective': objective, 'formats': formats,
            'capabilities': capabilities, 'known_absent_capabilities': absent}
"""
count = text.count(old_return)
print(f'normalized objective return: {count} exact match(es)')
if count != 1:
    raise SystemExit(f'expected one validate_slot return block, found {count}')
path.write_text(text.replace(old_return, new_return), encoding='utf-8')
print('Setup compatibility objective grammar fix applied.')
