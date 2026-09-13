"""Opt-in isolated Chromium component test; no installed Studio or Comfy backend.

Uses actual run-panel scripts/CSS, fixture shell styling/storage/transport, and
real Python projection/ticket journaling against the fake runtime used in tests.
This does not prove native browser-origin persistence or the complete Studio shell.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from test_workflow_preset_adapter import Runtime, GRAPH, INFO
from studio_workflow.core import catalog, new_document
from studio_workflow.preset_adapter import prepare_document
from studio_workflow.execution import run_ticket


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium', default='/usr/bin/chromium')
    parser.add_argument('--out', type=Path, default=ROOT / '.runtime/workflow-execution-browser')
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory() as folder, sync_playwright() as playwright:
        studio = Runtime(folder); doc = new_document(GRAPH, catalog(INFO, 'primary'), 'Illustration lighting study')
        doc['nodes']['3']['inputs'].update(text='An adult lanternkeeper in a warm evening street', steps=28, seed=20260913)
        calls = []
        def request(path, payload):
            calls.append(path)
            if path.endswith('/prepare-document'): result = prepare_document(studio, payload['document'], payload['preset_id'])
            elif path.endswith('/run'): result = run_ticket(studio, payload['ticket'], payload['approved'])
            elif path.startswith('/api/jobs/'):
                job = studio.jobs[path.rsplit('/', 1)[-1]]; job['status'] = 'completed'; result = studio.public(job)
            else: raise AssertionError('Unexpected route: ' + path)
            return result
        browser = playwright.chromium.launch(executable_path=args.chromium, headless=True, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1200, 'height': 940})
        errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('dialog', lambda dialog: dialog.accept())
        page.expose_function('fixtureRequest', request)
        page.set_content('''<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>
        :root{--wf-accent:#baffb9;color-scheme:dark}*{box-sizing:border-box}body{background:#10141b;color:#edf2f7;font:15px/1.55 system-ui;margin:0}main{max-width:1050px;margin:auto;padding:28px}h1{font-size:32px}h3{font-size:20px}p{color:#b6c4d5}.wf-panel{background:#181f29;border:1px solid #334254;border-radius:12px;padding:20px;min-width:0}.wf-toolbar{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}button,select{font:inherit;min-height:44px;padding:10px 14px;border:1px solid #334254;border-radius:8px;background:#121922;color:inherit;max-width:100%}button:disabled{opacity:.45}pre{background:#10161d;border-radius:8px;padding:16px}label{display:grid;gap:8px}button:focus-visible,select:focus-visible{outline:3px solid #baffb9;outline-offset:3px}@media(max-width:600px){main{padding:16px}}
        </style></head><body><main><small>WORKFLOW STUDIO · ISOLATED COMPONENT FIXTURE</small><h1>Review your next run</h1><section id="builder"><label>Registered recipe<select id="presetChoice"><option value="example">Example image recipe · synthetic test nodes</option></select></label></section></main></body></html>''')
        page.add_style_tag(content=(ROOT / 'app/static/workflow-execution.css').read_text())
        page.evaluate('''doc => {
          window.fixtureDoc = doc; window.fixtureEpoch = 1;
          window.WorkflowStudio = {snapshot: () => structuredClone(fixtureDoc), epoch: () => fixtureEpoch,
            schema: () => ({backend_id:doc.backend_id,schema_sha256:doc.schema_sha256}), validate: () => {}};
          const storage = new Map(); Object.defineProperty(window, 'sessionStorage', {value: {
            getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)}});
          window.fetch = async (path, options) => ({ok:true,json:async()=>fixtureRequest(path, options?.body?JSON.parse(options.body):null)});
        }''', doc)
        for filename in ('workflow-ticket-state.js', 'workflow-execution.js'):
            page.add_script_tag(content=(ROOT / 'app/static' / filename).read_text())
        assert not calls, calls
        page.get_by_role('button', name='Prepare run ticket', exact=True).click()
        page.wait_for_function("document.querySelector('#runWorkflowTicket').disabled === false")
        assert not studio.jobs
        page.screenshot(path=str(args.out / 'workflow-run-desktop.png'), full_page=True)
        page.set_viewport_size({'width':390, 'height':1100})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Horizontal overflow'
        page.screenshot(path=str(args.out / 'workflow-run-mobile.png'), full_page=True)
        page.evaluate("fixtureDoc.name += ' edit'; fixtureEpoch++; document.dispatchEvent(new Event('workflow:render'))")
        assert page.locator('#runWorkflowTicket').is_disabled()
        page.get_by_role('button', name='Clear finished / unsubmitted ticket', exact=True).click()
        page.get_by_role('button', name='Prepare run ticket', exact=True).click()
        page.wait_for_function("document.querySelector('#runWorkflowTicket').disabled === false")
        page.get_by_role('button', name='Run prepared recipe', exact=True).click()
        page.wait_for_function("document.querySelector('#workflowRunStatus').textContent.includes('queued')")
        page.get_by_role('button', name='Recover same request', exact=True).click()
        page.wait_for_function("document.querySelector('#observeWorkflowTicket').disabled === false")
        assert studio.calls == 1, 'Repeated ticket dispatched again'
        page.get_by_role('button', name='Observe job', exact=True).click()
        page.wait_for_function("document.querySelector('#clearWorkflowTicket').disabled === false")
        page.get_by_role('button', name='Clear finished / unsubmitted ticket', exact=True).click()
        assert not errors, errors
        print(json.dumps({'fixture_requests':calls, 'fake_job_creations':studio.calls, 'browser_errors':errors,
                          'model_submissions':0, 'source':'isolated component; fixture storage/transport/shell'}))
        browser.close()


if __name__ == '__main__': main()
