"""Why does the Krea atelier stack paint "@NJSW33T" into the picture? (23 September 2026, overnight lab)

    python krea_trigger.py render
    python krea_trigger.py seal

Both GGUF runs with Niji Sweet Spot tonight (#880: prompt 976da1a8 and Studio job 29e468ca) painted the trigger word as visible
text. Hypothesis: the trigger token at the start of the prompt is rendered as text, helped by the TextFusion LoRA. Method: the
`krea-anime-atelier-gguf` graph at its authored defaults (768x1152, 15 steps euler_ancestral, TextFusion 1.0 + Niji Sweet Spot
1.0, its witch prompt, text encoder on the CPU), two seeds, four configurations that differ only in the trigger and TextFusion:
- `start`: "@NJSW33T, " at the start (the authored prompt);
- `end`: the same prompt with ", @NJSW33T" at the end instead;
- `none`: no trigger;
- `start-noTF`: the trigger at the start, TextFusion pruned (strength 0).
Judged blind per seed for visible text (any legible or pseudo-legible glyphs), plus the usual rubric. Original character: Git-safe.
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import labkit  # noqa: E402

SEEDS = [281715418, 2026092391]
CONFIGS = ['start', 'end', 'none', 'start-noTF']


def graph(config, seed):
    g = json.loads((labkit.REPO / 'workflows/api/krea-anime-atelier-gguf-api.json').read_text(encoding='utf-8'))
    text = g['4']['inputs']['text']; assert text.startswith('@NJSW33T, '), text[:20]
    body = text[len('@NJSW33T, '):]
    g['4']['inputs']['text'] = {'start': text, 'end': body + ', @NJSW33T', 'none': body, 'start-noTF': text}[config]
    if config == 'start-noTF': g['10']['inputs']['strength_model'] = 0
    g = labkit.prune_loras(g)
    g['7']['inputs']['seed'] = seed
    g['9']['inputs']['filename_prefix'] = 'Research/overnight-20260923/krea-trigger/%s-%d' % (config, seed)
    return g


def render():
    results = labkit.Results(HERE)
    for seed in SEEDS:
        for config in CONFIGS:
            labkit.run_graph(graph(config, seed), '%s-%d' % (config, seed), results, timeout=1800, extra={'config': config, 'seed': seed})


def seal():
    results = labkit.Results(HERE)
    items = [{'group': 's%d' % (SEEDS.index(r['seed']) + 1), 'config': r['config'], 'file': r['outputs'][0]['file']}
             for r in results.records if r.get('status') == 'success' and r.get('outputs')]
    print(labkit.seal(items, HERE))


if __name__ == '__main__':
    {'render': render, 'seal': seal}[sys.argv[1]]()
