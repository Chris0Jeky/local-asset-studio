"""Top-level local gallery: ComfyUI output/Research/overnight-20260923/index.html linking every experiment's own index.html.

    python gallery_index.py

Each experiment line carries its one-line headline from the first sentence of its README's verdict or result, so the owner
can browse in the morning from one page. Never in Git (the pages show famous characters and fanservice cases).
"""
import html, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path('C:/AI/ComfyUI_windows_portable/ComfyUI/output/Research/overnight-20260923')
rows = []
for sub in sorted(p for p in ROOT.iterdir() if p.is_dir() and (p / 'index.html').exists()):
    readme = HERE / sub.name / 'README.md'
    title = sub.name
    if readme.exists():
        first = readme.read_text(encoding='utf-8').splitlines()[0]
        title = re.sub(r'^#\s*', '', first)
    cards = (sub / 'index.html').read_text(encoding='utf-8').count('<figure>')
    rows.append('<li><a href="%s/index.html">%s</a> <small>(%d pictures; evidence: experiments/curated/overnight-20260923/%s/)</small></li>'
                % (sub.name, html.escape(title), cards, sub.name))
page = ('<!doctype html><meta charset="utf-8"><title>overnight-20260923</title><style>body{font:15px sans-serif;background:#111;'
        'color:#ddd;max-width:980px;margin:24px auto}a{color:#9cf}li{margin:8px 0}</style><h1>Overnight lab, 23 September 2026</h1>'
        '<p>Agent-judged, not accepted. Every verdict under each picture is the lab agent\'s, with the rubric R1-R8; the owner '
        'decides. Famous-character and fanservice pictures live only here, never in Git.</p><ul>%s</ul>') % '\n'.join(rows)
(ROOT / 'index.html').write_text(page, encoding='utf-8'); print(ROOT / 'index.html', len(rows), 'experiments')
