"""Presentation contracts against a deterministic, explicitly non-generating DOM fixture.

Run: python tests/workshop_browser.py --output .runtime/workshop-qa
Uses Playwright's Chromium, or STUDIO_BROWSER_EXECUTABLE for a system browser.
This is not a live ComfyUI or full application qualification.
"""
import argparse
import json
import os
from pathlib import Path
import shutil

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / '.runtime/workshop-qa')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    def load(page):
        # Inline the exact production script/style: this also runs in offline browser sandboxes.
        html = (ROOT / 'tests/workshop_fixture.html').read_text()
        html = html.replace('<script src="/static/workshop.js"></script>', '<script>' + (ROOT / 'app/static/workshop.js').read_text() + '</script>')
        html = html.replace('</style>', '</style><style id="workshopStyles">' + (ROOT / 'app/static/workshop.css').read_text() + '</style>', 1)
        page.set_content(html)
    checks = []
    with sync_playwright() as p:
        executable = os.environ.get('STUDIO_BROWSER_EXECUTABLE') or shutil.which('chromium')
        browser = p.chromium.launch(**({'executable_path': executable} if executable else {}))
        page = browser.new_page(viewport={'width':1440,'height':900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        load(page)
        page.wait_for_selector('#workshopRecipeChange', timeout=5000)
        page.wait_for_timeout(100)
        assert page.evaluate('submitted') == 0
        assert page.evaluate("Object.entries(originalNodes).every(([id,node])=>document.getElementById(id)===node)")
        assert not page.locator('.ux-parameters').evaluate('(el)=>el.open')
        assert not page.locator('#negativeWrap').evaluate('(el)=>el.open')
        height=page.evaluate('document.documentElement.scrollHeight')
        assert height < 1600, height
        assert page.locator('#generate').bounding_box()['y'] < 900
        assert page.locator('#positive').bounding_box()['y'] < 900
        page.screenshot(path=str(args.output/'focus-atelier.png'),full_page=True)
        checks.append({'name':'desktop first viewport + original controls + no submission','height':height})
        page.locator('#positive').fill('My unsaved private draft')
        page.locator('#workshopRecipeChange').click()
        assert page.locator('#workshopRecipeDialog').evaluate('(el)=>el.open')
        assert page.locator('#presetSearch').evaluate('(el)=>el===document.activeElement')
        page.keyboard.press('Escape')
        assert page.locator('#workshopRecipeChange').evaluate('(el)=>el===document.activeElement')
        assert page.locator('#positive').input_value() == 'My unsaved private draft'
        page.locator('#workshopRecipeChange').click()
        page.locator('[data-id="ink"]').click()
        assert page.evaluate('selectionCount') == 0
        assert page.locator('#positive').input_value() == 'My unsaved private draft'
        page.locator('#workshopRecipeChange').click()
        page.once('dialog', lambda d: d.dismiss())
        page.locator('[data-id="refine"]').click()
        assert page.evaluate('selectionCount') == 0
        assert page.locator('#positive').input_value() == 'My unsaved private draft'
        page.once('dialog', lambda d: d.accept())
        page.locator('[data-id="refine"]').click()
        assert page.evaluate('selectionCount') == 1
        assert not page.locator('#workshopRecipeDialog').evaluate('(el)=>el.open')
        checks.append({'name':'native focus return + cancelled and accepted recipe replacement'})
        page.locator('#reference').set_input_files({'name':'source.png','mimeType':'image/png','buffer':b'fixture'})
        await_value=page.locator('#positive').input_value()
        layouts=page.locator('#workshopLayout option').evaluate_all('(els)=>els.map(e=>e.value)')
        skins=page.locator('#workshopSkin option').evaluate_all('(els)=>els.map(e=>e.value)')
        for layout in layouts:
            for skin in skins:
                page.select_option('#workshopLayout',layout)
                page.select_option('#workshopSkin',skin)
                assert page.locator('#positive').input_value()==await_value
                assert page.locator('#reference').evaluate('(el)=>el.files[0].name')=='source.png'
                assert page.evaluate('submitted')==0
        checks.append({'name':'all presentation combinations preserve draft and input identity','layouts':layouts,'skins':skins})
        page.evaluate("document.getElementById('uxBlockers').innerHTML='<div class=ux-blocker><p>Review image size</p><button data-ux-resolve=parameters>Review settings</button></div>'")
        page.locator('#workshopReview').click()
        page.locator('[data-ux-resolve="parameters"]').click()
        assert page.locator('[data-key="width"]').evaluate('(el)=>el===document.activeElement')
        assert page.locator('.ux-parameters').evaluate('(el)=>el.open')
        checks.append({'name':'readiness action still reveals and focuses original control'})
        page.evaluate("document.getElementById('createView').hidden=true")
        assert not page.locator('#generate').is_visible()
        page.evaluate("document.getElementById('createView').hidden=false")
        assert page.locator('#generate').is_visible()
        assert page.locator('#generate').is_disabled()
        page.evaluate("document.getElementById('generate').disabled=false")
        page.locator('#generate').click()
        assert page.evaluate('submitted')==1
        checks.append({'name':'route hiding and exactly one original explicit Generate handler'})
        page.close()
        for width,height in [(390,844),(1440,900)]:
            for layout in layouts:
                for skin in skins:
                    page=browser.new_page(viewport={'width':width,'height':height})
                    load(page)
                    page.wait_for_selector('#workshopRecipeChange')
                    page.select_option('#workshopLayout',layout)
                    page.select_option('#workshopSkin',skin)
                    page.wait_for_timeout(70)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),(width,layout,skin)
                    box=page.locator('#generate').bounding_box()
                    assert box['y']>=0 and box['y']+box['height']<=height,(box,width,layout,skin)
                    assert page.evaluate('submitted')==0
                    page.screenshot(path=str(args.output/f'{layout}-{skin}-{width}.png'),full_page=True)
                    page.close()
        assert not errors,errors
        checks.append({'name':'desktop/mobile layout × skin geometry and no page errors'})
        browser.close()
    (args.output/'report.json').write_text(json.dumps({'fixture':'workshop_fixture.html','live_comfyui':False,'checks':checks},indent=2)+'\n')
    print(json.dumps(checks,indent=2))

if __name__ == '__main__':
    main()
