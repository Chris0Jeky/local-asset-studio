"""Scenario QA over the actual Studio shell. Synthetic API data; zero inference.

Native HTTP: python tests/asset_detail_browser.py --out .runtime/asset-detail
Policy-restricted component mode: add --inert (test storage/transport, not native networking).
Add --baseline to record unmet expectations; JavaScript exceptions still fail.
Add --response-delay-ms 400 to exercise slow synthetic mutation/diagnostic responses.
"""
import argparse
import asyncio
import copy
import hashlib
import json
import re
import shutil
import threading
import time
from http.client import HTTPConnection
from pathlib import Path

import studio_browser_smoke as fixture

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'app/static'
BASE_ASSETS = copy.deepcopy(fixture.ASSETS)
for i in range(2):
    BASE_ASSETS[i].update(media_type='video', preset_id='wan22-i2v', job_id=f'wan-{i}', lineage=[f'asset-{1-i}'])
# Deliberately use no artwork as evidence of a synthetic video or model result.
for asset in BASE_ASSETS:
    asset['url'] = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="512" height="768"%3E%3C/svg%3E'

class State:
    def __init__(self, delay_ms=0):
        self.delay_seconds=delay_ms/1000; self.started=threading.Condition()
        self.writes=[]; self.gate=threading.Event(); self.gate.set()
        self.diagnostic_gate=threading.Event(); self.diagnostic_gate.set()
        self.fail_write=False; self.fail_diagnostic=False; self.diagnostics=0; self.receipts={}
    def wait_started(self, kind, count):
        with self.started:
            ready=self.started.wait_for(lambda: (len(self.writes) if kind=='write' else self.diagnostics)>=count,timeout=5)
        if not ready:raise TimeoutError('Synthetic '+kind+' request did not reach its gate')

class Handler(fixture.Handler):
    state=None
    def do_GET(self):
        if self.path.endswith('/i2v-diagnostic'):
            with self.state.started:
                self.state.diagnostics+=1
                failed=self.state.fail_diagnostic
                self.state.started.notify_all()
            if not self.state.diagnostic_gate.wait(10):return self.json({'error':'Fixture deadline'},504)
            time.sleep(self.state.delay_seconds)  # Deliberate server fault injection, not a test settling wait.
            if failed:return self.json({'error':'Recorded file unavailable (synthetic fault)'},503)
            return self.json({'job':{'id':self.path.split('/')[3]},'source':{'filename':self.path.split('/')[3]},'requested':{},'video':{'probe':{}},'graph':{},'artifacts':{}})
        return super().do_GET()
    def do_POST(self):
        if self.path=='/api/assets/update':
            data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            with self.state.started:
                self.state.writes.append(copy.deepcopy(data))
                self.state.started.notify_all()
            if not self.state.gate.wait(10):return self.json({'error':'Fixture deadline'},504)
            time.sleep(self.state.delay_seconds)
            if self.state.fail_write:return self.json({'error':'Workspace unavailable (synthetic fault)'},503)
            if data['request_id'] in self.state.receipts:return self.json(self.state.receipts[data['request_id']])
            selected=[a for a in fixture.ASSETS if a['id'] in data['ids']]
            if any(a['metadata_revision']!=data['expected_revisions'][a['id']] for a in selected):return self.json({'error':'Synthetic stale revision','code':'asset_revision_conflict','current':selected},409)
            for asset in fixture.ASSETS:
                if asset['id'] in data['ids']:
                    if data['action']=='edit':asset.update({k:v for k,v in data.items() if k not in {'ids','action','request_id','expected_revisions'}})
                    elif data['action']=='trash':asset['trashed_at']=123
                    elif data['action']=='restore':asset['trashed_at']=None
                    asset['metadata_revision']+=1
            receipt={'status':'applied','request_id':data['request_id'],'updated':data['ids'],'action':data['action'],'revisions':{a['id']:a['metadata_revision'] for a in selected},'applied':{k:v for k,v in data.items() if k in {'title','notes','tags','favorite','review'}} if data['action']=='edit' else {'trashed_at':123 if data['action']=='trash' else None}}
            self.state.receipts[data['request_id']]=receipt
            return self.json(receipt)
        return super().do_POST()

async def inert_page(page, port):
    """Actual HTML/scripts/styles with explicit test-only storage and API transport."""
    async def transport(path,options):
        if not isinstance(path,str) or not path.startswith('/api/') or '..' in path:raise ValueError('Test transport only serves fixture APIs')
        def request():
            connection=HTTPConnection('127.0.0.1',port,timeout=12)
            try:
                connection.request(options.get('method') or 'GET',path,(options.get('body') or '').encode('utf-8'),dict(options.get('headers') or {}, Origin=f'http://127.0.0.1:{port}'))
                reply=connection.getresponse();return {'status':reply.status,'body':reply.read().decode('utf-8')}
            finally:connection.close()
        return await asyncio.to_thread(request)
    await page.expose_function('__qaTransport',transport)
    markup=(STATIC/'index.html').read_text(encoding='utf-8')
    # No navigation-policy bypass. Native storage/origin, media loading and navigation are untested here.
    boot='''<script>class QAStorage{constructor(){this.data=new Map()}getItem(k){return this.data.get(k)??null}setItem(k,v){this.data.set(k,String(v))}removeItem(k){this.data.delete(k)}}
Object.defineProperty(window,'localStorage',{value:new QAStorage()});Object.defineProperty(window,'sessionStorage',{value:new QAStorage()});
window.fetch=async(path,options={})=>{const r=await __qaTransport(path,{method:options.method,body:options.body,headers:options.headers});return new Response(r.body,{status:r.status,headers:{'Content-Type':'application/json'}})};</script>'''
    markup=markup.replace('<head>','<head>'+boot)
    def script(match):
        file=STATIC/match.group(1).removeprefix('/static/')
        if 'vendor' in str(file):return ''
        return '<script>'+file.read_text(encoding='utf-8').replace('</script','<\\/script')+'</script>'
    markup=re.sub(r'<script(?: type="module")? src="([^"]+)"></script>',script,markup)
    markup=re.sub(r'<link rel="stylesheet" href="/static/([^"]+)">',lambda m:'<style>'+(STATIC/m.group(1)).read_text(encoding='utf-8')+'</style>',markup)
    markup=re.sub(r' src="/(?:api|examples)/[^"]+"','',markup)
    await page.set_content(markup)

def check_result(checks, errors, baseline=False):
    """Baseline relaxes expectations only, never execution failures."""
    if errors or (not baseline and any(c['status']=='fail' for c in checks)):
        raise SystemExit(1)


def delay_milliseconds(value):
    number=int(value)
    if not 0<=number<=2000:raise argparse.ArgumentTypeError('Use a delay between 0 and 2000 milliseconds')
    return number


async def run(args):
    from playwright.async_api import async_playwright
    args.out.mkdir(parents=True,exist_ok=True)
    state=State(getattr(args,'response_delay_ms',0));Handler.state=state;fixture.ASSETS[:]=copy.deepcopy(BASE_ASSETS);fixture.POSTS.clear()
    server=fixture.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    checks=[];errors=[];browser=None
    async def check(case, expectation, passed):
        print(case, passed, flush=True)
        checks.append({'id':case,'expectation':expectation,'status':'pass' if passed else 'fail'})
    try:
        async with async_playwright() as pw:
            browser=await pw.chromium.launch(executable_path=args.chromium or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
            page=await browser.new_page(viewport={'width':1440,'height':1100},reduced_motion='reduce')
            page.set_default_timeout(5000)
            page.on('pageerror',lambda e:errors.append(str(e)))
            if args.inert:await inert_page(page,server.server_port)
            else:await page.goto(f'http://127.0.0.1:{server.server_port}/#assets')
            await page.wait_for_function('!!catalog && !!selected')
            await page.evaluate("showView('assets')")
            await page.wait_for_selector('[data-asset-open="asset-0"]')
            # Observe the existing API promise without changing requests, results,
            # errors or the product code. Works in native and inert transport modes.
            await page.evaluate("""() => {
              window.__assetQaCalls=[]; const original=api;
              api=async(...args)=>{
                const kind=args[0]==='/api/assets/update'?'write':args[0].endsWith('/i2v-diagnostic')?'diagnostic':null;
                if(!kind)return original(...args);
                const call={kind,pending:true};__assetQaCalls.push(call);
                try{return await original(...args);}finally{call.pending=false;}
              };
            }""")
            async def open_asset(i=0):
                # Test setup closes without user input; each assertion exercises real user actions.
                await page.evaluate("""() => new Promise(resolve => {const d=document.querySelector('#assetDialog');if(!d.open){resolve();return;}d.addEventListener('close',resolve,{once:true});d.close();})""")
                # Independent scenarios must not restore the prior case's retained pending command.
                await page.evaluate("if(window.StudioReviewRecovery)sessionStorage.removeItem(StudioReviewRecovery.KEY)")
                await page.evaluate(f"openAsset('asset-{i}')")
                await page.wait_for_function("id => document.querySelector('#assetDialog').open && activeAsset?.id===id",arg=f'asset-{i}')
            async def settle():
                held=[kind for kind,gate in [('write',state.gate),('diagnostic',state.diagnostic_gate)] if not gate.is_set()]
                # A held response must have reached the server before the test
                # navigates or changes fault flags; merely starting fetch is not enough.
                for kind in held:
                    count=await page.evaluate("kind => __assetQaCalls.filter(c=>c.kind===kind).length",kind)
                    await asyncio.to_thread(state.wait_started,kind,count)
                await page.wait_for_function("""held =>
                  !__assetQaCalls.some(c=>c.pending && !held.includes(c.kind)) &&
                  (held.includes('write') || !assetDetailBusy) && !assetRefreshing
                """,arg=held)
            async def discard_dialog(dialog):await dialog.accept()
            page.on('dialog',discard_dialog)
            await open_asset()
            await page.fill('#assetNotes','Keep my detailed repair notes')
            await page.click('#assetFavorite');await settle()
            await check('ASSET-01','Favorite preserves unsaved notes',await page.input_value('#assetNotes')=='Keep my detailed repair notes')
            await check('ASSET-02','Favorite writes only favorite, not review/notes',set(state.writes[-1])=={'ids','action','favorite','request_id','expected_revisions','workspace_id'})
            await open_asset();await page.fill('#assetNotes','Stay on Escape')
            page.remove_listener('dialog',discard_dialog)
            prompts=[]
            async def stay_dialog(dialog):prompts.append(dialog.message);await dialog.dismiss()
            page.on('dialog',stay_dialog)
            await page.press('#assetNotes','Escape');await settle()
            await check('ASSET-03','Escape offers discard consent; Stay preserves draft',bool(prompts) and await page.locator('#assetDialog').is_visible() and await page.input_value('#assetNotes')=='Stay on Escape')
            await open_asset();await page.fill('#assetNotes','Keep my lineage context');prompts.clear()
            await page.click('[data-lineage="asset-1"]');await settle()
            await check('ASSET-04','Lineage navigation cannot discard edits without consent',bool(prompts) and await page.evaluate('activeAsset.id')=='asset-0' and await page.input_value('#assetNotes')=='Keep my lineage context')
            await open_asset();await page.fill('#assetNotes','Do not close');prompts.clear()
            await page.click('#closeAssetDialog');await settle()
            await check('ASSET-05','Close button offers the same discard choice as Escape',bool(prompts) and await page.locator('#assetDialog').is_visible())
            page.remove_listener('dialog',stay_dialog);page.on('dialog',discard_dialog)
            await open_asset();await page.fill('#assetNotes','Save, then continue')
            await page.click('#saveAssetDetails');await settle()
            await check('ASSET-06','Save keeps the current asset open for continuation',await page.locator('#assetDialog').is_visible() and fixture.ASSETS[0]['notes']=='Save, then continue')
            await open_asset();state.fail_write=True;await page.fill('#assetNotes','Retain this after error')
            await page.click('#saveAssetDetails');await settle()
            status=page.locator('#assetDetailStatus')
            await check('ASSET-07','Save failure is visible inside the open dialog',await status.count()>0 and 'unavailable' in (await status.inner_text()).lower() and await page.input_value('#assetNotes')=='Retain this after error')
            state.fail_write=False
            await open_asset();state.gate.clear();await page.fill('#assetNotes','First snapshot')
            count=len(state.writes);await page.click('#saveAssetDetails')
            await settle();await page.fill('#assetNotes','Newer edits during save')
            await check('ASSET-08','Duplicate save is disabled during in-flight mutation',await page.locator('#saveAssetDetails').is_disabled())
            state.gate.set();await settle()
            await check('ASSET-09','Late save preserves newer typing and leaves it unsaved',await page.locator('#assetDialog').is_visible() and await page.input_value('#assetNotes')=='Newer edits during save' and await status.count()>0 and 'unsaved' in (await status.inner_text()).lower())
            await check('ASSET-10','Save persists its click-time snapshot exactly once',len(state.writes)==count+1 and fixture.ASSETS[0]['notes']=='First snapshot')
            # Dirty-state screenshot is a real Chromium render with explicitly synthetic content.
            if await page.locator('#assetDialog').is_visible():await page.screenshot(path=str(args.out/'asset-detail-desktop.png'))
            await open_asset();state.diagnostic_gate.clear();state.fail_diagnostic=False
            await page.click('[data-i2v-diagnostic]');await settle();await page.click('[data-lineage="asset-1"]');state.diagnostic_gate.set();await settle()
            await check('ASSET-11','Late diagnostic success cannot replace the newly selected asset panel',await page.locator('#assetDiagnostic [data-i2v-diagnostic="wan-1"]').count()==1)
            await open_asset();state.diagnostic_gate.clear();state.fail_diagnostic=True
            await page.click('[data-i2v-diagnostic]');await settle();await page.click('[data-lineage="asset-1"]');state.diagnostic_gate.set();await settle()
            await check('ASSET-12','Late diagnostic failure cannot attach retry to another asset',await page.locator('#assetDiagnostic [data-i2v-diagnostic="wan-1"]').count()==1 and 'unavailable' not in await page.locator('#assetDiagnostic').inner_text())
            await open_asset();await page.click('[data-i2v-diagnostic]');await settle()
            await check('ASSET-13','Current diagnostic failure retains explicit retry',await page.locator('#assetDiagnostic [data-i2v-diagnostic="wan-0"]').count()==1)
            state.fail_diagnostic=False
            for failed in [False,True]:
                await open_asset();state.diagnostic_gate.clear();state.fail_diagnostic=failed
                await page.click('[data-i2v-diagnostic]');await settle()
                await page.click('[data-lineage="asset-1"]');await page.click('[data-lineage="asset-0"]')
                state.diagnostic_gate.set();await settle()
                await check('ASSET-18' if not failed else 'ASSET-19','A→B→A rejects old diagnostic '+('failure' if failed else 'success'),await page.locator('#assetDiagnostic [data-i2v-diagnostic="wan-0"]').count()==1 and 'unavailable' not in await page.locator('#assetDiagnostic').inner_text())
            state.fail_diagnostic=False
            await open_asset();state.diagnostic_gate.clear()
            await page.click('[data-i2v-diagnostic]');await settle();await page.click('#closeAssetDialog');await settle()
            await page.evaluate("openAsset('asset-0')");state.diagnostic_gate.set();await settle()
            await check('ASSET-20','Close/reopen rejects the previous session diagnostic',await page.locator('#assetDiagnostic [data-i2v-diagnostic="wan-0"]').count()==1)
            await open_asset();await page.fill('#assetTitle','Never lose my title');await page.fill('#assetTags','portrait, test');await page.select_option('#assetReview','needs_work')
            await page.click('#assetFavorite');await settle()
            await check('ASSET-21','Favorite preserves title, tags and review together',await page.input_value('#assetTitle')=='Never lose my title' and await page.input_value('#assetTags')=='portrait, test' and await page.input_value('#assetReview')=='needs_work')
            await page.evaluate("openAsset('missing-asset')")
            await check('ASSET-22','Missing navigation target retains the active editor',await page.evaluate('activeAsset.id')=='asset-0' and await page.input_value('#assetTitle')=='Never lose my title')
            await open_asset();state.gate.clear();await page.fill('#assetNotes','Busy snapshot');await page.click('#saveAssetDetails');await settle()
            await page.click('#closeAssetDialog');await page.click('[data-lineage="asset-1"]');await settle()
            await check('ASSET-23','Pending write holds close and navigation in the same session',await page.locator('#assetDialog').is_visible() and await page.evaluate('activeAsset.id')=='asset-0')
            state.gate.set();await settle()
            await page.click('#closeAssetDialog');await settle()
            await check('ASSET-24','Confirmed clean save can close normally',not await page.locator('#assetDialog').is_visible())
            await open_asset();state.fail_write=True;await page.fill('#assetNotes','Recover this favorite error');await page.click('#assetFavorite');await settle()
            await check('ASSET-25','Favorite failure is visible, retains edits and releases controls',await page.input_value('#assetNotes')=='Recover this favorite error' and 'unavailable' in (await status.inner_text()).lower() and not await page.locator('#saveAssetDetails').is_disabled())
            state.fail_write=False
            await open_asset();await page.fill('#assetNotes','A draft at narrow width')
            for width in [390,720]:
                await page.set_viewport_size({'width':width,'height':1100});await settle()
                await check('ASSET-14' if width==390 else 'ASSET-15',f'{width}px dialog remains within viewport',await page.evaluate("document.documentElement.scrollWidth<=innerWidth && document.querySelector('#assetDialog').getBoundingClientRect().right<=innerWidth"))
                await check('ASSET-26' if width==390 else 'ASSET-27',f'{width}px preview uses at most 35% viewport height',await page.locator('#assetDetailMedia').evaluate('(el)=>el.getBoundingClientRect().height<=innerHeight*.35'))
                await page.screenshot(path=str(args.out/f'asset-detail-{width}.png'))
                await page.locator('#assetDetailStatus').scroll_into_view_if_needed()
                await page.screenshot(path=str(args.out/f'asset-editing-{width}.png'))
            await check('ASSET-28','Dirty/save messages have a polite status region',await status.get_attribute('role')=='status' and await status.get_attribute('aria-live')=='polite')
            await page.focus('#assetNotes');await page.keyboard.press('Tab')
            keyboard_target=await page.evaluate('document.activeElement.id')
            await page.keyboard.press('Enter');await settle()
            await check('ASSET-29','Keyboard reaches Save from Notes and keeps the confirmed asset open',keyboard_target=='saveAssetDetails' and await page.locator('#assetDialog').is_visible() and 'saved' in (await status.inner_text()).lower())
            await page.locator('#saveAssetDetails').scroll_into_view_if_needed()
            await page.screenshot(path=str(args.out/'asset-saved-720.png'))
            await page.fill('#assetNotes','Keep this after a Trash error');state.fail_write=True
            await page.click('#assetTrash');await settle()
            await check('ASSET-30','Trash error restores editing and retains the unsaved draft',await page.locator('#assetDialog').is_visible() and await page.input_value('#assetNotes')=='Keep this after a Trash error' and not await page.locator('#assetNotes').is_disabled() and 'unavailable' in (await status.inner_text()).lower())
            state.fail_write=False
            await check('ASSET-16','These scenarios never create a generation or switch/install a backend',all(p['path'] in {'/api/estimate','/api/references/check'} for p in fixture.POSTS))
            await check('ASSET-17','No JavaScript exceptions in complete shell',not errors)
            await browser.close();browser=None
    finally:
        state.gate.set();state.diagnostic_gate.set();server.shutdown();server.server_close()
        receipt={'scope':'Actual Studio HTML/JS/CSS, synthetic assets and HTTP API fixture. No model inference, owner-PC, art or licence evidence.',
                 'mode':'inert: injected storage and API transport; native origin/network/media not tested' if args.inert else 'native browser HTTP against synthetic API',
                 'response_delay_ms':getattr(args,'response_delay_ms',0),
                 'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 'workspace_js_sha256':hashlib.sha256((STATIC/'workspace.js').read_bytes()).hexdigest(),
                 'style_css_sha256':hashlib.sha256((STATIC/'style.css').read_bytes()).hexdigest(),'checks':checks,'errors':errors,
                 'pass':sum(c['status']=='pass' for c in checks),'fail':sum(c['status']=='fail' for c in checks),'write_count':len(state.writes),
                 'posts':fixture.POSTS,'mutations':state.writes}
        (args.out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:receipt[k] for k in ['mode','pass','fail','errors']},indent=2))
    check_result(checks,errors,args.baseline)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--inert',action='store_true');parser.add_argument('--baseline',action='store_true');parser.add_argument('--chromium');parser.add_argument('--response-delay-ms',type=delay_milliseconds,default=0)
    asyncio.run(run(parser.parse_args()))
