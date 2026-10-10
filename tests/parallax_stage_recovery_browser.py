"""Actual stage-card clicks with synthetic API data; never runs generation."""
import argparse
import asyncio
import copy
import json
import shutil
import threading
from pathlib import Path

from playwright.async_api import async_playwright
import studio_browser_smoke as fixture
from asset_detail_browser import inert_page
import parallax

ROOT = Path(__file__).resolve().parents[1]
PRESET = next(p for p in fixture.CATALOG['presets'] if p.get('parallax_route'))
PLAN = dict(version=1, preset_id=PRESET['id'], source_asset_id='asset-0', source_sha256='a'*64,
            source_file='a'*32+'_room.png', width=512, height=512, objects='the desk', view_polygons=[])
PLAN['plan_id'] = parallax.plan_id(PLAN)
CALLS = []


class Handler(fixture.Handler):
    def do_POST(self):
        if self.path != '/api/parallax/stage':
            return super().do_POST()
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
        CALLS.append(body)
        if body.get('job_id') != 'fixture-job' or body.get('stage') not in parallax.STAGES:
            return self.json({'error': 'Invalid fixture stage'}, 400)
        return self.json(parallax.stage_payload(PLAN, body['stage'], fixture.source_context(fixture.ASSETS[0])))


async def run(args):
    args.out.mkdir(parents=True, exist_ok=True)
    fixture.POSTS.clear()
    CALLS.clear()
    original_jobs = copy.deepcopy(fixture.JOBS)
    job = copy.deepcopy(fixture.JOBS[0])
    job.update(preset_id=PRESET['id'], parallax=dict(PLAN, stage='plate'),
               parallax_finish={'job_id': 'fixture-split', 'summary': 'Synthetic split, not artwork acceptance'})
    fixture.JOBS[:] = [job]
    server = fixture.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    errors, checks, completed = [], [], False
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(executable_path=shutil.which('chromium'), headless=True, args=['--no-sandbox'])
            try:
                for width in (1440, 390):
                    page = await browser.new_page(viewport={'width': width, 'height': 1100})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('dialog', lambda dialog: dialog.accept())
                    page.set_default_timeout(5000)
                    if args.inert:
                        await inert_page(page, server.server_port)
                        # Inert fixtures do not resolve dynamically loaded relative scripts.
                        # Execute the exact module; this is not native loader/origin evidence.
                        await page.add_script_tag(content=(ROOT/'app/static/parallax-stage-recovery.js').read_text(encoding='utf-8'))
                    else:
                        await page.goto(f'http://127.0.0.1:{server.server_port}/#create', timeout=20000)
                    await page.wait_for_function("document.querySelector('#gallery').dataset.parallaxRecovery==='mounted' && backendActive==='primary' && !!selected")
                    await page.evaluate("showView('create');document.querySelectorAll('#gallery').forEach(node=>{for(let p=node;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;})")
                    for stage in ('plate', 'isolate'):
                        button = page.locator(f'.parallaxStage[data-job="fixture-job"][data-stage="{stage}"]')
                        await button.wait_for(state='visible')
                        before = len(CALLS)
                        await button.click()
                        await page.wait_for_function('(stage) => parallaxState?.stage===stage', arg=stage)
                        assert len(CALLS) == before+1, 'Capture must suppress the legacy duplicate request'
                        assert CALLS[-1] == {'job_id': 'fixture-job', 'stage': stage}
                        assert await page.evaluate('parallaxState.plan_id') == PLAN['plan_id']
                        assert await page.locator('#positive').input_value() == parallax.words(stage, PLAN['objects'])
                        checks.append(f'{width}px {stage}: real card loads exact stage once')
                    await page.evaluate("""() => {
                      const original=api;
                      api=async(url,options)=>{const response=await original(url,options);if(url==='/api/parallax/stage')await new Promise(resolve=>window.releaseStage=resolve);return response;};
                    }""")
                    await page.locator('.parallaxStage[data-stage="plate"]').click()
                    await page.wait_for_function("typeof releaseStage==='function'")
                    await page.locator('#positive').fill('Newer wording belongs to the owner.')
                    await page.evaluate('releaseStage()')
                    await page.wait_for_function("!document.querySelector('.parallaxStage[data-stage=plate]').disabled")
                    assert await page.locator('#positive').input_value() == 'Newer wording belongs to the owner.'
                    assert await page.evaluate('parallaxState.stage') == 'isolate'
                    checks.append(f'{width}px deferred response preserves newer wording and selected stage')
                    await page.close()
                assert not errors, errors
                assert not any(row['path'] == '/api/jobs' for row in fixture.POSTS), fixture.POSTS
                completed = True
            finally:
                await browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        fixture.JOBS[:] = original_jobs
        report = {'mode': 'inert transport/storage' if args.inert else 'native HTTP', 'checks': checks,
                  'errors': errors, 'stage_requests': CALLS, 'completed': completed,
                  'generation_submitted': any(row['path'] == '/api/jobs' for row in fixture.POSTS)}
        (args.out/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT/'.runtime/parallax-stage-recovery')
    parser.add_argument('--inert', action='store_true')
    asyncio.run(run(parser.parse_args()))
