"""Actual Prompt Lab + real review HTTP handlers; synthetic source bytes, no VLM.

Run: python tests/reference_review_browser.py --output .runtime/reference-review/browser
"""
import argparse
import base64
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from studio_prompt.http_extension import extend_handler
from test_reference_review import ReferenceReviewTests
from studio_browser_smoke import Handler as StaticHandler


HOLD = threading.Event(); ARRIVED = threading.Event(); RELEASE = threading.Event()


class Base(StaticHandler):
    studio = None
    def _json(self, status, value):
        if self.path == '/api/prompt/reference-review/preview' and status == 200 and HOLD.is_set():
            ARRIVED.set(); RELEASE.wait(10)
        return self.json(value, status)
    def _safe_host(self): return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'
    def _safe_mutation(self): return self._safe_host() and self.headers.get('Origin') == f'http://127.0.0.1:{self.server.server_port}'
    def _content_length(self, limit):
        n = int(self.headers.get('Content-Length', '-1'))
        if not 0 <= n <= limit: raise ValueError('Request too large')
        return n


POSTS = []
class Handler(extend_handler(Base)):
    def do_POST(self):
        POSTS.append(self.path)
        return super().do_POST()


def run(output):
    from playwright.sync_api import sync_playwright, expect
    fixture = ReferenceReviewTests(); fixture.setUp()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp); analysis = folder / 'analysis.json'; analysis.write_text(json.dumps({'analysis': fixture.report}))
        originals = []
        for i, source in enumerate(fixture.images):
            file = folder / f'renamed-{i}.png'; file.write_bytes(base64.b64decode(source['media_base64'])); originals.append(str(file))
        wrong = folder / 'wrong.png'; wrong.write_bytes(base64.b64decode(fixture.images[0]['media_base64']) + b'replaced')
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever); thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),
                    headless=True, args=['--no-sandbox'])
                try:
                    for width in (1440, 390):
                        page = browser.new_page(viewport={'width': width, 'height': 1000})
                        errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
                        page.goto(f'http://127.0.0.1:{server.server_port}/prompt-lab.html')
                        page.locator('#profile option').first.wait_for(state='attached')
                        initial = page.locator('#brief').input_value()
                        before = len(POSTS)
                        page.locator('#rr-analysis').set_input_files(str(analysis))
                        expect(page.locator('#rr-summary')).to_have_text(fixture.report['answer']['summary'], timeout=4000)
                        expect(page.locator('#rr-cards b')).to_have_count(0)  # Descriptions must be inert text.
                        expect(page.locator('#rr-preview')).to_be_disabled()
                        page.locator('#rr-originals').set_input_files(originals[::-1])
                        expect(page.locator('#rr-preview')).to_be_enabled()
                        expect(page.locator('#rr-source-status')).to_contain_text('2 originals matched')
                        style = page.locator('[data-reference="picture-1"] [data-facet="style"] textarea')
                        style.fill('bold expressive ink')
                        selected = page.locator('[data-reference="picture-1"] [data-facet="style"] input')
                        selected.uncheck(); selected.check()
                        page.locator('#rr-preview').focus(); page.keyboard.press('Enter')
                        expect(page.locator('#rr-apply')).to_be_enabled()
                        expect(page.locator('#rr-change-summary')).to_contain_text('2 reference')
                        expect(page.locator('#brief')).to_have_value(initial)
                        # Every manual edit invalidates the prepared result, not only a save.
                        page.locator('#brief').fill('A newer instruction')
                        expect(page.locator('#rr-apply')).to_be_disabled()
                        page.locator('#rr-preview').click(); expect(page.locator('#rr-apply')).to_be_enabled()
                        page.locator('#rr-apply').focus(); page.keyboard.press('Enter')
                        expect(page.locator('#style')).to_have_value('picture-1: bold expressive ink')
                        expect(page.locator('#brief')).to_have_value('A newer instruction')
                        assert len(page.evaluate('StudioPromptDraft.capture().intent.references')) == 2
                        with page.expect_download() as download:
                            page.locator('#rr-export').click()
                        receipt_file = output / f'receipt-{width}.json'; download.value.save_as(str(receipt_file))
                        receipt = json.loads(receipt_file.read_text())
                        assert receipt['preview']['reference_draft']['source_report_sha256'] == fixture.report['report_sha256']
                        assert receipt['preview']['reference_draft']['unresolved_questions'] == fixture.report['answer']['questions']
                        assert 'media_base64' not in receipt_file.read_text()
                        page.screenshot(path=str(output / f'review-{width}.png'), full_page=True)
                        page.locator('#rr-undo').click()
                        expect(page.locator('#style')).to_have_value('')
                        expect(page.locator('#brief')).to_have_value('A newer instruction')
                        assert not page.evaluate('StudioPromptDraft.capture().intent.references')
                        if width == 1440:
                            # Real handler computes a preview, then delays only its reply.
                            HOLD.set(); ARRIVED.clear(); RELEASE.clear()
                            try:
                                page.locator('#rr-preview').click()
                                assert ARRIVED.wait(5), 'The real preview handler was not reached'
                                page.locator('#style').fill('Newer edit while response is held')
                                expect(page.locator('#rr-preview')).to_be_disabled()
                                RELEASE.set()
                                expect(page.locator('#rr-preview')).to_be_enabled()
                                expect(page.locator('#rr-apply')).to_be_disabled()
                                expect(page.locator('#style')).to_have_value('Newer edit while response is held')
                            finally: HOLD.clear(); RELEASE.set()
                            page.locator('#rr-preview').click(); expect(page.locator('#rr-apply')).to_be_enabled()
                            page.locator('#rr-apply').click(); page.locator('#style').fill('Manual edit after apply')
                            page.locator('#rr-undo').click()
                            expect(page.locator('#rr-status')).to_contain_text('changed after applying')
                            expect(page.locator('#style')).to_have_value('Manual edit after apply')
                        page.locator('#rr-originals').set_input_files([str(wrong), originals[1]])
                        expect(page.locator('#rr-status')).to_contain_text('exact original')
                        expect(page.locator('#rr-preview')).to_be_disabled()
                        # No horizontal overflow at either width, including 200% text zoom.
                        page.locator('#rr-help').evaluate('(e)=>e.open=true')
                        page.screenshot(path=str(output / f'refusal-{width}.png'), full_page=True)
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'overflow at {width}'
                        page.add_style_tag(content='html{font-size:200%}')
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'zoom overflow at {width}'
                        assert not errors, errors
                        allowed = {'/api/prompt/compile','/api/prompt/reference-review/inspect','/api/prompt/reference-review/preview'}
                        assert set(POSTS[before:]) <= allowed, POSTS[before:]
                        page.close()
                    print(json.dumps({'widths': [1440,390], 'page_errors': 0, 'generation_requests': 0,
                        'helper_requests': 0, 'posts': {path: POSTS.count(path) for path in sorted(set(POSTS))}}))
                finally: browser.close()
        finally: server.shutdown(); thread.join(); server.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, default=ROOT/'.runtime/reference-review/browser')
    run(parser.parse_args().output)
