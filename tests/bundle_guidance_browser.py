"""Actual Explorer/scripts, production Handler stack and evaluator, synthetic inputs.

Run with existing Playwright/Chromium; no installations or models. Normal mode
uses native browser HTTP on Studio's allowed port. --inert uses inserted assets,
data-module URLs and a Python HTTP bridge (not browser-origin/network evidence).
Both modes exercise the real create_server Handler and read-only guidance route.
"""
import argparse
import base64
import copy
from http.client import HTTPConnection
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from test_bundle_guidance import fixture, G


def serialized(value):
    return json.dumps(value, ensure_ascii=True).replace('<', '\\u003c')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT/'.runtime/bundle-guidance-browser')
    parser.add_argument('--chromium')
    parser.add_argument('--inert', action='store_true')
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location('guidance_browser_server', ROOT/'app/server.py')
    server = importlib.util.module_from_spec(spec); spec.loader.exec_module(server)
    p, graph, manifest, knowledge = fixture()
    p.update(name='Turbo composition study', family='Synthetic fixture', choices={'sampler':['euler'], 'scheduler':['simple']})
    p['defaults']={key:graph[pairs[0][0]]['inputs'][pairs[0][1]] for key,pairs in G.bindings(p).items()}
    recipe={'id':'fixture-study','name':'Turbo composition study','preset_id':'fixture','family':'Synthetic fixture',
            'controls':{},'status':'unverified','notes':'Synthetic interaction fixture: deliberately high steps to demonstrate conditional advice. No artwork or model-quality evidence.'}
    shell='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Contextual guidance fixture</title><link rel="stylesheet" href="/static/bundle-explorer.css"></head><body><main><p>Synthetic browser fixture — no inference.</p><div id="createView"><label><input id="presetSearch"></label><textarea id="positive"></textarea><input id="batch" value="1"></div><p id="status"></p></main><script>
const esc=v=>String(v??'').replace(/[&<>\\'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
let catalog={presets:[PRESET]},atelierRecipes=[RECIPE],knowledge=KNOWLEDGE,installedLoras=[],selected=catalog.presets[0],submitting=false,parentAssets=[],referenceRecords=[],calls=[];
function values(){return {...selected.defaults};}function selectPreset(){calls.push('select');}function applyRecipe(){calls.push('apply');}function showView(){calls.push('view');}function message(v){document.querySelector('#status').textContent=v;}
async function api(path){const r=await fetch(path);const value=await r.json();if(!r.ok)throw Error(value.error||'Request failed');return value;}
</script><script src="/static/bundle-core.js"></script><script src="/static/bundle-explorer.js"></script></body></html>'''
    shell=shell.replace('PRESET',serialized(p)).replace('RECIPE',serialized(recipe)).replace('KNOWLEDGE',serialized(knowledge))
    calls=[]; slow=threading.Event()
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        for folder in ('presets','models','workflows/api'): (root/folder).mkdir(parents=True)
        def write_kb(value): (root/'presets/settings-kb.json').write_text(json.dumps(value))
        write_kb(knowledge); (root/'models/library.json').write_text(json.dumps(manifest))
        (root/p['graph']).write_text(json.dumps(graph))
        class ReadOnlyStudio:
            def __init__(self, _): self.root=root;self.lock=threading.RLock()
            def preset(self, key):
                if key!=p['id']: raise ValueError('Unknown preset')
                return copy.deepcopy(p)
            def graph_for(self, preset): return copy.deepcopy(graph),root/preset['graph']
            def inspect_preset(self, key): return {'graph':graph,'requirements':[],'nodes':[]}
            def __getattr__(self,key): raise AssertionError('Runtime/storage access forbidden: '+key)
        def factory(address, handler):
            class ObservedHandler(handler):
                def do_GET(self):
                    calls.append(('GET',self.path))
                    if self.path=='/':
                        data=shell.encode();self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
                    return super().do_GET()
                def do_POST(self):
                    calls.append(('POST',self.path))
                    if self.path!='/api/workflow-studio/guidance':
                        return self._json(405,{'error':'Write/inference route forbidden in fixture'})
                    return super().do_POST()
                def _json(self,status,value):
                    if isinstance(value,dict) and value.get('format')==G.FORMAT and any(c['current']==9 for r in value['claims'] for c in r['checks']):
                        slow.set();time.sleep(.8)
                    try: return super()._json(status,value)
                    except (BrokenPipeError,ConnectionResetError): pass
            return ThreadingHTTPServer(address,ObservedHandler)
        http=server.create_server(root,port=0 if args.inert else 8191,http_server=factory,studio_factory=ReadOnlyStudio)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        def bridge(value):
            path=value['path']; method=value.get('method','GET')
            if path not in ('/api/inspect/fixture','/api/workflow-studio/guidance'): raise AssertionError(path)
            connection=HTTPConnection('127.0.0.1',http.server_port,timeout=5)
            try:
                connection.request(method,path,value.get('body'),headers={'Host':'127.0.0.1:8191','Origin':'http://127.0.0.1:8191','Content-Type':'application/json'})
                reply=connection.getresponse();return {'status':reply.status,'body':reply.read().decode()}
            finally: connection.close()
        def inert():
            import re
            def module(name):
                code=(ROOT/'app/static'/name).read_text()
                for dependency in re.findall(r"(?:import\(['\"]|import ['\"])(/static/[^'\"]+)",code):
                    code=code.replace(dependency,module(dependency.split('/')[-1]))
                return 'data:text/javascript;base64,'+base64.b64encode(code.encode()).decode()
            markup=shell
            for name in ('bundle-explorer.css','bundle-tuning.css','bundle-guidance.css','bundle-workflow.css'):
                markup=markup.replace('</head>','<style>'+(ROOT/'app/static'/name).read_text()+'</style></head>')
            markup=markup.replace('<link rel="stylesheet" href="/static/bundle-explorer.css">','')
            for name in ('bundle-core.js','bundle-explorer.js'):
                code=(ROOT/'app/static'/name).read_text()
                for dependency in re.findall(r"import\(['\"](/static/[^'\"]+)",code): code=code.replace(dependency,module(dependency.split('/')[-1]))
                markup=markup.replace('<script src="/static/'+name+'"></script>','<script>'+code+'</script>')
            transport="""<script>window.fetch=async(path,options={})=>{const r=await fixtureHTTP({path,method:options.method||'GET',body:options.body});return new Response(r.body,{status:r.status});};</script>"""
            return markup.replace('<script>',transport+'<script>',1)
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True,executable_path=args.chromium or shutil.which('chromium'),args=['--no-sandbox'])
                for width in (1440,720,390):
                    write_kb(knowledge);(root/'models/library.json').write_text(json.dumps(manifest));slow.clear()
                    page=browser.new_page(viewport={'width':width,'height':1000},reduced_motion='reduce')
                    page.set_default_timeout(10000); errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    if args.inert:page.expose_function('fixtureHTTP',bridge);page.set_content(inert())
                    else:page.goto('http://127.0.0.1:8191/')
                    print(f'BEGIN {width}px guidance browser',flush=True)
                    page.locator('#bundleLauncher').focus();page.keyboard.press('Enter')
                    page.locator('[data-bundle="fixture-study"]').click()
                    panel=page.locator('#bundleScopedGuidance')
                    page.wait_for_function("document.querySelector('#bundleScopedGuidance')?.textContent.includes('Outside this source')")
                    print(f'{width}px outside-source state rendered',flush=True)
                    assert page.locator('[data-bundle-control="steps"]').input_value()=='15'
                    panel.get_by_role('button',name='Find control').first.click()
                    assert page.evaluate("document.activeElement.dataset.bundleControl")=='steps'
                    page.locator('[data-bundle-control="steps"]').fill('4')
                    page.wait_for_function("document.querySelector('#bundleScopedGuidance')?.textContent.includes('steps · current 4')")
                    assert 'Outside this source' not in panel.inner_text()
                    page.locator('[data-bundle-control="steps"]').fill('9')
                    # Poll through Playwright, allowing injected transport callbacks to run.
                    for _ in range(25):
                        page.wait_for_timeout(50)
                        if slow.is_set():break
                    assert slow.is_set()
                    page.locator('[data-bundle-control="steps"]').fill('4')
                    page.wait_for_timeout(1100)
                    assert 'current 4' in panel.text_content() and 'current 9' not in panel.text_content()
                    page.locator('[data-bundle-control="lora4"]').fill('0')
                    page.wait_for_function("document.querySelector('#bundleScopedGuidance')?.textContent.includes('Not applicable')")
                    assert 'Outside this source' not in panel.text_content()
                    page.locator('[data-bundle-control="lora4"]').fill('1')
                    page.wait_for_function("document.querySelector('#bundleScopedGuidance')?.textContent.includes('Applies to catalog pins')")
                    # Declared guidance conflicts stay visible instead of selecting a compromise.
                    conflict=copy.deepcopy(knowledge);other=copy.deepcopy(conflict['guidance']['claims'][0]);other['id']='other-source';other['settings'][0]['recommended']={'values':[8]};conflict['guidance']['claims'].append(other);write_kb(conflict)
                    panel.get_by_role('button',name='Recheck guidance').click()
                    page.wait_for_function("document.querySelector('#bundleScopedGuidance')?.textContent.includes('Sources disagree')")
                    assert page.locator('[data-bundle-control="steps"]').input_value()=='4'
                    # Raw text stays text; no source metadata becomes executable markup.
                    conflict['guidance']['claims'][0]['title']='<img src=x onerror="window.guidanceInjected=1">';write_kb(conflict)
                    panel.get_by_role('button',name='Recheck guidance').click()
                    page.wait_for_function("document.querySelector('#bundleScopedGuidance')?.textContent.includes('<img src=x')")
                    assert page.evaluate('window.guidanceInjected===undefined') and panel.locator('img').count()==0
                    write_kb(knowledge)
                    (root/'models/library.json').write_text('{"assets":[]}')
                    panel.get_by_role('button',name='Recheck guidance').click()
                    page.wait_for_function("document.querySelector('#bundleScopedGuidance')?.textContent.includes('Scope unknown')")
                    (root/'models/library.json').unlink()
                    panel.get_by_role('button',name='Recheck guidance').click()
                    page.wait_for_function("document.querySelector('#bundleScopedGuidance')?.textContent.includes('No such file')")
                    assert panel.locator('.bundle-guidance-results details').count()==0
                    (root/'models/library.json').write_text(json.dumps(manifest))
                    page.locator('[data-bundle-control="steps"]').fill('15')
                    page.wait_for_function("document.querySelector('#bundleScopedGuidance')?.textContent.includes('Outside this source')")
                    print(f'{width}px outside-source state rendered',flush=True)
                    panel.scroll_into_view_if_needed();page.screenshot(path=str(args.out/f'guidance-{width}.png'))
                    assert page.evaluate("document.querySelector('#bundleExplorer').scrollWidth<=document.querySelector('#bundleExplorer').clientWidth")
                    page.locator('[data-bundle-control="steps"]').fill('')
                    page.wait_for_function("document.querySelector('#bundleScopedGuidance')?.textContent.includes('finite number')")
                    assert panel.locator('.bundle-guidance-results details').count()==0
                    page.keyboard.press('Escape');assert page.evaluate('document.activeElement.id')=='bundleLauncher'
                    assert page.evaluate('calls.length')==0
                    assert not errors,errors
                    page.close();print(f'PASS {width}px {"inert assets / real Python HTTP" if args.inert else "native browser / production Handler"}: conditional advice, stale reply, conflicts, text safety, missing registry, unchanged workbench')
                browser.close()
            assert all(method!='POST' or path=='/api/workflow-studio/guidance' for method,path in calls),calls
        finally:http.shutdown();http.server_close();thread.join(5)


if __name__=='__main__':main()
