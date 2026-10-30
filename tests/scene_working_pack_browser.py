"""Shipped Scene briefs UI downloads real ZIP bytes from disposable HTTP/SQLite.

Synthetic files prove packaging, never media, licence or native-tool acceptance.
"""
import argparse
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import threading
from urllib.parse import urlsplit
import zipfile

from playwright.async_api import async_playwright
from browser_ports import browser_server
import studio_browser_smoke as shell
from test_scene_working_pack import SceneWorkingPackTests, server


async def run(out):
    out.mkdir(parents=True, exist_ok=True)
    checks = []; errors = []; requests = []; downloads = []; browser = None
    def check(name, value):
        checks.append({'name':name, 'passed':bool(value)})
        print(name, bool(value), flush=True); assert value, name
    case = SceneWorkingPackTests(); case.setUp(); payload = case.pack_fixture(); case.start.stop()
    studio = case.s; store = case.store; scope = case.workspace; before = copy.deepcopy(store.card(payload['id']))
    assets_before = {identifier:store.get(identifier) for identifier in case.expected}; jobs_before = copy.deepcopy(studio.jobs)
    transfer = {'delay':False}; entered = threading.Event(); release = threading.Event()

    class Base(server.Handler):
        workspace_id = scope
        json = shell.Handler.json
        def log_message(self, *args): pass
        def _safe_host(self): return self.headers.get('Host') == '127.0.0.1:' + str(self.server.server_port)
        def _safe_mutation(self): return self._safe_host() and self.headers.get('Origin') == 'http://' + self.headers.get('Host','')
        def _local_file(self, *args, **kwargs):
            if self.path.startswith('/api/exports/') and transfer['delay']:
                transfer['delay'] = False; entered.set()
                if not release.wait(15): raise RuntimeError('Synthetic transfer release timed out')
            return super()._local_file(*args, **kwargs)
        def do_GET(self):
            path = urlsplit(self.path).path
            if path.startswith(('/api/briefs','/api/assets/','/api/exports/')) or path == '/api/looks': return super().do_GET()
            if path == '/api/workspace': return self._json(200, store.snapshot(privacy=self.headers.get('X-Studio-Privacy','regular')))
            return shell.Handler.do_GET(self)
        def do_POST(self):
            if self.path.startswith('/api/briefs'): return super().do_POST()
            if self.path in ('/api/estimate','/api/references/check'): return shell.Handler.do_POST(self)
            return self._json(403, {'error':'The working pack fixture refuses unrelated writes'})
    Base.studio = studio
    class Handler(server.extend_handler(Base)):
        def do_GET(self): requests.append(('GET',self.path)); return super().do_GET()
        def do_POST(self): requests.append(('POST',self.path)); return super().do_POST()
    http = browser_server(Handler)
    thread = threading.Thread(target=http.serve_forever, kwargs={'poll_interval':.01}, daemon=True); thread.start()
    origin = 'http://127.0.0.1:' + str(http.server_port)
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None, headless=True)
            context = await browser.new_context(viewport={'width':1440,'height':1080}, reduced_motion='reduce', accept_downloads=True)
            page = await context.new_page(); page.set_default_timeout(10000)
            page.on('pageerror', lambda error:errors.append(str(error))); page.on('download', lambda download:downloads.append(download))
            page.on('dialog', lambda dialog:dialog.accept())
            async def action(name): await page.locator('#briefsView [data-action="'+name+'"]').click()
            async def idle(): await page.wait_for_function("!!document.querySelector('[data-action=workingPack]') && !document.querySelector('[data-action=workingPack]').disabled")
            async def status(text): await page.wait_for_function("text=>document.querySelector('#briefStatus')?.textContent.includes(text)", arg=text)
            await page.goto(origin+'/#briefs?id='+payload['id'], timeout=25000); await idle()
            await page.locator('[data-action=workingPack]').focus()
            check('Working pack action has a keyboard focus target', await page.locator('[data-action=workingPack]').evaluate('(el)=>el===document.activeElement'))
            async with page.expect_download() as pending:
                await page.keyboard.press('Enter')
            downloaded = await pending.value; destination = out / downloaded.suggested_filename; await downloaded.save_as(destination)
            await idle(); await status('Working pack downloaded')
            check('Browser downloads a portable named ZIP', destination.name == 'Lantern-Marsh-working-pack.zip' and await downloaded.failure() is None)
            with zipfile.ZipFile(destination) as archive:
                manifest = json.loads(archive.read('manifest.json')); brief = manifest['brief']
                check('Downloaded brief records exact saved identity and revision', (brief['id'],brief['revision'],brief['workspace_id']) == (payload['id'],0,scope))
                check('Downloaded direction roles criteria and empty slot are exact', brief['direction'] == before['body']['direction'] and all(brief['slots'][key] == {field:slot[field] for field in ('intent','criteria','selected')} for key,slot in before['body']['slots'].items()))
                check('Duplicate role selection stores four source files once', len(manifest['assets']) == 4 and len([name for name in archive.namelist() if name.startswith('assets/')]) == 4)
                check('Downloaded source bytes and hashes match independent fixture inputs', all(archive.read(asset['file']) == case.expected[asset['id']] and hashlib.sha256(archive.read(asset['file'])).hexdigest() == asset['sha256'] for asset in manifest['assets']))
                recipes = [asset['recipe'] for asset in manifest['assets'] if asset['recipe']]
                check('Available recipe bytes are hashed and absent recipes explicit', len(recipes) == 1 and sum(asset['recipe'] is None for asset in manifest['assets']) == 3 and all(hashlib.sha256(archive.read(recipe['file'])).hexdigest() == recipe['sha256'] for recipe in recipes))
            (out/'download-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
            check('Export leaves saved brief review records and recipe source unchanged', store.card(payload['id']) == before and studio.jobs == jobs_before and all(store.get(identifier) == asset for identifier,asset in assets_before.items()))
            await page.screenshot(path=str(out/'working-pack-wide.png'),full_page=True)

            count = len([request for request in requests if request == ('POST','/api/briefs/export')])
            await page.fill('#briefDirection','Unsaved direction must stay here'); await action('workingPack'); await status('Save the brief before downloading')
            check('Dirty draft explains Save first and never sends export', len([request for request in requests if request == ('POST','/api/briefs/export')]) == count and await page.input_value('#briefDirection') == 'Unsaved direction must stay here' and len(downloads) == 1)
            await action('reload'); await idle()
            await action('new'); await idle(); await action('workingPack'); await status('Save the brief before downloading')
            check('Unsaved brief cannot download a working pack', len(downloads) == 1 and len([request for request in requests if request == ('POST','/api/briefs/export')]) == count)
            await page.select_option('#briefSelect',payload['id']); await page.wait_for_function("document.querySelector('#briefName')?.value==='Lantern Marsh'"); await idle()

            source = store.file(case.selected['background']['id']); raw = source.read_bytes(); source.write_bytes(b'Replaced synthetic source')
            await action('workingPack'); await status('asset changed'); await idle()
            check('Stale source refuses download and retains saved selection', len(downloads) == 1 and store.card(payload['id']) == before and source.read_bytes() == b'Replaced synthetic source')
            source.write_bytes(raw)

            async def delayed():
                entered.clear(); release.clear(); transfer['delay'] = True
                await action('workingPack')
                check('Real ZIP transfer reached the delayed HTTP boundary', await asyncio.to_thread(entered.wait,10))
                check('Pending transfer exposes progress and disables repeat action', await page.locator('[data-action=workingPack]').is_disabled() and 'Preparing working pack' in await page.locator('#briefStatus').inner_text())
            await delayed()
            await page.evaluate("StudioPrivacy.setScope('private');StudioPrivacy.setScope('regular')")
            release.set(); await idle()
            check('Privacy out and back discards a delayed download', len(downloads) == 1)
            check('Privacy cancellation clears the preparing status', 'Preparing working pack' not in await page.locator('#briefStatus').inner_text())
            await delayed()
            with store.connection() as db: db.execute('UPDATE workspace_identity SET id=?', ('b'*32,))
            release.set(); await status('different Workspace'); await idle()
            check('Workspace change during binary transfer discards download', len(downloads) == 1 and store.card(payload['id']) == before)
            with store.connection() as db: db.execute('UPDATE workspace_identity SET id=?', (scope,))
            await delayed()
            await page.evaluate("document.dispatchEvent(new CustomEvent('studio:navigate',{detail:'assets'}))")
            release.set(); await page.wait_for_function("!document.querySelector('#assetsView').hidden")
            await page.evaluate("location.hash='#briefs?id=pack-brief'"); await idle()
            check('Leaving the brief discards a delayed download', len(downloads) == 1)
            check('Navigation cancellation clears the preparing status', 'Preparing working pack' not in await page.locator('#briefStatus').inner_text())

            # Real download URL remains scoped independently of the browser guard.
            export_path = next(path for method,path in requests if method == 'GET' and path.startswith('/api/exports/'))
            response = await context.request.get(origin+export_path.replace(scope,'c'*32))
            check('Stale Workspace download URL refuses server-side', response.status == 409)
            response = await context.request.get(origin+export_path, headers={'X-Studio-Privacy':'private'})
            check('Private scope cannot fetch the Regular pack', response.status != 200)

            await page.set_viewport_size({'width':390,'height':844}); await idle()
            await page.screenshot(path=str(out/'working-pack-narrow.png'),full_page=True)
            check('390px layout has no horizontal overflow', await page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            await page.locator('[data-action=download]').focus(); await page.keyboard.press('Tab')
            check('Tab reaches the named working pack action at 390px', await page.locator('[data-action=workingPack]').evaluate('(el)=>el===document.activeElement'))
            async with page.expect_download() as pending: await page.keyboard.press('Enter')
            await (await pending.value).save_as(out/'narrow-working-pack.zip'); await idle()
            check('Narrow keyboard download completes after cancelled contexts', len(downloads) == 2)
            check('No generation render or asset review write was sent', not any(method == 'POST' and path not in ('/api/briefs/export','/api/estimate','/api/references/check','/api/assets/selection') for method,path in requests))
            check('No JavaScript errors', not errors)
            await context.close(); await browser.close(); browser = None
    finally:
        release.set()
        if browser: await browser.close()
        http.shutdown(); http.server_close(); thread.join(timeout=10)
        (out/'result.json').write_text(json.dumps({'checks':checks,'browser_errors':errors,'requests':requests,
            'scope':'Synthetic real HTTP/SQLite/ZIP proof. No model, generation, media render or creative acceptance.'},indent=2),encoding='utf-8')
        case.tearDown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--out',type=Path,required=True)
    asyncio.run(run(parser.parse_args().out))
