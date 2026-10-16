"""Make's Tune this look (owner ask, 16 Oct 2026): switch the model to a compatible one, change and add adapters, steps,
negative and a locked seed; Generate sends exactly those settings, the run card names them, and Edit and re-run brings them
back. Never a model call: /api/jobs is answered by the fixture and recorded.

python tests/make_tune_browser.py
Fixture server from studio_browser_smoke (real frontend, synthetic API, real catalog, looks and settings knowledge).
"""
import json
import threading
import time
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
        if 'slow prepare' in data.get('scene', ''): time.sleep(1.0)  # a reply slow enough to change the form under it
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
            # A recorded non-commercial licence (the recipe's commercial_note) is tagged on its option; an unrecorded one is not.
            labels = dict(zip(offered, page.eval_on_selector_all('#makeModel option', 'o => o.map(x => x.textContent)')))
            assert 'non-commercial' in labels[SWITCH] and 'non-commercial' not in labels[BASE], labels
            page.select_option('#makeModel', SWITCH)
            assert 'Tuned: model Pearly Anima Mix' in page.text_content('#makeTuneSum'), page.text_content('#makeTuneSum')
            # Style strength folds into Tune while Tune shows adapters (audit N3): one multiplier, beside the strengths it scales.
            assert page.is_visible('#makeTuneScale') and not page.is_visible('#makeStrength'), 'one Style strength on screen with Tune open'
            page.evaluate('() => { const r = document.querySelector("[data-tune-strength=lora]"); r.value = "0.7"; r.dispatchEvent(new Event("input", {bubbles: true})); }')
            listed = page.eval_on_selector_all('#makeLoraList option', 'o => o.map(x => x.value)')
            assert ADDED in listed and FOREIGN not in listed, 'only adapters made for this model type are offered'
            # Made for this model first, other families of the same type after them and labelled so (audit N5), with the adapter's role.
            labels = page.eval_on_selector_all('#makeLoraList option', 'o => o.map(x => x.label || x.textContent)')
            fit = ['made for this model' in l for l in labels]
            assert any(fit) and not all(fit) and fit == sorted(fit, reverse=True) and all('may not suit' in l for l, f in zip(labels, fit) if not f), labels
            assert all(KNOWLEDGE['loras'][v]['family'] == 'Anima' for v, f in zip(listed, fit) if f) and all(KNOWLEDGE['loras'][v]['role'] in l for v, l in zip(listed, labels)), (listed, labels)
            assert 'made for Anima come first' in page.text_content('#makeLoraFit') and 'may not suit' in page.text_content('#makeLoraFit')
            page.fill('#makeLoraSearch', FOREIGN); page.click('[data-tune-add]')
            assert 'not an installed adapter for this model type' in page.text_content('#makeStatus') and not page.query_selector('[data-slot=lora2]')
            page.fill('#makeLoraSearch', ADDED); page.click('[data-tune-add]')
            assert page.query_selector('[data-slot=lora2]') and '@40u40uya' in page.text_content('[data-slot=lora2] small'), 'added row shows its trigger'
            page.fill('#makeLoraSearch', ADDED); page.click('[data-tune-add]')
            assert 'already added' in page.text_content('#makeStatus'), page.text_content('#makeStatus')
            assert page.eval_on_selector_all('.make-tune-row b', 'n=>n.length') == 2, 'a second Add of the same adapter adds nothing'
            # A look whose recipe is missing from the catalog says it cannot be tuned instead of breaking Make.
            assert page.evaluate('''(id)=>{const p=catalog.presets,i=p.findIndex(x=>x.id===id),saved=p[i];p.splice(i,1);StudioMake.refresh();const text=document.querySelector("#makeTuneBody").textContent;p.splice(i,0,saved);StudioMake.refresh();return text}''', BASE).startswith('This look')
            page.select_option('[data-tune=steps]', index=1)
            page.fill('#makeNegative', 'extra hands')
            page.uncheck('#makeNewSeed'); page.fill('#makeSeed', '1234')
            page.fill('#makeScene', SCENE)
            page.select_option('#makeShape', 'square'); page.select_option('#makeCount', '2')
            page.evaluate('() => { const r = document.querySelector("#makeTuneScale"); r.value = "50"; r.dispatchEvent(new Event("input", {bubbles: true})); }')
            assert page.text_content('[data-slot=lora] output') == '0.70 \u2192 0.35' and page.input_value('#makeStrength') == '50', page.text_content('[data-slot=lora] output')
            assert 'all adapters \u00d750%' in page.text_content('#makeTuneSum'), page.text_content('#makeTuneSum')
            assert page.evaluate('getComputedStyle(document.querySelector(".make-go")).position') == 'sticky' and page.query_selector('.make-go #makeGenerate')
            # Generate stays on screen with Tune open (audit N4): the bar is the composer's own child, on a desktop and on a phone.
            assert page.evaluate('document.querySelector(".make-go").parentElement.classList.contains("make-composer")')
            assert page.evaluate('document.querySelector("#makeNewSeed").closest(".make-tune-group")?.contains(document.querySelector("#makeSeed"))'), 'the seed lock sits by the Seed field'
            for width, height in ((1440, 900), (390, 844)):
                page.set_viewport_size({'width': width, 'height': height}); page.evaluate('() => document.querySelector("#makeTune").scrollIntoView({block: "start"})'); page.wait_for_timeout(80)
                box = page.evaluate('() => { const r = document.querySelector("#makeGenerate").getBoundingClientRect(); return [r.top, r.bottom, innerHeight]; }')
                assert 0 <= box[0] and box[1] <= box[2], (width, box)
            page.set_viewport_size({'width': 1440, 'height': 1000})
            about = page.text_content('.make-about')
            assert 'Details for maintainers' in about and 'Model:' in about, about
            assert not posted('/api/jobs'), 'tuning never submits'
            page.click('#makeGenerate'); page.wait_for_function('document.querySelector(".make-run .make-tuned")')
            # The status line is in the Generate bar, on screen after the press (audit N2), not at the top of the page.
            page.wait_for_function('document.querySelector("#makeStatus").textContent.startsWith("Started")')
            status = page.evaluate('() => { const s = document.querySelector("#makeStatus"), r = s.getBoundingClientRect(); return [!!s.closest(".make-go"), r.top, r.bottom, innerHeight]; }')
            assert status[0] and 0 <= status[1] and status[2] <= status[3], status
            jobs = posted('/api/jobs'); assert len(jobs) == 1, jobs
            job, steps = jobs[0], max(1, round(shipped['controls']['steps'] / 2 + 1e-9))
            c = job['controls']
            assert job['preset_id'] == SWITCH, job['preset_id']
            # Style strength at 50% scales every tuned adapter, the added one included.
            assert (c['lora'], c['lora_name'], c['lora2'], c['lora2_name']) == (0.35, shipped['controls']['lora_name'], round(KNOWLEDGE['loras'][ADDED]['default'] * 0.5, 2), ADDED), c
            assert job['batch_count'] == 2 and c['width'] == c['height'], (job['batch_count'], c['width'], c['height'])
            assert all(c[k] == 0 for k in ('lora3', 'lora4', 'lora5', 'lora6')), 'a switched model keeps none of its own authored adapters'
            assert (c['steps'], c['negative'], c['seed']) == (steps, 'extra hands', 1234), c
            assert c['positive'].startswith('@40u40uya, ') and SCENE in c['positive'], c['positive']
            target = presets[SWITCH]; bound = {k for k in c if target.get(k) or (target.get('bindings_extra') or {}).get(k)}
            assert bound == set(c), ('only inputs the target recipe binds', set(c) - bound)
            tuned = page.text_content('.make-run .make-tuned')
            assert all(part in tuned for part in ('model Pearly Anima Mix', '+', 'all adapters \u00d750%', '%d steps' % steps, 'own negative', 'seed 1234 locked')), tuned
            # Back to the look as made, then Edit and re-run: the run's tune comes back with its look.
            page.click('[data-tune-reset]'); assert page.input_value('#makeModel') == BASE and not page.query_selector('[data-slot=lora2]')
            page.click('[data-make-rerun="%s"]' % JOB['id'])
            assert page.input_value('#makeModel') == SWITCH and page.query_selector('[data-slot=lora2]'), 'Edit and re-run restores the tune'
            assert not page.is_checked('#makeNewSeed') and page.input_value('#makeSeed') == '1234' and page.input_value('#makeScene') == SCENE
            assert (page.input_value('#makeShape'), page.input_value('#makeCount'), page.input_value('#makeStrength')) == ('square', '2', '50'), 'the run keeps its own shape, count and strength'
            assert len(posted('/api/jobs')) == 1, 'restoring a run never submits'
            # A run made with new seeds each time comes back locked to the seed it used: change only the words, same picture.
            page.check('#makeNewSeed'); fixture.POSTS.clear(); page.click('#makeGenerate')
            page.wait_for_function('document.querySelector("#makeStatus").textContent.startsWith("Started")')
            used = posted('/api/jobs')[-1]['controls']['seed']; assert used != 1234, used
            page.click('[data-make-rerun="%s"]' % JOB['id'])
            assert not page.is_checked('#makeNewSeed') and page.input_value('#makeSeed') == str(used), (used, page.input_value('#makeSeed'))
            assert 'seed locked' in page.text_content('#makeStatus') and len(posted('/api/jobs')) == 1, page.text_content('#makeStatus')
            # The run keeps the settings read when Generate was pressed, not ones changed while Prepare was answering.
            page.fill('#makeScene', SCENE + ', slow prepare'); page.select_option('#makeShape', 'portrait'); fixture.POSTS.clear()
            page.click('#makeGenerate'); page.select_option('#makeShape', 'landscape')
            page.evaluate('() => { const r = document.querySelector("#makeStrength"); r.value = "120"; r.dispatchEvent(new Event("input")); }')
            page.wait_for_function('document.querySelector("#makeStatus").textContent.startsWith("Started")')
            page.click('[data-make-rerun="%s"]' % JOB['id'])
            assert (page.input_value('#makeShape'), page.input_value('#makeStrength')) == ('portrait', '50'), (page.input_value('#makeShape'), page.input_value('#makeStrength'))
            # A tune survives a reload (audit N7), and a damaged stored tune falls back to the look as made instead of breaking Make.
            page.reload(); page.wait_for_function('catalog?.presets?.length && knowledge?.loras && document.querySelector("#makeModel")')
            assert page.input_value('#makeModel') == SWITCH and page.query_selector('[data-slot=lora2]') and page.input_value('#makeStrength') == '50', 'the tune came back after a reload'
            assert 'model Pearly Anima Mix' in page.text_content('#makeTuneSum') and len(posted('/api/jobs')) == 1, 'a restored tune never submits'
            # An added adapter that has since been uninstalled drops the stored tune, never submitting an unknown file (#1453 review).
            page.evaluate('''(id) => { const all = JSON.parse(localStorage.getItem("studio.make.tune")); const t = all[id];
                t.rows = t.rows.map(r => r.added ? {...r, name: "ghost-uninstalled.safetensors"} : r);
                if (!t.rows.some(r => r.added)) t.rows.push({slot: "lora6", name: "ghost-uninstalled.safetensors", strength: 0.5, on: true, added: true});
                localStorage.setItem("studio.make.tune", JSON.stringify(all)); }''', LOOK)
            page.reload(); page.wait_for_function('catalog?.presets?.length && document.querySelector("#makeModel") && installedLoras.length')
            before = len(posted('/api/jobs')); page.fill('#makeScene', 'a lantern keeper at dusk'); page.click('#makeGenerate')
            page.wait_for_timeout(1500)
            sent = posted('/api/jobs')[before:]
            assert sent and 'ghost-uninstalled.safetensors' not in json.dumps(sent[-1]), 'an uninstalled added adapter is left out, never submitted'
            page.evaluate('(id) => localStorage.setItem("studio.make.tune", JSON.stringify({[id]: {rev: 0, preset: "wai", rows: "x", cleared: []}}))', LOOK)
            page.reload(); page.wait_for_function('catalog?.presets?.length && document.querySelector("#makeModel")')
            assert page.input_value('#makeModel') == BASE and not page.query_selector('[data-slot=lora2]'), 'a damaged tune is dropped'
            # Two models of one family are told apart by file; an added trigger never repeats a word the prompt already has (audit N11).
            page.click('[data-make-goal="character"]')
            if page.query_selector('[data-make-change]'): page.click('[data-make-change]')
            page.click('[data-make-look="look-anima-fantasy-portrait"]')
            names = [n.replace('As made \u00b7 ', '') for n in page.eval_on_selector_all('#makeModel option', 'o => o.map(x => x.textContent)')]
            assert len(names) == len(set(names)) and sum(n.startswith('Anima \u00b7 ') for n in names) == 2, names
            if page.query_selector('[data-make-change]'): page.click('[data-make-change]')
            page.click('[data-make-look="look-wai-fantasy-portrait"]')
            if not page.evaluate('document.querySelector("#makeTune").open'): page.click('#makeTune > summary')
            page.fill('#makeLoraSearch', 'illustrious_masterpieces_v3.safetensors'); page.click('[data-tune-add]'); page.fill('#makeScene', SCENE); fixture.POSTS.clear()
            page.click('#makeGenerate'); page.wait_for_function('document.querySelector("#makeStatus").textContent.startsWith("Started")')
            words = posted('/api/jobs')[-1]['controls']['positive'].lower()
            assert words.count('masterpiece') == 1 and words.count('best quality') == 1 and words.count('very aesthetic') == 1, words
            # An adapter whose file is fixed inside its recipe cannot move to another model: no switch is offered.
            page.click('[data-make-goal="game"]')
            if page.query_selector('[data-make-change]'): page.click('[data-make-change]')
            page.click('[data-make-look="look-preset-pixel-lora"]')
            if not page.evaluate('document.querySelector("#makeTune").open'): page.click('#makeTune > summary')
            assert page.eval_on_selector_all('#makeModel option', 'o => o.map(x => x.value)') == ['pixel-lora'], page.eval_on_selector_all('#makeModel option', 'o => o.map(x => x.value)')
            # A slow look starts at one picture.
            page.click('[data-make-goal="painting"]')
            if page.query_selector('[data-make-change]'): page.click('[data-make-change]')
            page.click('[data-make-look="look-krea-oil-fantasy"]'); assert page.input_value('#makeCount') == '1'
            browser.close()
    finally:
        server.shutdown(); server.server_close()
    assert not errors, errors
    print(json.dumps({'jobs_posted': len(posted('/api/jobs')), 'preset': SWITCH, 'tuned': tuned, 'page_errors': errors}))


if __name__ == '__main__':
    run()
