"""Paged source choices over the shipped UI and disposable production SQLite.

The fixture has 101 newer agent results above three personal results. It never
constructs Studio, uses installed runtimes, or accepts metadata/generation writes.
"""
import argparse
import asyncio
import hashlib
import json
import shutil
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from playwright.async_api import async_playwright
import studio_browser_smoke as fixture
import server as production
from browser_ports import BoundPortGuard, evidence_screenshot

ROOT = Path(__file__).resolve().parents[1]


async def exercise(args):
    args.out.mkdir(parents=True, exist_ok=True)
    checks, errors, writes, reads = [], [], [], []
    failure = None

    def check(identifier, condition):
        checks.append({'id': identifier, 'passed': bool(condition)})
        print(identifier, bool(condition), flush=True)
        if not condition:
            raise AssertionError(identifier)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        store = production.AssetWorkspace(root / 'workspace')
        source = root / 'fixture.png'
        Image.new('RGB', (48, 64), (80, 110, 120)).save(source)
        mine = [store.register({'id': f'mine-{i}', 'created_at': i, 'label': label,
                                'preset_name': 'Personal fixture',
                                'outputs': [{'filename': source.name, 'media_type': 'image'}]}, 0, source)
                for i, label in enumerate((None, '', 'Make · Portrait'))]
        agents = [store.register({'id': f'agent-{i}', 'created_at': 1000+i, 'label': 'Agent lab',
                                  'preset_name': 'Agent fixture',
                                  'outputs': [{'filename': source.name, 'media_type': 'image'}]}, 0, source)
                  for i in range(101)]
        personal = store.collection({'name': 'Personal only'})
        with store.connection() as db:
            db.executemany('INSERT INTO collection_assets VALUES (?,?)', [(personal['id'], key) for key in mine])
        before = store.snapshot()

        class Handler(BoundPortGuard, production.extend_handler(production.Handler)):
            studio = SimpleNamespace(assets=store, jobs={})
            json = fixture.Handler.json

            def do_GET(self):
                if self.path.startswith('/api/assets/page?'):
                    reads.append(self.path)
                if self.path == '/api/workspace' or self.path.startswith(('/api/assets/', '/api/collections')):
                    return super().do_GET()
                return fixture.Handler.do_GET(self)

            def do_POST(self):
                if self.path == '/api/assets/selection':
                    return super().do_POST()
                if self.path == '/api/assets/update':
                    writes.append(self.path)
                    return self._json(409, {'error': 'This observation fixture does not accept metadata writes'})
                return fixture.Handler.do_POST(self)

        http = production.StudioHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        fixture.POSTS.clear()
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(executable_path=shutil.which('chromium'), headless=True, args=['--no-sandbox'])
                context = await browser.new_context(viewport={'width': 1440, 'height': 1100}, reduced_motion='reduce')
                page = await context.new_page()
                page.set_default_timeout(8000)
                page.on('pageerror', lambda error: errors.append(str(error)))
                await page.goto(f'http://127.0.0.1:{http.server_port}/#assets', timeout=20000)

                async def settle():
                    await page.wait_for_function('!!assetPaging&&!assetRefreshing&&assetPaging.query===assetPageQuery()')

                await settle()
                check('SOURCE-01 default Mine finds all three older personal results',
                      set(await page.evaluate('assetState.assets.map(a=>a.id)')) == set(mine)
                      and await page.input_value('#assetSource') == 'mine'
                      and await page.locator('#assetSource').is_visible())
                await page.select_option('#assetSource', 'agent')
                await settle()
                check('SOURCE-02 Agent runs starts with one bounded page',
                      await page.evaluate('assetState.assets.length') == 100
                      and await page.locator('[data-asset-page="next"]').is_enabled())
                selected = await page.evaluate('assetState.assets[0].id')
                await page.locator(f'[data-asset-check="{selected}"]').check()
                await page.click('[data-asset-page="next"]')
                await settle()
                check('SOURCE-03 explicit Next reads the remaining agent and retains selection',
                      await page.evaluate('assetState.assets.length') == 1
                      and await page.evaluate('id=>assetSelection.has(id)', selected)
                      and await page.locator('[data-asset-page="next"]').is_disabled())
                await page.select_option('#assetSource', 'mine')
                await settle()
                check('SOURCE-04 changing source resets its cursor and keeps off-page selection',
                      set(await page.evaluate('assetState.assets.map(a=>a.id)')) == set(mine)
                      and await page.evaluate('assetPaging.history.length') == 0
                      and await page.evaluate('id=>assetSelection.has(id)', selected))
                await page.click(f'#assetCollections [data-scope="collection:{personal["id"]}"]')
                await settle()
                await page.select_option('#assetSource', 'agent')
                await settle()
                check('SOURCE-05 empty Agent page keeps its choice and names the source filter',
                      await page.locator('#assetGrid h3').inner_text() == 'No agent runs here'
                      and await page.input_value('#assetSource') == 'agent'
                      and await page.locator('#assetSource').is_visible())
                await page.set_viewport_size({'width': 390, 'height': 1100})
                await page.locator('#assetSource').scroll_into_view_if_needed()
                check('SOURCE-06 source controls and empty-state action fit at 390px',
                      await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                      and await page.locator('[data-asset-source="all"]').is_visible())
                await evidence_screenshot(page, path=str(args.out / 'source-empty-390.png'))
                await page.click('[data-asset-source="all"]')
                await settle()
                check('SOURCE-07 Show all sources reads the personal collection again',
                      set(await page.evaluate('assetState.assets.map(a=>a.id)')) == set(mine)
                      and await page.input_value('#assetSource') == 'all')
                check('SOURCE-08 all source observations leave saved metadata unchanged',
                      not writes and store.snapshot() == before
                      and all(post['path'] in {'/api/estimate', '/api/references/check'} for post in fixture.POSTS))
                check('SOURCE-09 no JavaScript exceptions', not errors)
                await browser.close()
        except Exception as error:
            failure = repr(error)
        finally:
            http.shutdown(); http.server_close(); thread.join(5)
            receipt = {'mode': 'native Chromium HTTP and production SQLite', 'checks': checks, 'errors': errors,
                       'execution_error': failure, 'metadata_writes': writes, 'page_reads': reads, 'other_posts': fixture.POSTS,
                       'fixture_assets': {'mine': len(mine), 'agent': len(agents)},
                       'source_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                                         for p in ('app/static/workspace.js', 'studio_workflow/asset_reads.py')},
                       'limits': 'Synthetic media and temporary Workspace; no installed runtime or generation.'}
            (args.out / 'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    if failure or errors or len(checks) != 9:
        raise AssertionError(failure or 'Source-filter fixture did not complete')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    asyncio.run(exercise(parser.parse_args()))
