"""Actual shipped Look UI, production listing/prepare and disposable SQLite Workspace; inert runtime.

python tests/looks_visual_reference_browser.py --output /path/to/evidence
No model process, generation, user database or CSS/image override is used.
"""
import argparse
import importlib.util
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

import studio_browser_smoke as fixture
import looks
from workspace import AssetWorkspace

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('preview_static_server', ROOT / 'app/server.py')
production_server = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(production_server)
PATH = '/static/look-previews/night-shift-ma-responsive-1024.webp'
SHA = '156df8bb9178be20691f5a6d0686a32d9be67daad61f84252119a15ccd489192'
VIEWPORTS = [(320, 900), (390, 844), (430, 932), (1536, 1060)]
REACHABILITY = '''e=>{const r=e.getBoundingClientRect(),dock=document.querySelector('.wk-run-dock').getBoundingClientRect(),header=document.querySelector('.studio-globalbar').getBoundingClientRect();return {rect:[r.x,r.y,r.width,r.height],visible:r.top>=header.bottom+4&&r.bottom<=innerHeight,overlapDock:r.left<dock.right&&r.right>dock.left&&r.top<dock.bottom&&r.bottom>dock.top,dock:[dock.x,dock.y,dock.width,dock.height],headerBottom:header.bottom,scroll:[scrollY,document.documentElement.scrollHeight-innerHeight]}}'''


def settle_keyboard_scroll(page):
    # Observe native keyboard scrolling; do not choose a replacement scroll position.
    page.evaluate('''()=>new Promise(resolve=>{let previous=scrollY,stable=0;function frame(){const current=scrollY;stable=Math.abs(current-previous)<.1?stable+1:0;previous=current;if(stable>=4)resolve();else requestAnimationFrame(frame)}requestAnimationFrame(frame)})''')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    report = {'scope': __doc__.split('\n')[0], 'created_utc': datetime.now(timezone.utc).isoformat(), 'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'source_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT).strip()),
              'viewports': [], 'checks': [], 'transfers': [], 'posts': [], 'errors': [], 'external_requests': []}
    def check(value, message):
        assert value, message
        report['checks'].append(message)
    raw = (ROOT / 'app' / PATH.lstrip('/')).read_bytes()
    check(len(raw) == 26460 and hashlib.sha256(raw).hexdigest() == SHA, 'Exact qualified 26,460-byte derivative')
    with tempfile.TemporaryDirectory() as tmp:
        assets = AssetWorkspace(Path(tmp) / 'assets')
        studio = SimpleNamespace(root=ROOT, assets=assets, catalog=lambda: fixture.CATALOG)
        before = looks.listing(studio)['looks'][0]
        seed = json.loads((ROOT / 'presets/looks.json').read_text(encoding='utf-8'))['looks'][0]
        check(before['lineage'] == seed['lineage'] and before['body'] == seed['body'], 'Actual SQLite seed preserves original recipe and Z2 lineage')
        class Handler(fixture.Handler):
            # Production remains pinned to 8191; this disposable test owns a random loopback port.
            def _safe_host(self):
                return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'
            _json = production_server.Handler._json
            def do_GET(self):
                path = urlsplit(self.path).path
                if path == '/api/looks': return self.json(looks.listing(studio))
                if path == PATH:
                    report['transfers'].append({'bytes': len(raw), 'sha256': SHA})
                if path == '/' or (path.startswith('/static/') and path != '/static/vendor/model-viewer/model-viewer.min.js'):
                    return production_server.Handler.do_GET(self)
                return super().do_GET()
            def do_POST(self):
                if self.path == '/api/looks/prepare':
                    payload = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
                    report['posts'].append({'path': self.path, 'payload': payload})
                    return self.json(looks.prepare(studio, payload))
                report['posts'].append({'path': self.path})
                return super().do_POST()
        with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
            report['owned_port'] = server.server_port
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    report['browser_version'] = browser.version
                    try:
                        for width, height in VIEWPORTS:
                            context = browser.new_context(viewport={'width': width, 'height': height}, device_scale_factor=1, reduced_motion='reduce')
                            page = context.new_page(); transfers_start = len(report['transfers'])
                            page.on('pageerror', lambda e: report['errors'].append(str(e)))
                            page.on('request', lambda r: report['external_requests'].append(r.url) if urlsplit(r.url).scheme in ('http', 'https') and urlsplit(r.url).hostname != '127.0.0.1' else None)
                            page.on('dialog', lambda dialog: dialog.accept())
                            page.goto(f'http://127.0.0.1:{server.server_port}/')
                            page.wait_for_function("document.querySelector('#lookSelect option[value=\"look-night-shift-retro-anime\"]')")
                            page.evaluate("showView('create');selectPreset('zimage-fast')")
                            check(len(report['transfers']) == transfers_start, f'{width}: startup does not load optional art')
                            page.locator('#lookBlock > summary').click()
                            page.locator('#lookSelect').select_option(before['id'])
                            check(page.locator('#lookPreview').get_attribute('open') is None and page.locator('#lookPreviewImage').get_attribute('src') is None, f'{width}: Look selection leaves preview folded/unloaded')
                            page.locator('#lookScene').fill('a rainy rooftop')
                            state = page.evaluate('JSON.stringify(StudioSetupDraft.capture())')
                            with page.expect_response(lambda response: urlsplit(response.url).path == PATH) as delivered:
                                page.locator('#lookPreview > summary').click()
                            response = delivered.value
                            data = response.body()
                            check(response.status == 200 and response.headers['content-type'] == 'image/webp' and len(data) == 26460 and hashlib.sha256(data).hexdigest() == SHA, f'{width}: actual production HTTP response bytes/hash/MIME verified')
                            page.wait_for_function("const i=document.querySelector('#lookPreviewImage');i.complete&&i.naturalWidth===1024&&!i.hidden")
                            check(state == page.evaluate('JSON.stringify(StudioSetupDraft.capture())'), f'{width}: preview opening does not change recipe/draft')
                            check(len(report['transfers']) == transfers_start + 1, f'{width}: explicit opening transfers one small derivative')
                            reachability = {'natural_caption': page.locator('#lookPreview figcaption').evaluate(REACHABILITY)}
                            page.screenshot(path=str(args.output/f'natural-entry-{width}.png'))
                            page.locator('#lookPreview>summary').focus()
                            for selector in ['#lookPrepare','#lookTrash']:
                                page.keyboard.press('Tab')
                                check(page.locator(selector).evaluate('e=>e===document.activeElement'), f'{width}: keyboard reaches {selector}')
                                focused=page.locator(selector).evaluate(REACHABILITY)
                                check(focused['visible'] and not focused['overlapDock'], f'{width}: keyboard focus clears dock for {selector}')
                                reachability[selector] = focused
                            page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)')
                            end=page.locator('#createView').evaluate('''e=>{const nodes=[...e.querySelectorAll('input,button,select,textarea,summary')].filter(n=>n.checkVisibility({contentVisibilityAuto:true,visibilityProperty:true})&&!n.closest('.wk-run-dock')),last=nodes.at(-1),r=last.getBoundingClientRect(),dock=document.querySelector('.wk-run-dock').getBoundingClientRect();return {lastText:last.textContent.slice(0,100),lastBottom:r.bottom,dockTop:dock.top,clear:r.bottom<=dock.top,scroll:[scrollY,document.documentElement.scrollHeight-innerHeight]}}''')
                            check(end['clear'] and abs(end['scroll'][0]-end['scroll'][1])<2, f'{width}: maximum scroll retains bottom control clearance')
                            reachability['maximum_scroll']=end
                            page.screenshot(path=str(args.output/f'maximum-scroll-{width}.png'))
                            page.locator('#lookPreview>summary').focus()
                            for selector in ['#lookPrepare','#lookTrash']:
                                page.keyboard.press('Tab');focused=page.locator(selector).evaluate(REACHABILITY)
                                check(focused['visible'] and not focused['overlapDock'], f'{width}: keyboard recovers {selector} from maximum scroll')
                            page.locator('#lookPreview>summary').focus();settle_keyboard_scroll(page)
                            keys=[]
                            for _ in range(24):
                                caption=page.locator('#lookPreview figcaption').evaluate(REACHABILITY)
                                if caption['visible'] and not caption['overlapDock']:break
                                key='ArrowUp' if caption['rect'][1]<caption['headerBottom']+4 else 'ArrowDown'
                                page.keyboard.press(key);keys.append(key);settle_keyboard_scroll(page)
                            caption=page.locator('#lookPreview figcaption').evaluate(REACHABILITY)
                            check(caption['visible'] and not caption['overlapDock'], f'{width}: settled keyboard navigation exposes caption without pointer-selected scroll')
                            reachability['keyboard_caption']=caption
                            reachability['caption_navigation_keys']=keys
                            page.screenshot(path=str(args.output/f'keyboard-caption-{width}.png'))
                            # Separate art-inspection crop; the reachability checks above do not rely on this position.
                            page.locator('#lookPreview').evaluate("e=>window.scrollTo(0,window.scrollY+e.getBoundingClientRect().top-120)")
                            geometry = page.locator('#lookPreview').evaluate('''e=>{const i=e.querySelector('img'),c=e.querySelector('figcaption'),a=i.getBoundingClientRect(),b=c.getBoundingClientRect(),s=getComputedStyle(c),p=getComputedStyle(c.querySelector('p'));return {image:[a.x,a.y,a.width,a.height],copy:[b.x,b.y,b.width,b.height],copyBackground:s.backgroundColor,textColor:p.color,natural:[i.naturalWidth,i.naturalHeight],alt:i.alt,animation:getComputedStyle(i).animationName,docWidth:document.documentElement.scrollWidth}}''')
                            check(geometry['docWidth'] <= width, f'{width}: no application horizontal overflow')
                            check(abs(geometry['image'][2]/geometry['image'][3] - 16/9) < .01, f'{width}: whole frame reserves 16:9')
                            check(geometry['copy'][1] >= geometry['image'][1] + geometry['image'][3] - 1, f'{width}: independent copy stays below art')
                            check(geometry['copyBackground'] == 'rgb(17, 23, 31)', f'{width}: copy has opaque backing')
                            check(geometry['animation'] == 'none' and bool(geometry['alt']), f'{width}: static image has meaningful accessible description')
                            check(page.locator('#lookPreview figcaption').evaluate('''e=>{const r=e.getBoundingClientRect(),hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return e.contains(hit)}'''), f'{width}: copy is readable above existing fixed dock')
                            page.locator('#lookPreview').screenshot(path=str(args.output/f'application-preview-{width}.png'))
                            page.screenshot(path=str(args.output/f'application-context-{width}.png'), full_page=True)
                            page.locator('#lookScene').fill('a rainy rooftop')
                            page.locator('#lookPrepare').click()
                            page.wait_for_function("document.querySelector('#lookStatus').textContent.includes('Nothing was generated')")
                            check('a rainy rooftop' in page.locator('#positive').input_value(), f'{width}: actual prepare puts typed scene in wording')
                            check(page.locator('#lookPreviewImage').get_attribute('src') == PATH, f'{width}: preparing does not turn reference into recipe input')
                            page.locator('#lookSelect').select_option('')
                            check(page.locator('#lookPreview').is_hidden() and page.locator('#lookPreviewImage').get_attribute('src') is None, f'{width}: changing selection clears preview')
                            report['viewports'].append({'viewport': [width,height], 'dpr': 1, 'reduced_motion': 'reduce', 'geometry': geometry,
                                                       'reachability':reachability,
                                                       'http_delivery': {'status': response.status,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'content_type':response.headers['content-type']},
                                                       'preview_png': f'application-preview-{width}.png', 'context_png': f'application-context-{width}.png'})
                            context.close()
                        context = browser.new_context(viewport={'width':390,'height':844}, forced_colors='active')
                        page = context.new_page(); before_transfers = len(report['transfers'])
                        page.goto(f'http://127.0.0.1:{server.server_port}/')
                        page.wait_for_function("document.querySelector('#lookSelect option[value=\"look-night-shift-retro-anime\"]')")
                        page.evaluate("showView('create');selectPreset('zimage-fast')")
                        page.locator('#lookBlock > summary').click();page.locator('#lookSelect').select_option(before['id']);page.locator('#lookPreview > summary').click()
                        page.locator('#lookPreviewFallback').wait_for(state='visible')
                        check(page.locator('#lookPreviewImage').is_hidden() and page.locator('#lookPreviewFallback').is_visible(), 'Forced colors retains meaningful text fallback')
                        check(len(report['transfers']) == before_transfers, 'Forced colors does not request optional art')
                        page.locator('#lookPreview').screenshot(path=str(args.output/'application-forced-colors-390.png'));context.close()
                        context = browser.new_context(viewport={'width':390,'height':844})
                        page = context.new_page(); page.route('**'+PATH, lambda route: route.fulfill(status=404, body='Unavailable'))
                        page.goto(f'http://127.0.0.1:{server.server_port}/');page.wait_for_function("document.querySelector('#lookSelect option[value=\"look-night-shift-retro-anime\"]')")
                        page.evaluate("showView('create');selectPreset('zimage-fast')")
                        page.locator('#lookBlock > summary').click();page.locator('#lookSelect').select_option(before['id']);page.locator('#lookPreview > summary').click()
                        page.locator('#lookPreviewFallback').wait_for(state='visible')
                        check(page.locator('#lookPreviewImage').is_hidden(), '404 suppresses broken image')
                        page.locator('#lookScene').fill('a rainy rooftop');check(page.locator('#lookPrepare').is_enabled(), 'Missing optional art never blocks Look preparation')
                        page.locator('#lookPreview').screenshot(path=str(args.output/'application-missing-picture-390.png'));context.close()
                    finally: browser.close()
                after = studio.assets.card(before['id'])
                check(after['body'] == before['body'] and after['lineage'] == before['lineage'] and after['revision'] == before['revision'], 'Preview/prepare preserve saved content and revision')
                check(all(row['path'] in ('/api/looks/prepare','/api/estimate') for row in report['posts']) and sum(row['path']=='/api/looks/prepare' for row in report['posts']) == 4, 'Four explicit prepares plus existing estimates; no jobs/generation mutations')
                check(not report['errors'] and not report['external_requests'], 'Zero page errors or external requests')
            finally: server.shutdown();thread.join(timeout=5)
            report['server_thread_joined'] = not thread.is_alive()
    (args.output/'browser-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f"PASS {len(report['checks'])} application checks; four real viewports; optional WebP unchanged")


if __name__ == '__main__': main()
