"""Named Library views over real HTTP/SQLite reads and disposable browser storage."""
import argparse
import asyncio
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
from types import SimpleNamespace
from urllib.parse import urlsplit
import uuid

from PIL import Image
from playwright.async_api import async_playwright, expect
from browser_ports import BoundPortGuard, browser_server
import studio_browser_smoke as shell
import server as production


async def run(out):
    out.mkdir(parents=True, exist_ok=True)
    checks, errors, requests = [], [], []
    browser = None
    def check(name, value):
        checks.append({'name': name, 'passed': bool(value)})
        print(name, bool(value), flush=True)
        assert value, name
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        stores, identifiers = [], []
        for workspace in ('a', 'b'):
            store = production.AssetWorkspace(root / workspace)
            ids = []
            for i, title in enumerate(('Forest path', 'Dusk repair', 'Agent draft', 'Private study')):
                source = root / f'{workspace}-{i}.png'
                Image.new('RGB', (96, 128), (70+i*35, 100, 130)).save(source)
                privacy = 'private' if i == 3 else 'regular'
                job = {'id': f'{workspace}-{i}', 'preset_name': 'Synthetic Library study', 'privacy': privacy,
                       'outputs': [{'filename': source.name, 'media_type': 'image'}]}
                if i == 2: job['run_label'] = 'Synthetic agent run'
                identifier = store.register(job, 0, source)
                store.update({'ids': [identifier], 'action': 'edit', 'title': title, 'favorite': i == 0,
                              'review': 'needs_work' if i == 1 else 'unreviewed',
                              'expected_revisions': {identifier: 0}, 'request_id': uuid.uuid4().hex}, privacy=privacy)
                ids.append(identifier)
            stores.append(store); identifiers.append(ids)
        for i in range(101): stores[0].collection({'name': f'Fixture collection {i:03}'})
        collection = stores[0].collection({'name': 'ZZZ temporary study collection'})
        before = [copy.deepcopy(store.snapshot(privacy='all')['assets']) for store in stores]

        class Handler(BoundPortGuard, production.extend_handler(production.Handler)):
            studio = SimpleNamespace(assets=stores[0], jobs={})
            json = shell.Handler.json
            def log_message(self, *args): pass
            def do_GET(self):
                requests.append(('GET', self.path))
                path = urlsplit(self.path).path
                if path == '/api/workspace' or path.startswith(('/api/assets/', '/api/collections')):
                    return super().do_GET()
                return shell.Handler.do_GET(self)
            def do_POST(self):
                requests.append(('POST', self.path))
                if self.path == '/api/assets/selection': return super().do_POST()
                if self.path in ('/api/estimate', '/api/references/check'): return shell.Handler.do_POST(self)
                return self._json(403, {'error': 'Named-view fixture refuses mutations'})

        http = browser_server(Handler)
        thread = threading.Thread(target=http.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
        thread.start()
        origin = 'http://127.0.0.1:' + str(http.server_port)
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None, headless=True)
                context = await browser.new_context(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
                page = await context.new_page(); page.set_default_timeout(10000)
                page.on('pageerror', lambda error: errors.append(str(error)))
                async def settle():
                    await page.wait_for_function('!!assetPaging&&!assetRefreshing&&!assetSearchTimer&&assetPaging.query===assetPageQuery()')
                async def expand():
                    if not await page.locator('#assetNamedViewsPanel').evaluate('(n)=>n.open'):
                        await page.locator('#assetNamedViewsPanel>summary').focus(); await page.keyboard.press('Enter')
                async def save(name):
                    await page.locator('#assetNamedName').fill(name); await page.locator('#assetNamedSave').click()
                    await expect(page.locator('#assetNamedStatus')).to_have_text('View saved.')
                async def restore(name):
                    await page.select_option('#assetNamedViews', name); await page.locator('#assetNamedRestore').click(); await settle()
                async def fields():
                    return await page.evaluate("({scope:assetScope,sort:$('#assetSort').value,type:$('#assetType').value,search:$('#assetSearch').value,archive:assetArchiveChoice(),source:assetSourceChoice(),group:assetGroupMode})")
                async def configure(scope, sort, media, search, archive, source, group):
                    await page.locator('[data-scope="'+scope+'"]').click(); await settle()
                    for selector, value in (('#assetSource', source), ('#assetSort', sort), ('#assetType', media), ('#assetArchiveFilter', archive), ('#assetGroup', group)):
                        await page.select_option(selector, value); await settle()
                    await page.locator('#assetSearch').fill(search); await settle()

                await page.goto(origin+'/#assets', timeout=25000); await settle(); await expand()
                check('Saved views opens from the keyboard', await page.locator('#assetNamedViewsPanel').evaluate('(n)=>n.open'))
                await configure('favorite', 'title', 'image', 'Forest', 'active', 'all', 'day')
                forest = await fields(); await save('Forest favorites')
                await configure('needs_work', 'oldest', 'all', 'Dusk', 'all', 'mine', 'recipe')
                repairs = await fields(); await save('Dusk repairs')
                await page.reload(); await settle(); await expand()
                await restore('Dusk repairs')
                check('Second named working set survives reload with every filter', await fields() == repairs)
                await page.locator('[data-asset-check="'+identifiers[0][1]+'"]').check()
                await restore('Forest favorites')
                check('First working set restores independently with its matching asset', await fields() == forest and await page.locator('[data-asset-check="'+identifiers[0][0]+'"]').count() == 1)
                check('Restoring a different view preserves the hidden checkbox selection', await page.evaluate('[...assetSelection]') == [identifiers[0][1]])
                await restore('Dusk repairs')
                check('Returning to the selected picture keeps its checkbox checked', await page.locator('[data-asset-check="'+identifiers[0][1]+'"]').is_checked())
                await page.locator('#assetNamedViewsPanel').scroll_into_view_if_needed()
                await page.screenshot(path=str(out/'named-views-wide.png'))
                await page.set_viewport_size({'width': 390, 'height': 844})
                await page.locator('#assetNamedRestore').focus()
                check('Narrow Use view control is keyboard reachable', await page.locator('#assetNamedRestore').evaluate('(n)=>n===document.activeElement'))
                check('Narrow saved-view controls do not overflow', await page.locator('#assetNamedViewsPanel').evaluate('(n)=>n.scrollWidth<=n.clientWidth+1'))
                await page.screenshot(path=str(out/'named-views-narrow.png'))
                await page.set_viewport_size({'width': 1440, 'height': 900})

                await page.locator('[data-privacy-scope="private"]').click(); await settle()
                check('Private view does not list Regular names', await page.locator('#assetNamedViews option').count() == 1)
                await save('Private study view')
                check('Private views explain tab-only storage', 'only in this tab' in await page.locator('#assetNamedHelp').inner_text())
                await page.locator('[data-privacy-scope="all"]').click(); await settle()
                check('All view does not list Private names', await page.locator('#assetNamedViews option').count() == 1)
                await save('All study view')
                check('Private and All names never enter persistent local storage', await page.evaluate("!JSON.stringify({...localStorage}).includes('Private study view')&&!JSON.stringify({...localStorage}).includes('All study view')"))
                await page.locator('[data-privacy-scope="regular"]').click(); await settle(); await restore('Forest favorites')
                await page.locator('#assetNamedName').fill('Unfinished workspace A name')
                Handler.studio.assets = stores[1]
                await page.locator('#workspaceRefresh').click(); await settle()
                check('Workspace B has no A views or draft name', await page.locator('#assetNamedViews option').count() == 1 and await page.input_value('#assetNamedName') == '')
                await save('Workspace B study')
                Handler.studio.assets = stores[0]
                await page.locator('#workspaceRefresh').click(); await settle()
                check('Returning to workspace A recovers only its two views', await page.locator('#assetNamedViews option').all_text_contents() == ['Choose a saved view…', 'Forest favorites', 'Dusk repairs'])

                await page.locator('#collectionPaging button').click()
                await page.locator('[data-scope="collection:'+collection['id']+'"]').click(); await settle(); await save('Collection study')
                await restore('Forest favorites'); previous = await fields()
                stores[0].collection({'action': 'delete', 'id': collection['id']})
                await page.locator('#workspaceRefresh').click(); await settle()
                await page.select_option('#assetNamedViews', 'Collection study'); await page.locator('#assetNamedRestore').click()
                await expect(page.locator('#assetNamedStatus')).to_contain_text('collection is unavailable')
                check('Missing collection keeps the current filters and saved view', await fields() == previous and await page.locator('#assetNamedViews option').count() == 4)
                await page.evaluate("window.fixtureSetItem=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k.startsWith('studio.assets.named-views.v1:'))throw Error('Synthetic storage refusal');return window.fixtureSetItem.call(this,k,v)}")
                await page.locator('#assetNamedName').fill('Denied save'); await page.locator('#assetNamedSave').click()
                await expect(page.locator('#assetNamedStatus')).to_contain_text('Synthetic storage refusal')
                check('Storage failure preserves saved views and filters', await fields() == previous and await page.locator('#assetNamedViews option').count() == 4)
                await page.evaluate('Storage.prototype.setItem=window.fixtureSetItem;delete window.fixtureSetItem')
                await page.select_option('#assetNamedViews', 'Collection study'); await page.locator('#assetNamedRemove').click()
                check('Removing a view preserves other views and current filters', await page.locator('#assetNamedViews option').count() == 3 and await fields() == previous)
                check('No asset or generation mutation was requested', not any(method == 'POST' and urlsplit(path).path not in ('/api/estimate', '/api/references/check', '/api/assets/selection') for method, path in requests))
                check('All saved asset metadata remains unchanged', [store.snapshot(privacy='all')['assets'] for store in stores] == before)
                check('No browser JavaScript errors', not errors)
                await context.close(); await browser.close(); browser = None
        finally:
            if browser: await browser.close()
            http.shutdown(); http.server_close(); thread.join(timeout=10)
            (out/'result.json').write_text(json.dumps({'checks': checks, 'browser_errors': errors, 'requests': requests,
                'scope': 'Synthetic images and disposable SQLite/browser storage. Fixture deletes one empty collection and injects one storage refusal. No model or native execution.'}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--out', type=Path, required=True)
    asyncio.run(run(parser.parse_args().out))
