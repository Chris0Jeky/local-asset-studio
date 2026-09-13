"""Reload recovery QA over the actual Studio shell and an ephemeral synthetic API.

Default mode uses native browser navigation for hosted CI. Local policy-restricted
machines may run only with --inert, which injects storage and transport into a
fresh document for each reload; that mode is explicitly not native storage proof.
No Studio process, SQLite store, generation endpoint or backend endpoint is used.
"""
import argparse
import asyncio
import copy
import hashlib
import json
import shutil
import threading
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import async_playwright
import asset_detail_browser as detail
import studio_browser_smoke as fixture

ROOT=Path(__file__).resolve().parents[1]
STATIC=ROOT/'app/static'
RECOVERY_KEY='studio.asset-recovery.v1.detail'


class Handler(detail.Handler):
    """Add the receipt observation endpoint to the in-memory detail fixture."""
    def do_GET(self):
        path=urlsplit(self.path).path
        if path.startswith('/api/assets/commands/') and len(path.split('/'))==5:
            request_id=path.split('/')[4]
            self.state.receipt_reads.append(request_id)
            return self.json(self.state.receipts.get(request_id,{'status':'unknown','request_id':request_id}))
        return super().do_GET()


async def run(args):
    args.out.mkdir(parents=True,exist_ok=True)
    state=detail.State();state.receipt_reads=[];Handler.state=state
    fixture.ASSETS[:]=copy.deepcopy(detail.BASE_ASSETS);fixture.POSTS.clear()
    server=fixture.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    checks=[];errors=[];browser=None
    async def check(case,expectation,passed):
        print(case,passed,flush=True)
        checks.append({'id':case,'expectation':expectation,'status':'pass' if passed else 'fail'})
    async def ready(page):
        await page.wait_for_function('!!catalog && !!selected')
        await page.evaluate("showView('assets')")
        await page.wait_for_selector('[data-asset-open="asset-0"]')
    try:
        async with async_playwright() as pw:
            browser=await pw.chromium.launch(executable_path=args.chromium or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
            context=await browser.new_context(viewport={'width':1440,'height':1100},reduced_motion='reduce')
            async def new_page(saved_session=None):
                page=await context.new_page();page.set_default_timeout(6000)
                page.on('pageerror',lambda error:errors.append(str(error)))
                if args.inert:await detail.inert_page(page,server.server_port,saved_session)
                else:await page.goto(f'http://127.0.0.1:{server.server_port}/#assets')
                await ready(page);return page
            async def accept_dialog(dialog):await dialog.accept()
            async def open_asset(page,identifier):
                # Explicitly leave this synthetic scenario through the editor's
                # own draft-discard consent; closing first adds a second prompt.
                page.on('dialog',accept_dialog)
                try:await page.evaluate('id=>openAsset(id)',identifier)
                finally:page.remove_listener('dialog',accept_dialog)
                await page.wait_for_function('id=>document.querySelector("#assetDialog").open && activeAsset?.id===id',arg=identifier)
            async def unknown(page):
                await page.wait_for_function('!assetDetailBusy && !!assetDetailPending')
            async def saved(page):
                await page.wait_for_function('!assetDetailBusy && !assetDetailPending && !assetDetailConflict')
            async def reload(page,case):
                before=len(state.writes);before_reads=len(state.receipt_reads)
                if args.inert:
                    retained=await page.evaluate('(key)=>sessionStorage.getItem(key)',RECOVERY_KEY)
                    await page.close()
                    page=await new_page({RECOVERY_KEY:retained} if retained is not None else {})
                else:
                    await page.reload();await ready(page)
                await check(case,'Reload sends no metadata POST or receipt check',len(state.writes)==before and len(state.receipt_reads)==before_reads)
                return page
            async def lose_next_reply(page,wire):
                if args.inert:
                    await page.evaluate("""() => {
                      const prior=window.fetch;let lose=true;window.__qaWirePosts=[];
                      window.fetch=async(path,options={})=>{if(path==='/api/assets/update')window.__qaWirePosts.push(String(options.body||''));const reply=await prior(path,options);if(lose&&path==='/api/assets/update'){lose=false;throw new TypeError('Synthetic reply loss after fixture commit');}return reply;};
                    }""")
                    return
                async def route(request):
                    if request.request.method=='POST' and request.request.url.endswith('/api/assets/update'):
                        wire.append(request.request.post_data or '')
                        if not wire:
                            raise AssertionError('missing browser request body')
                        if len(wire)==1:
                            await request.fetch();await request.abort('connectionfailed');return
                    await request.continue_()
                await page.route('**/api/assets/update',route)
            async def observe_posts(page,wire):
                if args.inert:
                    await page.evaluate("""() => {const prior=window.fetch;window.__qaWirePosts=[];window.fetch=async(path,options={})=>{if(path==='/api/assets/update')window.__qaWirePosts.push(String(options.body||''));return prior(path,options);};}""")
                    return
                async def route(request):
                    if request.request.method=='POST' and request.request.url.endswith('/api/assets/update'):wire.append(request.request.post_data or '')
                    await request.continue_()
                await page.route('**/api/assets/update',route)
            async def captured(page,wire):
                return (await page.evaluate('window.__qaWirePosts||[]')) if args.inert else wire

            page=await new_page()
            await open_asset(page,'asset-0')
            first_wire=[];await lose_next_reply(page,first_wire)
            await page.fill('#assetNotes','Committed snapshot whose reply was lost')
            await page.click('#saveAssetDetails');await unknown(page)
            first_body=await page.evaluate('assetDetailPending.body')
            await page.fill('#assetNotes','Newer typing after the lost reply')
            await check('RELOAD-01','Synthetic handler committed the snapshot before its reply was lost',fixture.ASSETS[0]['notes']=='Committed snapshot whose reply was lost')
            page=await reload(page,'RELOAD-02')
            await check('RELOAD-03','Reload presents recovery without opening the editor',await page.locator('[data-asset-recover-open]').count()==1 and not await page.locator('#assetDialog').is_visible())
            await page.click('[data-asset-recover-open]');await unknown(page)
            await check('RELOAD-04','Review restores newer typing with the original opened revision',await page.input_value('#assetNotes')=='Newer typing after the lost reply' and await page.evaluate('activeAsset.metadata_revision')==0)
            before=len(state.writes);before_reads=len(state.receipt_reads);await page.click('[data-asset-save-check]');await saved(page)
            await check('RELOAD-05','Receipt check uses GET and sends zero metadata POSTs',len(state.writes)==before and len(state.receipt_reads)==before_reads+1)
            await check('RELOAD-06','Receipt confirmation preserves newer typing as a draft',await page.input_value('#assetNotes')=='Newer typing after the lost reply' and await page.evaluate('assetDetailDirty()'))
            if not args.inert:await page.unroute('**/api/assets/update')

            await open_asset(page,'asset-1')
            retry_wire=[];await lose_next_reply(page,retry_wire)
            await page.fill('#assetNotes','Retry this exact snapshot')
            await page.click('#saveAssetDetails');await unknown(page)
            retry_body=await page.evaluate('assetDetailPending.body');retry_id=await page.evaluate('assetDetailPending.command.request_id')
            if args.inert:retry_wire=await captured(page,retry_wire)
            page=await reload(page,'RELOAD-07');await page.click('[data-asset-recover-open]');await unknown(page)
            await check('RELOAD-08','Reload retains exact pending request bytes and ID',await page.evaluate('assetDetailPending.body')==retry_body and await page.evaluate('assetDetailPending.command.request_id')==retry_id)
            if args.inert:await observe_posts(page,retry_wire)
            await page.click('[data-asset-save-retry]');await saved(page)
            if args.inert:retry_wire+=await captured(page,[])
            await check('RELOAD-09','Explicit retry sends the original body and request ID',len(retry_wire)>=2 and retry_wire[0]==retry_wire[-1] and state.writes[-1]==json.loads(retry_body))
            await check('RELOAD-10','Duplicate exact retry has one synthetic metadata effect',fixture.ASSETS[1]['metadata_revision']==1)
            await page.fill('#assetNotes','A later explicit save has new intent')
            await page.click('#saveAssetDetails');await saved(page)
            later=state.writes[-1]
            await check('RELOAD-11','Later explicit save uses a new ID and current revision',later['request_id']!=retry_id and later['expected_revisions']=={'asset-1':1} and fixture.ASSETS[1]['metadata_revision']==2)
            if not args.inert:await page.unroute('**/api/assets/update')

            await open_asset(page,'asset-2')
            trash_wire=[];await lose_next_reply(page,trash_wire)
            await page.fill('#assetNotes','Typing before a lost Trash reply')
            page.once('dialog',accept_dialog)
            await page.click('#assetTrash');await unknown(page)
            await page.fill('#assetNotes','Newer typing after the lost Trash reply')
            page=await reload(page,'RELOAD-12');await page.click('[data-asset-recover-open]');await unknown(page)
            before=len(state.writes);await page.click('[data-asset-save-check]');await saved(page)
            await check('RELOAD-13','Recovered Trash receipt keeps newer typing and sends no POST',len(state.writes)==before and await page.locator('#assetDialog').is_visible() and await page.input_value('#assetNotes')=='Newer typing after the lost Trash reply' and await page.evaluate('activeAsset.trashed_at')==123 and await page.evaluate('assetDetailDirty()'))

            await open_asset(page,'asset-3')
            await page.fill('#assetNotes','Unsent draft survives a reload')
            before=len(state.writes);page=await reload(page,'RELOAD-14')
            await page.click('[data-asset-recover-open]')
            await check('RELOAD-15','Unsent draft reload remains local and uses zero POSTs',len(state.writes)==before and await page.input_value('#assetNotes')=='Unsent draft survives a reload' and await page.evaluate('activeAsset.metadata_revision')==0)
            await page.set_viewport_size({'width':1440,'height':1100})
            await check('RELOAD-16','Desktop recovery view has no horizontal overflow',await page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            await page.screenshot(path=str(args.out/'recovery-desktop.png'),full_page=True)
            await page.set_viewport_size({'width':390,'height':1100})
            await check('RELOAD-17','390px recovery view has no horizontal overflow',await page.evaluate('document.documentElement.scrollWidth<=innerWidth && document.querySelector("#assetDialog").scrollWidth<=document.querySelector("#assetDialog").clientWidth'))
            await page.screenshot(path=str(args.out/'recovery-390.png'),full_page=True)
            await check('RELOAD-18','No generation or backend mutation is sent',all(post['path'] in {'/api/estimate','/api/references/check'} for post in fixture.POSTS))
            await check('RELOAD-19','No complete-shell JavaScript exception occurred',not errors)
            await browser.close();browser=None
    finally:
        if browser:await browser.close()
        state.gate.set();state.diagnostic_gate.set();server.shutdown();server.server_close();thread.join(2)
        receipt={'scope':'Actual Studio HTML, scripts and CSS with an ephemeral in-memory State/Handler fixture. No Studio runtime, SQLite, generation, backend or artwork evidence.',
                 'mode':'inert: injected storage and document recreation; not native storage/origin/network proof' if args.inert else 'native browser reload against ephemeral synthetic HTTP',
                 'workspace_js_sha256':hashlib.sha256((STATIC/'workspace.js').read_bytes()).hexdigest(),
                 'asset_recovery_js_sha256':hashlib.sha256((STATIC/'asset-recovery.js').read_bytes()).hexdigest(),
                 'checks':checks,'errors':errors,'pass':sum(c['status']=='pass' for c in checks),'fail':sum(c['status']=='fail' for c in checks),
                 'metadata_posts':state.writes,'other_posts':fixture.POSTS}
        (args.out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps({key:receipt[key] for key in ['mode','pass','fail','errors']},indent=2))
    if any(check['status']=='fail' for check in checks):raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--inert',action='store_true');parser.add_argument('--chromium')
    asyncio.run(run(parser.parse_args()))
