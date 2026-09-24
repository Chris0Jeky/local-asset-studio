"""Actual Create shell: File retention, modal behavior and deferred reference ownership.

Native: python tests/restyle_ownership_browser.py --out .runtime/restyle-ownership
Restricted environments: add --inert (explicit test storage/API bridge; not native origin proof).
No models, originals or generation are touched. Synthetic API data only.
"""
import argparse
import asyncio
import json
import shutil
import threading
from pathlib import Path

from playwright.async_api import async_playwright
import studio_browser_smoke as fixture
from asset_detail_browser import inert_page
from source_slot_choices_browser import exercise_source_choices

ROOT = Path(__file__).resolve().parents[1]


async def run(args):
    args.out.mkdir(parents=True, exist_ok=True)
    fixture.POSTS.clear()
    server = fixture.ThreadingHTTPServer(('127.0.0.1', 0), fixture.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    checks, errors, completed = [], [], False

    def check(name, result):
        checks.append({'name': name, 'passed': bool(result)})
        print(name, bool(result), flush=True)
        assert result, name

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(executable_path=shutil.which('chromium'),
                                               headless=True, args=['--no-sandbox'])
            page = await browser.new_page(viewport={'width': 1440, 'height': 1100})
            page.set_default_timeout(5000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            if args.inert:
                await inert_page(page, server.server_port)
            else:
                await page.goto(f'http://127.0.0.1:{server.server_port}/#create')
            await page.wait_for_function('!!catalog && !!selected && schemaAvailable')
            await page.wait_for_function("assetState.assets.some(a=>a.id==='asset-0')")
            await exercise_source_choices(page, check)
            await page.set_viewport_size({'width':1440, 'height':1100})
            await page.evaluate("""() => {
              window.__writes=[];window.__contextFails=false;window.__delayStyle=false;
              const original=api;
              api=async(url,options={})=>{
                if(options.method==='POST')window.__writes.push(url);
                if(url.endsWith('/context')&&window.__contextFails)throw Error('Synthetic context outage');
                if(url==='/api/upload')return {file:'local-look.png',sha256:'b'.repeat(64),width:32,height:32};
                if(url==='/api/assets/reference'&&JSON.parse(options.body).id==='asset-1'&&window.__delayStyle){
                  const result=await original(url,options);
                  await new Promise(resolve=>{window.__finishStyle=resolve});return result;
                }
                return original(url,options);
              };
              window.__reset=()=>{
                selectPreset('gentle-variation',true,true);
                const a=assetState.assets.find(a=>a.id==='asset-0');a.trashed_at=null;
                const context={version:1,asset_id:a.id,sha256:a.sha256,title:a.title,preset_id:'anima-portrait',
                  preset_name:'Synthetic UX fixture',job_id:'fixture-job',prompt_id:'fixture-prompt',
                  positive:'Explore one form, then continue with a variation.',negative:'blur',
                  prompt_origin:'submitted-output',prompt_role:'description',warning:'',width:512,height:768};
                beginContinuation({file:'a'.repeat(32)+'_kept-source.png',sha256:a.sha256,width:512,height:768,parent_asset:a.id,context},'gentle-variation','edit');
                showView('create');
              };
              window.__reset();
            }""")
            image = {'name': 'my-look.png', 'mimeType': 'image/png', 'buffer': (ROOT/'examples/references/lantern-reference.png').read_bytes()}
            await page.set_input_files('#reference', image)
            await page.evaluate("window.__picked=document.querySelector('#reference').files[0];assetState.assets.find(a=>a.id==='asset-0').trashed_at=123")
            await page.click('#uxSecondRestyle')
            check('refused opening retains exact native File and visible choice', await page.evaluate("document.querySelector('#reference').files[0]===window.__picked && !document.querySelector('#uxSecondPicture').hidden && !document.querySelector('#uxHandoff').open"))
            check('refused opening stages nothing', not await page.evaluate("window.__writes.some(url=>['/api/upload','/api/assets/reference','/api/jobs'].includes(url))"))
            await page.evaluate("assetState.assets.find(a=>a.id==='asset-0').trashed_at=null;window.__contextFails=true")
            await page.click('#uxSecondRestyle')
            await page.wait_for_function("document.querySelector('#uxHandoffStatus').textContent.includes('Synthetic context outage')")
            await page.keyboard.press('Escape')
            check('failed context and cancelled modal retain exact File', await page.evaluate("document.querySelector('#reference').files[0]===window.__picked && !document.querySelector('#uxSecondPicture').hidden"))
            await page.evaluate('window.__contextFails=false')
            await page.click('#uxSecondRestyle')
            await page.wait_for_function("!document.querySelector('#uxPrepareHandoff').disabled")
            await page.keyboard.press('Escape')
            check('cancelled valid handoff retains exact File', await page.evaluate("document.querySelector('#reference').files[0]===window.__picked"))
            await page.click('#uxSecondRestyle')
            await page.click('#uxPrepareHandoff')
            await page.wait_for_function("referenceRecords[0]?.file==='local-look.png' && referencePending===0")
            check('successful Prepare consumes the choice but preserves named source lineage', await page.evaluate("document.querySelector('#uxSecondPicture').hidden && document.querySelector('#reference').files.length===0 && parentByInput.lastReference==='asset-0' && parentAssets.includes('asset-0') && lastUploaded===continuationState.reference_file"))
            check('dialog API distinguishes modal reentry from a modeless conflict', await page.evaluate("""() => {
              const d=document.createElement('dialog');document.body.append(d);
              try{d.showModal();d.showModal();d.close();d.show();try{d.showModal();return false;}catch(e){return e.name==='InvalidStateError';}}
              finally{d.close();d.remove();}
            }"""))

            async def launch_library_style():
                await page.evaluate('window.__reset();window.__delayStyle=true;window.__finishStyle=null')
                await page.click('#uxPullAsset')
                await page.select_option('#uxSourceSlot', 'reference')
                await page.click('[data-ux-pull="asset-1"]')
                await page.click('#uxSecondRestyle')
                await page.click('#uxPrepareHandoff')
                await page.wait_for_function('typeof window.__finishStyle===\'function\'')

            await launch_library_style()
            await page.fill('#positive', 'New wording must survive the deferred picture copy.')
            await page.evaluate('window.__finishStyle()')
            await page.wait_for_function("referenceRecords[0]?.parent_asset==='asset-1' && referencePending===0")
            check('typing does not cancel a deferred board copy', await page.evaluate("document.querySelector('#positive').value==='New wording must survive the deferred picture copy.' && parentByInput.lastReference==='asset-0'"))
            await launch_library_style()
            await page.set_input_files('[data-ref-file="0"]', image)
            await page.wait_for_function("referenceRecords[0]?.file==='local-look.png'")
            await page.evaluate('window.__finishStyle()')
            await page.wait_for_function('referencePending===0')
            check('newer local upload wins over older library response', await page.evaluate("referenceRecords[0].file==='local-look.png' && !referenceRecords[0].parent_asset && !parentAssets.includes('asset-1') && parentByInput.lastReference==='asset-0'"))
            # Observe old bytes, then explicitly replace them before the old check responds.
            await page.evaluate("""() => {
              const original=api;
              api=(url,options={})=>url==='/api/references/check'
                ? new Promise(resolve=>{window.__finishCheck=resolve}) : original(url,options);
              window.__oldCheck=restoreReferenceSlots();
            }""")
            await page.set_input_files('[data-ref-file="0"]', image)
            await page.wait_for_function('referencePending===1')
            await page.evaluate("""async() => {
              window.__finishCheck([{file:'local-look.png',sha256:'b'.repeat(64),available:false}]);
              await window.__oldCheck;
            }""")
            check('stale availability does not invalidate a newly uploaded copy of the same bytes', await page.evaluate("!referenceRecords[0].missing && referencesReady() && referencePending===0 && parentByInput.lastReference==='asset-0'"))
            check('no generation submission', not await page.evaluate("window.__writes.includes('/api/jobs')"))
            check('no JavaScript exceptions', not errors)
            await page.screenshot(path=str(args.out/'final.png'), full_page=True)
            completed = True
            await browser.close()
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
        report = {'mode': 'inert explicit transport/storage' if args.inert else 'native HTTP',
                  'checks': checks, 'errors': errors, 'completed': completed, 'model_execution': False}
        (args.out/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT/'.runtime/restyle-ownership')
    parser.add_argument('--inert', action='store_true')
    asyncio.run(run(parser.parse_args()))
