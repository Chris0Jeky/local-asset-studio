"""Opt-in full-page Chromium + actual Studio HTTP/SQLite, synthetic Comfy nodes.

Binds only an unused container loopback :8191. No worker thread, model execution,
owner configuration or installed ComfyUI is used. Native browser storage enabled.
"""
import argparse
import copy
import json
import hashlib
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from test_server import server
from test_workflow_preset_adapter import GRAPH, PRESET, INFO
from studio_workflow.core import canonical, catalog, new_document
from studio_workflow.document_http import store as documents
from studio_workflow.run_http import store as runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inert', action='store_true', help='Use injected HTTP bridge/storage when browser navigation is blocked; not native-origin proof')
    parser.add_argument('--chromium', default='/usr/bin/chromium')
    parser.add_argument('--out', type=Path, default=ROOT / '.runtime/saved-run-browser')
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        for p in ('presets', 'workflows/api', 'config', 'fake-comfy/input'): (root/p).mkdir(parents=True, exist_ok=True)
        (root/'presets/catalog.json').write_text(json.dumps({'presets':[PRESET]}), encoding='utf-8')
        (root/PRESET['graph']).write_text(json.dumps(GRAPH), encoding='utf-8')
        (root/'config/local.json').write_text(json.dumps({'comfy_root': str(root/'fake-comfy')}), encoding='utf-8')
        with patch.object(threading.Thread, 'start'):
            studio = server.Studio(root)
        info = copy.deepcopy(INFO)
        info['Render']['input'] = {'required': {'model':['MODEL'], 'clip':['CLIP'], 'text':['STRING', {'multiline':True}],
            'seed':['INT', {'min':0,'max':2**64-1}], 'steps':['INT', {'min':1,'max':150}],
            'width':['INT', {'min':64,'max':2048}], 'height':['INT', {'min':64,'max':2048}],
            'cfg':['FLOAT', {'min':0,'max':30}], 'batch_size':['INT', {'min':1,'max':1}]}}
        info['Model']['input'] = {'required': {'ckpt_name':[['fixed.safetensors']]}}
        info['LoraLoader']['input'] = {'required': {'model':['MODEL'], 'clip':['CLIP'], 'lora_name':[['optional.safetensors']],
            'strength_model':['FLOAT', {'min':0,'max':2}], 'strength_clip':['FLOAT', {'min':0,'max':2}]}}
        info['SaveImage']['input'] = {'required': {'images':['IMAGE'], 'filename_prefix':['STRING']}}
        studio.node_info = lambda *a: copy.deepcopy(info)
        comfy_requests = []
        def no_model(path, *a, **kw):
            comfy_requests.append(path)
            if path == '/system_stats': return {'system':{}, 'devices':[]}
            raise AssertionError('No Comfy request allowed: '+path)
        studio._request = no_model
        # Actual handler, unchanged Host/origin checks and actual static files.
        http = server.create_server(root, studio_factory=lambda _: studio)
        thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=args.chromium, headless=True, args=['--no-sandbox'])
                context = browser.new_context(viewport={'width':1400,'height':1000})
                page = context.new_page(); errors=[]; writes=[]
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.on('dialog', lambda d: d.accept())
                page.on('request', lambda r: writes.append(r.url) if r.method=='POST' else None)
                browser_storage = {}
                def load_page(target):
                    if not args.inert:
                        target.goto('http://127.0.0.1:8191/workflow-studio.html', wait_until='networkidle'); return
                    html = (ROOT/'app/static/workflow-studio.html').read_text(encoding='utf-8')
                    scripts = re.findall(r'<script src="([^"]+)"></script>', html)
                    styles = re.findall(r'<link rel="stylesheet" href="([^"]+)">', html)
                    html = re.sub(r'<script src="[^"]+"></script>|<link rel="stylesheet" href="[^"]+">', '', html)
                    target.set_content(html)
                    def call(route, body):
                        req = Request('http://127.0.0.1:8191'+route, data=body.encode() if body is not None else None,
                                      headers={'Origin':'http://127.0.0.1:8191','Content-Type':'application/json'})
                        try:
                            with urlopen(req,timeout=10) as response: return {'status':response.status,'raw':response.read().decode()}
                        except HTTPError as exc:
                            with exc: return {'status':exc.code,'raw':exc.read().decode()}
                    target.expose_function('fixtureRequest',call)
                    target.expose_function('fixtureDigest',lambda data:list(hashlib.sha256(bytes(data)).digest()))
                    target.evaluate('''stored => {
                        const make = initial => {const data = new Map(Object.entries(initial));return {
                          get length(){return data.size},key:i=>[...data.keys()][i]??null,getItem:k=>data.get(k)??null,
                          setItem:(k,v)=>data.set(k,String(v)),removeItem:k=>data.delete(k),entries:()=>Object.fromEntries(data)}};
                        Object.defineProperty(window,'localStorage',{value:make(stored)});
                        Object.defineProperty(window,'sessionStorage',{value:make({})});
                        const nativeCrypto=window.crypto;
                        Object.defineProperty(window,'crypto',{value:{
                          randomUUID:()=>{const a=nativeCrypto.getRandomValues(new Uint8Array(16));a[6]=(a[6]&15)|64;a[8]=(a[8]&63)|128;
                            const t=[...a].map(b=>b.toString(16).padStart(2,'0')).join('');return t.slice(0,8)+'-'+t.slice(8,12)+'-'+t.slice(12,16)+'-'+t.slice(16,20)+'-'+t.slice(20)},
                          subtle:{digest:async(_,bytes)=>new Uint8Array(await fixtureDigest([...bytes])).buffer}}});
                        window.fetch=async(route,options={})=>{const r=await fixtureRequest(route,options.body??null);return {
                          ok:r.status>=200&&r.status<300,status:r.status,json:async()=>JSON.parse(r.raw),text:async()=>r.raw}};
                    }''',browser_storage)
                    for name in styles:target.add_style_tag(content=(ROOT/'app'/name.lstrip('/')).read_text(encoding='utf-8'))
                    for name in scripts:target.add_script_tag(content=(ROOT/'app'/name.lstrip('/')).read_text(encoding='utf-8'))
                load_page(page)
                assert page.locator('#prepareSavedRun').is_disabled()
                page.select_option('#presetChoice','example'); page.click('#loadPreset')
                page.wait_for_function('window.WorkflowStudio.snapshot() !== null')
                page.click('#saveSharedWorkflow')
                page.wait_for_function('window.WorkflowProject.snapshot().id && !window.WorkflowProject.snapshot().blocked')
                key=page.evaluate('window.WorkflowProject.snapshot().id')
                page.fill('#workflowName','Unsaved local study');page.locator('#workflowName').press('Tab')
                assert page.locator('#prepareSavedRun').is_disabled()
                page.click('#saveSharedWorkflow');page.wait_for_function('!window.WorkflowProject.snapshot().dirty && !window.WorkflowProject.snapshot().blocked')
                page.click('#prepareSavedRun');page.wait_for_function('!document.querySelector("#executeSavedRun").disabled')
                request_id=page.input_value('#savedRunRequest');record=runs(studio).get(request_id)
                assert not studio.jobs
                page.click('#loadSavedRuns');page.wait_for_function('document.querySelector("#savedRunHistory").options.length === 2')
                page.select_option('#savedRunHistory',request_id);page.click('#reviewSavedRun')
                page.wait_for_function('!document.querySelector("#executeSavedRun").disabled')
                # Another author advances the saved head; a new preparation is rejected,
                # not silently rebased, and the original run remains separately usable.
                revision=page.evaluate('window.WorkflowProject.snapshot().revision')
                documents(studio).command(key,{'request_id':'other-author','expected_revision':revision,
                    'commands':[{'op':'rename','name':'Agent changed the saved head'}]})
                page.click('#prepareSavedRun')
                page.wait_for_function('document.querySelector("#savedRunMessage").textContent.includes("Workflow changed")')
                assert not studio.jobs
                page.click('#removePreparationNote')
                # Keyboard draft edit after preparation leaves the saved source explicit.
                page.fill('#workflowName','Later unsaved changes');page.locator('#workflowName').press('Tab')
                assert page.locator('#prepareSavedRun').is_disabled()
                assert 'editor differs' in page.inner_text('#savedRunSource')
                page.click('#executeSavedRun');page.wait_for_function('document.querySelector("#savedRunMessage").textContent.includes("queued")')
                assert len(studio.jobs)==1 and studio.queue.qsize()==1
                page.click('#executeSavedRun');page.wait_for_function('!document.querySelector("#executeSavedRun").disabled')
                assert len(studio.jobs)==1 and studio.queue.qsize()==1
                page.click('#observeSavedRun');page.wait_for_function('document.querySelector("#savedRunMessage").textContent.includes("Original job: queued")')
                # Close the tab: server receipt plus native localStorage recover in a new tab.
                if args.inert: browser_storage = page.evaluate('localStorage.entries()')
                page.close();page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept())
                load_page(page)
                assert page.input_value('#savedRunRequest')==request_id
                assert page.locator('#executeSavedRun').is_disabled()
                page.click('#reviewSavedRun');page.wait_for_function('!document.querySelector("#executeSavedRun").disabled')
                assert len(studio.jobs)==1
                # Separately prepared wide-seed saved record: exact review/download,
                # without attempting to load its rounded graph into the browser editor.
                wide=new_document(GRAPH,catalog(info,'primary'),'Wide seed source');wide['nodes']['3']['inputs']['seed']=2**63-1
                saved=documents(studio).create({'request_id':'browser-wide-source','document':wide})
                wide_run=runs(studio).prepare(studio,{'request_id':'wide-preparation','document_id':saved['id'],'expected_revision':1,'preset_id':'example'})
                page.fill('#savedRunRequest','wide-preparation');page.click('#reviewSavedRun');page.wait_for_function('!document.querySelector("#downloadSavedTicket").disabled')
                assert '9223372036854775807' in page.inner_text('#savedRunControls')
                with page.expect_download() as downloading:page.click('#downloadSavedTicket')
                output=args.out/'wide-ticket.json';downloading.value.save_as(str(output))
                assert output.read_bytes()==canonical(wide_run['record']['report']['ticket'])
                page.locator('#reviewSavedRun').focus()
                page.locator('#workflowSavedRuns').screenshot(path=str(args.out/'saved-runs-desktop.png'))
                page.set_viewport_size({'width':390,'height':1100})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Horizontal overflow'
                page.locator('#workflowSavedRuns').screenshot(path=str(args.out/'saved-runs-mobile.png'))
                assert not errors, errors
                assert '/prompt' not in comfy_requests and len(studio.jobs)==1
                result={'browser':'inert full production page + injected HTTP bridge/storage/crypto' if args.inert else 'full production page + real HTTP/SQLite + native localStorage', 'jobs_queued':1,
                        'model_submissions':0,'page_errors':errors,'exact_wide_seed_export':True,'preparation_id':request_id}
                (args.out/'result.json').write_text(json.dumps(result,indent=2), encoding='utf-8');print(json.dumps(result))
                browser.close()
        finally:http.shutdown();http.server_close();thread.join(5)


if __name__=='__main__':main()
