"""Create readiness actions over the shipped shell; synthetic HTTP, no model execution.

Default: native browser HTTP. --inert substitutes storage and API transport explicitly.
--baseline records unmet expectations but never suppresses runtime/JavaScript errors.
"""
import argparse
import asyncio
import hashlib
import json
import shutil
import threading
from pathlib import Path
from urllib.parse import urlsplit

import studio_browser_smoke as fixture
from asset_detail_browser import inert_page

ROOT=Path(__file__).resolve().parents[1]

class State:
    def __init__(self):
        self.health={'online':True,'schema_available':True,'worker_alive':True,'missing_models':{},'devices':[]}
        self.inspect_fail=False
        self.gets=[]

class Handler(fixture.Handler):
    state=None
    def do_GET(self):
        path=urlsplit(self.path).path
        self.state.gets.append(path)
        if path=='/api/health':return self.json(self.state.health)
        if path.startswith('/api/inspect/'):
            if self.state.inspect_fail:return self.json({'error':'Injected required-file observation failure'},503)
            name=path.split('/')[-1]
            return self.json({'requirements':[{'file':name+'.safetensors','present':False,'installable':False,'install_note':'Synthetic pin-only file; no installation in this fixture.'}],'nodes':[{'type':'FixtureNode'}],'graph':{'fixture':name}})
        return super().do_GET()

async def run(args):
    from playwright.async_api import async_playwright
    args.out.mkdir(parents=True,exist_ok=True)
    state=State();Handler.state=state;fixture.POSTS.clear()
    server=fixture.ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    checks=[];errors=[];failure=None
    def check(id,expected,value):
        checks.append({'id':id,'expectation':expected,'passed':bool(value)});print(id,bool(value),expected,flush=True)
    try:
        async with async_playwright() as pw:
            browser=await pw.chromium.launch(executable_path=args.chromium or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
            page=await browser.new_page(viewport={'width':1440,'height':1100},reduced_motion='reduce');page.set_default_timeout(5000)
            page.on('pageerror',lambda e:errors.append(str(e)))
            if args.inert:await inert_page(page,server.server_port)
            else:await page.goto(f'http://127.0.0.1:{server.server_port}/#create')
            await page.wait_for_function('!!selected && !!readPoller')
            # Freeze periodic fixture reads, not product handlers or responses.
            await page.evaluate("readPoller.started=false;for(const lane of readPoller.lanes.values()){clearTimeout(lane.timer);lane.timer=null;}showView('create');selectPreset('qwen-3ref')")
            await page.wait_for_function("document.querySelector('#dependencyCount').textContent.includes('/ 1 present')")
            await page.fill('#positive','Keep my precise wording, style and composition.')
            async def stamp():return await page.evaluate("JSON.stringify({preset:selected.id,controls:values(),parents:parentAssets,references:attachedReferencePayload(),continuation:continuationState,batch:document.querySelector('#batch').value})")
            async def click_existing(selector,keyboard=False):
                item=page.locator(selector).first
                if not await item.count():return False
                if keyboard:await item.focus();await page.keyboard.press('Enter')
                else:await item.click()
                return True
            before=await stamp()
            check('READY-01','Required-reference blocker has a direct action',await page.locator('[data-ux-resolve="references"]').count()==1)
            await click_existing('[data-ux-resolve="references"]',True)
            check('READY-02','Keyboard action focuses Picture 1 input without opening/uploading a file',await page.evaluate("document.activeElement.dataset.refFile==='0'"))
            check('READY-03','Input navigation preserves wording, settings and attachments',await stamp()==before)
            # A filled first slot redirects the same action to the next missing slot.
            await page.evaluate("Object.assign(referenceRecords[0],{file:'fixture-first.png',missing:false});renderReferenceSlots()")
            await click_existing('[data-ux-resolve="references"]')
            check('READY-04','Action resolves the next missing slot from current state',await page.evaluate("document.activeElement.dataset.refFile==='1'"))
            await page.evaluate("document.querySelector('#referenceCards').querySelector('[data-ref-file=\"1\"]').hidden=true")
            await click_existing('[data-ux-resolve="references"]')
            check('READY-05','Unavailable target has visible feedback rather than guessed fallback',await page.locator('#uxReadinessActionStatus').count()>0 and 'not available' in await page.locator('#uxReadinessActionStatus').inner_text())
            await page.evaluate("document.querySelector('#referenceCards').querySelector('[data-ref-file=\"1\"]').hidden=false")
            state.health['missing_models']={'qwen-3ref':['checkpoints/missing.safetensors']}
            await page.evaluate('health()')
            await page.evaluate("document.querySelector('.dependencies').open=false")
            before=await stamp();await click_existing('[data-readiness-code="models"] [data-ux-resolve="dependencies"]',True)
            check('READY-06','Missing-file action opens and focuses the existing dependency disclosure',await page.evaluate("document.querySelector('.dependencies').open && document.activeElement===document.querySelector('.dependencies>summary')"))
            check('READY-07','Dependency navigation preserves the Create draft',await stamp()==before)
            state.inspect_fail=True;await page.evaluate('inspectSelected()')
            check('READY-08','Failed inspection has no obsolete presence count',await page.locator('#dependencyCount').inner_text()=='Unavailable')
            check('READY-09','Failed inspection exposes a read-only retry',await page.locator('[data-inspect-retry]').count()==1)
            await page.evaluate("document.querySelector('.dependencies').open=true")
            state.inspect_fail=False;n=len([x for x in state.gets if x.startswith('/api/inspect/')])
            retried=await click_existing('[data-inspect-retry]')
            if retried:await page.wait_for_function("document.querySelector('#dependencyCount').textContent==='0 / 1 present'")
            check('READY-10','Explicit dependency retry performs exactly one inspect GET',len([x for x in state.gets if x.startswith('/api/inspect/')])==n+1)
            check('READY-11','Inspection does not override the missing-model Generate hold',await page.locator('#generate').is_disabled())
            # Same readiness rendering must retain a focused button (periodic health used to rebuild text).
            action=page.locator('[data-ux-resolve="references"]')
            if await action.count():
                await action.focus();await page.evaluate('updateReady();updateReady()')
            check('READY-12','Identical readiness refresh preserves keyboard focus on the action',await page.evaluate("document.activeElement.dataset.uxResolve==='references'"))
            state.health['online']=False;state.health['schema_available']=False
            await page.evaluate('health()');before=await stamp()
            await click_existing('[data-readiness-code="offline"] [data-ux-resolve="models"]',True)
            check('READY-13','Offline action opens Models and focuses its environment control',await page.evaluate("view==='models' && document.activeElement.id==='backendChoice'"))
            check('READY-14','Models navigation does not change selected backend or Create draft',await page.evaluate("backendActive==='primary'") and await stamp()==before)
            await page.evaluate("showView('create')");state.health.update(online=True,schema_available=True,missing_models={})
            n=state.gets.count('/api/health');clicked=await click_existing('#uxRecheckReadiness',True)
            if clicked:await page.wait_for_function("!document.querySelector('#uxRecheckReadiness').disabled && online===true")
            check('READY-15','Recheck connection is an explicit health GET',state.gets.count('/api/health')==n+1)
            check('READY-16','Connection recovery leaves the required-reference hold in place',await page.locator('#generate').is_disabled() and (not clicked or await page.locator('[data-readiness-code="references"]').count()==1))
            summary=page.locator('#uxReadinessSummary')
            check('READY-17','A polite atomic summary describes changing blockers',await summary.count()>0 and await summary.get_attribute('role')=='status' and await summary.get_attribute('aria-live')=='polite' and await summary.get_attribute('aria-atomic')=='true')
            # Deadline fault: invoke the real handler with a held observation and accelerated timer.
            # This tests UI recovery from a hung shared read, not transport cancellation.
            deadline=await page.evaluate("""async()=>{
                const button=document.querySelector('#uxRecheckReadiness');if(!button)return null;
                const read=health,timer=window.setTimeout;let calls=0,rescue=null;
                health=()=>{calls++;return new Promise(resolve=>{rescue=timer(resolve,100);});};
                window.setTimeout=(fn,delay,...args)=>timer(fn,delay===15000?10:delay,...args);
                try{await Promise.all([button.onclick(),button.onclick()]);return {calls,enabled:!button.disabled,text:document.querySelector('#uxReadinessActionStatus').textContent};}
                finally{clearTimeout(rescue);health=read;window.setTimeout=timer;}
            }""") if await page.locator('#uxRecheckReadiness').count() else None
            check('READY-26','Hung connection check releases its UI with an honest timeout',deadline and deadline['enabled'] and 'timed out' in deadline['text'])
            check('READY-27','Repeated activation while checking coalesces and never retries automatically',deadline and deadline['calls']==1)
            # Text-only recipe has no source blocker; ready is explicitly bounded, not artistic approval.
            await page.evaluate("selectPreset('anima-portrait');online=true;schemaAvailable=true;updateReady()")
            check('READY-18','Unblocked summary keeps server validation explicit',await summary.count()>0 and 'server' in await summary.inner_text() and not await page.locator('#generate').is_disabled())
            await page.evaluate("selectPreset('wan22-i2v');applyI2VMode('canonical')")
            mode_block=await page.evaluate('i2vModeBlocker()')
            # Deliberately select the documented runtime hold without executing or rewriting its graph.
            if not mode_block:await page.evaluate("getControl('width').value=9999;updateReady()")
            before=await stamp();await click_existing('[data-ux-resolve="parameters"]',True)
            check('READY-19','Motion hold opens Parameters and focuses the mode selector',await page.evaluate("document.querySelector('.ux-parameters').open && document.activeElement.id==='i2vMode'"))
            check('READY-20','Motion guidance never auto-applies smaller settings',await stamp()==before)
            # Existing first/last inputs must be counted separately from role boards.
            await page.evaluate("selectPreset('h3-first-last');uploaded='first.png';lastUploaded='last.png';updateReady()")
            check('READY-21','Source note counts both first and last staged inputs', (await page.inner_text('#uxSourceNote')).startswith('2 attached'))
            await page.evaluate("selectPreset('qwen-3ref');online=false;schemaAvailable=false;missingByPreset={'qwen-3ref':['checkpoints/missing.safetensors']};updateReady()")
            for width,id in [(1440,'READY-22'),(390,'READY-23')]:
                await page.set_viewport_size({'width':width,'height':1100});await page.locator('#uxBlockers').scroll_into_view_if_needed()
                check(id,str(width)+'px readiness controls fit the viewport',await page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                await page.screenshot(path=str(args.out/f'create-readiness-{width}.png'))
            # A partial shared-draft adoption must remain a Generate hold after
            # readiness is rendered as structured actions instead of plain text.
            adoption_error=await page.evaluate("""()=>{
                selectPreset('pixel-lora');online=true;schemaAvailable=true;workerAlive=true;missingByPreset={};updateReady();
                const draft=StudioSetupDraft.capture(),stamp=StudioSetupDraft.stamp(),original=recipeChanged;
                let error='';recipeChanged=()=>{throw Error('Injected draft adoption failure');};
                try{StudioSetupDraft.adopt(draft,stamp,backendActive);}catch(e){error=e.message;}
                finally{recipeChanged=original;updateReady();}
                return error;
            }""")
            check('READY-28','Shared-draft adoption failure is exercised without a server command',adoption_error=='Injected draft adoption failure')
            check('READY-29','Incomplete shared adoption alone keeps Generate disabled with a visible reason',await page.evaluate("document.querySelector('#generate').disabled && document.querySelectorAll('[data-readiness-code]').length===1 && document.querySelector('[data-readiness-code=\"shared-setup\"]').textContent.includes('Shared setup loading was incomplete')"))
            check('READY-24','All helper actions cause zero generation/install/switch/reference-upload calls',all(x['path'] in ['/api/estimate','/api/references/check'] for x in fixture.POSTS))
            check('READY-25','No JavaScript exceptions in the complete shell',not errors)
            await browser.close()
    except BaseException as error:failure=repr(error);raise
    finally:
        server.shutdown();server.server_close();thread.join(2)
        receipt={'mode':'inert storage/transport' if args.inert else 'native HTTP/browser', 'scope':'Real Studio HTML/JS/CSS, synthetic read-only readiness APIs; no ComfyUI, installation or inference.', 'checks':checks,'errors':errors,'failure':failure,'pass':sum(x['passed'] for x in checks),'fail':sum(not x['passed'] for x in checks),'gets':state.gets,'posts':fixture.POSTS,'source_sha256':{x:hashlib.sha256((ROOT/'app/static'/x).read_bytes()).hexdigest() for x in ['app.js','studio-core.js','studio-workbench.js','studio.css']}}
        (args.out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    assert len(checks)==29 and not errors, 'Incomplete or erroneous browser run'
    if not args.baseline and any(not c['passed'] for c in checks):raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--inert',action='store_true');p.add_argument('--baseline',action='store_true');p.add_argument('--chromium');asyncio.run(run(p.parse_args()))
