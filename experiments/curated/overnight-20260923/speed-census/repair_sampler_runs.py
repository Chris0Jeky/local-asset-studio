"""Remove earlier jobs' sampler runs from the census records (Codex review of #859, P1).

    python repair_sampler_runs.py

The census ran with a labkit that did not yet filter ComfyUI log entries by submission time, so each record's
`sampler_runs` accumulated every earlier job still in ComfyUI's 300-entry log buffer. A job's own run is the latest one, so
this keeps at most the LAST run, and only when it (a) has the step count of the job's own KSampler (from the submitted
recipe) and (b) its progress-line elapsed time fits inside the job's own load-to-decode window from `phases.json`
(between 0.5x and 1.1x). Anything else is dropped and marked `sampler_runs_unverified` with the reason; nothing is guessed.
The untouched originals are kept as `sampler_runs_contaminated` for audit.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
records = json.loads((HERE / 'results.json').read_text(encoding='utf-8'))
windows = dict((p['label'], p.get('sampling')) for p in json.loads((HERE / 'phases.json').read_text(encoding='utf-8')))


def recipe_steps(record):
    recipe = json.loads((HERE / record['recipe_file']).read_text(encoding='utf-8'))
    graph = recipe.get('prompt') or recipe.get('graph') or recipe.get('submitted_graph') or recipe
    if isinstance(graph, dict) and 'workflow' in graph and isinstance(graph['workflow'], dict): graph = graph['workflow']
    for node in (graph.values() if isinstance(graph, dict) else []):
        if isinstance(node, dict) and node.get('class_type') in ('KSampler', 'KSamplerAdvanced'): return node['inputs'].get('steps')
    return None


for r in records:
    runs = r.get('sampler_runs_contaminated', r.get('sampler_runs')) or []
    r['sampler_runs_contaminated'] = runs
    steps, window = recipe_steps(r), windows.get(r['label'])
    last = runs[-1] if runs else None
    reason = None
    if last is None: reason = 'no sampler progress lines captured'
    elif steps is None: reason = 'no KSampler steps found in the submitted recipe'
    elif last['total_steps'] != steps: reason = 'last run has %s steps, the job had %s' % (last['total_steps'], steps)
    elif window is None: reason = "the job's own load/decode log lines were lost from ComfyUI's log buffer, so the run cannot be attributed"
    elif not 0.5 * window <= last['elapsed_s_tqdm'] <= 1.1 * window:
        reason = 'last run elapsed %s s does not fit the job window of %s s (lines lost to the log buffer)' % (last['elapsed_s_tqdm'], window)
    if reason:
        r['sampler_runs'] = []; r['sampler_runs_unverified'] = reason
    else:
        r['sampler_runs'] = [last]; r.pop('sampler_runs_unverified', None)
    print(r['label'], 'kept' if not reason else 'UNVERIFIED: ' + reason, r['sampler_runs'])
(HERE / 'results.json').write_text(json.dumps(records, indent=1) + '\n', encoding='utf-8', newline='\n')
