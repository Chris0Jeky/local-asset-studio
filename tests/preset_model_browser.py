"""Opt-in Chromium dependency-panel proof using real frontend files and inert APIs.

The HTTP fixture reuses studio_browser_smoke; backend behavior is covered separately
by test_preset_model_readiness's real Handler tests. No model or installer runs.
"""
from browser_ports import evidence_screenshot
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import threading
from browser_ports import browser_server
from urllib.parse import urlsplit

import studio_browser_smoke as fixture

ROWS = [
    {'file': 'inpaint/fix.patch', 'path': 'C:/fixture/models/inpaint/fix.patch', 'present': False,
     'asset_id': 'manual-patch', 'installable': False, 'install_note': 'Pin-only patch: copy the reviewed file manually.'},
    {'file': 'loras/curated.safetensors', 'path': 'C:/fixture/models/loras/curated.safetensors', 'present': False,
     'asset_id': 'curated', 'installable': True},
    {'file': 'unknown.safetensors', 'path': None, 'present': None, 'asset_id': None, 'installable': False,
     'note': 'Model folder unknown; declare model_files.', 'install_note': 'Review the exact source and destination.'},
    {'file': 'loras/unavailable.safetensors', 'present': True, 'installable': False,
     'note': 'Content verification unavailable for library pin fixture: file changed while hashing so its digest is unavailable.'},
    {'file': 'loras/different.safetensors', 'present': True, 'installable': False,
     'note': 'Content differs from library pin fixture: pinned sha256 a, observed sha256 b.'},
]

# Models-view fixture: shared known files, an unlisted adapter, an unknown location,
# and a failed inspection. GETs run through the real HTTP handler; no installer runs.
MODEL_ASSETS = [
    dict(id='shared', name='Shared model', file='checkpoints/shared.safetensors', present=False, installable=True),
    dict(id='manual', name='Manual encoder', file='text_encoders/manual.gguf', present=False, installable=False,
         install_note='Copy the reviewed encoder manually.'),
    dict(id='changed', name='Changed adapter', file='loras/changed.safetensors', present=True, installable=True),
    dict(id='ready', name='Checked model', file='vae/ready.safetensors', present=True, verified=True, installable=True),
    dict(id='unused', name='Unused model', file='loras/unused.safetensors', present=False, installable=True),
]
MODEL_ASSETS = [dict({'family':'Synthetic fixture', 'bytes':1024, 'verified':False, 'download':{},
                     'source':'https://example.com/fixture/'+row['id'], 'license':'Synthetic fixture',
                     'path':'C:/fixture/models/'+row['file']}, **row) for row in MODEL_ASSETS]
MODEL_LOOKS = [dict(id='fixture-'+key, kind='look', name='Fixture look '+key, usable=True, revision=0, lineage=[],
                    body=dict(preset_id=preset, template='{scene}', controls=controls))
               for key, preset, controls in [('A', 'pixel-lora', {'lora_name':'unlisted.safetensors'}),
                                             ('B', 'stylized-prop', {}), ('unknown', 'realvis', {}),
                                             ('unavailable', 'zimage-fast', {}), ('ready', 'krea-refine', {})]]
MODEL_REQUIREMENTS = {
    'pixel-lora': [dict(asset_id='shared', file='checkpoints/shared.safetensors', present=False),
                  dict(asset_id='manual', file='text_encoders/manual.gguf', present=False)],
    'stylized-prop': [dict(asset_id='shared', file='checkpoints/shared.safetensors', present=False),
                     dict(asset_id='changed', file='loras/changed.safetensors', present=True, pin_mismatch={'note':'Fixture changed bytes'})],
    'realvis': [dict(file='unknown-location.safetensors', present=None, note='Model folder unknown; inspect its source.')],
    'zimage-fast': None,
    'krea-refine': [],
}


class Handler(fixture.Handler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/looks':
            return self.json({'looks': MODEL_LOOKS, 'generation_submitted': False})
        if path == '/api/library':
            return self.json({'assets': MODEL_ASSETS, 'model_root': 'C:/fixture/models', 'folders': [], 'collections': [],
                              'inventory': [{'file':'vae/ready.safetensors', 'bytes':1024}],
                              'storage': {'free_bytes':100*1024**3, 'total_bytes':200*1024**3, 'reserve_bytes':7*1024**3}})
        if path.startswith('/api/inspect/'):
            preset = path.rsplit('/', 1)[-1]
            if preset in MODEL_REQUIREMENTS:
                rows = MODEL_REQUIREMENTS[preset]
                if rows is None:
                    return self.json({'error':'Synthetic file inspection unavailable'}, 503)
                return self.json({'requirements': rows, 'nodes': [], 'graph': {}})
            return self.json({'requirements': ROWS, 'nodes': [], 'graph': {}})
        if path == '/api/health':
            return self.json({'online': True, 'schema_available': True, 'missing_models': {'anima-portrait': ['inpaint/fix.patch']},
                              'pin_mismatch': {'anima-portrait': ['loras/unavailable.safetensors', 'loras/different.safetensors']}, 'devices': []})
        return super().do_GET()


def models_case(page, origin, output, width):
    healthy_backend = 'One model environment at a time. Switching never starts a generation.'
    # Make the original startup race deterministic: the backend reply arrives
    # before the catalog can select a recipe. Both requests still use real GETs.
    page.goto('about:blank')
    held_catalog = []
    def hold_catalog(route):
        held_catalog.append(route)
    page.route('**/api/catalog', hold_catalog)
    try:
        page.goto(origin+'/#models', wait_until='domcontentloaded')
        # All classic owners are now mounted. Re-read through the existing owner
        # while selection is still held, even if its first reply beat looks.js.
        page.evaluate('refreshBackends()')
        page.wait_for_function("backendActive==='primary' && backendReadPending===null")
        startup = page.evaluate('''()=>({selected:!!selected,
          backend_status:document.querySelector('#backendStatus').textContent,
          generate_disabled:document.querySelector('#generate').disabled,
          look_payload:StudioLooks.applicationPayload(selected?.id)})''')
        (output/f'models-startup-{width}.json').write_text(json.dumps(startup, indent=2)+'\n', encoding='utf-8')
        evidence_screenshot(page, path=str(output/f'models-startup-{width}.png'))
        assert held_catalog and not startup['selected'], startup
        assert startup['backend_status'] == healthy_backend, startup
        assert startup['generate_disabled'] and startup['look_payload'] == {}, startup
    finally:
        # Settle held requests before removing their interceptor; unroute may
        # otherwise release them itself, making a later continue_ a second owner.
        while held_catalog:
            held_catalog.pop(0).continue_()
        page.unroute('**/api/catalog', hold_catalog)
    page.wait_for_function('!!selected && schemaAvailable && !!window.StudioReadPoller && modelLooks?.length===5 && !modelUseBusy')
    overview = page.locator('#modelLooks')
    row = lambda name: overview.locator('.model-look').filter(has_text='Fixture look '+name)
    assert '1 of 5 looks ready now' in overview.inner_text()
    assert '3 missing files' in row('A').inner_text()
    assert '1 missing file · 1 changed file to check' in row('B').inner_text()
    assert 'unlisted.safetensors: missing file; not listed in the model library' in row('A').inner_text()
    assert '1 file not checked' in row('unknown').inner_text()
    assert 'Model folder unknown; inspect its source.' in row('unknown').inner_text()
    assert 'File check unavailable' in row('unavailable').inner_text()
    for name in ('shared.safetensors', 'manual.gguf', 'changed.safetensors'):
        assert name not in overview.inner_text(), (width, name)
    for asset in MODEL_ASSETS:
        assert page.locator('#modelCards [data-install="'+asset['id']+'"]').count() == 1
    assert 'Download missing files, or check files already on disk.' in page.locator('#modelsView').inner_text()
    assert '20 GiB reserved' not in page.locator('#modelsView').inner_text()
    assert '7.00 GiB' in page.locator('#storage').inner_text()

    def capture(target, name, reveal=True):
        if reveal:
            target.scroll_into_view_if_needed()
        bounds = target.evaluate('''node=>{const r=node.getBoundingClientRect(),x=(r.left+r.right)/2,y=(r.top+r.bottom)/2;
          const visible=n=>n.getClientRects().length && getComputedStyle(n).visibility!=='hidden';
          const headerBottom=Math.max(0,...[...document.querySelectorAll('.studio-globalbar,.studio-globalbar .privacy-bar')]
            .filter(visible).map(n=>n.getBoundingClientRect().bottom));
          const label=document.querySelector('.models-toolbar label[for="curatedModelSearch"]'),l=label.getBoundingClientRect();
          const toolbar=document.querySelector('.models-toolbar').getBoundingClientRect(),occupied=Math.max(headerBottom,toolbar.bottom);
          return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,width:innerWidth,height:innerHeight,
            occupied,hit:node.contains(document.elementFromPoint(x,y)),
            topHit:node.contains(document.elementFromPoint(r.left+Math.min(10,r.width/2),r.top+2)),scrollWidth:document.documentElement.scrollWidth,
            toolbar_label:{top:l.top,bottom:l.bottom,left:l.left,right:l.right,header_bottom:headerBottom,
              hit:label.contains(document.elementFromPoint((l.left+l.right)/2,(l.top+l.bottom)/2)),
              topHit:label.contains(document.elementFromPoint((l.left+l.right)/2,l.top+2))},
            placeholders:[...document.querySelectorAll('#modelLooks .look-thumb')].filter(visible).map(n=>{
              const b=n.getBoundingClientRect();return {width:b.width,height:b.height};}),
            backend_status:document.querySelector('#backendStatus').textContent,
            visible_errors:[...document.querySelectorAll('.error,[role="alert"],#workerFailure')].filter(visible)
              .filter(n=>n.textContent.trim()).map(n=>({id:n.id,text:n.textContent.trim()}))};}''')
        (output/f'{name}-{width}.json').write_text(json.dumps(bounds, indent=2)+'\n', encoding='utf-8')
        evidence_screenshot(page, path=str(output/f'{name}-{width}.png'))
        assert bounds['backend_status'] == healthy_backend and not bounds['visible_errors'], bounds
        assert bounds['occupied'] <= bounds['top'] < bounds['bottom'] <= bounds['height'], bounds
        assert 0 <= bounds['left'] < bounds['right'] <= bounds['width'], bounds
        assert bounds['hit'] and bounds['topHit'] and bounds['scrollWidth'] <= bounds['width'], bounds
        label = bounds['toolbar_label']
        assert label['header_bottom'] <= label['top'] < label['bottom'] <= bounds['height'], bounds
        assert 0 <= label['left'] < label['right'] <= bounds['width'] and label['hit'] and label['topHit'], bounds
        assert all(abs(box['width']-44) < .5 and abs(box['height']-44) < .5 for box in bounds['placeholders']), bounds
        return bounds

    def tab_to(target):
        for _ in range(80):
            if target.evaluate('node=>document.activeElement===node'):
                return
            page.keyboard.press('Tab')
        raise AssertionError('Keyboard traversal did not reach '+target.get_attribute('id'))

    page.locator('#curatedModelSearch').fill('shared.safetensors')
    assert overview.locator('.model-look').count() == 2
    assert page.locator('#modelCards .model-card').count() == 1
    page.locator('#curatedModelSearch').fill('Fixture look A')
    link = row('A').get_by_role('link', name='View files')
    assert link.count() == 1
    tab_to(link)
    summary_bounds = capture(link, 'models-summary', reveal=False)
    assert len(summary_bounds['placeholders']) == 1, summary_bounds
    page.keyboard.press('Enter')
    page.wait_for_function('document.querySelector("#modelLooks").hidden && !modelUseBusy')
    assert page.locator('#curatedModelTitle').inner_text().startswith('Files needed for ')
    assert page.locator('#modelCards .model-card').count() == 2
    assert page.locator('#modelCards .model-other-files').inner_text().count('unlisted.safetensors') == 1
    install = page.locator('#modelCards [data-install="shared"]')
    manual = page.locator('#modelCards [data-install="manual"]')
    assert install.is_enabled() and manual.is_disabled()
    assert 'Copy the reviewed encoder manually.' in page.locator('#modelCards').inner_text()
    assert page.locator('#modelCards [data-copy="C:/fixture/models/text_encoders/manual.gguf"]').count() == 1
    # Start at a visible native search control, then let Tab do all scrolling to the action.
    page.locator('#curatedModelSearch').click()
    tab_to(install)
    assert install.evaluate('node=>document.activeElement===node')
    action_bounds = capture(install, 'models-needed-files', reveal=False)

    def show_all():
        page.locator('#modelCards [data-models-all]').click()
        page.wait_for_function('!document.querySelector("#modelLooks").hidden && !modelUseBusy')
        assert page.locator('#curatedModelSearch').input_value() == ''
        assert page.locator('#modelStatus').input_value() == 'all'

    show_all()
    page.locator('#modelStatus').select_option('installed')
    page.wait_for_function('document.querySelectorAll("#modelCards .model-card").length===1 && document.querySelector("#modelCards [data-install=ready]")')
    assert page.locator('#modelCards .model-card').count() == 1
    assert page.locator('#modelCards [data-install="ready"]').count() == 1
    row('B').get_by_role('link', name='View files').click()
    page.wait_for_function('document.querySelector("#modelLooks").hidden && !modelUseBusy')
    assert page.locator('#modelCards .model-card').count() == 2
    verify = page.locator('#modelCards [data-install="changed"]')
    assert verify.is_visible() and verify.inner_text() == 'Verify'
    capture(verify, 'models-changed-file')
    show_all()
    row('unknown').get_by_role('link', name='View files').click()
    page.wait_for_function('document.querySelector("#modelLooks").hidden && !modelUseBusy')
    assert page.locator('#modelCards [data-install]').count() == 0
    assert 'unknown-location.safetensors: file not checked' in page.locator('#modelCards').inner_text()
    assert 'Model folder unknown; inspect its source.' in page.locator('#modelCards').inner_text()
    capture(page.locator('#modelCards .model-other-files'), 'models-unknown-file')
    return {'width':width, 'known_file_detail_once':True, 'shared_action_once':True, 'unlisted_detail_retained':True,
            'unknown_and_failed_checks_explicit':True, 'native_file_links':True, 'filters_and_search':True,
            'manual_install_preserved':True, 'keyboard_navigation':True, 'keyboard_focus':True,
            'startup_before_catalog_healthy':True, 'toolbar_label_uncovered':True, 'placeholders_44px':True, 'visible_errors':[],
            'summary_bounds':summary_bounds, 'action_bounds':action_bounds}


def run(output):
    from playwright.sync_api import sync_playwright
    output.mkdir(parents=True, exist_ok=True)
    http = browser_server(Handler)
    worker = threading.Thread(target=http.serve_forever, daemon=True); worker.start()
    cases = []; model_cases = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None,
                                        headless=True, args=['--no-sandbox'])
            try:
                for width in (1440, 390):
                    context = browser.new_context(viewport={'width': width, 'height': 1000}, reduced_motion='reduce')
                    page = context.new_page(); errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(f'http://127.0.0.1:{http.server_port}')
                    page.wait_for_function('!!selected && schemaAvailable')
                    page.evaluate("showView('create');selectPreset('anima-portrait')")
                    page.wait_for_selector('#dependencies [data-install="curated"]', state='attached')
                    page.wait_for_selector('#workshopInspect', state='attached')
                    page.evaluate("document.querySelector('#workshopSettings').open=true")  # QA 3 Nov: Recipe details sits inside Settings
                    page.locator('#workshopInspect > summary').click()
                    page.evaluate("for(let d=document.querySelector('#dependencies');d;d=d.parentElement)if(d.tagName==='DETAILS')d.open=true")
                    panel = page.locator('#dependencies')
                    assert panel.locator('[data-install]').count() == 1
                    assert panel.locator('[data-install="manual-patch"]').count() == 0
                    assert 'copy the reviewed file manually' in panel.text_content()
                    notes = panel.locator('.dependency').first.locator('.file-text small')
                    assert notes.count() == 2
                    bounds = notes.evaluate_all('(items)=>items.map(el=>({top:el.getBoundingClientRect().top,bottom:el.getBoundingClientRect().bottom}))')
                    assert bounds[1]['top'] >= bounds[0]['bottom'], bounds
                    unknown = panel.locator('.dependency').filter(has_text='unknown.safetensors')
                    assert unknown.locator('[data-copy]').count() == 0
                    assert 'Model folder unknown' in unknown.text_content()
                    badge = page.locator('#presetList [data-id="anima-portrait"] .badge').filter(has_text='Model verification needs attention')
                    assert badge.count() == 1
                    assert 'loras/unavailable.safetensors' in badge.get_attribute('title')
                    assert 'loras/different.safetensors' in badge.get_attribute('title')
                    assert 'Content verification unavailable' in panel.text_content()
                    assert 'Content differs from library pin' in panel.text_content()
                    page.evaluate('health()'); page.wait_for_function("document.querySelector('#health').textContent==='Recipe needs models'")
                    assert page.locator('#generate').is_disabled()
                    # Open the real dependency disclosure, then keyboard-focus its only valid install.
                    page.evaluate("for(let d=document.querySelector('#dependencies');d;d=d.parentElement)if(d.tagName==='DETAILS')d.open=true")
                    page.locator('#dependencies [data-install="curated"]').focus()
                    assert page.locator('#dependencies [data-install="curated"]').evaluate('(el)=>document.activeElement===el')
                    evidence_screenshot(page.locator('#dependencies'), path=str(output/f'dependencies-{width}.png'))
                    assert not errors, errors
                    writes = [post for post in fixture.POSTS if post['path'] not in ('/api/estimate', '/api/references/check')]
                    assert not writes, writes
                    cases.append({'width': width, 'unsupported_install_hidden': True, 'unknown_path_not_copyable': True,
                                  'pin_warning_honest': True, 'detailed_pin_notes_preserved': True,
                                  'readiness_blocks_generate': True, 'keyboard_focus': True, 'model_mutations': 0, 'page_errors': []})
                    model_cases.append(models_case(page, f'http://127.0.0.1:{http.server_port}', output, width))
                    assert not errors, errors
                    writes = [post for post in fixture.POSTS if post['path'] not in ('/api/estimate', '/api/references/check')]
                    assert not writes, writes
                    context.close()
            finally: browser.close()
    finally: http.shutdown(); http.server_close(); worker.join(5)
    root = Path(__file__).resolve().parents[1]
    receipt = {'fixture': 'real frontend with synthetic read APIs', 'cases': cases, 'models_cases':model_cases,
               'model_mutations':0, 'page_errors':[], 'source_sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest()
                 for name in ('app/static/app.js','app/static/index.html','app/static/style.css','app/static/looks.js','app/static/backends.js','tests/preset_model_browser.py')}}
    (output/'result.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args().out)
