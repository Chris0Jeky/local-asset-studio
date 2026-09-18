"""Run the complete Workshop presentation browser suite with layered production CSS."""
import base64
from pathlib import Path

import workshop_browser_core as core

ROOT = Path(__file__).resolve().parents[1]


def immersive_css() -> str:
    entrypoint = (ROOT / 'app/static/workshop-immersive.css').read_text(encoding='utf-8')
    entrypoint = entrypoint.replace("@import url('workshop-immersive-core.css');", '')
    css = (ROOT / 'app/static/workshop-immersive-core.css').read_text(encoding='utf-8') + '\n' + entrypoint
    for name in ('night-shift.svg', 'quiet-morning.svg'):
        data = base64.b64encode((ROOT / 'app/static/workshop-assets' / name).read_bytes()).decode('ascii')
        css = css.replace(f'/static/workshop-assets/{name}', f'data:image/svg+xml;base64,{data}')
    return css


core.immersive_css = immersive_css

if __name__ == '__main__':
    core.main()
