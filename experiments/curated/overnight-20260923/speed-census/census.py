"""Speed census of verified presets at their authored defaults, through the Studio (23 September 2026, overnight lab).

    python census.py [preset-id ...]

One Studio job per preset (POST /api/jobs with empty controls = the authored graph values), one at a time, ordered so
that presets sharing a model family run back to back. Each record: the job and prompt IDs, Studio elapsed seconds,
sampler s/step (steady state from ComfyUI's own log timestamps), peak dedicated/shared GPU memory of the ComfyUI
process, and the output file hashes. Already-recorded presets are skipped; nothing is ever resubmitted, except one
deliberate retry of the known first-checkpoint-swap `free_memory` IndexError (it fails before sampling).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import labkit  # noqa: E402

ORDER = ['wai', 'anime', 'pony', 'noob', 'cstati-v3-baseline', 'yumeflux-ilv1-baseline',
         'anima-portrait', 'anima-artist-stack', 'janima-v1-baseline', 'zimage', 'krea-portrait']


def swap_indexerror(record):
    text = str(record.get('failure')) + str(record.get('message'))
    return record.get('status') == 'failed' and 'list index out of range' in text


def main(ids):
    results = labkit.Results(HERE)
    for preset in ids or ORDER:
        intent = {'preset_id': preset, 'controls': {}, 'batch_count': 1, 'references': [], 'parent_assets': []}
        record = labkit.run_studio(intent, preset, results, timeout=2400, extra={'preset_id': preset})
        if swap_indexerror(record) and not results.find(preset + '-retry'):
            print('known free_memory IndexError before sampling; one deliberate retry', flush=True)
            labkit.run_studio(intent, preset + '-retry', results, timeout=2400, extra={'preset_id': preset, 'retry_of': record.get('job_id')})


if __name__ == '__main__':
    main(sys.argv[1:])
