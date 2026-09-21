"""One-shot guarded patch for bounded setup-context CLI reads."""
from pathlib import Path

path = Path('studio_workflow/setup_context_compatibility.py')
text = path.read_text(encoding='utf-8')
old = """        raw = args.request.read_bytes()
        need(len(raw) <= MAX_INPUT_BYTES,
             'Setup context request exceeds 1 MiB')
"""
new = """        with args.request.open('rb') as stream:
            raw = stream.read(MAX_INPUT_BYTES + 1)
        need(len(raw) <= MAX_INPUT_BYTES,
             'Setup context request exceeds 1 MiB')
"""
count = text.count(old)
print(f'bounded CLI read replacement: {count} exact match(es)')
if count != 1:
    raise SystemExit(f'expected one exact CLI read block, found {count}')
path.write_text(text.replace(old, new), encoding='utf-8')
print('Setup-context CLI bounded-read patch applied.')
