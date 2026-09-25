"""Real collection HTTP/SQLite under the Studio shell; synthetic non-generation APIs.

Native browser HTTP by default. --inert explicitly substitutes browser origin,
storage and transport. --baseline records expectation failures but not exceptions.
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

ROOT=Path(__file__).resolve().parents[1]

async def exercise(args):
    args.out.mkdir(parents=True,exist_ok=True)
    checks=[];errors=[];writes=[];failure=None;gate=threading.Event();gate.set()
    flags={'reject':False,'lose':False,'hold_read':False,'read_captured':False};dialogs=[];consent={'yes':False}
    read_gate=threading.Event();read_gate.set()
    def check(id,text,value):
        checks.append({'id':id,'expectation':text,'passed':bool(value)})
        print(id,bool(value),flush=True)
        if not value and not args.baseline:raise AssertionError(text)
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);store=production.AssetWorkspace(root/'one');other=production.AssetWorkspace(root/'two')
        file=root/'original.png';Image.new('RGB',(48,64),(100,120,140)).save(file)
        aid=store.register({'id':'collection-fixture','outputs':[{'filename':file.name,'media_type':'image'}]},0,file)
        a=store.collection({'name':'Portraits','description':'Retain this note'})
        b=store.collection({'name':'Other','description':'Other note'})
        original_hash=hashlib.sha256(file.read_bytes()).hexdigest()
        class Handler(production.Handler):
            studio=SimpleNamespace(assets=store)
            json=fixture.Handler.json
            def _safe_host(self):
                return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"
            def _safe_mutation(self):
                return self._safe_host() and self.headers.get("Origin") == f"http://127.0.0.1:{self.server.server_port}"
            def do_GET(self):
                if self.path=='/api/workspace' and flags['hold_read']:
                    flags['hold_read']=False;snapshot=self.studio.assets.snapshot();flags['read_captured']=True
                    if not read_gate.wait(8):return self._json(503,{'error':'Held-read fixture deadline'})
                    return self._json(200,snapshot)
                if self.path=='/api/workspace' or self.path.startswith('/api/assets/'):return super().do_GET()
                return fixture.Handler.do_GET(self)
            def do_POST(self):
                if self.path=='/api/collections':
                    raw=self.rfile.read(int(self.headers['Content-Length']));writes.append(json.loads(raw));self.rfile=io.BytesIO(raw)
                    if not gate.wait(8):return self._json(503,{'error':'Fixture deadline'})
                    if flags['reject']:
                        flags['reject']=False;return self._json(400,{'format':'studio.collection-error/v1','code':'collection_invalid_command','generation_submitted':False,'error':'Collection name rejected (fixture)'})
                    return super().do_POST()
                return fixture.Handler.do_POST(self)
            def _json(self,status,data):
                if self.path=='/api/collections' and status==200 and flags['lose']:
                    flags['lose']=False;self.close_connection=True;self.connection.shutdown(socket.SHUT_RDWR);return
                return super()._json(status,data)
        http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=http.serve_forever,daemon=True).start();fixture.POSTS.clear()
        try:
            async with async_playwright() as pw:
                browser=await pw.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
                page=await browser.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce');page.set_default_timeout(5000)
                page.on('pageerror',lambda e:errors.append(str(e)))
                async def confirm(dialog):
                    dialogs.append(dialog.message)
                    if consent['yes']:await dialog.accept()
                    else:await dialog.dismiss()
                page.on('dialog',confirm)
                if args.inert:
                    await inert_page(page,http.server_port)
                    await page.expose_function('__collectionDigest',lambda data:list(hashlib.sha256(bytes(data)).digest()))
                    await page.evaluate("""ids=>{
                      const proto=Object.getPrototypeOf(sessionStorage);
                      Object.defineProperty(proto,'length',{get(){return this.data.size;}});
                      proto.key=function(i){return [...this.data.keys()][i]??null;};
                      let index=0;crypto.randomUUID=()=>ids[index++];
                      Object.defineProperty(crypto,'subtle',{value:{digest:async(_,raw)=>new Uint8Array(await __collectionDigest([...new Uint8Array(raw)])).buffer}});
                    }""",[str(uuid.uuid4()) for _ in range(50)])
                else:await page.goto(f'http://127.0.0.1:{http.server_port}/#assets',timeout=20000)  # cold-runner first load (#911)
                await page.wait_for_function('!!catalog && !!selected && !!assetState.workspace_id && !!window.StudioReadPoller',timeout=20000)
                await page.evaluate("""()=>{showView('assets');const poller=window.StudioReadPoller;poller.started=false;for(const lane of poller.lanes.values()){if(lane.timer!==null)poller.clearTimeout(lane.timer);lane.timer=null;}window.collectionQaInFlight=0;const original=api;api=async(path,options)=>{if(path!=='/api/collections')return original(path,options);collectionQaInFlight++;try{return await original(path,options);}finally{collectionQaInFlight--;}};}""")
                async def refresh():
                    await page.wait_for_function('!assetRefreshing');await page.evaluate('refreshAssets(true)');await page.wait_for_function('!assetRefreshing')
                async def opened(id=None):
                    # Reset independent scenarios through fixture setup, not user consent.
                    await page.evaluate("""()=>new Promise(resolve=>{const d=document.querySelector('#collectionDialog');if(!d.open){resolve();return;}d.addEventListener('close',resolve,{once:true});d.close();})""")
                    await refresh();await page.evaluate('new StudioCollectionRecovery.Journal(sessionStorage,assetState.workspace_id).reset()');await page.evaluate('id=>openCollection(id)',id)
                async def status():return await page.locator('#collectionStatus').inner_text() if await page.locator('#collectionStatus').count() else ''
                async def settled():
                    await page.wait_for_function('collectionQaInFlight===0 && !collectionSession?.busy')
                async def submit():await page.locator('#collectionForm .primary').click()
                await opened(a['id'])
                check('COL-01','The dialog is named by its visible heading',await page.locator('#collectionDialog').get_attribute('aria-labelledby')=='collectionDialogTitle')
                await page.fill('#collectionName','Unfinished title');await page.click('#cancelCollection')
                check('COL-02','Cancel retains a dirty draft when discard is declined',await page.locator('#collectionDialog').is_visible() and await page.input_value('#collectionName')=='Unfinished title' and len(dialogs)==1)
                await opened(a['id']);await page.fill('#collectionDescription','Unfinished description');dialogs.clear();await page.press('#collectionDescription','Escape')
                check('COL-03','Escape uses the same discard decision',await page.locator('#collectionDialog').is_visible() and len(dialogs)==1)
                await opened(a['id']);await page.fill('#collectionName','Current draft');await page.evaluate('id=>openCollection(id)',a['id'])
                check('COL-04','Reopening the current collection preserves edits',await page.input_value('#collectionName')=='Current draft')
                await page.evaluate('id=>openCollection(id)',b['id'])
                check('COL-05','Opening another collection respects Stay',await page.input_value('#collectionName')=='Current draft')
                await page.evaluate("openCollection('missing')")
                check('COL-06','A missing collection cannot clear the editor',await page.input_value('#collectionName')=='Current draft')
                await opened();await page.fill('#collectionName','   ');n=len(writes);await submit();await settled()
                check('COL-07','Whitespace-only names are refused before HTTP',len(writes)==n)
                await opened(a['id']);await page.fill('#collectionName','Reject this');flags['reject']=True
                async with page.expect_response(lambda r:r.url.endswith('/api/collections')) if not args.inert else _nothing():await submit()
                await settled()
                check('COL-08','Validation failure is visible inside the dialog', 'rejected' in await status() and await page.input_value('#collectionName')=='Reject this')
                await opened();await page.evaluate('id=>{assetScope="all";assetSelection=new Set([id]);renderAssets();}',aid)
                await page.fill('#collectionName','  New group  ');await page.fill('#collectionDescription','  Group description  ')
                async with page.expect_response(lambda r:r.url.endswith('/api/collections')) if not args.inert else _nothing():await submit()
                # Native response events are unavailable in inert mode; observe actual storage.
                for _ in range(100):
                    created=[c for c in store.snapshot()['collections'] if c['name']=='New group']
                    if created:break
                    await asyncio.sleep(.02)
                await settled();await refresh();new=created[0]
                check('COL-09','Create keeps the editor open without switching the library',await page.locator('#collectionDialog').is_visible() and await page.evaluate('assetScope')=='all')
                check('COL-10','Create preserves the existing selected IDs',await page.evaluate('id=>assetSelection.has(id)',aid))
                check('COL-11','Only the normalized clicked collection fields are stored',new['description']=='Group description' and writes[-1]['name'].strip()=='New group')
                check('COL-12','The confirmed create session becomes an edit session',await page.evaluate('typeof collectionSession!=="undefined" && !!collectionSession?.id'))
                # Slow save, newer input, and attempted close; no arbitrary settle sleeps.
                await opened(a['id']);await page.fill('#collectionName','First snapshot');gate.clear();n=len(writes);await submit()
                for _ in range(100):
                    if len(writes)>n:break
                    await asyncio.sleep(.02)
                check('COL-13','The Save button is disabled while its request is pending',await page.locator('#collectionForm .primary').is_disabled())
                await page.fill('#collectionDescription','Newer typing');await page.click('#cancelCollection')
                check('COL-14','Closing during an in-flight save is held',await page.locator('#collectionDialog').is_visible())
                gate.set();await settled()
                await page.wait_for_function('document.querySelector("#collectionForm .primary").disabled===false || !document.querySelector("#collectionDialog").open')
                check('COL-15','Late confirmation leaves newer typing visible and unsaved',await page.locator('#collectionDialog').is_visible() and await page.input_value('#collectionDescription')=='Newer typing' and 'unsaved' in await status())
                check('COL-16','The stored description belongs to the clicked snapshot',next(c for c in store.snapshot()['collections'] if c['id']==a['id'])['description']=='Retain this note')
                await opened();await page.fill('#collectionName','Committed but reply lost');flags['lose']=True;await submit();await settled()
                for _ in range(100):
                    if any(c['name']=='Committed but reply lost' for c in store.snapshot()['collections']):break
                    await asyncio.sleep(.02)
                check('COL-17','A dropped committed response is unconfirmed, not a safe retry', 'not confirmed' in await status() and await page.locator('#collectionForm .primary').is_disabled())
                check('COL-18','Unconfirmed create retains its draft and sends no repeat',await page.input_value('#collectionName')=='Committed but reply lost' and sum(w['name']=='Committed but reply lost' for w in writes if 'name' in w)==1)
                dialogs.clear();await page.click('#cancelCollection')
                check('COL-19','Closing uncertainty explains it cannot cancel a server change',await page.locator('#collectionDialog').is_visible() and any('server change' in d for d in dialogs))
                await opened();await page.fill('#collectionName','Do not write to replacement');Handler.studio.assets=other
                await submit();await settled();await asyncio.sleep(.05)
                check('COL-20','A server Workspace replacement is refused without foreign writes',not other.snapshot()['collections'] and 'Workspace' in await status())
                Handler.studio.assets=store
                await opened();await page.evaluate('id=>{assetScope="collection:"+id;renderAssets();}',b['id']);await page.evaluate('document.querySelector("#collectionDialog").close()');dialogs.clear()
                # The existing library Remove collection button enters the guarded dialog.
                await page.click('#deleteCollection');await settled()
                check('COL-21','Removal asks about the named collection and keeps originals',any('Other' in d and 'original' in d for d in dialogs) and any(c['id']==b['id'] for c in store.snapshot()['collections']))
                # Confirmed removal, with a separate fixture collection.
                removed=store.collection({'name':'Remove this group'});await opened(removed['id']);consent['yes']=True
                if await page.locator('#removeCollection').count():await page.click('#removeCollection');await settled()
                else:await page.evaluate('id=>{assetScope="collection:"+id;}',removed['id']);await page.evaluate('document.querySelector("#deleteCollection").onclick()')
                check('COL-22','Confirmed removal removes grouping, never original assets',not any(c['id']==removed['id'] for c in store.snapshot()['collections']) and len(store.snapshot()['assets'])==1 and hashlib.sha256(file.read_bytes()).hexdigest()==original_hash)
                # A post-write refresh must follow the captured older read, never run alongside it.
                await opened(a['id']);await page.fill('#collectionName','Post-refresh rename')
                read_gate.clear();flags.update(hold_read=True,read_captured=False)
                await page.evaluate('void refreshAssets(true)')
                for _ in range(100):
                    if flags['read_captured']:break
                    await asyncio.sleep(.02)
                assert flags['read_captured'],'Read fixture never captured the old snapshot'
                await submit();await settled();
                assert await page.evaluate('!!window.StudioReadPoller.lanes.get("assets").queued'),'Post-save read was not queued behind the captured snapshot'
                read_gate.set()
                await page.wait_for_function('!assetRefreshing && !window.StudioReadPoller.lanes.get("assets").inFlight && !window.StudioReadPoller.lanes.get("assets").queued')
                check('COL-27','A confirmed rename refreshes after an older held library read',await page.evaluate('id=>assetState.collections.find(c=>c.id===id)?.name',a['id'])=='Post-refresh rename')
                remove_late=store.collection({'name':'Delete behind old refresh'})
                await opened(remove_late['id']);await page.evaluate('id=>{assetScope="collection:"+id;renderAssets();}',remove_late['id'])
                read_gate.clear();flags.update(hold_read=True,read_captured=False)
                await page.evaluate('void refreshAssets(true)')
                for _ in range(100):
                    if flags['read_captured']:break
                    await asyncio.sleep(.02)
                assert flags['read_captured'],'Delete fixture never captured the old snapshot'
                await page.click('#removeCollection');await settled();
                assert await page.evaluate('!!window.StudioReadPoller.lanes.get("assets").queued'),'Post-delete read was not queued behind the captured snapshot'
                read_gate.set()
                await page.wait_for_function('!assetRefreshing && !window.StudioReadPoller.lanes.get("assets").inFlight && !window.StudioReadPoller.lanes.get("assets").queued')
                check('COL-28','Confirmed removal clears the obsolete view after an older held read',await page.evaluate('id=>assetScope==="all" && !assetState.collections.some(c=>c.id===id)',remove_late['id']) and await page.locator('#assetScopeTitle').inner_text()=='All assets')
                consent['yes']=False;await opened(a['id']);await page.fill('#collectionDescription','A description to keep while browsing')
                await page.set_viewport_size({'width':390,'height':1000})
                check('COL-23','The collection editor fits a 390px viewport',await page.evaluate('document.querySelector("#collectionDialog").getBoundingClientRect().right<=innerWidth && document.documentElement.scrollWidth<=innerWidth'))
                check('COL-24','Status messages use a polite atomic region',await page.locator('#collectionStatus').count()>0 and await page.locator('#collectionStatus').get_attribute('aria-live')=='polite' and await page.locator('#collectionStatus').get_attribute('aria-atomic')=='true')
                await page.screenshot(path=str(args.out/'collection-draft-390.png'))
                await page.set_viewport_size({'width':1440,'height':1000});await page.screenshot(path=str(args.out/'collection-draft-desktop.png'))
                check('COL-25','Collection operations never imply generation/install/upload',all(p['path'] in {'/api/estimate','/api/references/check'} for p in fixture.POSTS))
                check('COL-26','The full shell has no JavaScript exceptions',not errors)
                await browser.close()
        except Exception as e:failure=type(e).__name__+': '+str(e)
        finally:
            gate.set();read_gate.set();http.shutdown();http.server_close()
    report={'mode':'inert storage/transport; actual collection HTTP/SQLite' if args.inert else 'native HTTP/browser; actual collection SQLite','checks':checks,'pass':sum(c['passed'] for c in checks),'fail':sum(not c['passed'] for c in checks),'errors':errors,'execution_error':failure,'writes':writes,'fixture_posts':fixture.POSTS,'hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['app/static/workspace.js','app/static/index.html','app/workspace.py','app/static/collection-recovery.js']}}
    module=ROOT/'app/static/collection-editor.js'
    if module.exists():report['hashes']['app/static/collection-editor.js']=hashlib.sha256(module.read_bytes()).hexdigest()
    (args.out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['mode','pass','fail','errors','execution_error']},indent=2))
    if failure or errors or len(checks)!=28 or (report['fail'] and not args.baseline):raise SystemExit(1)

class _nothing:
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--inert',action='store_true');p.add_argument('--baseline',action='store_true');asyncio.run(exercise(p.parse_args()))
