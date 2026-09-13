"""Opt-in control geometry proof; actual Studio source, synthetic HTTP only."""
import argparse
import asyncio
import hashlib
import json
import os
import shutil
import threading
from pathlib import Path

import studio_browser_smoke as fixture
from asset_detail_browser import inert_page


async def run(args):
    from playwright.async_api import async_playwright
    args.out.mkdir(parents=True, exist_ok=True)
    fixture.POSTS.clear()
    server = fixture.ThreadingHTTPServer(('127.0.0.1', 0), fixture.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cases, errors = [], []
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(executable_path=args.chromium or shutil.which('chromium'), headless=True)
            try:
                for width, scale in ((1440, 1), (390, 1), (1440, 2)):
                    page = await browser.new_page(viewport={'width': width // scale, 'height': 1000 // scale},
                                                  device_scale_factor=scale, reduced_motion='reduce')
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    if args.inert:
                        await inert_page(page, server.server_port)
                    else:
                        await page.goto(f'http://127.0.0.1:{server.server_port}/#create')
                    await page.wait_for_function('!!selected && schemaAvailable')
                    await page.evaluate("showView('create'); selectPreset('wan22-i2v')")
                    await page.wait_for_function("document.querySelector('#i2vMode')?.value === 'quick-diagnostic'")
                    if not await page.locator('#i2vMode').is_visible():
                        await page.locator('#i2vMode').locator('xpath=ancestor::details[1]/summary').click()
                    await page.locator('[data-key=seed]').fill('20260913')
                    textarea_height = await page.locator('#positive').evaluate('(e) => e.getBoundingClientRect().height')
                    for mode in ('quick-diagnostic', 'quality', 'canonical-upstream'):

                        await page.locator('#i2vMode').select_option(mode)
                        expected_seed = await page.locator('[data-key=seed]').input_value()
                        if mode == 'canonical-upstream':
                            await page.locator('[data-key=seed]').evaluate('''e => {
                                e.parentElement.firstChild.textContent='Zufallsstartwert – graine aléatoire – seed '.repeat(3)+'X'.repeat(80);
                            }''')
                        await page.locator('[data-key=seed]').focus()
                        await page.keyboard.press('Tab')
                        keyboard_next = await page.evaluate("document.querySelector('#controls').contains(document.activeElement) && document.activeElement !== getControl('seed')")
                        geometry = await page.evaluate('''() => ({
                            boxes: Object.fromEntries(['[data-key=seed]','#batch','#i2vMode'].map(id => {
                                const el=document.querySelector(id),r=el.getBoundingClientRect();
                                return [id,{width:r.width,height:r.height,labelHeight:el.parentElement.getBoundingClientRect().height,
                                    align:getComputedStyle(el.parentElement).alignContent}];})),
                            overflow: document.documentElement.scrollWidth > innerWidth + 1,
                            viewport: innerWidth,
                            full_width_help: document.querySelector('#i2vModeNote').getBoundingClientRect().width >= document.querySelector('#controls').clientWidth - 2,
                            textarea_height: document.querySelector('#positive').getBoundingClientRect().height,
                            note_clipped: document.querySelector('#i2vModeNote').scrollHeight > document.querySelector('#i2vModeNote').clientHeight + 1,
                            held: document.querySelector('#generate').disabled,
                            note: document.querySelector('#i2vModeNote').textContent,
                            seed: document.querySelector('[data-key=seed]').value
                        })''')
                        await page.locator('#controls').evaluate('e => window.scrollTo(0, scrollY + e.getBoundingClientRect().top - 90)')
                        seed_hit = await page.locator('[data-key=seed]').evaluate('''e => {
                            const r=e.getBoundingClientRect(); return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===e;
                        }''')
                        await page.screenshot(path=str(args.out / f'{mode}-{width}-{scale}x.png'))
                        passed = (all(30 <= b['height'] <= 64 for b in geometry['boxes'].values())
                                  and geometry['full_width_help'] and seed_hit
                                  and not geometry['overflow'] and not geometry['note_clipped'] and keyboard_next
                                  and geometry['seed'] == expected_seed and geometry['textarea_height'] == textarea_height
                                  and geometry['held'] == (mode != 'quick-diagnostic')
                                  and ('Held:' in geometry['note']) == (mode != 'quick-diagnostic'))
                        cases.append({'physical_width': width, 'reflow_scale': scale, 'mode': mode, 'keyboard_next': keyboard_next, 'seed_hit': seed_hit, 'passed': passed, **geometry})
                    await page.close()
            finally:
                await browser.close()
    finally:
        server.shutdown(); server.server_close(); thread.join(5)
    forbidden = [p for p in fixture.POSTS if p['path'] not in ('/api/estimate', '/api/references/check')]
    result = {'mode': 'inert-component-http-bridge' if args.inert else 'native-http-synthetic-api',
              'zoom_evidence': '2x cases emulate browser reflow with half the CSS viewport and double device scale; no browser chrome zoom command',
              'cases': cases, 'errors': errors, 'forbidden': forbidden,
              'source_sha256': {p: hashlib.sha256((fixture.ROOT / p).read_bytes()).hexdigest() for p in
                                ('app/static/style.css', 'app/static/app.js', 'tests/control_layout_browser.py')}}
    (args.out / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    if errors or forbidden or any(not c['passed'] for c in cases):
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--inert', action='store_true')
    parser.add_argument('--chromium', default=os.environ.get('CHROMIUM_PATH'))
    asyncio.run(run(parser.parse_args()))
