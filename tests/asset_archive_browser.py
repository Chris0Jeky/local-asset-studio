"""Native shipped Library + production asset HTTP/SQLite; synthetic startup catalog.

No model, runtime install or owner media. --inert substitutes origin/storage/transport
for policy-restricted local DOM checks; only the default mode is native acceptance.
"""
import argparse
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import threading
import traceback
from types import SimpleNamespace
from urllib.parse import urlsplit

from playwright.async_api import async_playwright
from PIL import Image
from browser_ports import browser_server
import studio_browser_smoke as fixture
from asset_detail_browser import inert_page
from test_server import server as production

ROOT=Path(__file__).resolve().parents[1]


async def run(args):
    args.out.mkdir(parents=True,exist_ok=True)
    checks=[];errors=[];server_errors=[];disconnects=[];requests=[];receipts=[];loss={'next':False}
    def check(name,passed):
        checks.append({'name':name,'passed':bool(passed)});print(name,bool(passed),flush=True)
        assert passed,name
    temp=tempfile.TemporaryDirectory(prefix='archive-browser-');root=Path(temp.name)
    store=production.AssetWorkspace(root);source=root/'synthetic.png'
    Image.new('RGB',(16,16),(120,140,160)).save(source)
    original=source.read_bytes();ids=[]
    for i in range(4):
        ids.append(store.register({'id':'archive-synthetic-run','created_at':10+i,'preset_name':'Archive synthetic',
                                  'outputs':[{'filename':'synthetic.png','media_type':'image'}]*4},i,source))
    private=store.register({'id':'archive-private','privacy':'private','created_at':50,'preset_name':'Private Archive canary',
                            'outputs':[{'filename':'synthetic.png','media_type':'image'}]},0,source)
    scope=store.snapshot()['workspace_id']
    col=store.collection({'name':'Retained collection'})['id']
    store.update({'ids':ids,'action':'add_collection','collection_id':col,'workspace_id':scope,
                  'request_id':'archive-browser-membership','expected_revisions':dict.fromkeys(ids,0)})
    paths={i:store.file(i,privacy='all') for i in [*ids,private]}
    def memberships():return {a['id']:a['collections'] for a in store.snapshot(privacy='all')['assets']}
    initial_memberships=memberships()

    class Base(production.Handler):
        studio=SimpleNamespace(assets=store,root=ROOT,jobs={})
        workspace_id=scope
        json=fixture.Handler.json
        def _safe_host(self):return self.headers.get('Host')=='127.0.0.1:'+str(self.server.server_port)
        def _safe_mutation(self):return self._safe_host() and self.headers.get('Origin')=='http://'+self.headers.get('Host','')
        def _json(self,status,value):
            if self.path=='/api/assets/update' and status==200:
                receipts.append(copy.deepcopy(value))
                if loss['next']:
                    loss['next']=False;self.close_connection=True;self.connection.shutdown(socket.SHUT_RDWR);return
            return super()._json(status,value)
        def do_GET(self):
            path=urlsplit(self.path).path
            if path.startswith('/api/assets/'):return super().do_GET()
            if path=='/api/workspace':return self._json(200,store.snapshot(privacy=self.headers.get('X-Studio-Privacy','regular')))
            return fixture.Handler.do_GET(self)
        def do_POST(self):
            if self.path=='/api/assets/update':return super().do_POST()
            if self.path in ('/api/estimate','/api/references/check'):return fixture.Handler.do_POST(self)
            return self._json(403,{'error':'Synthetic Archive journey refuses unrelated writes'})
    class Handler(production.extend_handler(Base)):
        def do_GET(self):
            requests.append({'method':'GET','path':self.path,'privacy':self.headers.get('X-Studio-Privacy','regular')})
            return super().do_GET()
        def do_POST(self):
            requests.append({'method':'POST','path':self.path,'privacy':self.headers.get('X-Studio-Privacy','regular')})
            return super().do_POST()
    http=browser_server(Handler)
    def server_error(request,address):
        error=sys.exc_info()[1]
        if isinstance(error,(BrokenPipeError,ConnectionResetError,ConnectionAbortedError)):disconnects.append(type(error).__name__)
        else:server_errors.append(traceback.format_exc())
    http.handle_error=server_error
    thread=threading.Thread(target=http.serve_forever,kwargs={'poll_interval':0.01},daemon=True);thread.start()
    origin='http://127.0.0.1:'+str(http.server_port);browser=None
    try:
        async with async_playwright() as pw:
            browser=await pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None,headless=True)
            context=await browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce')
            page=await context.new_page();page.set_default_timeout(8000);page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('dialog',lambda d:d.accept())
            if args.inert:
                await inert_page(page,http.server_port)
                await page.evaluate("showView('assets')")
            else:await page.goto(origin+'/#assets',timeout=20000)
            async def ready():
                await page.wait_for_function('assetState.workspace_id && !assetRefreshing && !!assetPaging',timeout=20000)
            async def open_asset(key):
                await page.locator('#assetGrid [data-asset-open="'+key+'"]').first.click()
                await page.wait_for_function('id=>activeAsset?.id===id && document.querySelector("#assetDialog").open',arg=key)
            async def settled():
                await page.wait_for_function('!assetDetailBusy && !assetLibraryBusy && !assetRefreshing')
            await ready()
            check('Default Library excludes private records',await page.locator('#assetGrid [data-asset-card="'+private+'"]').count()==0)
            await open_asset(ids[0]);await page.fill('#assetNotes','Unsaved Archive wording')
            await page.locator('#assetArchive').click();await settled()
            check('Archive is applied by the real Workspace command owner',store.get(ids[0])['archived_at'] is not None)
            check('Archive keeps the open unsaved editor',await page.locator('#assetDialog').evaluate('(el)=>el.open') and await page.input_value('#assetNotes')=='Unsaved Archive wording')
            check('Archive does not save local notes',store.get(ids[0])['notes']=='')
            check('Archive removes its card from the active view',await page.locator('#assetGrid [data-asset-card="'+ids[0]+'"]').count()==0)
            await page.locator('#assetArchive').click();await settled()
            check('Return to active restores visibility without discarding draft',store.get(ids[0])['archived_at'] is None and await page.input_value('#assetNotes')=='Unsaved Archive wording')
            # Fault after the real SQLite commit, before any response bytes.
            loss['next']=True;before=len(receipts);await page.locator('#assetArchive').click()
            await page.wait_for_function('!!assetDetailPending && !assetDetailBusy')
            check('Lost response retains exact pending Archive identity',len(receipts)==before+1 and await page.evaluate('assetDetailPending.command.action==="archive"'))
            saved=await page.evaluate('assetDetailPending.body')
            if args.inert:
                check('Inert mode does not claim native reload persistence',True)
            else:
                await page.reload();await ready()
                await page.locator('[data-asset-recover-open]').click()
                await page.wait_for_function('document.querySelector("#assetDialog").open && !!assetDetailPending')
                check('Same-tab native reload restores exact command and draft',await page.evaluate('assetDetailPending.body')==saved and await page.input_value('#assetNotes')=='Unsaved Archive wording')
            writes_before=sum(r['method']=='POST' and r['path']=='/api/assets/update' for r in requests)
            await page.locator('[data-asset-save-check]').click();await settled()
            check('Receipt recovery performs no replay',sum(r['method']=='POST' and r['path']=='/api/assets/update' for r in requests)==writes_before and not await page.evaluate('!!assetDetailPending'))
            check('Recovered Archive retains unsaved wording',await page.input_value('#assetNotes')=='Unsaved Archive wording')
            await page.locator('#closeAssetDialog').click()
            await page.select_option('#assetArchiveFilter','archived');await ready()
            await page.wait_for_selector('#assetGrid [data-asset-card="'+ids[0]+'"]')
            check('Archived filter retrieves the original ID',await page.locator('#assetGrid [data-asset-card]').count()==1)
            await open_asset(ids[0]);await page.locator('[data-asset-siblings="load"]').click()
            await page.wait_for_function('assetSiblingPage?.loaded && !assetSiblingRequest')
            check('Same-run inspection includes active and archived siblings',await page.locator('#assetSameRun [data-asset-open]').count()==4)
            await page.locator('#closeAssetDialog').click()
            await page.locator('#assetGrid [data-asset-check="'+ids[0]+'"]').check()
            await page.select_option('#assetArchiveFilter','active');await ready()
            await page.wait_for_selector('#assetGrid [data-asset-card="'+ids[1]+'"]')
            await page.locator('#assetGrid [data-asset-check="'+ids[1]+'"]').check()
            await page.locator('[data-bulk="archive"]').click();await settled()
            check('Off-page mixed bulk Archive keeps no-op revisions',store.get(ids[0])['metadata_revision']==4 and store.get(ids[1])['archived_at'] is not None)
            await page.select_option('#assetArchiveFilter','archived');await ready()
            await page.wait_for_function('assetPageRecords().length===2 && !assetRefreshing')
            await page.locator('#selectVisible').click();await page.locator('[data-bulk="unarchive"]').click();await settled()
            check('Bulk unarchive restores both IDs',all(store.get(i)['archived_at'] is None for i in ids[:2]))
            await page.locator('[data-privacy-scope="private"]').click();await ready()
            await page.select_option('#assetArchiveFilter','active');await ready()
            await open_asset(private);await page.locator('#assetArchive').click();await settled();await page.locator('#closeAssetDialog').click()
            await page.select_option('#assetArchiveFilter','archived');await ready()
            await page.wait_for_selector('#assetGrid [data-asset-card="'+private+'"]')
            check('Private Archive uses explicit private command scope',store.get(private,privacy='private')['archived_at'] is not None and any(r['method']=='POST' and r['path']=='/api/assets/update' and r['privacy']=='private' for r in requests))
            await page.locator('[data-privacy-scope="regular"]').click();await ready()
            await page.select_option('#assetArchiveFilter','all');await ready()
            await page.wait_for_function('assetPageRecords().length===4 && !assetRefreshing')
            check('Regular all-archive view still excludes private IDs',await page.locator('#assetGrid [data-asset-card="'+private+'"]').count()==0)
            for width in (1440,390):
                await page.set_viewport_size({'width':width,'height':1000})
                await page.locator('#assetArchiveFilter').focus()
                check(str(width)+'px Archive control is visible and keyboard reachable',await page.locator('#assetArchiveFilter').is_visible() and await page.locator('#assetArchiveFilter').evaluate('(el)=>el===document.activeElement'))
                check(str(width)+'px Library has no horizontal overflow',await page.evaluate('document.documentElement.scrollWidth')<=width)
                await page.screenshot(path=str(args.out/('archive-'+str(width)+'.png')),full_page=True)
            check('Original files and collection memberships remain unchanged',source.read_bytes()==original and all(store.file(i,privacy='all')==path and path.read_bytes()==original for i,path in paths.items()) and memberships()==initial_memberships)
            check('No generation or unrelated mutation was requested',all(r['path'].split('?')[0] in ('/api/assets/update','/api/assets/selection','/api/estimate','/api/references/check') for r in requests if r['method']=='POST'))
            check('No page exceptions',not errors);check('No unexpected handler errors',not server_errors)
            await browser.close();browser=None
    finally:
        if browser:await browser.close()
        http.shutdown();http.server_close();thread.join(3);temp.cleanup()
        sources=('app/workspace.py','studio_workflow/asset_reads.py','app/static/workspace.js','app/static/index.html',
                 'app/static/asset-recovery.js','app/static/asset-recovery-shelf.js','app/static/asset-recovery-lifecycle.js')
        (args.out/'receipt.json').write_text(json.dumps({'native_origin':not args.inert,'checks':checks,'page_errors':errors,
            'server_errors':server_errors,'client_disconnects':disconnects,'requests':requests,'commands':receipts,
            'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
            'limits':'Synthetic startup catalog/media; production asset routes and SQLite. No model generation or owner acceptance.'},indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--inert',action='store_true')
    parser.add_argument('--out',type=Path,default=ROOT/'.runtime/asset-archive')
    asyncio.run(run(parser.parse_args()))
