"""Fill job_id, prompt_id and original_image on an experiment's judgement records from its results.json, by sha256.

    python fill_ids.py <experiment-folder> [--source-ok]

Idempotent. A record whose image matches no recorded run is left alone and reported; with --source-ok such records are marked
`no_run: true` (a source picture sealed into a blind group). Mirrors labkit.judge()'s lookup for records written before it.
"""
import json, sys
from pathlib import Path


def index(folder):
    out = {}
    for r in json.loads((folder / 'results.json').read_text(encoding='utf-8')):
        prompt = r.get('prompt_id') or ((r.get('prompt_ids') or [None])[0])
        for o in (r.get('output_files') or []) + [o for o in (r.get('outputs') or []) if isinstance(o, dict) and o.get('sha256')]:
            if o.get('sha256'): out[o['sha256']] = (r.get('job_id'), prompt, o.get('file'))
    return out


folder = Path(sys.argv[1]); source_ok = '--source-ok' in sys.argv
idx = index(folder); path = folder / 'judgements.jsonl'
lines = [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines()]
missing = []
for j in lines:
    hit = idx.get(j['sha256'])
    if hit:
        j['job_id'] = j.get('job_id') or hit[0]; j['prompt_id'] = j.get('prompt_id') or hit[1]
        j['original_image'] = j.get('original_image') or hit[2]; j['no_run'] = False
    elif source_ok: j['no_run'] = True; j.setdefault('original_image', j['image'])
    else: missing.append(Path(j['image']).name)
path.write_text(''.join(json.dumps(j) + '\n' for j in lines), encoding='utf-8', newline='\n')
print(folder.name, len(lines), 'records;', 'unmatched:', missing or 'none')
