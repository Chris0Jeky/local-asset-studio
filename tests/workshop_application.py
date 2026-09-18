"""Real frontend + native HTTP/storage; synthetic API only, never ComfyUI.

Run with Playwright/Chromium: python tests/workshop_application.py --output .runtime/workshop-application
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import threading
from http.server import ThreadingHTTPServer

from playwright.sync_api import sync_playwright
import studio_browser_smoke as fixture

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / '.runtime/workshop-application')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    fixture.POSTS.clear()
    server = ThreadingHTTPServer(('127.0.0.1', 0), fixture.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    checks, errors = [], []
    try:
        with sync_playwright() as p:
            executable = os.environ.get('STUDIO_BROWSER_EXECUTABLE') or shutil.which('chromium')
            browser = p.chromium.launch(**({'executable_path': executable} if executable else {}))
            context = browser.new_context(viewport={'width':1440,'height':900})
            page = context.new_page()
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(origin + '/#create')
            page.wait_for_function('!!selected && schemaAvailable && !!document.querySelector("#workshopRecipeChange")')
            page.wait_for_function('document.querySelector("#workshopEta").textContent.includes("42")')
            page.wait_for_timeout(200)
            height = page.evaluate('document.documentElement.scrollHeight')
            # Focus keeps Recent runs closed; the collapsed Problems summary stays in the first viewport.
            assert height < 1700, height
            assert not page.locator('#workshopResults').evaluate('(el)=>el.open')
            assert page.evaluate("document.getElementById('jobProblemsHost') && !document.getElementById('workshopResults').contains(document.getElementById('jobProblemsHost'))")
            for selector in ['#positive','#generate','#workshopRecipeChange']:
                box = page.locator(selector).bounding_box()
                assert box and box['y'] >= 0 and box['y'] + box['height'] < 900, (selector,box)
            assert not page.locator('#negativeWrap').evaluate('(el)=>el.open')
            assert not page.locator('.ux-parameters').evaluate('(el)=>el.open')
            assert not page.locator('#workshopInspect').evaluate('(el)=>el.open')
            assert page.locator('#workshopLayout').input_value() == 'focus'
            assert page.locator('#workshopSkin').input_value() == 'atelier'
            assert page.locator('#workshopAmbience').input_value() == 'none'
            assert page.locator('#workshopAmbienceHero').is_hidden()
            stored = page.evaluate("JSON.parse(localStorage.getItem('studio.workshop.presentation.v2'))")
            assert stored == {'layout':'focus','skin':'atelier','ambience':'none'}, stored
            checks.append({'name':'real app default first viewport','document_height':height})
            page.screenshot(path=str(args.output/'application-focus.png'),full_page=True)
            # #598: the Prompt Lab handoff panel had no grid area, so the named templates auto-placed it in the
            # first free full-width row - measured at y=1353 (Focus) and y=1358 (Studio), ~1250 px below the fold.
            # It now takes the heading row; the hidden state must create no row at all.
            # Draft PR #625 covered mobile width and a visible ambience hero; both change which row is free.
            transfer=[]
            for layout,ambience in [(l,a) for l in ['focus','studio','immersive'] for a in ['none','night-shift']]:
                page.select_option('#workshopLayout',layout);page.select_option('#workshopAmbience',ambience);page.wait_for_timeout(120)
                closed=page.evaluate("()=>[document.querySelector('.ux-create-heading').getBoundingClientRect().y,document.querySelector('#createView .editor').getBoundingClientRect().y,document.documentElement.scrollHeight]")
                page.evaluate("document.querySelector('#uxTransfer').hidden=false");page.wait_for_timeout(120)
                heading=page.locator('.ux-create-heading').bounding_box()
                panel=page.locator('#uxTransfer').bounding_box();apply_button=page.locator('#uxApplyPrompt').bounding_box()
                # The panel follows the heading in DOM order, so it must follow it on screen and stay above the editor.
                assert panel['y']+panel['height']<=page.locator('#createView .editor').bounding_box()['y']+1,(layout,panel)
                assert layout=='immersive' or panel['y']>=heading['y']+heading['height']-1,(layout,heading,panel)
                # The handoff is useless below the fold: its primary Apply control must be in the first viewport.
                assert 0<=apply_button['y'] and apply_button['y']+apply_button['height']<=900,(layout,apply_button)
                assert layout=='immersive' or panel['width']>=heading['width']-1,(layout,panel,heading)
                page.evaluate("document.querySelector('#uxTransfer').hidden=true");page.wait_for_timeout(120)
                # Hiding it again restores the exact geometry of a Create view that never received a handoff.
                assert page.evaluate("()=>[document.querySelector('.ux-create-heading').getBoundingClientRect().y,document.querySelector('#createView .editor').getBoundingClientRect().y,document.documentElement.scrollHeight]")==closed,(layout,closed)
                transfer.append({'layout':layout,'ambience':ambience,'panel_y':round(panel['y']),'apply_y':round(apply_button['y']),'editor_y':closed[1]})
            page.select_option('#workshopLayout','focus');page.select_option('#workshopAmbience','none');page.wait_for_timeout(120)
            narrow=browser.new_page(viewport={'width':390,'height':844});narrow.on('pageerror',lambda e:errors.append(str(e)))
            narrow.goto(origin+'/#create');narrow.wait_for_function('!!selected && schemaAvailable && !!document.querySelector("#workshopRecipeChange")')
            for layout in ['focus','immersive']:
                narrow.select_option('#workshopLayout',layout)
                narrow.evaluate("document.querySelector('#uxTransfer').hidden=false");narrow.wait_for_timeout(120)
                small=narrow.locator('#uxApplyPrompt').bounding_box()
                assert small['y']+small['height']<=844,(layout,small)
                assert narrow.evaluate('document.documentElement.scrollWidth<=innerWidth'),layout
                transfer.append({'layout':layout,'width':390,'apply_y':round(small['y'])})
                narrow.evaluate("document.querySelector('#uxTransfer').hidden=true")
            narrow.close()
            checks.append({'name':'Prompt Lab handoff panel stays in the first viewport and costs nothing when hidden','cases':transfer})
            # Preserve input identity, source and pending draft through presentation changes.
            page.evaluate("window.keptPrompt=document.querySelector('#positive');window.keptGenerate=document.querySelector('#generate');window.keptReference=document.querySelector('#reference')")
            page.fill('#positive','A private draft that must not disappear')
            page.click('#workshopRecipeChange')
            assert page.locator('#presetSearch').evaluate('(el)=>el===document.activeElement')
            page.screenshot(path=str(args.output/'application-recipes.png'),full_page=True)
            page.keyboard.press('Escape')
            assert page.locator('#workshopRecipeChange').evaluate('(el)=>el===document.activeElement')
            page.click('#workshopRecipeChange')
            page.fill('#presetSearch','Krea')
            page.once('dialog',lambda d:d.dismiss())
            page.locator('#presetList button[data-id]').first.click()
            assert page.locator('#positive').input_value()=='A private draft that must not disappear'
            page.keyboard.press('Escape')
            page.click('#negativeWrap > summary')
            page.wait_for_function('Object.keys(localStorage).some(key=>key.startsWith("studio-draft-v1:") && (localStorage.getItem(key)||"").includes("A private draft that must not disappear"))')
            page.reload()
            page.wait_for_function('!!selected && schemaAvailable && !!document.querySelector("#workshopRecipeChange")')
            assert page.locator('#negativeWrap').evaluate('(el)=>el.open'), 'explicit negative disclosure choice survives reload'
            page.wait_for_selector('#uxRestoreDraft:not([hidden])')
            page.click('#uxRestoreDraft')
            page.wait_for_function('document.querySelector("#positive").value==="A private draft that must not disappear"')
            checks.append({'name':'native Escape/focus, cancellation, reload recovery and disclosure preference'})
            page.evaluate("selectPreset('qwen-1ref')")
            assert page.locator('#generate').is_disabled()
            page.click('#uxPullAsset')
            page.wait_for_selector('[data-ux-pull="asset-0"]')
            page.click('[data-ux-pull="asset-0"]')
            page.wait_for_function('parentAssets[0]==="asset-0" && !!uploaded')
            page.fill('#positive','Keep this source and its lineage')
            before = page.evaluate('JSON.stringify({controls:values(),uploaded,lastUploaded,parentAssets,parentByInput})')
            page.evaluate("window.keptPrompt=document.querySelector('#positive');window.keptGenerate=document.querySelector('#generate');window.keptReference=document.querySelector('#reference')")
            layouts=page.locator('#workshopLayout option').evaluate_all('(els)=>els.map(e=>e.value)')
            skins=page.locator('#workshopSkin option').evaluate_all('(els)=>els.map(e=>e.value)')
            ambiences=page.locator('#workshopAmbience option').evaluate_all('(els)=>els.map(e=>e.value)')
            for layout in layouts:
                for skin in skins:
                    for ambience in ambiences:
                        page.select_option('#workshopLayout',layout)
                        page.select_option('#workshopSkin',skin)
                        page.select_option('#workshopAmbience',ambience)
                        assert page.evaluate('JSON.stringify({controls:values(),uploaded,lastUploaded,parentAssets,parentByInput})') == before
                        assert page.evaluate("keptPrompt===document.querySelector('#positive') && keptGenerate===document.querySelector('#generate') && keptReference===document.querySelector('#reference')")
            assert not [row for row in fixture.POSTS if row['path']=='/api/jobs']
            checks.append({'name':'all presentation combinations preserve real source lineage, controls and zero submissions','layouts':layouts,'skins':skins,'ambiences':ambiences})
            page.select_option('#workshopLayout','focus')
            page.select_option('#workshopSkin','atelier')
            page.select_option('#workshopAmbience','none')
            page.click('#workshopTune')
            assert page.locator('[data-key="seed"]').is_visible()
            page.fill('[data-key="seed"]','1024')
            page.wait_for_function('document.querySelector(".wk-parameter-summary").textContent.includes("1024")')
            page.evaluate("showView('home')")
            assert not page.locator('#generate').is_visible()
            page.evaluate("showView('create')")
            assert page.locator('#generate').is_visible()
            # The real original handler reaches the fixture once. The fixture deliberately
            # refuses the mutation; no synthetic success or accepted generation is invented.
            assert page.locator('#generate').is_enabled()
            page.click('#generate')
            page.wait_for_function('document.querySelector("#status").textContent.includes("Unexpected mutation blocked")')
            submissions=[row for row in fixture.POSTS if row['path']=='/api/jobs']
            assert len(submissions)==1,submissions
            assert submissions[0]['data']['preset_id']=='qwen-1ref'
            assert submissions[0]['data']['controls']['positive']=='Keep this source and its lineage'
            checks.append({'name':'one explicit request reaches original submission handler; fixture rejects execution'})
            geometry=[]
            for width,h in [(390,844),(1440,900)]:
                for layout in layouts:
                    for skin in skins:
                        fresh=browser.new_page(viewport={'width':width,'height':h})
                        fresh.on('pageerror',lambda e:errors.append(str(e)))
                        fresh.goto(origin+'/#create')
                        fresh.wait_for_function('!!selected && schemaAvailable && !!document.querySelector("#workshopRecipeChange")')
                        fresh.select_option('#workshopLayout',layout)
                        fresh.select_option('#workshopSkin',skin)
                        fresh.select_option('#workshopAmbience','night-shift' if layout=='immersive' else 'none')
                        fresh.wait_for_timeout(150)
                        assert fresh.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,layout,skin)
                        box=fresh.locator('#generate').bounding_box()
                        assert box['y']>=0 and box['y']+box['height']<=h,(width,layout,skin,box)
                        assert fresh.locator('#workshopAmbienceHero').is_visible() == (layout=='immersive')
                        if layout=='immersive':
                            assert fresh.locator('#workshopSetupRail').is_visible()
                            assert fresh.locator('#workshopGuidance').is_visible()
                            setup_width=fresh.locator('#workshopSetupRail').bounding_box()['width']
                            editor_width=fresh.locator('#createView .editor').bounding_box()['width']
                            if width<600:
                                assert setup_width>=width-40,(width,setup_width)
                                assert editor_width>=width-40,(width,editor_width)
                            else:
                                assert setup_width>=230,(width,setup_width)
                                assert editor_width>=480,(width,editor_width)
                        if (layout,skin) in {('focus','atelier'),('studio','sakura'),('immersive','retro-anime')}:
                            fresh.screenshot(path=str(args.output/f'application-{layout}-{skin}-{width}.png'),full_page=True)
                        geometry.append({'width':width,'layout':layout,'skin':skin})
                        fresh.close()
            assert not errors,errors
            assert len([row for row in fixture.POSTS if row['path']=='/api/jobs'])==1
            checks.append({'name':'desktop/mobile layout × skin matrix; no page exceptions or additional submissions','cases':geometry})
            browser.close()
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
        (args.output/'report.json').write_text(json.dumps({'synthetic_api':True,'live_comfyui':False,'checks':checks,'page_errors':errors},indent=2)+'\n')
    print(json.dumps(checks,indent=2))

if __name__ == '__main__':
    main()
