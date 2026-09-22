"""Offline, no-network exercise of the export using the production presentation module."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('workshop_export',ROOT/'scripts/export-workshop-prototype.py')
exporter=importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'.runtime/workshop-prototype')
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=True)
    html=exporter.export();errors=[];requests=[]
    assert 'workshopImmersiveStyles' in html
    assert html.count('data:image/svg+xml;base64,') >= 4  # legacy skin motifs plus paired ambience
    with sync_playwright() as p:
        executable=os.environ.get('STUDIO_BROWSER_EXECUTABLE') or shutil.which('chromium')
        browser=p.chromium.launch(**({'executable_path':executable} if executable else {}))
        page=browser.new_page(viewport={'width':1440,'height':900})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda req:requests.append(req.url) if not req.url.startswith(('data:','blob:')) else None)
        page.set_content(html,wait_until='load')
        page.wait_for_function('document.querySelector("#workshopLayout")?.value==="immersive" && document.querySelector("#workshopSkin")?.value==="retro-anime" && document.querySelector("#workshopAmbience")?.value==="night-shift"')
        original_name=page.evaluate('selected.name')
        long_name='A long recipe name with settings, references and an exact version '+('x'*100)
        for width,height in [(1440,900),(390,844)]:
            page.set_viewport_size({'width':width,'height':height})
            for layout in ('focus','studio','immersive'):
                page.select_option('#workshopLayout',layout)
                page.evaluate('(name)=>{selected.name=name;document.querySelector("#createView").__workshop.sync()}',long_name)
                assert not page.locator('.wk-recipe > div').is_visible(), 'the export must not repeat the active recipe label'
                button=page.locator('#workshopRecipeChange')
                assert button.inner_text()=='Change: '+long_name
                box=button.bounding_box()
                assert box and box['width']>80 and box['x']>=0 and box['x']+box['width']<=width, box
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.evaluate('(name)=>{selected.name=name;document.querySelector("#createView").__workshop.sync()}',original_name)
        page.set_viewport_size({'width':1440,'height':900})
        assert page.locator('#demoArtwork').evaluate('(el)=>el.complete&&el.naturalWidth>0')
        assert page.locator('#workshopAmbienceHero').is_visible()
        for layout,skin,ambience in [('focus','atelier','none'),('studio','sakura','quiet-morning'),('immersive','retro-anime','night-shift')]:
            page.select_option('#workshopLayout',layout);page.select_option('#workshopSkin',skin);page.select_option('#workshopAmbience',ambience)
            page.screenshot(path=str(out/f'{layout}-{skin}-{ambience}.png'))
        page.fill('#positive','Keep my experimental brief')
        page.click('#workshopRecipeChange');page.fill('#presetSearch','Refine')
        page.once('dialog',lambda d:d.dismiss());page.locator('[data-id=refine]').click()
        assert page.locator('#positive').input_value()=='Keep my experimental brief'
        page.once('dialog',lambda d:d.accept());page.locator('[data-id=refine]').click()
        page.wait_for_function('!document.querySelector("#workshopRecipeDialog").open')
        page.locator('#reference').set_input_files(ROOT/'examples/gallery/pixel-lora-128.png')
        page.wait_for_function('!document.querySelector("#demoSource").hidden && document.querySelector("#demoSource").naturalWidth>0')
        page.select_option('#workshopLayout','focus');page.select_option('#workshopSkin','atelier');page.select_option('#workshopAmbience','none')
        assert page.locator('#reference').evaluate('(el)=>el.files.length')==1
        page.click('#generate')
        assert 'No job was submitted' in page.locator('#status').inner_text()
        page.click('#workshopTune');page.locator('[data-key=lora]').fill('0.5')
        assert page.locator('#demoStrength').inner_text()=='0.5'
        page.select_option('#workshopLayout','immersive');page.select_option('#workshopSkin','retro-anime');page.select_option('#workshopAmbience','night-shift')
        assert page.locator('#workshopGuidance').is_visible()
        page.locator('.wk-modebar a').first.click()
        assert page.locator('#demoNotice').is_visible()
        before=page.locator('#status').inner_text()
        assert page.locator('#workshopGuidanceAction').get_attribute('data-intent')=='open-results'
        page.click('#workshopGuidanceAction')
        assert page.locator('#workshopResults').evaluate('(el)=>el.open')
        assert page.locator('#status').inner_text()==before
        page.set_viewport_size({'width':390,'height':844})
        for layout in ['focus','studio','immersive']:
            page.select_option('#workshopLayout',layout)
            page.select_option('#workshopAmbience','night-shift' if layout=='immersive' else 'none')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            if layout=='immersive':
                assert page.locator('#workshopGuidance').is_visible()
                assert page.locator('#workshopSetupRail').bounding_box()['width']>=350
                assert page.locator('#createView .editor').bounding_box()['width']>=350
            page.screenshot(path=str(out/f'{layout}-mobile.png'))
        assert not errors,errors
        assert not requests,requests
        browser.close()
    checks=['standalone recipe labels and long-name geometry','Immersive + Retro Anime + Night Shift review default','embedded repository and paired local ambience art','guarded recipe replacement','local reference survives presentation switch','demo preview, no submission','adapter input feedback','offline route interception','read-only guidance','mobile geometry']
    (out/'report.json').write_text(json.dumps({'no_network_requests':True,'page_errors':errors,'checks':checks},indent=2)+'\n')
    print('Prototype: 10 checks passed; no network requests or page exceptions')

if __name__=='__main__':main()
