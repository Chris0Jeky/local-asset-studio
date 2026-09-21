"""One-shot guarded fix for strict reviewed-mapping revision pins."""
from pathlib import Path

path = Path('studio_workflow/setup_context_compatibility.py')
text = path.read_text(encoding='utf-8')
old = """    result['review_revision'] = compatibility.identity(value['review_revision'])
    need(result['review_revision'] is not None,
         'Reviewed mapping revision is required')
"""
new = """    need(isinstance(value['review_revision'], str)
         and source_compatibility.REVIEW_REVISION.fullmatch(
             value['review_revision']) is not None,
         'Reviewed mapping revision must remain a sha256:<64 lowercase hex> review pin')
    result['review_revision'] = value['review_revision']
"""
count = text.count(old)
print(f'review-pin validation replacement: {count} exact match(es)')
if count != 1:
    raise SystemExit(f'expected one exact review-pin block, found {count}')
path.write_text(text.replace(old, new), encoding='utf-8')
print('Strict setup review-pin validation applied.')
