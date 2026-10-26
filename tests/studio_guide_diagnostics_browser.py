"""Prove native load timeout evidence without claiming the earlier CI failure's cause."""
import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path
import shutil
import threading
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit

from browser_ports import browser_server
from studio_guide_diagnostics import GuideNavigationDiagnostics

CALLS=[];HELD=threading.Event();RELEASE=threading.Event()
PNG=bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000b49444154789c636000020000050001a5f645400000000049454e44ae426082')


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        path=urlsplit(self.path).path;CALLS.append(('GET',path))
        if path=='/held.png':
            HELD.set();RELEASE.wait(30);body=PNG;kind='image/png'
        else:
            image='<img src="/held.png" alt="Synthetic held image">' if path=='/held' else ''
            body=('<!doctype html><title>Synthetic diagnostic control</title><div class="studio-guide-panel">Ready</div>'
                  '<script>let selected=true,backendActive=true;</script>'+image).encode();kind='text/html'
        self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass


def run(out,without_diagnostics=False):
    from playwright.sync_api import sync_playwright,TimeoutError as BrowserTimeout
    out.mkdir(parents=True,exist_ok=True);checks=[];server=browser_server(Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    origin='http://127.0.0.1:'+str(server.server_port)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None,headless=True,args=['--no-sandbox'])
            try:
                for mode in ('control','held'):
                    CALLS.clear();page=browser.new_page(viewport={'width':1440,'height':1000});folder=out/mode
                    observer=nullcontext(page) if without_diagnostics else GuideNavigationDiagnostics(page,folder,lambda:CALLS)
                    try:
                        with observer as navigation:
                            navigation.goto(origin+'/'+mode,timeout=15000)
                            page.wait_for_selector('.studio-guide-panel')
                            page.wait_for_function('typeof selected !== "undefined" && !!selected && typeof backendActive !== "undefined" && !!backendActive')
                    except BrowserTimeout as error:
                        assert mode=='held' and HELD.is_set(),str(error)
                        assert 'Timeout 15000ms exceeded' in str(error),str(error)
                        # These asserts execute before releasing the held response or closing the page.
                        assert (folder/'navigation.json').is_file(),'load failure discarded its diagnostic receipt'
                        receipt=json.loads((folder/'navigation.json').read_text())
                        assert receipt['outcome']=='failed' and receipt['exception']['type']==type(error).__name__,receipt
                        assert any(item['resource_type']=='image' and item['url'].endswith('/held.png') for item in receipt['pending_requests']),receipt
                        phases=[item['event'] for item in receipt['events']]
                        assert 'domcontentloaded' in phases and 'load' not in phases,phases
                        assert {'method':'GET','url':'/held.png'} in receipt['server_calls'],receipt
                        page.wait_for_function('document.querySelector(".studio-guide-panel") && typeof selected !== "undefined" && !!selected && typeof backendActive !== "undefined" && !!backendActive',timeout=1000)
                        checks.append('original 15s load timeout propagates with pending image, DCL and server evidence before cleanup')
                    else:
                        assert mode=='control','held image did not retain the original load failure'
                        if not without_diagnostics:
                            receipt=json.loads((folder/'navigation.json').read_text())
                            assert receipt['outcome']=='passed' and any(item['event']=='load' for item in receipt['events']),receipt
                        checks.append('unchanged successful load and readiness control passes')
                    finally:
                        if mode=='held':RELEASE.set()
                        page.close()
            finally:browser.close()
        (out/'result.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'synthetic_fixture':True,'original_ci_cause':'unestablished'},indent=2)+'\n')
        for label in checks:print('PASS '+label,flush=True)
    finally:RELEASE.set();server.shutdown();server.server_close();thread.join(5)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--without-diagnostics',action='store_true',help='Retain the pre-fix missing-receipt failure for causal comparison.')
    args=parser.parse_args();run(args.out,args.without_diagnostics)
