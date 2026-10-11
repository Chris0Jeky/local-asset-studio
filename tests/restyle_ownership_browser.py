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
# A cold hosted runner can miss the first page load inside the 5 s interaction budget (#911).
FIRST_LOAD_MS = 20000


async def exercise_preparation_ownership(page, check, out):
    """Native modal/click behavior and shipped handlers; deferred synthetic API only."""
    await page.evaluate("""() => {
      window.__beforePreparationAPI=api;window.__prepareWrites=[];window.__prepareFinish={};
      window.__prepareHold=false;window.__finishPreparationJob=null;
      api=async(url,options={})=>{
        if(url.startsWith('/api/tiles/source/')||url.startsWith('/api/parallax/source/'))
          return {asset_id:'asset-0',eligible:true,width:1024,height:1024,max_views:3,flag:'Synthetic eligible source'};
        if(url==='/api/jobs'&&options.method==='POST'){
          window.__prepareWrites.push(url);
          await new Promise(resolve=>window.__finishPreparationJob=resolve);
          return {id:'synthetic-preparation-job',message:'Synthetic queued receipt'};
        }
        if(url==='/api/tiles/prepare'||url==='/api/parallax/prepare'){
          window.__prepareWrites.push(url);
          const tile=url.includes('/tiles/'),request=JSON.parse(options.body),preset=tile?'zimage-seam-repair':'parallax-edit';
          const file='a'.repeat(32)+'_prepared.png';
          const plan={version:1,plan_id:'b'.repeat(64),source_asset_id:request.asset_id,source_sha256:'c'.repeat(64),
            source_file:file,rolled_file:file,preset_id:preset,width:1024,height:1024,band_px:request.band_px??80};
          const result={plan,claim:{...plan,stage:'plate'},stage:'plate',file,preset_id:preset,width:1024,height:1024,
            words:'Synthetic clean plate wording',context:{title:'Synthetic source',positive:'Synthetic tile wording'},flag:'Synthetic preparation'};
          if(window.__prepareHold)await new Promise(resolve=>window.__prepareFinish[tile?'tile':'parallax']=()=>resolve(result));
          return result;
        }
        return window.__beforePreparationAPI(url,options);
      };
      window.__resetPreparation=()=>{
        submitting=false;selectPreset('anima-portrait',true,true);document.querySelector('#positive').value='Existing editor intent';
        window.__prepareWrites=[];window.__prepareFinish={};window.__finishPreparationJob=null;
        document.querySelector('#uxNotice').textContent='';
        showView('create');updateReady();
      };
      window.__preparationEditor=()=>JSON.stringify({preset:selected.id,controls:values(),parents:parentAssets,
        uploaded,continuation:continuationState,tile:tileState,parallax:parallaxState});
    }""")
    results=[]
    def record(name, value): results.append({'name':name,'passed':bool(value)})
    async def start(kind, held=True):
        await page.evaluate('(held)=>{window.__resetPreparation();window.__prepareHold=held;openAsset("asset-0")}', held)
        await page.wait_for_function("document.querySelector('[data-ux-tile]')&&!document.querySelector('[data-ux-tile]').disabled")
        await page.fill('#uxParallaxObjects', 'the foreground desk')
        await page.wait_for_function("!document.querySelector('[data-ux-parallax]').disabled")
        before=await page.evaluate('window.__preparationEditor()')
        await page.click('[data-ux-'+kind+']')
        if held: await page.wait_for_function('(kind)=>typeof window.__prepareFinish[kind]==="function"',arg=kind)
        else: await page.wait_for_function('!document.querySelector("#assetDialog").open')
        return before
    async def finish(kind):
        await page.evaluate('(kind)=>window.__prepareFinish[kind]()', kind)
        # Each preparation announces its outcome before its synchronous finally.
        await page.wait_for_function('''() => {
          const text=document.querySelector('#uxNotice').textContent;
          return ['Nothing was applied','Parallax layers prepared:','Seam cross prepared:',
            'Wait for the current submission before preparing a tile.'].some(value=>text.includes(value));
        }''')
    try:
        for kind,preset in (('tile','zimage-seam-repair'),('parallax','parallax-edit')):
            await start(kind, held=False)
            record(kind+' normal preparation adopts without generation',await page.evaluate('(preset)=>selected.id===preset&&!window.__prepareWrites.includes("/api/jobs")',preset))
            before=await start(kind)
            await page.keyboard.press('Escape')
            await page.wait_for_function('!document.querySelector("#assetDialog").open')
            record(kind+' pending preparation owns readiness after close',await page.evaluate('document.querySelector("#generate").disabled'))
            await page.evaluate('document.querySelector("#generate").click()')
            await page.evaluate('document.querySelector("#generate").onclick()')
            record(kind+' shipped handler refuses jobs while preparing',not await page.evaluate('window.__prepareWrites.includes("/api/jobs")'))
            await finish(kind)
            record(kind+' closed-dialog response preserves editor',await page.evaluate('window.__preparationEditor()')==before)
            record(kind+' pending preparation admits zero job posts',not await page.evaluate('window.__prepareWrites.includes("/api/jobs")'))
            if await page.evaluate('typeof window.__finishPreparationJob==="function"'):
                await page.evaluate('window.__finishPreparationJob()')
                await page.wait_for_function('!submitting')
            before=await start(kind)
            await page.keyboard.press('Escape')
            await page.wait_for_function('!document.querySelector("#assetDialog").open')
            await page.evaluate('openAsset("asset-0")')
            await page.wait_for_function('document.querySelector("#assetDialog").open')
            await finish(kind)
            record(kind+' reopened same asset rejects old request',await page.evaluate('window.__preparationEditor()')==before)
            record(kind+' old request does not close newer dialog',await page.evaluate('document.querySelector("#assetDialog").open'))
            await page.keyboard.press('Escape')
            before=await start(kind)
            await page.evaluate('submitting=true;updateReady()')
            await page.keyboard.press('Escape')
            await finish(kind)
            record(kind+' competing submission refuses response',await page.evaluate('window.__preparationEditor()')==before)
            await page.evaluate('submitting=false;updateReady()')
        await start('parallax')
        await page.click('[data-ux-tile]')
        record('parallax preparation refuses competing tile request',not await page.evaluate('window.__prepareWrites.includes("/api/tiles/prepare")'))
        if await page.evaluate('typeof window.__prepareFinish.tile==="function"'):
            await page.evaluate('window.__prepareFinish.tile()')
        await page.keyboard.press('Escape')
        await finish('parallax')
    finally:
        await page.evaluate('''async () => {
          Object.values(window.__prepareFinish).forEach(resolve=>resolve());
          if(window.__finishPreparationJob)window.__finishPreparationJob();
          await new Promise(resolve=>setTimeout(resolve,0));
        }''')
        await page.wait_for_function('!submitting')
        await page.evaluate('''() => {
          if(document.querySelector('#assetDialog').open)document.querySelector('#assetDialog').close();
          api=window.__beforePreparationAPI;submitting=false;window.__resetPreparation();
        }''')
        (out/'preparation-report.json').write_text(json.dumps({'checks':results,'transport':'synthetic API/native DOM',
            'model_execution':False},indent=2)+'\n',encoding='utf-8')
    for result in results: check(result['name'],result['passed'])


async def run(args):
    args.out.mkdir(parents=True, exist_ok=True)
    fixture.POSTS.clear()
    server = fixture.ThreadingHTTPServer(('127.0.0.1', 0), fixture.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    checks, errors, completed = [], [], False
    navigations=[]

    def check(name, result):
        checks.append({'name': name, 'passed': bool(result)})
        print(name, bool(result), flush=True)
        assert result, name

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(executable_path=shutil.which('chromium'),
                                               headless=True, args=['--no-sandbox'])
            page = await browser.new_page(viewport={'width': 1440, 'height': 1100})
            context=page.context
            await context.tracing.start(screenshots=True,snapshots=True,sources=True)
            page.on('framenavigated',lambda frame:navigations.append(frame.url) if frame==page.main_frame else None)
            page.set_default_timeout(5000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            try:
                if args.inert:
                    await inert_page(page, server.server_port)
                else:
                    await page.goto(f'http://127.0.0.1:{server.server_port}/#create',timeout=FIRST_LOAD_MS)
                await page.wait_for_function('!!catalog && !!selected && schemaAvailable',timeout=FIRST_LOAD_MS)
                await page.wait_for_function("assetState.assets.some(a=>a.id==='asset-0')",timeout=FIRST_LOAD_MS)
                await exercise_source_choices(page, check)
                await exercise_preparation_ownership(page, check, args.out)
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
            finally:
                await context.tracing.stop(path=str(args.out/'trace.zip'))
                await browser.close()
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
        report = {'mode': 'inert explicit transport/storage' if args.inert else 'native HTTP',
                  'checks': checks, 'errors': errors, 'navigations':navigations, 'completed': completed, 'model_execution': False}
        (args.out/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT/'.runtime/restyle-ownership')
    parser.add_argument('--inert', action='store_true')
    asyncio.run(run(parser.parse_args()))
