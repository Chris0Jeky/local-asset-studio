"""Actual Studio UI and shortlist policy; synthetic dependencies, never generation.

Default is native HTTP/storage. --inert is a disclosed component/full-shell mode
for containers that disallow localhost navigation; not evidence of native origin.
"""
import argparse
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
import studio_browser_smoke as fixture
from asset_detail_browser import inert_page
from test_recipe_shortlist import make_studio
from studio_workflow.shortlist import request as shortlist, PREFIX

CALLS=[];DELAY=0;FAIL=False;MALFORMED=False;ACTIVE=0;MAX_ACTIVE=0

class Handler(fixture.Handler):
    studio=None
    def do_POST(self):
        global ACTIVE,MAX_ACTIVE
        path=urlsplit(self.path).path;CALLS.append(path)
        if path==PREFIX:
            value=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            ACTIVE+=1;MAX_ACTIVE=max(MAX_ACTIVE,ACTIVE)
            try:
                report=shortlist(value,self.studio)
                if DELAY:time.sleep(DELAY)
                if FAIL:return self.json({'error':'Synthetic dependency service unavailable'},503)
                if MALFORMED:report['goal']='wrong-context'
                return self.json(report)
            except ValueError as exc:return self.json({'error':str(exc),'generation_submitted':False},400)
            finally:ACTIVE-=1
        return super().do_POST()


async def run(out,inert):
    global DELAY,FAIL,MALFORMED
    from playwright.async_api import async_playwright
    out.mkdir(parents=True,exist_ok=True);checks=[];errors=[]
    def check(condition,label):
        checks.append({'label':label,'passed':bool(condition)});print(('PASS ' if condition else 'FAIL ')+label,flush=True)
        assert condition,label
    with tempfile.TemporaryDirectory() as temp:
        studio=make_studio(temp);studio.presets=copy.deepcopy(fixture.CATALOG['presets'])
        # Real graph/capability identities with explicitly synthetic presence evidence.
        studio.graph_for=lambda p:(json.loads((ROOT/p['graph']).read_bytes()),ROOT/p['graph'])
        studio.requirements={p['id']:[] for p in studio.presets}
        studio._schema={n['class_type']:{} for p in studio.presets for n in studio.graph_for(p)[0].values()}
        for p in studio.presets:
            if p['id']=='anima-portrait':p['name']='<img src=x onerror=window.shortlistInjected=true>'
        fixture.CATALOG['presets']=copy.deepcopy(studio.presets)
        Handler.studio=studio
        http=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        origin='http://127.0.0.1:'+str(http.server_port)
        try:
            async with async_playwright() as p:
                browser=await p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None,headless=True,args=['--no-sandbox'])
                context=await browser.new_context(viewport={'width':1440,'height':1100},reduced_motion='reduce')
                page=await context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                if inert:
                    await inert_page(page,http.server_port)
                    await page.add_style_tag(content=(ROOT/'app/static/recipe-shortlist.css').read_text(encoding='utf-8'))
                    await page.add_script_tag(content=(ROOT/'app/static/recipe-shortlist.js').read_text(encoding='utf-8'))
                else:await page.goto(origin+'/?recipe_goal=new-image#create',timeout=15000)
                await page.wait_for_function("typeof catalog!=='undefined'&&!!selected&&!!document.querySelector('#recipeShortlist')")
                await page.evaluate("showView('create');document.querySelector('#recipeShortlist').open=true")
                check(PREFIX not in CALLS,'opening the Studio and shortlist makes no shortlist request')
                await page.evaluate("selectPreset('pixel-lora')")
                await page.fill('#positive','Keep this exact current prompt')
                await page.evaluate("uploaded='kept-source.png';lastUploaded='kept-last.png';parentAssets=['asset-0'];parentByInput={reference:'asset-0'}")
                snapshot="()=>({preset:selected.id,positive:document.querySelector('#positive').value,values:values(),uploaded,lastUploaded,parentAssets,parentByInput})"
                before=await page.evaluate(snapshot)
                await page.select_option('#uxIntent','animate')
                await page.click('#checkStartingRecipes')
                await page.wait_for_selector('#shortlistResults article')
                check(await page.locator('#shortlistResults article').count()<=6,'visible suggestion page is bounded')
                check('not permission to run' in await page.locator('#shortlistResults').inner_text(),'snapshot does not claim execution authority')
                check(await page.evaluate(snapshot)==before,'checking suggestions preserves the entire current editor/source state')
                check(await page.locator('#shortlistResults img').count()==0 and not await page.evaluate('!!window.shortlistInjected'),'untrusted preset labels remain inert text')
                first=await page.locator('#shortlistResults article').first.get_attribute('data-preset-id')
                await page.locator('#shortlistResults article').first.get_by_role('button',name='Find in recipe library').click()
                check(await page.evaluate('document.activeElement.dataset.id')==first,'Find focuses the real existing recipe button')
                check(await page.evaluate(snapshot)==before,'Find changes only library filters, never current recipe or source')
                await page.locator('#recipeShortlist > summary').focus();await page.keyboard.press('Enter')
                check(not await page.locator('#recipeShortlist').evaluate('x=>x.open'),'keyboard can collapse the shortlist')
                await page.keyboard.press('Enter')
                await page.get_by_role('button',name='Next suggestions',exact=True).click()
                await page.wait_for_function("!document.querySelector('#checkStartingRecipes').disabled&&!!document.querySelector('#shortlistResults article')")
                check(await page.locator('#shortlistResults article').first.get_attribute('data-preset-id')!=first,'explicit pagination advances without duplicating the first suggestion')
                # Every later page must bind the original observed snapshot.
                studio.requirements['anima-portrait']=[{'file':'changed.safetensors','present':False}]
                next_button=page.get_by_role('button',name='Next suggestions',exact=True)
                if await next_button.count():
                    await next_button.click();await page.wait_for_function("!document.querySelector('#checkStartingRecipes').disabled")
                    check('changed' in await page.locator('#shortlistStatus').inner_text() and await page.locator('#shortlistResults article').count()==0,'changed dependencies reject stale pagination instead of mixing snapshots')
                await page.select_option('#shortlistGoal','edit-image');await page.select_option('#shortlistReferences','1')
                previous=CALLS.count(PREFIX);await page.click('#checkStartingRecipes');await page.wait_for_selector('#shortlistResults article')
                check('declaration' in await page.locator('#shortlistResults').inner_text(),'reference counts never claim that source bytes were checked')
                check(CALLS.count(PREFIX)==previous+1,'goal and count changes do not auto-request')
                await page.locator('#recipeShortlist').screenshot(path=str(out/'desktop.png'))
                await page.set_viewport_size({'width':390,'height':844})
                await page.screenshot(path=str(out/'mobile-shell.png'))
                (out/'layout.json').write_text(json.dumps(await page.evaluate("""()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,nodes:[...document.querySelectorAll('body *')].filter(n=>n.getBoundingClientRect().width&&n.getBoundingClientRect().right>innerWidth+1).map(n=>({tag:n.tagName,id:n.id,cls:n.className,rect:n.getBoundingClientRect().toJSON()})).slice(0,30)})"""),indent=2),encoding='utf-8')
                check(await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'390px full Studio shell has no horizontal overflow')
                await page.locator('#recipeShortlist').screenshot(path=str(out/'mobile.png'))
                await page.set_viewport_size({'width':1440,'height':1100});await page.evaluate('document.body.style.zoom="2"')
                check(await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'200% zoom retains layout');await page.evaluate('document.body.style.zoom="1"')
                # Delayed read: real AbortSignal is covered by Node; native fetch additionally exercises it.
                DELAY=.7;before_calls=CALLS.count(PREFIX)
                await page.click('#checkStartingRecipes');await page.wait_for_function("document.querySelector('#checkStartingRecipes').disabled")
                await page.select_option('#shortlistGoal','new-image');await page.select_option('#shortlistGoal','edit-image')
                await asyncio.sleep(.9)
                check(await page.locator('#shortlistResults article').count()==0,'A to B to A field changes discard an earlier response')
                check(CALLS.count(PREFIX)==before_calls+1,'delayed reads are not retried automatically');DELAY=0
                FAIL=True;await page.click('#checkStartingRecipes');await page.wait_for_function("!document.querySelector('#checkStartingRecipes').disabled")
                check('unavailable' in await page.locator('#shortlistStatus').inner_text() and await page.locator('#shortlistResults article').count()==0,'service failure leaves explicit unknown evidence and no old actionable cards');FAIL=False
                MALFORMED=True;await page.click('#checkStartingRecipes');await page.wait_for_function("!document.querySelector('#checkStartingRecipes').disabled")
                check('context' in await page.locator('#shortlistStatus').inner_text(),'mismatched report context is rejected');MALFORMED=False
                await page.click('#checkStartingRecipes');await page.wait_for_selector('#shortlistResults article')
                await page.fill('#positive','A real edit invalidates the report')
                check(await page.locator('#shortlistResults article').count()==0,'actual editor input invalidates the old shortlist')
                if not inert:
                    count_before=CALLS.count(PREFIX)
                    entry=await context.new_page();entry.on('pageerror',lambda e:errors.append(str(e)))
                    await entry.set_viewport_size({'width':390,'height':844})
                    await entry.goto(origin+'/?recipe_goal=edit-image#create')
                    await entry.wait_for_selector('#checkStartingRecipes')
                    check(await entry.locator('#checkStartingRecipes').is_visible() and await entry.locator('#shortlistGoal').input_value()=='edit-image','mobile deep link opens the existing library drawer and desired goal')
                    await entry.goto(origin+'/workflow-studio.html')
                    await entry.wait_for_selector('#recipeShortlistLink a')
                    check(await entry.locator('#recipeShortlistLink a').get_attribute('href')=='/?recipe_goal=new-image#create','guided journeys provide a direct link to the existing recipe chooser')
                    check(CALLS.count(PREFIX)==count_before,'entry links do not automatically inspect or choose recipes')
                    await entry.close()
                check(not errors,'no page exceptions')
                forbidden=[x for x in CALLS if x not in (PREFIX,'/api/estimate')]
                check(not forbidden,'zero generation/install/switch/asset writes: '+str(forbidden))
                check(MAX_ACTIVE<=1,'bounded one in-flight read in these scenarios')
                await browser.close()
        finally:
            receipt={'checks':checks,'passed':sum(c['passed'] for c in checks),'errors':errors,'native_browser_transport':not inert,'synthetic_dependencies':True,'calls':CALLS,
                     'source_sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ('app/static/recipe-shortlist.js','app/static/recipe-shortlist.css','app/static/studio-shell.js','studio_workflow/shortlist.py')}}
            (out/'result.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
            http.shutdown();http.server_close();thread.join(5)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=ROOT/'.runtime/shortlist-browser');parser.add_argument('--inert',action='store_true');args=parser.parse_args()
    asyncio.run(run(args.out,args.inert))
