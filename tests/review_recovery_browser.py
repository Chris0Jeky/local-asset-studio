"""Review reload QA: actual UI, metadata HTTP and temporary SQLite; no inference.

Default: native HTTP, native tab storage and page.reload. --inert is explicitly a
component simulation, replacing browser storage/network and recreating the page
with a copied journal. It must not be reported as native reload evidence.
"""
import argparse
import asyncio
import hashlib
import io
import json
import shutil
import socket
import tempfile
import threading
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from playwright.async_api import async_playwright
import studio_browser_smoke as fixture
from asset_detail_browser import inert_page
import server as production

ROOT = Path(__file__).resolve().parents[1]
KEY = 'studio.asset-review-recovery.v1'


async def exercise(args):
    args.out.mkdir(parents=True, exist_ok=True)
    checks, errors, writes = [], [], []
    flags = {'lose': False, 'fail': False, 'read_fail': False}
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        store = production.AssetWorkspace(root)
        source = root/'source.png'
        Image.new('RGB', (48, 64), (100, 110, 120)).save(source)
        def register(target):
            return target.register({'id':'reload-qa','preset_name':'Review recovery QA','created_at':100,
                                    'outputs':[{'filename':'source.png','media_type':'image'}]}, 0, source)
        asset = register(store)
        class Handler(production.Handler):
            studio = SimpleNamespace(assets=store)
            json = fixture.Handler.json
            def do_GET(self):
                if self.path.endswith('/metadata') and flags['read_fail']:
                    return self._json(503, {'error':'Injected metadata observation failure'})
                if self.path == '/api/workspace' or self.path.startswith('/api/assets/'):
                    return super().do_GET()
                return fixture.Handler.do_GET(self)
            def do_POST(self):
                if self.path == '/api/assets/update':
                    raw = self.rfile.read(int(self.headers['Content-Length']))
                    writes.append({'body':raw.decode('utf-8'), 'command':json.loads(raw)})
                    self.rfile = io.BytesIO(raw)
                    if flags['fail']:
                        flags['fail'] = False
                        return self._json(503, {'error':'Injected pre-commit interruption'})
                    return super().do_POST()
                return fixture.Handler.do_POST(self)
            def _json(self, status, data):
                if flags['lose'] and self.path == '/api/assets/update' and data.get('status') == 'applied':
                    flags['lose'] = False
                    self.close_connection = True
                    self.connection.shutdown(socket.SHUT_RDWR)
                    return
                return super()._json(status, data)
        http = ThreadingHTTPServer(('127.0.0.1',8191), Handler)
        thread = threading.Thread(target=http.serve_forever,daemon=True)
        thread.start();fixture.POSTS.clear()
        def check(name, condition):
            checks.append({'id':name,'passed':bool(condition)})
            print(name, bool(condition), flush=True)
            if not condition:raise AssertionError(name)
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
                context = await browser.new_context(viewport={'width':1440,'height':1100},reduced_motion='reduce')
                async def new_page(raw=None):
                    page = await context.new_page()
                    page.set_default_timeout(6000)
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    if args.inert:await inert_page(page,8191)
                    else:await page.goto('http://127.0.0.1:8191/#assets')
                    await ready(page)
                    if raw is not None:await page.evaluate('(raw)=>sessionStorage.setItem("'+KEY+'",raw)',raw)
                    await open_asset(page)
                    return page
                async def ready(page):
                    await page.wait_for_function('!!catalog && !!selected && !!assetReviewRecovery')
                    await page.evaluate("showView('assets')")
                async def open_asset(page):
                    await page.wait_for_function("!assetRefreshing && !!assetState.workspace_id")
                    await page.evaluate("async id=>{await refreshAssets(true);openAsset(id)}",asset)
                    await page.wait_for_selector("#assetDialog[open]")
                async def reload(page):
                    if args.inert:
                        raw = await page.evaluate('sessionStorage.getItem("'+KEY+'")')
                        await page.close()
                        return await new_page(raw)
                    await page.reload();await ready(page);await open_asset(page)
                    return page
                async def restore(page):
                    await page.click('[data-review-restore]')
                    await page.wait_for_function('!assetReviewRecovery.blocked()')
                async def saved(page):
                    await page.wait_for_function('!assetDetailBusy && !assetDetailPending && !assetDetailConflict')
                async def unknown(page):
                    await page.wait_for_function('!assetDetailBusy && !!assetDetailPending')
                async def record(page):
                    return await page.evaluate('JSON.parse(sessionStorage.getItem("'+KEY+'"))')
                async def approve(dialog):await dialog.accept()
                async def deny(dialog):await dialog.dismiss()
                a = await new_page()
                await a.fill('#assetNotes','Local review: retain the original sleeve')
                check('RELOAD-01 draft checkpoint before any server mutation',not writes and (await record(a))['entries'][0]['draft']['notes'].startswith('Local review:'))
                before=len(writes);a=await reload(a)
                check('RELOAD-02 explicit offer after reload',await a.locator('[data-review-restore]').count()==1 and len(writes)==before)
                check('RELOAD-03 offer blocks accidental metadata save',await a.locator('#saveAssetDetails').is_disabled())
                check('RELOAD-27 offer status distinguishes saved metadata from local draft','Saved metadata is shown below' in await a.inner_text('#assetDetailStatus'))
                await restore(a)
                check('RELOAD-04 restore is read-only and retains draft',len(writes)==before and await a.input_value('#assetNotes')=='Local review: retain the original sleeve')
                await a.click('#saveAssetDetails');await saved(a)
                check('RELOAD-26 pending command is bound to its server database',writes[-1]['command']['workspace_id']==store.snapshot()['workspace_id'])
                check('RELOAD-05 confirmed clean save removes the recovery draft',(await record(a))['entries']==[] and store.get(asset)['notes'].startswith('Local review:'))
                b = await new_page()
                await a.fill('#assetNotes','Draft A');await b.fill('#assetNotes','Draft B')
                check('RELOAD-06 tabs have independent drafts',(await record(a))['entries'][0]['draft']['notes']=='Draft A' and (await record(b))['entries'][0]['draft']['notes']=='Draft B')
                await a.click('#saveAssetDetails');await saved(a);b=await reload(b)
                before=len(writes);await restore(b)
                check('RELOAD-07 stale restored draft uses revision conflict',await b.evaluate('!!assetDetailConflict') and await b.input_value('#assetNotes')=='Draft B' and len(writes)==before)
                check('RELOAD-08 read-only conflict exposes both versions','Draft A' in await b.inner_text('#assetDetailConflict') and 'Draft B' in await b.inner_text('#assetDetailConflict'))
                await b.set_viewport_size({'width':390,'height':1100});await b.locator('#assetDetailConflict').scroll_into_view_if_needed()
                check('RELOAD-09 narrow conflict stays within viewport',await b.evaluate("document.querySelector('#assetDialog').scrollWidth<=document.querySelector('#assetDialog').clientWidth"))
                await b.screenshot(path=str(args.out/'recovered-conflict-390.png'))
                await b.click('[data-asset-rebase]');await b.click('#saveAssetDetails');await saved(b)
                flags['lose']=True;await b.fill('#assetNotes','Committed with lost reply');await b.click('#saveAssetDetails');await unknown(b)
                sent=writes[-1]['body'];await b.fill('#assetNotes','Newer notes after loss')
                check('RELOAD-10 immutable command is distinct from newer typing',(await record(b))['entries'][0]['pending']['body']==sent and (await record(b))['entries'][0]['draft']['notes']=='Newer notes after loss')
                before=len(writes);b=await reload(b)
                await b.set_viewport_size({'width':1440,'height':1100})
                await b.screenshot(path=str(args.out/'reload-offer-desktop.png'))
                await restore(b)
                check('RELOAD-11 lost-response reload never posts automatically',len(writes)==before and await b.evaluate('assetDetailPending.body')==sent)
                # Reopen the real SQLite authority to establish durable receipt recovery.
                store=production.AssetWorkspace(root);Handler.studio.assets=store
                await b.click('[data-asset-save-check]');await saved(b)
                check('RELOAD-12 receipt recovery after store restart is read-only',len(writes)==before and store.get(asset)['notes']=='Committed with lost reply')
                check('RELOAD-13 receipt retains newer typing as unsaved',await b.input_value('#assetNotes')=='Newer notes after loss' and await b.evaluate('assetDetailDirty()'))
                await b.click('#saveAssetDetails');await saved(b)
                flags['lose']=True;await b.fill('#assetNotes','Exact replay');await b.click('#saveAssetDetails');await unknown(b)
                sent=writes[-1]['body'];revision=store.get(asset)['metadata_revision'];b=await reload(b);await restore(b)
                await b.click('[data-asset-save-retry]');await saved(b)
                check('RELOAD-14 explicit exact retry preserves bytes and single effect',writes[-1]['body']==sent and store.get(asset)['metadata_revision']==revision)
                flags['fail']=True;await b.fill('#assetNotes','Not yet saved');await b.click('#saveAssetDetails');await unknown(b)
                sent=writes[-1]['body'];b=await reload(b);await restore(b);before=len(writes)
                await b.click('[data-asset-save-check]');await unknown(b)
                check('RELOAD-15 missing receipt remains unknown',len(writes)==before and 'No receipt exists yet' in await b.inner_text('#assetDetailStatus'))
                await b.click('[data-asset-save-retry]');await saved(b)
                check('RELOAD-16 retry after pre-commit loss uses original identity',writes[-1]['body']==sent and store.get(asset)['notes']=='Not yet saved')
                # Failed observation must not apply the local envelope or make a write.
                await b.fill('#assetNotes','Retain during failed observation');b=await reload(b)
                flags['read_fail']=True;before=len(writes);await b.click('[data-review-restore]')
                await b.wait_for_function("document.querySelector('#assetDetailStatus').textContent.includes('Recovery not applied')")
                check('RELOAD-17 failed restore retains its offer and record',await b.locator('[data-review-restore]').count()==1 and len(writes)==before and (await record(b))['entries'][0]['draft']['notes']=='Retain during failed observation')
                flags['read_fail']=False;b.on('dialog',approve);await b.click('[data-review-discard]');b.remove_listener('dialog',approve)
                check('RELOAD-18 explicit discard does not change saved metadata',(await record(b))['entries']==[] and len(writes)==before and store.get(asset)['notes']=='Not yet saved')
                # Quota failure keeps the draft but requires a decision before unprotected dispatch.
                await b.evaluate('''() => {window.qaStorage=Object.getPrototypeOf(sessionStorage);window.qaSet=qaStorage.setItem;
                  qaStorage.setItem=function(k,v){if(k==='studio.asset-review-recovery.v1')throw Error('QuotaExceededError');return qaSet.call(this,k,v)};}''')
                await b.fill('#assetNotes','Quota draft');before=len(writes);b.on('dialog',deny);await b.click('#saveAssetDetails');b.remove_listener('dialog',deny)
                check('RELOAD-19 declined unprotected save dispatches nothing',len(writes)==before and await b.input_value('#assetNotes')=='Quota draft' and 'unavailable' in await b.inner_text('#assetReviewStorage'))
                await b.evaluate('() => {qaStorage.setItem=qaSet;}');await b.fill('#assetNotes','Draft before workspace switch')
                oldscope=store.snapshot()['workspace_id'];other=production.AssetWorkspace(root/'other');register(other);Handler.studio.assets=other
                b=await reload(b)
                check('RELOAD-20 another workspace never inherits recovery',await b.locator('[data-review-restore]').count()==0 and any(e['workspace']==oldscope for e in (await record(b))['entries']))
                Handler.studio.assets=store;b=await reload(b);await restore(b)
                check('RELOAD-21 returning to original workspace recovers original draft',await b.input_value('#assetNotes')=='Draft before workspace switch')
                b.on('dialog',approve);await b.click('#closeAssetDialog');b.remove_listener('dialog',approve)
                # Native dialog.close queues its close event; observe journal cleanup, not click return.
                await b.wait_for_function("!document.querySelector('#assetDialog').open && JSON.parse(sessionStorage.getItem('studio.asset-review-recovery.v1')).entries.length===0")
                check('RELOAD-22 normal discard close clears only the local draft',(await record(b))['entries']==[])
                # Future/malformed envelopes are data, never executable commands or silent resets.
                await b.evaluate('sessionStorage.setItem("'+KEY+'",\'{"version":99,"entries":[]}\')');b=await reload(b)
                check('RELOAD-23 future journal version is retained visibly',await b.evaluate('sessionStorage.getItem("'+KEY+'")')=='{"version":99,"entries":[]}' and 'Unsupported' in await b.inner_text('#assetReviewStorage'))
                check('RELOAD-24 no generation or backend changes',all(p['path'] in ['/api/estimate','/api/references/check'] for p in fixture.POSTS))
                check('RELOAD-25 no JavaScript exceptions',not errors)
                await browser.close()
        finally:
            http.shutdown();http.server_close();thread.join(2)
            receipt={'mode':'inert: copied journal across new pages; real HTTP/SQLite, not native reload/storage' if args.inert else 'native HTTP, tab sessionStorage and page.reload; real SQLite',
                     'checks':checks,'errors':errors,'writes':writes,'other_posts':fixture.POSTS,
                     'pass':sum(c['passed'] for c in checks),'fail':sum(not c['passed'] for c in checks),
                     'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['app/static/review-recovery-core.js','app/static/review-recovery-ui.js','app/static/workspace.js','app/workspace.py']},
                     'limits':['No owner-PC generation, native editor, screen-reader or browser-crash recovery evidence.','Closed tabs clear sessionStorage; bulk command drafts remain transient.']}
            (args.out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    if len(checks)!=27 or errors:raise AssertionError('Incomplete or exception-bearing browser evidence')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--inert',action='store_true')
    asyncio.run(exercise(parser.parse_args()))
