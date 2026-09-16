"""Real Chromium regression of shipped coach scripts on a synthetic, network-isolated page.

No Studio service, user workspace or model is contacted. The existing full-page
journey driver remains the integration gate; this fixture isolates disclosure
ownership, including native details layout and keyboard default actions.
Location, history and manifest reads are in-memory seams, not native navigation.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import unittest
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BROWSER = None
OUT = None
HTML = '''<!doctype html><html lang="en"><meta charset="utf-8">
<title>Guide disclosure fixture</title><style>
body { font-family: sans-serif; margin: 12px; } button, summary { margin: 4px; }
main { max-width: 700px; } [hidden] { display: none !important; }
</style><main>
<button id="elsewhere">Keep working here</button>
<div id="hiddenView" hidden><details id="hiddenPanel"><summary>Other tool</summary>
<button id="hiddenTarget">Unavailable action</button></details></div>
<details id="outer"><summary>Headless and agents</summary>
<details id="inner"><summary>Commands</summary><button id="target">Run explicitly</button>
</details></details></main>
<script>window.activations=0; document.getElementById('target').onclick=()=>window.activations++;</script>
</html>'''


class DisclosureBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(**({'executable_path': BROWSER} if BROWSER else {}))

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.context = self.browser.new_context(reduced_motion='reduce')
        self.page = self.context.new_page()
        self.page.set_default_timeout(3000)
        self.errors, self.requests = [], []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.route('**/*', lambda route: (self.errors.append('Unexpected network request'), route.abort()))

    def tearDown(self):
        try:
            self.requests = self.page.evaluate('window.fixtureRequests || []')
            self.assertEqual(self.errors, [])
            self.assertTrue(all(method == 'GET' for method, _ in self.requests), self.requests)
            self.assertEqual(self.page.evaluate('window.activations'), 0, 'The guide activated an action')
            if OUT:
                OUT.mkdir(parents=True, exist_ok=True)
                (OUT / (self._testMethodName + '.json')).write_text(json.dumps({
                    'fixture': 'synthetic-page/shipped-guide-scripts', 'requests': self.requests,
                    'page_errors': self.errors, 'activations': self.page.evaluate('window.activations'),
                }, indent=2) + '\n', encoding='utf-8')
        finally:
            self.context.close()

    def open(self, target='#target', alternatives=(), hidden=False):
        manifest = {'guides': [{'id': 'fixture', 'title': 'Inspect headless commands', 'steps': [
            {'id': 'commands', 'title': 'Inspect commands', 'detail': 'Find the command without running it.',
             'route': '/#agents', 'target': target, 'alternatives': list(alternatives), 'check': 'manual'}]}]}
        html = HTML.replace('<details id="outer">', '<details id="outer" hidden>') if hidden else HTML
        # set_content exercises real layout and keyboard events without navigating to
        # a local service. Script bytes are unchanged; only environmental I/O is injected.
        self.page.set_content(html)
        self.page.add_script_tag(content=(ROOT / 'app/static/studio-guide-state.js').read_text(encoding='utf-8'))
        self.page.evaluate("""({source,manifest}) => {
          window.fixtureRequests=[];
          const location=new URL('http://127.0.0.1:8191/?guide=fixture#agents');
          const history={pushState(_s,_t,url){location.href=new URL(url,location).href;},
            replaceState(_s,_t,url){location.href=new URL(url,location).href;}};
          const fetch=async(url, options={})=>{
            window.fixtureRequests.push([options.method || 'GET',url]);
            if ((options.method || 'GET')!=='GET' || url!=='/api/workflow-studio/guides')
              throw Error('Unexpected coach request '+url);
            return {ok:true,text:async()=>JSON.stringify(manifest)};
          };
          new Function('location','history','fetch',source)(location,history,fetch);
        }""", {'source': (ROOT / 'app/static/studio-guide.js').read_text(encoding='utf-8'), 'manifest': manifest})
        expect(self.page.locator('.studio-guide-panel')).to_be_visible()

    def closed(self, name='outer'):
        self.assertFalse(self.page.locator('#' + name).evaluate('(node) => node.open'), name + ' was reopened')

    def test_closed_panel_stays_closed_after_click_recheck_and_debounce(self):
        self.open()
        expect(self.page.locator('#target')).to_be_visible()
        self.page.locator('#outer > summary').click()
        self.closed()
        self.page.locator('#elsewhere').click()
        self.closed()
        self.page.locator('#checkGuideStep').click()
        self.closed()
        self.page.wait_for_timeout(800)
        self.closed()

    def test_explicit_keyboard_show_reopens_nested_panels_without_activation(self):
        self.open()
        self.page.locator('#inner > summary').click()
        self.page.locator('#outer > summary').click()
        self.page.locator('#elsewhere').focus()
        self.page.locator('#elsewhere').press('Space')
        self.closed(); self.closed('inner')
        self.page.locator('#showGuideControl').focus()
        self.page.keyboard.press('Enter')
        expect(self.page.locator('#target')).to_be_visible()
        expect(self.page.locator('#target')).to_be_focused()

    def test_automatic_reveal_never_focuses_an_action(self):
        self.open()
        expect(self.page.locator('#target')).to_be_visible()
        self.assertNotEqual(self.page.evaluate('document.activeElement.id'), 'target')
        self.page.locator('#elsewhere').focus()
        self.page.evaluate("document.dispatchEvent(new CustomEvent('studio:recipe'))")
        expect(self.page.locator('#elsewhere')).to_be_focused()

    def test_delayed_target_gets_one_reveal_when_the_feature_becomes_available(self):
        self.open(hidden=True)
        self.closed(); self.closed('inner')
        self.page.evaluate("document.getElementById('outer').hidden=false; document.dispatchEvent(new CustomEvent('studio:recipe'))")
        expect(self.page.locator('#target')).to_be_visible()
        self.page.locator('#outer > summary').click()
        self.page.evaluate("document.dispatchEvent(new CustomEvent('workflow:render'))")
        self.closed()

    def test_hidden_primary_does_not_open_its_panel_when_an_alternative_is_usable(self):
        self.open(target='#hiddenTarget', alternatives=('#target',))
        expect(self.page.locator('#target')).to_be_visible()
        self.closed('hiddenPanel')
        self.assertTrue(self.page.locator('#hiddenView').evaluate('(node) => node.hidden'))

    def test_css_hidden_candidate_is_not_opened_by_explicit_reveal(self):
        self.open()
        result = self.page.evaluate('''() => {
          const view=document.getElementById('hiddenView'); view.hidden=false; view.style.display='none';
          const panel=document.getElementById('hiddenPanel'); panel.open=false;
          const target=StudioGuideState.revealTarget({target:'#hiddenTarget'},document);
          return {target:target?.id || null, open:panel.open};
        }''')
        self.assertEqual(result, {'target': None, 'open': False})

    def test_peek_is_nonmutating_for_closed_nested_disclosures(self):
        self.open(hidden=True)
        result = self.page.evaluate('''() => {
          document.getElementById('outer').hidden=false;
          document.getElementById('outer').open=false; document.getElementById('inner').open=false;
          return {target:StudioGuideState.peekTarget({target:'#target'},document)?.id || null,
            outer:document.getElementById('outer').open, inner:document.getElementById('inner').open};
        }''')
        self.assertEqual(result, {'target': None, 'outer': False, 'inner': False})

    def test_closed_disclosure_and_its_first_summary_are_visible_targets(self):
        self.open(hidden=True)
        result = self.page.evaluate("""() => {
          const outer=document.getElementById('outer'); outer.hidden=false;
          outer.querySelector(':scope > summary').id='summaryTarget';
          return ['outer','summaryTarget'].map(id => StudioGuideState.peekTarget({target:'#'+id},document)?.id);
        }""")
        self.assertEqual(result, ['outer', 'summaryTarget'])
        self.closed(); self.closed('inner')

    def test_existing_visible_alternative_wins_without_opening_hidden_candidates(self):
        self.open(target='#hiddenTarget', alternatives=('#elsewhere',))
        expect(self.page.locator('#elsewhere')).to_have_class('studio-guide-target')
        self.closed('hiddenPanel'); self.closed(); self.closed('inner')

    def test_unusable_target_restores_only_disclosures_it_opened(self):
        self.open()
        result = self.page.evaluate("""() => {
          const outer=document.getElementById('outer'), inner=document.getElementById('inner');
          outer.open=true; inner.open=false; document.getElementById('target').style.visibility='hidden';
          const found=StudioGuideState.revealTarget({target:'#target'},document);
          return {found:found?.id || null, outer:outer.open, inner:inner.open};
        }""")
        self.assertEqual(result, {'found': None, 'outer': True, 'inner': False})

    def test_narrow_and_zoomed_layout_keep_user_disclosure_choice(self):
        for width, zoom in ((390, '1'), (1280, '2')):
            with self.subTest(width=width, zoom=zoom):
                self.page.set_viewport_size({'width': width, 'height': 900})
                if self.page.locator('.studio-guide-panel').count():
                    self.page.get_by_role('button', name='Pause guide', exact=True).click()
                self.open()
                self.page.evaluate('(zoom) => document.body.style.zoom=zoom', zoom)
                self.page.locator('#outer > summary').click()
                self.page.locator('#elsewhere').click()
                self.closed()
                self.page.locator('#showGuideControl').click()
                expect(self.page.locator('#target')).to_be_visible()

    def test_pause_removes_the_coach_without_revealing_closed_controls(self):
        self.open()
        self.page.locator('#outer > summary').click()
        self.page.get_by_role('button', name='Pause guide', exact=True).click()
        expect(self.page.locator('.studio-guide-panel')).to_have_count(0)
        self.page.locator('#elsewhere').click()
        self.closed()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('--browser-path', help='Use an already installed Chromium binary for this isolated fixture')
    parser.add_argument('--out', type=Path)
    args, rest = parser.parse_known_args()
    BROWSER, OUT = args.browser_path, args.out
    unittest.main(argv=[__file__, *rest])
