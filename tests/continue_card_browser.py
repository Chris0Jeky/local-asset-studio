"""Make Continue over actual HTTP and disposable SQLite; all writes refused."""
import argparse
import asyncio
import copy
import json
import os
from pathlib import Path
import shutil
import threading
from unittest.mock import patch
from urllib.parse import urlsplit

from playwright.async_api import async_playwright, expect
from browser_ports import browser_server
import studio_browser_smoke as shell
from test_native_export_history import NativeExportHistoryTests, server
import av_projects
from studio_av import project as av


async def run(out):
    out.mkdir(parents=True,exist_ok=True)
    checks,errors,requests=[],[],[];browser=None
    def check(name,value):
        checks.append({'name':name,'passed':bool(value)});print(name,bool(value),flush=True);assert value,name
    case=NativeExportHistoryTests();case.setUp();studio=case.studio;store=studio.assets
    ids=[case.asset['id']]
    source=store.file(ids[0]).read_bytes()
    for i in range(10):ids.append(studio.import_image(f'picture-{i}.png','image/png',source)['asset']['id'])
    with store.connection() as db:
        for i,key in enumerate(ids):
            db.execute('UPDATE assets SET created_at=?,title=?,review=?,privacy=? WHERE id=?',
                       (1700000000+i,'Older kept picture' if i==0 else 'Private kept picture' if i==10 else f'Picture {i}',
                        'selected' if i in (0,10) else 'needs_work' if i==1 else 'unreviewed','private' if i==10 else 'regular',key))
    plans=[case.prepare('ora'),case.prepare('atlas'),case.prepare('ora')]
    for i,(plan,status) in enumerate(zip(plans,('planned','completed','failed'))):
        studio.production._mutate(plan['id'],status=status)
        with studio.production.connect() as db:db.execute('UPDATE projects SET created=? WHERE id=?',(1700000200+i,plan['id']))
    scene_patches=[patch.object(studio.production.av,'executables',return_value={}),
                   patch.object(av_projects,'validate_media',side_effect=lambda p,root,tools:(av.validate(p,root),{}))]
    for mocked in scene_patches:mocked.start();case.addCleanup(mocked.stop)
    scenes=[]
    for i in range(8):
        scene=studio.production.av.create({'action':'create','name':'Saved scene '+str(i),'asset_ids':[ids[0]],'frames_per_shot':24});scenes.append(scene)
        with studio.production.connect() as db:db.execute('UPDATE projects SET created=? WHERE id=?',(1700000300+i,scene['id']))
    newest=scenes[-1]['id']
    studio.production.av.command(newest,{'action':'edit','expected_revision':0,'section':'shots','clip_id':'shot0','changes':{'frames':48}})
    studio.production._mutate(newest,status='failed')
    with studio.production.connect() as db:
        for key,revision,status,created in [('c'*32,0,'completed',1),('f'*32,1,'failed',2)]:
            db.execute('INSERT INTO av_renders VALUES (?,?,?,?,?,?,?)',(key,newest,revision,'{}',status,json.dumps({'artifacts':[],'message':'Synthetic retained '+status}),created))
    def scene_records():
        with studio.production.connect() as db:
            return {table:[tuple(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY rowid')]
                    for table in ('projects','av_documents','av_events','av_renders','av_exports')}
    scenes_before=scene_records()
    second=server.AssetWorkspace(case.root/'second-workspace')
    for mocked in reversed(case.fixture.patches):mocked.stop()
    before=copy.deepcopy(store.snapshot(privacy='all')['assets'])
    plan_before=[copy.deepcopy(studio.production._get(p['id'])) for p in plans]
    gate={'pause':False};entered=threading.Event();release=threading.Event()

    class Base(server.Handler):
        json=shell.Handler.json
        def log_message(self,*args):pass
        def _safe_host(self):return self.headers.get('Host')=='127.0.0.1:'+str(self.server.server_port)
        def _safe_mutation(self):return self._safe_host() and self.headers.get('Origin')=='http://'+self.headers.get('Host','')
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=='/api/looks':return self._json(200,json.loads((shell.ROOT/'presets/looks.json').read_text(encoding='utf-8')))
            if path=='/api/workspace/continue' and gate['pause']:
                gate['pause']=False;entered.set()
                if not release.wait(15):raise RuntimeError('Continue delay timed out')
            if path.startswith(('/api/assets/','/api/production','/api/workspace','/api/av')):return super().do_GET()
            return shell.Handler.do_GET(self)
        def do_POST(self):
            if self.path=='/api/assets/selection':return super().do_POST()
            return self._json(403,{'error':'Continue fixture refuses writes and generation'})
    Base.studio=studio
    class Handler(server.extend_handler(Base)):
        def do_GET(self):requests.append(('GET',self.path));return super().do_GET()
        def do_POST(self):requests.append(('POST',self.path));return super().do_POST()
    http=browser_server(Handler);thread=threading.Thread(target=http.serve_forever,kwargs={'poll_interval':.01},daemon=True);thread.start()
    origin='http://127.0.0.1:'+str(http.server_port)
    try:
        async with async_playwright() as pw:
            browser=await pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None,headless=True)
            context=await browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce')
            page=await context.new_page();page.set_default_timeout(10000);page.on('pageerror',lambda e:errors.append(str(e)))
            async def expand():
                await page.locator('#makeContinue>summary').focus();await page.keyboard.press('Enter')
                await expect(page.locator('[data-continue-refresh]')).to_be_enabled()
                await expect(page.locator('[data-continue-needs]')).to_be_visible()
            async def refresh():
                await page.locator('[data-continue-refresh]').click();await expect(page.locator('[data-continue-refresh]')).to_be_enabled()
            async def scope(value):
                await page.locator('[data-privacy-scope="'+value+'"]').click()
                await expect(page.locator('#makeContinue')).not_to_have_attribute('open','')
            await page.goto(origin+'/#make',timeout=25000)
            await expect(page.locator('#makeContinue>summary')).to_be_visible()
            check('Fresh browser storage leaves Continue collapsed and unread',not await page.locator('#makeContinue').evaluate('(n)=>n.open') and not any('/workspace/continue' in p for _,p in requests))
            await page.locator('#makeGoals [data-make-goal="character"]').click()
            await page.locator('#makeBody [data-make-look="look-wai-fantasy-portrait"]').click()
            await page.locator('#makeScene').fill('Unfinished Make wording')
            await expand()
            await expect(page.locator('[data-continue-asset]')).to_have_text('Older kept picture')
            check('Kept picture beyond the recent six is reachable',True)
            await expect(page.locator('[data-continue-plan]')).to_have_attribute('href','/?plan='+plans[2]['id']+'#production')
            check('Newest created failed native plan retains its recorded state', 'Recorded state: failed' in await page.locator('#makeContinue').inner_text())
            await expect(page.locator('[data-continue-scene]')).to_have_attribute('href','/av.html?project='+newest)
            check('Newest saved scene beyond six has its exact destination',await page.locator('[data-continue-scene]').inner_text()=='Saved scene 7')
            check('Saved scene revision and older completed render remain distinct','Saved revision 1' in await page.locator('#makeContinue').inner_text() and 'revision 0 (older than saved revision 1)' in await page.locator('#makeContinue').inner_text())
            check('Dates are explicitly creation dates and acceptance is not inferred','Created ' in await page.locator('#makeContinue').inner_text() and 'do not establish acceptance' in await page.locator('#makeContinue').inner_text())
            await page.screenshot(path=str(out/'continue-wide.png'))
            await page.set_viewport_size({'width':390,'height':844})
            await page.locator('#makeContinue').scroll_into_view_if_needed();await page.locator('#makeContinue').screenshot(path=str(out/'continue-narrow.png'))
            check('390px card has no horizontal page overflow',await page.evaluate('innerWidth===390&&document.documentElement.scrollWidth<=innerWidth'))
            await page.set_viewport_size({'width':1440,'height':1000})
            async with page.expect_popup() as opened:await page.locator('[data-continue-plan]').click()
            plan_page=await opened.value;await expect(plan_page.locator('#productionDetail')).to_contain_text(plans[2]['name']);await plan_page.close()
            check('Native link opens the existing exact plan destination',True)
            async with page.expect_popup() as opened:await page.locator('[data-continue-scene]').click()
            scene_page=await opened.value;scene_page.on('pageerror',lambda e:errors.append(str(e)))
            await expect(scene_page.locator('#avContent h2')).to_have_text('Saved scene 7')
            await expect(scene_page.locator('#avDocumentStatus')).to_contain_text('Revision 1')
            check('Scene link loads the exact saved project and revision',await scene_page.evaluate('avId')==newest)
            check('Scene recovery preserves unfinished Make wording',await page.input_value('#makeScene')=='Unfinished Make wording')
            await scene_page.screenshot(path=str(out/'scene-destination.png'));await scene_page.close()
            await page.locator('[data-continue-asset]').click();await expect(page.locator('#assetDialog')).to_be_visible()
            check('Kept link resolves the exact existing asset',await page.evaluate('activeAsset.id')==ids[0])
            await page.locator('#assetNotes').fill('Unfinished notes must remain')
            page.once('dialog',lambda dialog:dialog.dismiss())
            await page.evaluate('closeAssetDetails()')
            check('Draft remains unsaved',await page.input_value('#assetNotes')=='Unfinished notes must remain')
            await page.locator('#assetNotes').fill('');await page.evaluate('closeAssetDetails()')
            await page.locator('[data-continue-needs]').click()
            await expect(page.locator('#assetGrid button.asset-open[data-asset-open="'+ids[1]+'"]')).to_be_visible()
            check('Needs work uses the existing Library scope',await page.evaluate('assetScope')=='needs_work')
            await page.evaluate("showView('make')")
            await scope('private');await expand()
            await expect(page.locator('[data-continue-asset]')).to_have_text('Private kept picture')
            check('Private hides exports and selects its own kept picture',await page.locator('[data-continue-plan]').count()==0 and 'not read in Private' in await page.locator('#makeContinue').inner_text())
            check('Private hides saved scenes',await page.locator('[data-continue-scene]').count()==0 and 'Scenes are Regular-only' in await page.locator('#makeContinue').inner_text())
            await scope('all');await expand()
            check('All labels the native Regular boundary','Exports here are Regular-only' in await page.locator('#makeContinue').inner_text())
            check('All labels the scene Regular boundary','Scenes here are Regular-only' in await page.locator('#makeContinue').inner_text())
            await scope('regular');await expand()
            path=studio.production.root/plans[2]['id']/'plan.json';saved=path.read_bytes();path.unlink()
            try:
                await refresh();check('Missing latest plan is unavailable instead of empty or older','Native-export history unavailable' in await page.locator('#makeContinue').inner_text() and await page.locator('[data-continue-plan]').count()==0)
                await page.screenshot(path=str(out/'continue-unavailable.png'))
            finally:path.write_bytes(saved)
            scene_path=studio.production.root/newest/'plan.json';scene_saved=scene_path.read_bytes();scene_path.unlink()
            try:
                await refresh();check('Missing latest scene stays unavailable while native link survives','Saved-scene history unavailable' in await page.locator('#makeContinue').inner_text() and await page.locator('[data-continue-scene]').count()==0 and await page.locator('[data-continue-plan]').count()==1)
                await page.screenshot(path=str(out/'scene-unavailable.png'))
            finally:scene_path.write_bytes(scene_saved)
            gate['pause']=True;entered.clear();release.clear();await page.locator('[data-continue-refresh]').click()
            check('Delayed read entered actual HTTP handler',await asyncio.to_thread(entered.wait,5))
            await scope('private');await scope('regular');release.set()
            await page.wait_for_function("!document.querySelector('#makeContinue').open")
            await page.wait_for_timeout(150)
            check('Late privacy A-B-A response stays hidden',await page.locator('[data-continue-asset]').count()==0 and await page.locator('[data-continue-scene]').count()==0)
            await expand();gate['pause']=True;entered.clear();release.clear();await page.locator('[data-continue-refresh]').click()
            check('Workspace delay entered actual HTTP handler',await asyncio.to_thread(entered.wait,5))
            studio.assets=second;await page.evaluate('refreshAssets()');studio.assets=store;await page.evaluate('refreshAssets()');release.set()
            await page.wait_for_timeout(150)
            check('Late workspace A-B-A response stays hidden',not await page.locator('#makeContinue').evaluate('(n)=>n.open') and await page.locator('[data-continue-asset]').count()==0 and await page.locator('[data-continue-scene]').count()==0)
            await expand();await page.reload();await expect(page.locator('#makeContinue>summary')).to_be_visible()
            check('Expansion is not persisted',not await page.locator('#makeContinue').evaluate('(n)=>n.open'))
            check('Asset metadata unchanged by the browser',store.snapshot(privacy='all')['assets']==before)
            check('Native records unchanged by the browser',[studio.production._get(p['id']) for p in plans]==plan_before)
            check('Scene plans, revisions, attempts and exports unchanged by the browser',scene_records()==scenes_before)
            # The existing shell requests a timing estimate at startup; this fixture still refuses it.
            check('Only selection and the existing read-only timing request use POST',all(method=='GET' or path in ('/api/assets/selection','/api/estimate') for method,path in requests))
            check('No JavaScript page errors',not errors)
    finally:
        release.set();studio.assets=store
        if browser:await browser.close()
        http.shutdown();http.server_close();thread.join(timeout=2)
        (out/'result.json').write_text(json.dumps({'checks':checks,'errors':errors,'requests':requests},indent=2),encoding='utf-8')
        case.doCleanups()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    asyncio.run(run(parser.parse_args().out))
