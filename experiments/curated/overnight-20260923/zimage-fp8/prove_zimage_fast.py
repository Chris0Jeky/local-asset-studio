"""Studio proof of `zimage-fast` after #893 (fp8 build, text encoder on the CPU) (23 September 2026, overnight lab).

    python prove_zimage_fast.py

One `POST /api/jobs` at the preset's authored defaults: the shipped zimage prompt (a teal enamel camping lantern product photo),
seed 2026091101, 1024x1024, 8 steps. Records go to proof/ with the exact submitted recipe and the runtime identity.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import labkit  # noqa: E402

intent = {'preset_id': 'zimage-fast', 'controls': {}, 'batch_count': 1, 'references': [], 'parent_assets': []}
labkit.run_studio(intent, 'zimage-fast-proof', labkit.Results(HERE / 'proof'), timeout=1200,
                  extra={'config': 'studio-proof-defaults', 'preset_id': 'zimage-fast', 'backend_id': 'primary'})
