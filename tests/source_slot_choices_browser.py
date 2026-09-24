"""Library-source choices on the actual Create UI, using synthetic API data only."""
import argparse
import asyncio
import json
import shutil
import threading
from pathlib import Path

from playwright.async_api import async_playwright
import studio_browser_smoke as fixture
from asset_detail_browser import inert_page

ROOT = Path(__file__).resolve().parents[1]


async def exercise_source_choices(page, check):
    await page.evaluate("""() => {
      window.__choiceCalls=[];window.__choiceFailure=false;window.__choiceDelay=false;
      const original=api;
      api=async(url,options={})=>{
        if(url==='/api/upload'&&window.__choiceUploadDelay){
          window.__choiceUploadedFile=options.body;
          await new Promise(resolve=>{window.__choiceUploadRelease=resolve});
          return {file:'later-role.png',sha256:'d'.repeat(64),width:640,height:640};
        }
        if(url==='/api/assets/reference'){
          window.__choiceCalls.push(JSON.parse(options.body).id);
          if(window.__choiceFailure)throw Error('Synthetic copy unavailable');
          if(window.__choiceDelay){
            const result=await original(url,options);
            await new Promise(resolve=>{window.__choiceRelease=resolve});return result;
          }
        }
        return original(url,options);
      };
      window.__choiceReset=async(id)=>{
        window.__choiceFailure=false;window.__choiceDelay=false;
        selectPreset(id,true,true);
        const result=await post('/api/assets/reference',{id:'asset-0'});
        beginContinuation(result,id,'edit');
        document.querySelector('#positive').value='Keep my source and edited wording';
        showView('create');updateReady();
        window.__choiceCalls=[];
      };
      window.__choiceSnapshot=()=>JSON.stringify({controls:values(),parents:parentAssets,
        mapping:parentByInput,refs:attachedReferencePayload(),claim:continuationState});
    }""")

    async def offer(recipe='qwen-3ref'):
        await page.evaluate('(id)=>window.__choiceReset(id)', recipe)
        await page.locator('#uxPullAsset').click()
        await page.locator('[data-ux-pull="asset-1"]').wait_for(state='visible')
        await page.select_option('#uxSourceSlot', '0')
        before = await page.evaluate('__choiceSnapshot()')
        await page.locator('[data-ux-pull="asset-1"]').click()
        check('protected source offers a visible decision instead of a dead end', await page.evaluate("!document.querySelector('#uxSourcePicker').open && !document.querySelector('#uxSecondPicture').hidden"))
        check('offering a choice preserves all draft fields and stages nothing', before == await page.evaluate('__choiceSnapshot()') and not await page.evaluate('__choiceCalls.length'))
        return before

    # A replacement is destructive only after copying succeeds. A failed read must
    # not consume the source, its wording, or the explicit decision surface.
    before = await offer()
    await page.evaluate('__choiceFailure=true')
    page.once('dialog', lambda dialog: dialog.accept())
    await page.locator('#uxSecondReplace').click()
    await page.wait_for_function("document.querySelector('#uxNotice').textContent.includes('Synthetic copy unavailable')")
    check('failed source replacement retains the complete live draft and choice', before == await page.evaluate('__choiceSnapshot()') and not await page.locator('#uxSecondPicture').is_hidden())

    for field in ('contribution', 'avoid', 'role'):
        await offer()
        await page.evaluate('__choiceDelay=true;delete window.__choiceRelease')
        await page.locator('[data-ux-second-slot="1"]').click()
        await page.wait_for_function("typeof window.__choiceRelease==='function'")
        control = page.locator(f'[data-ref-{field}="0"]')
        if field == 'role':
            await control.select_option('costume')
            await control.focus()
        else:
            await control.fill('Keep this later reference wording')
            await control.evaluate('(n)=>n.setSelectionRange(5,9,"backward")')
        await page.evaluate('__choiceRelease()')
        await page.wait_for_function("referencePending===0 && referenceRecords[1]?.parent_asset==='asset-1'")
        check(f'delayed copy retains the active {field} field', await control.evaluate('(n)=>n===document.activeElement'))
        if field != 'role':
            check(f'delayed copy retains {field} selection and wording', await control.evaluate('(n)=>n.value==="Keep this later reference wording" && n.selectionStart===5 && n.selectionEnd===9 && n.selectionDirection==="backward"'))

    # A stale confirmation may not replace wording edited while its copy runs.
    await offer()
    await page.evaluate('__choiceDelay=true;delete window.__choiceRelease')
    page.once('dialog', lambda dialog: dialog.accept())
    await page.locator('#uxSecondReplace').click()
    await page.wait_for_function("typeof window.__choiceRelease==='function'")
    await page.fill('#positive', 'Newer wording after replacement confirmation')
    before = await page.evaluate('__choiceSnapshot()')
    await page.evaluate('__choiceRelease()')
    await page.wait_for_function("document.querySelector('#uxNotice').textContent.includes('workbench changed')")
    check('stale source replacement leaves newer wording and source intact', before == await page.evaluate('__choiceSnapshot()') and not await page.locator('#uxSecondPicture').is_hidden())
    check('stale source replacement retains prompt focus', await page.locator('#positive').evaluate('(n)=>n===document.activeElement'))

    # A local role upload started after replacement confirmation owns newer work,
    # even before its response changes the stamped reference record.
    before = await offer()
    await page.evaluate('__choiceDelay=true;__choiceUploadDelay=true;delete window.__choiceRelease;delete window.__choiceUploadRelease')
    page.once('dialog', lambda dialog: dialog.accept())
    await page.locator('#uxSecondReplace').click()
    await page.wait_for_function("typeof window.__choiceRelease==='function'")
    await page.set_input_files('[data-ref-file="1"]', {'name':'later-role.png','mimeType':'image/png','buffer':(ROOT/'examples/references/lantern-reference.png').read_bytes()})
    await page.wait_for_function("referencePending===1 && typeof window.__choiceUploadRelease==='function'")
    check('a newer role upload retains its actual selected File', await page.evaluate("__choiceUploadedFile===document.querySelector('[data-ref-file=\"1\"]').files[0]"))
    await page.evaluate('__choiceRelease()')
    await page.wait_for_function("document.querySelector('#uxNotice').textContent.includes('workbench changed')")
    check('pending role upload refuses replacement and keeps draft and decision', before == await page.evaluate('__choiceSnapshot()') and not await page.locator('#uxSecondPicture').is_hidden())
    check('refused replacement leaves the newer upload pending', await page.evaluate('referencePending===1'))
    await page.evaluate('__choiceUploadRelease()')
    await page.wait_for_function("referencePending===0 && referenceRecords[1]?.file==='later-role.png'")
    check('newer role upload still completes with the original continuation', await page.evaluate("continuationState?.source_asset_id==='asset-0' && referenceRecords[0].parent_asset==='asset-0' && !referenceRecords[1].parent_asset && document.querySelector('#positive').value==='Keep my source and edited wording'"))
    await page.evaluate('__choiceUploadDelay=false')

    # Reordering keeps field ownership on the same record, never its old index.
    await page.evaluate("__choiceReset('qwen-3ref')")
    await page.locator('[data-ref-avoid="1"]').fill('Follow this reference record')
    await page.evaluate("document.querySelector('[data-ref-down=\"1\"]').click()")
    check('reference field focus follows its record through reorder', await page.locator('[data-ref-avoid="2"]').evaluate('(n)=>n===document.activeElement && n.value==="Follow this reference record"'))

    for width in (1440, 390):
        await page.set_viewport_size({'width':width,'height':900})
        for count in (1, 2, 3):
            before = await offer(f'qwen-{count}ref')
            choices=page.locator('[data-ux-second-slot]')
            check(f'{width}px {count} references: only non-source slots offered', await choices.count()==count-1)
            if count > 1:
                reason=await page.locator('[data-readiness-code="second"]').text_content()
                check('multi-reference guidance does not claim this recipe reads one picture', 'reads one' not in reason and 'source' in reason)
            if count == 1:
                await page.locator('#uxSecondKeep').click()
                check('keep source dismisses the choice without modifying the draft', before == await page.evaluate('__choiceSnapshot()'))
                continue
            target=choices.last
            await target.focus()
            await page.keyboard.press('Enter')
            await page.wait_for_function("referencePending===0 && document.querySelector('#uxSecondPicture').hidden")
            state=await page.evaluate("({refs:attachedReferencePayload(),parents:parentAssets,claim:continuationState,wording:document.querySelector('#positive').value,calls:__choiceCalls})")
            check('alternative uses the existing slot and retains the protected source', state['refs'][0]['parent_asset']=='asset-0' and state['refs'][count-1]['parent_asset']=='asset-1' and state['claim']['source_asset_id']=='asset-0')
            check('alternative retains wording and stages exactly one copy', state['wording']=='Keep my source and edited wording' and state['calls']==['asset-1'] and set(state['parents'])=={'asset-0','asset-1'})
            check('choice action returns focus to the attached reference', await page.locator(f'[data-ref-contribution="{count-1}"]').evaluate('(n)=>n===document.activeElement'))

    await offer()
    page.once('dialog', lambda dialog: dialog.dismiss())
    before=await page.evaluate('__choiceSnapshot()')
    await page.locator('#uxSecondReplace').click()
    check('declined replacement retains source, wording and choice', before==await page.evaluate('__choiceSnapshot()') and not await page.locator('#uxSecondPicture').is_hidden())
    page.once('dialog', lambda dialog: dialog.accept())
    await page.locator('#uxSecondReplace').click()
    await page.wait_for_function("referencePending===0 && referenceRecords[0]?.parent_asset==='asset-1'")
    check('accepted replacement fills the real role slot, not only the hidden mirror', await page.evaluate("continuationState===null && referenceRecords[0].file===uploaded && parentAssets.length===1 && parentAssets[0]==='asset-1' && referenceRecords.slice(1).every(r=>!r.file)"))

    # Existing target metadata is explicit and replacement still needs confirmation.
    await page.evaluate("__choiceReset('qwen-3ref')")
    await page.evaluate("attachReferenceAsset(1,'asset-2')")
    await page.locator('#uxPullAsset').click()
    await page.locator('[data-ux-pull="asset-1"]').wait_for(state='visible')
    await page.select_option('#uxSourceSlot','0')
    await page.locator('[data-ux-pull="asset-1"]').click()
    before=await page.evaluate('__choiceSnapshot()')
    await page.evaluate('__choiceCalls=[]')
    check('occupied target is labeled as a replacement', 'Replace' in await page.locator('[data-ux-second-slot="1"]').inner_text())
    page.once('dialog', lambda dialog: dialog.dismiss())
    await page.locator('[data-ux-second-slot="1"]').click()
    check('declined occupied-slot replacement keeps both viewpoints', before==await page.evaluate('__choiceSnapshot()') and not await page.evaluate('__choiceCalls.length'))

    before=await offer()
    await page.evaluate('__choiceFailure=true')
    await page.locator('[data-ux-second-slot="1"]').click()
    await page.wait_for_function("document.querySelector('#uxNotice').textContent.includes('Synthetic copy unavailable')")
    check('failed copy preserves source, draft and explicit choice', before==await page.evaluate('__choiceSnapshot()') and not await page.locator('#uxSecondPicture').is_hidden())
    await page.evaluate('__choiceFailure=false;__choiceDelay=true;__choiceCalls=[]')
    await page.locator('[data-ux-second-slot="1"]').click()
    await page.wait_for_function("typeof window.__choiceRelease==='function'")
    # None of these actions may consume/reset the choice while its copy is in flight.
    await page.evaluate("""() => {
      document.querySelector('[data-ux-second-slot="2"]').click();
      document.querySelector('#uxSecondKeep').click();
      document.querySelector('#uxSecondReplace').click();
      document.querySelector('#uxSecondRestyle').click();
    }""")
    check('in-flight choice cannot dispatch twice or launch a different handoff', await page.evaluate("__choiceCalls.length===1 && !document.querySelector('#uxSecondPicture').hidden && !document.querySelector('#uxHandoff').open"))
    await page.fill('#positive','Newer typing while copying')
    await page.evaluate('__choiceRelease()')
    await page.wait_for_function("referencePending===0 && referenceRecords[1]?.parent_asset==='asset-1'")
    check('a valid deferred copy preserves unrelated newer typing', await page.locator('#positive').input_value()=='Newer typing while copying')
    check('deferred completion does not steal focus from active typing', await page.locator('#positive').evaluate('(n)=>n===document.activeElement'))

    await offer()
    await page.evaluate('__choiceDelay=true;delete window.__choiceRelease')
    await page.locator('[data-ux-second-slot="1"]').click()
    await page.wait_for_function("typeof window.__choiceRelease==='function'")
    await page.evaluate("selectPreset('anima-portrait',true,true)")
    before=await page.evaluate('__choiceSnapshot()')
    await page.evaluate('__choiceRelease()')
    await page.wait_for_function("document.querySelector('#uxNotice').textContent.includes('destination slot changed')")
    check('late copy cannot change a replacement recipe', before==await page.evaluate('__choiceSnapshot()'))
    await page.evaluate('__choiceDelay=false')


async def main(args):
    fixture.POSTS.clear()
    server=fixture.ThreadingHTTPServer(('127.0.0.1',0),fixture.Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    checks=[];errors=[]
    def check(name, passed):
        checks.append({'name':name,'passed':bool(passed)});print(name, bool(passed),flush=True)
        assert passed, name
    try:
        async with async_playwright() as pw:
            browser=await pw.chromium.launch(executable_path=shutil.which('chromium'))
            page=await browser.new_page(viewport={'width':1440,'height':900})
            page.set_default_timeout(5000);page.on('pageerror',lambda e:errors.append(str(e)))
            if args.inert:await inert_page(page,server.server_port)
            else:await page.goto(f'http://127.0.0.1:{server.server_port}/#create')
            await page.wait_for_function("!!selected && schemaAvailable && assetState.assets.length>0")
            await exercise_source_choices(page,check)
            check('no generation, installation or environment switching', all(row['path'] in {'/api/assets/reference','/api/estimate','/api/references/check'} for row in fixture.POSTS))
            check('no page exceptions',not errors)
            await browser.close()
    finally:
        server.shutdown();server.server_close();thread.join(5)
        args.out.mkdir(parents=True,exist_ok=True)
        (args.out/'report.json').write_text(json.dumps({'native_origin':not args.inert,'checks':checks,'errors':errors},indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--inert',action='store_true')
    parser.add_argument('--out',type=Path,default=ROOT/'.runtime/source-slot-choices')
    asyncio.run(main(parser.parse_args()))
