"""Markdown table of one experiment folder's results.json (+ judgements.jsonl when present).

    python table.py <folder>
"""
import json, sys
from pathlib import Path

folder = Path(sys.argv[1])
records = json.loads((folder / 'results.json').read_text(encoding='utf-8'))
judged = {}
jf = folder / 'judgements.jsonl'
if jf.exists():
    for line in jf.read_text(encoding='utf-8').splitlines():
        j = json.loads(line); judged[Path(j['image']).name] = j
print('| label | status | prompt | total s | sampler s/step (steady) | peak dedicated MB | peak shared MB | spill | verdict |')
print('| --- | --- | --- | --- | --- | --- | --- | --- | --- |')
for r in records:
    prompt = (r.get('prompt_id') or (r.get('prompt_ids') or [''])[0] or '')[:8]
    total = r.get('elapsed_seconds') or r.get('history_execution_seconds') or r.get('wall_seconds')
    ws = (r.get('ws') or {}).get('samplers') or []
    if ws: sps = ', '.join('%s' % s.get('s_per_step_steady') for s in ws)
    else:
        runs = r.get('sampler_runs') or []
        sps = str(runs[-1].get('s_per_step_steady') or runs[-1].get('s_per_step_tqdm')) + ' (log)' if runs else '-'
    files = [f['file'] for f in (r.get('output_files') or r.get('outputs') or [])]
    verdict = next((judged[Path(f).name]['verdict'] for f in files if Path(f).name in judged), '')
    print('| %s | %s | `%s` | %s | %s | %s | %s | %s | %s |' % (r['label'], r.get('status'), prompt, round(total, 1) if total else '-', sps,
          r.get('peak_dedicated_mb'), r.get('peak_shared_mb'), 'yes' if r.get('spilled') else 'no', verdict))
