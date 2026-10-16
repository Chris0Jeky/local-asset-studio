"""Picture goals stay in Make, and Compare looks runs one picture per look (owner ask, 16 Oct 2026; audit #5-#7, #16).

python tests/make_goals_browser.py [--screenshots DIR]
Fixture server from studio_browser_smoke (real frontend and catalog capabilities, synthetic API). Every /api/jobs is a
fixture record: no ComfyUI, no model. Asserts each goal's exact request, that the handoff dialog never opens, and that
recipe placeholders never reach the page.
"""
import argparse
import json
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright
import studio_browser_smoke as fixture

ROOT = Path(__file__).resolve().parents[1]
SHIPPED = [dict(entry, origin='seed', revision=0, trashed_at=None, usable=True, unusable_reason=None, anchor_asset_id=None)
           for entry in json.loads((ROOT / 'presets/looks.json').read_text(encoding='utf-8'))['looks']]
JOBS = {}
UPLOAD = 'f' * 32 + '_look.jpg'


class Handler(fixture.Handler):
    def do_GET(self):
        if self.path == '/api/looks': return self.json({'looks': SHIPPED, 'seed_errors': [], 'generation_submitted': False})
        if self.path.startswith('/api/assets/') and self.path.endswith('/thumb'):  # thumbnails for the screenshots
            asset = next((a for a in fixture.ASSETS if a['id'] == self.path.split('/')[3]), None)
            if asset: self.path = '/api/assets/%s/file' % asset['id']
        if self.path.startswith('/api/jobs/goal-'):
            job = JOBS[self.path.split('/')[-1]]
            job.update(status='completed', outputs=[dict(filename='out.png', asset_id='asset-0', media_type='image')])
            return self.json(job)
        return super().do_GET()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', '0'))
        if self.path == '/api/upload':
            self.rfile.read(length); fixture.POSTS.append({'path': self.path, 'data': {'filename': self.headers.get('X-Filename')}})
            return self.json({'file': UPLOAD, 'sha256': 'b' * 64, 'width': 512, 'height': 768, 'bytes': 2048}, 201)
        if self.path == '/api/pose/render':
            data = json.loads(self.rfile.read(length)); fixture.POSTS.append({'path': self.path, 'data': data})
            assert set(data) == {'width', 'height', 'keypoints'} and len(data['keypoints']) == 18, data
            return self.json({'file': 'e' * 32 + '_drawn-pose.png', 'sha256': 'd' * 64, 'bytes': 2048, 'width': data['width'], 'height': data['height'],
                              'artifact_id': 'c' * 64, 'renderer': 'studio.coco18-lines/v1', 'generation_submitted': False}, 201)
        if self.path == '/api/looks/prepare':
            data = json.loads(self.rfile.read(length)); fixture.POSTS.append({'path': self.path, 'data': data})
            look = next(l for l in SHIPPED if l['id'] == data['id'])
            return self.json({'preset_id': look['body']['preset_id'], 'controls': {**look['body']['controls'], 'positive': look['body']['template'].replace('{scene}', data['scene'])}})
        if self.path == '/api/jobs':
            data = json.loads(self.rfile.read(length)); fixture.POSTS.append({'path': self.path, 'data': data})
            job = dict(data, id='goal-' + str(len(JOBS)), status='queued', created_at=1789228800, outputs=[]); JOBS[job['id']] = job
            return self.json(job)
        return super().do_POST()


def jobs(): return [p['data'] for p in fixture.POSTS if p['path'] == '/api/jobs']
def posted(path): return [p['data'] for p in fixture.POSTS if p['path'] == path]


def run(shots):
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler); threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = 'http://127.0.0.1:' + str(server.server_port); errors = []; clicks = {}
    shots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 900}); page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(origin + '/#make'); page.wait_for_selector('[data-make-look]'); page.wait_for_function('!!catalog?.presets?.length&&!!window.StudioWorkbench?.polish')
        assert not jobs(), 'nothing is submitted on load'

        # Viewport shots with the step-2 heading at the top (a full-page capture repeats the sticky shell over the content).
        def shot(name, target='#makeComposer'):
            for width, height in ((1440, 900), (390, 844)):
                page.set_viewport_size({'width': width, 'height': height}); page.wait_for_timeout(150)
                page.evaluate('(s)=>{const e=document.querySelector(s);if(e)window.scrollTo(0,e.getBoundingClientRect().top+scrollY-140)}', target); page.wait_for_timeout(100)
                page.screenshot(path=str(shots / ('%s-%d.png' % (name, width))))
            page.set_viewport_size({'width': 1440, 'height': 900}); page.wait_for_timeout(150)

        def no_modal(): assert not page.evaluate('document.querySelector("#uxHandoff")?.open'), 'the handoff dialog must not open'

        def generate():
            before = len(jobs()); page.locator('#makeGenerate').click()
            page.wait_for_function('n=>document.querySelector("#makeStatus").textContent.startsWith("Started")||document.querySelector("[aria-invalid=true]")', arg=before, timeout=5000)
            page.wait_for_function('!document.querySelector("#makeGenerate").disabled'); return jobs()[before:]

        def goal(name, asset='asset-1'):
            # The chosen picture stays chosen across picture goals; Change picture reopens the grid.
            page.locator('[data-make-goal="%s"]' % name).click(); page.wait_for_selector('#makeComposer #makeGenerate,[data-make-pick]')
            if page.evaluate('(a)=>!!document.querySelector("[data-make-pick]")||!document.querySelector(`#makeComposer [data-ux-handoff="${a}"]`)', asset):
                if not page.locator('[data-make-pick]').count(): page.locator('[data-make-repick]').first.click()
                page.locator('[data-make-pick="%s"]' % asset).click()
            page.wait_for_selector('#makeComposer #makeGenerate')

        # Looks are ordered by lab evidence, proven ones wear a badge, each goal opens on its usual shape, and the general look has a plain name
        # (journey audit #12, #21, #24). The lab doc is docs/looks/LOOK-LAB-2026-10-16.md on branch lab/look-qualification-20261016.
        def looks_of(goal_id):
            page.locator('[data-make-goal="%s"]' % goal_id).click(); page.wait_for_selector('[data-make-look],#makeScene')
            if page.locator('[data-make-change]').count(): page.locator('[data-make-change]').click()
            return page.eval_on_selector_all('[data-make-look]', 'n=>n.map(e=>e.dataset.makeLook)')
        def pick_look(look_id):
            if page.locator('[data-make-change]').count(): page.locator('[data-make-change]').click()
            page.locator('[data-make-look="%s"]' % look_id).click(); page.wait_for_selector('#makeScene')
        CHARACTERS = ['look-anima-pearly-petiflow', 'look-oneobsession-anima-v20-showcase', 'look-anifox-ringeko', 'look-pearly-anima-mix-v10-showcase', 'look-wai-fantasy-portrait', 'look-anima-fantasy-portrait', 'look-animagine-fantasy-portrait']
        assert looks_of('character') == CHARACTERS, 'proven first, rejects after them, no oil-paint look under Anime character'
        shot('looks-character', '.make-looks')
        badged = page.eval_on_selector_all('.make-look', 'n=>n.filter(e=>e.querySelector(".make-tested")).map(e=>e.querySelector("[data-make-look]").dataset.makeLook)')
        assert badged == ['look-anima-pearly-petiflow'], badged  # kept in most test pictures (rounds 1-2); AniFox kept 0 of 2 new seeds
        assert page.locator('.make-tested').first.inner_text() == 'Tested well' and '4 of 4' in page.locator('.make-tested').first.get_attribute('title')
        pick_look('look-anima-pearly-petiflow'); assert page.locator('.make-chosen .make-tested').count() == 1 and page.input_value('#makeShape') == 'portrait'
        assert not page.locator('#makeDraft').count(), 'Draft first is for slow looks only'
        painting = looks_of('painting')
        assert painting[0] == 'look-anima-painterly-artist-tags' and {'look-krea-atelier-target-stack', 'look-krea-witch-nijisis'} <= set(painting) and painting[-1] == 'look-krea-witch-nijisis', painting
        assert looks_of('scene') == ['look-night-shift-retro-anime', 'look-noob-fantasy-scene', 'look-krea-watercolor-anime']
        pick_look('look-noob-fantasy-scene'); assert page.input_value('#makeShape') == 'landscape', 'a scene is wide by default'
        assert 'As designed · 832×1216' in page.locator('#makeShape option[value=design]').inner_text(), 'As designed stays available'
        page.locator('#makeScene').fill('a misty harbour at dawn'); job = generate()[0]
        assert (job['controls']['width'], job['controls']['height']) == (1216, 832), job['controls']
        assert looks_of('game')[0] == 'look-preset-stylized-prop'; pick_look('look-preset-pixel-lora'); assert page.input_value('#makeShape') == 'square'
        photo = looks_of('photo'); assert photo[:2] == ['look-preset-zimage-fast', 'look-preset-realvis'] and photo[-2:] == ['look-krea-realistic-snapshot', 'look-krea-lenovo-ultrareal'], photo
        names = page.eval_on_selector_all('.make-look-text b', 'n=>n.map(e=>e.textContent)'); assert 'Quick picture, any subject' in names and not any('Fast general' in n for n in names), names
        pick_look('look-preset-zimage-fast'); assert page.input_value('#makeShape') == 'design', 'a goal without a usual shape follows the look'

        # Draft first (audit #12): a slow look offers a quick low-step draft; the draft's card offers "Make the final", which stages the same
        # words and seed at the look's full steps and waits for Generate. Neither press submits anything but Generate.
        looks_of('painting'); pick_look('look-krea-oil-fantasy'); assert page.input_value('#makeCount') == '1'
        draft = page.locator('#makeDraft'); assert draft.count() == 1 and not draft.is_checked() and 'Draft first · 6 steps' in page.locator('#makeDraftBox').inner_text()
        draft.check(); assert page.input_value('[data-tune=steps]') == '6' and 'draft 6 steps' in page.locator('#makeTuneSum').inner_text(), 'the draft is Tune’s own steps control'
        page.locator('#makeScene').fill('a lone scholar on a bridge at dusk'); shot('draft-first'); before = len(jobs()); sent = generate(); no_modal()
        assert len(sent) == 1 and sent[0]['controls']['steps'] == 6 and sent[0]['preset_id'] == 'krea-anime-atelier', sent
        draft_job = sent[0]; page.wait_for_selector('[data-make-final]', timeout=8000)
        assert page.locator('[data-make-final]').inner_text() == 'Make the final' and 'draft 6 steps' in page.locator('.make-run .make-tuned').first.inner_text()
        page.locator('[data-make-final]').click(); assert len(jobs()) == before + 1, 'Make the final does not submit'
        assert not page.locator('#makeDraft').is_checked() and page.input_value('[data-tune=steps]') == '' and page.input_value('#makeScene') == 'a lone scholar on a bridge at dusk'
        assert not page.is_checked('#makeNewSeed') and page.input_value('#makeSeed') == str(draft_job['controls']['seed']), 'the seed is locked to the draft’s'
        assert 'Press Generate' in page.locator('#makeStatus').inner_text() and page.evaluate('document.activeElement.id') == 'makeGenerate'
        final = generate()[0]; assert final['controls']['steps'] == 12 and final['controls']['seed'] == draft_job['controls']['seed'], final['controls']
        assert final['controls']['positive'] == draft_job['controls']['positive'] and final['controls']['width'] == draft_job['controls']['width'], 'same words, same shape'
        page.wait_for_function('document.querySelectorAll(".make-run")[0].querySelector("[data-make-final]")===null'); assert page.locator('[data-make-final]').count() == 1, 'only the draft offers the final'
        clicks['draft'] = 5  # goal, look, Draft first, Generate, then Make the final and Generate (+ the words typed)

        # Restyle: search, pick, choose a look by its picture, Generate. The look's picture is the style board.
        page.locator('[data-make-goal="restyle"]').click(); page.wait_for_selector('[data-make-pick]')
        page.locator('[data-make-search="makePictures"]').fill('forest')
        assert page.locator('#makePictures [data-make-pick]').count() == 1, 'search narrows the grid'
        page.locator('[data-make-pick="asset-1"]').click(); page.wait_for_selector('#makeStyleLooks')
        assert page.locator('[data-make-style="look-preset-realvis"]').count() == 1
        sent = generate(); assert not sent and 'Choose the look' in page.locator('#makeStatus').inner_text(), 'no look, no job'
        page.locator('label:has([data-make-style="look-preset-realvis"])').click(); shot('goal-restyle')
        sent = generate(); no_modal(); assert len(sent) == 1, sent; job = sent[0]
        assert job['preset_id'] == 'restyle-klein-picture' and job['continuation']['intent'] == 'restyle' and job['continuation']['source_asset_id'] == 'asset-1', job
        assert job['controls']['last_reference'] == job['continuation']['reference_file'] and job['references'][0]['file'] == UPLOAD and job['references'][0]['role'] == 'style', job
        assert '[' not in job['controls']['positive'] and posted('/api/upload')[-1]['filename'] == 'look-preset-realvis.jpg', job
        assert job['parent_assets'] == ['asset-1'] and job['label'] == 'Make · Restyle a picture', job
        clicks['restyle'] = 4  # goal, picture, look, Generate
        # The words fallback keeps the recipe's keep-clause and fits the canvas to the picture.
        page.locator('[data-make-style-words]').click()
        assert page.locator('#makeF-look').input_value().startswith('Redraw this image as')
        page.locator('#makeF-look').fill('Redraw this image as a soft watercolour'); job = generate()[0]
        assert job['preset_id'] == 'restyle-klein' and job['controls']['positive'].startswith('Redraw this image as a soft watercolour. Keep ') and job['references'] == [], job
        assert job['controls']['reference'] and job['controls']['width'] and job['controls']['height'], job

        # Character in a new pose: two labelled slots, plain fields, never a bracket or a named example.
        goal('combine'); page.wait_for_selector('#makePoseSlot')
        text = page.locator('#makeComposer').inner_text() + ' '.join(page.eval_on_selector_all('#makeComposer [placeholder]', 'n=>n.map(e=>e.placeholder)'))
        assert 'character picture' in text.lower() and 'pose' in text.lower() and '[' not in text and 'e.g.' not in text and 'Ellen' not in text, text
        page.wait_for_selector('[data-make-pose-pick="asset-2"]'); page.locator('[data-make-pose-pick="asset-2"]').click()
        sent = generate(); assert not sent and page.locator('#makeF-who').get_attribute('aria-invalid') == 'true', 'empty fields block before any request'
        for key, words in (('who', 'the lantern keeper, a young elf'), ('clothes', 'a green cloak'), ('pose', 'arms crossed')):
            if page.locator('#makeF-' + key).count(): page.locator('#makeF-' + key).fill(words)
        shot('goal-combine-picture')
        job = generate()[0]; no_modal()
        assert job['preset_id'] == 'combine-klein-9b-copypose' and job['continuation']['intent'] == 'combine', job
        assert job['controls']['last_reference'] == job['continuation']['reference_file'] and job['references'][0]['role'] == 'pose', job
        assert set(job['parent_assets']) == {'asset-1', 'asset-2'} and '[' not in job['controls']['positive'] and 'the lantern keeper' in job['controls']['positive'], job
        clicks['combine'] = 4  # goal, character, pose picture, Generate (+3 fields typed)
        page.locator('label:has([data-make-pose-mode="figure"])').click(); page.locator('label:has([data-make-figure="standing"])').click()
        assert page.locator('#makeF-pose').input_value() == 'standing'
        for key, words in (('who', 'the lantern keeper'), ('clothes', 'a green cloak')):
            if page.locator('#makeF-' + key).count() and not page.locator('#makeF-' + key).input_value(): page.locator('#makeF-' + key).fill(words)
        shot('goal-combine-figure')
        job = generate()[0]
        assert job['preset_id'] == 'combine-klein-9b-skeleton' and job['references'][0]['file'].endswith('_drawn-pose.png') and posted('/api/pose/render'), job
        assert job['parent_assets'] == ['asset-1'] and '[' not in job['controls']['positive'], job

        # Change one thing.
        goal('edit'); page.locator('#makeF-change').fill('give her a red scarf'); shot('goal-edit')
        job = generate()[0]; assert job['preset_id'] == 'flux-edit' and 'give her a red scarf' in job['controls']['positive'] and '[' not in job['controls']['positive'], job
        clicks['edit'] = 3
        # Fix or upscale: the one-press polish route.
        goal('repair'); page.wait_for_selector('[data-make-fix="upscale"]'); page.locator('label:has([data-make-fix="upscale"])').click(); shot('goal-repair')
        job = generate()[0]; assert job['preset_id'] == 'anime-esrgan' and job['continuation']['intent'] == 'repair', job
        clicks['repair'] = 4
        # Animate: motion words and a length with its duration.
        goal('animate'); options = page.locator('#makeClip option').all_inner_texts()
        assert len(options) == 2 and all(' s' in o for o in options), options
        assert not generate() and page.locator('#makeF-motion').get_attribute('aria-invalid') == 'true'
        page.locator('#makeF-motion').fill('she turns her head and smiles'); shot('goal-animate')
        job = generate()[0]; assert job['preset_id'] == 'wan22-i2v' and job['controls']['positive'] == 'she turns her head and smiles' and job['controls']['mode'] == 'quick-diagnostic' and job['controls']['frames'] == 17, job
        clicks['animate'] = 3
        # Picture to 3D: one button.
        goal('mesh'); shot('goal-mesh')
        job = generate()[0]; assert job['preset_id'] == 'trellis-auto-cutout' and job['controls']['reference'] and 'positive' not in job['controls'], job
        clicks['mesh'] = 3
        # The full editor stays one link away on every goal.
        assert page.locator('#makeComposer [data-ux-handoff="asset-1"][data-ux-handoff-intent="mesh"]').count() == 1
        # A result's More menu opens a picture goal here with that picture chosen.
        page.wait_for_selector('[data-more="asset-0"]'); page.locator('[data-more="asset-0"] summary').first.click()
        page.locator('[data-make-from="restyle"][data-asset="asset-0"]').first.click(); page.wait_for_selector('#makeComposer [data-ux-handoff="asset-0"]'); no_modal()
        assert page.locator('#makeGoals [aria-checked=true]').get_attribute('data-make-goal') == 'restyle'

        # Compare looks: three looks, one scene, one press, one card.
        page.locator('[data-make-goal="character"]').click(); page.wait_for_selector('[data-make-look]')
        if page.locator('[data-make-change]').count(): page.locator('[data-make-change]').click()
        page.locator('[data-make-compare]').first.click()
        ids = page.eval_on_selector_all('[data-make-look]', 'n=>n.map(e=>e.dataset.makeLook)')
        for look in ids[:4]: page.locator('[data-make-look="%s"]' % look).click()
        assert page.locator('[data-make-look][aria-checked=true]').count() == 3 and 'at most' in page.locator('#makeStatus').inner_text()
        page.locator('#makeScene').fill('A lantern keeper in a pine wood at dusk')
        page.wait_for_function('document.querySelector("#makeEstimate").textContent.includes("3 pictures")')
        assert page.locator('#makeGenerate').inner_text() == 'Generate 3 pictures'
        shot('compare-composer')
        before = len(jobs()); page.locator('#makeGenerate').click()
        page.wait_for_function('n=>document.querySelector("#makeStatus").textContent.startsWith("Started 3")', timeout=8000)
        sent = jobs()[before:]; assert len(sent) == 3 and all(j['label'].startswith('Make · Compare · ') and j['batch_count'] == 1 for j in sent), sent
        seeds = {j['controls'].get('seed') for j in sent if 'seed' in j['controls']}; assert len(seeds) == 1, seeds
        page.wait_for_function('document.querySelectorAll(".make-compare figure [data-make-review=selected]").length===3', timeout=8000)
        assert page.locator('.make-compare').count() == 1 and page.locator('.make-compare [data-make-review=rejected]').count() == 3
        shot('compare-results', '.make-compare')
        clicks['compare'] = 6  # goal, Compare looks, 3 looks, Generate (+ one scene)
        assert all(p['path'] != '/api/jobs' or p['data'].get('label', '').startswith('Make') for p in fixture.POSTS)
        # The whole library stays searchable: the grid shows the newest 60, and an older picture is found by searching (#1442 review).
        many = [dict(fixture.ASSETS[0], id='old-%02d' % i, title='Picture %02d' % i, prompt_excerpt='scene %02d' % i, filename='p%02d.png' % i, created_at=1000 + i, media_type='image', trashed_at=None, tags=[]) for i in range(65)]
        many[0]['prompt_excerpt'] = 'the oldest lighthouse'
        page.route('**/api/workspace', lambda route: route.fulfill(json={'assets': many}))
        page.goto(origin + '/#make'); page.wait_for_selector('[data-make-goal="edit"]'); page.click('[data-make-goal="edit"]')
        if page.locator('[data-make-repick]').count(): page.click('[data-make-repick]')
        page.locator('[data-make-search="makePictures"]').fill('')
        page.wait_for_function('document.querySelectorAll("#makePictures [data-make-pick]").length===60')
        assert 'older picture' in page.locator('#makePictures').inner_text()
        page.locator('[data-make-search="makePictures"]').fill('lighthouse')
        page.wait_for_function('document.querySelectorAll("#makePictures [data-make-pick]").length===1')
        assert page.locator('#makePictures [data-make-pick="old-00"]').count() == 1
        assert not errors, errors
        browser.close()
    server.shutdown()
    print(json.dumps({'fixture_jobs_posted': len(jobs()), 'real_generation_submissions': 0, 'clicks_to_generate': clicks, 'page_errors': errors}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--screenshots', type=Path, default=ROOT / '.runtime/make-goals')
    run(parser.parse_args().screenshots)
