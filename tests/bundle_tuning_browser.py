"""Opt-in real-origin Chromium tuning tests with an inert workbench and HTTP fixture.

python tests/bundle_tuning_browser.py [screenshot-directory] [--inert]

--inert uses set_content, inline assets and mock read transport when navigation is
not permitted. Only the fixed module URL is replaced with the same generated
bytes as a data module (plus a delay); this does not test real-origin delivery.
Requires already installed Playwright and Chromium. No automatic installation.
The parent delivery unittest separately covers the actual Studio Handler.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import base64
import json
import os
import shutil
import sys
import threading
import time
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Bundle tuning fixture</title><link rel="stylesheet" href="/static/bundle-explorer.css"></head><body><main><p>Synthetic interaction fixture. No model inference or artwork.</p><div id="createView"><label><input id="presetSearch"></label><textarea id="positive"></textarea><select id="batch"><option>1</option><option selected>4</option></select></div><p id="status"></p></main><script src="/test-fixture.js"></script><script>
const esc=v=>String(v??'').replace(/[&<>\\'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const p=BundleFixture.preset;BundleFixture.source.id='krea-witch-nijisis';
let catalog={presets:[p]},selected=p,work={...p.defaults},submitting=false,parentAssets=['source-a'],referenceRecords=[],calls=[],applied=null;
let atelierRecipes=[BundleFixture.source,BundleFixture.target],knowledge=BundleFixture.knowledge,installedLoras=[];
async function api(path){const response=await fetch(path);if(!response.ok)throw Error('Fixture inspection failed');return response.json();}
function values(){return {...work};}function selectPreset(id){calls.push('select');selected=catalog.presets.find(x=>x.id===id);work={...selected.defaults};parentAssets=[];document.querySelector('#batch').value='1';}function applyRecipe(r){calls.push('apply');applied=r;work={...work,...r.controls};document.querySelector('#batch').value=String(r.batch_count);}function showView(v){calls.push('view:'+v);}function message(v){document.querySelector('#status').textContent=v;}
document.addEventListener('keydown',e=>{if(e.ctrlKey&&e.key==='Enter')calls.push('UNEXPECTED_GENERATE');});
</script><script src="/static/bundle-core.js"></script><script src="/static/bundle-explorer.js"></script></body></html>'''


class FixtureHandler(BaseHTTPRequestHandler):
    requests = []
    def log_message(self, *_): pass
    def do_GET(self):
        self.requests.append(('GET', self.path))
        if self.path == '/': data, mime = HTML.encode(), 'text/html'
        elif self.path == '/test-fixture.js':
            data, mime = (ROOT / 'tests/bundle_tuning_fixture.js').read_bytes(), 'text/javascript'
        elif self.path.startswith('/static/') and self.path.split('/')[-1] in {
            'bundle-core.js', 'bundle-explorer.js', 'bundle-showcase.js', 'bundle-explorer.css', 'bundle-tuning.css'
        }:
            if self.path.endswith('bundle-showcase.js'): time.sleep(.25)
            data = (ROOT / 'app/static' / self.path.split('/')[-1]).read_bytes()
            mime = 'text/css' if self.path.endswith('.css') else 'text/javascript'
        elif self.path == '/api/inspect/paint':
            data = json.dumps({'graph': {'1': {'inputs': {'ckpt_name': 'synthetic-base.safetensors'}},
                 '9': {'inputs': {'lora_name': 'ink.safetensors', 'strength_model': 1}},
                 '10': {'inputs': {'lora_name': 'turbo.safetensors', 'strength_model': 0}}}}).encode()
            mime = 'application/json'
        else:
            self.send_error(404); return
        self.send_response(200); self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_POST(self):
        self.requests.append(('POST', self.path)); self.send_error(405)


def inert_html():
    markup = HTML
    for name in ('bundle-explorer.css', 'bundle-tuning.css'):
        style = '<style>' + (ROOT / 'app/static' / name).read_text(encoding='utf-8') + '</style>'
        markup = markup.replace('</head>', style + '</head>')
    markup = markup.replace('<link rel="stylesheet" href="/static/bundle-explorer.css">', '')
    module = "await new Promise(resolve=>setTimeout(resolve,250));\n" + (ROOT / 'app/static/bundle-showcase.js').read_text(encoding='utf-8')
    module_url = 'data:text/javascript;base64,' + base64.b64encode(module.encode()).decode()
    files = {'/test-fixture.js': ROOT / 'tests/bundle_tuning_fixture.js',
             '/static/bundle-core.js': ROOT / 'app/static/bundle-core.js',
             '/static/bundle-explorer.js': ROOT / 'app/static/bundle-explorer.js'}
    for url, path in files.items():
        code = path.read_text(encoding='utf-8')
        if path.name == 'bundle-explorer.js':
            code = code.replace("import('/static/bundle-showcase.js')", 'import(' + json.dumps(module_url) + ')')
        markup = markup.replace('<script src="' + url + '"></script>', '<script>' + code + '</script>')
    mock = """<script>window.reads=[];window.fetch=async(path,options={})=>{
      reads.push({path,method:options.method||'GET'});
      if(path!='/api/inspect/paint')throw Error('Unexpected fixture fetch: '+path);
      return new Response(JSON.stringify({graph:{'1':{inputs:{ckpt_name:'synthetic-base.safetensors'}},
        '9':{inputs:{lora_name:'ink.safetensors',strength_model:1}},
        '10':{inputs:{lora_name:'turbo.safetensors',strength_model:0}}}}));
    };</script>"""
    return markup.replace('<script>', mock + '<script>', 1)


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('screenshots', nargs='?', type=Path)
    parser.add_argument('--inert', action='store_true')
    args = parser.parse_args()
    out = args.screenshots
    if out: out.mkdir(parents=True, exist_ok=True)
    http = ThreadingHTTPServer(('127.0.0.1', 0), FixtureHandler)
    thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, executable_path=os.environ.get('STUDIO_TEST_BROWSER') or shutil.which('chromium'), args=['--no-sandbox'])
            for width in (1440, 720, 390):
                page = browser.new_page(viewport={'width': width, 'height': 1000}, reduced_motion='reduce')
                errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
                if args.inert: page.set_content(inert_html())
                else: page.goto(f'http://127.0.0.1:{http.server_port}/')
                page.locator('#bundleLauncher').focus(); page.keyboard.press('Enter')
                page.locator('[data-bundle="krea-witch-nijisis"]').click()
                page.locator('[data-bundle-control="positive"]').fill('My preserved character brief')
                page.wait_for_timeout(400)
                assert page.locator('[data-bundle-control="positive"]').input_value() == 'My preserved character brief'
                if not args.inert: assert any(path == '/static/bundle-showcase.js' for _, path in FixtureHandler.requests)
                assert page.locator('#bundleBody figure').count() == 1
                page.keyboard.press('Control+Enter'); assert page.evaluate('calls.length') == 0
                page.locator('#bundleAlternative').select_option('fast')
                page.locator('#bundlePropose').click()
                assert 'Sampling' in page.locator('#bundleProposal').inner_text()
                assert 'wash_trigger is absent' in page.locator('#bundleProposal').inner_text()
                assert page.locator('#bundleStage').is_disabled()
                page.locator('#bundleProposalConsent').check(); page.locator('#bundleStage').click()
                assert page.locator('[data-bundle-control="steps"]').input_value() == '4'
                assert page.locator('[data-bundle-control="lora2"]').input_value() == '1'
                assert page.evaluate('calls.length') == 0
                page.locator('#bundleUndo').click()
                assert page.locator('[data-bundle-control="steps"]').input_value() == '30'
                page.locator('#bundleRedo').click()
                assert page.locator('[data-bundle-control="steps"]').input_value() == '4'
                assert not page.locator('#bundleConsent').is_checked()
                page.locator('[data-bundle-control="width"]').fill('769')
                page.locator('#bundlePropose').click()
                assert 'multiple' in page.locator('#bundleProposal').inner_text()
                page.locator('#bundleReset').click()
                page.locator('#bundlePropose').click()
                page.evaluate("atelierRecipes[1].notes='Changed after proposal'")
                page.locator('#bundleProposalConsent').check(); page.locator('#bundleStage').click()
                assert 'changed' in page.locator('#bundleProposal').inner_text()
                assert page.evaluate('calls.length') == 0
                page.locator('#bundlePropose').click()
                if out:
                    page.locator('#bundleTuning').scroll_into_view_if_needed()
                    page.screenshot(path=str(out / f'tuning-{width}.png'))
                assert page.evaluate("document.querySelector('#bundleExplorer').scrollWidth <= document.querySelector('#bundleExplorer').clientWidth")
                page.locator('#bundleProposalConsent').check(); page.locator('#bundleStage').click()
                page.locator('#bundleConsent').check(); page.locator('#bundleApply').click()
                assert page.evaluate('calls') == ['select', 'apply', 'view:create']
                assert page.evaluate('work.steps') == 4
                assert page.evaluate('applied.status') == 'unverified'
                assert page.evaluate('applied.evidence') is None
                assert page.locator('#batch').input_value() == '1'
                page.locator('#bundleLauncher').click()
                assert page.locator('#bundleApply').count() == 0
                page.keyboard.press('Escape'); assert page.evaluate('document.activeElement.id') == 'bundleLauncher'
                assert not errors, errors
                if args.inert: assert page.evaluate("reads.every(r=>r.method==='GET')")
                page.close(); print(f'PASS {width}px ({"inert" if args.inert else "HTTP fixture"}): native module load, delayed index, proposal, grouped stage, undo/redo, validation, stale source, unexecuted handoff, no implicit writes')
            browser.close()
        assert all(method == 'GET' for method, _ in FixtureHandler.requests), FixtureHandler.requests
    finally:
        http.shutdown(); http.server_close(); thread.join(timeout=5)


if __name__ == '__main__': run()
