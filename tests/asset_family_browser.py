"""Native Chromium + real temporary Workspace family/recall, never a model call."""
import argparse
import copy
import json
import tempfile
import threading
from browser_ports import browser_server
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

from playwright.sync_api import sync_playwright
import studio_browser_smoke as fixture
import io
from PIL import Image
from test_server import server, png
import tiles
import parallax
from studio_workflow.asset_read_http import extend_handler

ROOT = Path(__file__).resolve().parents[1]


def build_family_studio(root):
    root = Path(root)
    (root/'presets').mkdir(); (root/'config').mkdir(); (root/'workflows/api').mkdir(parents=True)
    (root/'fake-comfy/input').mkdir(parents=True)
    original = json.loads((ROOT/'presets/catalog.json').read_text(encoding='utf-8'))
    preset = next(p for p in original['presets'] if p['id'] == 'anima-portrait')
    (root/'presets/catalog.json').write_text(json.dumps({'presets': [preset]}))
    graph_path = root/preset['graph']; graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_bytes((ROOT/preset['graph']).read_bytes())
    (root/'config/local.json').write_text(json.dumps({'comfy_root': str(root/'fake-comfy')}))
    with patch.object(threading.Thread, 'start', lambda *_: None):
        studio = server.Studio(root)
    studio._request = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('Model request forbidden'))
    # A portrait-sized picture, so the layout check measures a realistic preview rather than an 8x12 pixel fixture.
    stream = io.BytesIO(); Image.new('RGB', (482, 704), 'purple').save(stream, 'PNG')
    source = root/'synthetic.png'; source.write_bytes(stream.getvalue())
    ids = []
    for index, name in enumerate(('Draft', 'Refine', 'Repair', 'Upscale')):
        _, graph, _, controls, _ = studio.prepare({'preset_id': preset['id'], 'controls': {'positive': 'A forest at dusk', 'seed': 10}, 'batch_count': 1})
        actual = copy.deepcopy(graph)
        actual[str(preset['seed'][0])]['inputs'][preset['seed'][1]] = 12
        job = {'id': 'family-job-'+str(index), 'status': 'completed', 'created_at': index+1, 'preset_id': preset['id'],
               'preset_name': name, 'controls': controls, 'batch_count': 1, 'graph': graph,
               'prompt_bindings': {key: [preset[key]] if preset.get(key) else [] for key in ('positive', 'negative')},
               'parent_assets': ids[-1:], 'references': [], 'prompt_ids': ['prompt-'+str(index)],
               'submissions': [{'prompt_id': 'prompt-'+str(index), 'graph': actual, 'seed': 12, 'status': 'completed'}],
               'outputs': [{'filename': 'synthetic.png', 'media_type': 'image', 'seed': 12, 'prompt_id': 'prompt-'+str(index)}]}
        studio.jobs[job['id']] = job
        asset_id = studio.assets.register(job, 0, source); job['outputs'][0]['asset_id'] = asset_id; ids.append(asset_id)
    return studio, ids


def build_handler(studio, posts, controls=None):
    controls = controls or {}
    class Base(fixture.Handler):
        def _safe_host(self): return self.headers.get('Host') == '127.0.0.1:'+str(self.server.server_port)
        def _safe_mutation(self): return self._safe_host() and self.headers.get('Origin') in (None, 'http://127.0.0.1:'+str(self.server.server_port))
        _content_length = server.Handler._content_length
        _drain_refused_body = server.Handler._drain_refused_body
        _json = server.Handler._json
        def do_GET(self):
            path = urlsplit(self.path).path
            if path.startswith('/api/tiles/source/') or path.startswith('/api/parallax/source/'):
                tile = path.startswith('/api/tiles/'); module = tiles if tile else parallax
                return self.json({'asset_id': path.rsplit('/', 1)[-1], 'width': 482, 'height': 704, 'eligible': False,
                                  'reason': module.eligibility(482, 704), 'flag': tiles.FLAT_ONLY if tile else parallax.FLAG})
            if path == '/api/workspace': return self.json(self.studio.assets.snapshot())
            if path == '/api/jobs': return self.json(list(self.studio.jobs.values()))
            if path.startswith('/api/assets/') and path.endswith('/file'):
                raw = self.studio.assets.file(path.split('/')[3]).read_bytes()
                self.send_response(200); self.send_header('Content-Length', str(len(raw))); self.send_header('Content-Type', 'image/png'); self.end_headers(); self.wfile.write(raw); return
            return super().do_GET()
        def do_POST(self):
            if self.path == '/api/recipe-check':
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                posts.append(self.path)
                if controls.get('hold'): controls['entered'].set(); controls['release'].wait(10)
                try: return self.json(self.studio.check_recipe(payload))
                except ValueError as error: return self.json({'error': str(error)}, 400)
            posts.append(self.path)
            return super().do_POST()
    Base.studio = studio
    return extend_handler(Base)


def exercise(out, browser_executable=None):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        studio, ids = build_family_studio(tmp); posts = []
        controls = {'hold': False, 'confirm': 'accept', 'entered': threading.Event(), 'release': threading.Event()}
        http = browser_server(build_handler(studio, posts, controls))
        thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
        origin = 'http://127.0.0.1:'+str(http.server_port)
        before = studio.assets.snapshot(); errors = []; checks = []
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, executable_path=browser_executable)
                for width in (1440, 390):
                    context = browser.new_context(viewport={'width': width, 'height': 900 if width == 1440 else 1000}, reduced_motion='reduce')
                    page = context.new_page(); page.set_default_timeout(10000)
                    page.on('pageerror', lambda e: errors.append(e.stack or str(e)))
                    page.on('dialog', lambda dialog: dialog.accept() if controls['confirm'] == 'accept' else dialog.dismiss())
                    try:
                        page.goto(origin+'/#assets', wait_until='domcontentloaded')
                        page.wait_for_function('window.StudioSetupDraft&&backendActive==="primary"&&catalog?.presets?.some(p=>p.id==="anima-portrait")')
                        page.locator('#assetGrid .asset-open[data-asset-open="'+ids[-1]+'"]').click()
                        page.wait_for_function('document.querySelectorAll("#assetFamily [data-family-step]").length===4')
                        assert page.locator('#assetFamily [data-family-step]').evaluate_all('(els)=>els.map(e=>e.dataset.familyStep)') == ids
                        page.wait_for_function('document.querySelector("#uxTileWhyAsset")?.textContent.includes("482")&&document.querySelector("#uxParallaxWhy")?.textContent.includes("512")')
                        # Imported picture: all three unavailable actions fold together, preserving the controls and reasons.
                        recorded = page.evaluate('({preset_id:activeAsset.preset_id,job_id:activeAsset.job_id})')
                        page.evaluate('activeAsset.preset_id=null;activeAsset.job_id=null;refreshCarriedVary()')
                        fold = page.locator('#assetNextSteps > .asset-unavailable')
                        assert fold.count() == 1 and not fold.evaluate('(el)=>el.open')
                        assert fold.locator(':scope > summary').inner_text() == 'Not available for this picture (3)'
                        controls_in_fold = fold.locator('.ux-tile > button,.ux-parallax > button,.ux-vary > button')
                        assert controls_in_fold.count() == 3 and all(not control.is_visible() for control in controls_in_fold.all())
                        reasons = fold.locator('small').all_text_contents()
                        fewer_words = len(' '.join(fold.locator(':scope > div').all_text_contents()).split())-len(fold.locator(':scope > summary').inner_text().split())
                        page.screenshot(path=str(out/('available-'+str(width)+'.png')), full_page=True)
                        assert page.locator('[data-family-recall="new"]').is_visible() and page.locator('[data-family-reference]').is_visible()
                        assert page.locator('#assetFamilyActions').evaluate('(el)=>!!(el.compareDocumentPosition(document.querySelector(".asset-unavailable"))&Node.DOCUMENT_POSITION_FOLLOWING)')
                        fold.locator(':scope > summary').click()
                        assert all(control.is_visible() and control.is_disabled() for control in controls_in_fold.all())
                        assert fold.locator('small').all_text_contents() == reasons
                        page.screenshot(path=str(out/('unavailable-'+str(width)+'.png')), full_page=True)
                        page.locator('#closeAssetDialog').click()
                        page.evaluate('(id)=>openAsset(id)', ids[-1])
                        assert not fold.evaluate('(el)=>el.open')
                        page.wait_for_function('document.querySelector("#uxTileWhyAsset")?.textContent.includes("482")&&document.querySelector("#uxParallaxWhy")?.textContent.includes("512")')
                        # If every action becomes available the disclosure disappears; available order is retained.
                        page.evaluate('''recorded=>{activeAsset.preset_id=null;activeAsset.job_id=null;refreshCarriedVary();Object.assign(activeAsset,recorded);document.querySelector('[data-ux-tile]').disabled=false;
                          document.querySelector('[data-ux-parallax]').disabled=false;refreshCarriedVary();}''', recorded)
                        assert fold.count() == 0, page.locator('#assetNextSteps').inner_html()
                        assert page.locator('#assetNextSteps > [role="group"]').evaluate_all('(els)=>els.map(el=>el.className)') == ['ux-tile','ux-parallax','ux-vary']
                        page.locator('#closeAssetDialog').click()
                        page.evaluate('(id)=>openAsset(id)', ids[-1])
                        page.wait_for_function('document.querySelectorAll("#assetFamily [data-family-step]").length===4')
                        checks.append({'width': width, 'unavailable_fold': 3, 'reasons_unchanged': True, 'reopen_closed': True, 'all_available_no_fold': True, 'fewer_visible_words': fewer_words})
                        if width == 1440:
                            # Layout: the picture and the next-step actions sit in the first 900 px viewport, above the form.
                            picture = page.locator('#assetDetailMedia img').bounding_box()
                            assert picture and picture['y'] + picture['height'] <= 900, picture
                            for name, locator in (('continue', page.locator('#assetHandoffs [data-ux-handoff]')),
                                                  ('vary', page.locator('.asset-next-steps [data-ux-vary]')),
                                                  ('same-recipe', page.locator('[data-family-recall="new"]'))):
                                if name == 'vary' and locator.count() == 0:
                                    checks.append({'width': width, 'vary_control_present': False}); continue
                                box = locator.bounding_box()
                                assert box and box['y'] + box['height'] <= 900, (name, box)
                            steps = page.locator('#assetNextSteps').bounding_box(); title = page.locator('#assetTitle').bounding_box()
                            assert steps and title and steps['y'] + steps['height'] <= title['y'], (steps, title)
                        page.locator('#assetFamily [data-family-open="'+ids[1]+'"]').click()
                        page.wait_for_function('(id)=>activeAsset.id===id', arg=ids[1])
                        page.wait_for_function('document.querySelectorAll("#assetFamily [data-family-step]").length===2')
                        page.locator('[data-family-children]').click()
                        page.locator('#assetFamilyChildren [data-family-open="'+ids[2]+'"]').wait_for()
                        page.locator('#assetFamilyChildren [data-family-open="'+ids[2]+'"]').click()
                        page.wait_for_function('(id)=>activeAsset.id===id', arg=ids[2])
                        # Unsaved metadata must survive recall; no hidden discard or mutation.
                        page.locator('#assetNotes').fill('Keep this unsaved review')
                        page.locator('[data-family-recall="new"]').click()
                        page.wait_for_function('document.querySelector("#assetFamilyStatus").textContent.includes("Finish the current edit")')
                        assert page.locator('#assetNotes').input_value() == 'Keep this unsaved review'
                        page.locator('#assetNotes').fill('')
                        page.locator('[data-family-recall="words"]').click()
                        page.wait_for_function('!document.querySelector("#assetDialog").open')
                        assert page.locator('#positive').input_value() == 'A forest at dusk'
                        assert page.locator('[data-key="seed"]').input_value() == '12'
                        assert page.evaluate('document.activeElement.id') == 'positive'
                        assert page.locator('#batch').input_value() == '1'
                        page.evaluate('(id)=>{showView("assets");openAsset(id)}', ids[-1])
                        page.locator('[data-family-recall="new"]').click()
                        page.wait_for_function('!document.querySelector("#assetDialog").open')
                        # Same recipe, new seed: Create opens with the recipe loaded and a changed seed; no job is posted.
                        assert page.evaluate('location.hash') == '#create' and page.locator('#createView').is_visible()
                        assert page.locator('#positive').input_value() == 'A forest at dusk'
                        assert page.locator('[data-key="seed"]').input_value() != '12'
                        assert 'New seed' in page.locator('#status').inner_text()
                        assert '/api/jobs' not in posts, posts
                        # A declined confirmation is visible and leaves the dialog and Create untouched.
                        page.evaluate('(id)=>{showView("assets");openAsset(id)}', ids[-1])
                        controls['confirm'] = 'dismiss'
                        page.locator('[data-family-recall="new"]').click()
                        page.wait_for_function('document.querySelector("#assetFamilyStatus").textContent.includes("confirmation was declined")')
                        assert page.locator('#assetDialog').evaluate('(d)=>d.open') and page.evaluate('location.hash') == '#assets'
                        assert '/api/jobs' not in posts, posts
                        controls['confirm'] = 'accept'
                        # One delayed check must not overwrite newer typing.
                        page.evaluate('(id)=>{showView("assets");openAsset(id)}', ids[-1])
                        controls['hold'] = True; controls['entered'].clear(); controls['release'].clear()
                        page.locator('[data-family-recall="words"]').click()
                        assert controls['entered'].wait(5)
                        page.evaluate('document.querySelector("#positive").value="Newer human words";document.querySelector("#positive").dispatchEvent(new Event("input",{bubbles:true}))')
                        controls['release'].set(); controls['hold'] = False
                        page.wait_for_function('document.querySelector("#assetFamilyStatus").textContent.includes("changed")')
                        assert page.locator('#positive').input_value() == 'Newer human words'
                        # The reference action opens the existing picker and focuses this exact asset,
                        # without selecting a recipe or copying source bytes on the user's behalf.
                        page.locator('#closeAssetDialog').click()
                        page.evaluate('(id)=>{selectPreset("gentle-variation");showView("assets");openAsset(id)}', ids[-1])
                        page.locator('[data-family-reference]').click()
                        page.wait_for_function('document.querySelector("#uxSourcePicker").open&&!document.querySelector("#uxSourceSearch").disabled')
                        page.wait_for_function('(id)=>document.activeElement?.dataset.uxPull===id', arg=ids[-1])
                        assert page.locator('#uxSourceSearch').input_value() == studio.assets.get(ids[-1])['title']
                        page.locator('[data-ux-close="uxSourcePicker"]').click()
                        page.evaluate('(id)=>{showView("assets");openAsset(id)}', ids[-1])
                        page.locator('[data-family-recall="words"]').focus()
                        assert page.evaluate('document.activeElement.dataset.familyRecall') == 'words'
                        page.evaluate('document.documentElement.style.zoom="2"')
                        page.locator('#assetFamily').scroll_into_view_if_needed()
                        assert page.locator('#assetFamily').evaluate('(el)=>el.scrollWidth<=el.clientWidth+2')
                        bounds = page.locator('#assetDialog,#assetFamily,#assetFamily button').evaluate_all(
                            '(els)=>els.map(el=>{const r=el.getBoundingClientRect();return {left:r.left,right:r.right,viewport:innerWidth}})')
                        assert all(r['left'] >= -1 and r['right'] <= r['viewport']+1 for r in bounds), bounds
                        page.screenshot(path=str(out/('family-'+str(width)+'.png')), full_page=True)
                        checks.append({'width': width, 'four_steps': True, 'navigation': True, 'recall': True, 'new_seed': True, 'declined_confirm_visible': True, 'draft_retained': True, 'stale_refused': True, 'source_picker_no_copy': True, 'keyboard_focus': True, 'zoom': 2})
                    except Exception as error:
                        evidence = {'status': 'failed', 'width': width, 'error': str(error)[:4000],
                                    'page_errors': errors[:30], 'post_routes': sorted(set(posts)),
                                    'completed_checks': checks}
                        try:
                            evidence['visible_status'] = page.locator('#assetFamilyStatus').all_text_contents()
                            evidence['console_status'] = page.locator('#status').all_text_contents()
                            page.screenshot(path=str(out/('failure-'+str(width)+'.png')), full_page=True, timeout=5000)
                        except Exception as capture_error:
                            evidence['capture_error'] = str(capture_error)[:500]
                        (out/'failure.json').write_text(json.dumps(evidence, indent=2)+'\n', encoding='utf-8')
                        raise
                    finally:
                        context.close()
                browser.close()
        finally:
            controls['release'].set(); http.shutdown(); http.server_close(); thread.join(5)
        assert not errors, errors
        assert studio.assets.snapshot() == before
        assert not any(path == '/api/jobs' or path == '/api/assets/reference' or '/start' in path for path in posts), posts
        report = {'checks': checks, 'page_errors': errors, 'post_routes': sorted(set(posts)), 'generation_submitted': False, 'workspace_unchanged': True}
        (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--out', default='.runtime/asset-family'); parser.add_argument('--browser'); args=parser.parse_args(); exercise(args.out, args.browser)
