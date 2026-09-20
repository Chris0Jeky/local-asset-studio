"""Native Chromium journeys on the actual composed Studio handler, inert storage only."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import threading
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'app'), str(ROOT / 'scripts')]
from playwright.sync_api import sync_playwright
import test_spoken_brief_exports as fixtures
from spoken_brief_qa import save_report
from spoken_brief_archive import inspect_run
sys.path.insert(0, str(ROOT))  # CLI fixture adds scripts first; prefer the actual package.
from studio_prompt.http_extension import extend_handler
spec = importlib.util.spec_from_file_location('spoken_browser_server', ROOT / 'app/server.py')
server_module = importlib.util.module_from_spec(spec); spec.loader.exec_module(server_module)


class SpokenBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        executable = os.environ.get('LAS_CHROMIUM_EXECUTABLE') or shutil.which('chromium')
        cls.browser = cls.pw.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop()

    def setUp(self):
        self.f = fixtures.ExportTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.archive = inspect_run(self.f.directory)
        evidence = {'schema_version': 1, 'manifest_sha256': self.archive['manifest_sha256'],
                    'master_sha256': self.archive['master']['sha256'], 'observations': []}
        self.report_id = save_report(self.f.directory, evidence)['id']
        self.traffic = []; traffic = self.traffic
        class Handler(extend_handler(server_module.Handler)):
            def _safe_host(inner): return inner.headers.get('Host') == f'127.0.0.1:{inner.server.server_port}'
            def _safe_mutation(inner): return inner._safe_host() and inner.headers.get('Origin') == 'http://' + inner.headers['Host']
            def do_GET(inner): traffic.append(('GET', inner.path)); return super().do_GET()
            def do_POST(inner): traffic.append(('POST', inner.path)); return super().do_POST()
        Handler.studio = SimpleNamespace(config={'spoken_briefs': {'archive_root': str(self.f.source.parent)}})
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01}); self.thread.start()
        self.addCleanup(self.stop_server)
        self.context = self.browser.new_context(viewport={'width': 1280, 'height': 900})
        self.addCleanup(self.context.close)
        self.page = self.context.new_page(); self.errors = []
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))
        self.origin = f'http://127.0.0.1:{self.server.server_port}'
        self.page.set_default_timeout(8000)
        self.page.goto(self.origin + '/spoken-briefs.html')
        self.page.wait_for_function("document.querySelector('#discover') && !document.querySelector('#discover').disabled")

    def stop_server(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(5)

    def inspect(self):
        self.page.locator('#discover').click()
        self.page.locator('#archiveList option').first.wait_for(state='attached')
        self.page.locator('#inspect').click()
        self.page.locator('#archivePanel').wait_for(state='visible')

    def assert_no_inference(self):
        posts = [path for method, path in self.traffic if method == 'POST']
        self.assertTrue(all(path.startswith(('/api/spoken-briefs/bookmark?', '/api/spoken-briefs/review?')) for path in posts), posts)
        self.assertFalse(self.errors, self.errors)

    def test_initial_page_and_archive_inspection_never_write_or_autoplay(self):
        self.assertFalse(any('/archives' in path for _, path in self.traffic))
        self.inspect()
        self.assertEqual('COMPRESSED.md', self.page.locator('#archiveTitle').inner_text())
        self.assertEqual(2, self.page.locator('#chapters button[data-chapter]').count())
        self.assertEqual(4, self.page.locator('#segments tbody tr').count())
        self.assertEqual(0, len([x for x in self.traffic if x[0] == 'POST']))
        self.assertTrue(self.page.locator('#player').evaluate('(a)=>a.paused'))
        self.assert_no_inference()

    def test_native_audio_explicit_bookmark_and_reload(self):
        self.inspect(); self.page.locator('#player').evaluate('(a)=>a.play()')
        self.page.wait_for_function("document.querySelector('#player').currentTime > 0")
        self.page.locator('#player').evaluate('(a)=>{a.pause();a.currentTime=0.01;}')
        self.assertFalse(any(m == 'POST' for m, _ in self.traffic))
        self.page.locator('#savePosition').click(); self.page.wait_for_function("document.querySelector('#status').textContent.includes('Bookmark saved')")
        prior = json.loads((self.f.directory / 'playback.json').read_bytes())
        self.assertGreater(prior['sample'], 0)
        self.page.reload(); self.page.wait_for_function("!document.querySelector('#discover').disabled")
        self.inspect()
        self.assertIn(str(prior['sample']), self.page.locator('#savedPosition').inner_text())
        self.assertEqual(1, len([m for m, _ in self.traffic if m == 'POST']))
        self.assert_no_inference()

    def test_saved_rate_is_applied_to_native_playback_and_segment_switches(self):
        from spoken_brief_exports import save_playback
        save_playback(self.f.directory, sample=0, rate=1.75)
        self.inspect()
        self.assertEqual('1.75', self.page.locator('#rate').input_value())
        self.assertEqual(1.75, self.page.locator('#player').evaluate('(a)=>a.playbackRate'))
        self.page.locator('#audioTarget').select_option('segment-0001')
        self.page.locator('#player').evaluate('(a)=>a.play()')
        self.page.wait_for_function("document.querySelector('#player').currentTime > 0")
        self.assertEqual(1.75, self.page.locator('#player').evaluate('(a)=>a.playbackRate'))
        self.assertFalse(any(m == 'POST' for m, _ in self.traffic))
        self.assert_no_inference()

    def test_report_and_listening_review_remain_separate(self):
        self.inspect(); self.page.locator('#reportList').select_option(self.report_id)
        self.page.locator('#loadReport').click(); self.page.wait_for_function("document.querySelector('#machineSummary').textContent.includes('not-transcribed')")
        self.assertIn('Unreviewed', self.page.locator('#humanSummary').inner_text())
        self.page.locator('#decision').select_option('replace'); self.page.locator('#reason').fill('Owner hears an unclear opening word.')
        self.page.locator('#reviewTarget').select_option('segment-0001'); self.page.locator('#saveReview').click()
        self.page.wait_for_function("document.querySelector('#status').textContent.includes('Listening review saved')")
        self.assertFalse((self.f.directory / 'replacements').exists())
        review = next((self.f.directory / 'qa/reviews').glob('*.json'))
        self.assertEqual('replace', json.loads(review.read_bytes())['decision'])
        self.assertIn('not-transcribed', self.page.locator('#machineSummary').inner_text())
        self.assert_no_inference()

    def test_bookmark_conflict_preserves_input_until_explicit_inspection(self):
        from spoken_brief_exports import save_playback
        self.inspect(); save_playback(self.f.directory, sample=11)
        self.page.locator('#savePosition').click(); self.page.wait_for_function("document.querySelector('#status').textContent.includes('Inspect this archive')")
        self.assertTrue(self.page.locator('#savePosition').is_disabled())
        self.assertEqual(11, json.loads((self.f.directory / 'playback.json').read_bytes())['sample'])
        self.page.locator('#reason').fill('Preserve this unsaved review')
        self.assertEqual('Preserve this unsaved review', self.page.locator('#reason').input_value())
        self.assert_no_inference()

    def test_chapter_seek_and_identity_named_download(self):
        self.inspect(); target = self.archive['chapters'][1]['start_sample'] / 48000
        self.page.locator('#chapters button[data-chapter]').nth(1).click()
        self.page.wait_for_function('(t)=>Math.abs(document.querySelector("#player").currentTime-t)<0.002', arg=target)
        self.assertTrue(self.page.locator('#player').evaluate('(a)=>a.paused'))
        with self.page.expect_download() as event: self.page.locator('#downloadChapters').click()
        download = event.value; self.assertIn(self.archive['manifest_sha256'][:12], download.suggested_filename)
        self.assertEqual(0, len([m for m, _ in self.traffic if m == 'POST']))
        output = os.environ.get('SPOKEN_BROWSER_SCREENSHOT')
        if output:
            Path(output).parent.mkdir(parents=True, exist_ok=True); self.page.screenshot(path=output, full_page=True)
        self.assert_no_inference()

    def test_failure_on_inspect_hides_stale_player_without_sending_writes(self):
        self.inspect(); (self.f.directory / 'receipt.json').write_text('{}', encoding='utf-8')
        self.page.locator('#inspect').click(); self.page.wait_for_function("document.querySelector('#status').textContent !== 'Verifying the retained archive and its actual PCM samples…'")
        self.assertTrue(self.page.locator('#archivePanel').is_hidden())
        self.assertFalse(any(m == 'POST' for m, _ in self.traffic))
        self.assert_no_inference()


if __name__ == '__main__': unittest.main(verbosity=2)
