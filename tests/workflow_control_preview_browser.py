"""Real Chromium DOM/keyboard with shipped panel and real planner; synthetic editor/I/O.

No navigation policy is changed. set_content supplies an isolated page, and a
Python binding calls the ordinary planner using synthetic installed schemas.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import sys
import unittest
from playwright.sync_api import sync_playwright, expect
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from studio_workflow.core import catalog
from studio_workflow.control_preview import preview
from test_workflow_control_preview import fixture
BROWSER = None
OUT = None
SCRIPT = ROOT / 'app/static/workflow-control-preview.js'
CSS = ROOT / 'app/static/workflow-control-preview.css'


class ControlPreviewBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(**({'executable_path':BROWSER} if BROWSER else {}))
    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop()
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), 'The interactive control-preview panel is missing')
        self.context = self.browser.new_context(reduced_motion='reduce')
        self.page = self.context.new_page(); self.page.set_default_timeout(3000)
        self.errors, self.requests = [], []
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))
        self.page.route('**/*', lambda route: (self.errors.append('Unexpected network request'),route.abort()))
        self.value, self.info = fixture(); self.original = None
        self.page.expose_function('fixturePreview', self.answer)
        self.addCleanup(self.close)
    def close(self):
        try:
            self.assertEqual(self.errors, [])
            if OUT:
                OUT.mkdir(parents=True,exist_ok=True)
                (OUT/(self._testMethodName+'.json')).write_text(json.dumps({
                    'fixture':'real-dom/synthetic-editor/real-planner', 'calls':len(self.requests),
                    'page_errors':self.errors, 'model_calls':0, 'workspace_writes':0,
                },indent=2)+'\n',encoding='utf-8')
        finally: self.context.close()
    def answer(self, value):
        self.requests.append(copy.deepcopy(value)); return preview(value,self.info,'primary')
    def open(self):
        self.original = copy.deepcopy(self.value['document'])
        self.page.set_content('''<!doctype html><html lang="en"><meta charset="utf-8"><title>Control preview</title>
<style>body{margin:12px;font-family:sans-serif}button,input,select,textarea{font:inherit}button{padding:6px}*{box-sizing:border-box}</style>
<main><section id="builder"><h1>Workflow builder fixture</h1><div class="wf-toolbar"></div></section>
<button id="elsewhere">Other work</button></main></html>''')
        if CSS.exists(): self.page.add_style_tag(content=CSS.read_text(encoding='utf-8'))
        self.page.evaluate('''({doc,schema})=>{
          window.fixtureDoc=doc;window.fixtureSchema=schema;window.fixtureEpoch=0;
          window.fixtureMode='normal';window.fixtureSent=[];window.fixtureNetwork=0;
          window.WorkflowStudio=Object.freeze({snapshot:()=>structuredClone(fixtureDoc),
            schema:()=>structuredClone(fixtureSchema),epoch:()=>fixtureEpoch,
            change:()=>{throw Error('Preview attempted a document write')},load:()=>{throw Error('Preview attempted a load')}});
          window.fetch=async(path,options)=>{
            fixtureNetwork++;if(path!=='/api/workflow-studio/control-preview'||options.method!=='POST')throw Error('Unexpected route');
            const request=JSON.parse(options.body);fixtureSent.push(request);
            const result=await fixturePreview(request);
            if(fixtureMode==='hold')await new Promise(resolve=>window.releasePreview=resolve);
            if(fixtureMode==='wrong-target')result.targets[0].node='not-requested';
            if(fixtureMode==='wrong-commands')result.commands[0].value=999;
            if(fixtureMode==='error')return new Response(JSON.stringify({error:'Fixture offline'}),{status:503});
            if(fixtureMode==='oversize')return new Response('x'.repeat(1048577));
            return new Response(JSON.stringify(result),{headers:{'Content-Type':'application/json'}});
          };
        }''', {'doc':self.value['document'],'schema':catalog(self.info,'primary')})
        self.page.add_script_tag(content=SCRIPT.read_text(encoding='utf-8'))
        self.page.locator('#controlPreviewPanel > summary').click()
    def add(self, node='a'):
        self.page.locator('#controlTargetNode').select_option(node)
        self.page.locator('#controlTargetInput').select_option('value')
        self.page.locator('#controlAddTarget').click()
    def propose(self, text='12'):
        self.page.locator('#controlProposedValue').fill(text)
        self.page.locator('#controlPreviewButton').click()
    def state(self, state):
        expect(self.page.locator('#controlPreviewResult')).to_have_attribute('data-state',state)
    def test_mount_target_selection_and_removal_are_local_only(self):
        self.open();self.assertEqual(self.requests,[]);self.add();self.add('b')
        self.page.get_by_role('button',name='Remove target a.value',exact=True).click()
        self.assertEqual(self.requests,[])
        self.assertEqual(self.page.evaluate('fixtureDoc'),self.original)
    def test_integer_preview_matches_sdk_shape_and_never_writes_the_draft(self):
        self.open();self.add();self.add('b');self.propose();self.state('ready')
        expect(self.page.locator('#controlPreviewResult')).to_contain_text('Mixed current values')
        expect(self.page.locator('#controlPreviewResult')).to_contain_text('a.value')
        self.assertEqual(len(self.requests),1)
        self.assertEqual(self.requests[0]['control']['targets'],self.value['control']['targets'])
        self.assertEqual(self.requests[0]['value'],12)
        self.assertEqual(self.page.evaluate('fixtureDoc'),self.original)
    def test_blocked_range_produces_visible_diagnostics_not_partial_commands(self):
        self.info['Finish']['input']['required']['value'][1]['max']=10
        self.value['document']['schema_sha256']=catalog(self.info,'primary')['schema_sha256']
        self.open();self.add();self.add('b');self.propose();self.state('blocked')
        expect(self.page.locator('#controlPreviewResult')).to_contain_text('outside')
        expect(self.page.locator('#controlPreviewResult')).to_contain_text('No commands proposed')
    def test_schema_declared_wide_bound_does_not_refuse_an_in_range_proposal(self):
        """A seed's installed max is 0xffffffffffffffff. The reply echoes that bound, so guarding the
        whole reply with the safe-integer rule refused every valid proposal for such an input."""
        self.info['Finish']['input']['required']['value'][1]['max']=18446744073709551615
        self.value['document']['schema_sha256']=catalog(self.info,'primary')['schema_sha256']
        self.open();self.add('b');self.propose();self.state('ready')
        expect(self.page.locator('#controlPreviewResult')).to_contain_text('1 proposed input changes')
        self.assertEqual(self.requests[-1]['value'],12)
        self.assertEqual(self.page.evaluate('fixtureDoc'),self.original)

    def test_duplicate_target_is_explained_without_adding_or_posting(self):
        self.open();self.add();self.add()
        expect(self.page.locator('#controlPreviewStatus')).to_contain_text('already')
        self.assertEqual(self.page.locator('#controlTargets li').count(),1)
        self.assertEqual(self.requests,[])
    def test_late_response_cannot_replace_newer_draft_evidence_or_focus(self):
        self.open();self.add();self.page.evaluate("fixtureMode='hold'");self.propose()
        self.page.wait_for_function("typeof releasePreview==='function'")
        self.page.locator('#elsewhere').focus()
        self.page.evaluate("fixtureDoc.nodes.a.inputs.value=33;fixtureEpoch++;document.dispatchEvent(new Event('workflow:render'));releasePreview()")
        self.page.wait_for_timeout(100)
        self.state('stale');expect(self.page.locator('#elsewhere')).to_be_focused()
        self.assertEqual(self.page.evaluate('fixtureDoc.nodes.a.inputs.value'),33)
        self.assertEqual(len(self.requests),1)
    def test_changed_proposal_invalidates_old_reply_without_retry(self):
        self.open();self.add();self.page.evaluate("fixtureMode='hold'");self.propose()
        self.page.wait_for_function("typeof releasePreview==='function'")
        self.page.locator('#controlProposedValue').fill('17')
        self.page.evaluate('releasePreview()');self.page.wait_for_timeout(100)
        self.state('stale');self.assertEqual(len(self.requests),1)
    def test_unsafe_integer_and_wide_draft_refuse_before_transport(self):
        self.open();self.add();self.propose('18446744073709551615')
        expect(self.page.locator('#controlPreviewStatus')).to_contain_text('safe integer')
        self.assertEqual(self.requests,[])
        self.page.evaluate('fixtureDoc.nodes.b.inputs.value=18446744073709551615')
        self.propose('12')
        expect(self.page.locator('#controlPreviewStatus')).to_contain_text('safe integer')
        self.assertEqual(self.requests,[])
    def test_checkbox_preserves_literal_type(self):
        self.value,self.info=fixture('BOOLEAN');self.open();self.add()
        self.page.locator('#controlProposedValue').check();self.page.locator('#controlPreviewButton').click();self.state('ready')
        self.assertIs(self.requests[-1]['value'],True)

    def test_multiline_text_preserves_exact_wording(self):
        self.value,self.info=fixture('STRING');self.open();self.add();self.propose('first line\nsecond line')
        self.state('ready');self.assertEqual(self.requests[-1]['value'],'first line\nsecond line')
    def test_combo_preserves_boolean_vs_integer_choice(self):
        self.value,self.info=fixture(first=[[True,1,'1']],second=[[True,1,'1']]);self.open();self.add();self.add('b')
        self.page.locator('#controlProposedValue').select_option('0');self.page.locator('#controlPreviewButton').click();self.state('ready')
        self.assertIs(self.requests[-1]['value'],True)
    def test_http_failure_is_explicit_and_never_retried(self):
        self.open();self.add();self.page.evaluate("fixtureMode='error'");self.propose()
        expect(self.page.locator('#controlPreviewStatus')).to_contain_text('Fixture offline')
        self.page.wait_for_timeout(200);self.assertEqual(len(self.requests),1)
        self.assertEqual(self.page.evaluate('fixtureDoc'),self.original)
    def test_oversized_reply_is_refused_without_retaining_partial_output(self):
        self.open();self.add();self.page.evaluate("fixtureMode='oversize'");self.propose()
        expect(self.page.locator('#controlPreviewStatus')).to_contain_text('1 MiB')
        self.assertEqual(self.page.locator('#controlPreviewResult [data-target]').count(),0)
    def test_document_replacement_clears_proposal_targets_and_old_results(self):
        self.open();self.add();self.propose();self.state('ready')
        self.page.evaluate("fixtureEpoch++;document.dispatchEvent(new Event('workflow:replace'));document.dispatchEvent(new Event('workflow:render'))")
        self.assertEqual(self.page.locator('#controlTargets li').count(),0)
        expect(self.page.locator('#controlPreviewButton')).to_be_disabled();self.state('stale')
    def test_hostile_labels_render_as_text_and_keyboard_preview_works(self):
        self.info['Source']['display_name']='<img src=x onerror=alert(1)>'
        self.value['document']['schema_sha256']=catalog(self.info,'primary')['schema_sha256']
        self.open();self.page.locator('#controlTargetNode').select_option('a')
        self.page.locator('#controlAddTarget').focus();self.page.keyboard.press('Enter')
        self.page.locator('#controlName').fill('<script>alert(1)</script>')
        self.page.locator('#controlProposedValue').fill('12')
        self.page.locator('#controlPreviewButton').focus();self.page.keyboard.press('Enter');self.state('ready')
        self.assertEqual(self.page.locator('#controlPreviewPanel img, #controlPreviewPanel script').count(),0)
    def test_mismatched_target_rows_and_commands_are_not_displayed_as_ready(self):
        self.open();self.add()
        for mode in ('wrong-target','wrong-commands'):
            self.page.evaluate('(mode)=>fixtureMode=mode',mode);self.propose()
            expect(self.page.locator('#controlPreviewStatus')).to_contain_text('incompatible')
            self.state('error')

    def test_wide_enum_option_refuses_instead_of_displaying_rounded_digits(self):
        self.value,self.info=fixture(first=[[2**64-1,'safe']],second=[[2**64-1,'safe']])
        self.open();self.add()
        expect(self.page.locator('#controlPreviewPanel')).to_contain_text('safe integer')
        expect(self.page.locator('#controlPreviewButton')).to_be_disabled()
        self.assertEqual(self.requests,[])

    def test_schema_refresh_updates_enum_editor_without_auto_preview(self):
        self.value,self.info=fixture(first=[['old']],second=[['old']]);self.open();self.add()
        self.page.evaluate("fixtureSchema.nodes.Source.inputs[0].options.options=['new'];document.dispatchEvent(new Event('workflow:render'))")
        expect(self.page.locator('#controlProposedValue option')).to_have_text(['"new"'])
        self.assertEqual(self.requests,[])

    def test_removing_unsupported_first_target_enables_remaining_scalar_preview(self):
        self.value,self.info=fixture(first=['COLOR',{'default':'#000000'}]);self.open();self.add();self.add('b')
        expect(self.page.locator('#controlPreviewButton')).to_be_disabled()
        self.page.get_by_role('button',name='Remove target a.value',exact=True).click()
        expect(self.page.locator('#controlPreviewButton')).to_be_enabled()
        self.propose();self.state('ready')

    def test_narrow_and_zoomed_panel_has_no_horizontal_page_overflow(self):
        self.open();self.add();self.add('b');self.propose();self.state('ready')
        for width,zoom in ((390,'1'),(1280,'2')):
            self.page.set_viewport_size({'width':width,'height':900})
            self.page.evaluate('(zoom)=>document.body.style.zoom=zoom',zoom)
            expect(self.page.locator('#controlPreviewButton')).to_be_visible()
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
        if OUT:self.page.screenshot(path=str(OUT/'control-preview-zoom.png'),full_page=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('--browser-path');parser.add_argument('--out',type=Path)
    args,rest=parser.parse_known_args();BROWSER,OUT=args.browser_path,args.out
    if OUT:OUT.mkdir(parents=True,exist_ok=True)
    unittest.main(argv=[__file__,*rest])
