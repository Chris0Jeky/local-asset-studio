"""One-shot guarded patch for canonical source-observation ordering."""
from pathlib import Path

path = Path('studio_workflow/source_compatibility.py')
text = path.read_text(encoding='utf-8')
old = (
    "    source_observations, gallery = gallery_claims(\n"
    "        report, candidate['id'], version_id, diagnostics)\n"
    "    evidence = [provider_evidence] + [\n"
)
new = (
    "    source_observations, gallery = gallery_claims(\n"
    "        report, candidate['id'], version_id, diagnostics)\n"
    "    source_observations = sorted(source_observations, key=canonical)\n"
    "    evidence = [provider_evidence] + [\n"
)
count = text.count(old)
print(f'observation ordering replacement: {count} exact match(es)')
if count != 1:
    raise SystemExit(f'expected one source observation block, found {count}')
path.write_text(text.replace(old, new), encoding='utf-8')
print('Source-observation canonical ordering patch applied.')
