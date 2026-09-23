"""Trigger follow-up: does the Niji Sweet Spot look survive without @NJSW33T, and with the trigger at a lower LoRA strength?

    python trigger2.py render
    python trigger2.py seal

Coordinator's request, 23 September 2026. The `krea-anime-atelier-gguf` graph at its authored defaults (768x1152, 15 steps
euler_ancestral, TextFusion 1.0 + Niji Sweet Spot, its witch prompt, text encoder on the CPU), three new seeds 2026092396-98, and
four configurations:
- `start-1.0`: the authored prompt with "@NJSW33T, " at the start, Niji Sweet Spot 1.0 (the reference look);
- `none-1.0`: no trigger, Niji Sweet Spot 1.0;
- `start-0.7`: the trigger at the start, Niji Sweet Spot 0.7;
- `none-0.0`: no trigger and Niji Sweet Spot pruned (TextFusion only), a control showing how much of the look is the LoRA.
Judged blind per seed: style fidelity to the triggered look (group letters shuffled, the reference among them, unknown) and
whether text is painted, searched at full resolution.
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import labkit  # noqa: E402

SEEDS = [2026092396, 2026092397, 2026092398]
CONFIGS = {'start-1.0': (True, 1.0), 'none-1.0': (False, 1.0), 'start-0.7': (True, 0.7), 'none-0.0': (False, 0.0)}
OUT = HERE / 'followup'


def graph(config, seed):
    trig, niji = CONFIGS[config]
    g = json.loads((labkit.REPO / 'workflows/api/krea-anime-atelier-gguf-api.json').read_text(encoding='utf-8'))
    text = g['4']['inputs']['text']; assert text.startswith('@NJSW33T, ')
    g['4']['inputs']['text'] = text if trig else text[len('@NJSW33T, '):]
    assert 'Niji' in g['11']['inputs']['lora_name']; g['11']['inputs']['strength_model'] = niji
    g = labkit.prune_loras(g)
    g['7']['inputs']['seed'] = seed
    g['9']['inputs']['filename_prefix'] = 'Research/overnight-20260923/krea-trigger/followup-%s-%d' % (config, seed)
    return g


def render():
    results = labkit.Results(OUT)
    for config in CONFIGS:  # config-major so each text is encoded once and reused from the cache for the other seeds
        for seed in SEEDS:
            labkit.run_graph(graph(config, seed), '%s-%d' % (config, seed), results, timeout=1800, extra={'config': config, 'seed': seed})


def seal():
    items = [{'group': 's%d' % (SEEDS.index(r['seed']) + 1), 'config': r['config'], 'file': r['outputs'][0]['file']}
             for r in labkit.Results(OUT).records if r.get('status') == 'success' and r.get('outputs')]
    print(labkit.seal(items, OUT))


if __name__ == '__main__':
    {'render': render, 'seal': seal}[sys.argv[1]]()
