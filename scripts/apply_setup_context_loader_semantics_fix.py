"""One-shot guarded fix for setup loader alternative/unknown semantics."""
from pathlib import Path

path = Path('studio_workflow/setup_context_compatibility.py')
text = path.read_text(encoding='utf-8')

old = """        'required_node_classes': sorted(compatibility.strings(
            value['required_node_classes'],
            'binding required node classes',
            MAX_BINDING_NODES,
            allow_empty=False,
        )),
"""
new = """        'required_node_classes': sorted(compatibility.strings(
            value['required_node_classes'],
            'binding required node classes',
            MAX_BINDING_NODES,
            allow_empty=True,
        )),
"""
count = text.count(old)
print(f'empty binding replacement: {count} exact match(es)')
if count != 1:
    raise SystemExit(f'expected one exact binding block, found {count}')
text = text.replace(old, new)

old = """def _required_nodes(candidate: dict) -> set[str]:
    result = {
        requirement[len('node:'):]
        for requirement in candidate['requires']
        if requirement.startswith('node:') and len(requirement) > len('node:')
    }
    for loader in candidate['loaders']:
        node_class = loader.split('.', 1)[0]
        if node_class:
            result.add(node_class)
    return result
"""
new = """def _required_nodes(candidate: dict, selected_loader: str) -> set[str]:
    result = {
        requirement[len('node:'):]
        for requirement in candidate['requires']
        if requirement.startswith('node:') and len(requirement) > len('node:')
    }
    # Candidate loaders are alternatives. Only the loader selected by this slot
    # becomes an implicit node requirement; explicit node:* companions remain
    # mandatory regardless of loader selection.
    if selected_loader in candidate['loaders']:
        node_class = selected_loader.split('.', 1)[0]
        if node_class:
            result.add(node_class)
    return result
"""
count = text.count(old)
print(f'selected loader replacement: {count} exact match(es)')
if count != 1:
    raise SystemExit(f'expected one exact required-nodes function, found {count}')
text = text.replace(old, new)

old = "        required_nodes = _required_nodes(candidate)\n"
new = "        required_nodes = _required_nodes(candidate, slot['loader'])\n"
count = text.count(old)
print(f'required-nodes call replacement: {count} exact match(es)')
if count != 1:
    raise SystemExit(f'expected one exact required-nodes call, found {count}')

path.write_text(text.replace(old, new), encoding='utf-8')
print('Setup context loader semantics fix applied.')
