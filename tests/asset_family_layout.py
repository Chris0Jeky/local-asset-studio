"""Network-free native layout check using the actual Asset dialog markup and CSS.

This checks geometry only; the separate HTTP browser journey owns interactions.
"""
import argparse
import json
from pathlib import Path
import re

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
FAMILY = '''<section id="assetFamily" class="asset-family"><h3>Family &amp; reuse</h3>
<div class="asset-family-actions"><button>Same recipe, new seed</button><button>Same seed, edit words</button><button>Use as reference</button></div>
<p>Recorded steps, oldest first. Missing or put-away steps stay visible. No generation submitted.</p>
<ol class="asset-family-strip"><li><button><b>Draft · 1</b><small>Draft · Seed 12</small></button></li></ol>
<button>Show children</button></section>'''


def exercise(out, executable=None):
    source = (ROOT/'app/static/index.html').read_text(encoding='utf-8')
    match = re.search(r'<dialog id="assetDialog"(?=[\s>]).*?</dialog>', source, flags=re.S)
    assert match is not None, 'The real Asset dialog is unavailable'
    marker = '<div id="assetLineage"></div>'
    assert match[0].count(marker) == 1
    dialog = match[0].replace(marker, marker+FAMILY)
    styles = '\n'.join((ROOT/'app/static'/name).read_text(encoding='utf-8') for name in
                       ('style.css', 'studio.css', 'asset-review.css', 'asset-family.css'))
    html = '<style>'+styles+'</style><body class="studio-shell"><main class="studio-main">'+dialog+'</main></body>'
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=executable)
        try:
            for width in (1440, 390):
                for zoom in (1, 2):
                    page = browser.new_page(viewport={'width': width, 'height': 1000})
                    page.route('**/*', lambda route: route.abort())
                    try:
                        page.set_content(html)
                        page.locator('#assetDialog').evaluate('(dialog)=>dialog.showModal()')
                        page.evaluate('(zoom)=>document.documentElement.style.zoom=zoom', zoom)
                        geometry = page.evaluate('''() => ({viewport:innerWidth, elements:
                          [...document.querySelectorAll('#assetDialog,#assetFamily,#assetFamily button')].map(el=>{
                            const r=el.getBoundingClientRect();return {id:el.id||el.textContent,
                              left:r.left,right:r.right,client:el.clientWidth,scroll:el.scrollWidth};})})''')
                        for item in geometry['elements']:
                            assert item['left'] >= -1 and item['right'] <= geometry['viewport']+1, (width, zoom, item)
                            assert item['scroll'] <= item['client']+1, (width, zoom, item)
                        results.append({'width': width, 'zoom': zoom, 'viewport_contained': True, 'geometry': geometry})
                    finally:
                        page.close()
        finally:
            browser.close()
    out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'network_used': False, 'checks': results}, indent=2)+'\n', encoding='utf-8')
    print('Asset family layout: all four viewport/zoom combinations are contained')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='.runtime/asset-family/layout-report.json')
    parser.add_argument('--browser')
    args = parser.parse_args()
    exercise(args.out, args.browser)
