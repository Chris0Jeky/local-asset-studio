"""krea-refine on the GGUF build with the CPU text encoder, against the fp8 Studio runs at 0.25 (23 September 2026, overnight lab).

    python gguf_refine.py run     # 3 direct prompts: each seed's exact Studio-submitted d025 graph, GGUF + CPU encoder
    python gguf_refine.py seal    # blind pairs per seed (fp8 Studio output vs GGUF) + key-gguf.sealed.json

The fp8 `krea-refine` runs at the new 0.25 default took 338-373 s each with up to 5.6 GB of the process in shared memory.
Question: does the `krea-portrait-gguf` recipe (#873/#880: `UnetLoaderGGUF` + `CLIPLoader device: cpu`) carry over to the refine
graph with the same picture? Method: each seed's own submitted graph (graphs/d025-<seed>.recipe.json -> workflow) with only the
diffusion loader and the encoder device changed; the same staged source, prompt, LoRAs, 4 steps and denoise 0.25.
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import labkit  # noqa: E402

SEEDS = [2026092381, 2026092382, 2026092383]
OUT = HERE / 'gguf'


def graph(seed):
    g = json.loads((HERE / 'graphs' / ('d025-%d.recipe.json' % seed)).read_text(encoding='utf-8'))['workflow']
    unet = next(k for k, v in g.items() if v['class_type'] == 'UNETLoader')
    g[unet] = {'class_type': 'UnetLoaderGGUF', 'inputs': {'unet_name': 'krea2_turbo-Q5_K_M.gguf'}}
    clip = next(k for k, v in g.items() if v['class_type'] == 'CLIPLoader'); g[clip]['inputs']['device'] = 'cpu'
    save = next(k for k, v in g.items() if v['class_type'] == 'SaveImage')
    g[save]['inputs']['filename_prefix'] = 'Research/overnight-20260923/krea-refine-foxes/gguf-d025-%d' % seed
    return g


def run():
    results = labkit.Results(OUT)
    for seed in SEEDS:
        labkit.run_graph(graph(seed), 'gguf-d025-%d' % seed, results, timeout=1800, extra={'config': 'gguf-cpute-d025', 'seed': seed})


def seal():
    fp8 = dict((r['seed'], r['output_files'][0]['file']) for r in json.loads((HERE / 'results.json').read_text(encoding='utf-8'))
               if r['config'] == 'denoise-0.25')
    items = []
    for r in labkit.Results(OUT).records:
        if r.get('status') == 'success' and r.get('outputs'):
            g = 's%d' % (SEEDS.index(r['seed']) + 1)
            items += [{'group': g, 'config': 'gguf-cpute', 'file': r['outputs'][0]['file']}, {'group': g, 'config': 'fp8-studio', 'file': fp8[r['seed']]}]
    print(labkit.seal(items, OUT))


if __name__ == '__main__':
    {'run': run, 'seal': seal}[sys.argv[1]]()
