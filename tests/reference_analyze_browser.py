"""Real browser -> real HTTP/SQLite -> actual Studio worker; only model/sensors fake.

Never creates a generation job or contacts the owner's workstation.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import queue
import shutil
import socket
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import test_reference_jobs as fixtures
from studio_prompt.http_extension import extend_handler
from studio_browser_smoke import Handler as StaticHandler

POSTS=[]
DROP=threading.Event(); DROP_RETIRE=threading.Event(); MODEL_ENTERED=threading.Event(); MODEL_RELEASE=threading.Event(); LOSE_MODEL=threading.Event()

class Base(StaticHandler):
    def _json(self,status,value):
        if self.path=='/api/prompt/reference-jobs/create' and status==202 and DROP.is_set():
            DROP.clear();self.close_connection=True
            self.connection.shutdown(socket.SHUT_RDWR);self.connection.close();return
        if self.path=='/api/prompt/reference-jobs/retire' and status==200 and DROP_RETIRE.is_set():
            DROP_RETIRE.clear();self.close_connection=True
            self.connection.shutdown(socket.SHUT_RDWR);self.connection.close();return
        return self.json(value,status)
    def _safe_host(self):return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'
    def _safe_mutation(self):return self._safe_host() and self.headers.get('Origin')==f'http://127.0.0.1:{self.server.server_port}'
    def _content_length(self,limit):
        n=int(self.headers.get('Content-Length','-1'))
        if not 0<=n<=limit:raise ValueError('Invalid request length')
        return n

class Handler(extend_handler(Base)):
    def do_POST(self):POSTS.append(self.path);return super().do_POST()


def run(output):
    from playwright.sync_api import sync_playwright,expect
    fixture=fixtures.ReferenceJobTests();fixture.setUp();fixture.start.stop()
    output.mkdir(parents=True,exist_ok=True)
    original=fixture.transport
    def model(*args,**kwargs):
        if args[2]=='/api/chat':
            MODEL_ENTERED.set()
            if not MODEL_RELEASE.wait(15):raise OSError('fixture model release timed out')
            if LOSE_MODEL.is_set():raise OSError('fixture: model accepted; reply lost')
        return original(*args,**kwargs)
    Handler.studio=fixture.studio_instance
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);http_thread=threading.Thread(target=server.serve_forever)
    original_get=fixture.studio_instance.queue.get
    class EndWorker(BaseException):pass
    def get(timeout=None):
        # The worker's own get is bounded now and it swallows queue.Empty, so the 40 s watchdog ends the worker explicitly.
        try:item=original_get(timeout=40)
        except queue.Empty:raise EndWorker()
        if item==('fixture-stop',None):raise EndWorker()
        return item
    def worker():
        try:fixture.studio_instance._work()
        except (EndWorker,queue.Empty):pass
    with tempfile.TemporaryDirectory() as tmp,patch('studio_prompt.reference_jobs.http_json',side_effect=model),patch.object(fixture.studio_instance.queue,'get',side_effect=get):
        originals=[]
        for n,row in enumerate(fixture.images):
            path=Path(tmp)/f'picture-{n+1}.png';path.write_bytes(base64.b64decode(row['media_base64']));originals.append(str(path))
        work_thread=threading.Thread(target=worker);http_thread.start();work_thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
                try:
                    for width in (1440,390):
                        page=browser.new_page(viewport={'width':width,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                        MODEL_ENTERED.clear();MODEL_RELEASE.clear()
                        if width==390:DROP.set()
                        before=POSTS.count('/api/prompt/reference-jobs/create')
                        page.goto(f'http://127.0.0.1:{server.server_port}/prompt-lab.html')
                        expect(page.locator('#ra-config')).to_contain_text(fixtures.MODEL)
                        page.locator('#ra-files').set_input_files(originals)
                        page.locator('#brief').fill('Same traveller, use that pose')
                        expect(page.locator('#ra-start')).to_be_enabled()
                        assert POSTS.count('/api/prompt/reference-jobs/create')==before
                        page.locator('#ra-start').focus();page.keyboard.press('Enter')
                        assert MODEL_ENTERED.wait(10),'Worker did not reach the fake model'
                        expect(page.locator('#ra-start')).to_be_disabled()
                        request_id=page.locator('#ra-identity').inner_text();assert request_id
                        page.locator('#brief').fill('Newer text while analysis is running')
                        if width==390:expect(page.locator('#ra-status')).to_contain_text('Check status')
                        # Reload the actual page with a committed (possibly lost-reply) request.
                        page.reload();expect(page.locator('#ra-identity')).to_have_text(request_id)
                        page.locator('#brief').fill('Keep this newer instruction')
                        MODEL_RELEASE.set()
                        expect(page.locator('#ra-use')).to_be_enabled(timeout=10000)
                        assert POSTS.count('/api/prompt/reference-jobs/create')==before+1
                        page.locator('#ra-files').set_input_files(originals[::-1])
                        page.locator('#ra-use').click()
                        expect(page.locator('#rr-summary')).to_have_text('Traveller leaning over a desk')
                        expect(page.locator('#rr-preview')).to_be_enabled()
                        expect(page.locator('#brief')).to_have_value('Keep this newer instruction')
                        page.locator('#rr-preview').click();expect(page.locator('#rr-apply')).to_be_enabled();page.locator('#rr-apply').click()
                        expect(page.locator('#subject')).to_have_value('silver-haired traveller')
                        assert page.evaluate("StudioPromptDraft.capture().intent.facets.action")=='leaning over a desk'
                        expect(page.locator('#brief')).to_have_value('Keep this newer instruction')
                        with page.expect_download() as download:page.locator('#rr-export').click()
                        destination=output/f'analysis-receipt-{width}.json';download.value.save_as(str(destination));receipt=json.loads(destination.read_text(encoding='utf-8'))
                        assert receipt['analysis']['request']['references'][0]['sha256']==fixture.refs[0]['sha256']
                        assert 'media_base64' not in destination.read_text(encoding='utf-8')
                        page.screenshot(path=str(output/f'analysis-{width}.png'),full_page=True)
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'overflow {width}'
                        page.add_style_tag(content='html{font-size:200%}')
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'text zoom overflow {width}'
                        if width==1440:
                            # A real pre-commit decoder refusal leaves an unknown ID.
                            page.locator('#ra-new').click();expect(page.locator('#ra-start')).to_be_enabled()
                            bad=Path(tmp)/'corrupt.png';bad.write_bytes(b'not an image')
                            page.locator('#ra-files').set_input_files(str(bad))
                            with page.expect_response(lambda r:r.url.endswith('/reference-jobs/create') and r.request.method=='POST') as rejection:
                                page.locator('#ra-start').click()
                            assert rejection.value.status==400
                            assert 'could not be decoded' in rejection.value.json()['error']
                            expect(page.locator('#ra-check')).to_be_enabled();page.locator('#ra-check').click()
                            expect(page.locator('#ra-status')).to_contain_text('Unknown analysis request')
                            expect(page.locator('#ra-new')).to_be_disabled()
                            page.locator('#ra-recovery summary').click();expect(page.locator('#ra-retire')).to_be_enabled()
                            rejected_id=page.locator('#ra-identity').inner_text()
                            DROP_RETIRE.set();page.locator('#ra-retire').click()
                            expect(page.locator('#ra-status')).to_contain_text('Check status before another command.')
                            assert not DROP_RETIRE.is_set(),'The real handler must have dropped the retirement reply'
                            expect(page.locator('#ra-new')).to_be_disabled()
                            expect(page.locator('#ra-check')).to_be_enabled();page.locator('#ra-check').click()
                            expect(page.locator('#ra-status')).to_contain_text('retired before creation')
                            expect(page.locator('#ra-identity')).to_have_text(rejected_id)
                            expect(page.locator('#ra-new')).to_be_enabled()
                            page.locator('#ra-new').click()
                            page.locator('#ra-files').set_input_files(originals);expect(page.locator('#ra-start')).to_be_enabled()
                            page.screenshot(path=str(output/'retirement-recovery.png'),full_page=True)
                        if width==390:
                            page.locator('#ra-new').click();expect(page.locator('#ra-start')).to_be_enabled()
                            LOSE_MODEL.set();page.locator('#ra-start').click()
                            expect(page.locator('#ra-status')).to_contain_text('uncertain',timeout=10000)
                            expect(page.locator('#ra-start')).to_be_disabled()
                            page.locator('#ra-hold summary').click();page.locator('#ra-release').click()
                            expect(page.locator('#ra-status')).to_contain_text('Confirm the specific helper call has stopped')
                            page.locator('#ra-acknowledge').check();page.locator('#ra-release').click()
                            expect(page.locator('#ra-new')).to_be_enabled();expect(page.locator('#ra-hold')).to_be_hidden()
                            LOSE_MODEL.clear()
                        assert not errors,errors;page.close()
                finally:browser.close()
            assert not fixture.studio_instance.jobs,'No generation job may be created'
            allowed={'/api/prompt/compile','/api/prompt/reference-jobs/create','/api/prompt/reference-jobs/release','/api/prompt/reference-jobs/retire',
                     '/api/prompt/reference-review/inspect','/api/prompt/reference-review/preview'}
            assert set(POSTS)<=allowed,POSTS
            assert POSTS.count('/api/prompt/reference-jobs/create')==4
            assert POSTS.count('/api/prompt/reference-jobs/retire')==1
            result={'widths':[1440,390],'page_errors':0,'generation_jobs':0,'analysis_create_requests':POSTS.count('/api/prompt/reference-jobs/create'),
                'checks':['actual worker','lost committed reply','reload without replay','current brief preserved','exact originals','guarded review','unknown resource hold release','pre-commit refusal retirement','lost retirement reply readback']}
            (output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
        finally:
            MODEL_RELEASE.set();fixture.studio_instance.queue.put(('fixture-stop',None));work_thread.join(20)
            server.shutdown();http_thread.join();server.server_close()
            fixture.tearDown();fixture.doCleanups()
            assert not work_thread.is_alive(),'Fixture worker must stop'

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'.runtime/reference-analysis/browser')
    run(parser.parse_args().output)