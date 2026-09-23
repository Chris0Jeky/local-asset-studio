"""Studio proof of `anime-masked-repair` after #881 (feathered mask, default denoise 0.6) (23 September 2026, overnight lab).

    python prove_masked_repair.py

One `POST /api/jobs` at the preset's new defaults (denoise and graph as merged), on the same staged RGBA hand mask of
`Studio/noob_00004_.png` used by `hand_inpaint.py` (stage.json), with the same hand wording, seed 2026092361. Records go to
proof/results.json with the recipe (the exact submitted graph); the output is then checked for five digits and the seam
(`feather.py`'s edge-band measure).
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import labkit  # noqa: E402
from hand_inpaint import POSITIVE, NEGATIVE  # noqa: E402

staged = json.loads((HERE / 'stage.json').read_text(encoding='utf-8'))
controls = {'positive': POSITIVE, 'negative': NEGATIVE, 'seed': 2026092361, 'reference': staged['upload']['file']}
intent = {'preset_id': 'anime-masked-repair', 'controls': controls, 'batch_count': 1, 'references': [], 'parent_assets': []}
labkit.run_studio(intent, 'anime-masked-repair-proof', labkit.Results(HERE / 'proof'), timeout=900,
                  extra={'config': 'studio-proof-defaults', 'seed': 2026092361, 'preset_id': 'anime-masked-repair', 'backend_id': 'primary'})
