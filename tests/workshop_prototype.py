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
    with sync_playwright() as p:
        executable=os.environ.get('STUDIO_BROWSER_EXECUTABLE') or shutil.which('chromium')
        browser=p.chromium.launch(**({'executable_path':executable} if executable else {}))
        page=browser.new_page(viewport={'width':1440,'height':900})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda req:requests.append(req.url) if not req.url.startswith(('data:','blob:')) else None)
        page.set_content(html,wait_until='load')
        page.wait_for_function('document.querySelector("#workshopLayout")?.value==="studio"')
        assert page.locator('#demoArtwork').evaluate('(el)=>el.complete&&el.naturalWidth>0')
        for layout,skin in [('focus','atelier'),('studio','atelier'),('studio','arcade'),('studio','sakura')]:
            page.select_option('#workshopLayout',layout);page.select_option('#workshopSkin',skin)
            page.screenshot(path=str(out/f'{layout}-{skin}.png'))
        page.fill('#positive','Keep my experimental brief')
        page.click('#workshopRecipeChange');page.fill('#presetSearch','Refine')
        page.once('dialog',lambda d:d.dismiss());page.locator('[data-id=refine]').click()
        assert page.locator('#positive').input_value()=='Keep my experimental brief'
        page.once('dialog',lambda d:d.accept());page.locator('[data-id=refine]').click()
        page.wait_for_function('!document.querySelector("#workshopRecipeDialog").open')
        page.locator('#reference').set_input_files(ROOT/'examples/gallery/pixel-lora-128.png')
        page.wait_for_function('!document.querySelector("#demoSource").hidden && document.querySelector("#demoSource").naturalWidth>0')
        page.select_option('#workshopLayout','focus');page.select_option('#workshopSkin','atelier')
        assert page.locator('#reference').evaluate('(el)=>el.files.length')==1
        page.click('#generate')
        assert 'No job was submitted' in page.locator('#status').inner_text()
        page.click('#workshopTune');page.locator('[data-key=lora]').fill('0.5')
        assert page.locator('#demoStrength').inner_text()=='0.5'
        page.set_viewport_size({'width':390,'height':844})
        for layout in ['focus','studio']:
            page.select_option('#workshopLayout',layout)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(out/f'{layout}-mobile.png'))
        assert not errors,errors
        assert not requests,requests
        browser.close()
    (out/'report.json').write_text(json.dumps({'no_network_requests':True,'page_errors':errors,'checks':['shared production layouts/skins','embedded repository art','guarded recipe replacement','local reference survives presentation switch','demo preview, no submission','adapter input feedback','mobile geometry']},indent=2)+'\n')
    print('Prototype: 7 checks passed; no network requests or page exceptions')

if __name__=='__main__':main()
