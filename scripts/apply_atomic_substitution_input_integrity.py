"""One-shot guarded fix for substitution staged-input integrity."""
from pathlib import Path

path = Path('studio_workflow/setup_drafts.py')
text = path.read_text(encoding='utf-8')
old = """            record={'draft':fresh['after'],'inputs':copy.deepcopy(current['inputs']),
                    'runtime':copy.deepcopy(current['runtime']),
                    'graph_sha256':current['graph_sha256']}
"""
new = """            after_inputs=self._inputs(fresh['after'])
            need(canonical(after_inputs)==canonical(current['inputs']),
                 'Substitution changes staged inputs; use the explicit staging workflow')
            record={'draft':fresh['after'],'inputs':after_inputs,
                    'runtime':copy.deepcopy(current['runtime']),
                    'graph_sha256':current['graph_sha256']}
"""
count = text.count(old)
print(f'staged-input receipt replacement: {count} exact match(es)')
if count != 1:
    raise SystemExit(f'expected one exact substitution record, found {count}')
path.write_text(text.replace(old, new), encoding='utf-8')
print('Staged-input integrity patch applied.')
