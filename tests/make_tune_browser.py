"""Make's Tune this look (owner ask, 16 Oct 2026): switch the model to a compatible one, change and add adapters, steps,
negative and a locked seed; Generate sends exactly those settings, the run card names them, and Edit and re-run brings them
back. Never a model call: /api/jobs is answered by the fixture and recorded.

python tests/make_tune_browser.py
Fixture server from studio_browser_smoke (real frontend, synthetic API, real catalog, looks and settings knowledge).
"""
import json
import threading
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
import studio_browser_smoke as fixture
from browser_ports import browser_server

ROOT = fixture.ROOT
import looks  # noqa: E402  (studio_browser_smoke puts app/ on sys.path)

SHIPPED = [dict(entry, origin='seed', revision=0, trashed_at=None, usable=True, unusable_reason=None, anchor_asset_id=None)
           for entry in json.loads((ROOT / looks.SEEDS).read_text(encoding='utf-8'))['looks']]
KNOWLEDGE = json.loads((ROOT / 'presets/settings-kb.json').read_text(encoding='utf-8'))
INSTALLED = sorted(KNOWLEDGE['loras'])  # synthetic inventory: every adapter the knowledge base describes
LOOK, BASE, SWITCH, ADDED, FOREIGN = 'look-anima-pearly-petiflow', 'anima-v1-baseline', 'pearly-anima-mix-v10-baseline', 'anima-koukouya_v2_step2500.safetensors', 'Niji_Sweet_Spot_Krea2_v2A.safetensors'
SCENE = 'an adult knight resting by a campfire in a snowy forest'
JOB = {'id': 'tune-job', 'status': 'queued', 'message': 'Queued (fixture, no model run)', 'outputs': [], 'batch_count': 1}


class Handler(fixture.Handler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/looks': return self.json({'looks': SHIPPED, 'seed_errors': [], 'generation_submitted': False})
        if path == '/api/knowledge': return self.json(KNOWLEDGE)
        if path == '/api/options': return self.json({'loras': INSTALLED})
        if path == '/api/jobs/' + JOB['id']: return self.json(JOB)
        return super().do_GET()

    def do_POST(self):
        if self.path not in ('/api/looks/prepare', '/api/jobs'): return super().do_POST()
        data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
        fixture.POSTS.append({'path': self.path, 'data': data})
        if self.path == '/api/jobs': return self.json(JOB)
        look = next(entry for entry in SHIPPED if entry['id'] == data['id'])
        return self.json({'preset_id': look['body']['preset_id'], 'controls': {'positive': looks.compose(look['body']['template'], data['scene']), **look['body']['controls']},
                          'look': {'id': look['id'], 'name': look['name'], 'revision': 0}, 'generation_submitted': False})


def posted(path):
    return [p['data'] for p in fixture.POSTS if p['path'] == path]


def run():
    server = browser_server(Handler); threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = 'http://127.0.0.1:' + str(server.server_port); errors = []
    presets = {p['id']: p for p in fixture.CATALOG['presets']}
    shipped = next(entry for entry in SHIPPED if entry['id'] == LOOK)['body']
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True); page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(origin + '/#make'); page.wait_for_function('catalog?.presets?.length && knowledge?.loras && installedLoras.length && document.querySelector("[data-make-goal]")')
            page.click('[data-make-goal="character"]'); page.click('[data-make-look="%s"]' % LOOK)
            assert page.evaluate('!document.querySelector("#makeTune").open'), 'Tune is folded shut by default'
            page.click('#makeTune > summary')
            offered = page.eval_on_selector_all('#makeModel option', 'o => o.map(x => x.value)')
            assert offered[0] == BASE and SWITCH in offered and 'oneobsession-anima-v20-baseline' in offered, offered
            for wrong in ('anima-artist-stack', 'janima-v1-baseline', 'anima-portrait', 'wai', 'krea-anime-atelier'):
                assert wrong not in offered, (wrong, offered)  # same file, too few slots, no adapter slots, other model types
            page.select_option('#makeModel', SWITCH)
            assert 'Tuned: model Pearly Anima Mix' in page.text_content('#makeTuneSum'), page.text_content('#makeTuneSum')
            page.evaluate('() => { const r = document.querySelector("[data-tune-strength=lora]"); r.value = "0.7"; r.dispatchEvent(new Event("input", {bubbles: true})); }')
            listed = page.eval_on_selector_all('#makeLoraList option', 'o => o.map(x => x.value)')
            assert ADDED in listed and FOREIGN not in listed, 'only adapters made for this model type are offered'
            page.fill('#makeLoraSearch', FOREIGN); page.click('[data-tune-add]')
            assert 'not an installed adapter for this model type' in page.text_content('#makeStatus') and not page.query_selector('[data-slot=lora2]')
            page.fill('#makeLoraSearch', ADDED); page.click('[data-tune-add]')
            assert page.query_selector('[data-slot=lora2]') and '@40u40uya' in page.text_content('[data-slot=lora2] small'), 'added row shows its trigger'
            page.select_option('[data-tune=steps]', index=1)
            page.fill('#makeNegative', 'extra hands')
            page.uncheck('#makeNewSeed'); page.fill('#makeSeed', '1234')
            page.fill('#makeScene', SCENE)
            assert not posted('/api/jobs'), 'tuning never submits'
            page.click('#makeGenerate'); page.wait_for_function('document.querySelector(".make-run .make-tuned")')
            jobs = posted('/api/jobs'); assert len(jobs) == 1, jobs
            job, steps = jobs[0], max(1, round(shipped['controls']['steps'] / 2 + 1e-9))
            c = job['controls']
            assert job['preset_id'] == SWITCH, job['preset_id']
            assert (c['lora'], c['lora_name'], c['lora2'], c['lora2_name']) == (0.7, shipped['controls']['lora_name'], KNOWLEDGE['loras'][ADDED]['default'], ADDED), c
            assert all(c[k] == 0 for k in ('lora3', 'lora4', 'lora5', 'lora6')), 'a switched model keeps none of its own authored adapters'
            assert (c['steps'], c['negative'], c['seed']) == (steps, 'extra hands', 1234), c
            assert c['positive'].startswith('@40u40uya, ') and SCENE in c['positive'], c['positive']
            target = presets[SWITCH]; bound = {k for k in c if target.get(k) or (target.get('bindings_extra') or {}).get(k)}
            assert bound == set(c), ('only inputs the target recipe binds', set(c) - bound)
            tuned = page.text_content('.make-run .make-tuned')
            assert all(part in tuned for part in ('model Pearly Anima Mix', '+', '%d steps' % steps, 'own negative', 'seed 1234 locked')), tuned
            # Back to the look as made, then Edit and re-run: the run's tune comes back with its look.
            page.click('[data-tune-reset]'); assert page.input_value('#makeModel') == BASE and not page.query_selector('[data-slot=lora2]')
            page.click('[data-make-rerun="%s"]' % JOB['id'])
            assert page.input_value('#makeModel') == SWITCH and page.query_selector('[data-slot=lora2]'), 'Edit and re-run restores the tune'
            assert not page.is_checked('#makeNewSeed') and page.input_value('#makeSeed') == '1234' and page.input_value('#makeScene') == SCENE
            assert len(posted('/api/jobs')) == 1, 'restoring a tune never submits'
            browser.close()
    finally:
        server.shutdown(); server.server_close()
    assert not errors, errors
    print(json.dumps({'jobs_posted': len(posted('/api/jobs')), 'preset': SWITCH, 'tuned': tuned, 'page_errors': errors}))


if __name__ == '__main__':
    run()
