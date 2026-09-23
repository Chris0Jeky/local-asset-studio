"""Studio proofs of the two GGUF Krea presets from #873 (23 September 2026, overnight lab).

    python prove_gguf_presets.py

One `POST /api/jobs` per preset at its authored defaults (the page's own path), one at a time, after the Studio server was
restarted to load #873's catalog. Records go to proofs/results.json with the Studio job and prompt IDs, the recipe
(`/api/jobs/<id>/recipe`, the exact submitted graph) and GPU timelines; outputs are then inspected at full resolution.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import labkit  # noqa: E402

results = labkit.Results(HERE / 'proofs')
for preset in ('krea-portrait-gguf', 'krea-anime-atelier-gguf'):
    intent = {'preset_id': preset, 'controls': {}, 'batch_count': 1, 'references': [], 'parent_assets': []}
    # labkit.run_studio records the Studio's active backend and ComfyUI's version/argv with every job (runtime_identity);
    # the preset's declared backend goes in too, so a receipt names the runtime without the catalog.
    labkit.run_studio(intent, preset, results, timeout=2400, extra={'preset_id': preset, 'config': 'studio-proof', 'backend_id': 'primary'})
