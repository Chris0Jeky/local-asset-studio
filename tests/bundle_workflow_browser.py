"""Opt-in bundle-to-Workspace browser proof, using real files and local HTTP.

Requires an installed Playwright/Chromium; never downloads one automatically.
Default uses the real WorkflowDocuments service with temporary SQLite. Explicit
--fixture-store uses a simulated receipt store for a partial source workspace.
This is a component harness, not the full Studio shell or a ComfyUI runtime.
--inert inserts the same UI scripts with set_content and explicit transport,
storage and crypto shims. It tests component reconstruction, not origin storage
persistence or native WebCrypto. Normal HTTP mode remains the integration gate.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import hashlib
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class Workspace:
    def __init__(self, path): self.path = path
    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path); db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db: yield db
        finally: db.close()


class ReceiptFixture:
    """Explicitly simulated. The service integration tests do not use this class."""
    def __init__(self): self.records = {}
    def create(self, payload):
        key = payload['request_id']
        repeated = key in self.records
        if not repeated:
            doc = copy.deepcopy(payload['document']); doc['revision'] = 1
            self.records[key] = dict(id=str(uuid.uuid5(uuid.UUID('0943b1d3-3a9c-4de4-a1b7-b59b8d7fa86d'), key)),
                document=doc, revision=1, head_revision=1, document_sha256='a'*64, generation_submitted=False)
        return dict(self.records[key], replayed=repeated)
    def list(self): return {'documents': list(self.records.values())}


def run():
    from playwright.sync_api import sync_playwright
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture-store', action='store_true')
    parser.add_argument('--inert', action='store_true')
    parser.add_argument('--chromium', default=shutil.which('chromium'))
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    fixture = json.loads(subprocess.check_output(['node', '-e', "console.log(JSON.stringify(require('./tests/bundle_workflow_fixture.cjs')))"], cwd=ROOT, text=True))
    with tempfile.TemporaryDirectory() as tmp:
        if args.fixture_store: store = ReceiptFixture()
        else:
            from studio_workflow.documents import WorkflowDocuments
            store = WorkflowDocuments(Workspace(str(Path(tmp)/'workspace.db')))
        state = {'requests': [], 'lose_next': False, 'delay': 0}
        html = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Bundle workflow proof</title><link rel="stylesheet" href="/static/bundle-workflow.css"><style>body{font:15px/1.6 system-ui;margin:0;background:#fafbf7;color:#202e29}main{max-width:820px;margin:auto;padding:20px}button,input{font:inherit}button{padding:10px;border:1px solid #9cac97;border-radius:7px;background:white;cursor:pointer}button:disabled{opacity:.5}summary{font-weight:650;cursor:pointer}h1{font-size:28px}.bundle-consent{display:flex;gap:8px}input[type=checkbox]{width:20px;height:20px}a{color:#245039}p{overflow-wrap:anywhere}</style></head><body><main id="bundleExplorer"><small>SYNTHETIC INTERACTION FIXTURE · NO MODEL INFERENCE</small><h1>Keep a tuned bundle</h1><p>Same graph. Named Steps. Shared revisions.</p><section id="host"></section></main><script src="/fixture.js"></script><script src="/static/workflow-project-state.js"></script><script src="/static/bundle-workflow-core.js"></script><script src="/static/bundle-workflow.js"></script><script>BundleWorkflow.mount(document.querySelector('#host'),()=>JSON.parse(JSON.stringify(fixture.snapshot)));</script></body></html>'''
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def reply(self, body, mime='application/json', code=200):
                self.send_response(code); self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
            def do_GET(self):
                state['requests'].append(('GET', self.path))
                if self.path=='/': return self.reply(html.encode(), 'text/html')
                if self.path=='/fixture.js': return self.reply(('window.fixture='+json.dumps(fixture)+';').encode(),'text/javascript')
                if self.path=='/api/workflow-studio/presets/paint':
                    time.sleep(state['delay']); return self.reply(json.dumps({'document':fixture['base'],'generation_submitted':False}).encode())
                if self.path in ['/static/'+n for n in ('workflow-project-state.js','bundle-workflow-core.js','bundle-workflow.js','bundle-workflow.css')]:
                    return self.reply((ROOT/'app/static'/self.path.rsplit('/',1)[-1]).read_bytes(), 'text/css' if self.path.endswith('.css') else 'text/javascript')
                self.reply(b'{}',code=404)
            def do_POST(self):
                state['requests'].append(('POST', self.path))
                if self.path!='/api/workflow-studio/documents': return self.reply(b'{}',code=405)
                value=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                result=store.create(value)
                if state['lose_next']:
                    state['lose_next']=False; return self.reply(b'{')  # Commit exists; its reply is malformed.
                self.reply(json.dumps(result).encode())
        def component_transport(path, body):
            state['requests'].append(('GET' if body is None else 'POST', path))
            if body is None and path == '/api/workflow-studio/presets/paint':
                return {'status':200,'body':json.dumps({'document':fixture['base'],'generation_submitted':False})}
            if body is not None and path == '/api/workflow-studio/documents':
                result=store.create(json.loads(body))
                if state['lose_next']:
                    state['lose_next']=False
                    return {'status':200,'body':'{'}
                return {'status':200,'body':json.dumps(result)}
            return {'status':404,'body':'{}'}

        def inert_page(context, retained=None, errors=None):
            page=context.new_page()
            if errors is not None: page.on('pageerror', lambda e: errors.append(str(e)))
            page.expose_function('__bundleTransport', component_transport)
            page.expose_function('__bundleDigest', lambda values:list(hashlib.sha1(bytes(values)).digest()))
            initial={} if retained is None else {'studio.workflow.pending-save.v1':retained}
            prefix=str(uuid.uuid4())
            boot = '<script>(function(){const values=new Map(Object.entries('+json.dumps(initial)+'''));let n=0;class TestStorage{getItem(k){return values.get(k)??null}setItem(k,v){values.set(k,String(v))}removeItem(k){values.delete(k)}}window.TestStorage=TestStorage;Object.defineProperty(window,'sessionStorage',{configurable:true,value:new TestStorage()});Object.defineProperty(window,'crypto',{configurable:true,value:{randomUUID:()=>'''+json.dumps(prefix)+'''+ '-'+(++n),subtle:{digest:async(_algorithm,bytes)=>new Uint8Array(await __bundleDigest([...bytes])).buffer}}});window.fetch=async(path,options={})=>{const result=await __bundleTransport(path,options.body??null);return new Response(result.body,{status:result.status,headers:{'Content-Type':'application/json'}});};})();</script>'''
            # Supply the same new scripts, but no normal origin/navigation is claimed.
            markup=html.replace('<script src="/fixture.js"></script>',boot+'<script>window.fixture='+json.dumps(fixture)+';</script>')
            for filename in ('workflow-project-state.js','bundle-workflow-core.js','bundle-workflow.js'):
                markup=markup.replace('<script src="/static/'+filename+'"></script>', '<script>'+(ROOT/'app/static'/filename).read_text(encoding='utf-8')+'</script>')
            markup=markup.replace('<link rel="stylesheet" href="/static/bundle-workflow.css">','<style>'+(ROOT/'app/static/bundle-workflow.css').read_text(encoding='utf-8')+'</style>')
            page.set_content(markup)
            return page

        http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True, executable_path=args.chromium, args=['--no-sandbox'])
                for width in (1440,390):
                    context=browser.new_context(viewport={'width':width,'height':1100},reduced_motion='reduce')
                    errors=[]; page=inert_page(context, errors=errors) if args.inert else context.new_page()
                    if not args.inert: page.on('pageerror', lambda e:errors.append(str(e)))
                    before=len(store.list()['documents']); state['requests'].clear()
                    if not args.inert: page.goto(f'http://127.0.0.1:{http.server_port}/')
                    page.locator('summary').click()
                    assert not [r for r in state['requests'] if r[1].startswith('/api/')]
                    page.locator('[data-bundle-workflow=prepare]').click()
                    page.wait_for_function("document.querySelector('.bundle-workflow-preview').textContent.includes('named Steps')")
                    assert page.locator('[data-bundle-workflow=save]').is_disabled()
                    assert not [r for r in state['requests'] if r[0]=='POST']
                    page.evaluate('fixture.snapshot.controls.steps=25')
                    page.locator('[data-bundle-workflow=consent]').check()
                    page.locator('[data-bundle-workflow=save]').click()
                    assert 'changed' in page.locator('[role=status]').inner_text()
                    assert len(store.list()['documents'])==before
                    page.locator('[data-bundle-workflow=prepare]').click()
                    page.wait_for_function("document.querySelector('.bundle-workflow-preview').textContent.includes('named Steps')")
                    # The exact shared pending request must be written before any POST.
                    page.evaluate("() => {window.storageClass=window.TestStorage||Storage;window.realSetItem=storageClass.prototype.setItem;storageClass.prototype.setItem=function(){throw Error('quota fixture')};}")
                    page.locator('[data-bundle-workflow=consent]').check()
                    page.locator('[data-bundle-workflow=save]').click()
                    assert 'quota' in page.locator('[role=status]').inner_text()
                    assert len(store.list()['documents'])==before
                    page.evaluate('() => {storageClass.prototype.setItem=realSetItem;}')
                    state['lose_next']=True
                    page.locator('[data-bundle-workflow=save]').click()
                    page.wait_for_function("!document.querySelector('[data-bundle-workflow=retry]').hidden && !document.querySelector('[data-bundle-workflow=retry]').disabled")
                    assert len(store.list()['documents'])==before+1
                    retained=page.evaluate("sessionStorage.getItem('studio.workflow.pending-save.v1')")
                    assert retained
                    if args.inert:
                        page.close();page=inert_page(context,retained,errors)
                    else: page.reload()
                    page.locator('summary').click()
                    assert page.evaluate("sessionStorage.getItem('studio.workflow.pending-save.v1')")==retained
                    page.locator('[data-bundle-workflow=retry]').click()
                    page.wait_for_function("document.querySelector('[role=status]').textContent.startsWith('Saved ')")
                    assert len(store.list()['documents'])==before+1
                    assert page.evaluate("sessionStorage.getItem('studio.workflow.pending-save.v1')") is None
                    assert [r for r in state['requests'] if r[0]=='POST']==[('POST','/api/workflow-studio/documents')]*2
                    if args.out:
                        args.out.mkdir(parents=True,exist_ok=True)
                        # Re-prepare a fresh view only, so the screenshot includes named Steps.
                        page.locator('[data-bundle-workflow=prepare]').click()
                        page.wait_for_function("document.querySelector('.bundle-workflow-preview').textContent.includes('named Steps')")
                        page.screenshot(path=str(args.out/f'bundle-workflow-{width}.png'),full_page=True)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    assert not errors,errors
                    context.close();print(f'PASS {width}px ({"inert component" if args.inert else "native HTTP/sessionStorage"}): stale draft, storage failure, lost response/reconstruction/replay, one saved record, zero inference routes')
                browser.close()
        finally: http.shutdown();http.server_close();thread.join(timeout=5)


if __name__=='__main__':run()
