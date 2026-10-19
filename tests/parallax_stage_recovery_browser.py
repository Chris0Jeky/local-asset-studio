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


async def reload_saved_stage(page, stage, checks, width):
    expected = await page.evaluate('StudioSetupDraft.capture()')
    saved = await page.evaluate("""() => {
      const key=Object.keys(localStorage).find(key=>key.startsWith('studio-draft-v1:')&&key.endsWith(':'+selected.id));
      return key?JSON.parse(localStorage.getItem(key)):null;
    }""")
    assert saved and saved['recipe']['parallax']['stage'] == stage, 'Accepted stage must be saved before further input or pagehide'
    assert saved['recipe'] == expected['recipe']
    before = len(CALLS)
    await page.reload()
    await page.wait_for_function("!!window.StudioSetupDraft && backendActive==='primary' && !!selected")
    await page.evaluate('(id) => { selectPreset(id,true,true);showView("create"); }', PRESET['id'])
    await page.locator('#uxRestoreDraft').click()
    await page.wait_for_function('(stage) => parallaxState?.stage===stage && uploaded===parallaxState.source_file', arg=stage)
    assert await page.evaluate('StudioSetupDraft.capture().recipe') == expected['recipe']
    assert len(CALLS) == before, 'Reload/Restore must not replay stage requests'
    checks.append(f'{width}px {stage}: saved immediately, reload/Restore retains exact recipe without replay')
    await page.evaluate("document.querySelectorAll('#gallery').forEach(node=>{for(let p=node;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;})")


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
    job.update(preset_id=PRESET['id'], preset_name='Parallax fixture, synthetic',
               status='completed', message='Completed fixture, not a model run',
               parallax=dict(PLAN, stage='plate'))
    job.pop('parallax_finish', None)
    if not job.get('outputs'):
        job['outputs'] = [{'filename': 'lantern.png', 'asset_id': 'asset-0', 'media_type': 'image', 'seed': 42}]
    sibling = dict(id='sibling-job', preset_name='Parallax fixture, synthetic', preset_id=PRESET['id'],
                   status='uncertain', message='Synthetic uncertain sibling, not a model run',
                   prompt_ids=[], has_pending_submission=True, controls={}, outputs=[], parallax=dict(PLAN, stage='isolate'))
    fixture.JOBS[:] = [job, sibling]
    server = fixture.browser_server(Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    errors, checks, completed = [], [], False
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(executable_path=shutil.which('chromium'), headless=True, args=['--no-sandbox'])
            try:
                for width in (1440, 390):
                    page = await browser.new_page(viewport={'width': width, 'height': 1100})
                    dialogs = []
                    async def on_dialog(dialog):
                        dialogs.append(dialog.message)
                        await dialog.accept()
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('dialog', on_dialog)
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
                    await page.locator('.parallaxStage[data-job="fixture-job"]').first.wait_for(state='visible')
                    gallery_text = await page.locator('#gallery').inner_text()
                    assert 'uncertain' in gallery_text, 'Original card keeps the live sibling status'
                    assert 'isolate' in gallery_text.lower(), 'Original card names the sibling stage'
                    assert 'Recent runs or Problems' in gallery_text, 'Uncertain sibling directs the owner to its problem record'
                    assert 'Resume observation' not in gallery_text, 'A sibling without a prompt receipt must not recommend unavailable observation'
                    assert 'Do not press Generate again' in gallery_text, 'Uncertain submission must not be repeated'
                    assert await page.evaluate('backendActive') == 'primary', 'Backend identity is unchanged'
                    for stage in ('plate', 'isolate'):
                        button = page.locator(f'.parallaxStage[data-job="fixture-job"][data-stage="{stage}"]')
                        await button.wait_for(state='visible')
                        dialogs.clear()
                        before = len(CALLS)
                        await button.click()
                        await page.wait_for_function('(stage) => parallaxState?.stage===stage', arg=stage)
                        assert len(CALLS) == before+1, 'Capture must suppress the legacy duplicate request'
                        assert CALLS[-1] == {'job_id': 'fixture-job', 'stage': stage}
                        assert await page.evaluate('parallaxState.plan_id') == PLAN['plan_id']
                        assert await page.evaluate('parallaxState.source_sha256') == 'a'*64
                        assert await page.evaluate('parallaxState.preset_id') == PRESET['id']
                        assert await page.locator('#positive').input_value() == parallax.words(stage, PLAN['objects'])
                        assert dialogs, 'Explicit recall asks before replacing Create'
                        assert 'Nothing runs' in dialogs[-1], 'Replacement confirmation is preserved'
                        assert dialogs[-1].count('uncertain') == 1, 'Confirmation keeps the exact sibling status once'
                        assert 'Inspect the original job' in dialogs[-1], 'Confirmation keeps the uncertainty instruction'
                        assert 'do not repeat' in dialogs[-1].lower(), 'Confirmation forbids repeating uncertainty'
                        status_text = await page.locator('#status').inner_text()
                        assert 'edit is loaded' in status_text and 'Review its words' in status_text, 'Create success is preserved'
                        assert status_text.count('uncertain') == 1, 'Create status keeps the exact sibling status once'
                        assert 'Inspect the original job' in status_text, 'Create status keeps the uncertainty instruction'
                        assert 'do not repeat' in status_text.lower(), 'Create status forbids repeating uncertainty'
                        checks.append(f'{width}px {stage}: real card loads exact stage once with truthful sibling context')
                        if not args.inert:
                            await reload_saved_stage(page, stage, checks, width)
                    sibling['status'] = 'running'
                    await page.evaluate('refresh()')
                    dialogs.clear()
                    before = len(CALLS)
                    await page.locator('.parallaxStage[data-job="fixture-job"][data-stage="isolate"]').click()
                    await page.wait_for_function("document.querySelector('#status').textContent.includes('Wait for the original job')")
                    assert len(CALLS) == before+1
                    assert 'running' in dialogs[-1] and 'Wait for the original job' in dialogs[-1]
                    assert 'running' in await page.locator('#status').inner_text()
                    assert await page.evaluate('parallaxState.plan_id') == PLAN['plan_id']
                    assert await page.evaluate('backendActive') == 'primary'
                    checks.append(f'{width}px live isolate: original activity remains visible after real recall; no job request')
                    sibling['status'] = 'uncertain'
                    await page.evaluate('refresh()')
                    if not args.inert:
                        plate = parallax.stage_payload(PLAN, 'plate', fixture.source_context(fixture.ASSETS[0]))
                        await page.evaluate('(plate) => beginParallax(plate)', plate)
                        await page.evaluate('afterParallaxSubmit({id:"fixture-job"},parallaxState,StudioSetupDraft.stamp())')
                        assert await page.evaluate('parallaxState.stage') == 'isolate'
                        await reload_saved_stage(page, 'isolate', checks, width)
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
