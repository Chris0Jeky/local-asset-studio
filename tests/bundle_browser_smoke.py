"""Opt-in real-browser interaction fixture (not workstation or inference evidence).

Run: python tests/bundle_browser_smoke.py [screenshot-directory]
Requires Playwright and an already installed Chromium; never installs either.
The fixture implements the documented legacy workbench seam. The production
bundle JS/CSS run unchanged. Full Studio/Windows integration is a separate check.
"""
from pathlib import Path
import os
import shutil
import sys
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Bundle interaction fixture</title><link rel="stylesheet" href="/app/static/bundle-explorer.css"><body><main><p>Synthetic interaction fixture — no model inference.</p><div id="createView"><label><input id="presetSearch"></label><textarea id="positive"></textarea><select id="batch"><option>1</option><option selected>4</option></select></div><p id="status"></p></main>
<script>
const esc=v=>String(v??'').replace(/[&<>\'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const p={id:'paint',name:'Painterly workbench',family:'Paint',positive:['4','text'],seed:['7','seed'],steps:['7','steps'],cfg:['7','cfg'],width:['6','width'],height:['6','height'],lora_name:['9','lora_name'],lora:['9','strength_model'],lora2_name:['10','lora_name'],lora2:['10','strength_model'],defaults:{positive:'unchanged personal idea',seed:123,steps:15,cfg:1,width:768,height:1152,lora_name:'ink.safetensors',lora:1,lora2_name:'other.safetensors',lora2:0},dimension_multiple:16};
let catalog={presets:[p,{...p,id:'wash',name:'Watercolour workbench'}]},selected=p,work={...p.defaults,lora2:1},submitting=false,parentAssets=['original-asset'],referenceRecords=[],calls=[];
let atelierRecipes=[{id:'painted',name:'Painterly character study',family:'Paint',preset_id:'paint',tags:['painterly'],controls:{positive:'An original cartographer in a lantern-lit library',lora:0.7},status:'unverified',notes:'A bundled checkpoint, adapter stack and starting configuration. This is a synthetic browser-test fixture.'},{id:'wash',name:'Watercolour environment',family:'Paint',preset_id:'wash',controls:{positive:'A quiet greenhouse at dawn'},status:'executed',evidence:'Synthetic status fixture, not an actual run'}];
document.addEventListener('keydown',e=>{if(e.ctrlKey&&e.key==='Enter')calls.push('UNEXPECTED_GLOBAL_SUBMIT');});
let knowledge={updated:'2026-09-13',families:{Paint:{prompt:{style:'Describe subject, lighting and composition.'},axes:[{id:'steps',control:'steps',values:[8,15],rationale:'Illustrative fixture. Do not treat these values as a recommendation.',sources:['https://docs.comfy.org/tutorials/basic/lora']}]}},loras:{'ink.safetensors':{label:'Ink treatment',trigger:'ink study'}}};
async function api(path){const r=await fetch(path);if(!r.ok)throw Error('Fixture inspection failed');return r.json();}
function values(){return {...work};}function selectPreset(id){calls.push('select');selected=catalog.presets.find(p=>p.id===id);work={...selected.defaults};parentAssets=[];document.querySelector('#batch').value='1';}function applyRecipe(r){calls.push('apply');work={...work,...r.controls};document.querySelector('#batch').value=String(r.batch_count);}function showView(v){calls.push('view:'+v);}function message(v){document.querySelector('#status').textContent=v;}
</script><script src="/app/static/bundle-core.js"></script><script src="/app/static/bundle-explorer.js"></script></body></html>'''



def run():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    markup = HTML.replace('<link rel="stylesheet" href="/app/static/bundle-explorer.css">', '<style>' + (ROOT / 'app/static/bundle-explorer.css').read_text() + '</style>')
    for name in ('bundle-core.js', 'bundle-explorer.js'):
        markup = markup.replace('<script src="/app/static/' + name + '"></script>', '<script>' + (ROOT / 'app/static' / name).read_text() + '</script>')
    mock = r"""<script>window.reads=[];window.fetch=async(path,options={})=>{reads.push({path,method:options.method||'GET'});if(path==='/static/bundle-showcase.json')return new Response(JSON.stringify({version:1,examples:{}}));const name=path.split('/').pop();if(name==='paint')await new Promise(resolve=>setTimeout(resolve,250));return new Response(JSON.stringify({graph:{'1':{inputs:{ckpt_name:name+'.safetensors'}},'9':{inputs:{lora_name:'ink.safetensors',strength_model:1}}},requirements:[]}));};</script>"""
    markup = markup.replace('<script>', mock + '<script>', 1)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=os.environ.get("STUDIO_TEST_BROWSER") or shutil.which("chromium"), args=["--no-sandbox"])
        for width in (1440, 390):
            page = browser.new_page(viewport={"width": width, "height": 1000}, reduced_motion="reduce")
            errors, writes = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: writes.append(request.url) if request.method != "GET" else None)
            page.set_content(markup)
            page.locator('#bundleLauncher').focus()
            page.keyboard.press('Enter')
            assert page.evaluate('document.activeElement.id') == 'bundleSearch'
            page.keyboard.press('Tab'); page.keyboard.press('Tab'); page.keyboard.press('Enter')
            page.wait_for_function("document.querySelector('#bundleIngredients').textContent.includes('paint.safetensors')")
            page.keyboard.press('Control+Enter')
            assert page.evaluate('calls.length') == 0
            assert page.evaluate("document.querySelector('#bundleExplorer').scrollWidth <= document.querySelector('#bundleExplorer').clientWidth")
            assert page.locator('#bundleApply').is_disabled()
            page.locator('[data-bundle-control="width"]').fill('769')
            assert page.locator('#bundleApply').is_disabled()
            assert 'multiple' in page.locator('#bundleApplyStatus').inner_text()
            page.locator('#bundleReset').click()
            page.locator('[data-bundle-control="steps"]').fill('18')
            assert 'not a preview' in page.locator('#bundleVariantNotice').inner_text()
            if output:
                page.locator('#bundleSelectedTitle').scroll_into_view_if_needed()
                page.screenshot(path=str(output / f'bundle-{width}.png'))
            # Cancel / Escape changes nothing and restores focus.
            page.keyboard.press('Escape')
            assert page.evaluate('calls.length') == 0
            assert page.evaluate('document.activeElement.id') == 'bundleLauncher'
            page.locator('#bundleLauncher').click()
            page.locator('[data-bundle="painted"]').click()
            # A later inspection cannot replace a newer selection.
            page.locator('[data-bundle="wash"]').click()
            page.wait_for_timeout(400)
            assert 'wash.safetensors' in page.locator('#bundleIngredients').inner_text()
            assert 'paint.safetensors' not in page.locator('#bundleIngredients').inner_text()
            page.locator('[data-bundle="painted"]').click()
            page.locator('#bundleConsent').check()
            page.evaluate("work.positive='changed elsewhere'")
            page.locator('#bundleApply').click()
            assert 'workbench changed' in page.locator('#bundleApplyStatus').inner_text()
            assert page.evaluate('calls.length') == 0
            # Re-review, then apply the complete baseline exactly once; no inherited adapter.
            page.locator('[data-bundle="painted"]').click()
            page.locator('#bundleConsent').check()
            page.locator('#bundleApply').click()
            assert page.evaluate('calls') == ['select', 'apply', 'view:create']
            assert page.evaluate('work.lora2') == 0
            assert page.locator('#batch').input_value() == '1'
            assert page.evaluate('parentAssets.length') == 0
            assert not page.locator('#bundleExplorer').is_visible()
            assert page.evaluate('document.activeElement.id') == 'positive'
            assert not writes, writes
            assert page.evaluate("reads.every(r=>r.method==='GET')")
            assert not errors, errors
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.close()
            print(f'PASS {width}px: browse, invalid input, edit/reset, cancel/focus, stale inspection, stale workbench, explicit single-output apply, zero writes')
        browser.close()


if __name__ == '__main__':
    run()
