"""Actual Studio pages + guide, synthetic HTTP data, never ComfyUI.

Native browser HTTP/storage only. Requires an environment that permits local
HTTP navigation. Hosted CI runs this gate; no simulated-browser fallback.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
from urllib.parse import urlsplit, urlencode

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import studio_browser_smoke as fixture
from studio_workflow.guides import guides
from studio_workflow.core import catalog, new_document, compile_document
from http.server import ThreadingHTTPServer

INFO={'Sink':{'input':{'required':{'text':['STRING',{}],'seed':['INT',{'min':0,'max':2**64-1}]}},'output':[],'output_node':True}}
SCHEMA=catalog(INFO,'primary')
DOC=new_document({'1':{'class_type':'Sink','inputs':{'text':'Synthetic guide fixture','seed':42}}},SCHEMA)
FAIL_HEALTH=False
HEALTH_DELAY=0
CALLS=[]
HEALTH_GATE_ARMED=False
HEALTH_GATE_START=threading.Event()
HEALTH_GATE_RELEASE=threading.Event()

class Handler(fixture.Handler):
    def do_GET(self):
        global FAIL_HEALTH, HEALTH_DELAY, HEALTH_GATE_ARMED
        path=urlsplit(self.path).path; CALLS.append(('GET',path))
        if path=='/api/workflow-studio/guides':return self.json(guides())
        if path=='/api/workflow-studio/nodes':return self.json(SCHEMA)
        if path=='/api/workflow-studio/documents':return self.json({'documents':[]})
        if path=='/api/health':
            if HEALTH_GATE_ARMED:
                HEALTH_GATE_ARMED=False
                HEALTH_GATE_START.set()
                HEALTH_GATE_RELEASE.wait(timeout=15)
            if HEALTH_DELAY:time.sleep(HEALTH_DELAY)
            if FAIL_HEALTH:return self.json({'error':'Synthetic unavailable health'},503)
            return self.json({'online':True,'worker_alive':True,'schema_available':True,'missing_models':{},'devices':[],'comfy_url':'http://127.0.0.1:8188'})
        if path=='/api/backends':return self.json({'active':'primary','busy':False,'operation':None,'profiles':[{'id':'primary','name':'Fixture runtime','url':'http://127.0.0.1:8188','active':True,'online':True,'installed':True}]})
        if path.startswith('/api/jobs/'):
            return self.json(next((j for j in fixture.JOBS if j['id']==path.rsplit('/',1)[-1]),{'error':'Missing synthetic job'}))
        return super().do_GET()
    def do_POST(self):
        CALLS.append(('POST',urlsplit(self.path).path))
        if self.path in ('/api/workflow-studio/nodes/refresh','/api/workflow-studio/compile'):
            raw=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
            return self.json(SCHEMA if self.path.endswith('/refresh') else compile_document(raw['document'],SCHEMA))
        return super().do_POST()


def run(out):
    global FAIL_HEALTH, HEALTH_DELAY, HEALTH_GATE_ARMED
    from playwright.sync_api import sync_playwright
    out.mkdir(parents=True,exist_ok=True); checks=[]; errors=[]; history_checks=[]
    fixture.ASSETS[0]['job_id']='fixture-job'; fixture.ASSETS[0]['review']='unreviewed'
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    origin='http://127.0.0.1:'+str(server.server_port)
    def check(condition,label):
        assert condition,label; checks.append(label); print('PASS '+label,flush=True)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None,headless=True,args=['--no-sandbox'])
            context=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce')
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            def visit(guide,stage):
                item=next(x for x in guides()['guides'] if x['id']==guide);step=next(x for x in item['steps'] if x['id']==stage)
                url=urlsplit(step['route']);address=origin+url.path+'?'+urlencode({'guide':guide,'stage':stage})+'#'+url.fragment
                page.goto(address,timeout=15000);page.wait_for_selector('.studio-guide-panel');
                if url.path=='/':page.wait_for_function('typeof selected !== "undefined" && !!selected && typeof backendActive !== "undefined" && !!backendActive')
                return step
            for guide in guides()['guides']:
                for step in guide['steps']:
                    visit(guide['id'],step['id'])
                    if guide['id']=='reference-edit' and step['id']=='sources':page.evaluate("selectPreset('gentle-variation')")
                    if step['target']:
                        page.click('#showGuideControl')
                        # Empty production detail / native export require explicit source selection;
                        # either a real visible target or an honest unavailable note must be present.
                        check(page.locator('.studio-guide-target').count()==1 or 'not visible' in page.locator('#guideTargetStatus').inner_text(),guide['id']+'/'+step['id']+' resolves or explains its actual feature target')
                    else:check('no single control' in page.locator('#guideTargetStatus').inner_text(),guide['id']+'/'+step['id']+' is explicitly manual')
            visit('reference-edit','sources');page.evaluate("selectPreset('pixel-lora')")
            page.click('#showGuideControl');check('not visible' in page.locator('#guideTargetStatus').inner_text(),'hidden reference inputs are not activated')
            page.evaluate("selectPreset('gentle-variation')")
            check('Target control is available' in page.locator('#guideTargetStatus').inner_text(),'recipe rendering rediscovers a newly visible target without clicking Show')
            page.click('#showGuideControl')
            check(page.locator('#referenceWrap').evaluate('n=>n.classList.contains("studio-guide-target")'),'a later single-reference control is rediscovered')
            page.evaluate("selectPreset('pixel-lora')")
            check('not visible' in page.locator('#guideTargetStatus').inner_text() and page.locator('.studio-guide-target').count()==0,'recipe rendering clears a now-hidden target and its highlight')
            page.evaluate("selectPreset('gentle-variation')")
            page.evaluate("uploaded='staged-fixture.png'");page.click('#checkGuideStep')
            page.wait_for_function('document.querySelector("#guideEvidence").dataset.state === "met"')
            check('attached' in page.locator('#guideEvidence').inner_text(),'actual string reference identity is recognized without upload')
            page.evaluate("uploaded=null")
            page.set_input_files('#reference',{'name':'fixture.png','mimeType':'image/png','buffer':b'synthetic-not-uploaded'})
            page.click('#checkGuideStep');check('not yet staged' in page.locator('#guideEvidence').inner_text(),'file selection is not claimed as staging')
            page.get_by_role('button',name='Next step',exact=True).click();page.wait_for_url('**stage=wording*')
            check(page.locator('#reference').evaluate('n=>n.files[0]?.name')=='fixture.png','next reference stage preserves selected local files')
            visit('first-image','readiness');page.evaluate("selectPreset('pixel-lora')")
            page.click('#checkGuideStep');page.wait_for_function('document.querySelector("#guideEvidence").dataset.state === "met"')
            check('memory fit' in page.locator('#guideEvidence').inner_text(),'ready evidence excludes memory and creative guarantees')
            page.evaluate("selectPreset('gentle-variation')")
            check(page.locator('#guideEvidence').get_attribute('data-state')=='unknown','programmatic recipe selection invalidates prior readiness')
            page.evaluate("selectPreset('pixel-lora')");page.click('#checkGuideStep')
            page.wait_for_function('document.querySelector("#guideEvidence").dataset.state === "met"')
            page.evaluate("applyRecipe({preset_id:'pixel-lora',name:'Guide setup',controls:{positive:'Setup changed wording'}})")
            check(page.locator('#guideEvidence').get_attribute('data-state')=='unknown','same-preset setup changes invalidate evidence without a DOM input event')
            page.click('#checkGuideStep');page.wait_for_function('document.querySelector("#guideEvidence").dataset.state === "met"')
            page.evaluate("applySaved({preset:'pixel-lora',controls:{positive:'Imported wording'}})")
            check(page.locator('#guideEvidence').get_attribute('data-state')=='unknown','saved/imported setup invalidates prior evidence')
            page.evaluate("selected.runtime_block='Synthetic incompatible runtime';updateReady()");page.click('#checkGuideStep');page.wait_for_function('!document.querySelector("#checkGuideStep").disabled')
            check(page.locator('#guideEvidence').get_attribute('data-state')=='blocked' and 'Synthetic incompatible runtime' in page.locator('#guideEvidence').inner_text() and page.locator('#generate').is_disabled(),'configured runtime block is honored by both guide and Generate')
            page.evaluate('selected.runtime_block=null;updateReady()')
            FAIL_HEALTH=True;page.click('#checkGuideStep');page.wait_for_function('!document.querySelector("#checkGuideStep").disabled')
            check(page.locator('#guideEvidence').get_attribute('data-state')=='unknown','failed readiness is unknown rather than success')
            FAIL_HEALTH=False;HEALTH_DELAY=0
            HEALTH_GATE_START.clear();HEALTH_GATE_RELEASE.clear();HEALTH_GATE_ARMED=True
            try:
                page.click('#checkGuideStep')
                check(HEALTH_GATE_START.wait(timeout=15),'readiness request entered the handler before the draft changed')
                page.fill('#positive','Changed while checking')
            finally:
                HEALTH_GATE_ARMED=False;HEALTH_GATE_RELEASE.set()
            page.wait_for_function('!document.querySelector("#checkGuideStep").disabled')
            check('discarded' in page.locator('#guideEvidence').inner_text(),'late readiness cannot certify a changed draft')
            visit('first-image','output');page.wait_for_selector('.studio-guide-target')
            check(page.evaluate('document.activeElement !== document.querySelector("#generate")') and page.locator('#generate').evaluate('n=>n.classList.contains("studio-guide-target")'),'arriving at the Generate step highlights the button without focusing it')
            page.click('#checkGuideStep');page.wait_for_selector('#guideObservedRun option[value="fixture-job"]',state='attached')
            check(page.locator('#guideObservedRun').input_value()=='' and page.locator('#guideEvidence').get_attribute('data-state')=='unknown','latest run is never selected by inference')
            page.select_option('#guideObservedRun','fixture-job');page.click('#checkGuideStep');page.wait_for_function('document.querySelector("#guideEvidence").dataset.state === "met"')
            check('output records' in page.locator('#guideEvidence').inner_text(),'specific recorded outputs are distinguished from acceptance')
            visit('first-image','review');page.click('#checkGuideStep');page.wait_for_function('!document.querySelector("#checkGuideStep").disabled')
            check(page.locator('#guideEvidence').get_attribute('data-state')=='blocked','unreviewed output requires human decision')
            fixture.ASSETS[0]['review']='rejected';page.click('#checkGuideStep');page.wait_for_function('document.querySelector("#guideEvidence").dataset.state === "met"')
            check('rejected' in page.locator('#guideEvidence').inner_text() and 'never approves' in page.locator('#guideEvidence').inner_text(),'rejection is a review decision not an art acceptance')
            # The coach reads its own step on arrival; the numbered list is the map.
            visit('first-image','recipe')
            page.wait_for_function('document.querySelector("#guideEvidence").dataset.state === "met"',timeout=15000)
            check('Not checked yet' not in page.locator('#guideEvidence').inner_text(),'arrival reads step evidence without a button press')
            check(page.locator('#checkGuideStep').inner_text()=='Re-check','the manual control is a re-check, not the only check')
            check(page.locator('.studio-guide-steps button').count()==6,'every step of the path is listed')
            check(page.locator('.studio-guide-steps [aria-current=step] .studio-guide-dot').get_attribute('data-state')=='met','the current step shows its last evaluated state')
            check(page.locator('.studio-guide-steps li').nth(3).locator('.studio-guide-dot').inner_text()=='4','other steps stay plain numbers')
            check(page.get_by_role('button',name='Open this step').count()==0,'the tool jump is hidden while already on that tool')
            page.locator('.studio-guide-steps li').nth(2).locator('button').click();page.wait_for_url('**stage=settings*')
            page.wait_for_selector('.studio-guide-panel');check('stage=settings' in page.url,'the step list navigates through the Next/Back guard')
            # A settled edit rechecks itself; no button press moves blocked to observed.
            visit('first-image','wording');page.fill('#positive','')
            page.wait_for_function('document.querySelector("#guideEvidence").dataset.state === "blocked"',timeout=15000)
            page.fill('#positive','Automatic recheck after typing')
            page.wait_for_function('document.querySelector("#guideEvidence").dataset.state === "met"',timeout=15000)
            check(True,'typing alone moves the wording step from blocked to observed')
            # One-click recipe choice runs the shipped picker, never a submission.
            visit('reference-edit','mechanism');page.evaluate("selectPreset('pixel-lora')")
            page.wait_for_selector('#chooseGuideRecipe')
            check('Qwen Atelier' in page.locator('#chooseGuideRecipe').inner_text(),'the recommended reference recipe is named on the button')
            # A drafted prompt is asked about first; declining keeps the draft and the current recipe.
            page.fill('#positive','Draft to keep');page.once('dialog',lambda d:d.dismiss());page.click('#chooseGuideRecipe')
            check(page.evaluate('selected.id')=='pixel-lora' and page.locator('#positive').input_value()=='Draft to keep','declining the recipe switch keeps the draft and recipe')
            page.once('dialog',lambda d:d.accept());page.click('#chooseGuideRecipe');page.wait_for_function('selected.id === "qwen-1ref"')
            page.wait_for_function('document.querySelector("#guideEvidence").dataset.state === "met"',timeout=15000)
            check(page.evaluate('selected.id')=='qwen-1ref','the coach selects the recommended recipe through the existing Create picker')
            visit('workflow','check');page.click('#loadNodes');page.wait_for_function('!!WorkflowStudio.schema()')
            page.evaluate('(doc)=>WorkflowStudio.load(doc)',DOC);page.click('#compileWorkflow');page.wait_for_function('WorkflowStudio.authoringStatus().checked_valid === true')
            page.click('#checkGuideStep');check(page.locator('#guideEvidence').get_attribute('data-state')=='met','guide reads the existing current connection-check receipt')
            page.evaluate("{const d=WorkflowStudio.snapshot();d.nodes['1'].inputs.text='Changed';WorkflowStudio.change(d);}")
            page.click('#checkGuideStep');check(page.locator('#guideEvidence').get_attribute('data-state')=='blocked','editing invalidates old connection evidence')
            page.get_by_role('button',name='Next step',exact=True).click();page.wait_for_url('**stage=save*')
            check(page.evaluate('WorkflowStudio.snapshot().nodes["1"].inputs.text')=='Changed' and page.evaluate('!!WorkflowStudio.schema()'),'same-page workflow steps preserve the draft and loaded schema')
            def history_probe():
                page.evaluate("""window.guideHistoryPhases=[];
                    for(const type of ['popstate','hashchange'])window.addEventListener(type,e=>
                        window.guideHistoryPhases.push({type,trusted:e.isTrusted,url:location.href}));""")
            def history_wait(label, required):
                # Query-changing stage traversal need not emit hashchange in Chromium.
                # Fragment-only traversal must exercise both native phases, never dispatchEvent.
                try:
                    page.wait_for_function("types=>types.every(type=>window.guideHistoryPhases.some(e=>e.type===type))",arg=required,timeout=10000)
                finally:
                    snapshot=page.evaluate("({url:location.href,events:window.guideHistoryPhases,state:document.querySelector('#guideEvidence')?.dataset.state})")
                    history_checks.append(dict(label=label,**snapshot))
                    (out/'history.json').write_text(json.dumps(history_checks,indent=2),encoding='utf-8')
                phases=[e['type'] for e in snapshot['events']]
                check(all(e['trusted'] for e in snapshot['events']),'native trusted history events: '+label)
                if 'hashchange' in required:
                    check(phases.index('popstate')<phases.index('hashchange'),'popstate precedes hashchange: '+label)
                check(snapshot['state']=='manual',label)
            visit('compare','budget');history_probe()
            page.get_by_role('button',name='Next step',exact=True).click();page.wait_for_url('**stage=inspect*')
            page.evaluate('window.guideHistoryPhases=[]');page.go_back();page.wait_for_url('**stage=budget*')
            history_wait('native Back restores the manual budget stage',['popstate'])
            page.fill('#positive','Changed after history')
            check(page.locator('#guideEvidence').get_attribute('data-state')=='unknown','real edits still invalidate the restored manual stage')
            page.evaluate('window.guideHistoryPhases=[]');page.go_forward();page.wait_for_url('**stage=inspect*')
            history_wait('native Forward restores the manual inspection stage',['popstate'])
            # Keep the query unchanged so Chromium emits the paired hashchange.
            # This uses the actual workbench navigation seam and native history, not fake events.
            page.evaluate("window.guideHistoryPhases=[];showView('create')")
            history_wait('native fragment navigation retains manual classification',['popstate','hashchange'])
            page.evaluate('window.guideHistoryPhases=[]');page.go_back();page.wait_for_url('**#production')
            history_wait('native fragment Back preserves manual classification through both phases',['popstate','hashchange'])
            page.evaluate('window.guideHistoryPhases=[]');page.go_forward();page.wait_for_url('**#create')
            history_wait('native fragment Forward preserves manual classification through both phases',['popstate','hashchange'])
            page.fill('#positive','Changed after fragment traversal')
            check(page.locator('#guideEvidence').get_attribute('data-state')=='unknown','real edits still invalidate after paired history phases')
            visit('first-image','wording');page.evaluate('window.guideNavigationSentinel="retained"');page.fill('#positive','Keep my exact guide draft')
            page.locator('#showGuideControl').focus();page.keyboard.press('Enter')
            check(page.locator('#positive').evaluate('n=>n===document.activeElement'),'keyboard control discovery focuses without clicking Generate')
            page.get_by_role('button',name='Next step',exact=True).click();page.wait_for_url('**stage=settings*')
            page.wait_for_selector('.studio-guide-panel');check('stage=settings' in page.url,'Next uses stable stage ID')
            check(page.evaluate('window.guideNavigationSentinel')=='retained' and page.locator('#positive').input_value()=='Keep my exact guide draft','Next does not reload or reset current Create inputs')
            page.get_by_role('button',name='Back',exact=True).click();page.wait_for_url('**stage=wording*');page.wait_for_selector('.studio-guide-panel')
            check(page.locator('#positive').input_value()=='Keep my exact guide draft','Back preserves current Create inputs')
            page.go_back();page.wait_for_url('**stage=settings*');page.wait_for_selector('.studio-guide-panel')
            check(page.locator('#positive').input_value()=='Keep my exact guide draft','browser history restores the coach without replacing the editor')
            page.get_by_role('button',name='Back',exact=True).click();page.wait_for_url('**stage=wording*');page.wait_for_selector('.studio-guide-panel')
            page.get_by_role('button',name='Pause guide',exact=True).click();check(page.locator('.studio-guide-panel').count()==0 and 'guide=' not in page.url,'Pause removes coaching without affecting the tool')
            page.goto(origin+'/workflow-studio.html#journeys');page.wait_for_selector('#goalCards a')
            resume=page.locator('#goalCards a',has_text='Resume').first;resume.click();page.wait_for_selector('.studio-guide-panel')
            check('stage=wording' in page.url,'resume restores stable navigation but not an observed success')
            page.set_viewport_size({'width':390,'height':844});page.click('#checkGuideStep')
            page.locator('.studio-guide-panel').screenshot(path=str(out/'guide-mobile.png'))
            check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'390px guide has no horizontal page overflow')
            page.set_viewport_size({'width':1440,'height':1000});page.evaluate('document.body.style.zoom="2"')
            check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'200% zoom retains page layout')
            page.evaluate('document.body.style.zoom="1"');page.locator('.studio-guide-panel').screenshot(path=str(out/'guide-desktop.png'))
            check(not errors,'no page exceptions: '+str(errors))
            forbidden=[x for x in CALLS if x[0]!='GET' and x[1] not in ('/api/estimate','/api/workflow-studio/nodes/refresh','/api/workflow-studio/compile')]
            check(not forbidden,'zero generation, installation, switching or asset-mutation calls: '+str(forbidden))
            browser.close()
        (out/'result.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'native_browser_transport':True,'fixture_data':True,'history':history_checks,'calls':CALLS},indent=2),encoding='utf-8')
    finally:server.shutdown();server.server_close();thread.join(5)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=ROOT/'.runtime/guide-proof')
    args=parser.parse_args();run(args.out)
