"""Actual setup UI/SQLite/uploader with synthetic model dependencies; never inference.

--inert is explicit component transport/storage/crypto, not a native-origin pass.
"""
from browser_ports import evidence_screenshot
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
from browser_ports import browser_server
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'app')]
import recipe_shortlist_browser as advice
from asset_detail_browser import inert_page
from test_recipe_shortlist_apply import SetupApplyTests
from studio_workflow.setup_draft_http import extend_handler
from studio_workflow.setup_drafts import PREFIX,SetupDrafts
from server import Handler as ProductionHandler

COMMANDS=[];READS=[];LOSE=False;LOSE_RESTORE=False;HOLD_ACTION=None;HOLD_CHECK=False
HELD=threading.Event();RELEASE=threading.Event()
class Handler(extend_handler(advice.Handler)):
    _content_length=ProductionHandler._content_length
    def _safe_host(self):return self.headers.get('Host')=='127.0.0.1:'+str(self.server.server_port)
    def _safe_mutation(self):return self._safe_host() and self.headers.get('Origin')=='http://127.0.0.1:'+str(self.server.server_port)
    def _json(self,status,value):
        global LOSE,LOSE_RESTORE
        if value.get('action')==HOLD_ACTION and HOLD_ACTION or HOLD_CHECK and value.get('inputs_available') is True:
            HELD.set()
            if not RELEASE.wait(15):return self.json({'error':'Fixture response hold expired'},503)
        if LOSE and value.get('action')=='apply' and value.get('status')=='committed':
            LOSE=False;return self.json({'error':'Injected response failure after the commit'},503)
        if LOSE_RESTORE and value.get('action')=='restore' and value.get('status')=='committed':
            LOSE_RESTORE=False;return self.json({'error':'Injected restore response failure after the commit'},503)
        return self.json(value,status)
    def _setup_reply(self,value):
        if value is not None:COMMANDS.append(copy.deepcopy(value))
        else:READS.append(self.path)
        return super()._setup_reply(value)

async def run(out,inert=False):
    global LOSE,LOSE_RESTORE,HOLD_ACTION,HOLD_CHECK
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
    Handler.studio=s;Handler.workspace_id=case.scope;http=browser_server(Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start();origin='http://127.0.0.1:'+str(http.server_port)
    try:
        async with async_playwright() as p:
            browser=await p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None,headless=True,args=['--no-sandbox'])
            context=await browser.new_context(viewport={'width':1440,'height':1100},reduced_motion='reduce');page=await context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.set_default_timeout(10000)
            if inert:
                await inert_page(page,http.server_port)
                for name in ('recipe-shortlist.css','setup-proposal.css','workshop.css'):await page.add_style_tag(content=(ROOT/'app/static'/name).read_text())
                await page.expose_function('__qaHash',lambda text:hashlib.sha256(text.encode()).hexdigest())
                for name in ('recipe-shortlist.js','setup-apply.js','setup-proposal.js','workshop.js'):await page.add_script_tag(content=(ROOT/'app/static'/name).read_text())
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
                if not await page.locator('#workshopRecipeDialog').evaluate('n=>n.open'):
                    await page.click('#workshopRecipeChange')
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
            check(not await page.locator('#setupProposalDialog').evaluate('n=>n.open') and not await page.locator('#workshopRecipeDialog').evaluate('n=>n.open'),'successful reviewed setup closes both review and recipe dialogs')
            await page.wait_for_function("document.activeElement===document.querySelector('#sharedSetupStatus')")
            check(await page.locator('#sharedSetupStatus').is_visible(),'applied setup status receives visible editor focus')
            await page.locator('#sharedSetupPanel').scroll_into_view_if_needed();await evidence_screenshot(page, path=str(out/'apply-desktop.png'))
            await page.set_viewport_size({'width':390,'height':844});await page.locator('#sharedSetupPanel').scroll_into_view_if_needed()
            check(await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'shared setup recovery fits the 390px shell');await evidence_screenshot(page, path=str(out/'apply-mobile.png'))
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
            await page.keyboard.press('Escape')
            if await page.locator('#workshopRecipeDialog').evaluate('n=>n.open'):await page.keyboard.press('Escape')
            writes=len(COMMANDS)
            if not inert:
                await page.reload();await page.wait_for_function("!!StudioSetupApply.controller&&!!selected")
                check(await page.evaluate('StudioSetupApply.controller.state.pending.request_id')==pending['request_id'],'native reload retains the exact pending request ID')
            await page.click('#recoverSharedSetup');await page.wait_for_function("!StudioSetupApply.controller.state.pending&&!StudioSetupApply.controller.running")
            check(len(COMMANDS)==writes and s.upload_count==6 and READS[-1].endswith('/'+pending['request_id']),'recovery reads the original receipt with zero repeated writes/copies')
            check(await page.evaluate("selected.id!=='qwen-3ref'"),'receipt recovery does not silently load the committed revision')
            page.once('dialog',lambda dialog:dialog.accept());await page.click('#loadSharedSetup');await page.wait_for_function("!StudioSetupApply.controller.running&&selected.id==='qwen-3ref'")
            check(s.upload_count==6,'explicit checked load uses existing staged inputs, without another copy')
            # Read-only Workspace history (#395): the real routes, SQLite rows and page; Create and the recovery journal stay as they are.
            draft_now=await page.evaluate('StudioSetupDraft.capture()');state_now=await page.evaluate('JSON.stringify(StudioSetupApply.controller.state)');writes=len(COMMANDS);uploads=s.upload_count
            await page.locator('#setupHistory summary').click();await page.wait_for_function("document.querySelectorAll('#setupHistoryList li').length>=3")
            check('current head' in await page.locator('#setupHistoryList li').first.inner_text(),'history lists the newest revision as the current head')
            await page.locator('#setupHistoryList input[type=checkbox]').nth(0).check();await page.locator('#setupHistoryList input[type=checkbox]').nth(2).check()
            await page.click('#setupHistoryCompare');await page.wait_for_function("document.querySelector('#setupHistoryComparison').textContent.includes('sections differ')||document.querySelector('#setupHistoryStatus').textContent.includes('sections differ')")
            check('Recipe and graph' in await page.locator('#setupHistoryComparison').inner_text(),'history comparison shows typed setup sections')
            check((await page.locator('#setupHistoryList a').first.get_attribute('href')).endswith('/export?workspace_id='+state['workspace_id']+'&revision='+str(json.loads(state_now)['revision'])),'history offers the existing export route')
            check(await page.evaluate('StudioSetupDraft.capture()')==draft_now and await page.evaluate('JSON.stringify(StudioSetupApply.controller.state)')==state_now and len(COMMANDS)==writes and s.upload_count==uploads,'history leaves Create, the recovery journal, writes and copies unchanged')
            if not inert:
                # Historical restore uses those same real routes and SQLite, with native Web Locks and crypto.
                key=json.loads(state_now)['draft_id'];head=json.loads(state_now)['revision'];store=SetupDrafts(s)
                originals={n:store.get(key,n)['record_json'] for n in range(1,head+1)}
                await page.fill('#positive','Keep my complete current wording before restoring')
                local=await page.evaluate('StudioSetupDraft.capture()');writes=len(COMMANDS);uploads=s.upload_count
                async def review(revision):
                    await page.click('#setupHistoryRefresh');await page.wait_for_function('!StudioSetupHistory.history.state.busy')
                    await page.click('[data-key="restore-'+str(revision)+'"]')
                    await page.wait_for_function('!!StudioSetupHistory.history.state.restoration&&!StudioSetupHistory.history.state.busy')
                await review(1)
                check(len(COMMANDS)==writes and s.upload_count==uploads,'restore review checks dependencies and compares records without writes or copies')
                await page.click('#setupHistoryRestoreCancel')
                check(len(COMMANDS)==writes and await page.evaluate('StudioSetupDraft.capture()')==local,'cancelled history restore preserves the complete local draft')
                check(await page.evaluate('document.activeElement.dataset.key')=='restore-1','cancel returns keyboard focus to the historical row')
                await review(1)
                for width,zoom,name in ((1440,'1','restore-wide'),(390,'1','restore-narrow'),(1440,'2','restore-zoom')):
                    await page.set_viewport_size({'width':width,'height':1100 if width==1440 else 844});await page.evaluate('(z)=>document.body.style.zoom=z',zoom)
                    await page.locator('#setupHistoryRestore').scroll_into_view_if_needed()
                    check(await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'history restore fits '+str(width)+'px at '+zoom+'x zoom')
                    await page.screenshot(path=str(out/(name+'.png')),animations='disabled')
                await page.evaluate('document.body.style.zoom="1"');await page.set_viewport_size({'width':1440,'height':1100})
                await page.locator('#setupHistoryRestoreConfirm').focus();await page.keyboard.press('Enter')
                await page.wait_for_function('(n)=>StudioSetupApply.controller.state.revision===n&&!StudioSetupApply.controller.running',arg=head+2)
                check([q['action'] for q in COMMANDS[writes:]]==['replace','restore'],'explicit historical restore makes exactly one checkpoint and one restore command')
                check(store.get(key,head+1)['draft']==local,'checkpoint retains the complete current Create draft')
                check(store.get(key,head+2)['record_json']==originals[1] and await page.evaluate('StudioSetupDraft.capture()')==before,'historical restore keeps exact original bytes and loads the selected setup')
                check({n:store.get(key,n)['record_json'] for n in originals}==originals,'all earlier SQLite revision records remain byte-identical')
                check(s.upload_count==uploads,'historical restore neither stages nor deletes input files')
                await page.locator('#sharedSetupStatus').scroll_into_view_if_needed();await page.screenshot(path=str(out/'restore-result.png'),animations='disabled')
                # A local edit after the actual checkpoint commit stops the second command.
                await review(2);HOLD_ACTION='replace';HELD.clear();RELEASE.clear();writes=len(COMMANDS)
                await page.click('#setupHistoryRestoreConfirm');check(await asyncio.to_thread(HELD.wait,5),'checkpoint response is held after its real SQLite commit')
                await page.fill('#positive','Later edit while checkpoint reply was held');RELEASE.set();HOLD_ACTION=None
                await page.wait_for_function('!StudioSetupApply.controller.running')
                check(len(COMMANDS)==writes+1 and COMMANDS[-1]['action']=='replace','late editor change preserves checkpoint and prevents the restore command')
                check(await page.locator('#positive').input_value()=='Later edit while checkpoint reply was held','late local editor wording survives')
                check('saved as revision' in await page.locator('#sharedSetupStatus').inner_text(),'partial completion names the saved checkpoint honestly')
                # Private/All are observation scopes, not new setup command authority.
                await page.click('#setupHistoryRefresh');await page.wait_for_function('!StudioSetupHistory.history.state.busy');writes=len(COMMANDS)
                await page.evaluate("StudioPrivacy.setScope('all')");await page.click('[data-key="restore-1"]')
                await page.wait_for_function("document.querySelector('#setupHistoryStatus').textContent.includes('only for a Regular')")
                check(len(COMMANDS)==writes and not await page.locator('#setupHistoryRestore').is_visible(),'All view cannot authorize a Regular history restore')
                await page.evaluate("StudioPrivacy.setScope('regular')")
                # Inject A-B-A context events while an actual checked-read response is held.
                for change,label in (("StudioPrivacy.setScope('private');StudioPrivacy.setScope('regular')",'privacy'),("const ws=assetState.workspace_id;assetState.workspace_id='f'.repeat(32);document.dispatchEvent(new CustomEvent('studio:workspace-change',{detail:{workspace_id:assetState.workspace_id}}));assetState.workspace_id=ws;document.dispatchEvent(new CustomEvent('studio:workspace-change',{detail:{workspace_id:ws}}))",'Workspace')):
                    await page.click('#setupHistoryRefresh');await page.wait_for_function('!StudioSetupHistory.history.state.busy');HOLD_CHECK=True;HELD.clear();RELEASE.clear()
                    await page.click('[data-key="restore-1"]');check(await asyncio.to_thread(HELD.wait,5),label+' checked read is held')
                    await page.evaluate(change);RELEASE.set();HOLD_CHECK=False
                    await page.wait_for_function('!StudioSetupHistory.history.state.busy')
                    check(not await page.locator('#setupHistoryRestore').is_visible() and len(COMMANDS)==writes,label+' A-B-A cannot reopen a stale restore action')
                # The server commits the restoration before losing its reply; reload/recovery never repeats it.
                await review(1);before_lost=await page.evaluate('StudioSetupDraft.capture()');LOSE_RESTORE=True
                await page.click('#setupHistoryRestoreConfirm');await page.wait_for_function('!!StudioSetupApply.controller.state.pending&&!StudioSetupApply.controller.running')
                pending=await page.evaluate('StudioSetupApply.controller.state.pending');writes=len(COMMANDS);committed=store.get(key)['revision']
                check(pending['action']=='restore' and store.get(key,committed)['record_json']==originals[1],'lost restore reply retains the exact original request after a real commit')
                check(await page.evaluate('StudioSetupDraft.capture()')==before_lost,'lost restore reply does not adopt the selected revision')
                await page.reload();await page.wait_for_function('!!StudioSetupApply.controller&&!!selected')
                check(await page.evaluate('StudioSetupApply.controller.state.pending.request_id')==pending['request_id'],'reload keeps the original restore request identity')
                reload_draft=await page.evaluate('StudioSetupDraft.capture()')
                await page.click('#recoverSharedSetup');await page.wait_for_function('!StudioSetupApply.controller.state.pending&&!StudioSetupApply.controller.running')
                check(len(COMMANDS)==writes and s.upload_count==uploads and READS[-1].endswith('/'+pending['request_id']),'restore recovery is GET-only with zero additional writes or copies')
                check(await page.evaluate('StudioSetupDraft.capture()')==reload_draft,'restore recovery leaves the reopened editor untouched')
                await page.locator('#sharedSetupPanel').scroll_into_view_if_needed();await page.screenshot(path=str(out/'restore-recovered.png'),animations='disabled')
            check(not errors,'zero page exceptions')
            seen=('/api/estimate','/api/assets/selection')  # the Library's read-only observation of off-page IDs
            forbidden=[x for x in advice.CALLS if x not in (advice.PREFIX,advice.PROPOSAL)+seen]+[x['path'] for x in advice.fixture.POSTS if x['path'] not in seen]
            check(not forbidden,'zero generation, installation, switching or unrelated asset-write calls: '+str(forbidden))
            (out/'result.json').write_text(json.dumps({'checks':checks,'passed':len(checks),'native':not inert,'commands':COMMANDS,'reads':READS,'uploads':s.upload_count,'errors':errors,'source_sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ('app/static/setup-apply.js','app/static/setup-history.js','app/static/setup-proposal.css','app/static/studio-workbench.js','studio_workflow/setup_drafts.py')}},indent=2))
            await browser.close()
    finally:http.shutdown();http.server_close();thread.join(5);case.doCleanups()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'.runtime/setup-apply');p.add_argument('--inert',action='store_true');a=p.parse_args();asyncio.run(run(a.out,a.inert))
