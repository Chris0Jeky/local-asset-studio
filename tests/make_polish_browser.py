"""S3 one-press Polish: StudioWorkbench.polish sends exactly one /api/jobs per press and leaves Create alone. Never a model call.

python tests/make_polish_browser.py
Fixture server from studio_browser_smoke (real frontend, synthetic API, real catalog capabilities).
"""
import json
import threading
import time
from http.server import ThreadingHTTPServer

from playwright.sync_api import sync_playwright
import studio_browser_smoke as fixture

WAI = 'asset-1'  # its context says it was made by the WAI recipe; asset-0 stays the fixture's Anima picture


def context(asset_id):
    asset = next(a for a in fixture.ASSETS if a['id'] == asset_id)
    return {**fixture.source_context(asset), 'preset_id': 'wai'} if asset_id == WAI else fixture.source_context(asset)


class Handler(fixture.Handler):
    def do_GET(self):
        if self.path.startswith('/api/assets/') and self.path.endswith('/context'): return self.json(context(self.path.split('/')[3]))
        return super().do_GET()

    def do_POST(self):
        if self.path not in ('/api/jobs', '/api/assets/reference'): return super().do_POST()
        data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
        fixture.POSTS.append({'path': self.path, 'data': data})
        if self.path == '/api/jobs': return self.json({'id': 'polish-'+str(len(fixture.POSTS)), 'status': 'queued', 'message': 'Queued (fixture, no model run)'})
        time.sleep(0.3)  # a second press lands while the first copy is still in flight
        return self.json({'file': 'a'*32+'_fixture.png', 'sha256': 'a'*64, 'width': 512, 'height': 768, 'parent_asset': data['id'], 'context': context(data['id'])})


def jobs():
    return [p['data'] for p in fixture.POSTS if p['path'] == '/api/jobs']


def run():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler); threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = 'http://127.0.0.1:'+str(server.server_port); errors = []
    template = {p['id']: p['continuation_capability']['template_sha256'] for p in fixture.CATALOG['presets']}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True); page = browser.new_page(); page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(origin+'/#create'); page.wait_for_function('window.StudioWorkbench?.polish&&catalog?.presets?.length&&!!selected')
            assert not jobs(), 'nothing is submitted on load'
            page.evaluate('()=>{selectPreset("anima-portrait");document.querySelector("#positive").value="My own words, untouched"}')
            before = page.evaluate('()=>({preset:selected.id,positive:document.querySelector("#positive").value,parents:[...parentAssets],uploaded,claim:continuationState||null,view})')
            plan = page.evaluate('(id)=>StudioWorkbench.polishPlan(id,"face")', WAI)
            assert plan['ok'] and plan['preset_id'] == 'anime-face', plan
            assert page.evaluate('(id)=>StudioWorkbench.polishPlan(id,"face")', 'asset-0')['preset_id'] == 'anime-detail-fix', 'an Anima picture gets the general detail pass'
            assert not jobs(), 'a plan never submits'
            # Two presses at once: one job, one plain refusal.
            settled = page.evaluate('async(id)=>(await Promise.allSettled([StudioWorkbench.polish(id,"face"),StudioWorkbench.polish(id,"face")])).map(r=>r.status==="fulfilled"?{ok:r.value.id}:{error:r.reason.message})', WAI)
            assert sum('ok' in r for r in settled) == 1 and any('already' in r.get('error', '') for r in settled), settled
            assert len(jobs()) == 1, jobs()
            job = jobs()[0]; claim = job['continuation']; file = 'a'*32+'_fixture.png'
            assert job['preset_id'] == 'anime-face' and job['parent_assets'] == [WAI] and job['batch_count'] == 1, job
            assert claim == {'version': 1, 'intent': 'repair', 'preset_id': 'anime-face', 'reference_file': file, 'source_asset_id': WAI,
                             'source_sha256': 'a'*64, 'template_sha256': template['anime-face']}, claim
            assert job['controls']['reference'] == file and job['controls']['positive'] == context(WAI)['positive'], job['controls']
            # Upscale takes no words; a non-anime refusal names its reason and sends nothing.
            up = page.evaluate('(id)=>StudioWorkbench.polish(id,"upscale")', WAI)
            assert up['id'] and len(jobs()) == 2 and jobs()[1]['preset_id'] == 'anime-esrgan' and 'positive' not in jobs()[1]['controls'], jobs()[1]
            refused = page.evaluate('(id)=>StudioWorkbench.polish(id,"sharpen").then(()=>"",e=>e.message)', WAI)
            assert refused and len(jobs()) == 2, refused
            after = page.evaluate('()=>({preset:selected.id,positive:document.querySelector("#positive").value,parents:[...parentAssets],uploaded,claim:continuationState||null,view})')
            assert after == before, (before, after)
            browser.close()
    finally:
        server.shutdown(); server.server_close()
    assert not errors, errors
    print(json.dumps({'jobs_posted': len(jobs()), 'double_press_posts': 1, 'create_unchanged': True, 'page_errors': errors}))


if __name__ == '__main__':
    run()
