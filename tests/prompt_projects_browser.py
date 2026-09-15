"""Real browser and shared SQLite commands; synthetic briefs, no model worker."""
import argparse
import base64
import copy
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'app'))
from workspace import AssetWorkspace
from studio_prompt.projects import PromptProjects
from studio_prompt.http_extension import extend_handler
from studio_browser_smoke import Handler as StaticHandler
import test_reference_review as reference_fixture

DROP=threading.Event();HOLD=threading.Event();ARRIVED=threading.Event();RELEASE=threading.Event();POSTS=[]
class Base(StaticHandler):
    def _json(self,status,value):
        if self.path.startswith('/api/prompt/projects/') and self.command=='POST' and status==200:
            if HOLD.is_set():ARRIVED.set();RELEASE.wait(10)
            if DROP.is_set():
                DROP.clear();self.close_connection=True;self.connection.shutdown(socket.SHUT_RDWR);self.connection.close();return
        return self.json(value,status)
    def _safe_host(self):return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'
    def _safe_mutation(self):return self._safe_host() and self.headers.get('Origin')==f'http://127.0.0.1:{self.server.server_port}'
    def _content_length(self,limit):
        n=int(self.headers.get('Content-Length','-1'))
        if not 0<=n<=limit:raise ValueError('Request too large')
        return n
class Handler(extend_handler(Base)):
    def do_POST(self):POSTS.append(self.path);return super().do_POST()

def run(output):
    from playwright.sync_api import sync_playwright,expect
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        ws=AssetWorkspace(tmp);service=PromptProjects(ws);scope=service.capabilities()['workspace_id']
        Handler.studio=SimpleNamespace(prompt_projects=service)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever);thread.start()
        reference=reference_fixture.ReferenceReviewTests();reference.setUp()
        report=Path(tmp)/'analysis.json';report.write_text(json.dumps(reference.report),encoding='utf-8')
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
                try:
                    for width in (1440,390):
                        context=browser.new_context(viewport={'width':width,'height':1000});page=context.new_page();errors=[]
                        page.on('pageerror',lambda e:errors.append(str(e)));base=f'http://127.0.0.1:{server.server_port}'
                        def ready(page):
                            page.goto(base+'/prompt-lab.html');expect(page.locator('#pp-create')).to_be_enabled()
                        def preview_open(page,key):
                            page.locator('#pp-list').select_option(key);page.locator('#pp-preview').click()
                            expect(page.locator('#pp-open')).to_be_enabled();page.locator('#pp-open').click()
                        ready(page)
                        page.locator('#pp-name').fill(f'Keeper {width}');page.locator('#brief').fill('Original precise words')
                        page.locator('#rr-analysis').set_input_files(str(report));expect(page.locator('#rr-summary')).to_have_text(reference.report['answer']['summary'])
                        page.locator('[data-reference="picture-1"] [data-facet="style"] textarea').fill('bold edited ink')
                        page.locator('#pp-create').focus();page.keyboard.press('Enter')
                        expect(page.locator('#pp-current')).to_contain_text('revision 1')
                        row=next(x for x in service.list(scope)['projects'] if x['name']==f'Keeper {width}');key=row['id']
                        saved=service.get(scope,key);assert saved['document']['reference_context']['review']['selections'][0]['overrides']['style']=='bold edited ink'
                        count=len(POSTS);page.reload();expect(page.locator('#pp-create')).to_be_enabled()
                        # Loading the page does not save, open or re-analyze the document.
                        assert not any(x.startswith('/api/prompt/projects/') for x in POSTS[count:])
                        preview_open(page,key);expect(page.locator('#brief')).to_have_value('Original precise words')
                        expect(page.locator('[data-reference="picture-1"] [data-facet="style"] textarea')).to_have_value('bold edited ink')
                        expect(page.locator('#rr-preview')).to_be_disabled()
                        other=context.new_page();ready(other);preview_open(other,key)
                        page.locator('#brief').fill('Revision two');page.locator('#pp-save').click();expect(page.locator('#pp-current')).to_contain_text('revision 2')
                        other.locator('#brief').fill('Stale other tab');other.locator('#pp-save').click()
                        expect(other.locator('#pp-status')).to_contain_text('changed on the server');expect(other.locator('#brief')).to_have_value('Stale other tab')
                        assert service.get(scope,key)['document']['intent']['brief']=='Revision two';other.close()
                        page.locator('#prompt-projects').get_by_text('Earlier revisions',exact=True).click()
                        page.locator('#pp-history').click();expect(page.locator('#pp-revision option[value="1"]')).to_have_count(1)
                        page.locator('#pp-revision').select_option('1');page.locator('#pp-old').click();expect(page.locator('#pp-restore')).to_be_enabled()
                        page.locator('#pp-restore').click();expect(page.locator('#pp-current')).to_contain_text('revision 3')
                        assert service.get(scope,key)['document']['intent']['brief']=='Original precise words'
                        # Explicit opening of restore result, never automatic overwrite.
                        expect(page.locator('#brief')).to_have_value('Revision two');page.locator('#pp-open').click()
                        expect(page.locator('#brief')).to_have_value('Original precise words')
                        page.locator('#brief').fill('Stored before a lost reply');DROP.set()
                        before=POSTS.count('/api/prompt/projects/save');page.locator('#pp-save').click()
                        expect(page.locator('#pp-recovery')).to_be_visible();expect(page.locator('#pp-status')).to_contain_text('Check save status')
                        page.reload();expect(page.locator('#pp-recovery')).to_be_visible();page.locator('#brief').fill('Keep newer typing after reload')
                        page.locator('#pp-check').click();expect(page.locator('#pp-status')).to_contain_text('confirmed')
                        expect(page.locator('#brief')).to_have_value('Keep newer typing after reload')
                        assert POSTS.count('/api/prompt/projects/save')==before+1;assert service.get(scope,key)['revision']==4
                        expect(page.locator('#pp-open')).to_be_enabled();page.locator('#pp-open').click()
                        expect(page.locator('#brief')).to_have_value('Stored before a lost reply')
                        # A successful delayed save must not replace later typing.
                        HOLD.set();ARRIVED.clear();RELEASE.clear();page.locator('#brief').fill('Sent before hold');page.locator('#pp-save').click()
                        assert ARRIVED.wait(5)
                        page.locator('#brief').fill('Newer while saving');RELEASE.set();HOLD.clear()
                        expect(page.locator('#pp-current')).to_contain_text('revision 5');expect(page.locator('#brief')).to_have_value('Newer while saving')
                        expect(page.locator('#pp-current')).to_contain_text('unsaved')
                        # Storage failure sends zero saves, preserving the user's current input.
                        before=POSTS.count('/api/prompt/projects/save')
                        page.evaluate("window.savedSet=Storage.prototype.setItem;Storage.prototype.setItem=function(){throw Error('quota fixture')}")
                        page.locator('#pp-save').click();expect(page.locator('#pp-status')).to_contain_text('retained')
                        assert POSTS.count('/api/prompt/projects/save')==before
                        page.evaluate('Storage.prototype.setItem=window.savedSet')
                        page.screenshot(path=str(output/f'briefs-{width}.png'),full_page=True)
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                        assert not errors,errors
                        (output/f'project-{width}.json').write_text(json.dumps(service.get(scope,key),indent=2),encoding='utf-8')
                        context.close()
                    assert set(POSTS)<={'/api/prompt/compile','/api/prompt/reference-review/inspect','/api/prompt/projects/create','/api/prompt/projects/save','/api/prompt/projects/restore'},POSTS
                    receipt={'widths':[1440,390],'page_errors':0,'model_calls':0,'generation_jobs':0,'writes':{x:POSTS.count(x) for x in sorted(set(POSTS))},'scenarios':['save/reload','review restoration','two-client conflict','append-only restore','lost reply/reload/read recovery','late save preserves typing','storage failure no write']}
                    (output/'result.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt))
                finally:browser.close()
        finally:RELEASE.set();server.shutdown();thread.join();server.server_close()
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'.runtime/prompt-projects/browser');run(parser.parse_args().output)
