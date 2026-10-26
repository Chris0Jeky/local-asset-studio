"""Actual metadata HTTP + SQLite beneath the real Studio UI; synthetic non-generation APIs.

Runs its own disposable server on a free loopback port (--port fixes one), refusing an occupied port. It never connects
this fixture to a running Studio. --inert substitutes only browser storage/transport
for environments that prohibit navigation; default mode uses native HTTP.
"""
from browser_ports import evidence_screenshot
import argparse
import asyncio
import io
import json
import shutil
import socket
import tempfile
import threading
import uuid
from pathlib import Path
from types import SimpleNamespace

from playwright.async_api import async_playwright
from PIL import Image
import studio_browser_smoke as fixture
from asset_detail_browser import inert_page
import server as production
from browser_ports import BoundPortGuard


async def exercise(args):
    args.out.mkdir(parents=True,exist_ok=True)
    checks=[];errors=[];writes=[];flags={'lose':False,'fail':False}
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary);store=production.AssetWorkspace(root)
        source=root/'source.png';Image.new('RGB',(48,64),(100,110,120)).save(source)
        ids=[store.register({'id':f'qa-{i}','preset_name':f'Metadata QA {i}','created_at':100-i,
                             'outputs':[{'filename':'source.png','media_type':'image'}]},0,source) for i in range(2)]
        class Handler(BoundPortGuard, production.extend_handler(production.Handler)):
            studio=SimpleNamespace(assets=store,jobs={})
            json=fixture.Handler.json
            def do_GET(self):
                if self.path=='/api/workspace' or self.path.startswith('/api/assets/') or self.path.startswith('/api/collections'):
                    return super().do_GET()
                return fixture.Handler.do_GET(self)
            def do_POST(self):
                if self.path=='/api/assets/selection':return super().do_POST()  # read-only Workspace observation, served by the real store
                if self.path=='/api/assets/update':
                    raw=self.rfile.read(int(self.headers['Content-Length']));writes.append(json.loads(raw));self.rfile=io.BytesIO(raw)
                    if flags['fail']:
                        flags['fail']=False;return self._json(503,{'error':'Injected service interruption before commit'})
                    return super().do_POST()
                return fixture.Handler.do_POST(self)
            def _json(self,status,data):
                if flags['lose'] and self.path=='/api/assets/update' and data.get('status')=='applied':
                    flags['lose']=False;self.close_connection=True
                    self.connection.shutdown(socket.SHUT_RDWR)
                    return
                return super()._json(status,data)
        # Production Host/Origin checks stay as shipped; BoundPortGuard only accepts this server's bound port.
        http=production.StudioHTTPServer(('127.0.0.1', args.port),Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start();fixture.POSTS.clear()
        def record(name,condition):
            checks.append({'id':name,'passed':bool(condition)});print(name,bool(condition),flush=True)
            if not condition:raise AssertionError(name)
        async def open_asset(page,identifier=ids[0]):
            await page.evaluate("""async id=>{
              const d=document.querySelector('#assetDialog');
              if(d.open)await new Promise(resolve=>{d.addEventListener('close',resolve,{once:true});d.close();});
              assetState=await api('/api/workspace');renderAssets();openAsset(id);
            }""",identifier)
        async def saved(page):await page.wait_for_function('!assetDetailBusy && !assetDetailPending && !assetDetailConflict')
        async def conflicted(page):await page.wait_for_function('!assetDetailBusy && !!assetDetailConflict')
        async def unknown(page):await page.wait_for_function('!assetDetailBusy && !!assetDetailPending')
        try:
            async with async_playwright() as pw:
                browser=await pw.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
                context=await browser.new_context(viewport={'width':1440,'height':1100},reduced_motion='reduce')
                pages=[await context.new_page(),await context.new_page()]
                for page in pages:
                    page.set_default_timeout(6000);page.on('pageerror',lambda e:errors.append(str(e)))
                    if args.inert:await inert_page(page, http.server_port)
                    else:await page.goto(f'http://127.0.0.1:{http.server_port}/#assets', timeout=20000)
                    await page.wait_for_function('!!catalog && !!selected')
                    await page.evaluate("showView('assets')")
                    await open_asset(page)
                a,b=pages
                await a.fill('#assetNotes','A confirmed correction');await a.click('#saveAssetDetails');await saved(a)
                await b.fill('#assetTitle','B revised title');await b.click('#saveAssetDetails');await conflicted(b)
                record('META-01 stale form never erases confirmed notes',store.get(ids[0])['notes']=='A confirmed correction')
                record('META-02 conflict retains local draft',await b.input_value('#assetTitle')=='B revised title')
                record('META-03 conflict shows saved version', 'A confirmed correction' in await b.locator('#assetDetailConflict').inner_text())
                before=len(writes);await b.click('[data-asset-rebase]')
                record('META-04 explicit rebase does not write',len(writes)==before)
                record('META-05 untouched remote notes survive rebase',await b.input_value('#assetNotes')=='A confirmed correction')
                await b.click('#saveAssetDetails');await saved(b)
                record('META-06 reviewed save writes only dirty title',writes[-1].get('title')=='B revised title' and 'notes' not in writes[-1] and store.get(ids[0])['metadata_revision']==2)
                await open_asset(a);await open_asset(b)
                await a.fill('#assetNotes','New note from A');await a.click('#saveAssetDetails');await saved(a)
                await b.fill('#assetNotes','B wants a different correction');await b.click('#saveAssetDetails');await conflicted(b)
                record('META-07 same-field conflict exposes both choices','Both changed' in await b.locator('#assetDetailConflict').inner_text())
                await evidence_screenshot(b, path=str(args.out/'conflict-desktop.png'))
                await b.set_viewport_size({'width':390,'height':1100});await b.locator('#assetDetailConflict').scroll_into_view_if_needed()
                record('META-08 narrow conflict remains within viewport',await b.evaluate("document.documentElement.scrollWidth<=innerWidth && document.querySelector('#assetDialog').scrollWidth<=document.querySelector('#assetDialog').clientWidth"))
                await evidence_screenshot(b, path=str(args.out/'conflict-390.png'))
                before=len(writes);await b.click('[data-asset-current]')
                record('META-09 use saved version is read-only',len(writes)==before and await b.input_value('#assetNotes')=='New note from A')
                await b.set_viewport_size({'width':1440,'height':1100})
                await open_asset(b);flags['lose']=True;await b.fill('#assetNotes','Committed but reply lost');await b.click('#saveAssetDetails');await unknown(b)
                record('META-10 dropped HTTP reply leaves committed server evidence',store.get(ids[0])['notes']=='Committed but reply lost')
                await b.fill('#assetNotes','Newer typing after loss');before=len(writes)
                await b.click('[data-asset-save-check]');await saved(b)
                record('META-11 status lookup never repeats POST',len(writes)==before)
                record('META-12 receipt preserves newer typing as unsaved',await b.input_value('#assetNotes')=='Newer typing after loss' and await b.evaluate('assetDetailDirty()'))
                await b.click('#saveAssetDetails');await saved(b)
                await open_asset(b);flags['lose']=True;await b.fill('#assetNotes','Exact retry candidate');await b.click('#saveAssetDetails');await unknown(b)
                original=writes[-1].copy();revision=store.get(ids[0])['metadata_revision'];await b.click('[data-asset-save-retry]');await saved(b)
                record('META-13 explicit retry preserves exact command',writes[-1]==original)
                record('META-14 duplicate POST has one SQLite effect',store.get(ids[0])['metadata_revision']==revision)
                await open_asset(b);flags['fail']=True;await b.fill('#assetNotes','Not yet committed');await b.click('#saveAssetDetails');await unknown(b)
                before=len(writes);await b.click('[data-asset-save-check]');await unknown(b)
                record('META-15 absent receipt stays unknown',len(writes)==before and 'No receipt exists yet' in await b.locator('#assetDetailStatus').inner_text())
                await b.click('[data-asset-save-retry]');await saved(b)
                record('META-16 retry after pre-commit failure preserves draft intent',store.get(ids[0])['notes']=='Not yet committed')
                # Bulk path: same selection version, one concurrent metadata update.
                await b.evaluate("document.querySelector('#assetDialog').close()")
                await b.evaluate("async ids=>{assetState=await api('/api/workspace');assetSelection=new Set(ids);renderAssets();}",ids)
                row=store.get(ids[0]);store.update({'request_id':uuid.uuid4().hex,'expected_revisions':{ids[0]:row['metadata_revision']},'ids':[ids[0]],'action':'edit','notes':'Concurrent bulk blocker'})
                await b.click('[data-bulk="selected"]')
                await b.wait_for_function('!assetLibraryBusy')
                record('META-17 stale bulk leaves every review unchanged',all(store.get(i)['review']=='unreviewed' for i in ids))
                record('META-18 stale bulk preserves selection',await b.evaluate('assetSelection.size')==2)
                await open_asset(b)
                flags['lose']=True;await b.click('#assetTrash');await unknown(b)
                await b.fill('#assetNotes','New notes after lost Trash response')
                before=len(writes);await b.click('[data-asset-save-check]');await saved(b)
                record('META-21 recovered Trash preserves later typing',await b.locator('#assetDialog').is_visible() and
                       await b.input_value('#assetNotes')=='New notes after lost Trash response' and await b.evaluate('assetDetailDirty()') and
                       store.get(ids[0])['trashed_at'] is not None and len(writes)==before)
                # #1211: chip repaint keeps keyboard focus, and restoring the saved answers is not a dirty edit.
                row=store.get(ids[1]);store.update({'request_id':uuid.uuid4().hex,'expected_revisions':{ids[1]:row['metadata_revision']},'ids':[ids[1]],'action':'edit','tags':['check:style=yes','hero']})
                await open_asset(a,ids[1]);before=len(writes)
                style=a.locator('[data-review-check="style"]');await style.focus();await a.keyboard.press('Enter')
                record('META-22 quick-check repaint preserves its focused button',await a.evaluate("document.activeElement?.dataset.reviewCheck==='style'"))
                hands=a.locator('[data-review-reason="hands"]');await hands.focus();await a.keyboard.press('Enter');await a.keyboard.press('Enter')
                record('META-23 reason-chip repaint preserves focus and sends nothing',await a.evaluate("document.activeElement?.dataset.reviewReason==='hands'") and len(writes)==before)
                await style.focus();await a.keyboard.press('Enter');await a.keyboard.press('Enter')
                record('META-24 restoring answers clears dirty state and retained draft',await a.input_value('#assetTags')=='hero, check:style=yes' and await a.evaluate('!assetDetailDirty() && assetRetainedDetail===null'))
                await a.click('#saveAssetDetails')
                record('META-25 saving the restored answer set is read-only',len(writes)==before and 'No unsaved changes' in await a.locator('#assetDetailStatus').inner_text())
                await a.click('#closeAssetDialog');await a.wait_for_function("!document.querySelector('#assetDialog').open")
                await a.fill('#assetSearch','no-matching-review-check-picture')
                await a.wait_for_function('!assetSearchTimer&&!assetRefreshing&&assetPaging.query===assetPageQuery()')
                plan={'id':'c'*32,'name':'Saved checks fixture','kind':'comparison','axis':'seed','values':[1],
                      'budget':{'reserved':1,'allowance':1},'created_at':1790000000,
                      'stages':[{'label':'A','job':{'id':'job-checks','preset_id':'fixture-create','status':'completed','outputs':[{'asset_id':ids[1],'media_type':'image'}]}}],
                      'state':{'status':'awaiting_review','message':'Finished'}}
                async def comparison_read(route):await route.fulfill(content_type='application/json',body=json.dumps([plan]))
                await a.route('**/api/production',comparison_read)
                await a.evaluate("productionId=null;showView('production')")
                load=a.locator(f'[data-candidate-check-load="{ids[1]}"]');await load.wait_for()
                await a.set_viewport_size({'width':390,'height':1100});await load.scroll_into_view_if_needed()
                record('META-26 off-page saved answers stay unknown until read',await a.locator('.candidate-checks').inner_text()=='Saved checks not loaded. Read them before answering.\n\nLoad saved checks' and await a.locator('[data-candidate-check]').count()==0 and await a.locator('.candidate-checks').evaluate('el=>el.scrollWidth<=el.clientWidth'))
                await evidence_screenshot(a,path=str(args.out/'checks-unloaded-390.png'))
                before=len(writes);await load.focus();await a.keyboard.press('Enter')
                loaded=a.locator(f'[data-candidate-check="style"][data-asset="{ids[1]}"]');await loaded.wait_for()
                record('META-27 loading saved checks changes no answer and focuses the loaded chip',len(writes)==before and (await loaded.get_attribute('aria-label')).startswith('style: yes.') and await a.evaluate("document.activeElement?.dataset.candidateCheck==='style'") and store.get(ids[1])['tags']==['check:style=yes','hero'])
                await a.set_viewport_size({'width':1440,'height':1100});await loaded.scroll_into_view_if_needed()
                await evidence_screenshot(a,path=str(args.out/'checks-loaded-1440.png'))
                await a.keyboard.press('1');await a.wait_for_function("document.querySelector('#productionMessage').textContent.startsWith('Saved for this candidate: style no.')")
                record('META-28 comparison key changes the observed saved answer once',len(writes)==before+1 and 'check:style=no' in store.get(ids[1])['tags'] and 'check:style=yes' not in store.get(ids[1])['tags'])
                record('META-19 no generation/backend mutation' ,all(p['path'] in ['/api/estimate','/api/references/check'] for p in fixture.POSTS))
                record('META-20 no page exceptions',not errors)
                await browser.close()
        finally:
            http.shutdown();http.server_close();thread.join(2)
            receipt={'mode':'inert storage/transport, real metadata HTTP and SQLite' if args.inert else 'native browser HTTP, real metadata HTTP and SQLite',
                     'checks':checks,'errors':errors,'mutations':writes,'other_posts':fixture.POSTS,
                     'limits':['Synthetic non-generation APIs; no Studio construction or model calls.',
                               'No owner-PC, screen-reader, reload-draft or artwork acceptance evidence.']}
            (args.out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    if len(checks)!=28:raise AssertionError('Scenario run did not complete')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--inert',action='store_true');parser.add_argument('--port', type=int, default=0, help='Fixed loopback port; 0 binds a free one')
    asyncio.run(exercise(parser.parse_args()))
