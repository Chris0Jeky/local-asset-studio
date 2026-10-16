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
SLOW = []  # non-empty: the source context answers slowly, so the page can be changed while Generate runs
CHARACTERS = []  # character cards saved through POST /api/characters, listed as app/characters.py lists them
FAIL_LABEL = []  # a Make job whose label ends with one of these is refused, as a Studio refusal mid-compare would be


class Handler(fixture.Handler):
    def do_GET(self):
        if SLOW and self.path.endswith('/context'): time.sleep(0.8)
        if self.path == '/api/looks': return self.json({'looks': SHIPPED, 'seed_errors': [], 'generation_submitted': False})
        if self.path == '/api/characters': return self.json({'characters': CHARACTERS, 'generation_submitted': False})
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
        if self.path == '/api/characters':
            data = json.loads(self.rfile.read(length)); fixture.POSTS.append({'path': self.path, 'data': data})
            if data['action'] == 'create':
                card = dict(id='character-%d' % len(CHARACTERS), kind='character', name=data['name'], body=data['body'], revision=0, trashed_at=None,
                            lineage=[{'role': 'canon', 'asset_id': data['canon_asset_id'], 'sha256': 'a' * 64}], usable=True, unusable_reason=None, canon_asset_id=data['canon_asset_id'])
                CHARACTERS.append(card); return self.json(card)
            card = next(c for c in CHARACTERS if c['id'] == data['id'])   # edit / trash / restore name the revision they read, as Workspace.card_command checks
            if data['expected_revision'] != card['revision']:
                return self.json({'error': 'This card changed since you read it; nothing changed. Reload it and try again.', 'code': 'card_revision_conflict'}, 409)
            if data['action'] == 'edit': card.update(name=data['name'], body=data['body'])
            else:
                away = data['action'] == 'trash'
                card.update(trashed_at=1789228800 if away else None, usable=not away, unusable_reason='This character is put away. Restore it to use it.' if away else None)
            card['revision'] += 1; return self.json(card)
        if self.path == '/api/jobs':
            data = json.loads(self.rfile.read(length))
            if any(data.get('label', '').endswith(x) for x in FAIL_LABEL): return self.json({'error': 'Fixture refusal'}, 400)
            fixture.POSTS.append({'path': self.path, 'data': data})
            job = dict(data, id='goal-' + str(len(JOBS)), status='queued', created_at=1789228800, outputs=[]); JOBS[job['id']] = job
            return self.json(job)
        return super().do_POST()


def fixture_card(i): return CHARACTERS[i]   # run() assigns its own CHARACTERS (look ids), so the fixture list is reached from here
def no_characters(): CHARACTERS.clear()
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
        # A look picked low in the gallery leaves "Describe your picture" in view below the fixed bar, and every goal chip
        # wraps on screen (audit N8).
        for (width, height), look in (((1440, 900), 'look-anifox-ringeko'), ((390, 844), 'look-wai-fantasy-portrait')):
            page.set_viewport_size({'width': width, 'height': height})
            if page.locator('[data-make-change]').count(): page.locator('[data-make-change]').click()
            page.evaluate('window.scrollTo(0,document.body.scrollHeight)'); page.locator('[data-make-look="%s"]' % look).click()
            heading = page.evaluate('()=>[document.querySelector("#makeComposer .make-step").getBoundingClientRect().top,document.querySelector(".studio-globalbar").getBoundingClientRect().bottom]')
            assert heading[0] >= heading[1], (width, heading)
        page.set_viewport_size({'width': 1440, 'height': 900})
        chips = page.evaluate('()=>[...document.querySelectorAll("[data-make-goal]")].map(e=>e.getBoundingClientRect().right)')
        assert len(chips) == 11 and max(chips) <= page.evaluate('document.documentElement.clientWidth'), chips
        # Honest speed (#1448): the lab's measured median per picture, not the recipe's hopes; a Best for line where the lab backs one;
        # a non-commercial tag only where the recipe's own commercial_note records it.
        card = lambda look: page.locator('.make-look:has([data-make-look="%s"])' % look)
        looks_of('character')
        assert card('look-anima-pearly-petiflow').locator('.make-pace').inner_text() == 'Fast · ~31 s'
        assert 'look lab' in card('look-anima-pearly-petiflow').locator('.make-pace').get_attribute('title')
        assert card('look-anima-pearly-petiflow').locator('.make-best').inner_text().startswith('Best for: Close-ups')
        assert card('look-oneobsession-anima-v20-showcase').locator('.make-licence').inner_text() == 'Non-commercial' and not card('look-anima-pearly-petiflow').locator('.make-licence').count()
        # This PC's finished runs of the look as made outrank the lab; a draft run (other steps) does not count.
        history = [dict(id='h%d' % i, label='Make · Flat pastel close-up', preset_id='anima-v1-baseline', status='completed', elapsed_seconds=secs, batch_count=2, controls=dict(steps=steps)) for i, (secs, steps) in enumerate(((240, 25), (260, 25), (20, 13)))]
        label = page.evaluate('(h)=>{jobs=h;StudioMake.refresh();return document.querySelector(\'.make-look:has([data-make-look="look-anima-pearly-petiflow"]) .make-pace\').textContent}', history)
        assert label == 'Medium · ~125 s', label
        page.evaluate('()=>{jobs=[];StudioMake.refresh();}')
        pick_look('look-anima-pearly-petiflow'); assert page.locator('.make-chosen .make-tested').count() == 1 and page.input_value('#makeShape') == 'portrait'
        assert 'Draft first · 13 steps' in page.locator('#makeDraftBox').inner_text(), 'a 25-step look offers a draft too'
        page.locator('[data-make-change]').click(); assert page.locator('[data-make-keep-look]').inner_text() == 'Stay with Flat pastel close-up', 'the gallery never says Keep'
        page.locator('[data-make-keep-look]').click()
        painting = looks_of('painting')
        assert painting[0] == 'look-anima-painterly-artist-tags' and {'look-krea-atelier-target-stack', 'look-krea-witch-nijisis'} <= set(painting) and painting[-1] == 'look-krea-witch-nijisis', painting
        assert looks_of('scene') == ['look-night-shift-retro-anime', 'look-noob-fantasy-scene', 'look-krea-watercolor-anime']
        assert card('look-night-shift-retro-anime').locator('.make-pace').inner_text() == 'Medium · ~163 s', 'Night Shift is not Fast (#1448)'
        assert card('look-krea-watercolor-anime').locator('.make-pace').inner_text() == 'Slow · ~6 min'
        assert card('look-noob-fantasy-scene').locator('.make-licence').count() == 1, 'NoobAI terms exclude commercial use'
        pick_look('look-night-shift-retro-anime'); assert not page.locator('#makeDraft').count(), 'an 8-step look that is not slow offers no draft'
        pick_look('look-noob-fantasy-scene'); assert page.input_value('#makeShape') == 'landscape', 'a scene is wide by default'
        assert 'As designed · 832×1216' in page.locator('#makeShape option[value=design]').inner_text(), 'As designed stays available'
        page.locator('#makeScene').fill('a misty harbour at dawn'); job = generate()[0]
        assert (job['controls']['width'], job['controls']['height']) == (1216, 832), job['controls']
        assert looks_of('game')[0] == 'look-preset-stylized-prop'; pick_look('look-preset-pixel-lora'); assert page.input_value('#makeShape') == 'square'
        photo = looks_of('photo'); assert photo[:2] == ['look-preset-zimage-fast', 'look-preset-realvis'] and photo[-2:] == ['look-krea-realistic-snapshot', 'look-krea-lenovo-ultrareal'], photo
        names = page.eval_on_selector_all('.make-look-text b', 'n=>n.map(e=>e.textContent)'); assert 'Quick picture, any subject' in names and not any('Fast general' in n for n in names), names
        pick_look('look-preset-zimage-fast'); assert page.input_value('#makeShape') == 'design', 'a goal without a usual shape follows the look'
        # On a phone the new card comes into view after Generate, and the status line is in the Generate bar (audit N2).
        page.set_viewport_size({'width': 390, 'height': 844}); page.locator('#makeScene').fill('a red kite over a beach'); generate()
        seen = page.evaluate('(id)=>{const r=document.querySelector(`[data-run="${id}"]`).getBoundingClientRect();return[r.top<innerHeight&&r.bottom>0,!!document.querySelector("#makeStatus").closest(".make-go")]}', list(JOBS)[-1])
        assert seen == [True, True], seen
        page.set_viewport_size({'width': 1440, 'height': 900})

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
        # The missing answer is marked on the choices, not on their fieldset.
        assert page.locator('#makeStyleLooks').get_attribute('aria-invalid') is None and page.locator('[data-make-style]').first.get_attribute('aria-invalid') == 'true'
        page.locator('label:has([data-make-style="look-preset-realvis"])').click(); shot('goal-restyle')
        assert page.locator('[data-make-style]').first.get_attribute('aria-invalid') is None
        # A look picked while the request is on its way does not change it: the choices were read at the press.
        SLOW.append(1); before = len(jobs()); page.locator('#makeGenerate').click()
        page.locator('label:has([data-make-style="look-preset-zimage-fast"])').click()
        page.wait_for_function('document.querySelector("#makeStatus").textContent.startsWith("Started")', timeout=8000); SLOW.clear(); page.wait_for_function('!document.querySelector("#makeGenerate").disabled')
        sent = jobs()[before:]; no_modal(); assert len(sent) == 1 and posted('/api/upload')[-1]['filename'] == 'look-preset-realvis.jpg', posted('/api/upload')[-1]; job = sent[0]
        page.locator('label:has([data-make-style="look-preset-realvis"])').click()
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
        page.wait_for_selector('[data-make-pose-pick="asset-2"]')
        assert not generate() and 'Choose the pose first' in page.locator('#makeStatus').inner_text(), 'no pose, no job'
        page.locator('[data-make-pose-pick="asset-2"]').click()
        assert 'Choose the pose first' not in page.locator('#makeStatus').inner_text(), 'the pose reminder clears once the pose is chosen (audit N10)'
        sent = generate(); assert not sent and page.locator('#makeF-who').get_attribute('aria-invalid') == 'true', 'empty fields block before any request'
        for key, words in (('who', 'the lantern keeper, a young elf'), ('clothes', 'a green cloak'), ('pose', 'arms crossed')):
            if page.locator('#makeF-' + key).count(): page.locator('#makeF-' + key).fill(words)
        shot('goal-combine-picture')
        job = generate()[0]; no_modal()
        assert job['preset_id'] == 'combine-klein-9b-copypose' and job['continuation']['intent'] == 'combine', job
        assert job['controls']['last_reference'] == job['continuation']['reference_file'] and job['references'][0]['role'] == 'pose', job
        assert set(job['parent_assets']) == {'asset-1', 'asset-2'} and '[' not in job['controls']['positive'] and 'the lantern keeper' in job['controls']['positive'], job
        clicks['combine'] = 4  # goal, character, pose picture, Generate (+3 fields typed)
        # Route from lab round 3 (PR #1481): Copy Pose is the default, "Put my character into this picture's scene" is Replace character;
        # each says what it keeps, and the pose field shows the lab's tested wording as its placeholder (never prefilled).
        assert page.is_checked('#makePoseRoute-copy') and 'face, clothes, background' in page.locator('#makePoseRouteHint-copy').inner_text()
        assert 'outfit, setting' in page.locator('#makePoseRouteHint-scene').inner_text() and page.locator('label:has(#makePoseRoute-scene)').inner_text().strip() == 'Put my character into this picture’s scene'
        assert page.get_attribute('#makeF-pose', 'placeholder') == 'holding one bamboo flute with both hands at chest height, front view, medium shot'
        page.locator('label:has(#makePoseRoute-scene)').click(); page.wait_for_selector('#makeF-outfit')
        assert page.is_checked('#makePoseRoute-scene') and 'only the person changes' in page.locator('#makePoseSlot').inner_text()
        page.locator('#makeF-outfit').fill('a long teal hanfu'); job = generate()[0]; no_modal()
        assert job['preset_id'] == 'combine-klein-9b-replace' and job['references'][0]['role'] == 'composition' and 'a long teal hanfu' in job['controls']['positive'], job
        # Edit and re-run on a pose run puts back its picture, pose, answers and route (wave 6 ask), and sends nothing.
        replace_id = list(JOBS)[-1]; page.wait_for_selector('[data-make-redo="%s"]' % replace_id); before = len(jobs())
        page.locator('label:has(#makePoseRoute-copy)').click(); page.locator('#makeF-who').fill('someone else')
        page.locator('[data-make-redo="%s"]' % replace_id).click(); page.wait_for_selector('#makeF-outfit')
        assert page.is_checked('#makePoseRoute-scene') and page.input_value('#makeF-outfit') == 'a long teal hanfu' and page.input_value('#makeF-who') == 'the lantern keeper, a young elf', page.input_value('#makeF-who')
        assert page.locator('#makePoseSlot [data-make-pose-change]').count() == 1 and len(jobs()) == before and 'answers are back' in page.locator('#makeStatus').inner_text()
        assert page.evaluate('(id)=>JSON.parse(localStorage.getItem("studio.make")).runs.find(r=>r.id===id).redo.poseRoute', replace_id) == 'scene', 'the route is stored with the run'
        page.locator('label:has(#makePoseRoute-copy)').click(); assert page.is_checked('#makePoseRoute-copy') and not page.locator('#makePoseFallback').count()
        # Copy Pose's model missing: the next picture route Make offers (never depth or plain 9B), and the page says why.
        page.route('**/api/health', lambda route: route.fulfill(json=dict(online=True, schema_available=True, missing_models={'combine-klein-9b-copypose': ['diffusion_models/copy-pose.safetensors']}, devices=[])))
        page.evaluate('health()'); page.wait_for_function('!!missingByPreset["combine-klein-9b-copypose"]')
        page.locator('label:has(#makePoseRoute-scene)').click(); page.locator('label:has(#makePoseRoute-copy)').click()
        why = page.locator('#makePoseFallback').inner_text()
        assert 'Copy Pose needs 1 model file first' in why and 'Klein 4B' in why and page.locator('#makePoseFallback a[href*="combine-klein-9b-copypose"]').count() == 1, why
        job = generate()[0]; assert job['preset_id'] == 'combine-klein', job
        page.unroute('**/api/health'); page.evaluate('health()'); page.wait_for_function('!missingByPreset["combine-klein-9b-copypose"]')
        page.locator('label:has([data-make-pose-mode="figure"])').click(); page.locator('label:has([data-make-figure="standing"])').click()
        assert page.locator('#makeF-pose').input_value() == 'standing'
        assert 'crossed legs on the bent figure' in page.locator('#makeFigureHint').inner_text() and not page.locator('#makePoseRoute-copy').count(), 'the figure route keeps its own hint, no picture routes'
        for key, words in (('who', 'the lantern keeper'), ('clothes', 'a green cloak')):
            if page.locator('#makeF-' + key).count() and not page.locator('#makeF-' + key).input_value(): page.locator('#makeF-' + key).fill(words)
        shot('goal-combine-figure')
        job = generate()[0]
        assert job['preset_id'] == 'combine-klein-9b-skeleton' and job['references'][0]['file'].endswith('_drawn-pose.png') and posted('/api/pose/render'), job
        assert job['parent_assets'] == ['asset-1'] and '[' not in job['controls']['positive'], job

        # My character (#1205 v1): a kept picture becomes the canon of a saved character, its words prefilled from the pose run;
        # saving makes no picture. Character in a new pose then lists it first, and choosing it sends the canon as it is with its words.
        pose_card = page.locator('[data-run="%s"]' % list(JOBS)[-1]); pose_card.locator('[data-make-review="selected"][data-asset="asset-0"]').wait_for(timeout=8000)
        assert not page.locator('[data-make-character-save]').count(), 'only a kept picture offers it'
        page.evaluate('()=>{assetState.assets.find(a=>a.id==="asset-0").review="selected";StudioMake.refresh();}')
        before = len(jobs()); pose_card.locator('[data-make-character-save="asset-0"]').click()
        form = pose_card.locator('.make-character-form')
        prefill = (form.locator('[data-make-char="who"]').input_value(), form.locator('[data-make-char="clothes"]').input_value())
        assert prefill == ('the lantern keeper, a young elf', 'a green cloak'), prefill
        form.locator('[type=submit]').click(); assert 'Name the character first' in page.locator('#makeStatus').inner_text() and not posted('/api/characters')
        form.locator('[data-make-char="name"]').fill('Mira'); form.locator('[data-make-char="who"]').fill('Mira, a lantern keeper with silver hair')
        form.locator('[data-make-char="clothes"]').fill('a moss-green cloak with brass buttons'); shot('character-save', '.make-character-form')
        form.locator('[type=submit]').click(); page.wait_for_function('document.querySelector("#makeStatus").textContent.startsWith("Saved")')
        assert posted('/api/characters') == [{'action': 'create', 'kind': 'character', 'name': 'Mira', 'canon_asset_id': 'asset-0',
                                              'body': {'who': 'Mira, a lantern keeper with silver hair', 'clothes': 'a moss-green cloak with brass buttons'}}], posted('/api/characters')
        assert len(jobs()) == before, 'saving a character submits nothing'
        assert page.locator('.make-canon').first.inner_text() == 'Canon of Mira' and not page.locator('.make-character-form').count()
        page.locator('[data-make-goal="combine"]').click(); page.wait_for_selector('#makePoseSlot'); page.locator('#makeComposer [data-make-repick]').click()
        page.wait_for_selector('[data-make-character="character-0"]'); shot('character-pick', '.make-characters')
        assert page.evaluate('document.querySelector(".make-characters").compareDocumentPosition(document.querySelector("#makePictures"))&Node.DOCUMENT_POSITION_FOLLOWING'), 'Your characters come first'
        before = len(jobs()); page.locator('[data-make-character="character-0"]').click(); page.wait_for_selector('#makePoseSlot')
        assert len(jobs()) == before, 'choosing a character submits nothing'
        assert (page.input_value('#makeF-who'), page.input_value('#makeF-clothes')) == ('Mira, a lantern keeper with silver hair', 'a moss-green cloak with brass buttons')
        assert 'Your character Mira' in page.locator('#makePoseSlot').evaluate('e=>e.previousElementSibling.textContent')
        if page.locator('#makeF-pose').count() and not page.input_value('#makeF-pose'): page.locator('#makeF-pose').fill('standing')
        job = generate()[0]; no_modal()
        assert job['continuation']['source_asset_id'] == 'asset-0' and job['parent_assets'][0] == 'asset-0', job
        assert 'Mira, a lantern keeper with silver hair' in job['controls']['positive'] and 'a moss-green cloak with brass buttons' in job['controls']['positive'], job['controls']['positive']
        clicks['character'] = 4  # goal, Change picture, the character, Generate (the pose kept or one word typed)

        # Manage characters (#1205 v2): Edit, Put away / Restore (revision-checked: a 409 reloads and changes nothing), and a read-only
        # Line-up per character, canon pinned first, then kept pictures that descend from it. None of it submits.
        before_manage = len(jobs()); kept_state = [(a['review'], a['lineage']) for a in fixture.ASSETS]
        fixture.ASSETS[4].update(review='selected', lineage=['asset-0'])   # a kept picture made from the canon
        fixture.ASSETS[3].update(review='selected', lineage=['asset-4'])   # a kept edit of that one: listed after it, so the chain needs a second pass
        fixture.ASSETS[2].update(lineage=['asset-0'])                      # made from the canon but needs work: not kept, not in the line-up

        def open_picker():
            page.locator('[data-make-goal="combine"]').click(); page.wait_for_selector('#makePoseSlot,[data-make-pick]')
            if page.locator('#makeComposer [data-make-repick]').count(): page.locator('#makeComposer [data-make-repick]').click()
            page.wait_for_selector('.make-characters')
        open_picker(); sc = '[data-open-key="lineup:character-0"]'
        assert page.locator(sc).count() == 1 and not page.locator(sc).evaluate('e=>e.open'), 'the line-up is a closed disclosure'
        page.locator(sc + ' summary').click(); page.wait_for_selector(sc + ' .make-lineup-item')
        page.wait_for_function('s=>[...document.querySelectorAll(s+" img")].every(i=>i.complete&&i.naturalWidth>0)', arg=sc)
        order = page.eval_on_selector_all(sc + ' .make-lineup-item', 'n=>n.map(e=>e.dataset.uxOpenAsset)')
        assert order == ['asset-0', 'asset-3', 'asset-4'], order   # canon first, then kept descendants newest first; asset-1 (unrelated) and asset-2 (not kept) stay out
        heights = page.eval_on_selector_all(sc + ' .make-lineup-item img', 'n=>n.map(e=>Math.round(e.getBoundingClientRect().height))')
        assert len(set(heights)) == 1 and heights[0] > 0, heights
        assert page.locator(sc + ' .make-lineup-item').first.inner_text().strip() == 'Canon'; shot('character-lineup', '.make-characters')
        page.locator(sc + ' .make-lineup-item').nth(1).click(); page.wait_for_function('document.querySelector("#assetDialog")?.open', timeout=5000)
        page.evaluate('document.querySelector("#assetDialog").close()')
        # Bounded at 24 kept pictures behind the canon, with the rest named.
        extra = [dict(fixture.ASSETS[0], id='lineup-%02d' % i, title='Lineup %02d' % i, filename='l%02d.png' % i, created_at=1789000000 + i, review='selected', lineage=['asset-0'], tags=[]) for i in range(26)]
        fixture.ASSETS.extend(extra); open_picker()
        page.wait_for_function('s=>document.querySelectorAll(s+" .make-lineup-item").length===25', arg=sc)
        assert '4 older kept pictures not shown' in page.locator(sc).inner_text(), page.locator(sc).inner_text()
        del fixture.ASSETS[-26:]
        assert len(jobs()) == before_manage, 'the line-up submits nothing'
        # Edit: the words and the avoid words; a stale revision (changed elsewhere) reloads the card and saves nothing.
        page.locator('[data-make-character-edit="character-0"]').click(); form = page.locator('.make-characters .make-character-form')
        assert [form.locator('[data-make-char="%s"]' % k).input_value() for k in ('name', 'who', 'clothes', 'avoid')] == ['Mira', 'Mira, a lantern keeper with silver hair', 'a moss-green cloak with brass buttons', ''], 'Edit shows the stored words'
        form.locator('[data-make-char="avoid"]').fill('glasses, hat'); shot('character-edit', '.make-characters')
        form.locator('[data-make-character-cancel]').click(); assert not page.locator('.make-character-form').count() and len(posted('/api/characters')) == 1, 'Cancel saves nothing'
        assert page.evaluate('document.activeElement.dataset.makeCharacterEdit') == 'character-0'
        page.locator('[data-make-character-edit="character-0"]').click(); form = page.locator('.make-characters .make-character-form')
        form.locator('[data-make-char="avoid"]').fill('glasses, hat'); fixture_card(0).update(name='Mira (renamed elsewhere)', revision=1)
        form.locator('[type=submit]').click(); page.wait_for_function('document.querySelector("#makeStatus")?.textContent.includes("changed somewhere else")')
        assert posted('/api/characters')[-1]['expected_revision'] == 0 and fixture_card(0)['body'].get('avoid') is None, 'a stale edit changes nothing'
        assert not page.locator('.make-character-form').count() and 'Mira (renamed elsewhere)' in page.locator('[data-make-character="character-0"]').inner_text(), 'the card is reloaded'
        page.locator('[data-make-character-edit="character-0"]').click(); form = page.locator('.make-characters .make-character-form')
        form.locator('[data-make-char="name"]').fill('Mira'); form.locator('[data-make-char="clothes"]').fill('a moss-green cloak, brass buttons, mud on the hem'); form.locator('[data-make-char="avoid"]').fill('glasses, hat')
        form.locator('[type=submit]').click(); page.wait_for_function('document.querySelector("#makeStatus")?.textContent.startsWith("Saved the changes")')
        assert posted('/api/characters')[-1] == {'action': 'edit', 'id': 'character-0', 'expected_revision': 1, 'name': 'Mira', 'body': {'who': 'Mira, a lantern keeper with silver hair', 'clothes': 'a moss-green cloak, brass buttons, mud on the hem', 'avoid': 'glasses, hat'}}, posted('/api/characters')[-1]
        assert 'glasses' not in page.locator('.make-characters').inner_text(), 'avoid words are stored, not shown'
        assert page.evaluate('document.activeElement.dataset.makeCharacterEdit') == 'character-0'
        # Avoid words ride only where the goal's request already has a negative field.
        page.locator('[data-make-character="character-0"]').click(); page.wait_for_selector('#makePoseSlot')
        if page.locator('#makeF-pose').count() and not page.input_value('#makeF-pose'): page.locator('#makeF-pose').fill('standing')
        job = generate()[0]
        assert 'negative' not in job['controls'] and 'glasses' not in json.dumps(job), 'this goal’s request has no negative field: the avoid words stay unused, silently'
        # No Make goal's recipe carries a negative today (one does when it binds a negative and continues from the source's description),
        # so give this one both, page-side only, to prove the append.
        page.evaluate("()=>{const p=catalog.presets.find(p=>p.id==='combine-klein-9b-skeleton');window.keepRole=p.continuation_capability.prompt_role;p.negative=['9','text'];p.continuation_capability.prompt_role='description';}")
        job = generate()[0]; page.evaluate("()=>{const p=catalog.presets.find(p=>p.id==='combine-klein-9b-skeleton');delete p.negative;p.continuation_capability.prompt_role=window.keepRole;}")
        assert job['controls']['negative'] == 'blur, glasses, hat' and 'glasses' not in job['controls']['positive'], job['controls']
        # Put away hides it from the chooser; Restore (under "Put away (n)") brings it back. A stale revision changes nothing.
        open_picker(); fixture_card(0)['revision'] += 1
        page.locator('[data-make-character-away="character-0"]').click(); page.wait_for_function('document.querySelector("#makeStatus")?.textContent.includes("changed somewhere else")')
        assert fixture_card(0)['trashed_at'] is None and page.locator('[data-make-character="character-0"]').count() == 1, 'a stale Put away changes nothing'
        page.locator('[data-make-character-away="character-0"]').click(); page.wait_for_function('document.querySelectorAll("[data-make-character]").length===0')
        assert posted('/api/characters')[-1] == {'action': 'trash', 'id': 'character-0', 'expected_revision': 3}, posted('/api/characters')[-1]
        assert 'All your characters are put away' in page.locator('.make-characters').inner_text() and page.locator('.make-away summary').inner_text() == 'Put away (1)'
        assert page.evaluate('document.activeElement.tagName') == 'SUMMARY', 'focus lands on the Put away disclosure'
        page.locator('.make-away summary').click(); shot('character-away', '.make-characters')
        page.locator('[data-make-character-restore="character-0"]').click(); page.wait_for_selector('[data-make-character="character-0"]')
        assert posted('/api/characters')[-1] == {'action': 'restore', 'id': 'character-0', 'expected_revision': 4} and not page.locator('.make-away').count()
        assert page.evaluate('document.activeElement.dataset.makeCharacter') == 'character-0'
        assert len(jobs()) == before_manage + 2, 'managing characters submitted nothing (the two jobs are the avoid-words checks)'
        for a, (review, lineage) in zip(fixture.ASSETS, kept_state): a.update(review=review, lineage=lineage)

        # Change one thing.
        goal('edit'); page.locator('#makeF-change').fill('give her a red scarf'); shot('goal-edit')
        job = generate()[0]; assert job['preset_id'] == 'flux-edit' and 'give her a red scarf' in job['controls']['positive'] and '[' not in job['controls']['positive'], job
        clicks['edit'] = 3
        # Fix or upscale: the one-press polish route.
        # A fix that cannot run here is not preselected, cannot be chosen, and its reason speaks Make's words (audit N9).
        page.evaluate('''()=>{window.realPlan=StudioWorkbench.polishPlan;StudioWorkbench.polishPlan=(id,kind)=>kind==="face"&&id==="asset-1"?Promise.resolve({ok:false,reason:"Fix face repaints with an anime model, which does not match Z-Image. Use Continue with this."}):window.realPlan(id,kind);}''')
        goal('repair'); page.wait_for_selector('#makeFixWhy-face')
        assert page.is_checked('[data-make-fix="details"]') and page.is_disabled('[data-make-fix="face"]') and not page.is_disabled('#makeGenerate')
        why = page.locator('#makeFixWhy-face').inner_text(); assert 'Continue with this' not in why and 'Change a picture' in why, why
        page.evaluate('()=>{StudioWorkbench.polishPlan=window.realPlan;}')
        page.wait_for_selector('[data-make-fix="upscale"]'); page.locator('label:has([data-make-fix="upscale"])').click(); shot('goal-repair')
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
        # From the second look on, the scene box comes into view with the keyboard in it (audit v3 N4); unchoosing keeps focus on the card.
        third = page.eval_on_selector_all('[data-make-look][aria-checked=true]', 'n=>n.map(e=>e.dataset.makeLook)')[-1]
        page.locator('[data-make-look="%s"]' % third).click(); assert page.evaluate('document.activeElement.dataset.makeLook') == third
        page.evaluate('window.scrollTo(0,0)'); page.locator('[data-make-look="%s"]' % third).click()
        page.wait_for_function('document.activeElement.id==="makeScene"&&(r=>r.top>=0&&r.bottom<=innerHeight)(document.querySelector("#makeComposer .make-step").getBoundingClientRect())', timeout=3000)
        assert 'Three looks chosen' in page.locator('#makeStatus').inner_text()
        page.locator('#makeScene').fill('A lantern keeper in a pine wood at dusk')
        page.wait_for_function('document.querySelector("#makeEstimate").textContent.includes("3 pictures")')
        assert page.locator('#makeGenerate').inner_text() == 'Generate 3 pictures'
        shot('compare-composer')
        before = len(jobs()); page.locator('#makeGenerate').click()
        page.wait_for_function('n=>document.querySelector("#makeStatus")?.textContent.startsWith("Started 3")', timeout=8000)
        sent = jobs()[before:]; assert len(sent) == 3 and all(j['label'].startswith('Make · Compare · ') and j['batch_count'] == 1 for j in sent), sent
        seeds = {j['controls'].get('seed') for j in sent if 'seed' in j['controls']}; assert len(seeds) == 1, seeds
        page.wait_for_function('document.querySelectorAll(".make-compare figure [data-make-review=selected]").length===3', timeout=8000)
        assert page.locator('.make-compare').count() == 1 and page.locator('.make-compare [data-make-review=rejected]').count() == 3
        shot('compare-results', '.make-compare')
        clicks['compare'] = 6  # goal, Compare looks, 3 looks, Generate (+ one scene)
        # A refusal mid-compare says how many started and that the rest were not sent.
        FAIL_LABEL.append(page.eval_on_selector_all('[data-make-look][aria-checked=true]', 'n=>n.map(e=>e.closest(".make-look").querySelector("b").textContent)')[1])
        before = len(jobs()); page.locator('#makeGenerate').click()
        page.wait_for_function('document.querySelector("#makeStatus")?.textContent.startsWith("Started 1 of 3")', timeout=8000); FAIL_LABEL.clear()
        assert len(jobs()) == before + 1 and 'the rest were not sent' in page.locator('#makeStatus').inner_text(), page.locator('#makeStatus').inner_text()
        # A picture goal whose copied reference does not match the verified source sends nothing.
        page.route('**/api/assets/reference', lambda route: route.fulfill(json={'file': 'x' * 32 + '_ref.png', 'sha256': '0' * 64, 'parent_asset': 'asset-1', 'context': {}}))
        goal('edit'); page.locator('#makeF-change').fill('give her a hat'); before = len(jobs())
        page.locator('#makeGenerate').click(); page.wait_for_function('document.querySelector("#makeStatus")?.textContent.includes("Nothing was sent")', timeout=5000)
        assert len(jobs()) == before, 'a mismatched copy sends no job'
        page.unroute('**/api/assets/reference')
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
        # Your pictures first (audit v3 N1): agent-run pictures (a run label not starting "Make · ") wait behind Show all, as the Library's Mine.
        # Each card names its look or recipe, its age and seed (N5). A new browser starts Your pictures from the library's Make runs (N6).
        now = int(time.time())
        base = dict(fixture.ASSETS[0], media_type='image', trashed_at=None, tags=[], lineage=[])
        mixed = [dict(base, id='mine-make', title='Make · 1', prompt_excerpt='pixel art inventory icon, a red potion', run_label='Make · Flat pastel close-up', job_id='seeded-1', created_at=now - 120, source={'seed': 7}),
                 dict(base, id='mine-plain', title='Imported', prompt_excerpt='pixel art inventory icon, a red potion', created_at=now - 7200, source={'seed': 8})]
        mixed += [dict(base, id='lab-%d' % i, title='Lab %d' % i, prompt_excerpt='pixel art inventory icon, lab sword %d' % i, run_label='Lab 1016c', created_at=now - i, source={'seed': i}) for i in range(5)]
        seeded_job = dict(id='seeded-1', status='completed', label='Make · Flat pastel close-up', preset_id='anima-portrait', created_at=now - 120, batch_count=1, controls={'positive': 'pixel art inventory icon, a red potion', 'seed': 7},
                          outputs=[dict(filename='out.png', asset_id='mine-make', media_type='image')])
        other = browser.new_page(viewport={'width': 1440, 'height': 900}); other.on('pageerror', lambda e: errors.append(str(e)))
        other.route('**/api/workspace', lambda route: route.fulfill(json={'assets': mixed}))
        other.route('**/api/jobs/seeded-1', lambda route: route.fulfill(json=seeded_job))
        other.goto(origin + '/#make'); other.wait_for_selector('.make-run[data-run="seeded-1"]', timeout=8000)
        assert other.evaluate('JSON.parse(localStorage.getItem("studio.make")).runs.map(r=>r.id)') == ['seeded-1'], 'the seeded run is kept in this browser'
        assert other.locator('.make-run[data-run="seeded-1"] [data-make-review]').count() == 2, 'Keep and Not this work on a seeded run'
        other.click('[data-make-goal="edit"]'); other.wait_for_selector('#makePictures [data-make-pick]')
        assert other.eval_on_selector_all('#makePictures [data-make-pick]', 'n=>n.map(e=>e.dataset.makePick)') == ['mine-make', 'mine-plain']
        toggle = other.locator('[data-make-all="makePictures"]')
        assert toggle.is_visible() and toggle.inner_text() == 'Show all pictures (5 more from agent runs)' and toggle.get_attribute('aria-pressed') == 'false'
        meta = other.eval_on_selector_all('#makePictures .make-pic-meta', 'n=>n.map(e=>e.textContent)')
        assert meta[0] == 'Flat pastel close-up · 2 min ago · seed 7' and meta[1] == 'Synthetic UX fixture · 2 h ago · seed 8', meta
        assert 'pixel art inventory icon, a red potion' in other.get_attribute('[data-make-pick="mine-make"]', 'title')
        other.fill('[data-make-search="makePictures"]', 'sword')
        assert 'No picture matches' in other.locator('#makePictures').inner_text() and '5 from agent runs do' in other.locator('#makePictures').inner_text()
        toggle.click(); other.wait_for_function('document.querySelectorAll("#makePictures [data-make-pick]").length===5')
        assert toggle.inner_text() == 'Show only my pictures' and toggle.get_attribute('aria-pressed') == 'true' and other.evaluate('document.activeElement.dataset.makeAll') == 'makePictures'
        other.fill('[data-make-search="makePictures"]', ''); other.wait_for_function('document.querySelectorAll("#makePictures [data-make-pick]").length===7')
        toggle.click(); other.wait_for_function('document.querySelectorAll("#makePictures [data-make-pick]").length===2')
        other.close()
        # One-time migration (#1205 v2): Combine's old who / clothes answers live in one browser's localStorage (studio-fills:<picture>). When no
        # character exists, a dismissible note offers to save one from a kept picture that still has them. Never automatic; dismissal is remembered.
        no_characters(); legacy = {'@who': 'the lantern keeper, a young elf', '@clothes': 'a green cloak'}
        seed = "localStorage.setItem('studio-fills:asset-1', %s);localStorage.setItem('studio-fills:asset-0', %s)" % (json.dumps(json.dumps(legacy)), json.dumps(json.dumps(legacy)))  # asset-0 is not kept

        def note_page():
            extra = browser.new_page(viewport={'width': 1440, 'height': 900}); extra.on('pageerror', lambda e: errors.append(str(e))); extra.add_init_script(seed)
            extra.goto(origin + '/#make'); extra.wait_for_function('!!catalog?.presets?.length&&!!window.StudioWorkbench?.polish'); extra.locator('[data-make-goal="edit"]').click()
            extra.wait_for_selector('[data-make-pick]'); return extra
        before_note = len(jobs()); fresh = note_page(); fresh.wait_for_selector('#makeCharNote .make-note')
        assert fresh.locator('[data-make-migrate]').evaluate_all('n=>n.map(e=>e.dataset.makeMigrate)') == ['asset-1'], 'only a kept picture with remembered answers is offered'
        assert not fresh.locator('.make-characters').count(), 'no character yet'
        fresh.locator('[data-make-migrate="asset-1"]').click(); nform = fresh.locator('#makeCharNote .make-character-form')
        assert (nform.locator('[data-make-char="who"]').input_value(), nform.locator('[data-make-char="clothes"]').input_value()) == (legacy['@who'], legacy['@clothes'])
        posts_before = len(posted('/api/characters')); nform.locator('[type=submit]').click()
        fresh.wait_for_function('document.querySelector("#makeStatus")?.textContent.includes("Name the character first")'); assert len(posted('/api/characters')) == posts_before
        nform.locator('[data-make-char="name"]').fill('Wren'); nform.locator('[type=submit]').click(); fresh.wait_for_function('document.querySelector("#makeStatus")?.textContent.startsWith("Saved")')
        assert posted('/api/characters')[-1] == {'action': 'create', 'kind': 'character', 'name': 'Wren', 'canon_asset_id': 'asset-1', 'body': {'who': legacy['@who'], 'clothes': legacy['@clothes']}}
        assert not fresh.locator('.make-note').count() and fresh.locator('[data-make-character="character-0"]').count() == 1, 'saved: the note goes and the character is listed'
        fresh.close()
        no_characters(); fresh = note_page(); fresh.wait_for_selector('#makeCharNote .make-note')
        fresh.locator('[data-make-note-dismiss]').click(); assert not fresh.locator('.make-note').count()
        assert fresh.evaluate('localStorage.getItem("studio.make.character-note")') == 'dismissed'
        fresh.locator('[data-make-goal="restyle"]').click(); fresh.wait_for_selector('[data-make-pick]'); fresh.reload(); fresh.wait_for_selector('[data-make-goal="edit"]'); fresh.locator('[data-make-goal="edit"]').click(); fresh.wait_for_selector('[data-make-pick]'); fresh.wait_for_timeout(300)
        assert not fresh.locator('.make-note').count(), 'a dismissed note is not offered again'
        assert len(jobs()) == before_note, 'the migration note submits nothing'
        fresh.close()
        assert not errors, errors
        browser.close()
    server.shutdown()
    print(json.dumps({'fixture_jobs_posted': len(jobs()), 'real_generation_submissions': 0, 'clicks_to_generate': clicks, 'page_errors': errors}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--screenshots', type=Path, default=ROOT / '.runtime/make-goals')
    run(parser.parse_args().screenshots)
