"""Native Chromium journeys on the actual composed Studio handler, inert storage only."""
from browser_ports import evidence_screenshot
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import threading
from browser_ports import browser_server
from types import SimpleNamespace
import unittest
from unittest.mock import patch

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
        self.f = fixtures.ExportTests(); self.addCleanup(self.f.doCleanups); self.f.setUp()
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
        Handler.studio = SimpleNamespace(root=ROOT, config={'spoken_briefs': {'archive_root': str(self.f.source.parent)}})
        self.server = browser_server(Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01}); self.thread.start()
        self.addCleanup(self.stop_server)
        self.context = self.browser.new_context(viewport={'width': 1280, 'height': 900})
        self.addCleanup(self.context.close)
        self.page = self.context.new_page(); self.errors = []
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))
        self.addCleanup(self.save_diagnostics)
        self.page.route('**/api/catalog', lambda route: route.fulfill(json={'presets': []}))
        self.page.route('**/api/looks', lambda route: route.fulfill(json={'looks': []}))
        self.origin = f'http://127.0.0.1:{self.server.server_port}'
        self.page.set_default_timeout(8000)
        self.page.goto(self.origin + '/spoken-briefs.html')
        self.page.wait_for_function("document.querySelector('#discover') && !document.querySelector('#discover').disabled")

    def stop_server(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(5)

    def save_diagnostics(self):
        output = os.environ.get('SPOKEN_BROWSER_SCREENSHOT')
        if output:
            target = Path(output).with_name(self._testMethodName + '.json')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps({'page_errors': self.errors, 'traffic': self.traffic}, indent=2), encoding='utf-8')

    def inspect(self):
        self.page.locator('#discover').click()
        self.page.locator('#archiveList option').first.wait_for(state='attached')
        self.page.locator('#inspect').click()
        self.page.locator('#archivePanel').wait_for(state='visible')

    def load_audio(self):
        self.page.locator('#player').evaluate('(a)=>a.play()')
        self.page.wait_for_function('document.querySelector("#player").readyState >= 1')
        self.page.locator('#player').evaluate('(a)=>a.pause()')

    def assert_no_inference(self):
        posts = [path for method, path in self.traffic if method == 'POST']
        self.assertTrue(all(path.startswith(('/api/spoken-briefs/bookmark?', '/api/spoken-briefs/review?')) for path in posts), posts)
        self.assertFalse(self.errors, self.errors)

    def test_source_preview_real_compiler_keyboard_and_narrow_snapshot(self):
        from spoken_brief_compile import compile_source, batch_segments
        pack = self.f.source.parent / 'lantern-pack'; pack.mkdir()
        source = pack / 'COMPRESSED.md'
        source.write_bytes(b'---\r\nfictional: true\r\n---\r\n# Lantern keeper\r\n\r\nKeep the lantern blue.\r\n\r\n## Next scene\r\n\r\nLeave a light in the window.\r\n\r\n```\r\nomitted_code()\r\n```\r\n<!-- hidden note -->\r\n')
        expected = compile_source(source)
        def snapshot():
            return {p.relative_to(self.f.source.parent): p.read_bytes() for p in self.f.source.parent.rglob('*') if p.is_file()}
        before = snapshot()
        for width in (1280, 390):
            self.page.set_viewport_size({'width': width, 'height': 900})
            self.page.goto(self.origin + '/spoken-briefs.html')
            self.page.wait_for_function("!document.querySelector('#previewSource').disabled")
            count = len([path for _, path in self.traffic if '/source-preview?' in path])
            self.page.locator('#sourceKey').fill('lantern-pack')
            self.assertEqual(count, len([path for _, path in self.traffic if '/source-preview?' in path]))
            with self.page.expect_response(lambda r: '/source-preview?' in r.url) as response:
                self.page.locator('#previewSource').focus(); self.page.keyboard.press('Enter')
            self.page.locator('#sourcePreview').wait_for(state='visible')
            self.assertEqual(expected, response.value.json()['manifest'])
            self.assertEqual([s['text'] for s in expected['segments']], self.page.locator('#sourceSegments p').all_text_contents())
            self.assertIn(f"{len(batch_segments(expected['segments']))} batches", self.page.locator('#sourceCounts').inner_text())
            self.assertIn('code blocks: 1', self.page.locator('#sourceOmissions').inner_text())
            self.assertIn(expected['source']['sha256'], self.page.locator('#sourceIdentity').inner_text())
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width)
            self.assertEqual(0, self.page.locator('#sourcePreview script, #sourcePreview img').count())
            output = os.environ.get('SPOKEN_BROWSER_SCREENSHOT')
            if output:
                target = Path(output).with_name(f'spoken-source-{width}.png')
                evidence_screenshot(self.page, path=str(target), full_page=True)
                self.assertTrue(target.is_file(), 'Required preview capture must actually exist')
        self.assertEqual(before, snapshot())
        self.inspect(); self.load_audio()
        self.page.locator('#reason').fill('Fictional listening note remains a draft.')
        self.page.locator('#sourceKey').fill('absent.md')
        self.page.locator('#previewSource').click()
        self.page.wait_for_function("document.querySelector('#sourceStatus').textContent.includes('absent.md')")
        self.assertTrue(self.page.locator('#sourcePreview').is_hidden())
        self.assertTrue(self.page.locator('#archivePanel').is_visible())
        self.assertEqual('Fictional listening note remains a draft.', self.page.locator('#reason').input_value())
        self.assertTrue(self.page.locator('#player').evaluate('(a)=>a.paused'))
        self.assertEqual(before, snapshot())
        self.assertFalse(any(method == 'POST' for method, _ in self.traffic))
        self.assert_no_inference()

    def test_source_preview_delayed_response_cannot_replace_selection_or_root_refresh(self):
        from studio_spoken.core import ArchiveAccess
        original = ArchiveAccess.source_preview
        self.page.evaluate("""() => {
          window.previewSettled = 0;
          const original = SpokenReview.SourcePreviewSession.prototype.preview;
          SpokenReview.SourcePreviewSession.prototype.preview = async function (...args) {
            try { return await original.apply(this, args); } finally { window.previewSettled++; }
          };
        }""")
        for completed, action in enumerate(('selection', 'root'), 1):
            entered, release = threading.Event(), threading.Event()
            def delayed(access, *args):
                value = original(access, *args); entered.set()
                if not release.wait(8): raise AssertionError('Owned preview was not released')
                return value
            with patch.object(ArchiveAccess, 'source_preview', delayed):
                try:
                    self.page.locator('#sourceKey').fill('.')
                    self.page.locator('#previewSource').click(); self.assertTrue(entered.wait(3))
                    if action == 'selection':
                        self.page.locator('#sourceKey').fill('different.md')
                    else:
                        self.page.locator('#refreshSource').click()
                        self.page.wait_for_function("!document.querySelector('#previewSource').disabled")
                    with self.page.expect_response(lambda r: '/source-preview?' in r.url): release.set()
                    self.page.wait_for_function('(count)=>window.previewSettled === count', arg=completed)
                    self.assertTrue(self.page.locator('#sourcePreview').is_hidden())
                finally: release.set()
        self.assertFalse(any(method == 'POST' for method, _ in self.traffic))
        self.assert_no_inference()

    def test_voice_main_links_to_listening_after_shell_replaces_topbar(self):
        self.page.route('**/api/voice-baseline', lambda route: route.fulfill(
            json={'capabilities': {'configured': False}, 'projects': []}))
        for width in (1280, 390):
            with self.subTest(width=width):
                self.page.set_viewport_size({'width': width, 'height': 900})
                self.page.goto(self.origin + '/voice.html')
                self.page.locator('.studio-sidebar').wait_for(state='attached')
                link = self.page.locator('main a[href="/spoken-briefs.html"]')
                self.assertEqual(1, link.count(), 'The listening entry must survive shared-shell mounting')
                self.assertTrue(link.is_visible())
                link.focus(); self.page.keyboard.press('Enter')
                self.page.wait_for_url('**/spoken-briefs.html')
                self.page.wait_for_function("!document.querySelector('#discover').disabled")
        self.assertFalse(any(method == 'POST' for method, _ in self.traffic))
        self.assert_no_inference()

    def test_listening_return_link_reaches_existing_production_document(self):
        # Navigation itself also works without script execution or API side effects.
        with self.browser.new_context(java_script_enabled=False) as context:
            page = context.new_page()
            for width in (1280, 390):
                with self.subTest(width=width):
                    page.set_viewport_size({'width': width, 'height': 900})
                    page.goto(self.origin + '/spoken-briefs.html')
                    nav = page.get_by_role('navigation', name='Studio views')
                    self.assertEqual('page', nav.get_by_role('link', name='Spoken Briefs', exact=True).get_attribute('aria-current'))
                    self.assertEqual('/voice.html', nav.get_by_role('link', name='Voice takes', exact=True).get_attribute('href'))
                    link = nav.get_by_role('link', name='Compare & review', exact=True)
                    self.assertEqual('/#production', link.get_attribute('href'))
                    link.focus()
                    with page.expect_navigation() as navigation:
                        page.keyboard.press('Enter')
                    self.assertEqual(200, navigation.value.status)
                    self.assertEqual(self.origin + '/#production', page.url)
                    self.assertEqual(1, page.locator('#productionView').count())
        self.assertFalse(any(method == 'POST' for method, _ in self.traffic))

    def assert_shell_destination(self):
        self.page.locator('.studio-sidebar').wait_for(state='attached')
        self.assertEqual('Spoken Briefs', self.page.locator('#studioPageTitle').inner_text())
        active = self.page.locator('.studio-sidebar [aria-current="page"]')
        self.assertEqual(1, active.count())
        self.assertEqual('/spoken-briefs.html', active.get_attribute('href'))
        self.assertEqual(0, self.page.locator('.topbar').count())

    def test_shared_sidebar_and_keyboard_finder_reach_spoken_briefs(self):
        self.page.route('**/api/voice-baseline', lambda route: route.fulfill(
            json={'capabilities': {'configured': False}, 'projects': []}))
        for width in (1280, 390):
            for entry in ('sidebar', 'finder'):
                with self.subTest(width=width, entry=entry):
                    self.page.set_viewport_size({'width': width, 'height': 900})
                    self.page.goto(self.origin + '/voice.html')
                    self.page.locator('.studio-sidebar').wait_for(state='attached')
                    if entry == 'sidebar':
                        if width == 390: self.page.locator('#studioNavToggle').click()
                        link = self.page.locator('.studio-sidebar a[href="/spoken-briefs.html"]')
                        self.assertEqual(1, link.count(), 'The shared sidebar must expose retained listening')
                        self.assertTrue(link.is_visible())
                        link.focus(); self.page.keyboard.press('Enter')
                    else:
                        self.page.keyboard.press('Control+k')
                        self.page.locator('#studioCommandSearch').fill('spoken briefs')
                        self.page.keyboard.press('ArrowDown')
                        self.assertEqual('/spoken-briefs.html', self.page.evaluate('document.activeElement.getAttribute("href")'))
                        self.page.keyboard.press('Enter')
                    self.page.wait_for_url('**/spoken-briefs.html')
                    self.assert_shell_destination()
        self.assertFalse(any(method == 'POST' for method, _ in self.traffic))
        self.assert_no_inference()

    def test_spoken_shell_skip_focus_and_keyboard_dismissal(self):
        for width in (1280, 390):
            with self.subTest(width=width):
                self.page.set_viewport_size({'width': width, 'height': 900})
                self.page.goto(self.origin + '/spoken-briefs.html')
                self.assert_shell_destination()
                self.page.keyboard.press('Tab')
                self.assertTrue(self.page.locator('.studio-skip').evaluate('(e)=>e===document.activeElement'))
                self.page.keyboard.press('Enter')
                self.assertTrue(self.page.locator('main').evaluate('(e)=>e===document.activeElement'))
                self.page.keyboard.press('Control+k')
                self.assertTrue(self.page.locator('#studioCommandSearch').evaluate('(e)=>e===document.activeElement'))
                self.page.keyboard.press('Escape')
                self.assertFalse(self.page.locator('#studioCommandDialog').evaluate('(e)=>e.open'))
                self.assertTrue(self.page.locator('main').evaluate('(e)=>e===document.activeElement'))
                if width == 390:
                    toggle = self.page.locator('#studioNavToggle')
                    toggle.focus(); self.page.keyboard.press('Enter')
                    self.assertEqual('true', toggle.get_attribute('aria-expanded'))
                    self.assertEqual('/spoken-briefs.html', self.page.evaluate('document.activeElement.getAttribute("href")'))
                    self.page.keyboard.press('Escape')
                    self.assertEqual('false', toggle.get_attribute('aria-expanded'))
                    self.assertTrue(toggle.evaluate('(e)=>e===document.activeElement'))
                    self.assertTrue(self.page.locator('.studio-sidebar').evaluate('(e)=>e.inert'))
        self.assertFalse(any(method == 'POST' for method, _ in self.traffic))
        self.assert_no_inference()

    def test_spoken_shell_and_inspected_archive_fit_desktop_and_mobile(self):
        for width in (1280, 390):
            with self.subTest(width=width):
                self.page.set_viewport_size({'width': width, 'height': 900})
                self.page.goto(self.origin + '/spoken-briefs.html')
                self.assert_shell_destination()
                self.inspect()
                self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width)
                for selector in ('main', '.studio-globalbar', '.layout>aside', '#archivePanel', '#archiveList', '#player', '.table-wrap', '#reviewForm'):
                    bounds = self.page.locator(selector).bounding_box()
                    self.assertIsNotNone(bounds, selector)
                    self.assertGreaterEqual(bounds['x'], 0, selector)
                    self.assertLessEqual(bounds['x'] + bounds['width'], width + 1, selector)
                self.assertGreaterEqual(self.page.locator('#rate').bounding_box()['width'], 60,
                                        'The playback-speed field must remain readable beside its label')
                self.assertTrue(self.page.locator('#player').evaluate('(a)=>a.paused && !a.autoplay && !a.currentTime'))
                output = os.environ.get('SPOKEN_BROWSER_SCREENSHOT')
                if output:
                    target = Path(output).with_name('spoken-shell-%d.png' % width)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    evidence_screenshot(self.page, path=str(target), full_page=True)
        self.assertFalse(any(method == 'POST' for method, _ in self.traffic))
        self.assert_no_inference()

    def test_native_voice_failure_disables_prepare_until_explicit_refresh(self):
        for width in (1280, 390):
            with self.subTest(width=width):
                self.page.set_viewport_size({'width': width, 'height': 900})
                self.page.route('**/api/voice-baseline', lambda route: route.fulfill(
                    status=503, content_type='text/html', body='<!doctype html>Unavailable'))
                self.page.goto(self.origin + '/voice.html')
                self.page.wait_for_function("document.querySelector('#voiceStatus').textContent.length > 0")
                self.assertTrue(self.page.locator('#voicePrepare').is_disabled())
                self.assertIn('unavailable', self.page.locator('#voiceStatus').inner_text().lower())
                self.assertIn('unavailable', self.page.locator('#voiceTakes').inner_text().lower())
                self.page.unroute('**/api/voice-baseline')
                self.page.route('**/api/voice-baseline', lambda route: route.fulfill(
                    json={'capabilities': {'configured': True}, 'projects': []}))
                self.page.locator('#voiceRefresh').click()
                self.page.wait_for_function("!document.querySelector('#voicePrepare').disabled")
                self.page.unroute('**/api/voice-baseline')
        self.assertFalse(any(method == 'POST' for method, _ in self.traffic))
        self.assert_no_inference()

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
        self.inspect(); self.load_audio(); save_playback(self.f.directory, sample=11)
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
            Path(output).parent.mkdir(parents=True, exist_ok=True); evidence_screenshot(self.page, path=output, full_page=True)
        self.assert_no_inference()

    def test_failure_on_inspect_hides_stale_player_without_sending_writes(self):
        self.inspect(); (self.f.directory / 'receipt.json').write_text('{}', encoding='utf-8')
        self.page.locator('#inspect').click(); self.page.wait_for_function("document.querySelector('#status').textContent !== 'Verifying the retained archive and its actual PCM samples…'")
        self.assertTrue(self.page.locator('#archivePanel').is_hidden())
        self.assertFalse(any(m == 'POST' for m, _ in self.traffic))
        self.assert_no_inference()


    def test_unloaded_audio_cannot_save_a_bookmark_but_can_receive_a_review(self):
        self.inspect()
        self.assertTrue(self.page.locator('#savePosition').is_disabled())
        self.assertFalse(self.page.locator('#saveReview').is_disabled())
        self.load_audio()
        self.page.wait_for_function('!document.querySelector("#savePosition").disabled')
        self.assertFalse(any(method == 'POST' for method, _ in self.traffic))
        self.assert_no_inference()

    def test_report_selection_clears_previous_evidence_without_implicit_load(self):
        self.inspect(); self.page.locator('#reportList').select_option(self.report_id)
        self.page.locator('#loadReport').click()
        self.page.wait_for_function("!document.querySelector('#linkReport').disabled")
        self.page.locator('#linkReport').check()
        before = list(self.traffic)
        self.page.locator('#reportList').select_option('')
        self.assertTrue(self.page.locator('#linkReport').is_disabled())
        self.assertFalse(self.page.locator('#linkReport').is_checked())
        self.page.get_by_text('Exact report, observations, and normalization', exact=True).click()
        self.assertEqual('No report selected.', self.page.locator('#reportDetail').inner_text())
        self.assertEqual('No machine report selected.', self.page.locator('#machineSummary').inner_text())
        self.assertEqual(before, self.traffic)
        self.assert_no_inference()

    def test_owner_selection_clears_displayed_judgement_not_saved_record(self):
        self.inspect(); self.page.locator('#reason').fill('A separate retained owner finding.')
        self.page.locator('#decision').select_option('keep'); self.page.locator('#saveReview').click()
        self.page.wait_for_function("document.querySelector('#status').textContent.includes('Listening review saved')")
        review = next((self.f.directory / 'qa/reviews').glob('*.json')); original = review.read_bytes()
        self.page.locator('#reviewList').select_option(review.stem); self.page.locator('#loadReview').click()
        self.page.wait_for_function("document.querySelector('#humanSummary').textContent.includes('keep')")
        self.page.locator('#reviewList').select_option('')
        self.page.get_by_text('Exact owner record', exact=True).click()
        self.assertEqual('No record selected.', self.page.locator('#reviewDetail').inner_text())
        self.assertIn('Unreviewed', self.page.locator('#humanSummary').inner_text())
        self.assertEqual(original, review.read_bytes())
        self.assert_no_inference()

    def test_overlapping_successful_bookmark_requires_a_new_inspection(self):
        from studio_spoken.core import ArchiveAccess
        self.inspect(); self.load_audio()
        self.page.locator('#player').evaluate('(a)=>{a.currentTime=0.01;}')
        self.page.wait_for_function('!document.querySelector("#savePosition").disabled')
        entered = threading.Event(); release = threading.Event(); original = ArchiveAccess.bookmark
        def delayed(access, key, value):
            entered.set()
            if not release.wait(8): raise AssertionError('Test did not release its owned bookmark request')
            return original(access, key, value)
        with patch.object(ArchiveAccess, 'bookmark', delayed):
            try:
                self.page.locator('#savePosition').click()
                self.assertTrue(entered.wait(3))
                self.page.locator('#inspect').click()
                self.page.locator('#archivePanel').wait_for(state='visible')
                release.set()
                self.page.wait_for_function("document.querySelector('#status').textContent.includes('Bookmark saved')")
                self.assertTrue(self.page.locator('#saveReview').is_disabled())
                self.assertEqual(1, len([method for method, _ in self.traffic if method == 'POST']))
                self.page.locator('#inspect').click()
                self.page.locator('#archivePanel').wait_for(state='visible')
                self.assertFalse(self.page.locator('#saveReview').is_disabled())
                self.assertIn('480 samples', self.page.locator('#savedPosition').inner_text())
            finally: release.set()
        self.assert_no_inference()


if __name__ == '__main__': unittest.main(verbosity=2)
