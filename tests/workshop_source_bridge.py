"""Production workshop source-state bridge regression.

Runs the exact presentation scripts against the deterministic no-generation fixture.
No API, model or ComfyUI process is connected.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import shutil

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def immersive_css() -> str:
    css = (ROOT / 'app/static/workshop-immersive.css').read_text(encoding='utf-8')
    for name in ('night-shift.svg', 'quiet-morning.svg'):
        data = base64.b64encode((ROOT / 'app/static/workshop-assets' / name).read_bytes()).decode('ascii')
        css = css.replace(f'/static/workshop-assets/{name}', f'data:image/svg+xml;base64,{data}')
    return css


def load(page):
    html = (ROOT / 'tests/workshop_fixture.html').read_text(encoding='utf-8')
    html = html.replace(
        '<script src="/static/workshop.js"></script>',
        '<script>' + (ROOT / 'app/static/presentation-context.js').read_text(encoding='utf-8').replace('</script', '<\\/script') + '</script>'
        + '<script>' + (ROOT / 'app/static/workshop.js').read_text(encoding='utf-8').replace('</script', '<\\/script') + '</script>',
    )
    styles = (
        '<style id="workshopStyles">' + (ROOT / 'app/static/workshop.css').read_text(encoding='utf-8') + '</style>'
        '<style id="workshopImmersiveStyles">' + immersive_css() + '</style>'
    )
    html = html.replace('</style>', '</style>' + styles, 1)
    page.set_content(html)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / '.runtime/workshop-source-bridge')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    checks, errors, requests = [], [], []
    with sync_playwright() as playwright:
        executable = os.environ.get('STUDIO_BROWSER_EXECUTABLE') or shutil.which('chromium')
        browser = playwright.chromium.launch(**({'executable_path': executable} if executable else {}))
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: requests.append(request.url) if request.url.startswith(('http:', 'https:', 'ws:', 'wss:')) else None)
        load(page)
        page.wait_for_selector('#workshopRecipeChange')

        page.evaluate("""() => {
          selected = {
            id:'combine-fixture', name:'Combine fixture',
            reference_slots:[{id:'pose', role:'Pose picture'}],
            reference_board:{min:1},
            last_reference:true,
            last_reference_label:'Picture to keep (image 1)',
            defaults:{positive:document.querySelector('#positive').value, negative:document.querySelector('#negative').value}
          };
          referenceRecords = [{role:'pose', file:'pose.png', missing:false}];
          uploaded = null; lastUploaded = null; window.parentAssets = [];
          document.dispatchEvent(new Event('studio:recipe'));
        }""")
        page.wait_for_timeout(50)
        missing_keep = page.evaluate("createView.__workshop.presentationView().sourceSummary")
        assert [slot['id'] for slot in missing_keep['missing']] == ['last-reference'], missing_keep
        assert [item['slotId'] for item in missing_keep['provided']] == ['pose'], missing_keep

        page.evaluate("lastUploaded='keep.png';document.dispatchEvent(new Event('studio:recipe'))")
        page.wait_for_timeout(50)
        supplied_keep = page.evaluate("createView.__workshop.presentationView().sourceSummary")
        assert {item['slotId'] for item in supplied_keep['provided']} == {'pose', 'last-reference'}, supplied_keep
        checks.append({'name': 'board and picture-to-keep are represented as distinct source slots'})

        for state in ['last-uploaded', 'missing-record', 'parent-asset']:
            page.evaluate("""state => {
              selected = {
                id:'source-confirm-'+state, name:'Source confirmation fixture',
                reference_slots:[{id:'pose', role:'Pose picture'}],
                reference_board:{min:1}, last_reference:true,
                defaults:{positive:document.querySelector('#positive').value, negative:document.querySelector('#negative').value}
              };
              uploaded = null;
              lastUploaded = state === 'last-uploaded' ? 'keep.png' : null;
              referenceRecords = state === 'missing-record'
                ? [{role:'pose', file:'missing.png', missing:true}]
                : [{role:'pose', file:null, missing:false}];
              window.parentAssets = state === 'parent-asset' ? ['asset-1'] : [];
              window.confirmCalls = 0;
              window.confirm = () => { window.confirmCalls++; return false; };
              document.dispatchEvent(new Event('studio:recipe'));
            }""", state)
            before_selection = page.evaluate('selectionCount')
            page.locator('#workshopRecipeChange').click()
            page.locator('[data-id="ink"]').click()
            assert page.evaluate('confirmCalls') == 1, state
            assert page.evaluate('selectionCount') == before_selection, state
            assert page.evaluate('selected.id') == 'source-confirm-' + state, state
            page.keyboard.press('Escape')
        checks.append({'name': 'every carried source state preserves recipe-replacement confirmation'})

        page.evaluate("""() => {
          selected = {
            id:'secondary-copy', name:'Secondary copy fixture',
            reference_slots:[{id:'pose', role:'Pose picture', required:true}],
            defaults:{positive:document.querySelector('#positive').value, negative:document.querySelector('#negative').value}
          };
          referenceRecords = []; uploaded = null; lastUploaded = null; window.parentAssets = [];
          document.querySelector('#uxBlockers .ux-blocker p').textContent =
            'Install the selected local model before generating.';
          document.querySelector('#generate').disabled = true;
          document.dispatchEvent(new Event('studio:recipe'));
        }""")
        page.wait_for_timeout(50)
        assert page.locator('#workshopGuidanceTitle').inner_text() == 'Review the source roles'
        secondary = page.locator('.wk-guidance-secondary').inner_text()
        assert 'Install the selected local model before generating.' in secondary, secondary
        checks.append({'name': 'secondary guidance retains the exact readiness description'})

        assert page.evaluate('submitted') == 0
        assert not errors, errors
        assert not requests, requests
        page.screenshot(path=str(args.output / 'source-bridge.png'), full_page=True)
        browser.close()

    report = {
        'fixture': 'workshop_fixture.html',
        'live_comfyui': False,
        'checks': checks,
        'page_errors': errors,
        'network_requests': requests,
        'job_submissions': 0,
    }
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
