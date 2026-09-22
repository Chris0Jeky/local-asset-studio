"""Read-only recovery UI over real temporary SQLite receipts and lifecycle changes.

Native by default. --inert explicitly substitutes origin/storage/crypto/locks and
browser transport; it proves component behavior, not native browser isolation.
Setup mutations are performed by the fixture's Workspace service, never by the
inspector. Every browser metadata/model mutation is counted and must remain zero.
"""
import argparse
import asyncio
import hashlib
import json
import shutil
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


async def exercise(args):
    args.out.mkdir(parents=True, exist_ok=True)
    checks, errors, metadata_posts, observation_reads = [], [], [], []
    gate, started = threading.Event(), threading.Event();gate.set()
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary);store=production.AssetWorkspace(root)
        source=root/'synthetic.png'
        with Image.new('RGB',(32,48),(110,120,130)) as image:image.save(source)
        source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
        ids=[store.register({'id':f'lifecycle-{i}','preset_name':'Synthetic lifecycle QA',
                            'outputs':[{'filename':source.name,'media_type':'image'}]},0,source) for i in range(12)]
        workspace=store.snapshot()['workspace_id']
        def command(selected,action,**fields):
            return {'ids':selected,'action':action,'workspace_id':workspace,'request_id':uuid.uuid4().hex,
                    'expected_revisions':{i:store.get(i)['metadata_revision'] for i in selected},**fields}
        group=store.collection({'name':'Historical collection — synthetic'})
        bulk=command(ids,'add_collection',collection_id=group['id']);store.update(bulk)
        library={'version':2,'workspace_id':workspace,'operation':{'command':bulk,'body':json.dumps(bulk,ensure_ascii=False,indent=2)},'selection':ids}
        before=store.metadata(ids[2],workspace)
        form={'title':before['title'],'tags':', '.join(before['tags']),'review':before['review'],'notes':before['notes']}
        trash=command([ids[2]],'trash');store.update(trash)
        detail={'version':2,'workspace_id':workspace,'id':ids[2],'metadata':before,'baseline':form,
                'draft':{**form,'notes':'Synthetic local draft <img src=x onerror="window.__injected=1"> '+('x'*7000)},
                'operation':{'command':trash,'body':json.dumps(trash,indent=2),'kind':'trash','snapshot':form},'conflict':None}
        store.update(command([ids[2]],'restore'))
        store.update(command([ids[1]],'trash'))
        store.collection({'id':group['id'],'action':'delete'})
        with store.connection() as db:db.execute('DELETE FROM assets WHERE id=?',(ids[0],))
        frozen=store.snapshot()

        class Handler(production.extend_handler(production.Handler)):
            studio=SimpleNamespace(assets=store)
            json=fixture.Handler.json
            def do_GET(self):
                if self.path.startswith('/api/assets/recovery-observation?'):
                    observation_reads.append(self.path);started.set()
                    if not gate.wait(10):return self._json(503,{'error':'Synthetic observation deadline'})
                if self.path=='/api/workspace' or self.path.startswith('/api/assets/'):
                    return super().do_GET()
                return fixture.Handler.do_GET(self)
            def do_POST(self):
                if self.path=='/api/assets/update':
                    metadata_posts.append(self.path)
                    return super().do_POST()
                return fixture.Handler.do_POST(self)
        http=ThreadingHTTPServer(('127.0.0.1',8191),Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start();fixture.POSTS.clear()
        failure=None
        def check(name,ok):
            checks.append({'id':name,'passed':bool(ok)});print(name,bool(ok),flush=True)
            if not ok:raise AssertionError(name)
        try:
            async with async_playwright() as pw:
                browser=await pw.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
                context=await browser.new_context(viewport={'width':1280,'height':1000},reduced_motion='reduce',accept_downloads=True)
                try:
                    async def new_page():
                        page=await context.new_page();page.set_default_timeout(7000)
                        page.on('pageerror',lambda e:errors.append(str(e)))
                        async def accept(dialog):await dialog.accept()
                        page.on('dialog',accept)
                        if args.inert:
                            await inert_page(page,8191)
                            await page.expose_function('__lifecycleHash',lambda data:list(hashlib.sha256(bytes(data)).digest()))
                            await page.evaluate('''()=>{
                              Object.defineProperty(window,'crypto',{value:{getRandomValues:crypto.getRandomValues.bind(crypto),subtle:{digest:async(n,data)=>new Uint8Array(await __lifecycleHash(Array.from(data))).buffer}}});
                              let tail=Promise.resolve();Object.defineProperty(navigator,'locks',{value:{request:(n,o,fn)=>{const p=tail.then(fn);tail=p.catch(()=>{});return p;}}});
                              assetShelfStore=StudioAssetRecoveryShelf.create({storage:()=>localStorage,locks:()=>navigator.locks,crypto});
                              assetShelfSession=StudioAssetRecoveryShelfSession.create({journal:assetRecovery,store:assetShelfStore,crypto,onStatus:assetShelfStatus});
                            }''')
                        else:await page.goto('http://127.0.0.1:8191/#assets')
                        await page.wait_for_function('!!catalog && !!selected')
                        await page.evaluate("showView('assets')")
                        await page.wait_for_function('assetState.assets.length===11')
                        await page.evaluate('''()=>{window.__lensCalls=[];const original=api;api=async(url,options)=>{const row={url,done:false};__lensCalls.push(row);try{return await original(url,options);}finally{row.done=true;}};}''')
                        return page
                    async def seed(page,local=detail):
                        await page.evaluate('''data=>{
                          assetRecovery.write('detail',data.detail);assetRecovery.write('library',data.library);
                          assetRetainedDetail=assetRecovery.read('detail');assetLibraryPending={...data.library.operation,selection:data.library.selection};renderLibraryRecovery();
                        }''',{'detail':local,'library':library})
                    async def shelf(page):
                        await page.click('#openAssetRecoveryShelf');await page.wait_for_function('!assetShelfReading')
                    async def inspect(page,slot):
                        await page.locator('[data-recovery-observe-slot="'+slot+'"]').focus()
                        await page.keyboard.press('Enter')
                        try:
                            await page.wait_for_function("document.querySelector('#assetLifecycleInspection [role=status]').textContent.startsWith('Read-only inspection complete')")
                        except Exception:
                            print(await page.locator('#assetLifecycleInspection').inner_text(), flush=True)
                            raise
                    page=await new_page()
                    check('LIFE-01 inspector is installed but page load performs no observation',await page.locator('#assetLifecycleInspection').count()==1 and not observation_reads)
                    await seed(page);await shelf(page)
                    raw=await page.evaluate("sessionStorage.getItem(StudioAssetRecovery.PREFIX+'library')")
                    await inspect(page,'library')
                    text=await page.locator('#assetLifecycleResults').inner_text()
                    check('LIFE-02 mixed selection accounts for all twelve retained IDs',await page.locator('#assetLifecycleResults article').count()==12 and all(i in text for i in ids))
                    check('LIFE-03 missing, trashed and active states are distinct',all(s in text for s in ['Missing now','In Trash now','Active now']))
                    check('LIFE-04 historical membership does not recreate its deleted collection','Confirmed historical request' in text and 'Target collection is missing' in text)
                    check('LIFE-05 inspection preserves exact pending journal bytes',await page.evaluate("sessionStorage.getItem(StudioAssetRecovery.PREFIX+'library')")==raw and not metadata_posts)
                    check('LIFE-06 keyboard action retains logical focus after receipt delivery',await page.evaluate("document.activeElement.id==='assetLifecycleTitle'"))
                    await inspect(page,'detail');text=await page.locator('#assetLifecycleResults').inner_text()
                    check('LIFE-07 restored current state is separate from historical Trash receipt','observed as restored' in text and 'Confirmed historical request' in text)
                    check('LIFE-08 review text is inert data',await page.evaluate('window.__injected===undefined') and await page.locator('#assetLifecycleInspection img').count()==0)
                    async with page.expect_download() as info:await page.click('#assetLifecycleExport')
                    download=await info.value;exported=json.loads(Path(await download.path()).read_text(encoding='utf-8'))
                    check('LIFE-09 export retains exact command and labels its observation',exported['record']['payload']['operation']['body']==detail['operation']['body'] and exported['format']=='studio.asset-recovery-inspection/v1')
                    await page.set_viewport_size({'width':390,'height':1000});await page.evaluate("document.documentElement.style.zoom='2'")
                    await page.locator('#assetLifecycleRefresh').focus();await page.keyboard.press('Tab')
                    check('LIFE-10 narrow CSS-200-percent layout preserves accessible actions',await page.evaluate("(()=>{const d=document.querySelector('#assetRecoveryShelfDialog'),b=document.activeElement;return b.id==='assetLifecycleExport'&&b.getBoundingClientRect().right<=innerWidth+1&&d.scrollWidth<=d.clientWidth+1&&d.getBoundingClientRect().right<=innerWidth+1;})()"))
                    await page.screenshot(path=str(args.out/'lifecycle-390-css200.png'))
                    await page.evaluate("document.documentElement.style.zoom='1'");await page.set_viewport_size({'width':1280,'height':1000})
                    gate.clear();started.clear();await page.click('#assetLifecycleRefresh')
                    if not await asyncio.to_thread(started.wait,5):raise TimeoutError('Held read did not reach the fixture')
                    await page.keyboard.press('Escape')
                    check('LIFE-11 Escape returns focus to the shelf launcher',await page.evaluate("document.activeElement.id==='openAssetRecoveryShelf'"))
                    await page.evaluate('id=>openAsset(id)',ids[2]);await page.fill('#assetNotes','Newer typing while an older read is held')
                    gate.set();await page.wait_for_function('__lensCalls.every(c=>c.done)')
                    check('LIFE-12 closed inspection cannot steal focus or replace newer typing',await page.evaluate("document.activeElement.id==='assetNotes'") and await page.input_value('#assetNotes')=='Newer typing while an older read is held' and not await page.locator('#assetLifecycleInspection').is_visible())
                    other=await new_page();other_detail=json.loads(json.dumps(detail));other_detail['draft']['notes']='Other tab local viewpoint'
                    await seed(other,other_detail);await shelf(other);await inspect(other,'detail')
                    check('LIFE-13 two page-local drafts remain independent',await page.input_value('#assetNotes')=='Newer typing while an older read is held' and 'Other tab local viewpoint' in await other.locator('#assetLifecycleInspection').inner_text())
                    await other.close()
                    await page.click('#closeAssetDialog');await shelf(page)
                    foreign=await page.evaluate('''async payload=>{
                      const p=structuredClone(payload),w='2'.repeat(32);p.workspace_id=w;p.metadata.workspace_id=w;p.operation.command.workspace_id=w;p.operation.body=JSON.stringify(p.operation.command);
                      const r=await StudioAssetRecoveryShelf.seal('detail',p,{id:'f'.repeat(32),created_at:1,updated_at:1,generation:1},crypto);
                      await assetShelfStore.importRecords([r]);return r.id;
                    }''',detail)
                    await page.click('#assetShelfRefresh');await page.wait_for_function('!assetShelfReading');count=len(observation_reads)
                    check('LIFE-14 foreign shelf record cannot read another Workspace',await page.locator('[data-shelf-observe="'+foreign+'"]').is_disabled() and len(observation_reads)==count)
                    unknown=json.loads(json.dumps(library));unknown['operation']['command']['request_id']=uuid.uuid4().hex;unknown['operation']['body']=json.dumps(unknown['operation']['command'],indent=2)
                    await page.evaluate("v=>assetRecovery.write('library',v)",unknown);await inspect(page,'library')
                    check('LIFE-15 unknown stays unknown without replay','Receipt unknown' in await page.locator('#assetLifecycleResults').inner_text() and not metadata_posts)
                    check('LIFE-16 inspector has no mutation controls',await page.locator('#assetLifecycleInspection button').all_text_contents()==['Read receipt and current state again','Export this inspection'])
                    check('LIFE-17 inspection, export and cancellation leave SQLite and media unchanged',store.snapshot()==frozen and hashlib.sha256(source.read_bytes()).hexdigest()==source_hash and not metadata_posts)
                    check('LIFE-18 no generation or unrelated write from browser',all(p['path']=='/api/estimate' for p in fixture.POSTS))
                    check('LIFE-19 no JavaScript exceptions',not errors)
                finally:
                    gate.set();await browser.close()
        except Exception as error:failure=error
        finally:
            gate.set();http.shutdown();http.server_close();thread.join(timeout=5)
        (args.out/'receipt.json').write_text(json.dumps({'mode':'inert substitutions; NOT native origin/storage/crypto/locks proof' if args.inert else 'native Chromium and temporary SQLite',
            'fixture':'Historical commands committed through Workspace service; inspector browser writes must be zero',
            'checks':checks,'errors':errors,'metadata_posts':len(metadata_posts),'observations':len(observation_reads),'failure':str(failure) if failure else None},indent=2),encoding='utf-8')
        if failure:raise failure


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inert',action='store_true');parser.add_argument('--out',type=Path,default=Path('.runtime/asset-recovery-lifecycle'))
    asyncio.run(exercise(parser.parse_args()))
