"""Opt-in Chromium proof: shipped UI/header boundary, inert APIs, no Comfy runtime."""
import argparse
import copy
import json
import os
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import studio_browser_smoke as fixture
import server as studio_server

IDENTIFIER='c'*32
PROJECT={'id':IDENTIFIER,'name':'Retained observation — synthetic fixture','kind':'comparison',
         'budget':{'allowance':2,'reserved':2},'axis':'seed','values':[],
         'state':{'status':'uncertain','message':'The retained prompt has finished; reconcile its failed outcome.'},
         'can_reconcile_tracking':True,
         'stages':[{'label':'A','operation':'generate','attempt':{'job_id':'retained-job'},
                    'job':{'id':'retained-job','preset_name':'Synthetic recovery fixture','status':'failed','outputs':[],
                           'prompt_ids':['known-prompt'],'message':'Recorded failure; no retry.',
                           'tracking_disposition':{'status':'resumed','history':[{'status':'stopped'}]}}}]}


class Handler(fixture.Handler,studio_server.Handler):
    # Fixture supplies inert routes; the real Handler supplies end_headers.
    script_reads=0
    def do_GET(self):
        path=urlsplit(self.path).path
        if path.endswith('.js'):Handler.script_reads+=1
        if path=='/api/health':
            return self.json({'online':True,'worker_alive':True,'schema_available':True,'missing_models':{},
                              'worker_failure':{'action':'generate','id':'retained-job','durable':False},'devices':[]})
        if path=='/__same_origin_frame':return self.frame_page('/')
        return super().do_GET()
    def frame_page(self,target):
        body=('<!doctype html><title>Embedding test</title><h1>Embedding test</h1><iframe title="Studio" src="'+target+'"></iframe>').encode()
        self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_POST(self):
        if urlsplit(self.path).path=='/api/production/'+IDENTIFIER+'/resume':
            body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
            fixture.POSTS.append({'path':self.path,'body':body})
            fixture.PLANS[0]['state'].update(status='failed',message='Outcome reconciled. An explicit repair branch is required.')
            fixture.PLANS[0]['can_reconcile_tracking']=False
            return self.json(fixture.PLANS[0])
        return super().do_POST()


def run(output):
    from playwright.sync_api import sync_playwright
    output.mkdir(parents=True,exist_ok=True);fixture.PLANS[:]=[copy.deepcopy(PROJECT)];fixture.POSTS.clear()
    target=ThreadingHTTPServer(('127.0.0.1',0),Handler);origin=f'http://127.0.0.1:{target.server_port}'
    class Parent(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_GET(self):Handler.frame_page(self,origin)
    parent=ThreadingHTTPServer(('127.0.0.1',0),Parent)
    threads=[]
    for http in (target,parent):
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start();threads.append(thread)
    result={'fixture':'Real Studio UI and end_headers; inert HTTP data; not a workstation or model run','passed':False}
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None,headless=True)
            try:
                page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                response=page.goto(origin);assert response.headers['content-security-policy']=="frame-ancestors 'none'"
                page.wait_for_function('!!selected && typeof renderProduction === "function"')
                page.wait_for_function('!document.querySelector("#workerFailure").hidden')
                assert page.locator('#workerFailure').is_visible(), 'Storage diagnostics must be visible in the active workspace'
                assert 'not saved' in page.locator('#workerFailure').inner_text()
                page.evaluate("showView('production');productionId='"+IDENTIFIER+"';renderProduction()")
                page.wait_for_selector('[data-project-action="resume"]')
                assert page.locator('#workerFailure').is_visible(), 'Changing views must not hide an unresolved worker diagnostic'
                button=page.locator('[data-project-action="resume"]')
                assert button.inner_text()=='Reconcile outcome only' and button.is_enabled()
                for width in (1440,390):
                    page.set_viewport_size({'width':width,'height':1000})
                    assert page.locator('#workerFailure').is_visible()
                    page.screenshot(path=str(output/f'recovery-{width}.png'),full_page=True)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Horizontal overflow'
                button.focus();button.press('Enter')
                page.wait_for_function("document.querySelector('#productionDetail').textContent.includes('Outcome reconciled')")
                assert page.locator('[data-project-action="resume"]').count()==0
                assert page.locator('[data-project-action="branch"]').count()==1
                result.update(browser=browser.version,page_errors=errors,keyboard_reconciliation=True)
                assert not errors,errors
                page.close()
                frames=[]
                for label,url in (('same-origin',origin+'/__same_origin_frame'),('cross-origin',f'http://127.0.0.1:{parent.server_port}')):
                    framed=browser.new_page();messages=[];framed.on('console',lambda message:messages.append(message.text))
                    before=Handler.script_reads;framed.goto(url)
                    framed.wait_for_timeout(500)
                    assert any('frame-ancestors' in m for m in messages),messages
                    assert Handler.script_reads==before, 'Framed Studio scripts executed'
                    frames.append({'parent':label,'blocked':True,'studio_script_requests':0,'policy_messages':messages})
                    framed.close()
                writes=[p for p in fixture.POSTS if p['path'] not in ('/api/estimate','/api/references/check')]
                assert len(writes)==1 and writes[0]['path']=='/api/production/'+IDENTIFIER+'/resume',writes
                result.update(passed=True,framing=frames,mutating_requests=writes)
            finally:browser.close()
    except Exception as exc:
        result['error']=str(exc);raise
    finally:
        for http in (target,parent):http.shutdown();http.server_close()
        for thread in threads:thread.join(5)
        (output/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    run(parser.parse_args().out)
