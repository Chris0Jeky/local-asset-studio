"""Native renderer checks of production dashboard/library seams; no HTTP or generation."""
from pathlib import Path
import unittest

import workshop_entry_points as entry
from bundle_browser_smoke import HTML as BUNDLE_HTML

ROOT = Path(__file__).resolve().parents[1]


def source(name):
    return (ROOT / 'app/static' / name).read_text(encoding='utf-8')


def region(text, start, end):
    return text[text.index(start):text.index(end, text.index(start))]


class DailyJourneys(entry.EntryPoints):
    def test_home_bundle_launcher_reuses_the_explorer_without_mutations(self):
        html = BUNDLE_HTML.replace('<main>', '<main><section id="homeView"><div class="ux-home-heading">Overview</div></section>')
        html = html.replace('<link rel="stylesheet" href="/app/static/bundle-explorer.css">', '<style>'+source('bundle-explorer.css')+'</style>')
        for name in ('bundle-core.js', 'bundle-explorer.js'):
            html = html.replace('<script src="/app/static/'+name+'"></script>', entry.script(name))
        for width in (1440, 390):
            with self.subTest(width=width):
                self.page.set_viewport_size({'width': width, 'height': 900})
                self.page.goto('about:blank')
                self.page.set_content(html)
                self.assertEqual(self.page.locator('#bundleHomeLauncher').count(), 1)
                self.assertTrue(self.page.locator('#bundleHomeLauncher').is_visible())
                self.page.click('#bundleHomeLauncher')
                self.assertEqual(self.page.locator('#bundleExplorer').count(), 1)
                self.assertTrue(self.page.locator('#bundleSearch').evaluate('(n)=>n===document.activeElement'))
                self.page.keyboard.press('Escape')
                self.page.wait_for_function('!document.querySelector("#bundleExplorer").open')
                self.assertTrue(self.page.locator('#bundleHomeLauncher').evaluate('(n)=>n===document.activeElement'))
                self.assertEqual(self.page.evaluate('calls'), [])

    def test_empty_results_explain_generate_import_and_continue(self):
        render = region(source('app.js'), 'function renderJobs(', '\nasync function refreshJobs')
        self.page.set_content('<div id="gallery"></div><div id="jobProblemsHost"></div><script>const $=s=>document.querySelector(s);let jobs=[],jobsSignature=null;function renderCompare(){}'+render+';renderJobs();</script>')
        copy = self.page.locator('#gallery').inner_text()
        self.assertIn('Generate', copy)
        self.assertIn('import', copy)
        self.assertIn('Continue with this', copy)
        self.assertEqual(self.page.locator('#gallery a').get_attribute('href'), '/#assets')

    def load_picker(self):
        production = region(source('studio-workbench.js'), '  // Pull any existing image', '  // Drafts are data only')
        self.page.set_content('''<button id="uxPullAsset">Pull from library</button><script>
const q=s=>document.querySelector(s),escape=v=>String(v);
function element(tag,cls){const n=document.createElement(tag);n.className=cls;return n;}
let selected={reference:true},referenceRecords=[],selectionEpoch=0,view='create',pickerBusy=false,pickerLoading=false,sourcePickerEpoch=0;
let assetState={assets:[{id:'old',title:'Cached old image',tags:[],media_type:'image'}]};
const takesSource=()=>!!selected.reference,NO_SOURCE_SLOT='Choose a reference recipe';
function announce(){}function after(){}function syncReady(){}function assetPreview(){return '';}
window.pending=[];function refreshAssets(){return new Promise(resolve=>pending.push(resolve));}
</script><script>'''+production+'</script>')

    def test_library_opens_immediately_and_refuses_failed_cached_results(self):
        self.load_picker()
        self.page.click('#uxPullAsset')
        self.assertTrue(self.page.locator('#uxSourcePicker').is_visible())
        self.assertIn('Loading', self.page.locator('#uxPickerStatus').inner_text())
        self.assertEqual(self.page.locator('[data-ux-pull]').count(), 0)
        self.page.evaluate('pending.shift()(false)')
        self.page.wait_for_function('!pickerLoading')
        self.assertIn('reopen', self.page.locator('#uxPickerStatus').inner_text())
        self.assertEqual(self.page.locator('[data-ux-pull]').count(), 0)

    def test_cancelled_library_read_cannot_reopen_or_fill_a_new_picker(self):
        self.load_picker()
        self.page.click('#uxPullAsset')
        self.page.keyboard.press('Escape')
        self.page.wait_for_function('!picker.open')
        self.page.click('#uxPullAsset')
        self.page.evaluate('pending.shift()(true)')
        self.assertEqual(self.page.locator('[data-ux-pull]').count(), 0)
        self.page.evaluate('pending.shift()(true)')
        self.page.wait_for_selector('[data-ux-pull]')
        self.assertEqual(self.page.locator('[data-ux-pull]').count(), 1)
        self.page.keyboard.press('Escape')
        self.page.wait_for_function('!picker.open')

    def test_failed_job_inspector_is_specific_escaped_and_read_only(self):
        inspect = region(source('studio-workbench.js'), '  function inspectJob(', '  async function refreshHome(')
        self.page.set_content('''<button id="origin">Inspect job</button><dialog id="uxJobInspector" class="studio-dialog"></dialog><script>
const q=s=>document.querySelector(s),escape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const U={failureDetails:()=>({summary:'Memory allocation failed',action:'Try a smaller canvas',detail:'engine detail'})};
let homeData={jobs:[{id:'failed-one',preset_name:'<img src=x onerror=alert(1)>',status:'failed',message:'No memory',prompt_ids:['retained-prompt'],recipe:{controls:{positive:'original wording'}}}]};
let homeUpdated=new Date(),jobInspector=document.querySelector('#uxJobInspector');function announce(){};
</script><script>'''+inspect+'''document.querySelector('#origin').onclick=()=>inspectJob('failed-one');</script>''')
        self.page.click('#origin')
        self.assertIn('failed-one', self.page.locator('#uxJobInspector').inner_text())
        self.assertIn('retained-prompt', self.page.locator('#uxJobInspector').inner_text())
        self.assertIn('Try a smaller canvas', self.page.locator('#uxJobInspector').inner_text())
        self.assertEqual(self.page.locator('#uxJobInspector img').count(), 0)
        self.assertEqual(self.page.locator('#uxJobInspector button').count(), 1)
        self.page.keyboard.press('Escape')
        self.page.wait_for_function('!jobInspector.open')
        self.assertTrue(self.page.locator('#origin').evaluate('(n)=>n===document.activeElement'))

    def test_workspace_refresh_reports_success_failure_and_busy(self):
        refresh = region(source('workspace.js'), 'async function refreshAssets(', '// Scope, filters')
        self.page.set_content('''<script>
let assetRefreshing=false,assetState={workspace_id:'old'},assetSignature='',jobsSignature='';
const assetSelection=new Set();let assetLibraryPending=null;
function renderLibraryRecovery(){}function renderAssets(){}function renderJobs(){}function assetMessage(){};
window.pending=[];function api(){return new Promise((resolve,reject)=>pending.push({resolve,reject}));}
</script><script>'''+refresh+'</script>')
        self.page.evaluate('()=>{window.first=refreshAssets()}')
        self.assertFalse(self.page.evaluate('refreshAssets()'))
        self.page.evaluate("pending.shift().reject(Error('offline'))")
        self.assertFalse(self.page.evaluate('first'))
        self.assertEqual(self.page.evaluate('assetState.workspace_id'), 'old')
        self.page.evaluate('()=>{window.second=refreshAssets()}')
        self.page.evaluate("pending.shift().resolve({workspace_id:'new'})")
        self.assertTrue(self.page.evaluate('second'))
        self.assertEqual(self.page.evaluate('assetState.workspace_id'), 'new')


if __name__ == '__main__':
    unittest.main(verbosity=2)
