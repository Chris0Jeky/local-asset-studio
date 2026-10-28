"""Make privacy boundaries over native HTTP, storage and real frontend with synthetic jobs only.

python tests/make_privacy_browser.py --out .runtime/make-privacy
The fixture never contacts ComfyUI; acknowledged jobs are inert records and use repository example media.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import traceback

from playwright.sync_api import sync_playwright
from browser_ports import browser_server, evidence_screenshot
import make_goals_browser as fixture
from make_draft_browser import synthetic_privacy, PRIVATE_TEXT

ROOT=Path(__file__).resolve().parents[1]


def run(output):
    output.mkdir(parents=True,exist_ok=True)
    rows=[];errors=[];server_errors=[];disconnects=[];requests=[];held=threading.Event();release=threading.Event();hold={'path':None}
    class Handler(fixture.Handler):
        def do_GET(self):
            requests.append({'method':'GET','path':self.path,'scope':self.headers.get('X-Studio-Privacy')})
            if self.path==hold['path']:held.set();release.wait(10)
            return super().do_GET()
        def do_POST(self):
            item={'method':'POST','path':self.path,'privacy':self.headers.get('X-Studio-Creation-Privacy'),'scope':self.headers.get('X-Studio-Privacy')};requests.append(item)
            if self.path==hold['path']:held.set();release.wait(10)
            if self.path=='/api/jobs':
                data=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))));item['data']=data
                fixture.fixture.POSTS.append({'path':self.path,'data':data});job=dict(data,id='goal-'+str(len(fixture.JOBS)),privacy=item['privacy'] or 'regular',status='queued',created_at=1789228800,outputs=[])
                fixture.JOBS[job['id']]=job;return self.json(job)
            return super().do_POST()
    server=browser_server(Handler)
    def server_error(request,address):
        error=sys.exc_info()[1]
        if isinstance(error,(BrokenPipeError,ConnectionResetError)):disconnects.append(type(error).__name__)
        else:server_errors.append(traceback.format_exc())
    server.handle_error=server_error
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();origin='http://127.0.0.1:'+str(server.server_port)
    def check(name,ok,detail=None):rows.append({'name':name,'passed':bool(ok),'detail':detail})
    def stores(page):return page.evaluate('({local:{...localStorage},session:{...sessionStorage}})')
    def settled(page):page.wait_for_function('document.querySelector("#makeView").dataset.draftState==="ready"')
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None)
            context=browser.new_context(viewport={'width':1440,'height':900},reduced_motion='reduce');synthetic_privacy(context)
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(origin+'/#make');page.wait_for_selector('[data-make-look]');settled(page)
            page.locator('[data-make-look="look-wai-fantasy-portrait"]').click();page.locator('#makeScene').fill(PRIVATE_TEXT)
            page.locator('#makeTune > summary').click();page.locator('[data-tune="negative"]').fill('PRIVATE NEGATIVE SENTINEL')
            page.evaluate("qaPrivacy('private')");settled(page)
            check('converting text draft keeps scene and negative',page.input_value('#makeScene')==PRIVATE_TEXT and page.input_value('[data-tune="negative"]')=='PRIVATE NEGATIVE SENTINEL')
            st=stores(page);check('converted scene and tune leave no persistent private text',PRIVATE_TEXT not in json.dumps(st['local']) and 'PRIVATE NEGATIVE SENTINEL' not in json.dumps(st['local']),{'local_keys':list(st['local'])})
            check('converted tune uses private session namespace','PRIVATE NEGATIVE SENTINEL' in st['session'].get('studio.make.tune.private',''))
            # Freeze privacy before prepare. A later switch cannot move this already intentional request to regular.
            hold['path']='/api/looks/prepare';held.clear();release.clear();before=len([r for r in requests if r['path']=='/api/jobs' and r['method']=='POST'])
            page.locator('#makeGenerate').click();page.wait_for_function('document.querySelector("#makeStatus").textContent.includes("Preparing")')
            assert held.wait(3),'prepare was not reached'
            page.evaluate("qaPrivacy('regular')");settled(page);release.set();hold['path']=None
            page.wait_for_function('!document.querySelector("#makeGenerate")?.disabled')
            page.wait_for_function('Object.values(sessionStorage).some(x=>x.includes("goal-"))')
            jobs=[r for r in requests if r['path']=='/api/jobs' and r['method']=='POST'][before:]
            check('one delayed private request stays private',len(jobs)==1 and jobs[0]['privacy']=='private' and PRIVATE_TEXT in json.dumps(jobs[0]['data']),jobs)
            check('regular results do not show the private run',PRIVATE_TEXT not in page.locator('#makeRuns').inner_text())
            st=stores(page);check('private run and redo never enter localStorage',PRIVATE_TEXT not in json.dumps(st['local']) and 'PRIVATE NEGATIVE SENTINEL' not in json.dumps(st['local']))
            check('acknowledged private job is retained in session storage','goal-' in st['session'].get('studio.make.private',''))
            page.evaluate("qaPrivacy('private')");settled(page);page.wait_for_selector('#makeRuns [data-run]')
            check('explicit private view restores the retained run',PRIVATE_TEXT in page.locator('#makeRuns').inner_text())
            page.evaluate("qaPrivacy('private','regular')");settled(page)
            check('scope-only regular filter hides private cards',PRIVATE_TEXT not in page.locator('#makeRuns').inner_text() and page.input_value('#makeScene')==PRIVATE_TEXT)
            page.evaluate("qaPrivacy('private','all')");settled(page);page.wait_for_selector('#makeRuns [data-run]')
            check('all filter can show the private card deliberately',PRIVATE_TEXT in page.locator('#makeRuns').inner_text())
            page.evaluate("qaPrivacy('regular','all')");settled(page);page.wait_for_selector('#makeRuns [data-make-rerun]')
            page.locator('#makeRuns [data-make-rerun]').first.click()
            check('private rerun cannot copy words into regular draft',PRIVATE_TEXT not in page.input_value('#makeScene') and 'Choose Private' in page.locator('#makeStatus').inner_text())
            check('refused private rerun keeps persistent storage regular',PRIVATE_TEXT not in json.dumps(stores(page)['local']))
            evidence_screenshot(page,path=str(output/'all-scope.png'))
            context.close()
            # A private edit may intentionally use a regular source. Only the output/staged copies are private.
            context=browser.new_context(viewport={'width':390,'height':844},reduced_motion='reduce');synthetic_privacy(context)
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(origin+'/#make');page.wait_for_selector('[data-make-look]');settled(page)
            page.locator('[data-make-goal="combine"]').click();page.locator('[data-make-pick="asset-1"]').click();page.locator('[data-make-pose-pick="asset-0"]').click()
            for key,text in [('who',PRIVATE_TEXT),('clothes','PRIVATE CLOTHES SENTINEL'),('pose','Looking over her left shoulder')]:page.locator('#makeF-'+key).fill(text)
            page.evaluate("qaPrivacy('private')");settled(page)
            start=len(requests);hold['path']='/api/assets/asset-1/context';held.clear();release.clear()
            page.locator('#makeGenerate').click();assert held.wait(3),'source context was not reached'
            page.evaluate("qaPrivacy('regular')");settled(page);release.set();hold['path']=None
            page.wait_for_function('Object.values(sessionStorage).some(x=>x.includes("PRIVATE CLOTHES SENTINEL")&&x.includes("goal-"))')
            sent=[r for r in requests[start:] if r['path']=='/api/jobs' and r['method']=='POST'];staged=[r for r in requests[start:] if r['path']=='/api/assets/reference']
            check('private pose request reads both regular sources explicitly',len(staged)==2 and all(r['scope']=='regular' and r['privacy']=='private' for r in staged),staged)
            check('private pose request survives privacy switch without a second submit',len(sent)==1 and sent[0]['privacy']=='private' and 'PRIVATE CLOTHES SENTINEL' in json.dumps(sent[0]['data']),sent)
            st=stores(page);check('private pose fills and redo stay out of localStorage','PRIVATE CLOTHES SENTINEL' not in json.dumps(st['local']) and PRIVATE_TEXT not in json.dumps(st['local']))
            check('private remembered fills use captured privacy after the switch','PRIVATE CLOTHES SENTINEL' in st['session'].get('studio-fills:asset-1.private',''))
            check('regular composer keeps private pose answers hidden',PRIVATE_TEXT not in page.locator('#makeView').evaluate('(e)=>[...e.querySelectorAll("input,textarea")].map(x=>x.value).join(" ")'))
            context.close();browser.close()
    except Exception as error:check('driver completed',False,type(error).__name__+': '+str(error))
    finally:release.set();server.shutdown();server.server_close();thread.join(timeout=5)
    check('zero page errors',not errors,errors);check('zero HTTP request-thread errors',not server_errors,server_errors)
    receipt={'mode':'native-http-synthetic-api','rows':rows,'requests':requests,'client_disconnects':disconnects,'inert_jobs':len(fixture.JOBS),'source_sha256':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in ['app/static/make.js','tests/make_privacy_browser.py']},
             'limits':'Only synthetic acknowledged jobs. No model, ComfyUI, user media, generation quality or owner art acceptance. Privacy browser owner is the explicitly synthetic contract from make_draft_browser.'}
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    for row in rows:print(('PASS ' if row['passed'] else 'FAIL ')+row['name'])
    print(str(sum(r['passed'] for r in rows))+'/'+str(len(rows)))
    return 0 if all(r['passed'] for r in rows) else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=ROOT/'.runtime/make-privacy');args=parser.parse_args();raise SystemExit(run(args.out))
