"""Actual Library navigation over disposable plans and synthetic retained receipts."""
import argparse
import asyncio
import copy
import json
import os
from pathlib import Path
import shutil
import threading
from urllib.parse import urlsplit

from playwright.async_api import async_playwright, expect
from browser_ports import browser_server
import studio_browser_smoke as shell
from test_native_export_history import NativeExportHistoryTests, server


async def run(out):
    out.mkdir(parents=True,exist_ok=True)
    checks=[];errors=[];requests=[];browser=None
    def check(name,value):
        checks.append({'name':name,'passed':bool(value)});print(name,bool(value),flush=True);assert value,name
    case=NativeExportHistoryTests();case.setUp()
    prepared=case.prepare('ora');completed=case.prepare('atlas');failed=case.prepare('ora')
    expected=b'Synthetic retained export fixture; no exporter executed.'
    case.retained(completed,body=expected);case.retained(failed,status='failed',body=b'{"fixture":"failed attempt"}',name='native/receipt.json')
    other=case.studio.import_image('unrelated.png','image/png',case.studio.assets.file(case.asset['id']).read_bytes())['asset']
    unrelated=case.prepare(ids=[other['id']])
    for patch in reversed(case.fixture.patches):patch.stop()
    studio=case.studio;store=studio.assets
    before=[copy.deepcopy(studio.production._get(p['id'])) for p in (prepared,completed,failed,unrelated)]
    asset_before=copy.deepcopy(store.get(case.asset['id']))
    gate={'pause':False};entered=threading.Event();release=threading.Event()

    class Base(server.Handler):
        workspace_id=case.workspace
        json=shell.Handler.json
        def log_message(self,*args):pass
        def _safe_host(self):return self.headers.get('Host')=='127.0.0.1:'+str(self.server.server_port)
        def _safe_mutation(self):return self._safe_host() and self.headers.get('Origin')=='http://'+self.headers.get('Host','')
        def do_GET(self):
            path=urlsplit(self.path).path
            if path.endswith('/native-exports') and gate['pause']:
                gate['pause']=False;entered.set()
                if not release.wait(15):raise RuntimeError('Synthetic history delay timed out')
            if path.startswith(('/api/assets/','/api/production')) or path=='/api/looks':return super().do_GET()
            if path=='/api/workspace':return self._json(200,store.snapshot(privacy=self.headers.get('X-Studio-Privacy','regular')))
            return shell.Handler.do_GET(self)
        def do_POST(self):
            if self.path in ('/api/estimate','/api/references/check'):return shell.Handler.do_POST(self)
            return self._json(403,{'error':'Export discovery fixture refuses mutations'})
    Base.studio=studio
    class Handler(server.extend_handler(Base)):
        def do_GET(self):requests.append(('GET',self.path));return super().do_GET()
        def do_POST(self):requests.append(('POST',self.path));return super().do_POST()
    http=browser_server(Handler);thread=threading.Thread(target=http.serve_forever,kwargs={'poll_interval':.01},daemon=True);thread.start()
    origin='http://127.0.0.1:'+str(http.server_port)
    try:
        async with async_playwright() as pw:
            browser=await pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None,headless=True)
            context=await browser.new_context(viewport={'width':1440,'height':900},reduced_motion='reduce',accept_downloads=True)
            page=await context.new_page();page.set_default_timeout(10000);page.on('pageerror',lambda e:errors.append(str(e)))
            async def open_asset(identifier):
                await page.locator('#assetGrid button.asset-open[data-asset-open="'+identifier+'"]').click()
                await expect(page.locator('#assetDialog')).to_be_visible()
            async def expand():
                await page.locator('#assetNativeExports>summary').focus();await page.keyboard.press('Enter')
                await expect(page.locator('#assetExportsList>li')).to_have_count(3)
            await page.goto(origin+'/#assets',timeout=25000);await open_asset(case.asset['id'])
            check('Opening a picture does not fetch history or start an export',not any('/native-exports' in p for _,p in requests))
            await page.locator('#assetNotes').fill('Unsaved picture notes stay here')
            await expand();content=await page.locator('#assetNativeExports').inner_text()
            check('Keyboard expansion distinguishes prepared completed and failed plans',all(word in content for word in ('Prepared','Completed','Failed','No produced files recorded.')))
            check('An unrelated source plan is absent',await page.locator('#assetExportsList a[href*="plan='+unrelated['id']+'"]').count()==0)
            await page.locator('#assetExportsList>li').first.locator('details>summary').click()
            check('Recorded source and plan hashes remain inspectable',case.asset['sha256'] in await page.locator('#assetExportsList').inner_text())
            await page.locator('#assetNativeExports').scroll_into_view_if_needed();await page.screenshot(path=str(out/'exports-wide.png'))
            link=page.locator('#assetExportsList a[href*="plan='+completed['id']+'"]')
            async with page.expect_popup() as opened:await link.click()
            plan_page=await opened.value;await expect(plan_page.locator('#productionDetail')).to_contain_text(completed['name'])
            check('Library opens the exact retained plan in a new tab',await plan_page.evaluate('productionId')==completed['id'])
            check('Plan navigation preserves unsaved source notes',await page.input_value('#assetNotes')=='Unsaved picture notes stay here')
            await plan_page.screenshot(path=str(out/'linked-plan-wide.png'));await plan_page.close()
            async with page.expect_download() as downloading:await page.locator('#assetExportsList a[download]').filter(has_text='export.zip').click()
            download=await downloading.value;target=out/'retained-file.bin';await download.save_as(target)
            check('Download returns exactly the retained fixture receipt bytes',target.read_bytes()==expected)
            await page.locator('#assetNotes').fill('');await page.reload();await open_asset(case.asset['id']);await expand()
            check('Reload discovers the same three recorded plans',await page.locator('#assetExportsList>li').count()==3)
            await page.set_viewport_size({'width':390,'height':844});await page.locator('#assetNativeExports').scroll_into_view_if_needed()
            await page.locator('#assetExportsList>li').first.locator('details>summary').click()
            check('Narrow history has no horizontal overflow',await page.locator('#assetDialog').evaluate('(n)=>n.scrollWidth<=n.clientWidth+1'))
            await page.locator('#assetExportsList a').first.focus()
            check('Narrow plan link is keyboard reachable',await page.locator('#assetExportsList a').first.evaluate('(n)=>n===document.activeElement'))
            await page.screenshot(path=str(out/'exports-narrow.png'))
            await page.locator('#assetExportsList>li').last.scroll_into_view_if_needed();await page.screenshot(path=str(out/'exports-narrow-last.png'))
            gate['pause']=True;await page.locator('#assetExportsRefresh').click()
            check('Delayed history read entered the fixture',await asyncio.to_thread(entered.wait,3))
            await page.locator('#closeAssetDialog').click();await open_asset(other['id']);release.set()
            await expect(page.locator('#assetExportsList')).to_be_empty()
            check('A late response cannot populate a different picture',await page.locator('#assetExportsList').inner_text()=='')
            check('No production or review mutation was requested',not any(m=='POST' and urlsplit(p).path not in ('/api/estimate','/api/references/check','/api/assets/selection') for m,p in requests))
            check('Saved plans and source metadata are unchanged',[studio.production._get(p['id']) for p in (prepared,completed,failed,unrelated)]==before and store.get(case.asset['id'])==asset_before)
            check('No browser JavaScript errors',not errors)
            await context.close();await browser.close();browser=None
    finally:
        release.set()
        if browser:await browser.close()
        http.shutdown();http.server_close();thread.join(timeout=10)
        (out/'result.json').write_text(json.dumps({'checks':checks,'browser_errors':errors,'requests':requests,
            'scope':'Synthetic prepared plans and retained receipt bytes; no exporter, native application, model or art acceptance.'},indent=2),encoding='utf-8')
        case.doCleanups()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    asyncio.run(run(parser.parse_args().out))
