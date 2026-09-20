"""Opt-in inert Chromium UI/SQLite smoke; no real Comfy or browser HTTP access.

Uses the actual HTML/CSS/three scripts and shared document service, with synthetic
nodes and a simulated browser transport/storage. Native shell navigation and actual
browser-origin persistence are intentionally not claimed by this fixture.
Run: python tests/workflow_steps_browser.py --chromium /usr/bin/chromium --out DIR
"""
import argparse
import json
from pathlib import Path
import re
import sys
import tempfile
import threading
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).parents[1]))
from studio_workflow.core import catalog, new_document, compile_document
from studio_workflow.document_http import route, PREFIX
from test_workflow_documents import SQLiteWorkspace
from test_workflow_steps import INFO, GRAPH


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--chromium'); parser.add_argument('--out', type=Path, default=Path('.runtime/workflow-steps-browser')); args = parser.parse_args()
    from playwright.sync_api import sync_playwright
    root = Path(__file__).parents[1]; static = root / 'app/static'; args.out.mkdir(parents=True, exist_ok=True)
    schema = catalog(INFO, 'primary'); doc = new_document(GRAPH, schema, 'Processing study')
    with tempfile.TemporaryDirectory() as temp, sync_playwright() as engine:
        studio = SimpleNamespace(assets=SQLiteWorkspace(temp), lock=threading.RLock())
        seen, errors = [], []
        def request(path, body):
            seen.append((path, body))
            try:
                if path == '/api/catalog': result = {'presets': [{'id': 'example', 'name': 'Synthetic processing study'}]}
                elif path.endswith('/guides'): result = {'guides': []}
                elif path.endswith('/nodes') or path.endswith('/nodes/refresh'): result = schema
                elif path.endswith('/presets/example'): result = {'document': doc}
                elif path.endswith('/compile'): result = compile_document(body['document'], schema)
                elif path == PREFIX or path.startswith(PREFIX + '/'): result = route(path, body, studio)
                else: raise ValueError('Unexpected fixture request: ' + path)
                return {'status': 200, 'body': result}
            except Exception as exc:
                return {'status': getattr(exc, 'status', 400), 'body': {'error': str(exc)}}
        kwargs = {'headless': True}
        if args.chromium: kwargs['executable_path'] = args.chromium
        browser = engine.chromium.launch(**kwargs); page = browser.new_page(viewport={'width': 1450, 'height': 1100})
        page.set_default_timeout(8000)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('dialog', lambda dialog: dialog.accept('Refine copy') if dialog.type == 'prompt' else dialog.accept())
        page.expose_function('fixtureRequest', request)
        html = re.sub(r'<script\b[^>]*>.*?</script>|<link\b[^>]*>', '', (static / 'workflow-studio.html').read_text(encoding='utf-8'), flags=re.S)
        page.set_content(html)
        page.evaluate('''() => {
          if (!crypto.randomUUID) { let id=0; Object.defineProperty(crypto,'randomUUID',{value:()=> 'fixture-' + (++id)}); }
          for (const key of ['localStorage','sessionStorage']) {
            const values = new Map(); Object.defineProperty(window,key,{value:{getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)}});
          }
          window.fetch = async (path,options={}) => { const r=await window.fixtureRequest(String(path),options.body?JSON.parse(options.body):null);return {ok:r.status>=200&&r.status<300,status:r.status,json:async()=>r.body}; };
        }''')
        for name in ('workflow-studio.css', 'workflow-projects.css'): page.add_style_tag(content=(static / name).read_text(encoding='utf-8'))
        for name in ('workflow-studio.js', 'workflow-project-state.js', 'workflow-projects.js'): page.add_script_tag(content=(static / name).read_text(encoding='utf-8'))
        page.wait_for_selector('#presetChoice option[value=example]', state='attached')
        assert not any(body is not None for _, body in seen), 'Startup mutated something'
        page.select_option('#presetChoice', 'example'); page.click('#loadPreset')
        page.wait_for_function('window.WorkflowStudio.snapshot()?.nodes["2"]')
        page.click('#createWorkflowStep'); page.get_by_label('Step name', exact=True).fill('Refine')
        page.locator('dialog label').filter(has_text='2 · Scale').locator('input').check()
        page.locator('dialog label').filter(has_text='2.factor').locator('input').check()
        page.get_by_label('2.factor setting label', exact=True).fill('Refinement amount')
        page.get_by_role('button', name='Apply step to draft').click()
        page.wait_for_selector('.wf-step-card')
        page.locator('#workflowSteps input[aria-label=factor]').fill('3.5'); page.locator('#workflowSteps input[aria-label=factor]').press('Tab')
        assert page.evaluate('WorkflowStudio.snapshot().nodes["2"].inputs.factor') == 3.5
        page.click('#saveSharedWorkflow'); page.wait_for_function('document.querySelector("#sharedWorkflowState").textContent.includes("r1 · saved")')
        original = studio._workflow_documents.list()['documents'][0]['id']
        studio._workflow_documents.command(original, {'request_id': 'agent-edit', 'expected_revision': 1, 'commands': [{'op': 'rename', 'name': 'Agent edit'}]})
        page.fill('#workflowName', 'Human local edit'); page.locator('#workflowName').press('Tab'); page.click('#saveSharedWorkflow')
        page.wait_for_function('document.querySelector("#sharedWorkflowStatus").textContent.includes("another window")')
        assert page.evaluate('WorkflowStudio.snapshot().name') == 'Human local edit'
        assert page.locator('#saveSharedWorkflow').is_disabled()
        page.click('#copySharedWorkflow'); page.wait_for_function('document.querySelector("#sharedWorkflowState").textContent.includes("r1 · saved")')
        assert len(studio._workflow_documents.list()['documents']) == 2
        page.get_by_role('button', name='Refresh saved', exact=True).click(); page.wait_for_selector(f'#sharedWorkflowChoice option[value="{original}"]', state='attached')
        page.select_option('#sharedWorkflowChoice', original); page.click('#openSharedWorkflow')
        page.wait_for_function('WorkflowStudio.snapshot().name === "Agent edit"')
        page.click('#loadWorkflowHistory'); page.wait_for_selector('#workflowRevisionChoice option[value="1"]', state='attached')
        page.select_option('#workflowRevisionChoice', '1'); page.click('#restoreSharedWorkflow')
        page.wait_for_function('document.querySelector("#sharedWorkflowState").textContent.includes("r3 · saved")')
        assert page.evaluate('WorkflowStudio.snapshot().name') == 'Processing study'
        page.click('#showWorkflowSteps'); page.get_by_role('checkbox', name='Enable step Refine', exact=True).uncheck()
        page.wait_for_function('WorkflowStudio.snapshot().disabled.includes("2")'); page.click('#compileWorkflow')
        page.wait_for_function('document.querySelector("#workflowStatus").textContent.includes("issue(s)")')
        assert page.locator('#workflowDiagnostics').is_visible()
        page.get_by_role('checkbox', name='Enable step Refine', exact=True).check(); page.wait_for_function('!WorkflowStudio.snapshot().disabled.length')
        page.get_by_role('button', name='Duplicate step', exact=True).click(); page.wait_for_function('WorkflowStudio.snapshot().steps.length === 2')
        page.get_by_role('button', name='Duplicate step', exact=True).first.click(); page.wait_for_function('WorkflowStudio.snapshot().steps.length === 3')
        assert page.evaluate('WorkflowStudio.snapshot().outputs') == ['3']
        before_order = page.evaluate('WorkflowStudio.snapshot().steps.map(step => step.id)')
        reordered = [before_order[1], before_order[0], before_order[2]]
        appended = [before_order[1], before_order[2], before_order[0]]
        before_effective = page.evaluate('JSON.stringify((({nodes,outputs,disabled,bypass,positions}) => ({nodes,outputs,disabled,bypass,positions}))(WorkflowStudio.snapshot()))')
        reduce_before = len([1 for route_name, body in seen if route_name == PREFIX + '/reduce'])
        assert page.get_by_role('button', name='Move up', exact=True).first.is_disabled()
        assert not page.get_by_role('button', name='Move down', exact=True).first.is_disabled()
        assert not page.get_by_role('button', name='Move up', exact=True).nth(1).is_disabled()
        assert not page.get_by_role('button', name='Move down', exact=True).nth(1).is_disabled()
        assert not page.get_by_role('button', name='Move up', exact=True).nth(2).is_disabled()
        assert page.get_by_role('button', name='Move down', exact=True).nth(2).is_disabled()
        page.get_by_role('button', name='Move down', exact=True).first.focus(); page.keyboard.press('Enter')
        page.wait_for_function('(expected) => JSON.stringify(WorkflowStudio.snapshot().steps.map(step => step.id)) === JSON.stringify(expected)', arg=reordered)
        assert len([1 for route_name, body in seen if route_name == PREFIX + '/reduce']) == reduce_before + 1
        assert page.evaluate('JSON.stringify((({nodes,outputs,disabled,bypass,positions}) => ({nodes,outputs,disabled,bypass,positions}))(WorkflowStudio.snapshot()))') == before_effective
        focus = page.evaluate('({step:document.activeElement.closest(\"[data-step-id]\")?.dataset.stepId, move:document.activeElement.dataset.stepMove})')
        assert focus == {'step': before_order[0], 'move': 'down'}, focus
        assert page.get_by_role('button', name='Move up', exact=True).first.is_disabled()
        assert page.get_by_role('button', name='Move down', exact=True).nth(2).is_disabled()
        page.click('#undoWorkflow'); page.wait_for_function('(expected) => JSON.stringify(WorkflowStudio.snapshot().steps.map(step => step.id)) === JSON.stringify(expected)', arg=before_order)
        page.click('#redoWorkflow'); page.wait_for_function('(expected) => JSON.stringify(WorkflowStudio.snapshot().steps.map(step => step.id)) === JSON.stringify(expected)', arg=reordered)
        page.get_by_role('button', name='Move down', exact=True).nth(1).click()
        page.wait_for_function('(expected) => JSON.stringify(WorkflowStudio.snapshot().steps.map(step => step.id)) === JSON.stringify(expected)', arg=appended)
        assert len([1 for route_name, body in seen if route_name == PREFIX + '/reduce']) == reduce_before + 2
        page.click('#undoWorkflow'); page.wait_for_function('(expected) => JSON.stringify(WorkflowStudio.snapshot().steps.map(step => step.id)) === JSON.stringify(expected)', arg=reordered)
        page.click('#saveSharedWorkflow'); page.wait_for_function('document.querySelector(\"#sharedWorkflowState\").textContent.includes(\"r4 · saved\")')
        assert [step['id'] for step in studio._workflow_documents.get(original)['document']['steps']] == reordered
        page.click('#compileWorkflow'); page.wait_for_function('document.querySelector("#workflowStatus").textContent.includes("Connections checked")')
        page.locator('#builder').screenshot(path=str(args.out / 'workflow-steps-desktop.png'))
        page.set_viewport_size({'width': 390, 'height': 844}); page.locator('#builder').screenshot(path=str(args.out / 'workflow-steps-mobile.png'))
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile page overflow'
        page.get_by_role('button', name='Edit step', exact=True).first.click(); page.keyboard.press('Escape')
        assert not page.locator('dialog').is_visible()
        assert not any(path in ('/api/jobs', '/api/workflow-studio/run') for path, _ in seen)
        assert not errors, errors
        evidence = {'browser': 'inert Chromium DOM', 'synthetic_nodes': True, 'real_sqlite_service': True,
                    'page_errors': errors, 'generation_requests': 0, 'requests': len(seen), 'saved_workflows': 2,
                    'checks': 'step form/settings/toggle/three-step duplicate/interior-and-end order/keyboard/focus/undo/redo, changed saved order, graph invariance, stale agent conflict, separate copy, open/history/restore, 390px overflow, Escape'}
        (args.out / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n'); print(json.dumps(evidence)); browser.close()


if __name__ == '__main__': main()
