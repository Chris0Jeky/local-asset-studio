"""Actual setup UI/SQLite/uploader with synthetic model dependencies; never inference.

--inert is explicit component transport/storage/crypto, not a native-origin pass.
"""
import argparse
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'app')]
import recipe_shortlist_browser as advice
from asset_detail_browser import inert_page
from test_recipe_shortlist_apply import SetupApplyTests
from studio_workflow.setup_draft_http import extend_handler
from studio_workflow.setup_drafts import PREFIX,SetupDrafts
from server import Handler as ProductionHandler

COMMANDS=[];READS=[];LOSE=False
class Handler(extend_handler(advice.Handler)):
    _content_length=ProductionHandler._content_length
    def _safe_host(self):return self.headers.get('Host')=='127.0.0.1:'+str(self.server.server_port)
    def _safe_mutation(self):return self._safe_host() and self.headers.get('Origin')=='http://127.0.0.1:'+str(self.server.server_port)
    def _json(self,status,value):
        global LOSE
        if LOSE and value.get('action')=='apply' and value.get('status')=='committed':
            LOSE=False;return self.json({'error':'Injected response failure after the commit'},503)
        return self.json(value,status)
    def _setup_reply(self,value):
        if value is not None:COMMANDS.append(copy.deepcopy(value))
        else:READS.append(self.path)
        return super()._setup_reply(value)

async def run(out,inert=False):
    global LOSE
    from playwright.async_api import async_playwright
    out.mkdir(parents=True,exist_ok=True);checks=[];errors=[]
    def check(ok,label):
        checks.append({'label':label,'passed':bool(ok)});print(('PASS ' if ok else 'FAIL ')+label,flush=True);assert ok,label
    case=SetupApplyTests();case.setUp();s=case.s
    s.presets=copy.deepcopy(advice.fixture.CATALOG['presets']);s.catalog_path=ROOT/'presets/catalog.json'
    s.graph_for=lambda p:(json.loads((ROOT/p['graph']).read_bytes()),ROOT/p['graph'])
    s.requirements={p['id']:[] for p in s.presets};s._schema={n['class_type']:{} for p in s.presets for n in s.graph_for(p)[0].values()}
    prototype=copy.deepcopy(advice.fixture.ASSETS[0]);advice.fixture.ASSETS.clear()
    for index,item in enumerate(case.items):
        asset=s.assets.get(item['asset_id']);path='/fixture/'+item['asset_id']+'.png';advice.EXTRA_MEDIA[path]=s.assets.file(item['asset_id'])
        advice.fixture.ASSETS.append({**prototype,**asset,'url':path,'title':'Reference '+str(index+1),'workspace_id':case.scope,'tags':[],'collections':[],'lineage':[]})
    Handler.studio=s;http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start();origin='http://127.0.0.1:'+str(http.server_port)
    try:
        async with async_playwright() as p:
            browser=await p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None,headless=True,args=['--no-sandbox'])
            context=await browser.new_context(viewport={'width':1440,'height':1100},reduced_motion='reduce');page=await context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.set_default_timeout(10000)
            if inert:
                await inert_page(page,http.server_port)
                for name in ('recipe-shortlist.css','setup-proposal.css'):await page.add_style_tag(content=(ROOT/'app/static'/name).read_text())
                await page.expose_function('__qaHash',lambda text:hashlib.sha256(text.encode()).hexdigest())
                for name in ('recipe-shortlist.js','setup-apply.js','setup-proposal.js'):await page.add_script_tag(content=(ROOT/'app/static'/name).read_text())
                await page.evaluate('StudioSetupApply.mount(window,{hashText:__qaHash,withLock:fn=>fn(),uuid:(()=>{let i=0;return()=>"fixture-command-"+(++i)})()});StudioSetupProposal.mount(window,{hashText:__qaHash})')
            else:await page.goto(origin+'/#create')
            await page.wait_for_function("typeof selected!=='undefined'&&!!selected&&!!StudioSetupApply.controller")
            await page.evaluate("showView('create');selectPreset('pixel-lora');document.querySelector('#batch').value='2';document.querySelector('#positive').value='Keep the original draft';recipeChanged()")
            before=await page.evaluate('StudioSetupDraft.capture()')
            await page.evaluate("showView('assets')")
            for item in case.items:await page.locator('[data-asset-check="'+item['asset_id']+'"]').check()
            await page.click('#uxFindSelectedRecipes')
            for i,role in enumerate(('identity','pose','style')):await page.select_option('#shortlistRole'+str(i+1),role)
            async def build():
                await page.click('#checkStartingRecipes');await page.wait_for_selector('[data-setup-proposal="qwen-3ref"]')
                await page.click('[data-setup-proposal="qwen-3ref"]');await page.fill('#proposalPositive','Reviewed identity, pose and ink style')
                await page.fill('#proposalNegative','');await page.fill('#proposalContribution1','face and costume');await page.fill('#proposalAvoid2','identity')
                await page.click('#buildSetupProposal');await page.wait_for_selector('#applyReviewedSetup')
            await build();check(not COMMANDS and s.upload_count==0,'review building and navigation do not create shared drafts or copy files')
            # Cancel the native confirmation: no checkpoint or copy.
            page.once('dialog',lambda dialog:dialog.dismiss());await page.click('#applyReviewedSetup')
            check(not COMMANDS and await page.evaluate('StudioSetupDraft.capture()')==before,'cancelled application preserves all Create inputs without a command')
            if not inert:
                await page.evaluate("window.qaHeld=false;window.qaLock=navigator.locks.request('studio-shared-setup-v1',()=>new Promise(resolve=>{window.qaHeld=true;window.qaRelease=resolve}));void 0")
                await page.wait_for_function('window.qaHeld')
                page.once('dialog',lambda dialog:dialog.accept());await page.click('#applyReviewedSetup')
                await page.wait_for_function('!StudioSetupApply.controller.running')
                check(not COMMANDS and s.upload_count==0,'a held native Web Lock prevents overlapping tab commands')
                await page.evaluate('window.qaRelease();window.qaLock')
            page.once('dialog',lambda dialog:dialog.accept());await page.click('#applyReviewedSetup')
            try:await page.wait_for_function("StudioSetupApply.controller.state.revision===2&&!StudioSetupApply.controller.running")
            except Exception:
                print(await page.evaluate("({status:document.querySelector('#sharedSetupStatus').textContent,state:StudioSetupApply.controller.state,errors:typeof crypto.randomUUID})"),flush=True);raise
            applied=await page.evaluate('StudioSetupDraft.capture()');state=await page.evaluate('StudioSetupApply.controller.state')
            check(applied['recipe']['preset']=='qwen-3ref','explicit application selects the reviewed recipe')
            check(applied['recipe']['controls']['positive']=='Reviewed identity, pose and ink style','explicit application uses reviewed wording, not recipe examples')
            check([r['role'] for r in applied['recipe']['references']]==['identity','pose','style'],'all three roles retain their Picture order')
            check(applied['recipe']['references'][0]['contribution']=='face and costume' and applied['recipe']['references'][1]['avoid']=='identity','per-picture contribution and avoid wording reach Create')
            check(s.upload_count==3 and [q['action'] for q in COMMANDS]==['create','apply'],'one checkpoint and application copy exactly three sources')
            for row in applied['recipe']['references']:
                check((s.comfy_root/'input'/row['file']).read_bytes()==s.assets.file(row['parent_asset']).read_bytes(),'staged bytes match reviewed source '+row['role'])
            if await page.locator('#setupProposalDialog').evaluate('n=>n.open'):await page.keyboard.press('Escape')
            await page.locator('#sharedSetupPanel').scroll_into_view_if_needed();await page.screenshot(path=str(out/'apply-desktop.png'))
            await page.set_viewport_size({'width':390,'height':844});await page.locator('#sharedSetupPanel').scroll_into_view_if_needed()
            check(await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'shared setup recovery fits the 390px shell');await page.screenshot(path=str(out/'apply-mobile.png'))
            await page.set_viewport_size({'width':1440,'height':1100});await page.evaluate('document.body.style.zoom="2"')
            check(await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'shared setup recovery fits 200% zoom');await page.evaluate('document.body.style.zoom="1"')
            await page.locator('#undoSharedSetup').focus();await page.keyboard.press('Enter');await page.wait_for_function("StudioSetupApply.controller.state.revision===3&&!StudioSetupApply.controller.running")
            check(await page.evaluate('StudioSetupDraft.capture()')==before,'keyboard Undo restores the complete prior draft as a new revision')
            check(s.upload_count==3 and len(list((s.comfy_root/'input').glob('*')))==3,'Undo does not re-copy or delete staged files')
            # Real commit followed by an injected error response. Recovery is read-only.
            await build();LOSE=True;page.once('dialog',lambda dialog:dialog.accept());await page.click('#applyReviewedSetup')
            await page.wait_for_function("!!StudioSetupApply.controller.state.pending&&!StudioSetupApply.controller.running")
            pending=await page.evaluate('StudioSetupApply.controller.state.pending');check('Original request:' in await page.locator('#setupApplyStatus').inner_text(),'unknown result and original request are visible inside the open review');check(s.upload_count==6,'response failure occurs after the second application copied its three inputs')
            check(await page.evaluate('StudioSetupDraft.capture()')==before,'unknown application outcome never replaces Create')
            await page.keyboard.press('Escape');writes=len(COMMANDS)
            if not inert:
                await page.reload();await page.wait_for_function("!!StudioSetupApply.controller&&!!selected")
                check(await page.evaluate('StudioSetupApply.controller.state.pending.request_id')==pending['request_id'],'native reload retains the exact pending request ID')
            await page.click('#recoverSharedSetup');await page.wait_for_function("!StudioSetupApply.controller.state.pending&&!StudioSetupApply.controller.running")
            check(len(COMMANDS)==writes and s.upload_count==6 and READS[-1].endswith('/'+pending['request_id']),'recovery reads the original receipt with zero repeated writes/copies')
            check(await page.evaluate("selected.id!=='qwen-3ref'"),'receipt recovery does not silently load the committed revision')
            page.once('dialog',lambda dialog:dialog.accept());await page.click('#loadSharedSetup');await page.wait_for_function("!StudioSetupApply.controller.running&&selected.id==='qwen-3ref'")
            check(s.upload_count==6,'explicit checked load uses existing staged inputs, without another copy')
            check(not errors,'zero page exceptions')
            forbidden=[x for x in advice.CALLS if x not in (advice.PREFIX,advice.PROPOSAL,'/api/estimate')]+[x['path'] for x in advice.fixture.POSTS if x['path'] not in ('/api/estimate',)]
            check(not forbidden,'zero generation, installation, switching or unrelated asset-write calls: '+str(forbidden))
            (out/'result.json').write_text(json.dumps({'checks':checks,'passed':len(checks),'native':not inert,'commands':COMMANDS,'reads':READS,'uploads':s.upload_count,'errors':errors,'source_sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ('app/static/setup-apply.js','app/static/studio-workbench.js','studio_workflow/setup_drafts.py')}},indent=2))
            await browser.close()
    finally:http.shutdown();http.server_close();thread.join(5);case.doCleanups()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'.runtime/setup-apply');p.add_argument('--inert',action='store_true');a=p.parse_args();asyncio.run(run(a.out,a.inert))
