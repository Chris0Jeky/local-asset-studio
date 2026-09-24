"""Workshop lifecycle and nested-dialog regressions against the real frontend.

Native HTTP/storage by default. --inert explicitly uses the existing component
transport/storage shim when localhost navigation is unavailable. No inference.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import threading
from http.server import ThreadingHTTPServer

from playwright.async_api import async_playwright
import studio_browser_smoke as fixture
from asset_detail_browser import inert_page
from workshop_browser_core import immersive_css
from workshop_wildcards import WILDCARDS, exercise_wildcards
from workshop_continuation_help import exercise_continuation_help

ROOT = Path(__file__).resolve().parents[1]


async def run(args):
    args.output.mkdir(parents=True, exist_ok=True)
    fixture.POSTS.clear()
    previous_wildcards = fixture.CATALOG.get("wildcards")
    if args.case in ("all", "wildcards"):
        fixture.CATALOG["wildcards"] = WILDCARDS
    server = ThreadingHTTPServer(('127.0.0.1', 0), fixture.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    checks, errors = [], []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(executable_path=os.environ.get('STUDIO_BROWSER_EXECUTABLE') or shutil.which('chromium') or None)
            page = await browser.new_page(viewport={'width':1440, 'height':900})
            page.set_default_timeout(10000)
            page.on('pageerror', lambda e: errors.append(str(e)))
            if args.inert:
                await inert_page(page, server.server_port)
                for name in ('workshop.css', 'bundle-explorer.css', 'studio-navigation.css', 'create-progressive-disclosure.css'):
                    await page.add_style_tag(content=(ROOT/'app/static'/name).read_text())
                await page.add_style_tag(content=immersive_css())
                for name in ('presentation-context.js', 'workshop.js', 'create-progressive-disclosure.js', 'bundle-core.js', 'bundle-explorer.js'):
                    await page.add_script_tag(content=(ROOT/'app/static'/name).read_text())
            else:
                await page.goto(f'http://127.0.0.1:{server.server_port}/#create')
            await page.wait_for_function('!!selected && !!document.querySelector("#workshopRecipeChange") && !!document.querySelector("#bundleLauncher")')
            await page.evaluate("showView('create')")
            await page.wait_for_timeout(150)
            if args.case in ('all', 'continuation'):
                await exercise_continuation_help(page, checks, fixture.POSTS)
                await page.set_viewport_size({'width':1440, 'height':900})
                await page.select_option('#workshopLayout', 'focus')
            if args.case in ('all', 'wildcards'):
                await exercise_wildcards(page, checks, fixture.POSTS)
                await page.set_viewport_size({'width':1440, 'height':900})
                await page.select_option('#workshopLayout', 'focus')
            if args.case in ('all', 'disclosure'):
                await page.evaluate("document.querySelector('#negativeWrap').open=false")
                await page.wait_for_function("sessionStorage.getItem('studio-negative-collapsed')==='1'")
                # Native details toggle is queued. Navigation can happen before it runs.
                value = await page.evaluate("""() => {
                    document.querySelector('#negativeWrap > summary').click();
                    window.dispatchEvent(new PageTransitionEvent('pagehide'));
                    return sessionStorage.getItem('studio-negative-collapsed');
                }""")
                assert value == '0', 'pagehide must persist the visible expanded state before the deferred toggle event'
                if not args.inert:
                    await page.reload()
                    await page.wait_for_function('!!selected && !!document.querySelector("#workshopRecipeChange")')
                    assert await page.locator('#negativeWrap').evaluate('n=>n.open'), 'expanded choice survives native reload'
                checks.append('negative disclosure is flushed through the existing preference owner before pagehide')
            if args.case in ('all', 'bundle'):
                await page.evaluate("""() => {
                    selectPreset('anima-portrait');
                    atelierRecipes=[{id:'workshop-fixture',name:'Workshop handoff fixture',family:'Anima',preset_id:'anima-portrait',
                        controls:{positive:'Reviewed bundle wording'},status:'unverified',notes:'Synthetic interaction fixture; no execution.'}];
                }""")
                await page.fill('#positive', 'Keep this draft until I apply')
                before = await page.evaluate('JSON.stringify(StudioSetupDraft.capture())')
                await page.click('#workshopRecipeChange')
                await page.click('#bundleLauncher')
                await page.click('[data-bundle="workshop-fixture"]')
                await page.keyboard.press('Escape')
                assert await page.locator('#workshopRecipeDialog').evaluate('n=>n.open'), 'cancelling a bundle keeps the recipe picker available'
                assert await page.locator('#bundleLauncher').evaluate('n=>n===document.activeElement')
                assert await page.evaluate('JSON.stringify(StudioSetupDraft.capture())') == before
                checks.append('bundle cancel returns to the picker without changing the draft')
                await page.click('#bundleLauncher')
                await page.click('[data-bundle="workshop-fixture"]')
                await page.check('#bundleConsent')
                # A concurrent edit makes the real bundle apply handler refuse the handoff.
                await page.evaluate("document.querySelector('#positive').value='A concurrent edit'")
                await page.click('#bundleApply')
                assert 'workbench changed' in await page.locator('#bundleApplyStatus').inner_text()
                assert await page.locator('#workshopRecipeDialog').evaluate('n=>n.open')
                assert await page.locator('#bundleExplorer').evaluate('n=>n.open')
                assert await page.locator('#positive').input_value() == 'A concurrent edit'
                checks.append('refused bundle application leaves both review surfaces and the current draft intact')
                await page.click('[data-bundle="workshop-fixture"]')
                await page.check('#bundleConsent')
                await page.click('#bundleApply')
                await page.wait_for_function("!document.querySelector('#bundleExplorer').open")
                assert not await page.locator('#workshopRecipeDialog').evaluate('n=>n.open'), 'successful bundle apply must close the parent recipe picker'
                await page.wait_for_function("document.activeElement===document.querySelector('#positive')")
                assert await page.locator('#positive').input_value() == 'Reviewed bundle wording'
                await page.fill('#positive', 'The applied draft is immediately editable')
                checks.append('successful bundle apply closes both dialogs and restores editable prompt focus')
            assert not [row for row in fixture.POSTS if row['path']=='/api/jobs']
            assert not errors, errors
            await page.screenshot(path=str(args.output/'handoff.png'))
            await browser.close()
    finally:
        if previous_wildcards is None:
            fixture.CATALOG.pop("wildcards", None)
        else:
            fixture.CATALOG["wildcards"] = previous_wildcards
        server.shutdown();server.server_close();thread.join(timeout=5)
        (args.output/'report.json').write_text(json.dumps({'native_origin':not args.inert,'live_comfyui':False,'checks':checks,'page_errors':errors}, indent=2)+'\n')
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'.runtime/workshop-handoffs')
    parser.add_argument('--inert', action='store_true')
    parser.add_argument('--case', choices=('all','bundle','disclosure','wildcards','continuation'), default='all')
    asyncio.run(run(parser.parse_args()))
